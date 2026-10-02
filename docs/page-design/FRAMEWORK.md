# Sayfa Tasarımı — framework kullanım kılavuzu (grup ajanları için)

SPEC.md tek doğruluk kaynağıdır; bu dosya framework'ün **nasıl kullanılacağını** anlatır.

## Blok klasörü
`frontend/src/components/pageblocks/<key>/`
- `schema.json` — SPEC §2.2/§2.3 biçimi (saf JSON). `status: "stub"` blok galeride gizlidir; bloğu bitirince `"ready"` yapın.
- `defaults.json` — şablon varsayılanı (Türkçe). Ortak gruplar (`_section/_visibility/_reveal`) `_common.json`'dan gelir;
  blok yalnız farklı olanı yazar (ör. `"_section": {"margin_bottom": {"desktop": 74, ...}}`).
- `Render.jsx` — `export default function Render({ block, settings, schema, ctx })`. `settings` varsayılanlarla dolu ve
  zamanlaması/gizli öğeleri süzülmüş gelir. Kenar boşluğu/arka plan/cihaz görünürlüğü/animasyon **BlockFrame** işidir;
  Render kendi `mb-*` sınıfını eklemez. Panelden gelen her metin/görsel/bağlantıya `data-pd-field="yol.0.alan"`,
  katalog verisine `data-pd-data` (veya `.product-item`) yazılır.
- `thumb.png` (480×270) ve `Render.test.jsx` (ilk satır `import "../testMocks";`; `renderBlock`, `mockFetch`,
  `hardcodedTexts` yardımcıları `../testUtils`).

Düzenledikten sonra: `python scripts/sync_block_schemas.py` (backend kopyaları + `index.generated.js` + thumbs) ve
`python scripts/validate_block_schemas.py`. `registry.js`, `index.generated.js`, `_shared`, `_fields`, `_global` ortak dosyalardır.

## Ortak bileşenler (`_shared`)
SectionHeader, ProductCard (`card`: grid | grid_small | horizontal | list_small | featured_big | deal | image_only),
BlockCarousel (`value` = şema carousel değeri; `header={(ctl)=>...}` başlık okları), Countdown/useCountdown, StockBar,
SavingsBadge, SmartImage, SmartLink/linkHref, RichText, useProductSource/useProductSources, Placeholder, PageCtx.

## Alan tipleri
Panel formu şemadan üretilir (`_fields/SchemaForm`). Desteklenen tipler SPEC §2.3 tablosunun tamamı; ek özellikler:
`item_noun` (repeater öğe adı), `show_if` anahtarlarında `_variant`, `$parent.alan`, `$root.alan`; `super_admin`.
countdown değeri `rolling_days` içerir (`end` boşsa bugün 23:59 + N gün).

## Uçtan uca deneme
```
backend:  DB_PATH=... JWT_SECRET=... uvicorn server:app --port <8200-8999>
vitrin:   yarn build → statik sunucu (/api → backend vekil)
API:      GET /api/page-design/home (admin) · PUT /api/page-design/home/draft (If-Match) · POST .../publish
          GET /api/page-blocks?page=home (public) · POST /api/page-blocks/resolve-products · GET /api/site-design
E2E:      BASE=http://localhost:<statik> API=http://localhost:<backend>/api TOKEN=<admin jwt> node e2e/pageblocks/page_design.e2e.js
```
Önizleme: `/onizleme/sayfa/home` (admin oturumu). `?pd-noanim=1` animasyonları kapatır (ekran görüntüsü karşılaştırması).
