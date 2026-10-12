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
import re
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


THEME_MARKER = "site_theme_red_2026_10_12_v1"
RED_THEME = {"preset": "custom", "primary_color": "#d71920", "primary_dark": "#b9141a", "text_on_primary": "white"}


async def apply_red_theme_once(db=None) -> bool:
    """Sahip talebi: sarı olan her şey kırmızı — Sayfa Tasarımı › Tema ana rengi bir kez kırmızıya çekilir
    (yeni yayın sürümü; panelden geri alınabilir / değiştirilebilir)."""
    try:
        if db is None:
            from routes.deps import db as _db
            db = _db
        if await db.settings.find_one({"id": THEME_MARKER}, {"_id": 1}):
            return False
        from pageblocks import store
        pub = await store.ensure(db, "home")
        draft = await store.get_draft(db, "home")
        g = copy.deepcopy(await store.get_global(db))
        g["site_theme"] = {**(g.get("site_theme") or {}), **RED_THEME}
        doc, errors, _ = await store.publish(db, "home", user="sistem (kırmızı tema)", blocks=pub.get("blocks") or [],
                                             global_=g)
        if errors:
            logger.error("[%s] yayın hatası: %s", THEME_MARKER, errors)
            return False
        if draft:
            draft = dict(draft)
            dg = dict(draft.get("global") or g)
            dg["site_theme"] = {**(dg.get("site_theme") or {}), **RED_THEME}
            draft["global"], draft["rev"] = dg, doc.get("rev")
            await db.page_layouts.replace_one({"id": "home:draft"}, draft, upsert=True)
        await db.settings.update_one({"id": THEME_MARKER}, {"$set": {"id": THEME_MARKER, "applied_at": _now()}},
                                     upsert=True)
        return True
    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] hata: %s", THEME_MARKER, e)
        return False


HIDE_BRAND_MARKER = "hide_grayzer_brand_2026_10_12_v1"
HIDDEN_BRAND_RX = r"\bgrayzer\b"


def brand_query() -> dict:
    rx = {"$regex": HIDDEN_BRAND_RX, "$options": "i"}
    return {"product_type": {"$ne": "set"}, "$or": [{"brand": rx}, {"name": rx}]}


async def hide_grayzer_once(db) -> dict:
    """Sahip talebi: Grayzer markalı ürünler sitede pasif. Bir kez çalışır (panelden yeniden açılan ürüne
    dokunmaz); bu ürünleri içeren hazır setlerde bileşen aynı kategoriden aktif bir ürünle değiştirilir."""
    if await db.settings.find_one({"id": HIDE_BRAND_MARKER}, {"_id": 1}):
        return {"skipped": "done"}
    ids = [p["id"] async for p in db.products.find({**brand_query(), "is_active": {"$ne": False}}, {"_id": 0, "id": 1})]
    if ids:
        await db.products.update_many({"id": {"$in": ids}}, {"$set": {
            "is_active": False, "deactivated_reason": "Sahip talebi: Grayzer markası satıştan kaldırıldı",
            "deactivated_at": _now()}})
    repaired = await repair_sets(db, set(ids))
    await db.settings.update_one({"id": HIDE_BRAND_MARKER}, {"$set": {
        "id": HIDE_BRAND_MARKER, "count": len(ids), "product_ids": ids, "sets": repaired, "applied_at": _now()}},
        upsert=True)
    logger.warning("[%s] %d ürün pasif, set onarımı: %s", HIDE_BRAND_MARKER, len(ids), repaired)
    return {"hidden": len(ids), "sets": repaired}


