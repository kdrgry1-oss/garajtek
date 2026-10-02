// Ana sayfa düzeni — şablonun v1.0 ana sayfası (PHP: pages/home.php) blok blok:
//   home-v1-slider → home-v1-ads-block → deals-and-tabs → 2-1-2-product-grid →
//   best-sellers-products-cards-carousel → home-banner → recently-added-products-carousel
//   (+ footer/brands-carousel, footer ürün sütunları)
// Vitrin (pages/Home.jsx) ve panel (Sayfa Tasarımı) bu tanımları paylaşır; backend karşılığı
// backend/home_layout.py (aynı sıra/varsayılanlar).

// Önerilen görsel ölçüleri (panelde "Önerilen: G×Y px"; vitrin yer tutucusu aynı oranı kullanır)
export const SIZES = {
  hero: [1920, 466],
  heroMobile: [800, 860],
  ads: [[410, 281], [410, 281], [714, 486]],
  fullBanner: [1170, 207],
  brand: [200, 60],
};

export const sizeText = (s) => `${s[0]} × ${s[1]}`;

// Ürün kaynakları (sekme/sütun/karusel)
export const PRODUCT_SOURCES = [
  { value: "featured", label: "Öne çıkan ürünler" },
  { value: "discounted", label: "İndirimdeki ürünler" },
  { value: "popular", label: "Çok satanlar" },
  { value: "newest", label: "En yeni ürünler" },
  { value: "category", label: "Seçili kategoriler" },
  { value: "manual", label: "Elle seçilen ürünler" },
];

export const DEFAULT_HOME_BLOCKS = [
  { type: "hero_slider", title: "Ana Slider", settings: { style: "electro", captions: [] } },
  {
    type: "ads_block", title: "Reklam Bannerları", settings: {
      items: [
        { pre: "Atölyeniz için", strong: "BÜYÜK", post: "FIRSATLAR", cta: "Hemen İncele", link: "/sale" },
        { pre: "Lift ve", strong: "Kompresörlerde", post: "", upto: "20", cta: "", link: "/liftler" },
        { pre: "En", strong: "Çok Satan", post: "Ürünler", cta: "Hemen İncele", link: "/tum-urunler?sort=popular&order=desc" },
      ],
    },
  },
  {
    type: "deals_tabs", title: "Günün Fırsatı ve Ürün Sekmeleri", settings: {
      special: { mode: "auto", title: "Günün Fırsatı" },
      tabs: [
        { label: "Öne Çıkanlar", source: "featured" },
        { label: "İndirimdekiler", source: "discounted" },
        { label: "Çok Satanlar", source: "popular" },
      ],
    },
  },
  { type: "product_grid_212", title: "Kategori Fırsatları", settings: { first_label: "En İyi Fırsatlar", first_source: "discounted", category_ids: [], max_tabs: 6 } },
  { type: "best_sellers", title: "Çok Satanlar", settings: { first_label: "İlk 20", category_ids: [], max_tabs: 3 } },
  { type: "full_banner", title: "Tam Genişlik Banner", settings: {} },
  { type: "product_slider", title: "Son Eklenenler", settings: { source: "newest", limit: 14 } },
  { type: "brands_carousel", title: "Markalar", settings: {} },
  {
    type: "product_columns", title: "Alt Ürün Sütunları", settings: {
      columns: [
        { title: "Öne Çıkan Ürünler", source: "featured" },
        { title: "İndirimdeki Ürünler", source: "discounted" },
        { title: "Çok Satanlar", source: "popular" },
      ],
    },
  },
].map((b, i) => ({ id: `default-${b.type}`, images: [], links: [], is_active: true, sort_order: i + 1, ...b }));
