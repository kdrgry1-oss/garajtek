"""
integrations_birfatura.py — BirFatura (birfatura.com) e-Fatura / e-Arşiv "Özel Entegrasyon".

BirFatura ÇEKME modeliyle çalışır (bkz. services/birfatura.py başlığı — sözleşme + kaynaklar):

  BirFatura'nın çağırdığı uçlar (token = `token` HTTP başlığı, panelde "API Şifresi"):
    POST /api/birfatura/api/orderStatus
    POST /api/birfatura/api/paymentMethods
    POST /api/birfatura/api/orders
    POST /api/birfatura/api/invoiceLinkUpdate
    POST /api/birfatura/api/orderCargoUpdate
  BirFatura panelindeki "site adresi" = {PUBLIC_API_URL}/api/birfatura (BirFatura sabit
  `/api/...` yollarını kendisi ekler).

  Panel (admin) uçları:
    GET  /api/integrations/birfatura/settings
    PUT  /api/integrations/birfatura/settings
    POST /api/integrations/birfatura/token        → yeni token (yalnız BU yanıtta düz metin)
    POST /api/integrations/birfatura/test         → uçları token ile içeriden çalıştırır
    GET  /api/integrations/birfatura/logs         → son BirFatura çağrıları

  Doğrudan fatura kesimi (OutEBelgeV2 — bkz. services/birfatura_out.py):
    PUT  /api/integrations/birfatura/out/settings          → anahtarlar (yalnız yazılır), ortam
    POST /api/integrations/birfatura/out/test              → GetNumberOfCredits (kalan kontör)
    GET  /api/integrations/birfatura/out/status            → {configured} (sipariş ekranı)
    GET  /api/integrations/birfatura/invoices/{id}/preview → tutar, alıcı, e-Arşiv/e-Fatura tahmini
    POST /api/integrations/birfatura/invoices/{id}         → faturayı keser (idempotent; 409)
    POST /api/integrations/birfatura/invoices/{id}/pdf     → PDF linkini yeniden sorgular

Güvenlik: entegrasyon kapalı ya da token yokken uçlar 404 (varlık sızmaz); token sabit-süreli
karşılaştırılır (hmac.compare_digest); aynı IP'den dakikada 10 hatalı token → 429. Token
veritabanında security.crypto ile ŞİFRELİ saklanır, hiçbir yanıta/loga yazılmaz.
"""
import hmac
import json
import os
import random
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .deps import db, logger, require_permission, client_ip_from_request
from services import birfatura as bf
from services import birfatura_out as bfo

SETTINGS_ID = "birfatura"
PERM = "integrations.birfatura"
LOG_COLLECTION = "birfatura_logs"
LOG_RETENTION_DAYS = 30
MAX_ORDERS_PER_PULL = 2000
_FAILED_AUTH_PER_MINUTE = 10

public_router = APIRouter(prefix="/birfatura/api", tags=["BirFatura (public)"])
admin_router = APIRouter(prefix="/integrations/birfatura", tags=["BirFatura (admin)"])

_failed_auth: dict = defaultdict(deque)


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------
def _reply(body: dict, status: int = 200) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def _msg(success: bool, message: str, status: int) -> JSONResponse:
    return _reply({"Success": success, "Message": message}, status)


async def _load_settings() -> dict:
    doc = await db.settings.find_one({"id": SETTINGS_ID}, {"_id": 0}) or {}
    return bf.merged_settings(doc)


def _decrypt_token(settings: dict) -> Optional[str]:
    enc = settings.get("token_enc")
    if not enc:
        return None
    try:
        from security.crypto import decrypt
        return decrypt(enc) or None
    except Exception:
        logger.error("[birfatura] token çözülemedi (SECRETS_MASTER_KEY değişmiş olabilir)")
        return None


def public_base_url(request: Optional[Request] = None) -> str:
    base = (os.environ.get("PUBLIC_API_URL") or os.environ.get("BACKEND_URL")
            or os.environ.get("SITE_URL") or "").strip().rstrip("/")
    if not base and request is not None:
        base = str(request.base_url).rstrip("/")
    return base


def endpoint_urls(base: str) -> dict:
    site = f"{base}/api/birfatura"
    return {
        "site_address": site,
        "order_status": f"{site}/api/orderStatus",
        "payment_methods": f"{site}/api/paymentMethods",
        "orders": f"{site}/api/orders",
        "invoice_link_update": f"{site}/api/invoiceLinkUpdate",
        "order_cargo_update": f"{site}/api/orderCargoUpdate",
    }


async def _log_call(endpoint: str, status: int, ip: str, started: float, message: str = "",
                    count: Optional[int] = None, source: str = "birfatura"):
    try:
        await db[LOG_COLLECTION].insert_one({
            "id": str(uuid.uuid4()), "at": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint, "status": int(status), "ip": (ip or "")[:64],
            "duration_ms": int((time.monotonic() - started) * 1000),
            "message": str(message or "")[:500], "count": count, "source": source,
        })
        if status < 400 and source == "birfatura":
            await db.settings.update_one({"id": SETTINGS_ID}, {"$set": {
                "last_call_at": datetime.now(timezone.utc).isoformat(), "last_call_endpoint": endpoint}})
        if random.random() < 0.05:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=LOG_RETENTION_DAYS)).isoformat()
            await db[LOG_COLLECTION].delete_many({"at": {"$lt": cutoff}})
    except Exception as e:  # loglama isteği asla bozmaz
        logger.warning(f"[birfatura] log yazılamadı: {e}")


def _too_many_failures(ip: str) -> bool:
    dq = _failed_auth[ip]
    now = time.monotonic()
    while dq and now - dq[0] > 60:
        dq.popleft()
    return len(dq) >= _FAILED_AUTH_PER_MINUTE


async def _guard(request: Request, endpoint: str):
    """(settings, None) ya da (None, hata yanıtı). Sıra: açık mı → kilit → token."""
    started = time.monotonic()
    ip = client_ip_from_request(request) or ""
    settings = await _load_settings()
    token = _decrypt_token(settings) if settings.get("enabled") else None
    if not token:
        return None, _reply({"Success": False, "Message": "Bulunamadı."}, 404)
    if _too_many_failures(ip):
        await _log_call(endpoint, 429, ip, started, "çok fazla hatalı token denemesi")
        r = _msg(False, "Çok fazla hatalı deneme. Lütfen bekleyin.", 429)
        r.headers["Retry-After"] = "60"
        return None, r
    given = request.headers.get("token") or ""
    if not given or not hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8")):
        _failed_auth[ip].append(time.monotonic())
        await _log_call(endpoint, 401, ip, started, "token yok" if not given else "token hatalı")
        return None, _msg(False, "Yetkisiz erişim (token).", 401)
    return settings, None


