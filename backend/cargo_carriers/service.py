"""
cargo_carriers/service.py — Taşıyıcıdan bağımsız sipariş kargo akışı (Aras / PTT).

  create_shipment_for_order  → barkod/gönderi kaydı + sipariş alanları (MNG akışıyla aynı şema)
  cancel_order_shipment      → kargo firmasında iptal + sipariş kargo alanlarını temizle
  refresh_order_tracking     → tek sipariş takip sorgusu + durum çevirme
  poll_tick                  → zamanlayıcı: açık Aras/PTT gönderilerini toplu senkronla

Sipariş üzerinde yazılan alanlar (Orders.jsx, etiket, müşteri takip sayfası bunları okur):
  cargo_provider_code ("ARAS"/"PTT"), cargo_provider_name, cargo_company ("Aras"/"PTT"),
  cargo_barcode_number (etiket barkodu), cargo_tracking_number (gerçek takip no; Aras'ta şube
  irsaliye kesince dolar), cargo_tracking_link, cargo_barcode_created, cargo{…}.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional

from fastapi import HTTPException

from .common import (
    CarrierError, is_cod_order, normalize_il, phone10, STATUS_LABELS_TR,
    ST_ACCEPTED, ST_IN_TRANSIT, ST_OUT_FOR_DELIVERY, ST_DELIVERED, ST_RETURNED, ST_FAILED,
)
from .packages import compute_package, load_products
from .registry import get_carrier, load_carrier_config, normalize_code

logger = logging.getLogger(__name__)

LIVE_CODES = ("ARAS", "PTT")          # bu modülün uçtan uca yönettiği taşıyıcılar
COMPANY_FIELD = {"ARAS": "Aras", "PTT": "PTT", "MNG": "MNG"}   # customer.py _CARGO_NAME_MAP anahtarı
_PRE_SHIP = ("pending", "confirmed", "processing", "preparing", "ready_to_ship")
SHIPPED_STATES = (ST_ACCEPTED, ST_IN_TRANSIT, ST_OUT_FOR_DELIVERY, ST_FAILED)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _cargo_log(db, order_id: str, code: str, action: str, status: str, **extra):
    try:
        doc = {"id": str(uuid.uuid4()), "order_id": order_id, "provider": code, "action": action,
               "status": status, "created_at": _now()}
        doc.update({k: v for k, v in extra.items() if v is not None})
        await db.cargo_logs.insert_one(doc)
    except Exception as e:  # log yazılamasa da akış bozulmaz
        logger.warning(f"[cargo] log yazılamadı: {e}")


async def _order_event(order: Dict, description: str, user: Optional[Dict], meta: Dict):
    try:
        from routes.orders import _log_order_event
        await _log_order_event(order["id"], "cargo", description, user, meta,
                               order_number=order.get("order_number"))
    except Exception as e:
        logger.debug(f"[cargo] order event: {e}")


async def _notify(db, order: Dict, status_key: str, event: str, extra: Dict):
    """Ayarlar > Sipariş Durumları'nda açık kanallara (sms/email) bildirim."""
    try:
        from order_statuses import get_status_config
        from notification_service import send_notification
        cfg = await get_status_config(db)
        nz = (cfg.get("notify") or {}).get(status_key) or {}
        ch = [c for c in ("sms", "email") if nz.get(c)]
        if not ch:
            return
        try:
            from routes.orders import _order_notify_vars
            variables = await _order_notify_vars(order, **extra)
        except Exception:
            variables = dict(extra)
        ship = order.get("shipping_address") or {}
        await send_notification(db, event,
                                to_phone=ship.get("phone") or order.get("customer_phone") or order.get("phone"),
                                to_email=ship.get("email") or order.get("customer_email") or order.get("user_email"),
                                variables=variables, channels=ch)
    except Exception as e:
        logger.warning(f"[cargo] bildirim gönderilemedi ({event}, {order.get('order_number')}): {e}")