async def repair_sets(db, removed: set) -> list:
    """Hazır setlerde (set_seed alanlı) çıkarılan bileşeni aynı kategoriden aktif, stoklu bir ürünle değiştirir;
    bulunamazsa bileşeni setten çıkarır."""
    import product_sets as ps
    out = []
    if not removed:
        return out
    async for st in db.products.find({"product_type": "set", "set_items.product_id": {"$in": list(removed)}},
                                     {"_id": 0}):
        items = list(st.get("set_items") or [])
        used = {i.get("product_id") for i in items}
        new_items, swapped, dropped = [], 0, 0
        for it in items:
            pid = it.get("product_id")
            if pid not in removed:
                new_items.append(it)
                continue
            old = await db.products.find_one({"id": pid}, {"_id": 0, "category_id": 1}) or {}
            q = {"is_active": True, "stock": {"$gt": 0}, "product_type": {"$ne": "set"}, "is_deleted": {"$ne": True},
                 "price": {"$gt": 0}, "id": {"$nin": list(used | removed)}}
            if old.get("category_id"):
                q["category_id"] = old["category_id"]
            alt = None
            tries = [q]
            if len(items) >= 100:  # 100 ürünlük set 100'de kalsın: kategoride yoksa herhangi bir aktif ürün
                tries.append({k: v for k, v in q.items() if k != "category_id"})
            for qq in tries:
                async for c in db.products.find(qq, {"_id": 0, "id": 1, "name": 1, "brand": 1, "variants": 1}).limit(200):
                    if c.get("variants") or re.search(HIDDEN_BRAND_RX, f"{c.get('brand') or ''} {c.get('name') or ''}", re.I):
                        continue
                    alt = c
                    break
                if alt:
                    break
            if alt:
                new_items.append({**it, "product_id": alt["id"]})
                used.add(alt["id"])
                swapped += 1
            else:
                dropped += 1
        await db.products.update_one({"id": st["id"]}, {"$set": {"set_items": new_items, "updated_at": _now()}})
        doc = await db.products.find_one({"id": st["id"]}, {"_id": 0})
        await ps.refresh_set(db, doc)
        out.append({"set": st.get("name"), "swapped": swapped, "dropped": dropped, "items": len(new_items)})
    return out


BRAND_LOGO_MARKER = "brand_logo_grayzer_removed_2026_10_12_v1"


def strip_brand_logos(blocks: list) -> tuple:
    out, removed = [], 0
    for b in blocks or []:
        b = copy.deepcopy(b)
        if _type(b) == "brands_carousel":
            st = b.get("settings") or {}
            keep = [x for x in (st.get("brands") or []) if not re.search(HIDDEN_BRAND_RX, str((x or {}).get("name") or ""), re.I)]
            removed += len(st.get("brands") or []) - len(keep)
            st["brands"] = keep
            b["settings"] = st
        out.append(b)
    return out, removed


async def remove_brand_logo_once(db) -> int:
    """Sahip talebi: ana sayfa Markalar bandından Grayzer logosu kaldırılır (yeni yayın sürümü; bir kez)."""
    try:
        if await db.settings.find_one({"id": BRAND_LOGO_MARKER}, {"_id": 1}):
            return 0
        from pageblocks import store
        pub = await store.ensure(db, "home")
        blocks, removed = strip_brand_logos(pub.get("blocks") or [])
        if removed:
            draft = await store.get_draft(db, "home")
            doc, errors, _ = await store.publish(db, "home", user="sistem (marka logosu)", blocks=blocks,
                                                 global_=await store.get_global(db))
            if errors:
                logger.error("[%s] yayın hatası: %s", BRAND_LOGO_MARKER, errors)
                return 0
            if draft:
                draft = dict(draft)
                draft["blocks"], _r = strip_brand_logos(draft.get("blocks") or [])
                draft["rev"] = doc.get("rev")
                await db.page_layouts.replace_one({"id": "home:draft"}, draft, upsert=True)
        await db.settings.update_one({"id": BRAND_LOGO_MARKER}, {"$set": {"id": BRAND_LOGO_MARKER, "removed": removed,
                                                                         "applied_at": _now()}}, upsert=True)
        return removed
    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] hata: %s", BRAND_LOGO_MARKER, e)
        return 0


REAL_BRANDS_MARKER = "brands_real_2026_10_12_v1"
DEMO_BRAND_NAMES = {"liftmax", "airpro", "torkmatik", "balanstek", "voltix", "weldon", "diagnox", "teknolift",
                    "atölye pro", "atolye pro", "grayzer"}
REAL_BRANDS = [("Rico", "rico"), ("NT Tools", "nt-tools"), ("İzeltaş", "izeltas"), ("Ponis Metal", "ponis-metal"),
               ("DHT", "dht"), ("Demiriz", "demiriz"), ("Bosch", "bosch"), ("Catpower", "catpower")]


