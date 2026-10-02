"""Kurumsal/hukuki CMS sayfaları: yer tutucu işleme ve idempotent tohumlama."""
import asyncio
import os
import sys

import pytest

pytest.importorskip("mongomock")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from localdb import AsyncIOMotorClient  # noqa: E402
import legal_pages as lp  # noqa: E402
from legal_content import LEGAL_PAGES, LEGAL_SLUGS, SLUG_ALIASES  # noqa: E402
from page_seed_data import DEFAULT_PAGES as OLD_PAGES  # noqa: E402
import tenant_config  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def db(tmp_path):
    tenant_config.invalidate()
    d = AsyncIOMotorClient(path=str(tmp_path / "t.db"))["shop"]
    yield d
    d.client.close()
    tenant_config.invalidate()


CFG = {
    "brand": {"store_name": "GarajTek"},
    "company": {"legal_name": "ACME <Ltd> & Şti", "address": "Mahmutbey Mah. 2453. Sk. No: 46",
                "city": "Bağcılar / İstanbul", "tax_office": "Güneşli", "tax_number": "8961050800"},
    "contact": {"email": "info@garajtek.com", "phone": "0543 579 10 56"},
    "domains": {"storefront_url": "https://garajtek.com"},
}


# ───────────────────────────────────────────────────────── yer tutucu işleme
def test_render_company_placeholders_escaped_and_markers():
    v = lp.values_from_config(CFG)
    out = lp.render("<p>{{sirket.unvan}} | {{ sirket.vkn }} | {{sirket.mersis}} | {{site.url}} | "
                    "{{sirket.telefon_tel}} | {{bilinmeyen.alan}}</p>", v)
    assert "ACME &lt;Ltd&gt; &amp; Şti" in out          # HTML-escape
    assert "8961050800" in out
    assert "[MERSİS No]" in out                          # boş alan açıkça işaretlenir
    assert "https://garajtek.com" in out
    assert "05435791056" in out
    assert "{{bilinmeyen.alan}}" in out                  # bilinmeyen anahtar korunur
    assert "Mahmutbey Mah. 2453. Sk. No: 46 Bağcılar / İstanbul" == v["sirket.adres"]


def test_render_legacy_keys_and_order_fields():
    v = lp.values_from_config(CFG)
    assert lp.render("{{company_name}}/{{store_name}}/{{site}}", v) == "ACME &lt;Ltd&gt; &amp; Şti/GarajTek/garajtek.com"
    txt = "<td>{{alici.ad}}</td>{{siparis.urunler}}"
    kept = lp.render(txt, v, keep_order_fields=True)
    assert kept == txt
    public = lp.render(txt, v)
    assert "{{" not in public and "sipariş" in public


def test_all_seed_pages_render_without_leftover_placeholders():
    v = lp.values_from_config(CFG)
    for p in LEGAL_PAGES:
        for k in ("title", "content", "meta_title", "meta_description"):
            out = lp.render(p[k], v)
            assert "{{" not in out, (p["slug"], k)
        assert "8961050800" not in p["content"]          # firma bilgisi metne gömülü değil


def test_aliases_point_to_seeded_slugs():
    for alias, target in SLUG_ALIASES.items():
        assert target in LEGAL_SLUGS, alias
        assert lp.canonical_slug(alias) == target


def test_legacy_template_detection():
    old = next(p for p in OLD_PAGES if p["slug"] == "kvkk")
    filled = old["content"].replace("{{company_name}}", "Eski Firma A.Ş.").replace("{{phone}}", "0212 000")
    assert lp.is_pristine({"slug": "kvkk", "content": filled})
    assert not lp.is_pristine({"slug": "kvkk", "content": filled + "<p>admin ekledi</p>"})
    assert not lp.is_pristine({"slug": "ozel-sayfa", "content": "<p>x</p>"})


# ───────────────────────────────────────────────────────── tohumlama
def test_seed_fresh_db_is_idempotent(db):
    async def go():
        r1 = await lp.ensure_legal_pages(db)
        assert sorted(r1["created"]) == sorted(LEGAL_SLUGS)
        r2 = await lp.ensure_legal_pages(db)
        assert r2["created"] == [] and r2["updated"] == []
        assert sorted(r2["unchanged"]) == sorted(LEGAL_SLUGS)
        assert await db.pages.count_documents({}) == len(LEGAL_SLUGS)
    run(go())


