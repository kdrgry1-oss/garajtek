"""site_refresh — iletişim, üst bar ve ana sayfa sırası tek seferlik düzeltmesi."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import site_refresh as SR  # noqa: E402


@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    return AsyncIOMotorClient(path=str(tmp_path / "sr.db"))["test"]


def _run(c):
    return asyncio.run(c)


def test_reorder_home_moves_brands_and_adds_stats_once():
    blocks = [{"type": t} for t in ("hero_slider", "ads_block", "deals_tabs", "product_slider", "brands_carousel")]
    out = SR.reorder_home(blocks)
    assert [b["type"] for b in out] == ["hero_slider", "features_list", "ads_block", "brands_carousel",
                                        "deals_tabs", "product_slider"]
    st = out[1]["settings"]
    assert st["_variant"] == "stats" and [i["strong_text"] for i in st["items"]][:2] == ["1.000+", "81 İl"]
    again = SR.reorder_home(out)
    assert [b["type"] for b in again] == [b["type"] for b in out]


def test_patch_global_topbar_and_contact():
    g = SR.patch_global({"site_topbar": {"right_items": [{"label": "Mağazamız"}], "currency_text": "Türk Lirası (₺)"}})
    assert [i["label"] for i in g["site_topbar"]["right_items"]] == ["Teknik Destek", "Mağazamız"]
    assert g["site_topbar"]["currency_text"] == ""
    assert g["site_contact"]["phone"] == "0543 276 89 73"
    assert "Tekstilkent" in g["site_contact"]["address"]
    assert len(SR.patch_global(g)["site_topbar"]["right_items"]) == 2


def test_run_once_live_data(db):
    from pageblocks import store
    _run(store.ensure(db, "home"))
    _run(db.settings.update_one({"id": "tenant_config"}, {"$set": {"company": {"address": "Mahmutbey"},
                                                                    "contact": {"phone": "0543 579 10 56"}}},
                                upsert=True))
    assert _run(SR.run_once(db)) is True
    pub = _run(store.ensure(db, "home"))
    types = [b["type"] for b in pub["blocks"]]
    assert types.index("brands_carousel") == types.index("ads_block") + 1
    assert types[1] == "features_list"
    g = _run(store.get_global(db))
    assert g["site_topbar"]["currency_text"] == ""
    assert g["site_topbar"]["right_items"][0]["label"] == "Teknik Destek"
    tc = _run(db.settings.find_one({"id": "tenant_config"}, {"_id": 0}))
    assert tc["company"]["address"] == SR.ADDRESS and tc["contact"]["phone"] == SR.PHONE
    br = _run(db.settings.find_one({"id": "business_rules"}, {"_id": 0}))
    assert br["values"]["storefront.whatsapp_number"] == "905432768973"
    assert _run(SR.run_once(db)) is False  # bir kez


def test_red_theme_applied_once(db):
    from pageblocks import store
    _run(store.ensure(db, "home"))
    assert _run(SR.apply_red_theme_once(db)) is True
    g = _run(store.get_global(db))
    assert g["site_theme"]["primary_color"] == "#d71920" and g["site_theme"]["text_on_primary"] == "white"
    assert _run(SR.apply_red_theme_once(db)) is False


def test_hide_grayzer_and_repair_sets(db):
    _run(db.products.insert_many([
        {"id": "g1", "name": "Grayzer Silikon Sprey", "brand": "GRAYZER", "is_active": True, "stock": 5, "price": 10,
         "category_id": "c1"},
        {"id": "g2", "name": "Grayzer ROCK271 Takım Arabası", "brand": "ROCKFORCE", "is_active": True, "stock": 5,
         "price": 10, "category_id": "c2"},
        {"id": "r1", "name": "Rico Pense", "brand": "Rico", "is_active": True, "stock": 5, "price": 10, "category_id": "c1"},
        {"id": "a1", "name": "Başka sprey", "brand": "DHT", "is_active": True, "stock": 5, "price": 12, "category_id": "c1"},
        {"id": "s1", "name": "Set", "product_type": "set", "is_active": True, "set_discount_pct": 5,
         "set_items": [{"product_id": "g1", "quantity": 1}, {"product_id": "g2", "quantity": 1},
                       {"product_id": "r1", "quantity": 1}]},
    ]))
    res = _run(SR.hide_grayzer_once(db))
    assert res["hidden"] == 2
    get = lambda i: _run(db.products.find_one({"id": i}, {"_id": 0}))  # noqa: E731
    assert get("g1")["is_active"] is False and get("g2")["is_active"] is False and get("r1")["is_active"] is True
    items = [i["product_id"] for i in get("s1")["set_items"]]
    assert items == ["a1", "r1"]  # g1 → aynı kategoriden a1; g2 için yedek yok → çıkarıldı
    assert _run(SR.hide_grayzer_once(db)) == {"skipped": "done"}
