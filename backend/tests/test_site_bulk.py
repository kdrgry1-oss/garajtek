"""Toplu site aktarımı (url_import.site_bulk) — sahte HTTP, ağ yok."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_url_import import Store, _creator, _fetcher, _img, _ld_page, _run  # noqa: E402
from url_import import site_bulk as SB  # noqa: E402

B = "https://www.shop.example"
H = {"content-type": "text/html; charset=utf-8"}
X = {"content-type": "application/xml"}


def _routes():
    idx = (f'<?xml version="1.0"?><sitemapindex><sitemap><loc>{B}/sitemap-products.xml</loc></sitemap>'
           f'<sitemap><loc>{B}/sitemap-categories.xml</loc></sitemap></sitemapindex>').encode()
    prods = (f'<urlset><url><loc>{B}/urun/lift-4-ton</loc></url><url><loc>{B}/urun/kompresor-100</loc></url>'
             f'<url><loc>{B}/urun/yok</loc></url><url><loc>https://baska.example/urun/x</loc></url></urlset>').encode()
    return {
        f"{B}/robots.txt": (200, {"content-type": "text/plain"}, f"User-agent: *\nSitemap: {B}/sitemap.xml\n".encode()),
        f"{B}/sitemap.xml": (200, X, idx),
        f"{B}/sitemap-products.xml": (200, X, prods),
        f"{B}/sitemap-categories.xml": (200, X, f"<urlset><url><loc>{B}/kategori/liftler</loc></url></urlset>".encode()),
        f"{B}/urun/lift-4-ton": (200, H, _ld_page("Lift 4 Ton", "100000", "L4", [f"{B}/img/l.jpg"])),
        f"{B}/urun/kompresor-100": (200, H, _ld_page("Kompresör 100 Lt", "2000", "K1", [f"{B}/img/k.jpg"],
                                                       crumbs=("Kompresörler",))),
        f"{B}/img/l.jpg": (200, {"content-type": "image/jpeg"}, _img()),
        f"{B}/img/k.jpg": (200, {"content-type": "image/jpeg"}, _img(color=(1, 2, 3))),
    }


@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    return AsyncIOMotorClient(path=str(tmp_path / "bulk.db"))["test"]


def test_bulk_import_sitemap_price_and_resume(db, monkeypatch):
    from seed_categories import load_tree, seed_categories
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    _run(seed_categories(db, load_tree()))
    store = Store(db)
    routes = _routes()

    def go():
        return _run(SB.run(db, create_product=_creator(db), store_image=store.store, delete_file=store.delete,
                           sites=[B], fetcher_factory=lambda: _fetcher(routes)))

    res = go()
    assert res["shop.example"]["imported"] == 2, res
    q = _run(db.site_import_queue.find({}, {"_id": 0}).to_list(50))
    assert {r["url"] for r in q} == {f"{B}/urun/lift-4-ton", f"{B}/urun/kompresor-100", f"{B}/urun/yok"}
    by = {r["url"]: r for r in q}
    assert by[f"{B}/urun/yok"]["status"] == "pending" and by[f"{B}/urun/yok"]["attempts"] == 1
    p = _run(db.products.find_one({"stock_code": "L4"}, {"_id": 0}))
    assert p["price"] == 110000.0 and p["is_active"] is True
    assert p["demo"] is False and p["noindex"] is False and p["image_credit"] == ""
    assert p["seed_source"] == SB.SEED_SOURCE and len(p["images"]) == 1
    # yeniden başlatma: keşif tekrarlanmaz, tamamlananlar yeniden yazılmaz, başarısız 3. denemede bırakılır
    del routes[f"{B}/sitemap.xml"]
    go()
    go()
    assert _run(db.products.count_documents({"seed_source": SB.SEED_SOURCE})) == 2
    yok = _run(db.site_import_queue.find_one({"url": f"{B}/urun/yok"}, {"_id": 0}))
    assert yok["status"] == "failed" and yok["attempts"] == 3
    st = _run(SB.status(db))
    assert st["hosts"]["shop.example"] == {"done": 2, "failed": 1}


def test_crawl_fallback_without_sitemap(db, monkeypatch):
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    home = (f'<html><body><nav><a href="/kategori/liftler">Liftler</a></nav>'
            f'<a href="/urun/lift-4-ton">Lift</a></body></html>').encode()
    routes = {f"{B}/": (200, H, home), f"{B}/kategori/liftler": (200, H, b"<html><body></body></html>")}

    async def go():
        async with _fetcher(routes) as f:
            assert await SB.discover_sitemap(f, B) == []
            return await SB.discover_crawl(f, B)
    assert _run(go()) == [f"{B}/urun/lift-4-ton"]


def test_tag_pages_skipped_and_wrong_imports_removed(db, monkeypatch):
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    store = Store(db)
    assert SB.is_candidate(f"{B}/meta-etiket/duz-keski-fiyat", B) is False
    assert SB.is_candidate(f"{B}/takim-arabalari-7-cekmeceli", B) is True
    tag = f"{B}/meta-etiket/duz-keski"
    _run(db.site_import_queue.insert_one({"url": tag, "host": "shop.example", "status": "done", "attempts": 0}))
    _run(db.site_import_queue.insert_one({"url": f"{B}/urun/a", "host": "shop.example", "status": "done"}))
    _run(db.products.insert_one({"id": "t1", "seed_source": SB.SEED_SOURCE, "source_url": tag}))
    _run(db.products.insert_one({"id": "ok1", "seed_source": SB.SEED_SOURCE, "source_url": f"{B}/urun/a"}))
    _run(db.files.insert_one({"id": "f1", "seed_source": SB.SEED_SOURCE, "source_page": tag}))
    res = _run(SB.cleanup_non_products(db, store.delete))
    assert res == {"skipped": 1, "removed_products": 1, "removed_files": 1}
    assert _run(db.products.count_documents({})) == 1
    assert _run(db.site_import_queue.find_one({"url": tag}))["status"] == "skipped"


def test_recategorize_by_name_rules(db):
    from seed_categories import load_tree, seed_categories
    _run(seed_categories(db, load_tree()))
    cats = {c["slug"]: c for c in _run(db.categories.find({}, {"_id": 0}).to_list(500))}
    fren_test = cats["fren-test-cihazlari"]["id"]
    _run(db.products.insert_many([
        {"id": "a", "seed_source": SB.SEED_SOURCE, "name": "Grayzer Silikon Sprey 500 ML", "category_id": ""},
        {"id": "b", "seed_source": SB.SEED_SOURCE, "name": "Grayzer Fren Balata Temizleme Spreyi 500 ML",
         "category_id": fren_test},
        {"id": "c", "seed_source": SB.SEED_SOURCE, "name": "DHT 125 mm Tezgah Üstü Mengene", "category_id": ""},
        {"id": "d", "seed_source": SB.SEED_SOURCE, "name": "DHT 1 Ton Katlanır Hidrolik Vinç",
         "category_id": cats["motor-vincleri"]["id"]},
        {"id": "e", "seed_source": "baska", "name": "Silikon Sprey", "category_id": ""},
    ]))
    assert _run(SB.recategorize(db)) == 3
    get = lambda i: _run(db.products.find_one({"id": i}, {"_id": 0}))  # noqa: E731
    a = get("a")
    assert a["category_id"] == cats["temizleme-ve-bakim-spreyleri"]["id"]
    assert a["category_ids"][-1] == cats["bakim-kimyasallari-ve-spreyler"]["id"]
    assert get("b")["category_name"] == "Temizleme ve Bakım Spreyleri"
    assert get("c")["category_id"] == cats["mengeneler"]["id"]
    assert get("d")["category_id"] == cats["motor-vincleri"]["id"]
    assert get("e")["category_id"] == ""
    assert _run(SB.recategorize(db)) == 0
