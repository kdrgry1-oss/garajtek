"""Panel ↔ vitrin SEO tutarlılığı (e2e bulguları #41-#49 regresyonları):
CMS sayfa meta'sı, sitemap/noindex tutarlılığı, boş genel SEO ayarları, pasif kategori,
CMS slug normalizasyonu + 301, Merchant feed çift kaçış ve görselsiz ürünler."""
import asyncio
import os
import sys

import pytest

pytest.importorskip("mongomock")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from localdb import AsyncIOMotorClient  # noqa: E402
import tenant_config  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def _real_routes(monkeypatch):
    """Diğer testlerin bıraktığı sahte `routes` paketlerini bu test süresince kaldırır."""
    real_dir = os.path.join(ROOT, "routes")
    for name in [n for n in list(sys.modules) if n == "routes" or n.startswith("routes.")]:
        f = getattr(sys.modules[name], "__file__", None) or ""
        if not f.startswith(real_dir):
            monkeypatch.delitem(sys.modules, name)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    tenant_config.invalidate()
    _real_routes(monkeypatch)
    d = AsyncIOMotorClient(path=str(tmp_path / "seo.db"))["shop"]
    import routes.extras as ex
    import routes.pages as pg
    import routes.products as rp
    import routes.seo as seo
    for m in (ex, pg, rp, seo):
        monkeypatch.setattr(m, "db", d)
    yield d
    d.client.close()
    tenant_config.invalidate()


def _meta(path):
    import routes.extras as ex
    return run(ex.seo_page_meta(path=path))


def _sitemap():
    import routes.seo as seo
    return run(seo.sitemap_xml()).body.decode()


# ── #41/#42: /sayfa/* panel meta'sı + indekslenebilirlik ─────────────────────

def test_cms_page_meta_uses_panel_seo_fields_and_is_indexable(db):
    run(db.pages.insert_one({"id": "p1", "slug": "sync-test-sayfa", "title": "Hakkımızda {{site.ad}}",
                             "content": "<p>İçerik</p>", "meta_title": "SYNC Meta Baslik",
                             "meta_description": "SYNC meta aciklama", "is_active": True}))
    m = _meta("/sayfa/sync-test-sayfa")
    assert m["found"] is True and m["type"] == "page"
    assert m["title"] == "SYNC Meta Baslik"
    assert m["description"] == "SYNC meta aciklama"
    assert m["canonical"].endswith("/sayfa/sync-test-sayfa")
    assert "noindex" not in m["robots"]
    # meta_title boşsa sayfa başlığı (yer tutucu çözülmüş) kullanılır
    run(db.pages.update_one({"id": "p1"}, {"$set": {"meta_title": ""}}))
    m = _meta("/sayfa/sync-test-sayfa")
    assert "{{" not in m["title"] and m["title"].startswith("Hakkımızda")


def test_cms_page_missing_or_inactive_is_noindex_and_override_applies(db):
    run(db.pages.insert_one({"id": "p2", "slug": "pasif", "title": "P", "is_active": False}))
    assert "noindex" in _meta("/sayfa/pasif")["robots"]
    assert "noindex" in _meta("/sayfa/yok-boyle")["robots"]
    run(db.pages.insert_one({"id": "p3", "slug": "kvkk", "title": "KVKK", "is_active": True}))
    run(db.seo_meta.insert_one({"path": "/sayfa/kvkk", "title": "Ozel", "noindex": True}))
    m = _meta("/sayfa/kvkk")
    assert m["title"] == "Ozel" and m["robots"] == "noindex,nofollow"
    # Eski alias adresi kanonik sayfaya canonical'lanır
    run(db.seo_meta.delete_many({}))
    m = _meta("/sayfa/kvkk-aydinlatma-metni")
    assert m["canonical"].endswith("/sayfa/kvkk") and "noindex" not in m["robots"]


def test_nonexistent_root_legal_paths_not_indexable(db):
    # /hakkimizda, /kvkk kökte rota değil (içerik /sayfa/* altında)
    assert "noindex" in _meta("/hakkimizda")["robots"]
    assert "noindex" in _meta("/kvkk")["robots"]


def test_sitemap_skips_noindex_override_paths_and_encodes_slugs(db):
    run(db.pages.insert_one({"id": "a", "slug": "acik", "title": "A", "is_active": True}))
    run(db.pages.insert_one({"id": "b", "slug": "gizli", "title": "B", "is_active": True}))
    run(db.pages.insert_one({"id": "c", "slug": "Eski Büyük", "title": "C", "is_active": True}))
    run(db.seo_meta.insert_one({"path": "/sayfa/gizli", "noindex": True}))
    body = _sitemap()
    assert "/sayfa/acik<" in body
    assert "/sayfa/gizli<" not in body
    assert "Eski Büyük" not in body and "/sayfa/Eski%20B%C3%BCy%C3%BCk<" in body


