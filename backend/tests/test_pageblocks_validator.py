"""backend/pageblocks doğrulayıcısı (SPEC §2.7): Türkçe hatalar, temizleme, varsayılanlar, zamanlama."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pageblocks as pb  # noqa: E402


def test_unknown_type_raises():
    with pytest.raises(pb.UnknownBlockType):
        pb.validate_block({"type": "yok_boyle_blok", "settings": {}})
    with pytest.raises(pb.UnknownBlockType):  # global şema blok olarak eklenemez
        pb.validate_block({"type": "site_theme", "settings": {}})


def test_default_settings_variant_patch_and_common_groups():
    d = pb.default_settings("ads_block", "v2")
    assert d["columns"] == "2" and d["_variant"] == "v2" and d["_v"] == 2
    assert d["_section"]["width"] == "container" and d["_section"]["margin_bottom"]["desktop"] == 74
    assert d["_visibility"] == {"desktop": True, "tablet": True, "mobile": True,
                                "schedule": {"start": "", "end": ""}, "audience": "all"}
    assert d["_reveal"]["effect"] == "fadeIn"
    assert pb.default_settings("hero_slider")["_section"]["width"] == "full_bleed"
    assert pb.default_settings("hero_slider", "nope")["_variant"] == "v1"


def test_instantiate_fills_defaults_and_ids():
    b = pb.instantiate("hero_slider")
    assert len(b["settings"]["slides"]) == 3 and all(s["_id"] for s in b["settings"]["slides"])
    assert b["template_default_hash"].startswith("sha1-")
    assert pb.instantiate("hero_slider", seed="x")["id"] == pb.instantiate("hero_slider", seed="x")["id"]


def test_rich_text_and_links_sanitised_with_turkish_errors():
    b = pb.instantiate("hero_slider")
    s = b["settings"]["slides"]
    s[0]["title"] = '<script>alert(1)</script><b onclick="x">Kalın</b><img src=x onerror=1><span class="hl">v</span>'
    s[2]["button"]["link"] = {"kind": "url", "url": "javascript:alert(1)"}
    s[1]["background"] = {"url": "data:image/png;base64,AAA"}
    clean, errors, _w = pb.validate_block(b)
    t = clean["settings"]["slides"][0]["title"]
    assert "<script" not in t and "onclick" not in t and "<img" not in t
    assert "<strong>Kalın</strong>" in t and '<span class="hl">v</span>' in t
    msgs = {e["path"]: e for e in errors}
    assert "settings.slides[2].button.link" in msgs
    assert msgs["settings.slides[2].button.link"]["label"] == "Ana Slider › Slaytlar › Slayt 3 › Düğme › Bağlantı"
    assert "geçersiz" in msgs["settings.slides[2].button.link"]["message"]
    assert clean["settings"]["slides"][2]["button"]["link"]["url"] == ""
    assert "settings.slides[1].background" in msgs and clean["settings"]["slides"][1]["background"] is None


def test_number_clamp_select_coerce_repeater_max_unknown_dropped():
    b = pb.instantiate("ads_block")
    st = b["settings"]
    st["text_size"] = 99
    st["columns"] = 4
    st["items"] = st["items"] * 3
    st["bilinmeyen"] = 1
    clean, errors, warnings = pb.validate_block(b)
    c = clean["settings"]
    assert c["text_size"] == 3 and c["columns"] == "4" and len(c["items"]) == 4
    assert "bilinmeyen" not in c
    assert any("Bilinmeyen alan" in w["message"] for w in warnings)
    assert any("En fazla 4" in w["message"] for w in warnings)
    assert not errors


def test_product_source_normalised():
    b = pb.instantiate("product_slider")
    b["settings"]["source"] = {"kind": "popular", "limit": 500, "product_ids": ["a", "", None]}
    clean, errors, _w = pb.validate_block(b)
    src = clean["settings"]["source"]
    assert src["kind"] == "best_sellers" and src["limit"] == 48 and src["product_ids"] == ["a"]
    assert not errors


def test_required_and_min_items():
    b = pb.instantiate("hero_slider")
    b["settings"]["slides"] = []
    _c, errors, _w = pb.validate_block(b, strict=True)
    assert any("En az 1" in e["message"] for e in errors)


def test_item_level_schedule_and_hidden_filtered():
    b = pb.instantiate("hero_slider")
    s = b["settings"]["slides"]
    s[0]["_schedule"] = {"start": "2030-01-01T00:00", "end": ""}
    s[1]["_hidden"] = True
    out = pb.apply_schedule([b], datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert [x["title"] for x in out[0]["settings"]["slides"]] == [s[2]["title"]]
    s[2]["_schedule"] = {"start": "", "end": "2020-01-01T00:00"}
    assert pb.apply_schedule([b], datetime(2026, 1, 1, tzinfo=timezone.utc)) == []  # hepsi gitti → blok gizli


def test_block_schedule_inactive_and_legacy():
    b = pb.instantiate("full_banner")
    b["settings"]["_visibility"]["schedule"] = {"start": "2026-05-01T10:00", "end": "2026-05-01T12:00"}
    now_in = datetime(2026, 5, 1, 8, 30, tzinfo=timezone.utc)  # İstanbul 11:30
    now_out = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)  # İstanbul 13:00
    assert pb.apply_schedule([b], now_in) and not pb.apply_schedule([b], now_out)
    b2 = pb.instantiate("full_banner")
    b2["is_active"] = False
    assert pb.apply_schedule([b2]) == []
    leg = {"id": "x", "type": "eski", "settings": {"_legacy": True}}
    assert pb.apply_schedule([leg]) == []
    clean, errors, warnings = pb.validate_block(leg)
    assert clean["settings"]["_legacy"] and not errors and warnings


def test_singleton_and_layout_validation():
    blocks = [pb.instantiate("rotating_text"), pb.instantiate("rotating_text"), pb.instantiate("ads_block")]
    clean, g, errors, _w = pb.validate_layout(blocks, {})
    assert [b["sort_order"] for b in clean] == [1, 2, 3]
    assert any("yalnız bir tane" in e["message"] for e in errors)
    assert set(g) >= {"site_theme", "site_header"} and g["site_theme"]["primary_color"] == "#fed700"


def test_global_color_validation():
    g, errors, _w = pb.validate_global({"site_theme": {"primary_color": "url(javascript:1)"}})
    assert errors and g["site_theme"]["primary_color"] == "#fed700"


def test_with_defaults_fills_new_fields_into_old_items():
    st = {"slides": [{"title": "Eski slayt"}]}
    out = pb.with_defaults("hero_slider", st)
    assert out["slides"][0]["title"] == "Eski slayt"
    assert out["slides"][0]["button"]["style"] == "primary" and out["slides"][0]["layout"] == "promo"
    assert out["carousel"]["transition"] == "fade"
