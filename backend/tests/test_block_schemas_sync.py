"""Blok şemaları: frontend kanonik kopya ↔ backend kopyası bayt-eşit; §2 meta doğrulaması; varsayılanlar geçerli."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_backend_copies_in_sync():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_block_schemas.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_schemas_valid_against_spec_format():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "validate_block_schemas.py")],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr


def test_spec_catalog_keys_all_present():
    sys.path.insert(0, str(REPO / "backend"))
    import pageblocks as pb
    keys = set(pb.block_schemas())
    spec = {"hero_slider", "ads_block", "full_banner", "banner_two_columns", "banner_grid_text_image", "banner_mosaic",
            "hero_tabs", "deal_slider", "features_list", "half_banners", "video_banner", "text_block", "instashop",
            "rotating_text", "countdown_bar", "deals_tabs", "product_grid_212", "products_6_1", "deals_carousel",
            "deals_week_limited", "product_grid", "banner_with_products_grid", "best_sellers", "product_slider",
            "products_carousel_tabs", "products_carousel_with_image", "product_columns", "brands_carousel",
            "home_list_categories", "category_icon_cards", "categories_icon_carousel", "categories_brands_card",
            "category_list_image_carousel", "popular_search_tags", "sidebar_image_ad", "sidebar_product_list",
            "sidebar_products_carousel", "sidebar_features", "sidebar_blog_carousel", "page_hero", "info_cards",
            "team_grid", "accordion", "text_columns"}
    assert spec <= keys, spec - keys
    globs = set(pb.global_schemas())
    assert {"site_theme", "site_topbar", "site_header", "site_departments_menu", "site_secondary_menu",
            "site_newsletter", "site_footer_contact", "site_footer_links", "site_footer_bottom",
            "site_footer_widgets", "site_contact"} <= globs
