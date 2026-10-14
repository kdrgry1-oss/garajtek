"""Regresyon (panel ↔ vitrin 2. tur): pasif varyant, pasif kategori alt ağacı, kategori sıra 0,
kategori slug koruma/alias/301 + ürün kopya alanları, 'Menüde göster', indirimli fiyat
doğrulaması ve /sale, kategori sıralama ekranı görselsiz ürün, anasayfa blok önbelleği,
marka bandı ve panel efektif fiyat sıralaması."""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Req:
    def __init__(self, auth=""):
        self.headers = {"authorization": auth} if auth else {}
    client = None
    cookies = {}
    query_params = {}
    url = type("U", (), {"path": "/api/products"})()
    method = "GET"


_ADMIN = {"email": "a@b", "role": "admin"}


def run(c):
    return asyncio.run(c)


@pytest.fixture
def E(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.products as products
    import routes.categories as categories
    import routes.deps as deps
    tdb = AsyncIOMotorClient(path=str(tmp_path / "s2.db"))["test"]
    for m in (products, categories, deps):
        monkeypatch.setattr(m, "db", tdb)
    products.invalidate_members_only_cache()
    yield products, categories, tdb
    products.invalidate_members_only_cache()


def _ins(tdb, coll, docs):
    async def go():
        for d in docs:
            await tdb[coll].insert_one(dict(d))
    run(go())


# ---------------------------------------------------------------- #8 pasif kategori alt ağacı
def test_inactive_parent_hides_subtree_and_products(E):
    products, categories, tdb = E
    _ins(tdb, "categories", [
        {"id": "1", "name": "Kök", "slug": "kok", "parent_id": None, "is_active": False},
        {"id": "2", "name": "Alt", "slug": "alt", "parent_id": "1", "is_active": True},
        {"id": "3", "name": "Diğer", "slug": "diger", "parent_id": None, "is_active": True},
    ])
    _ins(tdb, "products", [
        {"id": "p1", "name": "Alttaki", "price": 10, "is_active": True, "images": ["a.jpg"],
         "category_id": "2", "category_ids": ["2", "1"], "category_name": "Alt", "category_slug": "alt"},
        {"id": "p2", "name": "Diğerdeki", "price": 10, "is_active": True, "images": ["a.jpg"],
         "category_id": "3", "category_ids": ["3", "2"], "category_name": "Diğer"},
    ])
    cats = run(categories.get_categories(_Req(), visible_only=True))
    assert [c["id"] for c in cats] == ["3"]          # aktif alt kategori kök gibi SIZMAZ
    allc = run(categories.get_categories(_Req()))
    assert {c["id"] for c in allc} == {"1", "2", "3"}  # panel hepsini görür

    async def listing(**kw):
        q, _ = await products._build_products_query(_Req(), **kw)
        return sorted([p["id"] async for p in tdb.products.find(q, {"_id": 0, "id": 1})])

    assert run(listing()) == ["p2"]                  # birincil kategorisi pasif → gizli
    assert run(listing(category="alt")) == []        # pasif alt ağaç sayfası boş
    assert run(listing(category="diger")) == ["p2"]
    assert run(listing(search="Alttaki")) == []


# ---------------------------------------------------------------- #9 sıra 0
def test_sort_order_zero_is_first(E):
    _, categories, tdb = E
    _ins(tdb, "categories", [
        {"id": "a", "name": "B", "slug": "b", "parent_id": None, "sort_order": 5},
        {"id": "b", "name": "A", "slug": "a", "parent_id": None, "sort_order": 0},
        {"id": "c", "name": "C", "slug": "c", "parent_id": None},
    ])
    cats = run(categories.get_categories(_Req(), visible_only=True))
    assert [c["id"] for c in cats] == ["b", "a", "c"]


# ---------------------------------------------------------------- #10 #11 #13 #18 #44 slug / ad
def test_create_normalizes_slug_and_keeps_menu_flag(E):
    _, categories, tdb = E
    r = run(categories.create_category({"name": "SYNC-İzmir Gİriş", "slug": "sync-i-zmir-gi-ris",
                                        "show_in_menu": False}, _ADMIN))
    c = run(tdb.categories.find_one({"id": r["id"]}, {"_id": 0}))
    assert c["slug"] == "sync-izmir-giris"              # eski panelin bozuk slug'ı düzeltilir
    r2 = run(categories.create_category({"name": "SYNC-İzmir Gİriş"}, _ADMIN))
    c2 = run(tdb.categories.find_one({"id": r2["id"]}, {"_id": 0}))
    assert c2["slug"] == "sync-izmir-giris-2" and c2["show_in_menu"] is True   # çakışma → ek
    assert c["show_in_menu"] is False
    r3 = run(categories.create_category({"name": "SYNC-İzmir Gİriş"}, _ADMIN))
    assert run(tdb.categories.find_one({"id": r3["id"]}, {"_id": 0}))["slug"] == "sync-izmir-giris-3"


def test_update_keeps_sent_slug_aliases_old_and_redirects(E):
    _, categories, tdb = E
    _ins(tdb, "categories", [{"id": "10", "name": "SYNC Kategori Bir", "slug": "sync-kategori-bir",
                              "parent_id": None, "is_active": True}])
    run(categories.update_category("10", {"name": "SYNC Kategori Bir", "slug": "sync-ozel-slug",
                                          "show_in_menu": False}, _ADMIN))
    c = run(tdb.categories.find_one({"id": "10"}, {"_id": 0}))
    assert c["slug"] == "sync-ozel-slug" and c["slug_aliases"] == ["sync-kategori-bir"]
    assert c["show_in_menu"] is False
    red = run(tdb.seo_redirects.find_one({"from_path": "/kategori/sync-kategori-bir"}, {"_id": 0}))
    assert red["to_path"] == "/kategori/sync-ozel-slug" and red["status_code"] == 301 and red["is_active"]
    assert run(tdb.seo_redirects.find_one({"from_path": "/sync-kategori-bir"}, {"_id": 0}))["to_path"] == "/sync-ozel-slug"
    # eski slug alias ile bulunur
    assert run(categories.get_category("sync-kategori-bir"))["id"] == "10"
    # Geri adlandırma döngü üretmez: yeni hedefin kendi yönlendirmesi kapanır
    run(categories.update_category("10", {"slug": "sync-kategori-bir"}, _ADMIN))
    back = run(tdb.seo_redirects.find_one({"from_path": "/sync-kategori-bir"}, {"_id": 0}))
    assert back["is_active"] is False


def test_update_slug_conflict_409(E):
    _, categories, tdb = E
    _ins(tdb, "categories", [{"id": "1", "name": "A", "slug": "a"}, {"id": "2", "name": "B", "slug": "b"}])
    with pytest.raises(HTTPException) as e:
        run(categories.update_category("2", {"name": "B", "slug": "a"}, _ADMIN))
    assert e.value.status_code == 409


def test_rename_syncs_product_copies(E):
    products, categories, tdb = E
    _ins(tdb, "categories", [
        {"id": "1", "name": "Kök", "slug": "kok", "parent_id": None},
        {"id": "2", "name": "SYNC-Alt Kat", "slug": "sync-alt-kat", "parent_id": "1"},
    ])
    _ins(tdb, "products", [
        {"id": "p1", "name": "Ürün", "price": 10, "is_active": True, "images": ["a.jpg"], "category_id": "2",
         "category_ids": ["2", "1"], "category_name": "SYNC-Alt Kat", "category_slug": "sync-alt-kat",
         "breadcrumb": "Kök>SYNC-Alt Kat"},
    ])
    # panel slug alanını addan (lib/slug) doldurur
    run(categories.update_category("2", {"name": "SYNC-Yenilenmis Kat", "slug": "sync-yenilenmis-kat"}, _ADMIN))
    p = run(tdb.products.find_one({"id": "p1"}, {"_id": 0}))
    assert p["category_name"] == "SYNC-Yenilenmis Kat" and p["category_slug"] == "sync-yenilenmis-kat"
    assert p["breadcrumb"] == "Kök>SYNC-Yenilenmis Kat"
    # üst kategori adı değişince alt kategorideki ürünün breadcrumb'ı da güncellenir
    run(categories.update_category("1", {"name": "Kök Yeni"}, _ADMIN))
    p = run(tdb.products.find_one({"id": "p1"}, {"_id": 0}))
    assert p["breadcrumb"] == "Kök Yeni>SYNC-Yenilenmis Kat" and p["category_name"] == "SYNC-Yenilenmis Kat"
    assert run(tdb.categories.find_one({"id": "1"}, {"_id": 0}))["slug"] == "kok-yeni"

    async def found(term):
        q, _ = await products._build_products_query(_Req(), search=term)
        return [x["id"] async for x in tdb.products.find(q, {"_id": 0, "id": 1})]
    assert run(found("SYNC-Yenilenmis")) == ["p1"]


# ---------------------------------------------------------------- #14 indirimli fiyat
def test_sale_price_must_be_lower(E):
    products, _, tdb = E
    _ins(tdb, "products", [{"id": "2000", "name": "B", "slug": "b-2000", "price": 1200.0, "stock": 1,
                            "variants": [], "urun_karti_id": "2000"}])
    with pytest.raises(HTTPException) as e:
        run(products.update_product("2000", {"sale_price": 1500}, _Req(), _ADMIN))
    assert e.value.status_code == 400
    with pytest.raises(HTTPException):
        run(products.create_product({"name": "Y", "price": 100, "sale_price": 100}, _Req(), _ADMIN))
    run(products.update_product("2000", {"price": 1200, "sale_price": 1000}, _Req(), _ADMIN))
    assert run(tdb.products.find_one({"id": "2000"}, {"_id": 0}))["sale_price"] == 1000
    run(products.update_product("2000", {"sale_price": None}, _Req(), _ADMIN))   # indirim kaldırma serbest


def test_sale_listing_ignores_invalid_sale_price(E):
    products, _, tdb = E
    _ins(tdb, "products", [
        {"id": "ok", "name": "OK", "price": 100, "sale_price": 80, "is_active": True, "images": ["a"]},
        {"id": "bad", "name": "BAD", "price": 100, "sale_price": 150, "is_active": True, "images": ["a"]},
    ])

    async def ids():
        q, _ = await products._build_products_query(_Req(), category="sale")
        return sorted([x["id"] async for x in tdb.products.find(q, {"_id": 0, "id": 1})])
    assert run(ids()) == ["ok"]


# ---------------------------------------------------------------- ek: panel fiyat sıralaması
def test_admin_price_sort_uses_effective_price(E, monkeypatch):
    products, _, tdb = E
    import routes.deps as deps
    monkeypatch.setattr(deps, "_decode_jwt_strict", lambda t: {"user_id": "u", "is_admin": True})
    _ins(tdb, "products", [
        {"id": "a", "name": "A", "price": 429, "is_active": True, "created_at": "1"},
        {"id": "b", "name": "B", "price": 500, "sale_price": 385, "is_active": True, "created_at": "2"},
        {"id": "c", "name": "C", "price": 400, "sale_price": 450, "is_active": True, "created_at": "3"},
    ])

    def ids(**kw):
        r = run(products.get_products(_Req("Bearer x"), page=1, limit=20, admin_view="1", sort="price",
                                      order="asc", **kw))
        return [p["id"] for p in r["products"]], r["products"]
    order, rows = ids()
    assert order == ["b", "c", "a"]                  # 385, 400 (geçersiz indirim → price), 429
    assert all("_eff_price" not in p for p in rows)
    assert ids(search="A")[0][0] in {"a", "b", "c"}  # arama dalı da hata vermez


# ---------------------------------------------------------------- #16 sıralama ekranı
def test_category_order_hides_imageless(E):
    products, _, tdb = E
    _ins(tdb, "products", [
        {"id": "g", "name": "Görselsiz", "is_active": True, "category_ids": ["5"], "stock": 9, "images": []},
        {"id": "v", "name": "Görselli", "is_active": True, "category_ids": ["5"], "stock": 1, "images": ["x.jpg"]},
    ])
    r = run(products.get_category_order("5", limit=600))
    assert [p["id"] for p in r["products"]] == ["v"]
    assert r["total_all"] == 1 and r["hidden_no_image"] == 1


# ---------------------------------------------------------------- #6 pasif varyant
def test_inactive_variant_not_sellable(E):
    products, _, tdb = E
    import product_sets as ps
    prod = {"id": "9371", "price": 2000, "is_active": True, "stock": 8,
            "variants": [{"id": "23", "size": "S1", "stock": 5, "is_active": False},
                         {"id": "24", "size": "S2", "stock": 3}]}
    assert ps.item_stock(prod, "23") == 0 and ps.item_stock(prod, "24") == 3
    _ins(tdb, "products", [prod])
    out = run(products.cart_pricing({"product_ids": ["9371"]}))["items"]["9371"]["variants"]
    assert out["23"]["stock"] == 0 and out["23"]["is_active"] is False
    assert out["24"]["stock"] == 3 and out["24"]["is_active"] is True


# ---------------------------------------------------------------- #17 anasayfa blok önbelleği
def test_storefront_cache_cleared_after_product_write(E):
    products, _, tdb = E
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from routes.deps import require_admin
    from pageblocks import products as pbp
    pbp._CACHE["x"] = (0, [])
    app = FastAPI()
    app.include_router(products.router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: _ADMIN
    _ins(tdb, "products", [{"id": "t1", "name": "T", "price": 10, "is_active": True}])
    c = TestClient(app)
    c.post("/api/products/cart-pricing", json={"product_ids": ["t1"]})
    assert "x" in pbp._CACHE                          # salt-okur POST önbelleği boşaltmaz
    r = c.post("/api/products/t1/toggle-active")
    assert r.status_code == 200 and r.json()["is_active"] is False
    assert pbp._CACHE == {}


def test_cached_block_drops_passive_product(E):
    _, _, tdb = E
    from pageblocks import products as pbp
    _ins(tdb, "products", [{"id": "on", "is_active": True}, {"id": "off", "is_active": False}])
    rows = [{"id": "on"}, {"id": "off"}]
    assert run(pbp._drop_inactive(tdb, rows)) == [{"id": "on"}]


# ---------------------------------------------------------------- #15 marka bandı
def test_brand_band_active_sorted_and_keeps_product_brands(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.page_design as pd
    tdb = AsyncIOMotorClient(path=str(tmp_path / "b.db"))["test"]
    monkeypatch.setattr(pd, "db", tdb)
    _ins(tdb, "brands", [
        {"id": "1", "name": "Pasif Marka", "image": "p.png", "is_active": False, "sort_order": 0},
        {"id": "2", "name": "İkinci", "image": "b.png", "is_active": True, "sort_order": 2},
        {"id": "3", "name": "Birinci", "image": "a.png", "is_active": True, "sort_order": 1},
    ])
    _ins(tdb, "products", [
        {"id": "x", "brand": "SwissTron", "is_active": True, "created_at": "2"},
        {"id": "y", "brand": "Pasif Marka", "is_active": True, "created_at": "1"},
    ])
    items = run(pd.catalog_brands())["items"]
    names = [i["name"] for i in items]
    assert names == ["Birinci", "İkinci", "SwissTron"]
    assert items[1]["url"] == "/arama?q=%C4%B0kinci"
