"""Ürün Setleri + kapıda ödeme kuralları — gerçek localdb üzerinde.

Kapsam: set fiyatlama, bileşen stok/en alt kategori, set indiriminin kampanya motoruna
(evaluate_cart_promotions — sepet, kasa ve sipariş aynı fonksiyonu çağırır) entegrasyonu,
eksik set / değiştirilen bileşen kuralları, sipariş kalemi indirim dağıtımı ve kapıda ödeme
ürün/kategori kapatma kuralları."""
import ast
import asyncio
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import product_sets as ps  # noqa: E402
import cod_rules  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    d = AsyncIOMotorClient(path=str(tmp_path / "sets.db"))["test"]
    cats = [
        {"id": "10", "slug": "lokma-takimlari", "name": "Lokma Takımları", "parent_id": None},
        {"id": "11", "slug": "lokma-setleri", "name": "Lokma Setleri", "parent_id": "10"},
        {"id": "20", "slug": "el-aletleri", "name": "El Aletleri", "parent_id": None},
        {"id": "21", "slug": "tork-anahtarlari", "name": "Tork Anahtarları", "parent_id": "20"},
        {"id": "30", "slug": "urun-setleri", "name": "Ürün Setleri", "parent_id": None},
        {"id": "40", "slug": "indirimli-urunler", "name": "İndirimli Ürünler", "parent_id": None},
    ]
    prods = [
        {"id": "A", "name": "94 Parça Lokma", "price": 1000, "stock": 0, "category_id": "11",
         "category_ids": ["11", "10", "40"]},
        {"id": "B", "name": "Tork Anahtarı", "price": 500, "sale_price": 400, "stock": 5,
         "category_id": "21", "category_ids": ["21", "20"]},
        {"id": "C", "name": "108 Parça Lokma", "price": 900, "stock": 7, "category_id": "11",
         "category_ids": ["11", "10"]},
        {"id": "D", "name": "LED Lamba", "price": 100, "stock": 3, "category_id": "20", "category_ids": ["20"],
         "variants": [{"id": "D1", "size": "Sarı", "stock": 0}, {"id": "D2", "size": "Siyah", "stock": 3,
                                                                "price_diff": 20}]},
        {"id": "S", "name": "Atölye Seti", "product_type": "set", "price": 1, "stock": 0, "category_id": "30",
         "category_ids": ["30"], "set_discount_pct": 10,
         "set_items": [{"product_id": "A", "quantity": 1}, {"product_id": "B", "quantity": 1},
                       {"product_id": "D", "quantity": 2, "variant_id": "D2"}]},
    ]
    for c in cats:
        run(d.categories.insert_one(c))
    for p in prods:
        run(d.products.insert_one(p))
    return d


def test_components_pricing_and_leaf_category(db):
    s = run(db.products.find_one({"id": "S"}, {"_id": 0}))
    res = run(ps.refresh_set(db, s))
    comps = {c["product_id"]: c for c in res["components"]}
    assert comps["A"]["in_stock"] is False and comps["A"]["leaf_category"]["slug"] == "lokma-setleri"
    assert comps["B"]["unit_price"] == 400 and comps["B"]["list_unit_price"] == 500
    assert comps["D"]["variant_id"] == "D2" and comps["D"]["unit_price"] == 120
    pr = res["pricing"]
    assert pr["components_total"] == 1000 + 400 + 2 * 120
    assert pr["set_price"] == round(pr["components_total"] * 0.9, 2)
    assert pr["missing_count"] == 1
    saved = run(db.products.find_one({"id": "S"}))
    assert saved["price"] == pr["components_total"] and saved["sale_price"] == pr["set_price"]
    assert saved["stock"] == 1  # D: 3 // 2 = 1 tam set (A tükendi → değiştir akışı)


def test_unit_price_matches_order_engine():
    src = (ROOT / "routes" / "orders.py").read_text()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "_eff_unit_price")
    scope = {}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "orders", "exec"), scope)
    cases = [({"price": 100}, None), ({"price": 100, "sale_price": 80}, None), ({"price": 100, "sale_price": 120}, None),
             ({"price": 100, "sale_price": "", "variants": [{"id": "v", "price_adjustment": 15}]}, "v"),
             ({"price": 100, "variants": [{"id": "v", "price_diff": -5}]}, "v")]
    for prod, vid in cases:
        assert ps.unit_price(prod, vid) == scope["_eff_unit_price"](prod, vid)