def test_seed_upgrades_untouched_old_pages_and_keeps_edited(db):
    async def go():
        old = {p["slug"]: p for p in OLD_PAGES}
        untouched = old["mesafeli-satis"]["content"].replace("{{company_name}}", "Eski Ltd").replace(
            "{{address}}", "Eski adres").replace("{{phone}}", "0").replace("{{email}}", "a@b.c")
        await db.pages.insert_one({"id": "1", "slug": "mesafeli-satis", "title": "Mesafeli Satış",
                                   "content": untouched, "is_active": True})
        await db.pages.insert_one({"id": "2", "slug": "kvkk", "title": "KVKK",
                                   "content": "<p>Avukatımızın yazdığı metin</p>", "is_active": True})
        await db.pages.insert_one({"id": "3", "slug": "gizlilik", "title": "Gizlilik",
                                   "content": old["gizlilik"]["content"], "is_active": False})
        r = await lp.ensure_legal_pages(db)
        assert "mesafeli-satis" in r["updated"] and "gizlilik" in r["updated"]
        assert r["kept_customized"] == ["kvkk"]
        kv = await db.pages.find_one({"slug": "kvkk"})
        assert kv["content"] == "<p>Avukatımızın yazdığı metin</p>"
        ms = await db.pages.find_one({"slug": "mesafeli-satis"})
        assert "{{sirket.unvan}}" in ms["content"] and ms["seed_hash"]
        gz = await db.pages.find_one({"slug": "gizlilik"})
        assert gz["is_active"] is False                    # pasif kararı korunur

        # admin düzenlerse sonraki çalıştırmada korunur
        await db.pages.update_one({"slug": "mesafeli-satis"}, {"$set": {"content": ms["content"] + "<p>ek</p>"}})
        r2 = await lp.ensure_legal_pages(db)
        assert "mesafeli-satis" in r2["kept_customized"]
        # admin sayfayı silerse yeniden dayatılmaz
        await db.pages.delete_one({"slug": "cerez-politikasi"})
        r3 = await lp.ensure_legal_pages(db)
        assert "cerez-politikasi" in r3["skipped_deleted"]
        # açık "varsayılana döndür"
        r4 = await lp.ensure_legal_pages(db, force_slugs={"kvkk", "cerez-politikasi"})
        assert "kvkk" in r4["updated"] and "cerez-politikasi" in r4["created"]
    run(go())


def test_company_defaults_only_fill_empty_once(db):
    async def go():
        await db.settings.insert_one({"id": "tenant_config", "company": {"legal_name": "Admin Ünvanı"},
                                      "contact": {"phone": ""}})
        r = await lp.apply_company_defaults(db)
        assert "company.legal_name" not in r["applied"]
        assert "contact.phone" in r["applied"] and "company.tax_number" in r["applied"]
        cfg = await tenant_config.get_tenant_config(db, use_cache=False)
        assert cfg["company"]["legal_name"] == "Admin Ünvanı"
        assert cfg["company"]["tax_number"] == "8961050800"
        assert cfg["brand"]["store_name"] == "GarajTek"
        # admin bir alanı bilerek boşaltırsa tekrar doldurulmaz
        await db.settings.update_one({"id": "tenant_config"}, {"$set": {"contact.phone": ""}})
        r2 = await lp.apply_company_defaults(db)
        assert r2["applied"] == []
        tenant_config.invalidate()
        cfg = await tenant_config.get_tenant_config(db, use_cache=False)
        assert cfg["contact"]["phone"] == ""
    run(go())


def test_render_page_uses_live_company_settings(db):
    async def go():
        await lp.ensure_legal_pages(db)
        await lp.apply_company_defaults(db)
        page = await db.pages.find_one({"slug": "kvkk"}, {"_id": 0})
        out = await lp.render_page(db, page)
        assert "USTAELLER TEKNİK YAPI HIRDAVAT" in out["content"]
        assert "seed_hash" not in out
        await db.settings.update_one({"id": "tenant_config"}, {"$set": {"company.mersis_number": "0123456789012345"}})
        tenant_config.invalidate()
        out2 = await lp.render_page(db, page)
        assert "0123456789012345" in out2["content"]
    run(go())