async def _json_body(request: Request):
    raw = await request.body()
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return None
    return data if isinstance(data, dict) else None


async def _assign_bf_order_id(order: dict) -> int:
    """W-numaralı sipariş → sayısal kısmı. Diğerleri için kalıcı sayaç (900000000+)."""
    oid = bf.numeric_order_id(order)
    if oid is not None:
        return oid
    from pymongo import ReturnDocument
    doc = await db.counters.find_one_and_update(
        {"_id": "birfatura_order_seq"}, {"$inc": {"seq": 1}}, upsert=True,
        return_document=ReturnDocument.AFTER)
    oid = 900000000 + int(doc["seq"])
    await db.orders.update_one({"id": order["id"]}, {"$set": {"birfatura_order_id": oid}})
    return oid


async def _find_order_by_ref(ref: str) -> Optional[dict]:
    proj = {"_id": 0}
    if ref.isdigit():
        o = await db.orders.find_one({"birfatura_order_id": int(ref)}, proj)
        if o:
            return o
        o = await db.orders.find_one({"order_number": f"W{ref}"}, proj)
        if o:
            return o
    return (await db.orders.find_one({"order_number": ref}, proj)
            or await db.orders.find_one({"id": ref}, proj))


async def _default_vat_rate(settings: dict):
    if settings.get("default_vat_rate") not in (None, ""):
        return settings["default_vat_rate"]
    try:
        main = await db.settings.find_one({"id": "main"}, {"_id": 0, "default_vat_rate": 1}) or {}
        if main.get("default_vat_rate") not in (None, ""):
            return main["default_vat_rate"]
    except Exception:
        pass
    return 10


async def _product_meta(orders: list) -> tuple:
    """Siparişlerdeki ürünlerin KDV oranı + kart bilgileri → (vat_map, meta)."""
    pids = list({it.get("product_id") for o in orders for it in (o.get("items") or [])
                 if isinstance(it, dict) and it.get("product_id")})
    vat_map, meta = {}, {}
    if pids:
        async for p in db.products.find({"id": {"$in": pids}}, {
                "_id": 0, "id": 1, "vat_rate": 1, "brand": 1, "name": 1, "stock_code": 1, "sku": 1,
                "urun_karti_id": 1, "csv_card_id": 1}):
            meta[p["id"]] = p
            if p.get("vat_rate") not in (None, ""):
                vat_map[p["id"]] = p["vat_rate"]
    return vat_map, meta


async def collect_orders(settings: dict, status_id: int, start: datetime, end: datetime,
                         site_url: str = "") -> tuple:
    """Durum grubu + tarih aralığındaki siparişleri sözleşme biçiminde döndürür.
    Döner: (orders, skipped[{order_number, reason}])."""
    statuses = bf.statuses_for_group(settings, status_id)
    if not statuses:
        return [], []
    field = "updated_at" if settings.get("date_field") == "updated_at" else "created_at"
    # ISO-string ön filtre (gün sınırı, gevşek) + Python'da kesin aralık kontrolü.
    lo = (start - timedelta(days=1)).date().isoformat()
    hi = (end + timedelta(days=2)).date().isoformat()
    query = {"status": {"$in": statuses}, field: {"$gte": lo, "$lt": hi}}
    raw = await db.orders.find(query, {"_id": 0}).sort(field, 1).to_list(MAX_ORDERS_PER_PULL * 2)

    picked, skipped = [], []
    for o in raw:
        dt = bf.parse_any_dt(o.get(field))
        if not dt or dt < start or dt > end:
            continue
        reason = bf.skip_reason(o, settings)
        if reason:
            skipped.append({"order_number": o.get("order_number"), "reason": reason})
            continue
        picked.append(o)
        if len(picked) >= MAX_ORDERS_PER_PULL:
            break

    vat_map, meta = await _product_meta(picked)
    dflt = await _default_vat_rate(settings)

    out = []
    for o in picked:
        try:
            oid = await _assign_bf_order_id(o)
            m = bf.map_order(o, settings, vat_map=vat_map, default_vat_rate=dflt,
                             product_meta=meta, site_url=site_url, bf_order_id=oid)
        except Exception as e:
            logger.exception(f"[birfatura] sipariş eşlenemedi {o.get('order_number')}: {e}")
            skipped.append({"order_number": o.get("order_number"), "reason": "eşleme hatası"})
            continue
        bad = bf.violations(m)
        if bad:
            skipped.append({"order_number": o.get("order_number"),
                            "reason": "zorunlu alan boş: " + ", ".join(bad)})
            continue
        out.append(m)
    return out, skipped


# ---------------------------------------------------------------------------
# BirFatura'nın çağırdığı uçlar
# ---------------------------------------------------------------------------
@public_router.api_route("/orderStatus", methods=["POST", "GET"])
async def bf_order_status(request: Request):
    started = time.monotonic()
    settings, err = await _guard(request, "orderStatus")
    if err:
        return err
    data = bf.status_dictionary(settings)
    await _log_call("orderStatus", 200, client_ip_from_request(request), started, count=len(data))
    return _reply({"OrderStatus": data})


@public_router.api_route("/paymentMethods", methods=["POST", "GET"])
async def bf_payment_methods(request: Request):
    started = time.monotonic()
    settings, err = await _guard(request, "paymentMethods")
    if err:
        return err
    await _log_call("paymentMethods", 200, client_ip_from_request(request), started,
                    count=len(bf.PAYMENT_METHODS))
    return _reply({"PaymentMethods": bf.PAYMENT_METHODS})