# ---------------------------------------------------------------------------
# PTT barkod aralığı → sıradaki barkod (atomik sayaç)
# ---------------------------------------------------------------------------
async def allocate_ptt_barcode(db, cfg: Dict) -> str:
    import ptt_kargo_client as pc
    rng = pc.parse_range(cfg.get("barcode_range_start"), cfg.get("barcode_range_end"))
    if not rng:
        raise HTTPException(status_code=400, detail=(
            "PTT barkod aralığı tanımlı değil ya da hatalı. Kargo Ayarları > PTT Kargo'da PTT'nin verdiği "
            "12 haneli 'Barkod aralığı başlangıç/bitiş' değerlerini girin."))
    start, end = rng
    cid = "ptt_barcode"
    doc = await db.cargo_counters.find_one({"id": cid}, {"_id": 0}) or {}
    if doc.get("range_start") != start:
        # Yeni aralık tanımlandı → sayaç sıfırlanır (eski aralıktan kalan numaralar tekrar kullanılmaz)
        await db.cargo_counters.update_one({"id": cid}, {"$set": {"id": cid, "range_start": start,
                                                                  "range_end": end, "seq": 0}}, upsert=True)
    upd = await db.cargo_counters.find_one_and_update({"id": cid}, {"$inc": {"seq": 1}},
                                                      return_document=True, upsert=True)
    seq = int((upd or {}).get("seq") or 1)
    n = start + seq - 1
    if n > end:
        raise HTTPException(status_code=400, detail="PTT barkod aralığı tükendi. PTT'den yeni aralık alıp ayarlara girin.")
    return pc.make_barcode(n)


# ---------------------------------------------------------------------------
# Oluştur
# ---------------------------------------------------------------------------
async def build_context(db, order: Dict, code: str, cfg: Dict) -> Dict:
    ship = order.get("shipping_address") or {}
    name = (f"{ship.get('first_name', '')} {ship.get('last_name', '')}".strip()
            or ship.get("full_name") or ship.get("name") or "")
    phone = phone10(ship.get("phone") or order.get("customer_phone"))
    city = normalize_il(ship.get("city"))
    district = str(ship.get("district") or "").strip()
    address = " ".join(x for x in (str(ship.get("address") or "").strip(),
                                   str(ship.get("neighborhood") or "").strip()) if x).strip()
    missing = [lbl for lbl, v in (("alıcı adı", name), ("telefon", phone), ("il", city),
                                  ("ilçe", district), ("adres", address)) if not v]
    if missing:
        raise HTTPException(status_code=400, detail=f"Teslimat bilgisi eksik ({', '.join(missing)}). Kargo kaydı oluşturulamaz.")
    if len(phone) != 10:
        raise HTTPException(status_code=400, detail="Alıcı telefonu 10 haneli olmalı (5XXXXXXXXX).")
    items = order.get("items") or []
    content = "; ".join(f"{it.get('quantity', 1)}x {it.get('product_name') or it.get('name') or ''}".strip()
                        for it in items)[:200] or "Ürün"
    products = await load_products(db, items)
    pkg = compute_package(order, products, default_desi=cfg.get("default_desi", 1.0),
                          default_kg=cfg.get("default_kg", 1.0))
    is_cod = is_cod_order(order)
    total = float(order.get("total") or order.get("grand_total") or order.get("subtotal") or 0)
    try:
        from routes.orders import _get_sender_info
        sender = await _get_sender_info()
    except Exception:
        sender = {}
    return {
        "cfg": cfg, "order": order, "package": pkg, "reference": str(order.get("order_number") or order.get("id")),
        "receiver_name": name, "phone": phone, "email": ship.get("email") or order.get("user_email") or "",
        "city": city, "district": district, "address_line": address, "content": content,
        "is_cod": is_cod, "cod_amount": round(total, 2) if is_cod else 0.0, "sender": sender,
    }


