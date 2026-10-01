"""
cargo_carriers/registry.py — Kargo firması (taşıyıcı) arayüzü + kayıt defteri.

Sipariş akışı kargo firmasını KODU ile çağırır (MNG / ARAS / PTT); her taşıyıcı aynı arayüzü
uygular:
    test_connection(cfg)                         → {ok, message}
    create(ctx)                                  → {ok, barcode, tracking_number, tracking_url, extra, message}
    cancel(order, cfg)                           → {ok, message}
    track(order, cfg)                            → {ok, found, tracking_number, status, status_text,
                                                    delivered_at, tracking_url, events}
    tracking_url(tracking_no)                    → müşteri takip linki

MNG (DHL eCommerce) için gönderi OLUŞTURMA mevcut ve kapsamlı akışta kalır
(routes/orders.py:create_cargo_barcode); burada yalnızca test/iptal/takip sarılır.
Aras ve PTT tamamen bu arayüz üzerinden çalışır (cargo_carriers/service.py).

Ayarlar: providers_config(kind="cargo").providers.<key> (şifreli; routes/provider_settings.py)
+ settings(id="cargo_carrier_settings") {default_carrier, default_desi, default_kg}.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from .common import CarrierError, ST_CREATED, ST_ACCEPTED, ST_DELIVERED, ST_UNKNOWN

logger = logging.getLogger(__name__)

CARRIER_SETTINGS_ID = "cargo_carrier_settings"


def _num(v, default: float) -> float:
    try:
        f = float(str(v).replace(",", "."))
        return f if f > 0 else default
    except (TypeError, ValueError):
        return default


class Carrier:
    code = ""
    key = ""          # providers_config.providers anahtarı
    name = ""
    supports_create = True

    def tracking_url(self, tracking_no: str = "") -> str:  # pragma: no cover - alt sınıf
        return ""

    def is_configured(self, cfg: Dict) -> bool:  # pragma: no cover
        return False

    async def test_connection(self, cfg: Dict) -> Dict:  # pragma: no cover
        raise NotImplementedError

    async def create(self, ctx: Dict) -> Dict:  # pragma: no cover
        raise NotImplementedError

    async def cancel(self, order: Dict, cfg: Dict) -> Dict:  # pragma: no cover
        raise NotImplementedError

    async def track(self, order: Dict, cfg: Dict) -> Dict:  # pragma: no cover
        raise NotImplementedError


# ---------------------------------------------------------------------------
class ArasCarrier(Carrier):
    code, key, name = "ARAS", "aras", "Aras Kargo"

    def tracking_url(self, tracking_no: str = "") -> str:
        import aras_kargo_client as ac
        return ac.tracking_url(tracking_no)

    def is_configured(self, cfg: Dict) -> bool:
        return bool(cfg.get("username") and cfg.get("password"))

    async def test_connection(self, cfg: Dict) -> Dict:
        import aras_kargo_client as ac
        return await asyncio.to_thread(
            ac.test_connection, username=cfg.get("username", ""), password=cfg.get("password", ""),
            customer_code=cfg.get("customer_code", ""), query_username=cfg.get("query_username", ""),
            query_password=cfg.get("query_password", ""), env=cfg.get("env", "test"),
            ship_url=cfg.get("ship_url", ""), query_url=cfg.get("query_url", ""))

    async def create(self, ctx: Dict) -> Dict:
        import aras_kargo_client as ac
        cfg, order, pkg = ctx["cfg"], ctx["order"], ctx["package"]
        integration_code = ctx["reference"]
        payload = ac.build_order(
            integration_code=integration_code,
            receiver_name=ctx["receiver_name"], receiver_address=ctx["address_line"],
            receiver_phone=ctx["phone"], city=ctx["city"], town=ctx["district"],
            pieces=pkg["pieces"], desi=pkg["desi"], kg=pkg["kg"],
            invoice_number=str(order.get("invoice_number") or ""),
            waybill_number=integration_code, description=ctx["content"],
            is_cod=ctx["is_cod"], cod_amount=ctx["cod_amount"],
            cod_collection_type=str(cfg.get("cod_collection_type") or "0"),
            payor_type=str(cfg.get("payor_type") or "1"),
            sender_account_address_id=str(cfg.get("sender_address_id") or ""),
        )
        res = await asyncio.to_thread(ac.set_order, payload, username=cfg["username"],
                                      password=cfg["password"], env=cfg.get("env", "test"),
                                      ship_url=cfg.get("ship_url", ""))
        if not res.get("ok"):
            return {"ok": False, "message": res.get("message"), "code": res.get("code"), "raw": res.get("raw")}
        barcode = payload["PieceDetails"][0]["BarcodeNumber"]
        return {
            "ok": True,
            "barcode": barcode,                     # etikete basılan, şubenin okuttuğu parça barkodu
            "tracking_number": "",                  # Aras takip no şube irsaliye kesince oluşur (senkron doldurur)
            "tracking_url": ac.tracking_url(""),
            "message": res.get("message") or "Aras Kargo kaydı oluşturuldu",
            "extra": {"integration_code": integration_code,
                      "piece_barcodes": [d["BarcodeNumber"] for d in payload["PieceDetails"]],
                      "invoice_key": res.get("invoice_key", "")},
        }

    async def cancel(self, order: Dict, cfg: Dict) -> Dict:
        import aras_kargo_client as ac
        cargo = order.get("cargo") or {}
        ic = cargo.get("integration_code") or str(order.get("order_number") or order.get("id"))
        res = await asyncio.to_thread(ac.cancel_dispatch, username=cfg["username"], password=cfg["password"],
                                      integration_code=ic, env=cfg.get("env", "test"),
                                      ship_url=cfg.get("ship_url", ""))
        return {"ok": bool(res.get("ok")), "message": res.get("message"), "code": res.get("code")}

    async def track(self, order: Dict, cfg: Dict) -> Dict:
        import aras_kargo_client as ac
        cargo = order.get("cargo") or {}
        ic = cargo.get("integration_code") or str(order.get("order_number") or order.get("id"))
        if not cfg.get("customer_code"):
            return {"ok": False, "error": "Aras müşteri kodu (CustomerCode) girilmemiş — takip sorgulanamaz"}
        return await asyncio.to_thread(
            ac.track_by_integration_code,
            username=cfg.get("query_username") or cfg["username"],
            password=cfg.get("query_password") or cfg["password"],
            customer_code=cfg["customer_code"], integration_code=ic, env=cfg.get("env", "test"),
            query_url=cfg.get("query_url", ""))


# ---------------------------------------------------------------------------
class PttCarrier(Carrier):
    code, key, name = "PTT", "ptt", "PTT Kargo"

    def tracking_url(self, tracking_no: str = "") -> str:
        import ptt_kargo_client as pc
        return pc.tracking_url(tracking_no)

    def is_configured(self, cfg: Dict) -> bool:
        return bool(cfg.get("customer_number") and cfg.get("password"))

    async def test_connection(self, cfg: Dict) -> Dict:
        import ptt_kargo_client as pc
        return await asyncio.to_thread(pc.test_connection, musteri_id=str(cfg.get("customer_number", "")),
                                       sifre=cfg.get("password", ""), env=cfg.get("env", "test"),
                                       range_start=str(cfg.get("barcode_range_start") or ""),
                                       takip_url=cfg.get("takip_url", ""))

    async def create(self, ctx: Dict) -> Dict:
        import ptt_kargo_client as pc
        cfg, pkg = ctx["cfg"], ctx["package"]
        barcode = ctx.get("barcode")
        if not barcode:
            raise CarrierError("PTT barkodu ayrılamadı (barkod aralığını kontrol edin)")
        dongu = pc.build_dongu(
            barcode=barcode, receiver_name=ctx["receiver_name"],
            address=f"{ctx['address_line']} {ctx['district']} {ctx['city']}".strip(),
            city=ctx["city"], town=ctx["district"], phone=ctx["phone"], email=ctx.get("email", ""),
            reference=ctx["reference"], desi=pkg["desi"], kg=pkg["kg"],
            is_cod=ctx["is_cod"], cod_amount=ctx["cod_amount"],
            odeme_sekli=str(cfg.get("odeme_sekli") or ""), ek_hizmet=str(cfg.get("ek_hizmet") or ""),
            cod_service_code=str(cfg.get("cod_service_code") or "OS"),
            posta_ceki_no=str(cfg.get("posta_ceki_no") or ""),
        )
        dosya = f"{ctx['reference']}-{barcode}"[:50]
        sender = ctx.get("sender") if str(cfg.get("send_sender_info") or "").lower() in ("1", "true", "evet", "yes") else None
        res = await asyncio.to_thread(pc.kabul_ekle2, dongu, musteri_id=str(cfg["customer_number"]),
                                      sifre=cfg["password"], dosya_adi=dosya, env=cfg.get("env", "test"),
                                      sender=sender, kabul_url=cfg.get("kabul_url", ""))
        if not res.get("ok"):
            return {"ok": False, "message": res.get("message"), "code": res.get("code"), "raw": res.get("raw")}
        bc = res.get("barcode") or barcode
        return {
            "ok": True,
            "barcode": bc,
            "tracking_number": bc,                  # PTT barkodu = resmî takip numarası
            "tracking_url": res.get("tracking_link") or pc.tracking_url(bc),
            "message": res.get("message") or "PTT gönderi kaydı oluşturuldu",
            "extra": {"dosya_adi": dosya, "ptt_barcode": bc},
        }

    async def cancel(self, order: Dict, cfg: Dict) -> Dict:
        import ptt_kargo_client as pc
        cargo = order.get("cargo") or {}
        bc = cargo.get("ptt_barcode") or order.get("cargo_barcode_number") or ""
        if not bc:
            return {"ok": False, "message": "Siparişte PTT barkodu yok"}
        res = await asyncio.to_thread(pc.barkod_veri_sil, barcode=bc, musteri_id=str(cfg["customer_number"]),
                                      sifre=cfg["password"], dosya_adi=cargo.get("dosya_adi", ""),
                                      env=cfg.get("env", "test"), kabul_url=cfg.get("kabul_url", ""))
        return {"ok": bool(res.get("ok")), "message": res.get("message"), "code": res.get("code")}

    async def track(self, order: Dict, cfg: Dict) -> Dict:
        import ptt_kargo_client as pc
        cargo = order.get("cargo") or {}
        bc = cargo.get("ptt_barcode") or order.get("cargo_tracking_number") or order.get("cargo_barcode_number")
        if not bc:
            return {"ok": False, "error": "Siparişte PTT barkodu yok"}
        r = await asyncio.to_thread(pc.gonderi_sorgu, barcode=bc, musteri_id=str(cfg["customer_number"]),
                                    sifre=cfg["password"], env=cfg.get("env", "test"),
                                    takip_url=cfg.get("takip_url", ""))
        if not r.get("ok"):
            return {"ok": False, "error": r.get("message") or "PTT sorgu hatası"}
        r["tracking_number"] = bc
        return r


# ---------------------------------------------------------------------------
class MngCarrier(Carrier):
    """DHL eCommerce (eski MNG). Gönderi oluşturma routes/orders.py'deki mevcut akışta kalır."""
    code, key, name = "MNG", "mng", "DHL E-Commerce (MNG)"
    supports_create = False

    def tracking_url(self, tracking_no: str = "") -> str:
        tn = str(tracking_no or "").strip()
        return f"https://kargotakip.dhlecommerce.com.tr/?takipNo={tn}" if tn else "https://www.dhlecommerce.com.tr/gonderitakip"

    def is_configured(self, cfg: Dict) -> bool:
        return bool(cfg.get("username") and cfg.get("password"))

    async def test_connection(self, cfg: Dict) -> Dict:
        from mng_kargo_client import baglanti_test
        r = await asyncio.to_thread(baglanti_test)
        return {"ok": bool(r.get("ok")), "message": ("MNG/DHL servisi yanıt verdi: " + str(r.get("result") or ""))
                if r.get("ok") else f"MNG/DHL: {r.get('error')}"}

    async def cancel(self, order: Dict, cfg: Dict) -> Dict:
        from mng_kargo_client import cancel_shipment
        cargo = order.get("cargo") or {}
        r = await asyncio.to_thread(cancel_shipment, username=cfg.get("username", ""), password=cfg.get("password", ""),
                                    siparis_no=str(order.get("order_number") or order.get("id")),
                                    gonderi_no=cargo.get("mng_gonderi_no") or "")
        return {"ok": bool(r.get("ok")), "message": r.get("hata") or "MNG gönderisi iptal edildi"}

    async def track(self, order: Dict, cfg: Dict) -> Dict:
        from mng_kargo_client import get_mng_shipment_status
        info = await asyncio.to_thread(get_mng_shipment_status, username=cfg.get("username", ""),
                                       password=cfg.get("password", ""),
                                       siparis_no=str(order.get("order_number") or order.get("id")))
        if not info.get("ok"):
            return {"ok": False, "error": info.get("error")}
        gn = info.get("gonderi_no") or ""
        txt = (info.get("kargo_statu_aciklama") or "").lower()
        st = ST_DELIVERED if (info.get("teslim_tarihi") or ("teslim edildi" in txt)) else (ST_ACCEPTED if gn else ST_CREATED)
        return {"ok": True, "found": True, "tracking_number": gn, "status": st,
                "status_text": info.get("kargo_statu_aciklama") or "", "tracking_url": self.tracking_url(gn),
                "delivered_at": info.get("teslim_tarihi") or ""}


