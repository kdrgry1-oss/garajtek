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