def _line(pid, price, qty=1, set_id="S", slot=None):
    return {"product_id": pid, "price": price, "qty": qty, "set_id": set_id, "set_slot": slot or pid}


def test_set_discount_only_when_complete(db):
    # A tükendi ve sepette değil → set eksik → indirim yok
    assert run(ps.compute_set_discounts(db, [_line("B", 400), _line("D", 120, 2)])) == []
    # A yerine aynı EN ALT kategoriden C seçildi → set tamam → %10 yalnız set kalemlerinde
    items = [_line("C", 900, slot="A"), _line("B", 400), _line("D", 120, 2), {"product_id": "X", "price": 50, "qty": 1}]
    e = run(ps.compute_set_discounts(db, items))
    assert len(e) == 1 and e[0]["amount"] == round((900 + 400 + 240) * 0.10, 2)
    assert e[0]["units"] == {0: 1, 1: 1, 2: 2}
    # Başka kategoriden ürün yuvayı dolduramaz
    bad = [_line("B", 400, slot="A"), _line("B", 400), _line("D", 120, 2)]
    assert run(ps.compute_set_discounts(db, bad)) == []
    # Bileşen adedi eksik (D: 1 < 2) → indirim yok; 2 tam set → iki katı
    assert run(ps.compute_set_discounts(db, [_line("C", 900, slot="A"), _line("B", 400), _line("D", 120, 1)])) == []
    two = run(ps.compute_set_discounts(db, [_line("C", 900, 2, slot="A"), _line("B", 400, 3), _line("D", 120, 4)]))
    assert two[0]["sets"] == 2 and two[0]["amount"] == round((900 * 2 + 400 * 2 + 120 * 4) * 0.10, 2)


def _evaluate(db, items, coupons=()):
    """Gerçek evaluate_cart_promotions (routes/coupons.py) — set indirimi + kampanyalar."""
    source = ROOT / "routes" / "coupons.py"
    names = {"evaluate_cart_promotions", "_compute_discount", "fold_code", "_item_category_set",
             "_item_in_scope", "_allocate_discount"}
    nodes = [n for n in ast.parse(source.read_text()).body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]

    class Cursor:
        def __aiter__(self):
            async def rows():
                for c in coupons:
                    yield c
            return rows()

    class DB:
        products = db.products
        categories = db.categories
        settings = type("S", (), {"find_one": AsyncMock(return_value={})})()
        coupons = type("C", (), {"find": lambda *a: Cursor()})()

    scope = {"db": DB(), "re": re, "_promo_cap_pct": AsyncMock(return_value=70),
             "_log_coupon_attempt": AsyncMock(), "logger": __import__("logging").getLogger("t")}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), "exec"), scope)

    async def enrich(v):
        return v

    async def validate(c, total, lines, *a):
        return {"valid": True, "discount": scope["_compute_discount"](c, total, lines), "free_shipping": False}

    scope.update(_enrich_items_category_ids=enrich, _evaluate_single=validate,
                 resolve_coupon_code=AsyncMock(return_value=(None, "")))
    total = round(sum(i["price"] * i["qty"] for i in items), 2)
    return run(scope["evaluate_cart_promotions"](total, items))


def test_engine_applies_set_discount_before_campaigns(db):
    items = [_line("C", 900, slot="A"), _line("B", 400), _line("D", 120, 2)]
    r = _evaluate(db, items)
    assert r["set_discount"] == 154.0 and r["total_discount"] == 154.0
    assert r["applied"][0]["coupon_id"] == "set:S" and r["applied"][0]["set_id"] == "S"
    # %10 sepet kampanyası set-indirimli KALAN tutar üzerinden hesaplanır
    camp = [{"id": "K", "code": "K", "type": "percent", "value": 10, "auto_apply": True, "combinable": True}]
    r2 = _evaluate(db, items, camp)
    k = next(a for a in r2["applied"] if a["coupon_id"] == "K")
    assert k["discount"] == round((1540 - 154) * 0.10, 2)
    # set dışı sepette hiçbir şey değişmez
    plain = _evaluate(db, [{"product_id": "B", "price": 400, "qty": 1}])
    assert plain["set_discount"] == 0 and plain["applied"] == []