@public_router.post("/orders")
async def bf_orders(request: Request):
    started = time.monotonic()
    ip = client_ip_from_request(request)
    settings, err = await _guard(request, "orders")
    if err:
        return err
    body = await _json_body(request)
    if body is None:
        await _log_call("orders", 400, ip, started, "gövde JSON nesnesi değil")
        return _msg(False, "İstek gövdesi geçerli bir JSON nesnesi olmalı.", 400)
    raw_sid = body.get("orderStatusId")
    try:
        if isinstance(raw_sid, bool):
            raise ValueError
        status_id = int(str(raw_sid).strip())
    except Exception:
        await _log_call("orders", 422, ip, started, "orderStatusId geçersiz")
        return _msg(False, "orderStatusId geçersiz.", 422)
    start = bf.parse_bf_date(body.get("startDateTime"))
    end = bf.parse_bf_date(body.get("endDateTime"))
    if not start or not end:
        await _log_call("orders", 422, ip, started, "tarih biçimi geçersiz")
        return _msg(False, "startDateTime/endDateTime 'dd.MM.yyyy HH:mm:ss' biçiminde olmalı.", 422)
    if end < start:
        await _log_call("orders", 422, ip, started, "tarih aralığı ters")
        return _msg(False, "endDateTime, startDateTime'dan önce olamaz.", 422)
    max_days = max(1, int(settings.get("max_window_days") or 31))
    if (end - start).total_seconds() > max_days * 86400:
        await _log_call("orders", 422, ip, started, "tarih aralığı çok geniş")
        return _msg(False, f"Tarih aralığı en fazla {max_days} gün olabilir.", 422)

    orders, skipped = await collect_orders(settings, status_id, start, end, site_url=_site_url())
    note = f"durum={status_id} {body.get('startDateTime')} → {body.get('endDateTime')}"
    if skipped:
        note += f" · atlanan {len(skipped)}: " + "; ".join(
            f"{s.get('order_number')} ({s.get('reason')})" for s in skipped[:10])
    await _log_call("orders", 200, ip, started, note, count=len(orders))
    return _reply({"Orders": orders})


def _site_url() -> str:
    return (os.environ.get("SITE_URL") or os.environ.get("FRONTEND_PUBLIC_URL") or "").strip().rstrip("/")


@public_router.post("/invoiceLinkUpdate")
async def bf_invoice_link_update(request: Request):
    started = time.monotonic()
    ip = client_ip_from_request(request)
    settings, err = await _guard(request, "invoiceLinkUpdate")
    if err:
        return err
    body = await _json_body(request)
    if body is None:
        await _log_call("invoiceLinkUpdate", 400, ip, started, "gövde JSON nesnesi değil")
        return _msg(False, "İstek gövdesi geçerli bir JSON nesnesi olmalı.", 400)
    ref = bf.clean_order_ref(body.get("orderId"))
    url = str(body.get("faturaUrl") or "").strip()
    raw_no = body.get("faturaNo")
    number = bf.safe_text(raw_no, 64)
    raw_date = body.get("faturaTarihi")
    inv_dt = bf.parse_bf_date(raw_date) if raw_date not in (None, "") else None
    if not ref:
        await _log_call("invoiceLinkUpdate", 422, ip, started, "orderId geçersiz")
        return _msg(False, "orderId geçersiz.", 422)
    if raw_no not in (None, "") and number is None:
        await _log_call("invoiceLinkUpdate", 422, ip, started, f"faturaNo geçersiz ({ref})")
        return _msg(False, "faturaNo geçersiz.", 422)
    if raw_date not in (None, "") and inv_dt is None:
        await _log_call("invoiceLinkUpdate", 422, ip, started, f"faturaTarihi geçersiz ({ref})")
        return _msg(False, "faturaTarihi 'dd.MM.yyyy HH:mm:ss' biçiminde olmalı.", 422)
    if not url or len(url) > 2000 or not bf.host_allowed(url, settings.get("trusted_invoice_hosts") or []):
        await _log_call("invoiceLinkUpdate", 422, ip, started, f"faturaUrl reddedildi ({ref}): güvenilen host değil")
        return _msg(False, "faturaUrl geçersiz (yalnız https ve güvenilen BirFatura adresleri).", 422)

    order = await _find_order_by_ref(ref)
    if not order:
        await _log_call("invoiceLinkUpdate", 404, ip, started, f"sipariş bulunamadı ({ref})")
        return _msg(False, "Sipariş bulunamadı.", 404)

    now = datetime.now(timezone.utc).isoformat()
    issued_at = inv_dt.isoformat() if inv_dt else (order.get("invoice_issued_at") or now)
    same = (order.get("invoice_provider") == "birfatura"
            and (order.get("invoice_pdf_url") or "") == url
            and (order.get("invoice_number") or "") == (number or order.get("invoice_number") or ""))
    if same:  # idempotent: BirFatura aynı güncellemeyi tekrar gönderebilir
        await _log_call("invoiceLinkUpdate", 200, ip, started, f"{order.get('order_number')}: değişiklik yok")
        return _msg(True, "Fatura bağlantısı güncellendi.", 200)

    update = {
        "invoice_issued": True,
        "invoice_provider": "birfatura",
        "invoice_pdf_url": url,
        "invoice_issued_at": issued_at,
        "invoice_issued_by": "BirFatura",
        "invoice_last_error": "",
        "invoice_in_progress": False,
        "birfatura_invoice": {"number": number, "url": url, "date": issued_at, "received_at": now},
        "updated_at": now,
    }
    if number:
        update["invoice_number"] = number
    push = {}
    if order.get("invoice_issued") and order.get("invoice_number") and \
            (order.get("invoice_number") != number or order.get("invoice_provider") != "birfatura"):
        push = {"invoice_history": {"number": order.get("invoice_number"),
                                    "provider": order.get("invoice_provider") or "",
                                    "url": order.get("invoice_pdf_url") or "",
                                    "replaced_at": now}}
    upd = {"$set": update}
    if push:
        upd["$push"] = push
    await db.orders.update_one({"id": order["id"]}, upd)
    try:
        await db.order_events.insert_one({
            "id": str(uuid.uuid4()), "order_id": order["id"],
            "order_number": order.get("order_number") or "", "event_type": "invoice",
            "description": f"BirFatura faturası işlendi: {number or '-'}",
            "actor": "BirFatura", "meta": {"invoice_number": number, "provider": "birfatura"},
            "created_at": now,
        })
    except Exception:
        pass
    await _log_call("invoiceLinkUpdate", 200, ip, started, f"{order.get('order_number')}: {number or '-'}")
    return _msg(True, "Fatura bağlantısı güncellendi.", 200)


