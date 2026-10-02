"""Sayfa Tasarımı v2 geçişi (SPEC §6.2): canlı DB'den alınmış anonim blok dökümleri (fixture) →
(a) hiçbir yönetici değeri kaybolmaz, (b) şema doğrulaması geçer, (c) idempotent."""
import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pageblocks as pb  # noqa: E402
from pageblocks import migrations as mig  # noqa: E402
from pageblocks import store  # noqa: E402

FIX = json.loads((Path(__file__).parent / "fixtures" / "page_blocks_v1.json").read_text(encoding="utf-8"))
CTX = {"cat_names": {"c-lift": "Liftler", "c-komp": "Kompresörler"}, "cat_slugs": {"liftler", "kompresorler"}}


def _run(c):
    return asyncio.run(c)


def _by_id(blocks):
    return {b["id"]: b for b in blocks}


def _strings(v, out=None):
    out = set() if out is None else out
    if isinstance(v, dict):
        for x in v.values():
            _strings(x, out)
    elif isinstance(v, list):
        for x in v:
            _strings(x, out)
    elif isinstance(v, (str, int, float)) and not isinstance(v, bool):
        out.add(str(v))
    return out


@pytest.fixture(scope="module")
def migrated():
    return _by_id(mig.migrate_page(copy.deepcopy(FIX), CTX, "home"))


def test_every_block_kept_in_order_with_ids(migrated):
    ids = [b["id"] for b in mig.migrate_page(copy.deepcopy(FIX), CTX, "home")]
    assert ids == [b["id"] for b in sorted(FIX, key=lambda b: b["sort_order"])]
    assert migrated["b-cd"]["is_active"] is False


def test_all_validate_without_errors(migrated):
    for b in migrated.values():
        if b["settings"].get("_legacy"):
            continue
        assert not b["settings"].get("_migration_errors"), (b["id"], b["settings"].get("_migration_errors"))
        _c, errors, _w = pb.validate_block(b, strict=True)
        assert errors == [], (b["id"], errors)


def test_hero_parallel_arrays_become_slides(migrated):
    st = migrated["b-hero"]["settings"]
    assert st["_variant"] == "v1" and st["_v"] == 2
    s = st["slides"]
    assert len(s) == 3
    assert s[0]["background"]["url"] == "/api/upload/files/hero-a.webp"
    assert (s[0]["background"]["w"], s[0]["background"]["h"]) == (1920, 422)
    assert s[0]["background"]["mobile_url"] == "/api/upload/files/hero-a-m.webp"
    assert "mobile_url" not in s[1]["background"]
    assert s[2]["background"]["mobile_url"] == "/api/upload/files/hero-c-m.webp"
    assert s[0]["title"] == "Lift Kampanyası" and s[0]["subtitle"] == "4 TON ÇİFT SÜTUN"
    assert s[0]["price"] == "₺129.900" and s[0]["button"]["text"] == "İncele"
    assert s[0]["button"]["link"] == {"kind": "category", "url": "/liftler", "slug": "liftler", "new_tab": False}
    # caption.link kazanır, eyebrow → subtitle
    assert s[1]["button"]["link"]["url"] == "/kampanya/kompresor" and s[1]["subtitle"] == "ATÖLYENİN GÜCÜ"
    assert s[1]["_schedule"] == {"start": "2026-01-01T00:00", "end": "2026-01-31T23:59"}
    assert s[2]["price_prefix"] == "şimdi sadece" and s[2]["price"] == "₺24.900"
    assert st["carousel"]["autoplay"] is True and st["carousel"]["interval"] == 7000
    assert all(x.get("_id") for x in s)


def test_slide_schedule_filter_keeps_captions_aligned(migrated):
    """Eski hata: slide_schedule images'ı süzüp captions'ı süzmüyordu → kayık açıklamalar."""
    from datetime import datetime, timezone
    pub = pb.apply_schedule([migrated["b-hero"]], datetime(2026, 3, 1, tzinfo=timezone.utc))
    slides = pub[0]["settings"]["slides"]
    assert [x["title"] for x in slides] == ["Lift Kampanyası", "Lastik Servisi"]
    assert slides[1]["background"]["url"].endswith("hero-c.webp")
    inside = pb.apply_schedule([migrated["b-hero"]], datetime(2026, 1, 15, tzinfo=timezone.utc))
    assert len(inside[0]["settings"]["slides"]) == 3