def test_order_item_discounts_allocate_set_discount_to_set_lines(db):
    src = (ROOT / "routes" / "orders.py").read_text()
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_order_item_discounts")
    scope = {"db": db, "_round2": lambda v: round(float(v or 0) + 1e-9, 2)}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "orders", "exec"), scope)
    import types
    fake = types.ModuleType("routes.coupons")
    fake._item_in_scope = lambda *a, **k: True
    prev = {k: sys.modules.get(k) for k in ("routes", "routes.coupons")}
    if prev["routes"] is None:
        pkg = types.ModuleType("routes")
        pkg.__path__ = [str(ROOT / "routes")]
        sys.modules["routes"] = pkg
    sys.modules["routes.coupons"] = fake
    try:
        scope["__package__"] = "routes"
        order = {"items": [{"product_id": "C", "price": 900, "quantity": 1, "set_id": "S"},
                           {"product_id": "B", "price": 400, "quantity": 1, "set_id": "S"},
                           {"product_id": "X", "price": 100, "quantity": 1}],
                 "discount": 130, "subtotal": 1400,
                 "applied_promotions": [{"coupon_id": "set:S", "discount": 130}]}
        out = run(scope["_order_item_discounts"](order))
    finally:
        for k, v in prev.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    assert out[2] == 0 and round(out[0] + out[1], 2) == 130 and out[0] == 90


def test_cod_rules(db):
    run(db.settings.insert_one({"id": "main", "payment_methods": {"cash_on_delivery": True}}))
    run(db.categories.update_one({"id": "21"}, {"$set": {"cod_disabled": True}}))
    cfg = run(cod_rules.cod_config(db))
    assert cfg["enabled"] is True and cfg["excluded_category_ids"] == ["21"] and cfg["fee"] == 10
    ex = cfg["excluded_category_ids"]
    assert cod_rules.product_cod_blocked({"category_ids": ["21", "20"]}, ex)       # kategori
    assert cod_rules.product_cod_blocked({"cod_disabled": True}, [])               # ürün
    assert cod_rules.product_cod_blocked({"catalog_fields": {"URUNKAPIDAODEMEYASAKLI": "1"}}, [])
    assert not cod_rules.product_cod_blocked({"category_ids": ["11"]}, ex)
    run(db.settings.update_one({"id": "main"}, {"$set": {"payment_methods": {"cash_on_delivery": False}}}))
    assert run(cod_rules.cod_config(db))["enabled"] is False


def test_clean_set_items():
    rows = ps.clean_set_items([{"product_id": "A", "quantity": "3"}, {"product_id": "A"}, {"product_id": ""},
                               {"product_id": "B", "quantity": 0, "variant_id": 7, "note": "x" * 300}])
    assert rows == [{"product_id": "A", "quantity": 3},
                    {"product_id": "B", "quantity": 1, "variant_id": "7", "note": "x" * 120}]


# ── Sözleşme 7.2: 100 bileşenli set tek işlemde ───────────────────────────────

def test_hundred_item_set_single_pass(db):
    import time
    for i in range(100):
        run(db.products.insert_one({"id": f"H{i}", "name": f"Parça {i}", "price": 10 + i, "stock": 50,
                                    "category_id": "21", "category_ids": ["21", "20"]}))
    items = [{"product_id": f"H{i}", "quantity": 1 + (i % 3)} for i in range(100)]
    assert len(ps.clean_set_items(items)) == 100
    run(db.products.insert_one({"id": "BIG", "name": "Büyük Set", "product_type": "set", "price": 1,
                                "set_discount_pct": 5, "set_items": items}))
    t0 = time.perf_counter()
    res = run(ps.refresh_set(db, run(db.products.find_one({"id": "BIG"}, {"_id": 0}))))
    assert len(res["components"]) == 100 and res["pricing"]["missing_count"] == 0
    lines = [{"product_id": f"H{i}", "price": 10 + i, "qty": 1 + (i % 3), "set_id": "BIG", "set_slot": f"H{i}"}
             for i in range(100)]
    e = run(ps.compute_set_discounts(db, lines))
    assert len(e) == 1 and len(e[0]["units"]) == 100
    total = sum((10 + i) * (1 + (i % 3)) for i in range(100))
    assert e[0]["amount"] == round(total * 0.05, 2)
    assert time.perf_counter() - t0 < 5  # tek geçiş, sorgu sayısı bileşen sayısından bağımsız