async def create_shipment_for_order(db, order: Dict, code: str, current_user: Optional[Dict] = None) -> Dict:
    code = normalize_code(code)
    carrier = get_carrier(code)
    if not carrier or code not in LIVE_CODES:
        raise HTTPException(status_code=400, detail=f"{code} için canlı kargo entegrasyonu yok")
    cfg = await load_carrier_config(db, code)
    if not carrier.is_configured(cfg):
        raise HTTPException(status_code=400, detail=(
            f"{carrier.name} entegrasyon bilgileri eksik. Ayarlar > Kargo Ayarları > {carrier.name} bölümünü doldurun."))
    ctx = await build_context(db, order, code, cfg)
    if code == "PTT":
        pending = ((order.get("cargo_pending") or {}).get("PTT") or "")
        import ptt_kargo_client as pc
        ctx["barcode"] = pending if pc.is_valid_barcode(pending) else await allocate_ptt_barcode(db, cfg)
        if ctx["barcode"] != pending:
            # Ayrılan barkod siparişe yazılır → PTT isteği başarısız olursa tekrar denemede aynı barkod kullanılır
            await db.orders.update_one({"id": order["id"]}, {"$set": {"cargo_pending.PTT": ctx["barcode"]}})
    summary = {"reference": ctx["reference"], "il": ctx["city"], "ilce": ctx["district"],
               "desi": ctx["package"]["desi"], "kg": ctx["package"]["kg"], "cod": ctx["is_cod"]}
    try:
        res = await carrier.create(ctx)
    except CarrierError as e:
        await _cargo_log(db, order["id"], code, "create_shipment", "exception", error=e.message[:1000],
                         request_summary=summary)
        raise HTTPException(status_code=502, detail=f"{carrier.name} bağlantı hatası: {e.message[:300]}")
    if not res.get("ok"):
        await _cargo_log(db, order["id"], code, "create_shipment", "error", error=str(res.get("message"))[:1000],
                         raw=str(res.get("raw") or "")[:1000], request_summary=summary)
        raise HTTPException(status_code=502, detail=f"{carrier.name} hatası: {res.get('message') or 'Bilinmeyen hata'}")

    barcode = res.get("barcode") or ""
    tn = res.get("tracking_number") or ""
    link = carrier.tracking_url(tn) if tn else (res.get("tracking_url") or carrier.tracking_url(""))
    cur = order.get("status")
    update = {
        "cargo_tracking_number": tn,
        "cargo_barcode_number": barcode,
        "cargo_tracking_link": link,
        "cargo_tracking_url": link,
        "cargo_provider_name": carrier.name,
        "cargo_provider_code": code,
        "cargo_company": COMPANY_FIELD.get(code, code),
        "cargo": {
            "provider": code,
            "provider_name": carrier.name,
            "tracking_number": tn or barcode,      # etiket/yazdır butonu için dolu (MNG ile aynı kural)
            "tracking_link": link,
            "barcode": barcode,
            "label_format": "10x15cm",
            "env": cfg.get("env", "test"),
            "package": ctx["package"],
            "cod": ctx["is_cod"],
            "cod_amount": ctx["cod_amount"],
            "status": "created",
            "status_text": STATUS_LABELS_TR["created"],
            "created_at": _now(),
            **(res.get("extra") or {}),
        },
        "cargo_barcode_created": True,
        "cargo_status_text": STATUS_LABELS_TR["created"],
        "status": "preparing" if cur in ("pending", "confirmed", "processing") else cur,
        "updated_at": _now(),
    }
    await db.orders.update_one({"id": order["id"]}, {"$set": update, "$unset": {"cargo_pending": ""}})
    await _cargo_log(db, order["id"], code, "create_shipment", "success", tracking_number=tn or barcode,
                     request_summary=summary)
    await _order_event(order, f"{carrier.name} kargo kaydı oluşturuldu (barkod {barcode})", current_user,
                       {"cargo_company": code, "barcode": barcode, "tracking_number": tn})
    if update["status"] == "preparing" and cur != "preparing":
        await _notify(db, {**order, **update}, "preparing", "order_preparing",
                      {"order_number": ctx["reference"], "cargo_provider": carrier.name})
    return {
        "success": True,
        "tracking_number": tn or barcode,
        "barcode": barcode,
        "tracking_link": link,
        "cargo_provider_name": carrier.name,
        "cargo_provider_code": code,
        "package": ctx["package"],
        "env": cfg.get("env", "test"),
        "message": f"✅ {carrier.name} kaydı oluşturuldu: {barcode}"
                   + ("" if tn else " — takip no, şube paketi okutunca otomatik gelecek"),
    }


# ---------------------------------------------------------------------------
# İptal
# ---------------------------------------------------------------------------
_CARGO_FIELDS_TO_CLEAR = ("cargo_tracking_number", "cargo_barcode_number", "cargo_tracking_link",
                          "cargo_tracking_url", "cargo_provider_name", "cargo_provider_code", "cargo",
                          "cargo_gonderi_no", "cargo_status_text", "cargo_label_printed_at",
                          "cargo_label_print_count")