def test_ads_items(migrated):
    it = migrated["b-ads"]["settings"]["items"]
    assert it[0]["text"] == "Lokma<br><strong>TAKIMLARI</strong> burada"
    assert it[0]["action_type"] == "link" and it[0]["action_text"] == "Göz At"
    assert it[0]["image"]["url"] == "/api/upload/files/ad-1.webp"
    assert it[1]["action_type"] == "upto" and it[1]["action_value"] == "35"
    assert it[1]["link"]["kind"] == "category"
    assert it[2]["image"] is None and it[2]["link"]["url"] == "/tum-urunler?sort=popular&order=desc"


def test_deals_tabs_and_grid(migrated):
    d = migrated["b-deals"]["settings"]
    assert d["deal"]["mode"] == "manual" and d["deal"]["title"] == "Haftanın Fırsatı" and d["deal"]["product"] == "p-77"
    assert [t["label"] for t in d["tabs"]] == ["Vitrin", "Fırsatlar", "Popüler", "Liftler"]
    assert [t["source"]["kind"] for t in d["tabs"]] == ["featured", "discounted", "best_sellers", "category"]
    assert d["tabs"][3]["source"]["category_ids"] == ["c-lift"]
    g = migrated["b-212"]["settings"]
    assert g["nav_items"][0]["label"] == "Süper Fırsatlar" and g["nav_items"][0]["source"]["kind"] == "featured"
    assert [x["label"] for x in g["nav_items"][1:]] == ["Liftler", "Kompresörler"]
    assert g["nav_auto_categories"]["enabled"] is False and g["nav_auto_categories"]["max"] == 3


def test_best_sellers_visibility_and_schedule(migrated):
    b = migrated["b-best"]["settings"]
    assert b["header"]["title"] == "En Çok Satılanlar"
    assert b["header"]["pills"][0]["label"] == "Top 20"
    assert b["header"]["pills"][1]["label"] == "Kompresörler"
    assert b["header"]["pills"][1]["source"]["category_ids"] == ["c-komp"]
    assert b["_visibility"]["desktop"] is True and b["_visibility"]["mobile"] is False
    assert b["_visibility"]["schedule"]["start"].startswith("2026-02-01T09:00+00:00")


def test_banners_sliders_brands_columns(migrated):
    f = migrated["b-full"]["settings"]
    assert f["image"]["url"] == "/api/upload/files/wide.webp" and f["link"]["url"] == "/indirimli-urunler"
    assert f["image"]["alt"] == "Atölye Kampanyası"
    s = migrated["b-slider"]["settings"]
    assert s["header"]["title"] == "Kompresör Dünyası"
    assert s["source"]["kind"] == "category" and s["source"]["category_ids"] == ["c-komp"] and s["source"]["limit"] == 10
    assert s["header"]["link"]["label"] == "Tümü" and s["_section"]["background"] == "#f5f5f5"
    s2 = migrated["b-slider2"]["settings"]
    assert s2["source"]["kind"] == "manual" and s2["source"]["product_ids"] == ["p-1", "p-2", "p-3"]
    br = migrated["b-brands"]["settings"]
    assert br["source"] == "manual" and [x["name"] for x in br["brands"]] == ["Liftmax", "Air Pro"]
    assert br["brands"][0]["logo"]["url"] == "/api/upload/files/brand-1.png"
    cols = migrated["b-cols"]["settings"]["columns"]
    assert [c["title"] for c in cols] == ["Vitrin", "İndirim", "Popüler"]
    assert [c["source"]["kind"] for c in cols] == ["featured", "discounted", "best_sellers"]


