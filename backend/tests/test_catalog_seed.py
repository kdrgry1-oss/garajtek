"""Fatura tohumu (Al Nalburiye 25-09-2026): fiyat formülü, idempotentlik, yönetici düzenlemesinin
korunması, varyant fiyatı (sepet/kasa) ve üretici görsellerinin indirilmesi (sahte HTTP)."""
import asyncio
import io
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import catalog_seed as cs  # noqa: E402
from seed_categories import load_tree, seed_categories  # noqa: E402

EXPECTED = {
    "GT-IZL-IKAT12": (5312.34, 1475.65, 3, "anahtar-takimlari"),
    "GT-BSH-PNS3": (3902.34, 1083.98, 6, "penseler"),
    "GT-IZL-KAT12": (6494.40, 1804.00, 6, "anahtar-takimlari"),
}
YIA = {"6x7 mm": 546.48, "8x9 mm": 552.42, "10x11 mm": 611.82, "12x13 mm": 693.00, "14x15 mm": 730.62,
       "16x17 mm": 827.64, "18x19 mm": 1069.20, "20x22 mm": 1075.14}


def _orders_fn(name):
    """routes/orders.py'deki saf fonksiyonu modül içe aktarmadan yükler (diğer testlerin
    sys.modules['routes'] taklitlerinden etkilenmesin)."""
    import ast
    tree = ast.parse((ROOT / "routes" / "orders.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    scope = {}
    exec(compile(ast.Module(body=[node], type_ignores=[]), "orders.py", "exec"), scope)
    return scope[name]


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    return AsyncIOMotorClient(path=str(tmp_path / "seed.db"))["test"]


def _creator(db):
    """Panelin create_product'ının özü: id, varyant id'leri, kategori, ana stok = Σ varyant."""
    n = {"i": 0}

    async def create(data):
        n["i"] += 1
        pid = f"p{n['i']}"
        variants = [{**v, "id": f"{pid}-v{i}"} for i, v in enumerate(data.get("variants") or [])]
        doc = {**data, "id": pid, "slug": f"s-{pid}", "variants": variants,
               "category_ids": data.get("categories") or []}
        if variants:
            doc["stock"] = sum(v["stock"] for v in variants)
        await db.products.insert_one(doc)
        return {"id": pid}
    return create


def test_seed_json_prices_match_formula():
    seed = cs.load_seed()
    slugs = {n["slug"] for n in load_tree()}
    codes = set()
    for p in seed["products"]:
        assert p["category_slug"] in slugs
        assert p["brand"] in ("İzeltaş", "Bosch")
        for v in p.get("variants") or [p]:
            assert cs.sale_price(v["line_total"], v["qty"]) == v["expected_price"], v
            # 3 × net × 1,20 (kuruş yuvarlaması dahilinde)
            assert abs(v["expected_price"] - 3.6 * v["line_total"] / v["qty"]) < 0.006
        for c in cs._codes(p):
            assert c not in codes
            codes.add(c)
        assert p["intro"] and p["bullets"] and p["meta_title"] and p["source_page_urls"]
        assert len(p["meta_title"]) <= 70


def test_apply_creates_products_with_prices_variants_and_is_idempotent(db):
    _run(seed_categories(db, load_tree()))
    res = _run(cs.apply_seed(db, _creator(db), category_timeout=0))
    assert res["marker"] == "written" and len(res["created"]) == 4
    cats = {c["id"]: c["slug"] for c in _run(db.categories.find({}, {"_id": 0}).to_list(5000))}
    for code, (price, cost, qty, slug) in EXPECTED.items():
        p = _run(db.products.find_one({"stock_code": code}, {"_id": 0}))
        assert p["price"] == price and p["purchase_price"] == cost and p["stock"] == qty
        assert cats[p["category_id"]] == slug
        assert p["is_active"] is True and not p.get("demo") and not p.get("noindex")
        assert p["vat_rate"] == 20 and p["vat_included"] is True
        assert p["catalog_seed"] == cs.SEED_ID and p["images"] == []
        assert p["specs"]["piece_count"] in (3, 12) and p["meta_description"]
    bosch = _run(db.products.find_one({"stock_code": "GT-BSH-PNS3"}, {"_id": 0}))
    assert bosch["barcode"] == "4059952655857" and bosch["specs"]["mpn"] == "1600A02C0S"

    y = _run(db.products.find_one({"stock_code": "GT-IZL-YIA"}, {"_id": 0}))
    assert cats[y["category_id"]] == "yildiz-iki-agiz-anahtarlar"
    assert y["price"] == 546.48 and y["stock"] == 48 and y["variant_labels"] == {"size": "Ölçü"}
    _eff_unit_price = _orders_fn("_eff_unit_price")  # sunucu-otoriter sepet/kasa birim fiyatı
    for v in y["variants"]:
        assert v["stock"] == 6
        assert _eff_unit_price(y, v["id"]) == YIA[v["size"]], v
    assert {v["sku"] for v in y["variants"]} == {f"GT-IZL-YIA-{s}" for s in
                                                 ("0607", "0809", "1011", "1213", "1415", "1617", "1819", "2022")}

    # ikinci çalıştırma: işaret var → hiçbir şey yapılmaz
    again = _run(cs.apply_seed(db, _creator(db), category_timeout=0))
    assert again["marker"] == "already"
    assert _run(db.products.count_documents({"catalog_seed": cs.SEED_ID})) == 4


def test_admin_edits_never_overwritten_and_existing_codes_skipped(db):
    _run(seed_categories(db, load_tree()))
    # yönetici ürünü panelden zaten açmış (aynı stok kodu, farklı fiyat) ve varyant SKU'su başka üründe
    _run(db.products.insert_one({"id": "admin1", "name": "Elle açılan", "stock_code": "GT-BSH-PNS3",
                                 "price": 3500.0}))
    _run(db.products.insert_one({"id": "admin2", "name": "Tekil yıldız", "stock_code": "X",
                                 "variants": [{"sku": "GT-IZL-YIA-1011"}]}))
    res = _run(cs.apply_seed(db, _creator(db), category_timeout=0))
    assert sorted(res["skipped"]) == ["GT-BSH-PNS3", "GT-IZL-YIA"]
    assert _run(db.products.find_one({"id": "admin1"}))["price"] == 3500.0
    # işaret silinse bile (yeniden çalıştırma) mevcut ürünler ezilmez/çoğaltılmaz
    p = _run(db.products.find_one({"stock_code": "GT-IZL-KAT12"}))
    _run(db.products.update_one({"id": p["id"]}, {"$set": {"price": 9999.0, "name": "Yönetici adı"}}))
    _run(db.settings.delete_one({"id": cs.MARKER}))
    res2 = _run(cs.apply_seed(db, _creator(db), category_timeout=0))
    assert res2["created"] == [] and "GT-IZL-KAT12" in res2["skipped"]
    p2 = _run(db.products.find_one({"id": p["id"]}))
    assert p2["price"] == 9999.0 and p2["name"] == "Yönetici adı"


def test_missing_categories_do_not_write_marker(db):
    res = _run(cs.apply_seed(db, _creator(db), category_timeout=0))
    assert res["marker"] is None and res["created"] == [] and res["missing_categories"]
    assert not _run(db.settings.find_one({"id": cs.MARKER}))


# ── görseller (sahte HTTP) ───────────────────────────────────────────────────

def _img(color=(200, 30, 30)):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (400, 300), color).save(b, "JPEG")
    return b.getvalue()


def _fetcher(routes):
    from url_import import fetcher as F

    def handler(req):
        r = routes.get(str(req.url))
        if r is None:
            return httpx.Response(404, text="yok")
        if callable(r):
            return r(req)
        status, headers, body = r
        return httpx.Response(status, headers=headers, content=body)

    async def resolve(host, port):
        return ["93.184.216.34"]
    return F.Fetcher(min_interval=0, transport=httpx.MockTransport(handler), resolver=resolve)


class Store:
    def __init__(self, db):
        self.db, self.n = db, 0

    async def store(self, data, ctype, ext, name, extra=None):
        self.n += 1
        assert ctype == "image/webp" and data[:4] == b"RIFF"
        await self.db.files.insert_one({"id": f"f{self.n}", "storage_path": name, **(extra or {})})
        return {"success": True, "path": name, "url": f"/api/upload/files/{name}"}


def test_fetch_images_official_page_then_fallback_and_never_overwrite(db):
    _run(seed_categories(db, load_tree()))
    _run(cs.apply_seed(db, _creator(db), category_timeout=0))
    H = {"content-type": "text/html; charset=utf-8"}
    J = {"content-type": "image/jpeg"}
    seed = {p["stock_code"]: p for p in cs.load_seed()["products"]}
    ikat = seed["GT-IZL-IKAT12"]["source_page_urls"]
    bosch = seed["GT-BSH-PNS3"]["source_page_urls"]
    routes = {
        # üretici sayfası: og:image + galeri
        ikat[0]: (200, H, b'<html><head><meta property="og:image" content="https://izeltas.com.tr/img/0100-set.jpg">'
                          b'<meta property="og:title" content="0100"></head><body><h1>0100</h1></body></html>'),
        "https://izeltas.com.tr/img/0100-set.jpg": (200, J, _img()),
        # Bosch: ilk sayfanın görseli sıcak-bağlantı korumalı (hep 403) → ikinci sayfaya geçilir;
        # ikinci sayfanın CDN'i yalnız doğru Referer ile görsel verir
        bosch[0]: (200, H, b'<html><head><meta property="og:image" content="https://cdn.koctas.example/b.jpg">'
                           b'</head><body></body></html>'),
        "https://cdn.koctas.example/b.jpg": (403, {"content-type": "text/html"}, b"forbidden"),
        bosch[1]: (200, H, b'<html><head><script type="application/ld+json">{"@type":"Product","name":"Pense",'
                           b'"image":["https://cdn.example.com/pense-1.jpg","https://cdn.example.com/pense-2.jpg"]}'
                           b'</script></head><body></body></html>'),
        "https://cdn.example.com/pense-1.jpg": lambda req: (
            httpx.Response(200, headers=J, content=_img((10, 80, 10))) if req.headers.get("referer") == bosch[1]
            else httpx.Response(403)),
        "https://cdn.example.com/pense-2.jpg": (200, J, _img((10, 10, 80))),
    }
    # yönetici kombine takıma kendi görselini yüklemiş → dokunulmamalı
    p = _run(db.products.find_one({"stock_code": "GT-IZL-KAT12"}))
    _run(db.products.update_one({"id": p["id"]}, {"$set": {"images": ["/api/upload/files/admin.webp"]}}))

    store = Store(db)

    async def go():
        f = _fetcher(routes)
        try:
            return await cs.fetch_missing_images(db, store_image=store.store, fetcher=f)
        finally:
            await f.close()
    got = _run(go())
    assert got["izl-iki-agiz-12"] == 1 and got["bosch-pense-3"] == 2
    assert got["izl-yildiz-iki-agiz"] == 0 and "izl-kombine-12" not in got
    a = _run(db.products.find_one({"stock_code": "GT-IZL-IKAT12"}))
    assert a["images"] == ["/api/upload/files/izl-iki-agiz-12-1.webp"] and a["images_fetched_at"]
    assert a["images_source_page"] == ikat[0]
    b = _run(db.products.find_one({"stock_code": "GT-BSH-PNS3"}))
    assert len(b["images"]) == 2 and b["images_source_page"] == bosch[1]
    k = _run(db.products.find_one({"stock_code": "GT-IZL-KAT12"}))
    assert k["images"] == ["/api/upload/files/admin.webp"] and not k.get("images_fetched_at")
    y = _run(db.products.find_one({"stock_code": "GT-IZL-YIA"}))
    assert y["images"] == [] and y["images_fetch_attempts"] == 1 and y["images_fetch_error"]
    assert b["images_fetch_error"] == "" and b["images_fetch_attempts"] == 1
    files = _run(db.files.find({}, {"_id": 0}).to_list(50))
    assert all(f["catalog_seed"] == cs.SEED_ID and not f.get("demo") for f in files)

    # ikinci tur: yalnız hâlâ görselsiz olan (yıldız) yeniden denenir; deneme sınırı aşılınca durur
    pend = _run(cs.pending_image_products(db))
    assert [d["stock_code"] for d in pend] == ["GT-IZL-YIA"]
    _run(db.products.update_one({"id": y["id"]}, {"$set": {"images_fetch_attempts": cs.MAX_IMAGE_ATTEMPTS}}))
    assert _run(cs.pending_image_products(db)) == []