CARRIERS: Dict[str, Carrier] = {c.code: c for c in (MngCarrier(), ArasCarrier(), PttCarrier())}
_KEY_TO_CODE = {c.key: c.code for c in CARRIERS.values()}
_ALIASES = {"ARAS": "ARAS", "ARASKARGO": "ARAS", "PTT": "PTT", "PTTKARGO": "PTT",
            "MNG": "MNG", "DHL": "MNG", "MNGKARGO": "MNG", "DHLECOMMERCE": "MNG"}


def normalize_code(code) -> str:
    """'aras' / 'Aras Kargo' / 'ARAS' → 'ARAS'; tanınmayan → büyük harfli girdi."""
    raw = str(code or "").strip()
    key = "".join(ch for ch in raw.upper().replace("İ", "I") if ch.isalnum())
    return _ALIASES.get(key) or _KEY_TO_CODE.get(raw.lower()) or key


def get_carrier(code) -> Optional[Carrier]:
    return CARRIERS.get(normalize_code(code))


def code_for_key(key: str) -> str:
    return _KEY_TO_CODE.get(str(key or "").lower(), "")


# ---------------------------------------------------------------------------
# Ayarlar
# ---------------------------------------------------------------------------
async def get_carrier_settings(db) -> Dict:
    s = await db.settings.find_one({"id": CARRIER_SETTINGS_ID}, {"_id": 0}) or {}
    return {
        "default_carrier": normalize_code(s.get("default_carrier") or "") or "",
        "default_desi": _num(s.get("default_desi"), 1.0),
        "default_kg": _num(s.get("default_kg"), 1.0),
        "auto_sync": s.get("auto_sync", True) is not False,
    }