def test_text_video_insta_half_topbars(migrated):
    t = migrated["b-text"]["settings"]
    assert t["title"] == "Neden Biz?" and t["body"] == "20 yıllık tecrübe.<br>Yetkili servis &lt;güvencesi&gt;."
    assert t["image"]["url"].endswith("about.webp") and t["link"]["url"] == "/sayfa/hakkimizda"
    v = migrated["b-video"]["settings"]
    assert v["video"]["url"].endswith("v.mp4") and v["poster"]["url"].endswith("poster.webp")
    i = migrated["b-insta"]["settings"]
    assert i["title"] == "Instagram'da Biz" and len(i["items"]) == 2
    h = migrated["b-half"]["settings"]
    assert [x["link"]["url"] for x in h["items"]] == ["/a", "/b"]
    r = migrated["b-rot"]["settings"]
    assert [m["text"] for m in r["messages"]] == ["2.500 TL üzeri kargo bedava", "Kapıda ödeme seçeneği"]
    assert r["interval"] == 5000 and r["background"] == "#111111"
    c = migrated["b-cd"]["settings"]
    assert c["text"] == "YAZ KAMPANYASI\nSEPETTE %10" and c["countdown"]["heading"] == "BİTİMİNE:"
    assert c["countdown"]["end"] == "2026-06-30T23:59:59" and c["countdown"]["on_expire"] == "show_text"
    assert c["countdown"]["expired_text"] == "Kampanya bitti"


def test_unknown_type_kept_as_legacy(migrated):
    u = migrated["b-unknown"]
    assert u["settings"]["_legacy"] is True
    assert u["settings"]["_legacy_source"]["settings"]["token"] == "gizli-değil"
    assert pb.apply_schedule([u]) == []


def test_no_admin_value_lost(migrated):
    """Eski bloktaki her anlamlı metin/URL değeri yeni blokta (bir yerde) bulunmalı."""
    ignore = {"electro", "electro_home_v1", "eski", "Europe/Istanbul", "Europe/London", "home", "category",
              "popular", "featured", "discounted", "true", "false"}
    for old in FIX:
        new = migrated[old["id"]]
        have = _strings(new)
        have_txt = " ".join(have)
        vals = _strings({k: v for k, v in old.items() if k in ("images", "links", "settings", "title")})
        for v in vals:
            if v in ignore or v in ("", "0", "2", "3", "4", "5", "7000", "10"):
                continue
            if v.isdigit() and int(v) < 100:
                continue
            frag = v.replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
            ok = v in have or frag in have_txt or v.replace("\n", "<br>") in have_txt or \
                any(p.strip() and p.strip() in have_txt for p in v.split("|")) or \
                v.replace("{year}", "{yıl}") in have_txt or \
                any(v.replace(".", "").replace(",", "") in x.replace(".", "") for x in have) or \
                v.replace(" ", "+") in have_txt
            if old["id"] == "b-hero" and v == "/kompresorler":
                ok = True  # SPEC §6.2: slayt açıklamasının kendi bağlantısı links[i]'den önceliklidir
            if old["type"] == "countdown_bar" and v == "2026-06-01T00:00":
                ok = True  # yedek metin varken başlangıç → sayaç dışı (eski davranış)
            assert ok, (old["id"], v)


def test_migrate_block_is_idempotent(migrated):
    for b in migrated.values():
        again = mig.migrate_block(copy.deepcopy(b), CTX)
        assert again["settings"] == b["settings"]
    twice = mig.migrate_page(copy.deepcopy(FIX), CTX, "home")
    assert twice == mig.migrate_page(copy.deepcopy(FIX), CTX, "home")


def test_pristine_blocks_get_full_template_defaults():
    old = {"id": "x", "type": "ads_block", "title": "Reklam Bannerları", "images": [],
           "settings": {"layout": "electro_home_v1", "items": [{"pre": "a", "strong": "b"}]}}
    b = mig.migrate_block(old, CTX)
    assert b["settings"]["items"][0]["text"] == pb.default_settings("ads_block")["items"][0]["text"]


# ------------------------------------------------------------ canlı (localdb) çalışma
@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    return AsyncIOMotorClient(path=str(tmp_path / "pd.db"))["test"]


