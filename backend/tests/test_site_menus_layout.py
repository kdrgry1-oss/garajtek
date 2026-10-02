"""Menü grupları temizleme ve ana sayfa varsayılan düzeni (saf fonksiyonlar)."""
from routes.site_menus import _clean_group, _clean_items, DEFAULTS
import pageblocks
from pageblocks.migrations import _pristine


def test_clean_items_depth_and_js_links():
    items = [{"label": "A", "link": "javascript:alert(1)", "children": [
        {"label": "B", "children": [{"label": "C", "children": [{"label": "D"}]}]}]}]
    out = _clean_items(items)
    assert out[0]["link"] == "/"
    assert out[0]["children"][0]["children"][0]["label"] == "C"
    assert "children" not in out[0]["children"][0]["children"][0]  # 3 seviye sınırı


def test_clean_group_defaults_roundtrip():
    for k, v in DEFAULTS.items():
        g = _clean_group(k, v)
        assert isinstance(g, dict)
    assert _clean_group("departments", {"mode": "x", "max_roots": 999})["max_roots"] == 30


def test_default_home_order_matches_template():
    types = [b["type"] for b in pageblocks.default_home()]
    assert types[:7] == ["hero_slider", "ads_block", "deals_tabs", "product_grid_212", "best_sellers",
                         "full_banner", "product_slider"]


def test_pristine_detection():
    assert _pristine({"type": "hero_slider", "title": "Ana Slider", "images": [], "settings": {}})
    assert not _pristine({"type": "hero_slider", "title": "Ana Slider", "images": ["x"], "settings": {}})
    assert not _pristine({"type": "text_block", "title": "Benim", "images": [], "settings": {}})
    assert not _pristine({"type": "full_banner", "title": "Tek Banner", "updated_at": "x", "settings": {}})
