"""Sahibin 12.10.2026 düzeltmeleri — canlı veriye BİR KEZ uygulanır (işaret: settings.id=MARKER).

1. İletişim: adres "Tekstilkent, A16 Blok No: 20, Esenler / İstanbul", telefon "0543 276 89 73";
   tenant_config (Şirket Bilgileri → footer, yasal sayfalar, iletişim), settings.main aynası,
   Sayfa Tasarımı › İletişim (site_contact) ve WhatsApp butonu (storefront.whatsapp_*).
2. Üst bar: "Teknik Destek" bağlantısı (Mağazamız'ın soluna), "Türk Lirası (₺)" kaldırılır.
3. Ana sayfa: Markalar bandı Reklam Kutuları'nın hemen altına; slider altına istatistik bandı
   (features_list / stats). Yayındaki düzen yeni bir sürüm olarak yayınlanır (Sürümler'den geri
   alınabilir); yayınlanmamış taslak varsa ona da aynı değişiklik uygulanır.
Sonradan panelden yapılan değişikliklere dokunmaz (bir kez çalışır).
"""
from __future__ import annotations

import copy
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("site_refresh")

MARKER = "site_refresh_2026_10_12_v1"
ADDRESS = "Tekstilkent, A16 Blok No: 20"
CITY = "Esenler / İstanbul"
FULL_ADDRESS = f"{ADDRESS}, {CITY}"
PHONE = "0543 276 89 73"
WHATSAPP_INTL = "905432768973"
SUPPORT_PAGE = "/sayfa/garanti-kosullari"

TECH_SUPPORT_ITEM = {
    "label": "Teknik Destek",
    "icon": {"icon": "ec ec-support"},
    "link": {"kind": "url", "url": SUPPORT_PAGE, "new_tab": False},
    "special": "",
    "guest_text": "",
}

STATS_ITEMS = [
    ("1.000+", "Ürün ve ekipman çeşidi"),
    ("81 İl", "Adrese teslimat"),
    ("2 Yıl", "Garanti güvencesi"),
    ("Teknik Destek", "Pzt–Cmt 09:00–18:00"),
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stats_block() -> dict:
    import pageblocks as pb
    b = pb.instantiate("features_list", "stats", title="İstatistik Bandı")
    st = b.setdefault("settings", {})
    st["items"] = [{"_id": uuid.uuid4().hex[:10], "icon": {"icon": ""}, "strong_text": n, "text": t,
                    "link": {"kind": "none", "url": "", "new_tab": False}} for n, t in STATS_ITEMS]
    st["border"] = True
    return b


def _type(b: dict) -> str:
    return str(b.get("type") or b.get("key") or "")


def reorder_home(blocks: list) -> list:
    """Markalar → Reklam Kutuları'nın hemen arkasına; istatistik bandı → slider'ın arkasına (yoksa)."""
    out = [copy.deepcopy(b) for b in blocks or []]
    brands = [b for b in out if _type(b) == "brands_carousel"]
    if brands:
        br = brands[0]
        out.remove(br)
        idx = next((i for i, b in enumerate(out) if _type(b) == "ads_block"), None)
        if idx is None:
            idx = next((i for i, b in enumerate(out) if _type(b) == "hero_slider"), -1)
        out.insert(idx + 1, br)
    has_stats = any(_type(b) == "features_list" and (b.get("variant") == "stats"
                    or (b.get("settings") or {}).get("_variant") == "stats") for b in out)
    if not has_stats:
        hi = next((i for i, b in enumerate(out) if _type(b) == "hero_slider"), -1)
        out.insert(hi + 1, stats_block())
    for i, b in enumerate(out, start=1):
        b["sort_order"] = i
    return out


def patch_global(g: dict) -> dict:
    g = copy.deepcopy(g or {})
    sc = dict(g.get("site_contact") or {})
    sc.update(phone=PHONE, address=FULL_ADDRESS, whatsapp=PHONE)
    g["site_contact"] = sc
    tb = dict(g.get("site_topbar") or {})
    items = [it for it in (tb.get("right_items") or []) if isinstance(it, dict)]
    if not any((it.get("label") or "").strip().lower() == "teknik destek" for it in items):
        items.insert(0, dict(TECH_SUPPORT_ITEM, _id=uuid.uuid4().hex[:10]))
    tb["right_items"] = items
    tb["currency_text"] = ""
    g["site_topbar"] = tb
    return g


async def _contact(db):
    from tenant_config import get_tenant_config, invalidate, legacy_write_through
    patch = {"company.address": ADDRESS, "company.district": "", "company.city": CITY,
             "contact.phone": PHONE, "contact.whatsapp": PHONE}
    await db.settings.update_one({"id": "tenant_config"}, {"$set": patch}, upsert=True)
    invalidate(db)
    try:
        full = await get_tenant_config(db, use_cache=False)
        await db.settings.update_one({"id": "main"}, {"$set": legacy_write_through(full),
                                                      "$setOnInsert": {"id": "main"}}, upsert=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("settings.main aynası: %s", e)
    try:
        import business_rules as br
        await br.save_rules(db, {"storefront.whatsapp_enabled": True, "storefront.whatsapp_number": WHATSAPP_INTL})
    except Exception as e:  # noqa: BLE001
        logger.warning("whatsapp ayarı: %s", e)


async def _layout(db):
    from pageblocks import store
    pub = await store.ensure(db, "home")
    draft = await store.get_draft(db, "home")
    g = patch_global(await store.get_global(db))
    blocks = reorder_home(pub.get("blocks") or [])
    doc, errors, _status = await store.publish(db, "home", user="sistem (site düzeltmesi)", blocks=blocks, global_=g)
    if errors:
        logger.error("[%s] yayın hatası: %s", MARKER, errors)
        return False
    if draft:  # yayınlanmamış taslak kaybolmasın: aynı değişikliklerle geri yaz
        draft = dict(draft)
        draft["blocks"] = reorder_home(draft.get("blocks") or [])
        draft["global"] = patch_global(draft.get("global") or g)
        draft["rev"] = doc.get("rev")
        await db.page_layouts.replace_one({"id": "home:draft"}, draft, upsert=True)
    return True


async def run_once(db=None) -> bool:
    try:
        if db is None:
            from routes.deps import db as _db
            db = _db
        if await db.settings.find_one({"id": MARKER}, {"_id": 1}):
            return False
        await _contact(db)
        if not await _layout(db):
            return False
        await db.settings.update_one({"id": MARKER}, {"$set": {"id": MARKER, "done": True, "applied_at": _now()}},
                                     upsert=True)
        logger.warning("[%s] uygulandı", MARKER)
        return True
    except Exception as e:  # noqa: BLE001 — açılışı asla düşürme
        logger.exception("[%s] hata: %s", MARKER, e)
        return False