@public_router.post("/orderCargoUpdate")
async def bf_order_cargo_update(request: Request):
    started = time.monotonic()
    ip = client_ip_from_request(request)
    settings, err = await _guard(request, "orderCargoUpdate")
    if err:
        return err
    body = await _json_body(request)
    if body is None:
        await _log_call("orderCargoUpdate", 400, ip, started, "gövde JSON nesnesi değil")
        return _msg(False, "İstek gövdesi geçerli bir JSON nesnesi olmalı.", 400)
    ref = bf.clean_order_ref(body.get("orderId"))
    code = bf.safe_text(body.get("cargoTrackingCode"), 64)
    turl = str(body.get("cargoTrackingCodeUrl") or "").strip()
    company = bf.safe_text(body.get("cargoCompany"), 100)
    if not ref or not code:
        await _log_call("orderCargoUpdate", 422, ip, started, "orderId/cargoTrackingCode geçersiz")
        return _msg(False, "orderId ve cargoTrackingCode zorunlu.", 422)
    if turl and (not turl.startswith(("https://", "http://")) or len(turl) > 2000):
        turl = ""
    order = await _find_order_by_ref(ref)
    if not order:
        await _log_call("orderCargoUpdate", 404, ip, started, f"sipariş bulunamadı ({ref})")
        return _msg(False, "Sipariş bulunamadı.", 404)
    now = datetime.now(timezone.utc).isoformat()
    upd = {"birfatura_cargo": {"tracking_code": code, "tracking_url": turl or None, "company": company,
                               "status_id": body.get("orderStatusId"),
                               "update_time": str(body.get("updateDateTime") or "")[:19], "received_at": now}}
    # Kargo bilgisi siparişin kendi kargo alanlarına YALNIZ boşsa yazılır (kendi kargo
    # entegrasyonumuzun verisinin üstüne yazılmaz). Durum değiştirilmez (bildirim akışları
    # sipariş durum ekranına aittir).
    if settings.get("store_cargo_updates", True) and not (order.get("cargo_tracking_number") or "").strip():
        upd["cargo_tracking_number"] = code
        if company and not order.get("cargo_provider_name"):
            upd["cargo_provider_name"] = company
        if turl and not order.get("cargo_tracking_link"):
            upd["cargo_tracking_link"] = turl
    await db.orders.update_one({"id": order["id"]}, {"$set": upd})
    await _log_call("orderCargoUpdate", 200, ip, started, f"{order.get('order_number')}: {code}")
    return _msg(True, "Kargo bilgisi güncellendi.", 200)


# ---------------------------------------------------------------------------
# Panel (admin) uçları
# ---------------------------------------------------------------------------
_PUBLIC_SETTING_KEYS = ("enabled", "status_groups", "date_field", "discount_mode", "default_vat_rate",
                        "shipping_vat_rate", "service_vat_rate", "default_tckn", "only_site_orders",
                        "skip_invoiced_elsewhere", "max_window_days", "trusted_invoice_hosts",
                        "store_cargo_updates", "invoice_explanation")


def _public_view(settings: dict, request: Request) -> dict:
    out = {k: settings.get(k) for k in _PUBLIC_SETTING_KEYS}
    out["has_token"] = bool(settings.get("token_enc"))
    out["token_hint"] = settings.get("token_hint") or ""
    out["token_created_at"] = settings.get("token_created_at") or ""
    out["last_call_at"] = settings.get("last_call_at") or ""
    out["last_call_endpoint"] = settings.get("last_call_endpoint") or ""
    out["urls"] = endpoint_urls(public_base_url(request))
    out["payment_methods"] = bf.PAYMENT_METHODS
    try:
        from order_statuses import ORDER_STATUS_CATALOG
        out["status_catalog"] = [{"key": s["key"], "label": s["label"]} for s in ORDER_STATUS_CATALOG]
    except Exception:
        out["status_catalog"] = []
    out["out"] = _out_public_view(settings)
    return out


@admin_router.get("/settings")
async def get_birfatura_settings(request: Request, current_user: dict = Depends(require_permission(PERM))):
    return _public_view(await _load_settings(), request)


def _validate_settings(payload: dict) -> dict:
    clean = {}
    if "enabled" in payload:
        clean["enabled"] = bool(payload["enabled"])
    for k in ("only_site_orders", "skip_invoiced_elsewhere", "store_cargo_updates"):
        if k in payload:
            clean[k] = bool(payload[k])
    if "date_field" in payload:
        if payload["date_field"] not in ("created_at", "updated_at"):
            raise HTTPException(400, "date_field: created_at ya da updated_at olmalı")
        clean["date_field"] = payload["date_field"]
    if "discount_mode" in payload:
        if payload["discount_mode"] not in ("net", "line"):
            raise HTTPException(400, "discount_mode: net ya da line olmalı")
        clean["discount_mode"] = payload["discount_mode"]
    for k in ("default_vat_rate", "shipping_vat_rate", "service_vat_rate"):
        if k in payload:
            v = payload[k]
            if v in (None, "") and k == "default_vat_rate":
                clean[k] = None
                continue
            try:
                v = int(v)
            except Exception:
                raise HTTPException(400, f"{k}: 0–100 arası tamsayı olmalı")
            if not 0 <= v <= 100:
                raise HTTPException(400, f"{k}: 0–100 arası olmalı")
            clean[k] = v
    if "max_window_days" in payload:
        try:
            v = int(payload["max_window_days"])
        except Exception:
            raise HTTPException(400, "max_window_days tamsayı olmalı")
        if not 1 <= v <= 366:
            raise HTTPException(400, "max_window_days 1–366 arası olmalı")
        clean["max_window_days"] = v
    if "default_tckn" in payload:
        v = "".join(ch for ch in str(payload["default_tckn"] or "") if ch.isdigit())
        if len(v) != 11:
            raise HTTPException(400, "default_tckn 11 haneli olmalı")
        clean["default_tckn"] = v
    if "invoice_explanation" in payload:
        clean["invoice_explanation"] = str(payload["invoice_explanation"] or "")[:300]
    if "trusted_invoice_hosts" in payload:
        hosts = payload["trusted_invoice_hosts"] or []
        if isinstance(hosts, str):
            hosts = [h for h in hosts.replace(",", "\n").split("\n")]
        hosts = [str(h).strip().lower() for h in hosts if str(h).strip()]
        for h in hosts:
            if not all(c.isalnum() or c in ".-*" for c in h) or ("*" in h and not h.startswith("*.")):
                raise HTTPException(400, f"Geçersiz host: {h}")
        if not hosts:
            raise HTTPException(400, "En az bir güvenilen fatura host'u gerekli")
        clean["trusted_invoice_hosts"] = hosts[:20]
    if "status_groups" in payload:
        try:
            from order_statuses import all_status_keys
            known = set(all_status_keys())
        except Exception:
            known = None
        groups, seen = [], set()
        for g in payload["status_groups"] or []:
            try:
                gid = int(g.get("id"))
            except Exception:
                raise HTTPException(400, "Durum grubu Id'si tamsayı olmalı")
            if gid <= 0 or gid in seen:
                raise HTTPException(400, f"Durum grubu Id'si benzersiz ve pozitif olmalı ({gid})")
            seen.add(gid)
            name = str(g.get("name") or "").strip()[:80]
            if not name:
                raise HTTPException(400, f"Durum grubu {gid} için ad gerekli")
            sts = [str(s) for s in (g.get("statuses") or [])]
            if known is not None and any(s not in known for s in sts):
                raise HTTPException(400, f"Bilinmeyen sipariş durumu: {[s for s in sts if s not in known]}")
            if not sts:
                raise HTTPException(400, f"'{name}' grubunda en az bir sipariş durumu seçilmeli")
            groups.append({"id": gid, "name": name, "statuses": sts})
        if not groups:
            raise HTTPException(400, "En az bir durum grubu gerekli")
        clean["status_groups"] = groups
    return clean


