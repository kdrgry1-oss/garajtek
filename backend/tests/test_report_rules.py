import importlib.util
import asyncio
from pathlib import Path
import sys
import types


# Load the pure aggregation helpers without importing routes/__init__.py (which
# intentionally registers the complete FastAPI application dependency graph).
routes_pkg = types.ModuleType("routes")
routes_pkg.__path__ = []
deps_stub = types.ModuleType("routes.deps")
deps_stub.db = object()
sys.modules.setdefault("routes", routes_pkg)
sys.modules.setdefault("routes.deps", deps_stub)
spec = importlib.util.spec_from_file_location(
    "routes.report_dedup", Path(__file__).parents[1] / "routes" / "report_dedup.py"
)
report_dedup = importlib.util.module_from_spec(spec)
sys.modules["routes.report_dedup"] = report_dedup
spec.loader.exec_module(report_dedup)
canonical_order_stages = report_dedup.canonical_order_stages
effective_order_date_match = report_dedup.effective_order_date_match
split_confirmed_return = report_dedup.split_confirmed_return
product_quantity_metrics = report_dedup.product_quantity_metrics
kept_gross_revenue = report_dedup.kept_gross_revenue
reconciled_platform_breakdown = report_dedup.reconciled_platform_breakdown
product_platform_metrics = report_dedup.product_platform_metrics
payment_report_group_key = report_dedup.payment_report_group_key
allocate_order_total = report_dedup.allocate_order_total

partial_cancel_net_values = report_dedup.partial_cancel_net_values


def test_effective_date_prefers_marketplace_and_falls_back_only_when_empty():
    match = effective_order_date_match("2026-08-01", "2026-08-31")
    assert match["$or"][0] == {
        "marketplace_order_date": {"$gte": "2026-08-01", "$lte": "2026-08-31"}
    }
    assert match["$or"][1] == {
        "marketplace_order_date": {"$in": [None, ""]},
        "created_at": {"$gte": "2026-08-01", "$lte": "2026-08-31"},
    }


def test_canonical_order_preference_is_terminal_partial_then_newest():
    stages = canonical_order_stages()
    assert [next(iter(stage)) for stage in stages] == [
        "$addFields", "$addFields", "$sort", "$group", "$replaceRoot"
    ]
    sort = stages[2]["$sort"]
    assert sort["_report_terminal"] == -1
    assert sort["_report_partial_cancel"] == -1
    assert sort["updated_at"] == -1


def test_empty_order_number_uses_internal_identity():
    key = canonical_order_stages()[1]["$addFields"]["_report_dedupe_key"]
    assert key["$cond"][1] == {"$concat": ["order:", "$_report_order_number"]}
    assert key["$cond"][2]["$concat"][0] == "id:"


def test_confirmed_return_is_removed_from_net_but_cancel_is_not_in_denominator():
    net_qty, net_amount, return_qty, return_amount = split_confirmed_return(8, 800.0, 4)
    assert (net_qty, net_amount, return_qty, return_amount) == (4, 400.0, 4, 400.0)
    assert return_qty / (net_qty + return_qty) * 100 == 50.0


def test_confirmed_return_cannot_exceed_sold_quantity():
    assert split_confirmed_return(2, 300.0, 9) == (0, 0.0, 2, 300.0)


def test_product_quantity_metrics_separates_gross_and_operational_rates():
    metrics = product_quantity_metrics(net=2, cancelled=2, returned=4)
    assert metrics == {
        "gross_qty": 8,
        "gross_return_rate_pct": 50.0,
        "return_rate_excluding_cancels_pct": 66.67,
    }


def test_product_quantity_metrics_are_non_negative_and_zero_safe():
    assert product_quantity_metrics(-1, 0, 0) == {
        "gross_qty": 0,
        "gross_return_rate_pct": 0.0,
        "return_rate_excluding_cancels_pct": 0.0,
    }


def test_kept_gross_revenue_applies_discount_once():
    # Brüt 1000, indirim 200; kalan net satış 400 ise kalan brüt 500'dür.
    assert kept_gross_revenue(400, 1000, 200) == 500
    assert kept_gross_revenue(400, 0, 0) == 400


def test_product_lines_close_to_authoritative_order_total_to_the_cent():
    # Legacy item sum is 1,400 although the paid order total is 1,000.
    rows = allocate_order_total([700, 700], 1000)
    assert rows == [500, 500]
    assert sum(rows) == 1000


def test_order_total_allocation_puts_rounding_remainder_on_last_line():
    rows = allocate_order_total([1, 1, 1], 100)
    assert rows == [33.33, 33.33, 33.34]
    assert round(sum(rows), 2) == 100


def test_active_scope_partial_cancel_is_not_subtracted_twice():
    assert partial_cancel_net_values(800, 2, 200, 1, "active") == (800, 2)


def test_legacy_full_scope_partial_cancel_keeps_historical_subtraction():
    assert partial_cancel_net_values(1000, 3, 200, 1, "") == (800, 2)


def test_profitability_platform_parts_equal_canonical_product_totals():
    rows = reconciled_platform_breakdown({
        "qty": 3, "revenue": 100.01,
        "platform_breakdown": [
            {"platform": "site", "qty": 1, "revenue": 33.33},
            {"platform": "other", "qty": 2, "revenue": 66.67},
        ],
    })
    assert sum(row["qty"] for row in rows) == 3
    assert round(sum(row["revenue"] for row in rows), 2) == 100.01


def test_product_platform_metrics_keep_all_and_channel_scopes_separate():
    rows = product_platform_metrics(
        [
            {"platform": "other", "qty": 2, "revenue": 200},
            {"platform": "site", "qty": 7, "revenue": 700},
        ],
        [
            {"platform": "other", "cancel": 2, "return": 4,
             "cancel_total": 150, "return_total": 400},
            {"platform": "site", "cancel": 1, "return": 0,
             "cancel_total": 100, "return_total": 0},
        ],
    )
    by_platform = {row["platform"]: row for row in rows}
    other = by_platform["other"]
    assert other["gross_qty"] == 8
    assert other["gross_return_rate_pct"] == 50.0
    assert other["net_revenue"] == 200.0
    assert other["gross_revenue"] == 750.0
    assert other["net_qty"] + other["cancel_qty"] + other["return_qty"] == other["gross_qty"]
    assert sum(row["gross_qty"] for row in rows) == 16
    assert sum(row["net_qty"] for row in rows) == 9
    assert sum(row["cancel_qty"] for row in rows) == 3
    assert sum(row["return_qty"] for row in rows) == 4


def test_payment_report_group_puts_other_channel_records_in_one_bucket():
    assert payment_report_group_key({
        "platform": "web", "marketplace": "legacy-channel",
        "payment_method": "marketplace",
    }) == "other"
    assert payment_report_group_key({
        "platform": "web", "payment_method": "bank_transfer",
    }) == "bank_transfer"