def real_brand_items() -> list:
    from urllib.parse import quote
    return [{"_id": uuid.uuid4().hex[:10], "name": n,
             "logo": {"url": f"/brands/{slug}.svg", "alt": n},
             "link": {"kind": "search", "url": f"/arama?q={quote(n)}", "new_tab": False}} for n, slug in REAL_BRANDS]


def swap_demo_brands(blocks: list) -> tuple:
    """Markalar bandındaki örnek (uydurma) markalar → mağazada satılan gerçek markalar. Panelden eklenmiş başka bir
    marka varsa korunur ve listenin sonuna eklenir."""
    out, changed = [], False
    for b in blocks or []:
        b = copy.deepcopy(b)
        if _type(b) == "brands_carousel":
            st = b.get("settings") or {}
            cur = [x for x in (st.get("brands") or []) if isinstance(x, dict)]
            others = [x for x in cur if str(x.get("name") or "").strip().lower() not in DEMO_BRAND_NAMES]
            if len(others) != len(cur) or not cur:
                have = {str(x.get("name") or "").strip().lower() for x in others}
                st["brands"] = [x for x in real_brand_items() if x["name"].lower() not in have] + others
                b["settings"] = st
                changed = True
        out.append(b)
    return out, changed


async def real_brands_once(db) -> bool:
    try:
        if await db.settings.find_one({"id": REAL_BRANDS_MARKER}, {"_id": 1}):
            return False
        from pageblocks import store
        pub = await store.ensure(db, "home")
        blocks, changed = swap_demo_brands(pub.get("blocks") or [])
        if changed:
            draft = await store.get_draft(db, "home")
            doc, errors, _ = await store.publish(db, "home", user="sistem (gerçek markalar)", blocks=blocks,
                                                 global_=await store.get_global(db))
            if errors:
                logger.error("[%s] yayın hatası: %s", REAL_BRANDS_MARKER, errors)
                return False
            if draft:
                draft = dict(draft)
                draft["blocks"], _c = swap_demo_brands(draft.get("blocks") or [])
                draft["rev"] = doc.get("rev")
                await db.page_layouts.replace_one({"id": "home:draft"}, draft, upsert=True)
        await db.settings.update_one({"id": REAL_BRANDS_MARKER}, {"$set": {"id": REAL_BRANDS_MARKER, "changed": changed,
                                                                          "applied_at": _now()}}, upsert=True)
        return changed
    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] hata: %s", REAL_BRANDS_MARKER, e)
        return False


async def deactivate_broken_sets(db) -> int:
    """Bileşeni 2'nin altına düşen (ör. tüm ürünleri satıştan kaldırılmış) aktif setleri pasife alır. Her açılışta,
    tekrarlanabilir."""
    n = 0
    async for st in db.products.find({"product_type": "set", "is_active": {"$ne": False}}, {"_id": 0, "id": 1, "set_items": 1}):
        ids = [i.get("product_id") for i in (st.get("set_items") or [])]
        active = await db.products.count_documents({"id": {"$in": ids}, "is_active": {"$ne": False}}) if ids else 0
        if active < 2:
            await db.products.update_one({"id": st["id"]}, {"$set": {
                "is_active": False, "deactivated_at": _now(),
                "deactivated_reason": "Setin aktif bileşeni kalmadı (2'den az)"}})
            n += 1
    return n


async def run_once(db=None) -> bool:
    try:
        if db is None:
            from routes.deps import db as _db
            db = _db
        if await db.settings.find_one({"id": MARKER}, {"_id": 1}):
            await apply_red_theme_once(db)
            await hide_grayzer_once(db)
            await deactivate_broken_sets(db)
            await remove_brand_logo_once(db)
            await real_brands_once(db)
            return False
        await _contact(db)
        if not await _layout(db):
            return False
        await db.settings.update_one({"id": MARKER}, {"$set": {"id": MARKER, "done": True, "applied_at": _now()}},
                                     upsert=True)
        logger.warning("[%s] uygulandı", MARKER)
        await apply_red_theme_once(db)
        await hide_grayzer_once(db)
        await deactivate_broken_sets(db)
        await remove_brand_logo_once(db)
        await real_brands_once(db)
        return True
    except Exception as e:  # noqa: BLE001 — açılışı asla düşürme
        logger.exception("[%s] hata: %s", MARKER, e)
        return False