async def _audit(action: str, before: dict, after: dict, current_user: dict, request: Request):
    try:
        from activity_audit import record_admin_audit
        await record_admin_audit(db, action=action, entity_type="integration", entity_id="birfatura",
                                 before=before, after=after, current_user=current_user, request=request,
                                 source="integrations.birfatura")
    except Exception:
        pass


@admin_router.put("/settings")
async def save_birfatura_settings(payload: dict, request: Request,
                                  current_user: dict = Depends(require_permission(PERM))):
    clean = _validate_settings(payload or {})
    before = await _load_settings()
    if clean.get("enabled") and not before.get("token_enc"):
        raise HTTPException(400, "Etkinleştirmeden önce bir token oluşturun.")
    clean["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one({"id": SETTINGS_ID}, {"$set": clean}, upsert=True)
    after = await _load_settings()
    strip = lambda d: {k: d.get(k) for k in _PUBLIC_SETTING_KEYS}  # noqa: E731
    await _audit("integration.birfatura.settings", strip(before), strip(after), current_user, request)
    return {"success": True, "settings": _public_view(after, request)}


@admin_router.post("/token")
async def regenerate_birfatura_token(request: Request, current_user: dict = Depends(require_permission(PERM))):
    """Yeni token (GUID) üretir. Düz değer YALNIZ bu yanıtta döner; DB'de şifreli saklanır.
    Eski token anında geçersizleşir → BirFatura panelindeki API şifresi de güncellenmeli."""
    from security.crypto import encrypt
    token = str(uuid.uuid4())
    before = await _load_settings()
    now = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one({"id": SETTINGS_ID}, {"$set": {
        "token_enc": encrypt(token), "token_hint": token[-4:], "token_created_at": now,
        "token_created_by": current_user.get("email", ""), "updated_at": now}}, upsert=True)
    await _audit("integration.birfatura.token_regenerate",
                 {"had_token": bool(before.get("token_enc"))}, {"had_token": True}, current_user, request)
    return {"success": True, "token": token, "token_hint": token[-4:], "token_created_at": now,
            "message": "Token oluşturuldu. Bu değeri şimdi kopyalayın; tekrar gösterilmez."}


@admin_router.post("/test")
async def test_birfatura(request: Request, payload: Optional[dict] = None,
                         current_user: dict = Depends(require_permission(PERM))):
    """Bağlantı testi: kayıtlı token ile sözlükleri ve sipariş çekimini (son N gün, seçili grup)
    İÇERİDEN çalıştırır (BirFatura'nın göreceği yanıtın aynısı) + genel adres erişimini dener."""
    payload = payload or {}
    started = time.monotonic()
    settings = await _load_settings()
    token = _decrypt_token(settings)
    result = {"enabled": bool(settings.get("enabled")), "has_token": bool(token), "checks": []}
    if not token:
        result["checks"].append({"name": "Token", "ok": False, "detail": "Token yok — önce token oluşturun."})
        return result
    try:
        days = max(1, min(int(payload.get("days") or 7), int(settings.get("max_window_days") or 31)))
    except Exception:
        days = 7
    groups = bf.status_dictionary(settings)
    try:
        gid = int(payload.get("status_id") or (groups[0]["Id"] if groups else 1))
    except Exception:
        gid = groups[0]["Id"] if groups else 1
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    orders, skipped = await collect_orders(settings, gid, start, end, site_url=_site_url())
    result["checks"].append({"name": "Sipariş durumları", "ok": bool(groups), "detail": f"{len(groups)} durum"})
    result["checks"].append({"name": "Siparişler", "ok": True,
                             "detail": f"son {days} gün, durum {gid}: {len(orders)} sipariş, {len(skipped)} atlandı"})
    result["request"] = {"orderStatusId": gid, "startDateTime": bf.fmt_bf_date(start),
                         "endDateTime": bf.fmt_bf_date(end)}
    result["sample"] = {"Orders": orders[:3]}
    result["skipped"] = skipped[:20]

    # Genel adres erişimi (BirFatura'nın göreceği yol). Yerel/özel ağda başarısız olabilir.
    base = public_base_url(request)
    urls = endpoint_urls(base)
    if base.startswith("http"):
        try:
            import httpx
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as c:
                r = await c.post(urls["order_status"], headers={"token": token}, json={})
            ok = r.status_code == 200 and "OrderStatus" in (r.text or "")
            detail = f"HTTP {r.status_code}"
            if not settings.get("enabled") and r.status_code == 404:
                detail += " (entegrasyon kapalı olduğu için 404 beklenir)"
            result["checks"].append({"name": "Genel adres erişimi", "ok": ok, "detail": detail,
                                     "url": urls["order_status"]})
        except Exception as e:
            result["checks"].append({"name": "Genel adres erişimi", "ok": False,
                                     "detail": f"{type(e).__name__}: {str(e)[:160]}", "url": urls["order_status"]})
    await _log_call("test", 200, client_ip_from_request(request), started,
                    f"panel testi: {len(orders)} sipariş", count=len(orders), source="panel")
    return result


@admin_router.get("/logs")
async def birfatura_logs(limit: int = 50, current_user: dict = Depends(require_permission(PERM))):
    limit = max(1, min(int(limit or 50), 200))
    rows = await db[LOG_COLLECTION].find({}, {"_id": 0}).sort("at", -1).to_list(limit)
    return {"logs": rows}


# ---------------------------------------------------------------------------
# Doğrudan fatura kesimi — BirFatura OutEBelgeV2 (services/birfatura_out.py)
# ---------------------------------------------------------------------------
INVOICE_PERM = "orders.invoice"
OUT_SECRETS = (("api_key", "X-Api-Key"), ("secret_key", "X-Secret-Key"), ("integration_key", "X-Integration-Key"))
OUT_LOCK_STALE_SECONDS = 300
OUT_TRANSPORT = None   # testler httpx.MockTransport koyar; üretimde gerçek ağ (TLS doğrulamalı)


def _out_secret(settings: dict, name: str) -> Optional[str]:
    enc = settings.get(f"out_{name}_enc")
    if not enc:
        return None
    try:
        from security.crypto import decrypt
        return decrypt(enc) or None
    except Exception:
        logger.error(f"[birfatura-out] {name} çözülemedi (SECRETS_MASTER_KEY değişmiş olabilir)")
        return None


def _out_base_url(settings: dict) -> str:
    return bfo.normalize_base_url(settings.get("out_base_url")) or bfo.DEFAULT_BASE_URL


def _out_client(settings: dict, require_enabled: bool = True) -> Optional[bfo.OutClient]:
    if require_enabled and not settings.get("out_enabled"):
        return None
    keys = [_out_secret(settings, n) for n, _ in OUT_SECRETS]
    if not all(keys):
        return None
    return bfo.OutClient(_out_base_url(settings), *keys, transport=OUT_TRANSPORT)


def _out_public_view(settings: dict) -> dict:
    """Sırlar ASLA dönmez: yalnız var/yok + son 4 hane ipucu."""
    v = {
        "enabled": bool(settings.get("out_enabled")),
        "base_url": _out_base_url(settings),
        "base_url_choices": bfo.BASE_URL_CHOICES,
        "company_vkn": settings.get("out_company_vkn") or "",
        "last_credits": settings.get("out_last_credits"),
        "last_credits_at": settings.get("out_last_credits_at") or "",
        "updated_at": settings.get("out_updated_at") or "",
    }
    for n, _ in OUT_SECRETS:
        v[f"has_{n}"] = bool(settings.get(f"out_{n}_enc"))
        v[f"{n}_hint"] = settings.get(f"out_{n}_hint") or ""
    v["configured"] = v["enabled"] and all(v[f"has_{n}"] for n, _ in OUT_SECRETS)
    return v


def _out_audit_view(settings: dict) -> dict:
    v = _out_public_view(settings)
    v.pop("base_url_choices", None)
    return v


@admin_router.put("/out/settings")
async def save_out_settings(payload: dict, request: Request,
                            current_user: dict = Depends(require_permission(PERM))):
    """Anahtarlar YALNIZ yazılır: boş/eksik alan = mevcut değer korunur; `clear_keys` hepsini siler."""
    payload = payload or {}
    before = await _load_settings()
    upd: dict = {}
    if "base_url" in payload:
        u = bfo.normalize_base_url(payload.get("base_url"))
        if not u:
            raise HTTPException(400, "Ortam adresi yalnız https://…edonustur.com ya da https://…birfatura.com olabilir.")
        upd["out_base_url"] = u
    if "company_vkn" in payload:
        v = "".join(ch for ch in str(payload.get("company_vkn") or "") if ch.isdigit())
        if v and len(v) not in (10, 11):
            raise HTTPException(400, "Firma VKN/TCKN 10 ya da 11 haneli olmalı.")
        upd["out_company_vkn"] = v
    changed = []
    from security.crypto import encrypt
    for n, label in OUT_SECRETS:
        val = payload.get(n)
        if val is None:
            continue
        val = str(val).strip()
        if not val:
            continue
        if len(val) > 512 or any(ord(ch) <= 32 or ord(ch) == 127 for ch in val):
            raise HTTPException(400, f"{label} geçersiz (boşluk/kontrol karakteri içeremez, en fazla 512 karakter).")
        upd[f"out_{n}_enc"] = encrypt(val)
        upd[f"out_{n}_hint"] = bfo.secret_hint(val)
        changed.append(n)
    if payload.get("clear_keys"):
        for n, _ in OUT_SECRETS:
            upd[f"out_{n}_enc"] = None
            upd[f"out_{n}_hint"] = ""
        upd["out_enabled"] = False
        changed = [n for n, _ in OUT_SECRETS]
    elif "enabled" in payload:
        en = bool(payload.get("enabled"))
        if en:
            merged = {**before, **upd}
            if not all(merged.get(f"out_{n}_enc") for n, _ in OUT_SECRETS):
                raise HTTPException(400, "Açmadan önce X-Api-Key, X-Secret-Key ve X-Integration-Key'in üçünü de girin.")
        upd["out_enabled"] = en
    now = datetime.now(timezone.utc).isoformat()
    upd["out_updated_at"] = now
    upd["out_updated_by"] = current_user.get("email", "")
    await db.settings.update_one({"id": SETTINGS_ID}, {"$set": upd}, upsert=True)
    after = await _load_settings()
    try:
        from activity_audit import record_admin_audit
        await record_admin_audit(db, action="integration.birfatura.out_settings", entity_type="integration",
                                 entity_id="birfatura", before=_out_audit_view(before),
                                 after=_out_audit_view(after), current_user=current_user, request=request,
                                 source="integrations.birfatura", metadata={"keys_changed": changed})
    except Exception:
        pass
    return {"success": True, "out": _out_public_view(after)}


@admin_router.post("/out/test")
async def test_out_connection(request: Request, current_user: dict = Depends(require_permission(PERM))):
    """Bağlantı testi: GetNumberOfCredits → kalan kontör. Açık olması gerekmez (önce test, sonra aç)."""
    started = time.monotonic()
    ip = client_ip_from_request(request)
    settings = await _load_settings()
    client = _out_client(settings, require_enabled=False)
    if not client:
        return {"ok": False, "detail": "Önce X-Api-Key, X-Secret-Key ve X-Integration-Key'i kaydedin."}
    try:
        credits = await client.get_credits(settings.get("out_company_vkn") or "")
    except bfo.OutError as e:
        await _log_call("out:GetNumberOfCredits", e.status or 502, ip, started, e.message, source="panel")
        return {"ok": False, "detail": e.message, "base_url": client.base_url}
    now = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one({"id": SETTINGS_ID}, {"$set": {"out_last_credits": credits,
                                                                "out_last_credits_at": now}})
    await _log_call("out:GetNumberOfCredits", 200, ip, started, f"kalan kontör: {credits}", source="panel")
    return {"ok": True, "credits": credits, "base_url": client.base_url, "checked_at": now}


@admin_router.get("/out/status")
async def out_status(current_user: dict = Depends(require_permission("orders.view"))):
    """Sipariş ekranı: doğrudan kesim yapılandırılmış mı? (sır dönmez)"""
    settings = await _load_settings()
    return {"configured": bool(_out_client(settings)), "provider": bfo.PROVIDER}


async def _prepare_invoice(order: dict, settings: dict, client: bfo.OutClient, ettn: str,
                           *, tolerate_lookup_errors: bool = False) -> dict:
    """Fatura modelini kurar ve alıcının e-Fatura mükellefiyetini GetUserPK ile belirler."""
    vat_map, meta = await _product_meta([order])
    dflt = await _default_vat_rate(settings)
    kw = dict(vat_map=vat_map, default_vat_rate=dflt, product_meta=meta)
    inv = bfo.build_invoice(order, settings, ettn=ettn, **kw)
    tax_no = inv.get("taxNo") or ""
    system, tag, source, lookup_error = bfo.SYSTEM_EARSIV, None, "bireysel", None
    if bfo.should_query_user(tax_no, settings):
        try:
            is_e, tag = bfo.pick_receiver(await client.get_user_pk(tax_no))
            system = bfo.SYSTEM_EFATURA if is_e else bfo.SYSTEM_EARSIV
            source = "gib"
        except bfo.OutError as e:
            if not tolerate_lookup_errors:
                raise
            system, source, lookup_error = None, "bilinmiyor", e.message
    if tag:
        inv = bfo.build_invoice(order, settings, ettn=ettn, receiver_tag=tag, **kw)
    problems = [f"Zorunlu alan boş: {f}." for f in bfo.violations(inv)] + bfo.total_problems(order, inv)
    return {"invoice": inv, "system_type": system, "receiver_tag": tag, "type_source": source,
            "lookup_error": lookup_error, "problems": problems}


def _http_error(status: int, detail: str, **extra) -> JSONResponse:
    return JSONResponse({"detail": detail, **extra}, status_code=status, headers={"Cache-Control": "no-store"})


async def _order_event(order: dict, description: str, current_user: dict, meta: dict):
    try:
        await db.order_events.insert_one({
            "id": str(uuid.uuid4()), "order_id": order["id"],
            "order_number": order.get("order_number") or "", "event_type": "invoice",
            "description": description, "actor": (current_user or {}).get("email", ""),
            "meta": meta, "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


async def _order_audit(order: dict, action: str, before: dict, after: dict, current_user: dict,
                       request: Request, success: bool = True, metadata: Optional[dict] = None):
    try:
        from activity_audit import record_admin_audit
        await record_admin_audit(db, action=action, entity_type="order", entity_id=order["id"],
                                 before=before, after=after, current_user=current_user, request=request,
                                 source="integrations.birfatura", success=success,
                                 metadata={"order_number": order.get("order_number"), **(metadata or {})})
    except Exception:
        pass


@admin_router.get("/invoices/{order_id}/preview")
async def preview_out_invoice(order_id: str, current_user: dict = Depends(require_permission(INVOICE_PERM))):
    """Onay penceresi: tutar, alıcı, e-Arşiv/e-Fatura tahmini, engeller. Fatura KESMEZ."""
    settings = await _load_settings()
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")
    client = _out_client(settings)
    res = {"configured": bool(client), "order_number": order.get("order_number") or "",
           "existing": bfo.existing_invoice(order), "blocked": bfo.block_reason(order),
           "maybe_sent": bool(order.get("birfatura_out_maybe_sent")),
           "order_total": bf.num(bfo.expected_total(order))}
    if not client or res["existing"]:
        return res
    try:
        p = await _prepare_invoice(order, settings, client, order.get("birfatura_out_ettn") or bfo.new_ettn(),
                                   tolerate_lookup_errors=True)
    except Exception as e:
        logger.exception(f"[birfatura-out] önizleme hatası {order.get('order_number')}: {e}")
        res["problems"] = ["Fatura modeli oluşturulamadı (sipariş verisi eksik/bozuk)."]
        return res
    res.update(bfo.summary(p["invoice"], p["system_type"]))
    res.update({"receiver_tag": p["receiver_tag"], "type_source": p["type_source"],
                "lookup_error": p["lookup_error"], "problems": p["problems"]})
    return res


@admin_router.post("/invoices/{order_id}")
async def issue_out_invoice(order_id: str, request: Request,
                            current_user: dict = Depends(require_permission(INVOICE_PERM))):
    """Siparişe BirFatura OutEBelgeV2 ile e-Fatura / e-Arşiv keser.

    İdempotent: sipariş zaten faturalıysa 409 + mevcut fatura. Aynı anda iki kesim kilitle
    engellenir; ETTN siparişe ÖNCE yazılır ve yeniden denemede AYNI ETTN kullanılır (zaman aşımında
    fatura kesilmiş olabilir — aynı ETTN ikinci kez resmîleşemez)."""
    started = time.monotonic()
    ip = client_ip_from_request(request)
    settings = await _load_settings()
    client = _out_client(settings)
    if not client:
        return _http_error(400, "Doğrudan fatura kesimi yapılandırılmamış (BirFatura → Doğrudan Fatura Kesme).")
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        return _http_error(404, "Sipariş bulunamadı")
    existing = bfo.existing_invoice(order)
    if existing:
        no = existing["invoice_number"]
        return _http_error(409, f"Bu siparişin faturası zaten kesilmiş{': ' + no if no else ''}.", invoice=existing)
    reason = bfo.block_reason(order)
    if reason:
        return _http_error(400, reason)

    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    stale = (now_dt - timedelta(seconds=OUT_LOCK_STALE_SECONDS)).isoformat()
    ettn = order.get("birfatura_out_ettn") or bfo.new_ettn()
    lock = await db.orders.update_one(
        {"id": order_id, "invoice_issued": {"$ne": True},
         "$or": [{"birfatura_out_lock": {"$exists": False}}, {"birfatura_out_lock": None},
                 {"birfatura_out_lock": ""}, {"birfatura_out_lock": {"$lt": stale}}]},
        {"$set": {"birfatura_out_lock": now, "birfatura_out_ettn": ettn}})
    if not getattr(lock, "matched_count", 0):
        return _http_error(409, "Bu sipariş için fatura kesimi zaten sürüyor. Birkaç saniye sonra sayfayı yenileyin.")

    async def fail(status: int, msg: str, *, maybe_sent: bool = False, op: str = "SendBasicInvoiceFromModel"):
        upd = {"birfatura_out_lock": None, "invoice_last_error": msg,
               "invoice_last_error_at": datetime.now(timezone.utc).isoformat()}
        if maybe_sent:
            upd["birfatura_out_maybe_sent"] = True
        await db.orders.update_one({"id": order_id}, {"$set": upd})
        await _log_call(f"out:{op}", status, ip, started, f"{order.get('order_number')}: {msg}", source="panel")
        await _order_audit(order, "order.invoice.birfatura_out", {"invoice_issued": False},
                           {"invoice_issued": False}, current_user, request, success=False,
                           metadata={"error": msg[:300], "maybe_sent": maybe_sent})
        return _http_error(status, msg, maybe_sent=maybe_sent)

    try:
        p = await _prepare_invoice(order, settings, client, ettn)
    except bfo.OutError as e:
        return await fail(502, f"Alıcının e-Fatura mükellefiyeti sorgulanamadı: {e.message}", op="GetUserPK")
    except Exception as e:
        logger.exception(f"[birfatura-out] model hatası {order.get('order_number')}: {e}")
        return await fail(422, "Fatura modeli oluşturulamadı (sipariş verisi eksik/bozuk).", op="model")
    if p["problems"]:
        return await fail(422, "Fatura kesilmedi: " + " ".join(p["problems"]), op="model")

    inv, system = p["invoice"], p["system_type"]
    try:
        result = await client.send_basic_invoice(inv)
    except bfo.OutError as e:
        msg = e.message
        if e.maybe_sent:
            msg += (" Fatura kesilmiş olabilir — BirFatura panelinden kontrol edin. Tekrar denerseniz aynı"
                    f" ETTN ({ettn}) ile gönderilir.")
        return await fail(502, msg, maybe_sent=e.maybe_sent)

    inv_no = bf.safe_text(result.get("invoiceNo"), 64) or ""
    if inv_no == "string":
        inv_no = ""
    pdf = None
    try:
        pdf = await client.get_pdf_link(ettn, system)
    except bfo.OutError as e:
        logger.warning(f"[birfatura-out] PDF linki alınamadı {order.get('order_number')}: {e.message}")
    pdf = pdf or bfo.safe_link(result.get("pdfLink")) or ""
    type_label = bfo.TYPE_LABEL[system]
    done = datetime.now(timezone.utc).isoformat()
    record = {
        "ettn": ettn, "system_type": system, "receiver_tag": p["receiver_tag"], "invoice_no": inv_no,
        "pdf_link": pdf, "pdf_pending": not pdf, "total_incl": inv.get("totalPaidTaxIncluding"),
        "total_excl": inv.get("totalPaidTaxExcluding"), "base_url": client.base_url,
        "issued_at": done, "issued_by": current_user.get("email", ""),
    }
    await db.orders.update_one({"id": order_id}, {"$set": {
        "invoice_issued": True,
        "invoice_provider": bfo.PROVIDER,
        "invoice_uuid": ettn,
        "invoice_number": inv_no,
        "invoice_pdf_url": pdf,
        "invoice_type": type_label,
        "invoice_issued_at": done,
        "invoice_issued_by": current_user.get("email", ""),
        "invoice_last_error": "",
        "invoice_in_progress": False,
        "birfatura_out_lock": None,
        "birfatura_out_maybe_sent": False,
        "birfatura_out_ettn": None,      # kullanıldı → (fatura sıfırlanırsa) sonraki kesim yeni ETTN alır
        "birfatura_out": record,
        "updated_at": done,
    }})
    kind = "e-Fatura" if system == bfo.SYSTEM_EFATURA else "e-Arşiv"
    await _order_event(order, f"BirFatura {kind} kesildi: {inv_no or ettn}", current_user,
                       {"invoice_number": inv_no, "invoice_uuid": ettn, "invoice_type": type_label,
                        "provider": bfo.PROVIDER})
    await _order_audit(order, "order.invoice.birfatura_out", {"invoice_issued": False},
                       {"invoice_issued": True, "invoice_number": inv_no, "invoice_type": type_label,
                        "invoice_uuid": ettn, "total": inv.get("totalPaidTaxIncluding")},
                       current_user, request)
    await _log_call("out:SendBasicInvoiceFromModel", 200, ip, started,
                    f"{order.get('order_number')}: {kind} {inv_no or ettn}", count=1, source="panel")
    invoice = {"invoice_number": inv_no, "invoice_uuid": ettn, "invoice_pdf_url": pdf,
               "invoice_type": type_label, "invoice_issued_at": done, "invoice_provider": bfo.PROVIDER}
    msg = f"{kind} kesildi: {inv_no or ettn}."
    if not pdf:
        msg += " PDF birkaç dakika içinde hazır olur (sipariş detayından 'PDF'i yenile')."
    return {"success": True, "invoice": invoice, "message": msg}


@admin_router.post("/invoices/{order_id}/pdf")
async def refresh_out_invoice_pdf(order_id: str, request: Request,
                                  current_user: dict = Depends(require_permission(INVOICE_PERM))):
    """Doğrudan kesilmiş faturanın PDF linkini GetPDFLinkByUUID ile yeniden sorgular."""
    started = time.monotonic()
    settings = await _load_settings()
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(404, "Sipariş bulunamadı")
    rec = order.get("birfatura_out") if isinstance(order.get("birfatura_out"), dict) else {}
    if order.get("invoice_provider") != bfo.PROVIDER or not order.get("invoice_uuid"):
        raise HTTPException(400, "Bu sipariş panelden doğrudan faturalanmamış.")
    client = _out_client(settings, require_enabled=False)
    if not client:
        raise HTTPException(400, "BirFatura API anahtarları kayıtlı değil.")
    system = rec.get("system_type") or (bfo.SYSTEM_EFATURA if order.get("invoice_type") == "e-fatura"
                                        else bfo.SYSTEM_EARSIV)
    try:
        link = await client.get_pdf_link(order["invoice_uuid"], system)
    except bfo.OutError as e:
        await _log_call("out:GetPDFLinkByUUID", e.status or 502, client_ip_from_request(request), started,
                        e.message, source="panel")
        return _http_error(502, e.message)
    if not link:
        return {"success": False, "detail": "PDF henüz hazır değil; birkaç dakika sonra tekrar deneyin."}
    await db.orders.update_one({"id": order_id}, {"$set": {
        "invoice_pdf_url": link, "birfatura_out.pdf_link": link, "birfatura_out.pdf_pending": False,
        "updated_at": datetime.now(timezone.utc).isoformat()}})
    return {"success": True, "invoice_pdf_url": link}
