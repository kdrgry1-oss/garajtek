import ast
from pathlib import Path
import pytest
from shipping_rules import shipping_quote


@pytest.mark.parametrize("net,free", [(3999.99, False), (4000, True), (4000.01, True)])
def test_inclusive_boundary(net, free):
    assert shipping_quote(net, [], 4000, 99) == {"basis": net, "free": free, "cost": 0 if free else 99, "fee": 99}


def test_campaign_and_points_discounts_before_threshold():
    assert shipping_quote(6000, [600, 1080, 321], 4000, 99) == {
        "basis": 3999, "free": False, "cost": 99, "fee": 99}
    assert shipping_quote(6000, [600, 1080, 320], 4000, 99)["free"]


def test_free_shipping_coupon_applies_even_with_threshold():
    # Bulgu #19: 'Kargo bedava' kuponu, otomatik eşik kampanyası varken de kargoyu kaldırır.
    assert shipping_quote(649, [0], 3000, 100, True)["cost"] == 0
    assert shipping_quote(649, [0], 3000, 100, False)["cost"] == 100


def test_other_tenant_and_no_threshold():
    assert shipping_quote(100, [], 100, 15)["free"]
    assert not shipping_quote(5000, [], None, 15)["free"]
    assert shipping_quote(100, [], None, 15, True)["free"]


def test_shipping_rules_fee_and_free_rule():
    # Bulgu #0: Kargo Kuralları sunucuda da uygulanır; 'Kargo bedava' kuralı 0 TL.
    from shipping_rules import match_shipping_rule
    rules = [{"min_cart": 0, "shipping_cost": 49, "free_shipping": False},
             {"min_cart": 1000, "max_cart": 2000, "shipping_cost": 0, "free_shipping": True},
             {"min_cart": 0, "shipping_cost": 1, "is_active": False}]
    assert match_shipping_rule(rules, 296.76)["shipping_cost"] == 49
    q = shipping_quote(296.76, [], None, 99, False, rules=rules)
    assert (q["cost"], q["fee"], q["free"]) == (49, 49, False)
    assert shipping_quote(1500, [], None, 99, False, rules=rules) == {
        "basis": 1500, "free": True, "cost": 0.0, "fee": 99}
    assert shipping_quote(2500, [], None, 99, rules=rules)["cost"] == 49   # max_cart aşıldı
    assert shipping_quote(100, [], None, 99, rules=[])["cost"] == 99


def test_restricted_campaign_does_not_set_threshold():
    # Bulgu #20: ödeme yöntemi/kategori ile kısıtlı otomatik ücretsiz kargo genel eşiği belirlemez.
    from shipping_rules import threshold_from_campaigns, promo_free_shipping
    base = {"is_active": True, "free_shipping": True, "auto_apply": True}
    camps = [{**base, "min_cart_total": 0, "payment_methods": ["cash_on_delivery"]},
             {**base, "min_cart_total": 0, "categories": ["liftler"]},
             {**base, "min_cart_total": 0, "first_order_only": True},
             {**base, "min_cart_total": 3000, "payment_methods": []},
             {**base, "min_cart_total": 1000, "end_at": "2000-01-01"}]
    assert threshold_from_campaigns(camps) == 3000
    assert threshold_from_campaigns(camps[:3]) is None
    assert not promo_free_shipping([{"free_shipping": True, "threshold_campaign": True}])
    assert promo_free_shipping([{"free_shipping": True, "threshold_campaign": False}])


def test_payment_discount_not_in_shipping_basis_in_order_source():
    # Bulgu #23: havale/ödeme tipi indirimi ücretsiz kargo tabanına girmez (kasa ile aynı).
    source = (Path(__file__).parents[1] / "routes/orders.py").read_text()
    assert "shipping_quote(_subtotal, [_server_discount, _pm_disc]" not in source
    assert '_subtotal, [_server_discount, _pm_disc, order.get("points_used", 0)]' not in source
    assert "rules=_ship_rules" in source


def test_order_final_shipping_is_after_actual_points_before_gift_card_and_total_check():
    # Guard the real orchestration placement, not just the pure arithmetic.
    source = (Path(__file__).parents[1] / "routes/orders.py").read_text()
    ast.parse(source)
    start = source.index('order["points_used"] = _sp["points"]')
    final = source.index('order["shipping_eligibility_basis"] = _ship_quote["basis"]')
    gift = source.index('from .gift_cards import redeem_gift_card_for_order')
    check = source.index('if _client_total > 0 and abs(_client_total - _server_total)')
    assert start < final < gift < check


def test_expired_campaign_not_live():
    from datetime import datetime, timezone
    from shipping_rules import campaign_live
    now = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
    assert not campaign_live({"start_at": "2026-09-22T21:00:00+00:00", "end_at": "2026-09-25T20:59:59+00:00"}, now)
    assert not campaign_live({"start_at": "2026-09-27T00:00:00+00:00"}, now)
    assert campaign_live({"end_at": "2026-09-26"}, now)
    assert campaign_live({}, now)