# ── #45: boş genel SEO ayarı başlığı silmez ──────────────────────────────────

def test_home_meta_drops_empty_values_and_uses_panel_values(db):
    m = _meta("/")
    assert m["found"] is True
    for k in ("title", "description", "og_title", "og_description", "og_image"):
        assert m.get(k, None) != "", k  # boş anahtar gönderilmez
    import routes.extras as ex
    cfg = run(tenant_config.get_tenant_config(db, use_cache=False))
    seo = {**cfg["seo_geo"], "default_title": "SYNC- Ana Baslik", "default_description": "SYNC- aciklama"}
    run(db.settings.update_one({"id": "tenant_config"},
                               {"$set": tenant_config.TenantConfig.model_validate({**cfg, "seo_geo": seo}).model_dump()},
                               upsert=True))
    ex.invalidate_tenant_config(db)
    m = _meta("/")
    assert m["title"] == "SYNC- Ana Baslik" and m["description"] == "SYNC- aciklama"


# ── #47: pasif kategori ──────────────────────────────────────────────────────

def test_inactive_category_is_noindex(db):
    run(db.categories.insert_one({"id": "k1", "slug": "pasif-kat", "name": "Pasif", "is_active": False}))
    run(db.categories.insert_one({"id": "k2", "slug": "aktif-kat", "name": "Aktif", "is_active": True}))
    m = _meta("/kategori/pasif-kat")
    assert m.get("type") != "category" and "noindex" in m["robots"]
    m = _meta("/kategori/aktif-kat")
    assert m["type"] == "category" and "noindex" not in m["robots"]


# ── #48: CMS slug normalizasyonu + otomatik 301 ──────────────────────────────

def test_page_slug_normalized_and_old_slug_redirects(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import routes.pages as pg
    import routes.extras as ex
    app = FastAPI()
    app.include_router(pg.router, prefix="/api")
    app.include_router(ex.seo_public_router, prefix="/api")
    app.dependency_overrides[pg.require_admin] = lambda: {"id": "adm", "email": "a@example.com", "role": "admin"}
    c = TestClient(app)
    r = c.post("/api/pages", json={"slug": " SYNC Test Büyük ", "title": "T"})
    assert r.status_code == 200 and r.json()["slug"] == "sync-test-buyuk"
    pid = r.json()["id"]
    r = c.put(f"/api/pages/{pid}", json={"slug": "Sync Test 2"})
    assert r.status_code == 200
    assert c.get("/api/pages/sync-test-2").status_code == 200
    red = c.get("/api/seo/resolve-redirect", params={"path": "/sayfa/sync-test-buyuk"}).json()
    assert red["found"] is True and red["to"] == "/sayfa/sync-test-2" and red["status_code"] == 301
    # Geri dönüşte döngü oluşmaz: yeni yoldan eski yönlendirme silinir
    c.put(f"/api/pages/{pid}", json={"slug": "sync-test-buyuk"})
    assert c.get("/api/seo/resolve-redirect", params={"path": "/sayfa/sync-test-buyuk"}).json()["found"] is False
    red = c.get("/api/seo/resolve-redirect", params={"path": "/sayfa/sync-test-2"}).json()
    assert red["to"] == "/sayfa/sync-test-buyuk"
    assert c.put(f"/api/pages/{pid}", json={"slug": "!!!"}).status_code == 400


# ── #46 + #49: Merchant feed ─────────────────────────────────────────────────

def test_merchant_feed_single_escape_and_skips_imageless():
    import routes.products as rp
    prods = [
        {"id": "1", "slug": "s1", "name": "Bosch&#x27;un Set", "price": 10,
         "description": "<p>Bosch&#x27;un pense &amp; seti&nbsp;x</p>", "images": ["https://cdn.example/1.jpg"]},
        {"id": "2", "slug": "s2", "name": "Görselsiz", "price": 10, "description": "x", "images": []},
    ]
    xml = rp._build_merchant_xml(prods, "https://shop.example", "Shop")
    assert "&amp;#x27;" not in xml and "&amp;amp;" not in xml
    assert "Bosch&#x27;un pense &amp; seti x" in xml
    assert "<g:id>2</g:id>" not in xml


def test_imageless_product_absent_from_sitemap_and_feed(db):
    import routes.products as rp
    run(db.products.insert_one({"id": "a", "slug": "gorselli", "name": "A", "is_active": True, "price": 1,
                                "images": ["https://cdn.example/a.jpg"]}))
    run(db.products.insert_one({"id": "b", "slug": "gorselsiz", "name": "B", "is_active": True, "price": 1,
                                "images": []}))
    body = _sitemap()
    assert "/urun/gorselli<" in body and "gorselsiz" not in body
    _site, _shop, prods = run(rp._feed_site_shop_prods())
    assert [p["id"] for p in prods] == ["a"]