async def resolve_default_code(db) -> str:
    """Varsayılan kargo firması: Kargo Ayarları'ndaki açık seçim → providers_config.active_provider
    (yalnız canlı entegrasyonu olan MNG/ARAS/PTT) → MNG."""
    s = await get_carrier_settings(db)
    if s["default_carrier"] in CARRIERS:
        return s["default_carrier"]
    try:
        doc = await db.providers_config.find_one({"kind": "cargo"}, {"_id": 0, "active_provider": 1}) or {}
        c = code_for_key(doc.get("active_provider") or "")
        if c in CARRIERS:
            return c
    except Exception:
        pass
    return "MNG"


async def load_carrier_config(db, code: str) -> Dict:
    """Taşıyıcı kimlik bilgileri (ŞİFRESİ ÇÖZÜLMÜŞ) + desi/kg varsayılanları.
    Aktif seçili olmasa da okunur → birden çok firma aynı anda kullanılabilir."""
    carrier = get_carrier(code)
    if not carrier:
        return {}
    doc = await db.providers_config.find_one({"kind": "cargo"}, {"_id": 0}) or {}
    try:
        from routes.provider_settings import decrypt_provider_doc
        doc = decrypt_provider_doc("cargo", doc)
    except Exception as e:  # pragma: no cover - kripto yoksa düz değer
        logger.warning(f"[cargo] provider config decrypt: {e}")
    cfg = dict((doc.get("providers") or {}).get(carrier.key) or {})
    gs = await get_carrier_settings(db)
    cfg["default_desi"] = _num(cfg.get("default_desi"), gs["default_desi"])
    cfg["default_kg"] = _num(cfg.get("default_kg"), gs["default_kg"])
    cfg["env"] = cfg.get("env") or "test"
    return cfg
