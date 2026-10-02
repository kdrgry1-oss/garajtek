"""Ana sayfa varsayılan düzeni — şablonun v1.0 ana sayfası (PHP sürümünde pages/home.php):

  home-v1-slider → home-v1-ads-block → deals-and-tabs → 2-1-2-product-grid →
  best-sellers-products-cards-carousel → home-banner → recently-added-products-carousel
  (+ footer/brands-carousel ve footer ürün sütunları)

Her bölüm Admin › Tasarım › Sayfa Tasarımı'nda ayrı, düzenlenebilir bir bloktur (sırala, aç/kapa,
çoğalt, önizle). Görseli olmayan alanlar vitrinde şablon ölçüsünde nötr yer tutucu gösterir.

ensure_default_home(db): ana sayfada hiç blok yoksa VEYA yalnız eski "el değmemiş" varsayılan
iskelet bloklar varsa (görselsiz, hiç düzenlenmemiş) bu düzeni BİR KEZ kurar. Yöneticinin
düzenlediği bir tasarımın üzerine ASLA yazmaz. Üst barlar (dönen yazı / geri sayım) korunur.
"""
from __future__ import annotations

from datetime import datetime, timezone
import uuid

LAYOUT_TAG = "electro_home_v1"
_MIGRATION_KEY = "electro_home_v1"
# Üst bar blokları sayfa düzeninden bağımsızdır → kurulumda korunur.
_TOP_BAR_TYPES = {"rotating_text", "countdown_bar"}
# Eski seed-default-home iskeleti (görselsiz) — "el değmemiş" sayılır.
_OLD_DEFAULT = {("hero_slider", "Ana Slider"), ("full_banner", "Tek Banner"), ("half_banners", "İki Banner"),
                ("product_slider", "Yeni Sezon"), ("instashop", "Stilini Yarat")}

# Önerilen görsel ölçüleri (panelde gösterilir; vitrin yer tutucusu da bu oranı kullanır)
SIZES = {
    "hero_slider": [1920, 466],
    "hero_slider_mobile": [800, 860],
    "ads_block": [[410, 281], [410, 281], [714, 486]],
    "full_banner": [1170, 207],
    "brands_carousel": [200, 60],
}


def default_blocks() -> list[dict]:
    return [
        {"type": "hero_slider", "title": "Ana Slider",
         "settings": {"style": "electro", "captions": []}},
        {"type": "ads_block", "title": "Reklam Bannerları",
         "settings": {"items": [
             {"pre": "Atölyeniz için", "strong": "BÜYÜK", "post": "FIRSATLAR", "cta": "Hemen İncele", "link": "/sale"},
             {"pre": "Lift ve", "strong": "Kompresörlerde", "post": "", "upto": "20", "cta": "", "link": "/liftler"},
             {"pre": "En", "strong": "Çok Satan", "post": "Ürünler", "cta": "Hemen İncele",
              "link": "/tum-urunler?sort=popular&order=desc"},
         ]}},
        {"type": "deals_tabs", "title": "Günün Fırsatı ve Ürün Sekmeleri",
         "settings": {"special": {"mode": "auto", "title": "Günün Fırsatı"},
                      "tabs": [{"label": "Öne Çıkanlar", "source": "featured"},
                               {"label": "İndirimdekiler", "source": "discounted"},
                               {"label": "Çok Satanlar", "source": "popular"}]}},
        {"type": "product_grid_212", "title": "Kategori Fırsatları",
         "settings": {"first_label": "En İyi Fırsatlar", "first_source": "discounted", "category_ids": [], "max_tabs": 6}},
        {"type": "best_sellers", "title": "Çok Satanlar",
         "settings": {"first_label": "İlk 20", "category_ids": [], "max_tabs": 3}},
        {"type": "full_banner", "title": "Tam Genişlik Banner", "settings": {"recommended": SIZES["full_banner"]}},
        {"type": "product_slider", "title": "Son Eklenenler", "settings": {"source": "newest", "limit": 14}},
        {"type": "brands_carousel", "title": "Markalar", "settings": {}},
        {"type": "product_columns", "title": "Alt Ürün Sütunları",
         "settings": {"columns": [{"title": "Öne Çıkan Ürünler", "source": "featured"},
                                  {"title": "İndirimdeki Ürünler", "source": "discounted"},
                                  {"title": "Çok Satanlar", "source": "popular"}]}},
    ]


def _pristine(block: dict) -> bool:
    if block.get("updated_at") or (block.get("images") or []):
        return False
    st = block.get("settings") or {}
    if st.get("product_ids") or st.get("text") or st.get("captions"):
        return False
    if st.get("layout") == LAYOUT_TAG:
        return True
    return (block.get("type"), block.get("title")) in _OLD_DEFAULT


async def install_default_home(db, *, replace: bool) -> dict:
    """Varsayılan düzeni kurar. replace=True: üst barlar dışındaki ana sayfa bloklarını siler."""
    now = datetime.now(timezone.utc).isoformat()
    removed = 0
    if replace:
        res = await db.page_blocks.delete_many({"page": "home", "type": {"$nin": list(_TOP_BAR_TYPES)}})
        removed = res.deleted_count
    base = await db.page_blocks.count_documents({"page": "home"})
    created = []
    for i, b in enumerate(default_blocks(), start=1):
        doc = {
            "id": str(uuid.uuid4()), "type": b["type"], "title": b["title"], "images": [], "links": [],
            "settings": {**b.get("settings", {}), "layout": LAYOUT_TAG}, "page": "home",
            "sort_order": base + i, "is_active": True, "show_desktop": True, "show_mobile": True, "created_at": now,
        }
        await db.page_blocks.insert_one(doc)
        created.append(doc["id"])
    return {"created": len(created), "removed": removed}


async def ensure_default_home(db) -> dict | None:
    """Tek seferlik geçiş (idempotent). Kurulum yapıldıysa sonucu, yapılmadıysa None döner."""
    mig = await db.settings.find_one({"id": "migrations"}, {"_id": 0}) or {}
    if mig.get(_MIGRATION_KEY):
        return None
    blocks = await db.page_blocks.find({"page": "home"}, {"_id": 0}).to_list(200)
    layout = [b for b in blocks if b.get("type") not in _TOP_BAR_TYPES]
    result = None
    if all(_pristine(b) for b in layout):
        result = await install_default_home(db, replace=bool(layout))
    await db.settings.update_one(
        {"id": "migrations"},
        {"$set": {_MIGRATION_KEY: {"at": datetime.now(timezone.utc).isoformat(),
                                   "installed": bool(result), "skipped_custom": not result}}},
        upsert=True)
    return result
