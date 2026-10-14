"""Panel ↔ vitrin senkron regresyonları (e2e 2. tur bulguları #0, #1, #2, #3, #19, #20, #23, #25).

Gerçek route fonksiyonları localdb ile çalıştırılır (canlı DB/ağ yok)."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def tdb(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.settings as settings_mod
    import routes.coupons as coupons_mod
    import routes.catalog_extras as extras_mod
    db = AsyncIOMotorClient(path=str(tmp_path / "sync.db"))["test"]
    for m in (settings_mod, coupons_mod, extras_mod):
        monkeypatch.setattr(m, "db", db)
    try:
        import routes.deps as deps
        monkeypatch.setattr(deps, "db", db)
    except Exception:
        pass
    return db


# ── Ek iş / #1: havale/öğrenci yüzdesi boş-geçersiz → ayar sayfasıyla aynı (%5) ─────────

def test_effective_pct_setting_matches_settings_page():
    from routes.settings import effective_pct_setting as eff
    k = "bank_transfer_discount_pct"
    assert eff({}, k) == 5
    assert eff({k: ""}, k) == 5            # eskiden orders.py "" → %0 sayıyordu → 409
    assert eff({k: "  "}, k) == 5
    assert eff({k: None}, k) == 5
    assert eff({k: "abc"}, k) == 5         # float("abc") artık patlamıyor
    assert eff({k: 0}, k) == 0             # 0 = kapalı
    assert eff({k: "7,5"}, k) == 7.5
    assert eff({k: 150}, k) == 90
    assert eff({"edu_discount_pct": ""}, "edu_discount_pct") == 5


def test_orders_reads_bank_pct_via_shared_helper():
    src = (Path(__file__).parents[1] / "routes/orders.py").read_text()
    assert 'float(_pmset.get("bank_transfer_discount_pct", 5) or 0)' not in src
    assert '_eff_pct(_pmset, "bank_transfer_discount_pct")' in src


# ── #20: kısıtlı otomatik ücretsiz kargo genel eşiği belirlemez; türetilmiş alan geri yazılmaz ──

def test_restricted_auto_free_shipping_does_not_lower_threshold(tdb):
    from routes.settings import resolve_free_shipping_threshold

    async def go():
        base = {"is_active": True, "free_shipping": True, "auto_apply": True, "type": "fixed", "value": 0}
        await tdb.coupons.insert_one({**base, "id": "c1", "code": "FSCOD", "min_cart_total": 0,
                                      "payment_methods": ["cash_on_delivery"]})
        await tdb.coupons.insert_one({**base, "id": "c2", "code": "FSLIFT", "min_cart_total": 0,
                                      "categories": ["liftler"]})
        r1 = await resolve_free_shipping_threshold({})
        await tdb.coupons.insert_one({**base, "id": "c3", "code": "FS3000", "min_cart_total": 3000})
        r2 = await resolve_free_shipping_threshold({})
        return r1, r2

    assert run(go()) == (None, 3000)


def test_update_settings_does_not_persist_derived_fields(tdb, monkeypatch):
    import routes.settings as settings_mod

    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(settings_mod, "record_admin_audit", _noop)

    async def go():
        await tdb.settings.insert_one({"id": "main", "cod_default_applied": True})
        await tdb.coupons.insert_one({"id": "c3", "code": "FS3000", "is_active": True, "free_shipping": True,
                                      "auto_apply": True, "min_cart_total": 3000})
        # Admin ekranı GET yanıtını (türetilmiş eşik + kargo kuralları dahil) geri POST eder.
        await settings_mod.update_settings(
            {"site_name": "x", "free_shipping_threshold": 3000.0,
             "shipping_rules": [{"min_cart": 0, "shipping_cost": 49}]},
            request=None, current_user={"email": "a@b"})
        return await tdb.settings.find_one({"id": "main"}, {"_id": 0})

    doc = run(go())
    assert doc["site_name"] == "x"
    assert "shipping_rules" not in doc
    assert "free_shipping_threshold" not in doc


# ── #0: Kargo kuralları vitrin ve sipariş için aynı listeden ───────────────────────────

def test_active_shipping_rules_exposed_and_quoted(tdb):
    from routes.settings import active_shipping_rules
    from shipping_rules import shipping_quote

    async def go():
        await tdb.shipping_rules.insert_one({"id": "r1", "name": "SYNC-49", "min_cart": 0, "max_cart": None,
                                             "shipping_cost": 49, "free_shipping": False, "is_active": True})
        await tdb.shipping_rules.insert_one({"id": "r2", "name": "pasif", "min_cart": 0,
                                             "shipping_cost": 1, "is_active": False})
        return await active_shipping_rules()

    rules = run(go())
    assert rules == [{"min_cart": 0.0, "max_cart": None, "shipping_cost": 49.0, "free_shipping": False}]
    assert shipping_quote(296.76, [], None, 99, False, rules=rules)["cost"] == 49


# ── #2: Ödeme Tipi İndirimleri kayıtlı şemadan okunur, kasa anahtarlarıyla eşleşir ──────

def test_payment_type_discount_rules_read_saved_schema(tdb):
    import routes.catalog_extras as ex

    async def go():
        await ex.upsert_pay({"payment_method": "cash_on_delivery", "discount_type": "percent",
                             "discount_value": 10, "label": "SYNC-KapidaYuzde10", "is_active": True}, {})
        await ex.upsert_pay({"payment_method": "iyzico", "discount_type": "fixed",
                             "discount_value": 25, "min_cart": 500, "is_active": True}, {})
        await ex.upsert_pay({"payment_method": "havale", "discount_type": "percent",
                             "discount_value": 3, "is_active": True}, {})
        return (await ex.resolve_payment_discounts())["discounts"]

    d = run(go())
    assert d["cash_on_delivery"] == {"type": "percent", "percent": 10.0, "amount": 0.0,
                                     "min_cart": 0.0, "label": "SYNC-KapidaYuzde10"}
    assert d["credit_card"]["amount"] == 25.0 and d["credit_card"]["min_cart"] == 500.0
    assert "bank_transfer" not in d and "havale" not in d   # havale Ayarlar'daki yüzdeyle
    amt = ex.payment_type_discount_amount
    assert amt(d["cash_on_delivery"], 296.76) == 29.68
    assert amt(d["credit_card"], 296.76) == 0               # min sepet altında
    assert amt(d["credit_card"], 600) == 25.0


def test_create_order_applies_payment_type_discount_in_source():
    src = (Path(__file__).parents[1] / "routes/orders.py").read_text()
    assert "payment_type_discount_rules as _pt_rules" in src
    assert '_pm_disc = round(_bank_disc + _ptype_disc, 2)' in src


# ── #19/#20/#25: kampanya motoru ─────────────────────────────────────────────────────

def _evaluate(**kw):
    from routes.coupons import evaluate_cart_promotions
    return run(evaluate_cart_promotions(**kw))


def _items(price, qty=1, pid="p1", cat="tornavida"):
    return [{"product_id": pid, "category_id": cat, "price": price, "qty": qty}]


def test_free_shipping_coupon_marks_non_threshold_and_auto_campaign_marks_threshold(tdb):
    from shipping_rules import promo_free_shipping

    run(tdb.coupons.insert_one({"id": "auto", "code": "AUTOFS", "title": "Kargo 3000", "type": "fixed", "value": 0,
                                "is_active": True, "auto_apply": True, "free_shipping": True,
                                "min_cart_total": 3000, "combinable": True}))
    run(tdb.coupons.insert_one({"id": "code", "code": "SYNCFREE", "title": "Kargo bedava", "type": "fixed",
                                "value": 0, "is_active": True, "auto_apply": False, "free_shipping": True,
                                "min_cart_total": 0, "combinable": True}))
    r = _evaluate(cart_total=500, items=_items(500), entered_code="SYNCFREE", payment_method="bank_transfer")
    applied = {a["code"]: a for a in r["applied"]}
    assert applied["SYNCFREE"]["free_shipping"] and not applied["SYNCFREE"]["threshold_campaign"]
    assert promo_free_shipping(r["applied"])          # sipariş/kasa: kargo 0 (bulgu #19)

    r2 = _evaluate(cart_total=3500, items=_items(3500), payment_method="bank_transfer")
    a2 = {a["code"]: a for a in r2["applied"]}
    assert a2["AUTOFS"]["threshold_campaign"] is True  # eşikle uygulanır, ayrıca sayılmaz
    assert not promo_free_shipping(r2["applied"])


def test_payment_and_category_restricted_free_shipping(tdb):
    run(tdb.coupons.insert_one({"id": "cod", "code": "FSCOD", "type": "fixed", "value": 0, "is_active": True,
                                "auto_apply": True, "free_shipping": True, "min_cart_total": 0,
                                "payment_methods": ["cash_on_delivery"], "combinable": True}))
    run(tdb.coupons.insert_one({"id": "lift", "code": "FSLIFT", "type": "fixed", "value": 0, "is_active": True,
                                "auto_apply": True, "free_shipping": True, "min_cart_total": 0,
                                "categories": ["liftler"], "combinable": True}))
    bank = _evaluate(cart_total=500, items=_items(500), payment_method="bank_transfer")
    assert bank["free_shipping"] is False and bank["applied"] == []
    cod = _evaluate(cart_total=500, items=_items(500), payment_method="cash_on_delivery")
    assert [a["code"] for a in cod["applied"]] == ["FSCOD"]
    assert cod["applied"][0]["threshold_campaign"] is False
    lift = _evaluate(cart_total=500, items=_items(500, cat="liftler"), payment_method="bank_transfer")
    assert [a["code"] for a in lift["applied"]] == ["FSLIFT"]


def test_min_cart_total_uses_post_set_base(tdb):
    from routes.coupons import _evaluate_single
    c = {"id": "p10", "code": "P10", "type": "percent", "value": 10, "is_active": True, "min_cart_total": 2400}
    lines = _items(2487.88)
    assert run(_evaluate_single(c, 2487.88, lines))["valid"]
    # Set indirimi sonrası 1990,30 < 2400 → yüzde kampanyası da (ücretsiz kargo gibi) geçmez.
    assert not run(_evaluate_single(c, 2487.88, lines, None, "", "", 1990.30))["valid"]
    src = (Path(__file__).parents[1] / "routes/coupons.py").read_text()
    assert "round(cart_total - _set_total, 2))" in src


def test_free_shipping_gate_is_reported_not_silent(tdb):
    run(tdb.coupons.insert_one({"id": "pct", "code": "PCT10", "type": "percent", "value": 10, "is_active": True,
                                "auto_apply": True, "min_cart_total": 2400, "combinable": True}))
    run(tdb.coupons.insert_one({"id": "fs", "code": "FS2400", "title": "Kargo", "type": "fixed", "value": 0,
                                "is_active": True, "auto_apply": True, "free_shipping": True,
                                "min_cart_total": 2400, "combinable": True}))
    r = _evaluate(cart_total=2487.88, items=_items(2487.88), payment_method="bank_transfer")
    assert [a["code"] for a in r["applied"]] == ["PCT10"]
    assert r["free_shipping"] is False
    blocked = r["free_shipping_blocked"]
    assert blocked and blocked[0]["code"] == "FS2400" and blocked[0]["needed"] > 0
