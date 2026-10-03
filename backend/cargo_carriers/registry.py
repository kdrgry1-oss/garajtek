"""
cargo_carriers/registry.py — Kargo firması (taşıyıcı) arayüzü + kayıt defteri.

Sipariş akışı kargo firmasını KODU ile çağırır (ARAS / PTT); her taşıyıcı aynı arayüzü
uygular:
    test_connection(cfg)                         → {ok, message}
    create(ctx)                                  → {ok, barcode, tracking_number, tracking_url, extra, message}
    cancel(order, cfg)                           → {ok, message}
    track(order, cfg)                            → {ok, found, tracking_number, status, status_text,
                                                    delivered_at, tracking_url, events}
    tracking_url(tracking_no)                    → müşteri takip linki

Desteklenen entegrasyonlar yalnızca Aras Kargo ve PTT Kargo'dur; ikisi de tamamen bu arayüz
üzerinden çalışır (cargo_carriers/service.py). Eski siparişlerde kayıtlı başka firma kodları
(ör. geçmişte kullanılan entegrasyonlar) yalnızca görüntülenir; bu kayıt defterinde yer almaz.

Ayarlar: providers_config(kind="cargo").providers.<key> (şifreli; routes/provider_settings.py)
+ settings(id="cargo_carrier_settings") {default_carrier, default_desi, default_kg}.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Optional

from .common import CarrierError

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
            "tracking_url": ac.tracking_url("", account_id=str(cfg.get("tracking_account_id") or ""),
                                            receiver_code=integration_code),
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


CARRIERS: Dict[str, Carrier] = {c.code: c for c in (ArasCarrier(), PttCarrier())}
_KEY_TO_CODE = {c.key: c.code for c in CARRIERS.values()}
_ALIASES = {"ARAS": "ARAS", "ARASKARGO": "ARAS", "PTT": "PTT", "PTTKARGO": "PTT"}
DEFAULT_CODE = "ARAS"   # hiçbir seçim yoksa: Aras → (yoksa) PTT


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
    (yalnız ARAS/PTT) → kimlik bilgisi girilmiş ilk firma (Aras, sonra PTT) → ARAS."""
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
    try:
        for c in ("ARAS", "PTT"):
            if CARRIERS[c].is_configured(await load_carrier_config(db, c)):
                return c
    except Exception:
        pass
    return DEFAULT_CODE


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


# ---------------------------------------------------------------------------
# Başlangıç migrasyonu: kaldırılan entegrasyonlar → Aras
# ---------------------------------------------------------------------------
async def migrate_legacy_default(db) -> Dict:
    """İDEMPOTENT: kayıtlı aktif/varsayılan kargo firması artık desteklenmeyen bir firmaysa
    (ör. 'mng' / 'dhl_ecommerce') varsayılanı 'aras' / 'ARAS' yapar. Kayıtlı kimlik bilgileri
    SİLİNMEZ (providers.<eski> olduğu gibi kalır, yalnız yok sayılır). Her açılışta güvenle çalışır."""
    out = {"active_provider": None, "default_carrier": None}
    now = datetime.now(timezone.utc).isoformat()
    doc = await db.providers_config.find_one({"kind": "cargo"}, {"_id": 0, "active_provider": 1}) or {}
    ap = str(doc.get("active_provider") or "").strip()
    if ap and ap.lower() not in {c.key for c in CARRIERS.values()}:
        await db.providers_config.update_one(
            {"kind": "cargo"},
            {"$set": {"active_provider": "aras", "legacy_active_provider": ap, "updated_at": now}})
        out["active_provider"] = f"{ap} → aras"
    s = await db.settings.find_one({"id": CARRIER_SETTINGS_ID}, {"_id": 0, "default_carrier": 1}) or {}
    dc = str(s.get("default_carrier") or "").strip()
    if dc and normalize_code(dc) not in CARRIERS:
        await db.settings.update_one(
            {"id": CARRIER_SETTINGS_ID},
            {"$set": {"default_carrier": DEFAULT_CODE, "legacy_default_carrier": dc, "updated_at": now}})
        out["default_carrier"] = f"{dc} → {DEFAULT_CODE}"
    out["shipping_fee_carrier"] = await _migrate_fee_carrier(db, now)
    return out


async def _migrate_fee_carrier(db, now: str):
    """Müşteriye yansıyan kargo ücreti 'varsayılan kargo firması'nın ücretidir (settings.main
    default_cargo_company + cargo_fees; panelde tenant_config.shipping). Firma eski bir anahtarsa
    (ör. 'mng') 'aras' yapılır ve Aras ücreti boşsa ESKİ ÜCRET Aras'a kopyalanır → checkout tutarı
    DEĞİŞMEZ. Diğer eski ücret anahtarları silinmez (yok sayılır)."""
    valid = {c.key for c in CARRIERS.values()}
    changed = []

    def _plan(cur_key, fees):
        k = str(cur_key or "").strip()
        if not k or k.lower() in valid:
            return None
        fees = dict(fees or {}) if isinstance(fees, dict) else {}
        if fees.get("aras") in (None, "") and fees.get(k) not in (None, ""):
            fees["aras"] = fees.get(k)
        return k, fees

    main = await db.settings.find_one({"id": "main"}, {"_id": 0, "default_cargo_company": 1, "cargo_fees": 1}) or {}
    p = _plan(main.get("default_cargo_company"), main.get("cargo_fees"))
    if p:
        await db.settings.update_one({"id": "main"}, {"$set": {
            "default_cargo_company": "aras", "cargo_fees": p[1],
            "legacy_default_cargo_company": p[0], "updated_at": now}})
        changed.append(f"main:{p[0]} → aras")
    tc = await db.settings.find_one({"id": "tenant_config"}, {"_id": 0, "shipping": 1}) or {}
    ship = tc.get("shipping") or {}
    p = _plan(ship.get("default_carrier"), ship.get("carrier_fees"))
    if p:
        await db.settings.update_one({"id": "tenant_config"}, {"$set": {
            "shipping.default_carrier": "aras", "shipping.carrier_fees": p[1]}})
        changed.append(f"tenant_config:{p[0]} → aras")
    if changed:
        try:
            import tenant_config as _tc
            _tc.invalidate(db)
        except Exception:
            pass
    return ", ".join(changed) or None