def _seed(db):
    async def go():
        for b in FIX:
            await db.page_blocks.insert_one(copy.deepcopy(b))
        await db.categories.insert_one({"id": "c-lift", "name": "Liftler", "slug": "liftler"})
        await db.settings.insert_one({"id": "site_menus", "topbar": {"welcome": "Hoş geldin usta!", "items": [
            {"id": "x", "label": "Bayiler", "link": "/sayfa/bayiler", "icon": "ec ec-map-pointer"}]},
            "center": {"right_text": "Aynı gün kargo", "right_link": "/sayfa/kargo"}})
        await db.settings.insert_one({"id": "footer", "mode": "structured", "columns": [
            {"title": "Kurumsal", "links": [{"to": "/sayfa/hakkimizda", "label": "Biz Kimiz"}]}],
            "newsletter": {"title": "Bülten", "description": "Fırsatları kaçırmayın", "placeholder": "e-posta"},
            "social": {"instagram": "https://instagram.com/garaj", "facebook": ""},
            "copyright": "© {year} Garaj", "payment_band_url": "/api/upload/files/pay.png"})
    _run(go())


def test_run_migration_backup_publish_mirror_and_idempotent(db):
    _seed(db)
    res = _run(mig.run_migration(db))
    assert res and res["pages"]["home"] == len(FIX) and res["legacy"] == 1
    rev0 = _run(db.page_layout_revisions.find_one({"id": "home:rev:0"}))
    assert rev0["raw"] and len(rev0["blocks"]) == len(FIX) and rev0["summary"] == "Geçiş öncesi yedek"
    pub = _run(db.page_layouts.find_one({"id": "home:published"}, {"_id": 0}))
    assert pub["rev"] == 1 and [b["id"] for b in pub["blocks"]][:3] == ["b-rot", "b-cd", "b-hero"]
    mirror = _run(db.page_blocks.find({}, {"_id": 0}).to_list(None))
    assert len(mirror) == len(FIX) and all(m["settings"].get("_v") == 2 or m["settings"].get("_legacy") for m in mirror)
    sd = _run(db.settings.find_one({"id": "site_design"}))["published"]
    assert sd["site_topbar"]["welcome_text"] == "Hoş geldin usta!"
    assert sd["site_topbar"]["right_items"][0]["label"] == "Bayiler"
    assert sd["site_secondary_menu"]["right_text"] == "Aynı gün kargo"
    assert sd["site_footer_links"]["columns"][0]["links"][0]["label"] == "Biz Kimiz"
    assert sd["site_newsletter"]["title"] == "Bülten" and sd["site_newsletter"]["placeholder"] == "e-posta"
    assert sd["site_footer_contact"]["social"] == [{"network": "instagram", "url": "https://instagram.com/garaj",
                                                   "_id": sd["site_footer_contact"]["social"][0]["_id"]}]
    assert sd["site_footer_bottom"]["copyright"] == "© {yıl} Garaj"
    assert sd["site_footer_bottom"]["payment_band_image"]["url"] == "/api/upload/files/pay.png"
    # ikinci çalıştırma hiçbir şey yapmaz
    assert _run(mig.run_migration(db)) is None
    assert _run(db.page_layouts.find_one({"id": "home:published"}, {"_id": 0})) == pub
    # public: inaktif + legacy + zamanı gelmemiş dönmez
    blocks = _run(store.public_blocks(db, "home"))
    ids = [b["id"] for b in blocks]
    assert "b-cd" not in ids and "b-unknown" not in ids and "b-hero" in ids


def test_restore_rev0_reconverts_into_draft(db):
    _seed(db)
    _run(mig.run_migration(db))
    doc, errors, _w = _run(store.restore_revision(db, "home", 0, user="t"))
    assert doc["id"] == "home:draft" and len(doc["blocks"]) == len(FIX) and errors == []
    assert doc["global"]["site_topbar"]["welcome_text"] == "Hoş geldin usta!"


def test_empty_db_gets_default_home(db):
    res = _run(mig.run_migration(db))
    pub = _run(db.page_layouts.find_one({"id": "home:published"}))
    assert res["pages"]["home"] == 9
    assert [b["type"] for b in pub["blocks"]] == [k for k, _v, _t in pb.DEFAULT_HOME]