async def cancel_order_shipment(db, order: Dict, current_user: Optional[Dict] = None) -> Dict:
    code = normalize_code(order.get("cargo_provider_code") or (order.get("cargo") or {}).get("provider") or "")
    carrier = get_carrier(code)
    if not carrier or (not order.get("cargo_barcode_created") and not order.get("cargo_barcode_number")):
        raise HTTPException(status_code=400, detail="Siparişte iptal edilecek kargo kaydı yok")
    if order.get("status") in ("shipped", "in_transit", "out_for_delivery", "delivered"):
        raise HTTPException(status_code=400, detail="Kargoya verilmiş/teslim edilmiş gönderi iptal edilemez")
    if code == "MNG":
        from routes.orders import _get_mng_settings
        cfg = await _get_mng_settings()
    else:
        cfg = await load_carrier_config(db, code)
    try:
        res = await carrier.cancel(order, cfg)
    except CarrierError as e:
        raise HTTPException(status_code=502, detail=f"{carrier.name} bağlantı hatası: {e.message[:300]}")
    await _cargo_log(db, order["id"], code, "cancel_shipment", "success" if res.get("ok") else "error",
                     error=None if res.get("ok") else str(res.get("message"))[:500])
    if not res.get("ok"):
        raise HTTPException(status_code=502, detail=f"{carrier.name} iptal edemedi: {res.get('message')}")
    unset = {k: "" for k in _CARGO_FIELDS_TO_CLEAR}
    st = order.get("status")
    await db.orders.update_one({"id": order["id"]}, {
        "$set": {"cargo_barcode_created": False, "updated_at": _now(),
                 "status": "confirmed" if st == "preparing" else st},
        "$unset": unset})
    await _order_event(order, f"{carrier.name} kargo kaydı iptal edildi", current_user,
                       {"cargo_company": code, "barcode": order.get("cargo_barcode_number")})
    return {"success": True, "message": f"{carrier.name} kaydı iptal edildi ({res.get('message') or 'OK'})"}


# ---------------------------------------------------------------------------
# Takip / durum
# ---------------------------------------------------------------------------
async def apply_tracking(db, order: Dict, info: Dict, *, code: str, notify: bool = True) -> Optional[str]:
    """Taşıyıcı takip sonucunu siparişe yazar; gerekirse durumu shipped/delivered yapar.
    Döner: yeni sipariş durumu veya None."""
    carrier = get_carrier(code)
    tn = (info.get("tracking_number") or "").strip()
    st = info.get("status") or ""
    text = info.get("status_text") or STATUS_LABELS_TR.get(st, "")
    now = _now()
    upd = {"cargo.status": st, "cargo.status_text": text, "cargo_query_at": now}
    if text:
        upd["cargo_status_text"] = text
    if info.get("events"):
        upd["cargo.events"] = info["events"][-30:]
    if tn:
        link = carrier.tracking_url(tn) if carrier else ""
        upd.update({"cargo_tracking_number": tn, "cargo.tracking_number": tn, "cargo_gonderi_no": tn})
        if link:
            upd.update({"cargo_tracking_link": link, "cargo_tracking_url": link, "cargo.tracking_link": link})
    cur = order.get("status")
    new_status = None
    if st == ST_DELIVERED and cur != "delivered":
        new_status = "delivered"
        upd["delivered_at"] = now
        if not order.get("shipped_at"):
            upd["shipped_at"] = now
    elif st in SHIPPED_STATES and (tn or order.get("cargo_tracking_number")) and cur in _PRE_SHIP:
        new_status = "shipped"
        upd["shipped_at"] = now
    if new_status:
        upd["status"] = new_status
    upd["updated_at"] = now
    await db.orders.update_one({"id": order["id"]}, {"$set": upd})
    if st == ST_RETURNED and (order.get("cargo") or {}).get("status") != ST_RETURNED:
        await _order_event(order, f"Kargo iade sürecinde: {text}", None, {"cargo_company": code})
    if new_status and notify:
        merged = {**order, "cargo_tracking_number": tn or order.get("cargo_tracking_number"),
                  "cargo_tracking_link": upd.get("cargo_tracking_link") or order.get("cargo_tracking_link")}
        await _notify(db, merged, new_status, "order_shipped" if new_status == "shipped" else "order_delivered",
                      {"tracking_number": merged["cargo_tracking_number"] or "",
                       "tracking_url": merged.get("cargo_tracking_link") or "",
                       "tracking_link": merged.get("cargo_tracking_link") or "",
                       "cargo_provider": carrier.name if carrier else code})
        await _order_event(order, f"Kargo durumu: {text} → {new_status}", None,
                           {"cargo_company": code, "tracking_number": tn})
    return new_status