# ── Vitrin uçları: stok kontrolü, alternatifler, hızlı sipariş ─────────────────

@pytest.fixture
def client(db, monkeypatch):
    import types
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    pkg = types.ModuleType("routes")
    pkg.__path__ = [str(ROOT / "routes")]
    deps = types.ModuleType("routes.deps")
    deps.db = db
    deps.logger = __import__("logging").getLogger("sets-test")

    async def _admin():
        return {"id": "a", "is_admin": True}
    deps.require_admin = _admin
    deps.require_permission = lambda key: _admin
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.deps", deps)
    sys.modules.pop("routes.product_sets", None)
    import importlib
    mod = importlib.import_module("routes.product_sets")
    app = FastAPI()
    app.include_router(mod.router, prefix="/api")
    run(db.products.insert_one({"id": "E", "name": "Lokma 72", "price": 700, "stock": 4, "stock_code": "LK-72",
                                "category_id": "11", "category_ids": ["11", "10"], "sold_count": 3,
                                "variants": []}))
    run(db.products.insert_one({"id": "F", "name": "Anahtar", "price": 50, "stock": 9, "category_id": "20",
                                "category_ids": ["20"], "variants": [{"id": "F1", "size": "10 mm", "stock": 0,
                                                                      "barcode": "869000000001"},
                                                                     {"id": "F2", "size": "13 mm", "stock": 9,
                                                                      "barcode": "869000000002"}]}))
    yield TestClient(app)
    sys.modules.pop("routes.product_sets", None)


def test_cart_stock_marks_out_of_stock_lines(client):
    r = client.post("/api/storefront/cart-stock", json={"lines": [
        {"product_id": "A", "quantity": 1}, {"product_id": "C", "quantity": 9},
        {"product_id": "F", "variant_id": "F1", "quantity": 1}, {"product_id": "YOK", "quantity": 1}]}).json()["items"]
    assert r["A|"]["available"] is False and r["A|"]["leaf_category"]["slug"] == "lokma-setleri"
    assert r["C|"]["available"] is True and r["C|"]["enough"] is False and r["C|"]["stock"] == 7
    assert r["F|F1"]["available"] is False
    assert r["YOK|"]["available"] is False and r["YOK|"]["active"] is False


def test_alternatives_from_same_leaf_category(client):
    d = client.get("/api/storefront/alternatives", params={"product_id": "A"}).json()
    assert d["category"]["slug"] == "lokma-setleri"
    ids = [p["id"] for p in d["items"]]
    assert set(ids) == {"C", "E"} and "A" not in ids  # stokta, aynı alt kategori, set değil
    assert all(p["stock"] > 0 for p in d["items"])


def test_quick_order_resolves_codes_in_one_call(client):
    d = client.post("/api/storefront/quick-order", json={"lines": [
        {"code": "LK-72", "qty": 2}, {"code": "869000000002", "qty": 3}, {"code": "869000000001", "qty": 1},
        {"code": "YOKKOD", "qty": 1}]}).json()
    by = {f["code"]: f for f in d["found"]}
    assert by["LK-72"]["product"]["id"] == "E" and by["LK-72"]["quantity"] == 2
    assert by["869000000002"]["variant"]["id"] == "F2" and by["869000000002"]["stock"] == 9
    assert by["869000000001"]["stock"] == 0
    assert d["missing"] == ["YOKKOD"]


def test_public_set_endpoint_and_cod_check(client, db):
    d = client.get("/api/product-sets/S").json()
    assert d["set"]["name"] == "Atölye Seti" and len(d["components"]) == 3
    run(db.settings.insert_one({"id": "main", "payment_methods": {"cash_on_delivery": True}}))
    run(db.products.update_one({"id": "B"}, {"$set": {"cod_disabled": True}}))
    c = client.post("/api/storefront/cod-check", json={"product_ids": ["B", "C"], "subtotal": 500}).json()
    assert c["available"] is False and c["blocked"] == ["Tork Anahtarı"]
    ok = client.post("/api/storefront/cod-check", json={"product_ids": ["C"], "subtotal": 500}).json()
    assert ok["available"] is True