async def refresh_order_tracking(db, order: Dict) -> Dict:
    code = normalize_code(order.get("cargo_provider_code") or "")
    carrier = get_carrier(code)
    if not carrier or code not in LIVE_CODES:
        raise HTTPException(status_code=400, detail="Bu sipariş Aras/PTT entegrasyonuyla gönderilmemiş")
    cfg = await load_carrier_config(db, code)
    try:
        info = await carrier.track(order, cfg)
    except CarrierError as e:
        raise HTTPException(status_code=502, detail=f"{carrier.name} takip sorgusu başarısız: {e.message[:300]}")
    if not info.get("ok"):
        raise HTTPException(status_code=502, detail=f"{carrier.name} takip sorgusu başarısız: {info.get('error') or info.get('message')}")
    if not info.get("found"):
        return {"success": True, "tracking_number": order.get("cargo_tracking_number") or "",
                "message": f"{carrier.name}: gönderi henüz şubede işlem görmedi. Okutulunca otomatik güncellenecek."}
    new_status = await apply_tracking(db, order, info, code=code)
    tn = info.get("tracking_number") or order.get("cargo_tracking_number") or ""
    msg = f"📦 {carrier.name}: {info.get('status_text') or STATUS_LABELS_TR.get(info.get('status'), '')}"
    if tn:
        msg += f" · Takip No: {tn}"
    if new_status:
        msg += f" · Sipariş durumu → {new_status}"
    return {"success": True, "tracking_number": tn, "status": info.get("status"),
            "kargo_statu_aciklama": info.get("status_text"), "tracking_link": carrier.tracking_url(tn),
            "new_status": new_status, "message": msg}


async def poll_tick(db, *, limit: int = 150) -> Dict:
    """Zamanlayıcı: son 45 günün açık Aras/PTT gönderilerini sorgular (shipped/delivered çevirir)."""
    started = datetime.now(timezone.utc)
    cutoff = (started - timedelta(days=45)).isoformat()
    q = {"cargo_provider_code": {"$in": list(LIVE_CODES)},
         "cargo_barcode_created": True,
         "status": {"$in": ["confirmed", "processing", "preparing", "ready_to_ship", "shipped",
                            "in_transit", "out_for_delivery"]},
         "created_at": {"$gt": cutoff}}
    stats = {"processed": 0, "shipped": 0, "delivered": 0, "errors": 0, "skipped": 0}
    cfgs: Dict[str, Dict] = {}
    async for order in db.orders.find(q, {"_id": 0}).limit(limit):
        code = normalize_code(order.get("cargo_provider_code"))
        carrier = get_carrier(code)
        if code not in cfgs:
            cfgs[code] = await load_carrier_config(db, code)
        cfg = cfgs[code]
        if not carrier or not carrier.is_configured(cfg):
            stats["skipped"] += 1
            continue
        try:
            info = await carrier.track(order, cfg)
        except CarrierError as e:
            stats["errors"] += 1
            logger.warning(f"[cargo-poll] {code} {order.get('order_number')}: {e.message}")
            continue
        except Exception as e:  # pragma: no cover - beklenmeyen
            stats["errors"] += 1
            logger.warning(f"[cargo-poll] {code} {order.get('order_number')}: {e}")
            continue
        if not info.get("ok"):
            stats["errors"] += 1
            continue
        stats["processed"] += 1
        if info.get("found"):
            ns = await apply_tracking(db, order, info, code=code)
            if ns == "shipped":
                stats["shipped"] += 1
            elif ns == "delivered":
                stats["delivered"] += 1
    stats["duration_ms"] = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    try:
        await db.settings.update_one({"id": "multi_cargo_poll_health"},
                                     {"$set": {"id": "multi_cargo_poll_health", "last_finish_at": _now(), **stats}},
                                     upsert=True)
    except Exception:
        pass
    return stats
