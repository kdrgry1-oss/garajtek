# Sayfa Tasarımı — %100 Şablon Eşdeğerliği Spesifikasyonu

> Durum: KESİN SPEC (v2). Tüm uygulama ajanları (framework + blok grupları A/B/C/D) bu dosyayı
> tek doğruluk kaynağı kabul eder. Bu dosyayla kod çelişirse kod düzeltilir.
>
> Kaynak şablon: ThemeForest **Electro** — v1.0 (`theme/1.0/PHP`, `theme/1.0/HTML`) ve v2.0
> (`theme/2.0/html/home/*.html`). Aşağıda `T1` = `theme/1.0/PHP`, `T1H` = `theme/1.0/HTML`,
> `T2` = `theme/2.0` (scratchpad içindeki açılmış zip).

## 0. Amaç ve kabul ölçütleri

Sahibin hedefi (aynen): *"Sayfa tasarımı yönetimi anasayfa ile %100 uyumlu çalışmalı; en ince
ayrıntısına kadar koda gerek kalmadan düzenleyebilmeliyim."*

Kabul ölçütleri (her biri Playwright ile test edilir — bkz. §9):

1. **Eşdeğerlik:** Vitrinde ana sayfada görünen HER bölüm, metin, görsel, bağlantı, ürün kaynağı,
   karusel ayarı, görünürlük, sıra ve stil Sayfa Tasarımı'ndan düzenlenebilir. Vitrinde
   "sabit kodlu" (panelden değiştirilemeyen) tek bir görünür metin/görsel/bağlantı kalmaz
   (istisna: ürün/kategori verisinin kendisi — o katalogdan gelir).
2. **Tek şema:** Panel formu, vitrin renderer'ı ve backend doğrulaması AYNI blok şemasından
   (§2) beslenir. Bir alanı şemaya eklemek = panelde form alanı + backend doğrulaması + renderer
   prop'u. Elle yazılmış blok-özel panel formu YOK (özel widget'lar hariç, §2.3).
3. **Önizleme = vitrin:** Panel önizlemesi vitrinin gerçek blok bileşenlerini (aynı CSS, aynı
   `.electro` kapsamı) bir iframe içinde render eder; piksel farkı 0 (aynı viewport'ta
   vitrin ekran görüntüsü ile önizleme ekran görüntüsü karşılaştırılır).
4. **Varsayılan = şablon:** "Şablon varsayılanına sıfırla" ile her blok, v1.0 `home.html`'deki
   karşılığını (Türkçe/garaj ekipmanı metinleriyle) birebir yeniden üretir.
5. **Taslak/yayın:** Düzenlemeler taslakta kalır; "Yayınla" atomik; revizyon geçmişi ve geri
   alma vardır. Yarım kalmış kayıt canlı sayfayı bozamaz.
6. **Türkçe:** Tüm panel etiketleri, yardım metinleri, varsayılan içerikler Türkçe.

---

## 1. Mevcut durum (denetim özeti) ve kapatılacak boşluklar

| Konu | Bugün | Hedef |
|---|---|---|
| Depolama | `page_blocks` satırları; `settings` opak dict; tip doğrulaması yok | Şema-doğrulamalı `settings`; yayın + taslak `page_layouts` belgeleri (§5) |
| Varsayılanlar | `backend/home_layout.py` ve `frontend/src/lib/homeLayout.js` elle kopya, zaten farklı | Her blok için tek `defaults.json`; backend senkron kopyası + eşitlik testi |
| Panel formları | `PageDesign.jsx` (1826 satır) + `HomeBlockFields.jsx` içinde elle | Şemadan otomatik form (`SchemaForm`) |
| Önizleme | Şematik küçük resim listesi; "Taslağı sitede önizle" ayrı sekmede, üst barlar canlıdan | Yan yana canlı iframe, gerçek bileşenler, cihaz genişlikleri, tıkla-seç |
| Kaydet | Sıralı DELETE/PUT/POST/reorder, atomik değil, kaydet = yayınla | Taslak otomatik kayıt + atomik yayın + revizyon |
| Karusel ayarları | `Home.jsx` içinde sabit | Şemada `carousel` alanı (autoplay, aralık, döngü, kırılım başına adet…) |
| Geri sayım | Yalnız `deals_tabs.special.mode/title` | Bitiş tarihi, birimler, Türkçe etiketler, süre bitiminde davranış |
| Zamanlama hatası | Yayın filtresi `images/links/img_dims/slide_schedule`'ı süzüyor ama `captions/mobile_images`'ı süzmüyor → kayık açıklamalar | Slaytlar tek `repeater` (her slayt kendi alanlarını taşır) — paralel diziler kalkar |
| Taslak sızıntısı | Public GET `is_active=false` blokları da döndürüyor (`?preview=true`) | Public GET yalnız yayınlanmış + aktif + zamanı gelmiş blokları döndürür |
| Tip değiştirme | Düzenle modalında blok tipi değiştirilebiliyor, eski ayarlar kalıyor | Tip değiştirilemez; "Çoğalt" ve "Sil" var |
| `seed-default-home` | Eski 5 bloklu tuzak | Kaldırılır (410 Gone + mesaj) |
| Ürün önbelleği | `_srcCache` oturum boyunca bayatlıyor | 60 sn TTL + önizlemede devre dışı |
| `GET /page-blocks` | `.to_list(50)` sınırı | Sınır kalkar (yayın belgesi tek doküman) |

---

## 2. Ortak blok şeması formatı (JSON)

### 2.1 Dosya düzeni (konvansiyon — framework oluşturur, grup ajanları doldurur)

```
frontend/src/components/pageblocks/
  registry.js                 # framework: tüm blokları toplar (otomatik import listesi)
  _shared/                    # framework: SectionHeader, ProductCard varyantları, Countdown,
                              #   BlockCarousel, SmartLink, SmartImage, RichText, StockBar,
                              #   SavingsBadge, useProductSource, useBlockTheme, Placeholder
  _fields/                    # framework: SchemaForm + her alan tipinin widget'ı
  <key>/
    schema.json               # GRUP AJANI: alan tanımları (bu spesifikasyondaki tablo)
    defaults.json             # GRUP AJANI: şablon varsayılanı (Türkçe)
    Render.jsx                # GRUP AJANI: vitrin bileşeni — props: { block, settings, ctx }
    thumb.png                 # GRUP AJANI: blok galerisi küçük resmi (480×270, şablondan ekran görüntüsü)
    Render.test.jsx           # GRUP AJANI: en az "varsayılanlarla render" + "boş durum" testi
    migrate.js                # (opsiyonel) eski ayar → yeni ayar dönüşümü (frontend tarafı yok; bkz backend)
backend/pageblocks/
  __init__.py                 # framework: şema yükleyici, doğrulayıcı, varsayılan üretici
  schemas/<key>.schema.json   # SENKRON KOPYA (script üretir, elle düzenlenmez)
  schemas/<key>.defaults.json # SENKRON KOPYA
  migrations.py               # framework: eski blok → yeni blok dönüştürücüler (§6)
scripts/sync_block_schemas.py # framework: frontend → backend kopyalar; --check modu CI/test için
```

- `schema.json` ve `defaults.json` **saf JSON**'dur (yorum yok) — CRA bunları doğrudan import eder,
  backend `json.load` eder. Kanonik konum `frontend/src/components/pageblocks/<key>/`; backend
  kopyası `scripts/sync_block_schemas.py` ile üretilir; `backend/tests/test_block_schemas_sync.py`
  iki kopyanın bayt-eşit olduğunu doğrular.
- Grup ajanları YALNIZ kendi `<key>/` klasörlerine dokunur + `sync` script'ini çalıştırıp
  `backend/pageblocks/schemas/<key>.*.json` kopyalarını commit eder. `registry.js`'e ekleme
  framework tarafından `import.meta`-benzeri otomatik toplama ile yapılır
  (`require.context('./', true, /schema\.json$/)`), yani grup ajanı `registry.js`'e dokunmaz.

### 2.2 Şema belgesi

```jsonc
{
  "key": "hero_slider",              // blok tipi (page_blocks.type) — değişmez
  "version": 2,                      // şema sürümü; settings._v ile karşılaştırılır
  "title": "Ana Slider",             // galeride ve listede görünen ad
  "description": "Tam genişlik görsel slider (şablon: home-v1-slider)",
  "category": "slider",              // galeri kategorisi: slider | banner | urun | firsat | kategori | marka | icerik | kenar | ust_bar
  "group": "A",                      // uygulama grubu (bilgi amaçlı)
  "template_refs": ["T1/inc/blocks/homepage/home-v1-slider.php"],
  "layout": "full_bleed",            // full_bleed | container | sidebar
  "singleton": false,                // true → sayfada en fazla 1 adet
  "allowed_pages": ["home", "*"],    // hangi sayfa tasarımlarında eklenebilir
  "variants": [                      // opsiyonel "Görünüm" seçici; seçildiğinde defaults_patch uygulanır
    { "value": "v1", "label": "v1 – Ana sayfa (varsayılan)", "defaults_patch": { } },
    { "value": "v3", "label": "v3 – Menüsüz geniş açıklama", "defaults_patch": { "caption_column": "wide" } }
  ],
  "tabs": ["İçerik", "Ürünler", "Görünüm", "Karusel", "Gelişmiş"], // form sekmeleri (boş sekme gizlenir)
  "fields": [ /* Alan[] — §2.3 */ ],
  "common": ["section", "visibility", "reveal"] // otomatik eklenen ortak gruplar — §2.4
}
```

### 2.3 Alan (Field) tanımı

```jsonc
{
  "name": "title",                 // settings içindeki anahtar (iç içe: "deal.title" değil; iç içe için type:"group")
  "type": "text",                  // aşağıdaki tiplerden biri
  "label": "Başlık",
  "help": "Bölüm başlığı. Boş bırakılırsa başlık satırı gizlenir.",
  "tab": "İçerik",
  "default": "Çok Satanlar",       // defaults.json'daki değerle aynı olmalı (test eder)
  "required": false,
  "show_if": { "header_right": ["pills"] },   // koşullu görünürlük (AND; değer listesi = OR)
  "responsive": false,             // true → değer {desktop, tablet, mobile} nesnesi; panelde cihaz sekmeli
  "width": "full"                  // form yerleşimi: full | half | third
}
```

**Alan tipleri ve değer şekilleri** (backend doğrulayıcı bunları zorlar):

| type | Ek özellikler | Değer şekli | Panel widget'ı |
|---|---|---|---|
| `text` | `max_length` (vars. 200), `placeholder` | `"string"` | tek satır |
| `textarea` | `max_length` (2000) | `"string"` | çok satır |
| `rich_text` | `marks`: alt kümesi `["strong","em","br","span_highlight","sup","sub","link"]`, `max_length` (1000) | güvenli HTML string (sunucuda beyaz liste ile temizlenir: `strong, em, br, span[class=hl], sup, sub, a[href]`) | mini editör: **K**, *İ*, satır sonu, vurgu rengi |
| `image` | `recommended: [w,h]`, `min: [w,h]`, `accept` (`image/*` vars., `video/*` opsiyonel), `allow_mobile` (bool), `aspect_lock` (bool) | `{ "url", "alt", "w", "h", "focal": {"x":0.5,"y":0.55}, "mobile_url"?, "mobile_focal"?, "crop"?: {x,y,w,h} }` | yükle/kütüphaneden seç, ölçü ipucu ("Önerilen 1920×466 px — yüklenen 1600×400, %83"), kırpma + odak noktası, alt metin, opsiyonel mobil görsel |
| `link` | `kinds` alt kümesi `["category","product","page","brand","search","url","none"]` | `{ "kind":"category", "id":"…", "slug":"…", "url":"/liftler", "label"?:"", "new_tab":false }` (`url` her zaman çözümlenmiş halde saklanır; `id` varsa vitrin slug değişikliğinde yeniden çözer) | seçici: Kategori / Ürün / Sayfa / Marka / Arama / Özel URL |
| `color` | `palette`: `"theme"` ise tema renkleri önerilir, `allow_transparent` | `"#fed700"` veya `"var(--primary)"` veya `""` (varsayılan) | renk seçici + "Tema ana rengi" + "Varsayılan" |
| `number` | `min`, `max`, `step`, `unit` (`px`,`ms`,`%`,`adet`,`em`) | `number` | sayı + birim |
| `bool` | — | `true/false` | anahtar (switch) |
| `select` | `options: [{value,label}]` | `"value"` | açılır liste veya segment (≤4 seçenek) |
| `icon` | `set: "electro"` (font-electro + FA alt kümesi), `allow_upload` | `{ "icon":"ec-transport" }` veya `{ "image": {image} }` | ikon galerisi + SVG/PNG yükle |
| `date_time` | `with_time` (vars. true), `tz` (vars. `Europe/Istanbul`) | ISO-8601 `"2026-12-31T23:59:00+03:00"` | tarih + saat seçici |
| `product_source` | `allowed_kinds`, `default_limit`, `max_limit` (vars. 48) | bkz. aşağı | kaynak düzenleyici |
| `product_picker` | `multiple` (bool), `max` | `["prod_id", …]` veya `"prod_id"` | ürün arama + sürükle sırala |
| `category_picker` | `multiple`, `max`, `with_children` (bool) | `["cat_id", …]` | ağaç seçici (`CategoryTreeSelect`) |
| `brand_picker` | `multiple` | `["brand_id"]` | marka listesi |
| `repeater` | `item_fields: Field[]`, `min`, `max`, `item_label` (şablon: `"{{label}}"`), `item_default`, `sortable` (vars. true), `item_toggle` (vars. true → her öğede `_hidden` bool), `item_schedule` (bool → her öğede `_schedule`) | `[ {…}, … ]`; her öğe kalıcı `_id` (uuid) taşır | kartlar: sürükle, çoğalt, gizle, sil, aç/kapa |
| `group` | `fields: Field[]`, `collapsible` | `{ … }` | çerçeveli alan grubu |
| `carousel` | `defaults` (aşağıdaki şekil), `hide`: gizlenecek alt alanlar | bkz. aşağı | "Karusel" sekmesi |
| `spacing` | — | `{ "top": 0, "bottom": 50, "unit":"px" }` (responsive destekli) | dört kutu |
| `countdown` | — | bkz. aşağı | geri sayım grubu |
| `section_header` | — | bkz. §2.5 | başlık satırı grubu |
| `html` | yalnız süper-admin, `sanitize: "strict"` | `"string"` | kod alanı (yalnız `text_block` eski uyumluluk) |

**`product_source` değeri:**

```jsonc
{
  "kind": "featured",            // manual | category | discounted | newest | best_sellers | featured | top_rated | tag | brand | recently_viewed
  "product_ids": [],             // kind=manual
  "category_ids": [], "include_children": true,   // kind=category
  "tag": "",                     // kind=tag
  "brand_ids": [],               // kind=brand
  "limit": 6,
  "sort": "default",             // default | newest | price_asc | price_desc | popular | discount_desc | name_asc | random_daily
  "exclude_out_of_stock": true,
  "exclude_ids": [],             // her zaman hariç tutulacaklar
  "fill_with": "none"            // limit dolmazsa: none | newest | featured  (boş blok görünmesin diye)
}
```

Backend tek uç: `POST /api/page-blocks/resolve-products` `{sources:[source…]}` →
`{results:[[product…]…]}` (kart için gereken alanlar; 60 sn önbellek; `recently_viewed`
istemcide localStorage id listesinden `manual` olarak çözümlenir). Mevcut eşleme korunur:
`featured→is_featured`, `discounted→slider-feed?source=discounted`, `best_sellers→sort=popular`,
`newest→created_at desc`, `top_rated→rating desc` (rating yoksa `popular`'a düşer).

**`carousel` değeri** (Owl v1 davranışını Embla `Carousel.jsx` ile taklit eder):

```jsonc
{
  "per_view": { "0": 1, "480": 2, "768": 2, "992": 3, "1200": 6, "1480": 6 }, // min-width kırılımları (Owl tarzı)
  "slides_to_scroll": 1,
  "rows": 1,                  // sayfa başına satır (kart karuselleri 2)
  "gutter": 0,                // px
  "autoplay": false, "interval": 5000, "pause_on_hover": true,
  "loop": false, "rewind": false,
  "transition": "slide",      // slide | fade
  "speed": 300,               // ms
  "dots": true,
  "arrows": "header",         // none | header (başlık sağında ‹ ›) | side (iki yanda) | outer (marka karuseli)
  "drag": true,
  "last_active_divider": true // şablondaki .last-active: son görünen kartın sağ ayırıcısı gizlenir
}
```

**`countdown` değeri:**

```jsonc
{
  "enabled": true,
  "end": "2026-12-31T23:59:00+03:00",
  "units": ["days","hours","minutes","seconds"],     // alt küme
  "hide_zero_days": true,                              // şablon: span[data-value="0"] gizli
  "labels": { "days":"Gün", "hours":"Saat", "minutes":"Dk", "seconds":"Sn" },
  "heading": "Acele edin! Kampanya bitimine:",
  "on_expire": "hide_block",                           // hide_block | hide_timer | show_text | zero
  "expired_text": "Kampanya sona erdi",
  "pad": true
}
```

**Özel widget'lar** (otomatik formun parçası, framework yazar): `ImageField` (yükle + kırp +
odak), `LinkField`, `ProductSourceField` (canlı "eşleşen ürün sayısı: 14" göstergesi),
`CarouselField` (kırılım tablosu), `CountdownField`, `IconField`, `RichTextField`,
`RepeaterField`. Grup ajanları yeni widget YAZMAZ; eksik ihtiyaç framework'e bildirilir.

### 2.4 Ortak gruplar (`common`) — her bloğa otomatik eklenir

`section` (sekme "Görünüm"):

| alan | tip | varsayılan | not |
|---|---|---|---|
| `_section.width` | select `container`/`full_bleed`/`wide` | şemanın `layout` değeri | `wide` = 1430 px (v2.0 wd) |
| `_section.background` | color | `""` | bant rengi (ör. #f9f9f9) |
| `_section.background_image` | image (rec. 1920×600) | — | |
| `_section.padding` | spacing (responsive) | 0/0 | şablon bantları 58px 0 |
| `_section.margin_bottom` | number px (responsive) | 50 (= 3.571em × 14) | şablonda blok başına farklı; her `defaults.json` kendi değerini yazar |
| `_section.text_color` | color | `""` | |
| `_section.anchor_id` | text | `""` | `#kampanyalar` gibi bağlantı hedefi |
| `_section.css_class` | text (yalnız süper-admin) | `""` | |

`visibility` (her blok satırında da ikon olarak):

| alan | tip | varsayılan |
|---|---|---|
| `_visibility.desktop` (≥1200) | bool | true |
| `_visibility.tablet` (768–1199) | bool | true |
| `_visibility.mobile` (<768) | bool | true |
| `_visibility.schedule` | group `{start: date_time, end: date_time}` | boş |
| `_visibility.audience` | select `all`/`guests`/`members` | `all` |

`reveal`:

| alan | tip | varsayılan |
|---|---|---|
| `_reveal.enabled` | bool | true |
| `_reveal.effect` | select `fadeIn`,`fadeInUp`,`fadeInDown`,`fadeInLeft`,`fadeInRight`,`zoomIn`,`slideInUp` | `fadeIn` |
| `_reveal.offset` | number % | 90 |
| `_reveal.once` | bool | true |

`is_active` (yayında/gizli), `title` (yalnız panelde görünen iç ad) blok kökünde kalır.

### 2.5 `section_header` (tüm ürün bölümlerinin ortak başlığı)

Şablon: `h2.h1` (1.786em, line-height 1.6em, padding-bottom .4em) + alt 1px #dadada çizgi + başlık
genişliğinde 2px ana renk alt çizgi; sağ tarafta: hiçbiri | ok (‹ › #aeaeae 1.429em) | hap/sekme
bağlantıları | "Tümünü gör" bağlantısı.

```jsonc
{
  "title": "Çok Satanlar",
  "tag": "h2",                       // h2 | h3 | sr-only (başlık gizli, ekran okuyucu için)
  "align": "left",                   // left | center
  "right": "pills",                  // none | arrows | pills | link | countdown
  "pills": [ { "label":"İlk 20", "link":{…}, "active":true, "as_tab": false } ],
  "link": { "label":"Tümünü gör", "link":{…} },
  "underline": true                  // 2px ana renk alt çizgi
}
```

### 2.6 Kayıtlı blok belgesi (veritabanı)

```jsonc
{
  "id": "uuid", "type": "hero_slider", "title": "Ana Slider (iç ad)",
  "is_active": true,
  "settings": { "_v": 2, "_variant": "v1", /* şema alanları */ , "_section":{…}, "_visibility":{…}, "_reveal":{…} },
  "sort_order": 1,
  "template_default_hash": "sha1-of-defaults.json", // "varsayılandan değişti mi" rozetini sağlar
  "created_at": "…", "updated_at": "…", "updated_by": "admin_id"
}
```

Eski üst-düzey `images[]`, `links[]`, `img_dims`, `show_desktop`, `show_mobile`, `page` alanları
geçişte (§6) `settings` içine taşınır; bir sürüm boyunca okuma uyumluluğu için korunur, sonra kalkar.

### 2.7 Backend doğrulama

`backend/pageblocks/__init__.py`:

- `load_schemas()` — tüm `schemas/*.schema.json`'ı yükler (uygulama başında, önbellekli).
- `validate_block(block) -> (clean_block, errors[])` — bilinmeyen tip → 422; bilinmeyen alanlar
  atılır (uyarı ile), tip uyumsuzluğu → 422 alan yolu ile (`settings.slides[2].button.link.url`),
  `rich_text` sanitize, `image.url` yalnız `/api/uploads/…`, `/static/…` veya izinli CDN,
  `link.url` `javascript:` vb. reddedilir, `number` min/max kırpılır, `repeater` max uygulanır.
- `default_settings(key, variant=None)` — `defaults.json` + varyant yaması + ortak grup varsayılanları.
- `apply_schedule(blocks, now)` — blok ve repeater öğe düzeyinde `_schedule` / `_visibility.schedule` süzme
  (paralel dizi yok → kayma hatası biter).
- Hatalar Türkçe mesaj döndürür ("Slayt 3: düğme bağlantısı geçersiz").

---

## 3. Blok kataloğu

Gösterim: her blok için `anahtar` — Türkçe ad — grup — durum — şablon kaynağı; ardından alan
listesi `alan: tip = varsayılan` (varsayılan v1.0 home.html değerlerinin garajtek uyarlamasıdır).
"Görsel" varsayılanları `null` = yükleme yapılmadıysa şablon ölçüsünde nötr yer tutucu
(`_shared/Placeholder`) gösterilir; demo içerik kartı (`DemoContentCard`) bu alanları doldurabilir.

Durum: **mevcut** = bugün var, yeniden yazılacak (`exists-needs-work`); **yeni** = yok.

Varsayılan ana sayfada (`in_default_home`) olanlar ★ ile işaretli, sıra numarasıyla.

### Ürün kartı varyantları (paylaşılan — `_shared/ProductCard`, framework yazar)

| `card` değeri | Şablon | Görsel | İçerik |
|---|---|---|---|
| `grid` | `display_product()` (T1 inc/components/product.php) | 250×232 | kategori bağlantısı, h3 ad, görsel, fiyat (ins/del), "Sepete Ekle", hover: Favori + Karşılaştır |
| `grid_small` | `.columns-6` make-product-small | 250×232 küçük | aynı, küçük tipografi |
| `horizontal` | `display_card_product()` | 250×232, media-left %42.35 | yatay kart; hover alanı üstte 1px #eaeaea |
| `list_small` | footer/sidebar listesi | 75×75 / 180×180 | görsel + ad + fiyat (+ yıldız opsiyonel) |
| `featured_big` | 2-1-2 / 6-1 ana ürün | 600×600 (+3× 180×180 küçük) | büyük görsel, fiyat 1.786em, küçük resim galerisi |
| `deal` | section-onsale-product | 250×232 / 600×600 | kazanç rozeti, fiyat, stok çubuğu, geri sayım |
| `image_only` | v2 recently viewed | 300×300 | yalnız görsel |

Global kart ayarları (tema ayarı, §4.1): favori / karşılaştır / kategori etiketi / eski fiyat /
indirim rozeti ("-%25") göster-gizle, "Sepete Ekle" metni.

---

### GRUP A — Slider, banner ve içerik

#### A1 ★1 `hero_slider` — Ana Slider — mevcut
Kaynak: T1 `home-v1-slider.php`, `home-v2-slider.php`, `homepage-3/home-v3-slider.php`, `_sliders.scss`,
T1H `electro.js` L98-319; T2 index/v2/v3/v4/v9/v10/v11 slider bölümleri. layout `full_bleed`.

Varyantlar (`_variant`): `v1` (vars.: açıklama `col-md-offset-3 col-md-5` — dikey menüye yer
bırakır), `v2` (sol kenar çubuklu düzen: left 33.33%), `v3` (`col-md-8`, menüsüz), `v2_product`
(T2 index: arka plan + sağda ürün görseli, Slick tarzı kaydırma), `boxed_side_banners`
(T2 v4/v10: kutulu slider + sağda 2–3 banner kartı), `rounded_with_deals` (T2 v9: yuvarlak köşeli
slider + sağda fırsat kartı karuseli), `fullscreen` (T2 v11: şeffaf header altında, 1920×660),
`menu_strip` (T2 v7: gövde içi dikey menü + slider + kategori şeridi + sağ banner sütunu).

| alan | tip | varsayılan |
|---|---|---|
| `height` | number px, responsive | desktop 485, tablet 400, mobile 300 |
| `background_color` | color | `#f9f9f9` |
| `caption_column` | select `offset3_5` / `wide8` / `center` / `left4` | `offset3_5` |
| `caption_padding_top` | number px, responsive | 85 / 60 / 20 |
| `slides` | repeater (min 1, max 10, item_schedule) | 3 slayt (aşağı) |
| `slides[].background` | image rec 1920×466, allow_mobile (mobil rec 800×860), focal vars. {0.5,0.55} | null |
| `slides[].product_image` | image rec 416×420 (show_if variant v2_product/boxed/menu_strip) | null |
| `slides[].layout` | select `price` (başlık+alt başlık+fiyat+düğme) / `promo` (üst başlık+vurgulu başlık+düğme) / `image_only` | 1: price, 2–3: promo |
| `slides[].pretitle` | text (`.hero-subtitle-v2`, #34bcec, 1.125em/600, büyük harf) | promo: "ATÖLYENİZE DEĞER KATIN" |
| `slides[].title` | rich_text marks strong/br (`.hero-1` 4.125em/300 veya `.hero-2` 3em/300) | 1: "YENİ NESİL<br>LİFT SİSTEMLERİ"; 2: "Kompresörlerde <strong>%40'a varan</strong> indirim"; 3: "Lastik ekipmanlarında <strong>yeni sezon</strong>" |
| `slides[].subtitle` | text (`.hero-subtitle` 0.938em/800) | 1: "PROFESYONEL SERVİSLER İÇİN" |
| `slides[].price_prefix` | text | 1: "başlayan fiyatlarla" |
| `slides[].price` | text (`.hero-v2-price span` 3.5em/700) | 1: "₺49.900" |
| `slides[].button` | group {`text`: text = "Alışverişe Başla", `link`: link = kategori `liftler`, `style`: select primary/dark/outline = primary} | |
| `slides[].text_color` | color | `#333e48` |
| `slides[].text_align` | select left/center/right | left |
| `slides[].animation` | sabit katmanlar için `group` {pretitle, title, subtitle, price, button, product_image} × {`effect` select (fadeIn, fadeInDown, fadeInUp, fadeInLeft, fadeInRight, zoomIn, slideInLeft, slideInRight, none), `delay` ms, `duration` ms} | slayt1: fadeInDown 500/700/1000/1000, 800 ms; slayt3: fadeInLeft/fadeInRight/fadeInLeft |
| `side_banners` | repeater max 3 (show_if boxed_side_banners/menu_strip) {image rec 246×176, text rich_text, cta text "Hemen Al", link, style select gray/white_rotated} | 3 öğe |
| `side_deals` | group (show_if rounded_with_deals) {source product_source kind discounted limit 4, countdown} | |
| `category_strip` | repeater (show_if menu_strip) {image 300×300, label, link} | 5 öğe |
| `carousel` | carousel; hide per_view/rows | autoplay true, interval 5000, pause_on_hover false, loop true, transition `fade`, speed 250, dots true, arrows `none` |
| `easing` | select easeOutCubic/linear | easeOutCubic |

Notlar: v1 şablonun hata/tekrarları (aynı açıklamanın tekrarlanması) kopyalanmaz. Header dikey menü
"ana sayfada açık" ayarı (§4) açıksa `caption_column=offset3_5` önerilir; panel bu uyumsuzluğu uyarır.

#### A2 ★2 `ads_block` — Reklam Kutuları (3'lü / 2'li / 4'lü) — mevcut
Kaynak: T1 `home-v1-ads-block.php`, `home-v2-ads-block.php`, `homepage-3/home-v3-ads-block.php`, `_ads.scss`;
T2 index/v2/v3/v5/v6/v8 Banner bölümleri. layout `container`.

Varyantlar: `v1` (3 sütun, görsel %60 / metin %40, metin 1.286em), `v2` (2 sütun, 60/40, 1.571em,
letter-spacing -1px), `v3` (2 sütun, 62/38), `v2_cards` (T2: 4 sütun gri kart 190×150 küçük görsel),
`wide_plus_two` (T2 v8: 1 geniş + 2).

| alan | tip | varsayılan |
|---|---|---|
| `columns` | select 2/3/4 | 3 |
| `ratio` | select `60_40` / `62_38` / `50_50` | 60_40 |
| `text_size` | number em | 1.286 |
| `card_background` | color | `#f5f5f5` |
| `items` | repeater max 4 | 3 öğe |
| `items[].image` | image rec (1) 410×281 (2) 410×281 (3) 714×486 | null |
| `items[].text` | rich_text strong/br (büyük harf, 200) | 1: "Atölyeniz için<br><strong>BÜYÜK</strong> fırsatlar"; 2: "Lift ve<br><strong>Kompresörlerde</strong>"; 3: "En<br><strong>Çok Satan</strong><br>Ürünler" |
| `items[].action_type` | select `link` / `upto` / `from_price` | 1: link, 2: upto, 3: link |
| `items[].action_text` | text (show_if link) | "Hemen İncele" |
| `items[].action_prefix` | text (show_if upto/from_price) | upto: "%'ye varan"; from: "başlayan" |
| `items[].action_value` | text | upto: "20"; from: "749" |
| `items[].action_suffix` | text | from: ",99" |
| `items[].currency` | text | "₺" |
| `items[].link` | link | 1: `/sale`, 2: kategori `liftler`, 3: `/tum-urunler?sort=popular&order=desc` |
| `items[].image_rotation` | number derece (T2 v8) | 0 |
| `_section.margin_bottom` | | 74 (5.286em) |

#### A3 ★6 `full_banner` — Tam Genişlik Banner — mevcut
Kaynak: T1 `home-banner.php`, `home-banner-v2.php`; T2 index L8038 (metin + fiyat kutulu).
Varyantlar: `image` (v1: yalnız görsel bağlantı), `text_overlay` (T2: arka plan + başlık + fiyat kutusu).

| alan | tip | varsayılan |
|---|---|---|
| `image` | image rec 1170×207, allow_mobile (rec 750×300) | null |
| `link` | link | `/sale` |
| `title` | rich_text (show_if text_overlay) | "ATÖLYENİZİ <strong>YENİLEYİN</strong>, KAZANÇLI ÇIKIN" |
| `price_label` | text | "BAŞLAYAN FİYATLARLA" |
| `price` | text | "₺7.999" |
| `price_box_color` | color | tema ana rengi |
| `_section.margin_bottom` | | 70 |

#### A4 `banner_two_columns` — İki Kolonlu Görsel Banner — yeni
T2 v2/v3/v6/v7/v8/v11. `items` repeater min 2 max 2 {image rec 690×150, link, alt}; `gap` number 30.

#### A5 `banner_grid_text_image` — Metinli/Görselli Banner Izgarası — yeni
T2 v5/v7. `rows` repeater max 3 {`wide_side` select left/right, `wide.background` color #f5f5f5,
`wide.title` text = "Profesyonel Lastik Sökme Makineleri", `wide.text` text = "ve en hızlı balans
çözümleri", `wide.price_prefix` = "başlayan", `wide.price` = "₺24.900", `wide.image` image 446×262,
`wide.link` link, `small.image` image 446×262, `small.link` link}.

#### A6 `banner_mosaic` — Banner Mozaiği (1 büyük + 6 küçük) — yeni
T2 v9. `big` {image 552×325, link}; `small` repeater max 6 {image 268×155, link}; `radius` number 10.

#### A7 `hero_tabs` — Sekmeli Hero + Ürün Karuseli — yeni
T2 v6. `background` image 1920×714; `tabs` repeater max 6 {label text, title rich_text, offer_label
text "SON FIRSAT", amount text "₺2.500", amount_suffix "İNDİRİM!", button {text, link}, image
724×360}; `products` group {source product_source (kind featured, limit 9), carousel (per_view
{0:2,768:2,992:2,1200:3,1400:5,1480:7}, arrows side)}.

#### A8 `deal_slider` — Haftanın Fırsatı Slider — yeni
T2 v5 (küçük resim navigasyonlu) ve v8 (sarı bant). Varyant `thumbs` / `primary_band`.
`background` image 1400×420; `band_color` color (primary_band); `slides` repeater max 6 {kicker
text "SINIRLI", title text "HAFTANIN FIRSATI", subtitle text "KAMPANYA BİTMEDEN YETİŞİN", product
product_picker (tek), image_override image 400×400, countdown countdown (units hours/minutes/seconds),
show_stock bool true, thumb_label text "4K GÖRÜNTÜLÜ ENDOSKOP", button {text "Hemen Al", link}};
`carousel` (autoplay false, dots mobile).

#### A9 `features_list` — Özellikler / Avantajlar Şeridi — yeni
T1 `homepage-3/features-list.php`, `_features-list.scss`; T2 v3. layout `container`.
| alan | tip | varsayılan |
|---|---|---|
| `layout` | select `horizontal` / `vertical` | horizontal |
| `columns` | select 3/4/5 | 5 |
| `border` | bool (1px #ddd, radius 8px, ayraçlar) | true |
| `items` | repeater max 6 | 5: ec-transport "Ücretsiz Kargo" / "2.500 TL üzeri"; ec-customers "%99 Olumlu" / "Müşteri yorumu"; ec-returning "14 gün" / "kolay iade"; ec-payment "Güvenli Ödeme" / "3D Secure"; ec-tag "Orijinal" / "Markalar" |
| `items[].icon` | icon (electro, allow_upload) | |
| `items[].strong_text` | text | |
| `items[].text` | text | |
| `items[].link` | link (opsiyonel) | none |
| `icon_color` | color | `#333e48` |

#### A10 `half_banners` — İki Banner (eski) — mevcut
Eski tip; şemaya taşınır: `items` repeater 2 {image rec 570×300, link, alt}. Galeride "Eski bloklar" altında.

#### A11 `video_banner` — Video Banner — mevcut
`video` image(accept video/*), `poster` image 1170×500, `title` text, `text` textarea, `button`
{text, link}, `autoplay` bool true, `muted` bool true, `loop` bool true.

#### A12 `text_block` — Metin Bloğu — mevcut
`title` text, `body` rich_text (marks tümü + link), `align` select, `max_width` number px 900.
(Eski HTML içerik `legacy_html` html alanına taşınır, yalnız süper-admin düzenler.)

#### A13 `instashop` — Atölyemizden (Instagram tarzı ızgara) — mevcut
`title` text "Atölyemizden", `items` repeater max 12 {image 600×600, link, alt}, `columns` select 4/6.

#### A14 `rotating_text` — Dönen Duyuru Şeridi (üst bar) — mevcut
category `ust_bar`, singleton. `messages` repeater {text, link}, `interval` ms 4000, `background`
color, `text_color` color, `position` select `above_topbar`/`below_topbar`. Akıştan çıkarılıp
Header'a verilir (bugünkü davranış); önizleme artık taslak değerini kullanır.

#### A15 `countdown_bar` — Geri Sayım Şeridi (üst bar) — mevcut
category `ust_bar`, singleton. `text` text, `countdown` countdown, `link` link, `background` color,
`text_color` color.

### GRUP B — Fırsatlar ve ürün ızgaraları

#### B1 ★3 `deals_tabs` — Özel Teklif + Ürün Sekmeleri — mevcut
Kaynak: T1 `deals-and-tabs.php`, `_section-onsale-product.scss`, `_products-carousel-tabs.scss`;
T2 index Deals-and-tabs, v6 "Catch Daily Deals". layout `container`. Varyant `v1` (vars.) / `v2`
(T2: 370px kart, 75×75 dairesel kazanç, 8 ürünlük sekme) / `discount_tabs` (T2 v6).

| alan | tip | varsayılan |
|---|---|---|
| `deal` | group | |
| `deal.enabled` | bool | true |
| `deal.mode` | select `auto` (en yüksek indirimli stoklu ürün) / `manual` | auto |
| `deal.product` | product_picker (show_if manual) | — |
| `deal.title` | text | "Özel Teklif" |
| `deal.title_override` | rich_text (boşsa ürün adı) | "" |
| `deal.image_override` | image rec 250×232 | null |
| `deal.savings` | group {`show` bool true, `label` text "Kazancınız", `mode` select auto/manual, `amount` text} | |
| `deal.stock` | group {`show` bool true, `sold_label` "Satılan:", `available_label` "Kalan:", `mode` select auto(stok verisinden)/manual, `sold` number 2, `available` number 26} | |
| `deal.countdown` | countdown | end = bugün+7 gün 23:59, units 4'ü, heading "Acele edin! Kampanya bitimine:" |
| `deal.border_color` | color | tema ana rengi (2px, radius 1.214em) |
| `deal.link` | link | ürün sayfası (otomatik) |
| `tabs` | repeater min 1 max 6 | 3: "Öne Çıkanlar" featured; "İndirimdekiler" discounted; "Çok Satanlar" best_sellers |
| `tabs[].label` | text | |
| `tabs[].source` | product_source | limit 6 |
| `default_tab` | number (0-indeksli) | 0 |
| `columns` | select 2/3/4 | 3 |
| `card` | select grid/grid_small | grid |
| `tab_animation` | select none/fade/slideInUp | fade |
| `tab_align` | select center/left | center |
| `_section.margin_bottom` | | 70 (5em) |

#### B2 ★4 `product_grid_212` — 2-1-2 Ürün Izgarası — mevcut
Kaynak: T1 `2-1-2-product-grid.php`, `_products-2-1-2.scss`; T2 index Products-4-1-4. layout `full_bleed`.
Varyant `2_1_2` (vars.) / `4_1_4` (T2: 4+1+4, büyük 564×520 + 3× 100×100 galeri, lightbox).

| alan | tip | varsayılan |
|---|---|---|
| `nav_mode` | select `links` (şablon: kategori bağlantıları) / `tabs` (JS ile ürün kümesini değiştirir) | tabs |
| `nav_items` | repeater max 10 | 1: "En İyi Fırsatlar" (discounted), sonra kök kategorilerden otomatik 6 öğe |
| `nav_items[].label` | text | |
| `nav_items[].link` | link (show_if nav_mode links) | |
| `nav_items[].source` | product_source limit 5 (show_if nav_mode tabs) | kategori |
| `nav_auto_categories` | group {`enabled` bool true, `max` number 6, `exclude` category_picker} | |
| `main_product_mode` | select `first_of_source` / `manual` | first_of_source |
| `main_product` | product_picker (show_if manual) | |
| `main_thumbnails` | bool (ürün galerisinden 3 küçük resim) | false (v1) / true (4_1_4) |
| `lightbox` | bool | false |
| `background` → `_section.background` | | `#f9f9f9` |
| `_section.padding` | | 58/58 |
| `_section.margin_bottom` | | 85 |
| `column_widths` | select `23_52_23` (lg %23.685/%52.63/%23.685) / `25_50_25` | 23_52_23 |

#### B3 `products_6_1` — 6+1 / 8+1 Çok Satanlar Izgarası — yeni
T1 `homepage-3/products-6-1.php`, `_products-6-1.scss`; T2 v3 Products-8-1. layout `full_bleed`.
`header` section_header (title "Çok Satanlar", right pills: "İlk 7" aktif + 3 kategori); `count`
select 6/8 = 6; `source` product_source (best_sellers, limit 7); `main_product_mode`/`main_product`
(B2 ile aynı); `main_image_height` number px 367; `thumbnails` number 3 (max 4);
`_section.background` #f9f9f9, padding 58/58.

#### B4 `deals_carousel` — Haftanın Fırsatları Karuseli — yeni
T1 `deals-of-the-week-carousel.php`; T2 v2 Deal, v7/v8/v11 "Deals of the Day". Varyant `gallery`
(T1: tek fırsat/slayt, 600×600 + küçük resimler) / `cards` (T2: kart karuseli + başlıkta geri sayım).

| alan | tip | varsayılan |
|---|---|---|
| `header` | section_header | title "Haftanın Fırsatları", tag h2, underline false (renk #343f49) |
| `prev_label` / `next_label` | text | "Önceki Fırsat" / "Sonraki Fırsat" |
| `deals` | repeater max 8 (show_if gallery) {product product_picker, title_override rich_text, main_image image 600×600, thumbnails repeater max 4 {image 180×180}, savings group, stock group, countdown countdown} | 2 öğe, auto (indirimli ilk 2) |
| `source` | product_source (show_if cards) | discounted, limit 9 |
| `header_countdown` | countdown (show_if cards) | |
| `border_color` | color | tema ana rengi |
| `carousel` | carousel | gallery: per_view hepsi 1, dots true, arrows none (metin bağlantılı); cards: {0:2,768:3,992:4,1200:4,1400:5} |

#### B5 `deals_week_limited` — Sınırlı Haftalık Fırsatlar — yeni
T2 v4/v11. `background` color #f5f5f5; `left.title` rich_text "Haftanın <strong>Sınırlı</strong>
Fırsatları"; `left.big_symbol` text "%"; `left.offer` group {prefix "KAZANCINIZ", value "70",
suffix "%", sub "İNDİRİM!"}; `left.button` {text "Alışverişe Başla", link}; `left.countdown`
countdown (hours/minutes/seconds); `source` product_source (discounted, 9); `carousel` per_view
{0:2,768:2,992:2,1200:3,1400:4,1480:5}, arrows side.

#### B6 `product_grid` — Ürün Izgarası — yeni
T2 v7 "Recommendation For You", v10 "Hot Products Today", v9 recently viewed (card image_only).
`header` section_header (title "Size Özel Öneriler", right link "Tümünü gör"); `source`
product_source (featured, 12); `columns` number responsive (6/4/2); `card` select grid/image_only/horizontal;
`pagination` bool false; `show_more_button` group {enabled false, text "Daha Fazla Göster"}.

#### B7 `banner_with_products_grid` — Banner + Ürün Izgarası — yeni
T2 v2/v4/v7/v10. `header` section_header (pills as_tab true); `side` select
`banner`/`featured_product`/`category_list`/`menu`/`none`; `side_position` select left/right;
`banner` {image rec 360×616, link}; `featured_product` product_picker; `category_links` repeater
{label, link} max 10; `tabs` repeater max 6 {label, source product_source limit 8}; `columns`
number responsive 4/3/2.

### GRUP C — Ürün karuselleri ve sütunlar

#### C1 ★5 `best_sellers` — Ürün Kartları Karuseli (Çok Satanlar) — mevcut
Kaynak: T1 `best-sellers-products-cards-carousel.php`, `best-seller-home-v2.php`,
`homepage-3/section-product-cards-carousel.php`, `_product-cards-carousel.scss`, `_product-card.scss`;
T2 index/v2/v3/v5. layout `container`.

| alan | tip | varsayılan |
|---|---|---|
| `header` | section_header | title "Çok Satanlar", right `pills`: "İlk 20" (aktif, span) + kök kategorilerden 3 |
| `pills_auto_categories` | group {enabled true, max 3} | |
| `pills_as_tabs` | bool (hap tıklanınca ürünler değişir; şablonda yalnız bağlantı) | true |
| `source` | product_source | best_sellers, limit 12 |
| `columns` | select 2/3/4 | 3 |
| `rows_per_slide` | number 1–3 | 2 |
| `card` | select horizontal/grid | horizontal |
| `carousel` | carousel; hide per_view (sayfa = columns×rows) | dots true, arrows `none` (pills varken), autoplay false, loop false |

Not: Şablonun `oldPrice/newPrice` ters geçirme hatası kopyalanmaz (indirimli fiyat `ins`, eski `del`).

#### C2 ★7 `product_slider` — Ürün Karuseli (Yeni Eklenenler / kategori / trend) — mevcut
Kaynak: T1 `recently-added-products-carousel.php`, `home-v2-categories-products-carousel.php`,
`_products-carousel.scss`; T2 index Recently Viewed + v2/v3/v5/v6/v7/v8/v9/v11. layout `container`.

| alan | tip | varsayılan |
|---|---|---|
| `header` | section_header | title "Yeni Eklenenler", right `arrows` |
| `source` | product_source | newest, limit 14 (şablon 8 — repo değeri korunur) |
| `card` | select grid_small/grid/horizontal | grid_small (6'lı) |
| `show_discount_badge` | bool | false |
| `carousel` | carousel | per_view {0:1,480:2,768:2,992:3,1200:6,1480:6}, dots true, arrows header, loop false, autoplay false, last_active_divider true |

Etkin şablon yapılandırması: electro.js'teki İLK init (6'lı). İkinci (1'li) yok sayılır.

#### C3 `products_carousel_tabs` — Sekmeli Ürün Karuseli — yeni
T1 `product-carousel-tab.php`, `homepage-3/products-carousel-tabs.php`; T2 v2/v3/v4/v5/v6/v9
(tabbed_products_carousel dahil). Varyant `centered` (T1 v2: 3'lü), `left` (T1 v3: 4'lü),
`pill_header` (T2 v5/v6: başlık + hap sekmeler + "Tümünü gör" + opsiyonel yan banner).
`header` section_header (tag sr-only "Ürün Sekmeleri"; pill_header'da görünür başlık); `tabs`
repeater max 8 {label, source product_source limit 7} = Öne Çıkanlar/İndirimdekiler/En Çok
Beğenilenler; `default_tab` 0; `display` select carousel/grid = carousel; `side_banner` {enabled
false, image 390×370, link, position left}; `card` grid; `carousel` per_view {0:1,480:1,768:2,
992:3,1200:3} (left: 1200:4), dots true, arrows none. Gizli sekmedeki karusel görünür olunca
yeniden ölçülmelidir.

#### C4 `products_carousel_with_image` — Arka Plan Görselli Ürün Karuseli — yeni
T1 `homepage-3/products-carousel-with-image.php`, `_products-carousel-with-image.scss`; T2 v3.
layout `full_bleed`. `background_image` image 1919×1026 (cover); `_section.background` #f9f9f9;
`side_image` image 665×616 (PNG şeffaf); `side_image_link` link; `image_position` select left/right
= left; `header` section_header (title "Lastik ve Balans Ekipmanları", right arrows); `source`
product_source (category, 7); `card` grid (beyaz iç arka plan); `carousel` per_view {0:1,992:2,
1200:2}, gutter 30, dots false, arrows header. `_section.padding` 58/0, margin_bottom 85.

#### C5 ★9 `product_columns` — Alt Ürün Sütunları (footer üstü) — mevcut
T1 footer widgets; T2 Footer-top-widget. layout `container`. `columns` repeater 3–4 {title text,
source product_source limit 3, show_rating bool, show_old_price bool true} = "Öne Çıkan Ürünler"
featured / "İndirimdeki Ürünler" discounted / "En Çok Beğenilenler" top_rated; `promo` {enabled
false, image 330×360, link} (yalnız ≥1480); `card` list_small (75×75). Bu blok sayfadaysa Footer'ın
kendi ürün bandı gizlenir (bugünkü `hideWidgets` davranışı korunur).

### GRUP D — Kategoriler, markalar, kenar çubuğu, içerik sayfaları

#### D1 ★8 `brands_carousel` — Marka Logoları Karuseli — mevcut
Kaynak: T1 `inc/footer/brands-carousel.php`, `_brands-carousel.scss`; T2 Brand Carousel. layout `container`.

| alan | tip | varsayılan |
|---|---|---|
| `source` | select `catalog` (logosu olan markalar) / `manual` | catalog |
| `brands` | repeater max 30 (show_if manual) {logo image rec 200×60, name text, link link (kind brand)} | — |
| `show_name_overlay` | bool (hover'da h4 ad) | true |
| `grayscale` | bool (gri, hover'da renkli; opacity .5→1) | true |
| `logo_max_height` | number px | 50 |
| `carousel` | carousel | per_view {0:1,480:1,768:2,992:3,1200:5}, arrows outer, dots false, rewind true, autoplay false, pause_on_hover true, drag false |
| `_section.margin_bottom` | | 85 (6.071em) |
| `show_on_all_pages` | bool (şablon: tüm sayfalarda footer üstü) | false |

#### D2 `home_list_categories` — Bu Ayın Popüler Kategorileri — yeni
T1 `homepage-3/home-list-categories.php`, `_home-list-categories.scss`; T2 v3.
`header` section_header (title "Bu Ayın Popüler Kategorileri"); `columns` select 3/4 = 3;
`categories` repeater max 12 {category category_picker (tek), image_override image 250×232
(150px gösterilir), name_override text, sub_mode select auto/manual = auto, sub_limit number 4,
sub_links repeater {label, link} (manual), see_all_text text "Tümünü gör"}; varsayılan 6 kök kategori otomatik.

#### D3 `category_icon_cards` — Kategori Kartları (döndürülmüş görsel) — yeni
T2 v4/v5/v8. `header` section_header (opsiyonel); `columns` responsive 5/3/2; `rotation` number 15;
`tiles` repeater max 12 {image 300×300, label, link}; `lead_banner` {enabled false, image 543×272,
label, link}; `tile_background` color #fff.

#### D4 `categories_icon_carousel` — İkonlu Kategori Karuseli — yeni
T2 v6/v8. `items` repeater max 16 {icon icon, label, link (category)}; `band_color` color; `carousel`
per_view {0:2,554:3,768:5,992:6,1200:8,1600:10}, arrows side, dots mobile.

#### D5 `categories_brands_card` — Markalar + Kategori Kutuları Kartı — yeni
T2 v11. `brands_label` "Markalar:"; `brands` brand_picker (6); `more_brands` {text "+ Tüm Markalar",
link}; `boxes` repeater max 8 {header_image 350×92, title, category category_picker, links repeater
max 6 {label, link}}; `overlap_hero` bool (negatif üst boşluk) true.

#### D6 `category_list_image_carousel` — Kategori Listesi + Büyük Görsel Karuseli — yeni
T2 v9. `header` section_header (right arrows); `slides` repeater max 5 {groups repeater max 2 {title,
links repeater max 7}, links repeater max 7, image 840×370, link}.

#### D7 `popular_search_tags` — Popüler Aramalar — yeni
T2 v8. `title` text "Popüler Aramalar"; `tags` repeater max 30 {label, link (kind search)};
varsayılan 10: "Lift", "Kompresör", "Lastik sökme", "Balans", "Kriko", "Hava tabancası",
"Yağ boşaltma", "Takım arabası", "Akü test", "Far ayar".

#### D8 Kenar çubuğu düzeni (T1/T2 home-v2) — yeni
Sayfa düzeyi ayar `page.layout` = `full` (vars.) / `left_sidebar` (§4.2). Sidebar blokları
yalnız `left_sidebar` düzeninde "Kenar Çubuğu" alanına eklenebilir (layout `sidebar`):
- `sidebar_image_ad` — {image 270×428, link}
- `sidebar_product_list` — {title "Son Eklenenler", source product_source (newest, 5), card list_small}
- `sidebar_products_carousel` — {title "Öne Çıkan Ürünler", source (featured, 4), carousel per_view 1, arrows header, dots false}
- `sidebar_features` — features_list şeması `layout: vertical` varsayılanıyla (ayrı key, aynı Render)
- `sidebar_blog_carousel` — {title "Blogdan", limit 4, carousel 1'li} (blog modülü yoksa galeride gizlenir)

#### D9 İçerik sayfası blokları (Hakkımızda tipi; ana sayfa dışı CMS sayfaları) — yeni, düşük öncelik
- `page_hero` — {background image 1920×600, title "Hakkımızda", text textarea, min_height 564}
- `info_cards` — repeater 3 {image 500×300, title, text}
- `team_grid` — repeater 6 {photo 300×300 (yuvarlak), name, role}
- `accordion` — {title "Size nasıl yardımcı olabiliriz?", items repeater {question, answer rich_text}}
- `text_columns` — repeater 4 {title, text}

---

## 4. Global alanlar (header / footer / tema) — framework işi

Global alanlar da AYNI şema formatıyla tanımlanır (`frontend/src/components/pageblocks/_global/<key>/`),
singleton olarak `settings` koleksiyonunda `id: "site_design"` belgesinde, aynı taslak/yayın
mekanizmasıyla saklanır. Sayfa Tasarımı'nda sol panelde **"Genel Alanlar"** sekmesi: Tema, Üst Bar,
Header, Dikey Menü, Footer… Menü öğeleri (ağaç yapısı) Menü Yönetimi'nde kalır; Sayfa Tasarımı
bunlara "Menüyü düzenle →" bağlantısı verir ve önizlemede menüyü gösterir.

### 4.1 `site_theme` — Tema
`primary_color` color #fed700; `primary_dark` color "" (boşsa -%8 açıklık otomatik); `preset`
select yellow/blue/red/orange/green/dark_green/flat_blue/gold/pink/black (T1 colors/*.css; ör. blue
#0787ea/#067ad4); `text_on_primary` select dark #333e48/white; `body_text` #333e48; `sale_color`
#df3737; `link_color` #0077d0; `font_family` select (Open Sans vars., Google Fonts listesi);
`base_font_size` number 14; `container_width` select 1200/1430; `card` group {show_wishlist true,
show_compare true, show_category true, show_old_price true, show_discount_badge false,
add_to_cart_text "Sepete Ekle"}; `reveal_default` (fadeIn on); `lazy_images` bool true;
`go_to_top` {enabled true, offset 400, position bottom-right}.

### 4.2 `site_page_layout` (sayfa başına) — `layout` full/left_sidebar, `sidebar_offset` auto.

### 4.3 `site_topbar` — Üst Bar
T1 `inc/header/top-bar.php`; T2 Topbar. `enabled` true; `style` select white/gray/primary/transparent;
`left_mode` select welcome/phone_email; `welcome_text` "Garaj ve oto servis ekipmanlarında
güvenilir adres"; `welcome_link`; `right_items` repeater {label, link, icon (ec-map-pointer,
ec-transport, ec-shopping-bag, ec-user), visible} = "Mağazalarımız", "Sipariş Takibi", "Mağaza",
"Hesabım" (mevcut `site_menus.topbar` öğelerinden taşınır); `hide_below` select lg/xl = lg.

### 4.4 `site_header` — Header
`variant` select v1 (vars.: logo+arama+ikonlar / dikey menü+ikincil menü) / v2 (logo+ana menü+destek /
sarı bant) / v3 (sarı geniş ana menü) / v3_full_color / v4…v11 (T2 kombinasyonları; ilk sürümde
v1, v2, v3, v3_full_color zorunlu, diğerleri sonra); `logo` group {image (SVG/PNG, kutu 175.748×42.52),
width, max_height, mobile_image, footer_image 156×37, favicon, link "/", alt}; `search` group
{enabled, placeholder "Ürün, marka veya kategori ara…", show_category_select true, all_label
"Tüm Kategoriler", style pill_bordered/pill_on_band/underline, button_color primary/dark,
live_suggestions true}; `icons` group {compare, wishlist, account_mobile, cart, cart_show_total,
badge_style primary/dark/white, mini_cart_dropdown, texts {view_cart "Sepeti Gör", checkout
"Ödeme", subtotal "Ara Toplam", empty "Sepetiniz boş"}, order}; `support` group {enabled false
(v2'de true), icon ec-support, label "Destek", phone, email}; `transparent_on_home` bool;
`mobile_band_primary` bool true; `sticky` bool false; `bottom_margin`.

### 4.5 `site_departments_menu` — Dikey "Tüm Kategoriler" menüsü
`enabled`; `title` "Tüm Kategoriler"; `title_icon` fa-list-ul; `header_style` primary_rounded/
primary_square/transparent_topline; `open_on_home` true; `open_elsewhere` false; `toggle_event`
click/hover; `width` 270; `overlay_hero` true (make-absolute); mega menü genişlikleri (540/600/900/450/277)
ve arka plan görseli (540×460) Menü Yönetimi'ndeki öğe düzeyinde (`megamenu` şeması).

### 4.6 `site_secondary_menu` / `site_primary_nav` — öğeler Menü Yönetimi'nde; burada: `enabled`,
`right_text` "2.500 TL üzeri ücretsiz kargo", `right_link`, `highlight_color` (#df3737), `position`.

### 4.7 Footer
- `site_footer_widgets` — `enabled` (ana sayfada `product_columns` varsa gizlenir) ve `columns` (C5 ile aynı şema).
- `site_newsletter` — `enabled`, `icon` ec-newsletter, `title` "Bültene Abone Olun", `marketing_text`
  rich_text "...ve <strong>ilk alışverişinize 250 TL indirim</strong> kazanın", `placeholder`
  "E-posta adresiniz", `button_text` "Abone Ol", `success_text` "Teşekkürler, aboneliğiniz alındı.",
  `error_text` "Lütfen geçerli bir e-posta girin.", `consent_text` rich_text (KVKK/İYS onayı),
  `background` color primary.
- `site_footer_contact` — `show_logo`; `call_us_icon` ec-support; `call_us_text` "Sorunuz mu var?
  7/24 arayın!"; `phones` repeater; `address_title` "İletişim Bilgileri"; `address` textarea;
  `email`; `social` repeater {network select, url, visible}. Telefon/e-posta/adres **tek kaynak**:
  `site_contact` (header destek bloğu da buradan okur).
- `site_footer_links` — `columns` repeater max 4 {title (boş olabilir — devam sütunu), links
  repeater {label, link}}; `auto_fill_from_categories` bool.
- `site_footer_bottom` — `copyright` rich_text "© {yıl} garajtek — Tüm hakları saklıdır"; `payment_logos`
  repeater {image (52px gösterilir), alt} veya `payment_band_image`; `extra_links` repeater (KVKK,
  Mesafeli Satış…); `etbis_qr` image; `background` #eaeaea.

Mevcut `FooterDesign.jsx` ve `site_menus.py` verileri bu şemalara geçişte (§6.4) taşınır; eski
ekranlar "Sayfa Tasarımı › Genel Alanlar"a yönlendirilir (Menü Yönetimi menü ağaçları için kalır).

---

## 5. Editör UX gereksinimleri

### 5.1 Yerleşim (`/admin/sayfa-tasarimi`)

```
┌ Üst çubuk: [Sayfa: Ana Sayfa ▾] [Masaüstü | Tablet | Mobil] [↶ Geri] [↷ İleri] [Revizyonlar]
│            durum: "Taslak — 3 değişiklik, 12 sn önce otomatik kaydedildi"  [Önizle ↗] [Yayınla]
├────────────── 360px ──────────────┬──────────────── esnek ────────────────┐
│ Sekmeler: [Bloklar] [Genel Alanlar]│  CANLI ÖNİZLEME (iframe, gerçek vitrin)│
│ Blok listesi (sürükle-bırak):     │  - seçili blok sarı çerçeve + etiket    │
│  ⋮⋮ ★ Ana Slider   👁 🖥📱 ⧉ 🗑  │  - bloğa tıkla → soldaki form açılır     │
│  ⋮⋮ Reklam Kutuları …             │  - blok arası "+ Blok ekle" çizgisi     │
│ [+ Blok Ekle] → galeri             │  - cihaz genişliği: 1440 / 1024 / 390  │
│ Seçili blok formu (sekmeli,        │    (ölçeklenmiş, gerçek viewport)       │
│  şemadan otomatik)                 │                                        │
└────────────────────────────────────┴────────────────────────────────────────┘
```

Gereksinimler:

1. **Canlı önizleme**: iframe `/onizleme/sayfa/home?token=…` — vitrinin GERÇEK `Home` sayfası,
   gerçek Header/Footer ve `registry`'deki `Render.jsx` bileşenleri. Panel taslağı
   `postMessage({type:"pd:draft", layout, global})` ile gönderir (her değişiklikte, 150 ms debounce);
   iframe yeniden yüklenmeden yeniden render eder. Üst barlar ve global alanlar da taslaktan okunur.
   iframe → panel: `pd:select {blockId}`, `pd:ready`, `pd:height`. Önizleme rotası yalnız geçerli
   admin token'ı ile açılır, `noindex`.
2. **Sürükle-bırak sıralama** (liste ve önizlemede blok tutamacı); klavye ile ↑/↓.
3. **Çoğalt** (yeni `id`, repeater öğelerine yeni `_id`), **sil** (onaylı, geri alınabilir),
   **gizle/göster** (`is_active`), **cihaz görünürlüğü** (🖥 tablet 📱 ayrı ikonlar),
   **zamanlama** (başlangıç/bitiş; listede ⏱ rozeti).
4. **Taslak / yayın**: Her değişiklik taslağa otomatik kaydedilir (3 sn debounce,
   `PUT /api/page-design/{page}/draft` + `If-Match: rev`). "Yayınla" → `POST /publish` atomik.
   Çakışma (başka admin) → "Başka bir yönetici değişiklik yaptı — birleştir / üzerine yaz / vazgeç".
   "Taslağı at" → yayındaki sürüme dön.
5. **Geri al / ileri al**: istemci 100 adım (Ctrl+Z / Ctrl+Shift+Z); **revizyonlar**: her yayında
   sunucu revizyonu (son 50), listede tarih + yönetici + özet ("2 blok değişti"), "Bu sürümü
   önizle", "Bu sürüme geri dön" (taslağa yükler).
6. **Görsel yükleme**: sürükle-bırak; önerilen ölçü ipucu ve kalite uyarısı (küçükse sarı,
   oran farklıysa "kırpılacak"); kırpma aracı (önerilen orana kilitli seçenek); **odak noktası**
   (tıkla → `focal`, vitrin `object-position`); alt metin zorunlu uyarısı; mobil görsel opsiyonu;
   medya kütüphanesinden yeniden kullanma; istemci sıkıştırma (2400 px, JPEG/WebP 0.86).
7. **"Şablon varsayılanına sıfırla"** — blok başına (onaylı; geri alınabilir) ve alan başına (alan
   yanında ↺ simgesi, değer varsayılandan farklıysa görünür). Listede "değiştirildi" noktası.
8. **Blok galerisi** ("+ Blok Ekle"): kategoriler (Slider, Banner, Ürün, Fırsat, Kategori, Marka,
   İçerik, Kenar Çubuğu, Üst Bar); her kart `thumb.png` (şablondaki bölümün ekran görüntüsü), ad,
   kısa açıklama, "şablonda: v1 ana sayfa, v3…" etiketi, varyant seçimi; eklenen blok
   **varsayılanlarla dolu** gelir (boş blok yok), seçili konuma eklenir.
9. **Tip değiştirilemez**; "Görünüm/Varyant" değiştirilebilir (değişmeyen alanlar korunur, onay
   ile varyant yaması uygulanır).
10. **Doğrulama**: alan hataları satır içi kırmızı; yayın butonu hata varken pasif + hata listesi
    ("Ana Slider › Slayt 2 › Düğme bağlantısı boş").
11. **Ürün kaynağı önizlemesi**: kaynak alanında "eşleşen 14 ürün" + ilk 6 küçük resim.
12. **Sayfa seçici**: Ana Sayfa (ilk sürüm); şema `allowed_pages` ile ileride CMS sayfaları.
13. **Erişilebilirlik**: tüm kontroller klavye ile; Türkçe aria etiketleri.
14. Eski "Gelişmiş İçeriği Düzenle" modalı ve şematik önizleme kaldırılır.

### 5.2 API (framework)

| Uç | Açıklama |
|---|---|
| `GET /api/page-design/{page}` | admin: `{published:{rev,blocks,global}, draft:{rev,base_rev,blocks,global}|null}` |
| `PUT /api/page-design/{page}/draft` | taslağı yaz (tüm düzen; şema doğrulamalı, `If-Match`) |
| `DELETE /api/page-design/{page}/draft` | taslağı at |
| `POST /api/page-design/{page}/publish` | taslağı doğrula → `page_layouts` yayın belgesini tek yazımla değiştir, revizyon ekle, `page_blocks` aynasını güncelle |
| `GET /api/page-design/{page}/revisions` / `GET …/revisions/{rev}` / `POST …/revisions/{rev}/restore` | geçmiş |
| `GET /api/page-design/schemas` | tüm şemalar + varsayılanlar (panel için; build içindekiyle aynı) |
| `POST /api/page-blocks/resolve-products` | ürün kaynakları |
| `GET /api/page-blocks?page=home` (public, uyumlu) | yayındaki, aktif, zamanı gelmiş bloklar; `is_active=false` ASLA dönmez |
| `GET /api/site-design` (public) | yayındaki global alanlar |

Depolama: `page_layouts` koleksiyonu `{id:"home:published"|"home:draft", page, rev, base_rev,
blocks[], global{}, updated_at, updated_by}`; `page_layout_revisions` `{id, page, rev, blocks,
global, published_at, published_by, summary}` (son 50). `page_blocks` yayında ayna olarak tutulur
(eski uçlar ve diğer modüller bozulmasın); `.to_list(50)` sınırı kalkar.

---

## 6. Varsayılan ana sayfa ve canlı veritabanı geçişi

### 6.1 Varsayılan ana sayfa (v1.0 `home.html` / `pages/home.php` sırası)

| # | type | variant | iç ad |
|---|---|---|---|
| 1 | `hero_slider` | v1 | Ana Slider |
| 2 | `ads_block` | v1 | Reklam Kutuları |
| 3 | `deals_tabs` | v1 | Özel Teklif ve Ürün Sekmeleri |
| 4 | `product_grid_212` | 2_1_2 | Kategori Fırsatları (2-1-2) |
| 5 | `best_sellers` | — | Çok Satanlar |
| 6 | `full_banner` | image | Tam Genişlik Banner |
| 7 | `product_slider` | — | Yeni Eklenenler |
| 8 | `brands_carousel` | — | Markalar (şablonda `#content` dışı, footer üstü) |
| 9 | `product_columns` | — | Alt Ürün Sütunları (şablonda footer widget'ları) |

Global: header v1 (dikey menü ana sayfada açık, slider üzerine biner), topbar, footer (bülten,
iletişim, 3 bağlantı sütunu, telif + ödeme logoları). `default_blocks()` (Python) ve
`DEFAULT_HOME_BLOCKS` (JS) artık elle yazılmaz; ikisi de `defaults.json` dosyalarından üretilir
(`backend/pageblocks.default_home()`, `registry.defaultHome()`).

### 6.2 Geçiş kuralları (idempotent, `migrations.page_design_v2` anahtarı)

Çalışma: uygulama başında bir kez (kilitli), önce **yedek**: `page_blocks` tümü
`page_layout_revisions`'a `rev: 0, summary: "Geçiş öncesi yedek"` olarak yazılır.

Her `page_blocks` satırı için (`page` boşsa `home` kabul):

1. **Tip eşleme** (anahtarlar korunur — yeniden adlandırma yok): `hero_slider, ads_block, deals_tabs,
   product_grid_212, best_sellers, full_banner, product_slider, brands_carousel, product_columns,
   half_banners, text_block, video_banner, instashop, rotating_text, countdown_bar` → aynı key.
   Bilinmeyen tip → `settings._legacy = true` ile olduğu gibi korunur, vitrinde render edilmez,
   panelde "Desteklenmeyen eski blok" uyarısıyla gösterilir (silme sahibin kararı).
2. **Varsayılan birleştirme**: `settings = deepMerge(default_settings(type, variant), eski_settings_dönüştürülmüş)`
   — yöneticinin girdiği HER değer kazanır; yalnız eksik alanlar varsayılandan dolar. Ancak
   **"el değmemiş"** (`_pristine()` mevcut tanımı: `updated_at` yok, görsel yok, metin yok,
   layout etiketi `electro_home_v1`) bloklarda varsayılan metinler tam uygulanır.
3. **Alan dönüşümleri**:
   - `hero_slider`: `images[i]` → `slides[i].background.url`, `img_dims[i]` → `w,h`;
     `mobile_images[i]` → `slides[i].background.mobile_url`; `captions[i]` {title, subtitle,
     price, cta, link…} → slayt alanları (`cta`→`button.text`, `link`→`button.link` `{kind:url}`);
     `links[i]` → `button.link` (caption linki yoksa); `slide_schedule[i]` → `slides[i]._schedule`;
     `style` → `_variant` (`electro`→`v1`). Paralel diziler bu adımda birleştirilir; uzunluk
     farklıysa `images` uzunluğu esas alınır.
   - `ads_block`: `items[].pre/strong/post` → `text` = `pre<br><strong>strong</strong> post`;
     `cta` → `action_type: link` + `action_text`; `upto` → `action_type: upto` + `action_value`;
     `image` (string) → `{url}`; `link` → `{kind:"url", url}` (kategori yolu tanınırsa `kind:category`).
   - `deals_tabs`: `special.mode/title` → `deal.mode/title`; `tabs[].source` (string) →
     `{kind: map(source), limit: 6}` (`popular` → `best_sellers`).
   - `product_grid_212`: `first_label/first_source` → `nav_items[0]`; `category_ids` →
     `nav_auto_categories` kapalı + manuel nav öğeleri; `max_tabs` → `nav_auto_categories.max`.
   - `best_sellers`: `first_label` → `header.pills[0].label`; `category_ids/max_tabs` → hap öğeleri.
   - `product_slider`: `source/limit/category_ids/product_ids` → `source` nesnesi; `title`
     (blok kökü) → `header.title` **yalnız** `header.title` boşsa (eski bloklarda başlık köktedir);
     `category_slug` (ölü alan) → `category_ids` çözümlenebilirse, değilse atılır.
   - `full_banner`, `half_banners`, `instashop`, `brands_carousel`: `images[i]`/`links[i]` →
     ilgili `image`/`items[i]` / `brands[i]` (brands_carousel'de görsel varsa `source: manual`).
   - `product_columns`: `columns[].source` string → nesne (limit 3).
   - `show_desktop`/`show_mobile` → `_visibility.desktop`/`mobile` (+ `tablet = show_desktop`);
     `settings.schedule` → `_visibility.schedule`.
4. `settings._v = 2`; `template_default_hash` hesaplanır; `updated_at` DEĞİŞTİRİLMEZ (pristine
   tespiti bozulmasın).
5. Sonuç `page_layouts` `home:published` belgesine (sıra `sort_order`) yazılır; taslak yok.
6. `site_menus` (topbar, departments, center, hamburger, mobile) ve `FooterDesign` verisi
   (`columns, newsletter, social, copyright, payment_band_url`) → `site_design` global belgesine
   aynı kurallarla (yönetici değeri kazanır) taşınır; eski uçlar bir sürüm boyunca yeni belgeden
   okuyup yazar (geri uyum).
7. Doğrulama hatası veren blok atlanmaz: `settings._migration_errors` ile korunur, panelde uyarı.
8. Geri dönüş: `POST /api/page-design/home/revisions/0/restore`.
9. `POST /seed-default-home` → 410; `install-default-home` yeni varsayılan üreticiyi kullanır.

Geçiş testleri (`backend/tests/test_page_design_migration.py`): bugünkü canlı DB'den alınmış
anonim örnek blok dökümleri (fixture) → dönüşüm → (a) hiçbir yönetici değeri kaybolmamış,
(b) şema doğrulaması geçer, (c) idempotent (iki kez çalıştırma aynı sonuç).

---

## 7. Uygulama grupları (paralel ajanlar)

Kural: Her grup ajanı YALNIZ `frontend/src/components/pageblocks/<key>/` klasörlerine ve
`backend/pageblocks/schemas/<key>.*.json` kopyalarına (script ile) dokunur. `_shared`, `_fields`,
`_global`, `registry.js`, `Home.jsx`, `PageDesign.jsx`, backend uçları framework'ündür. Ortak
bileşen ihtiyacı → framework ajanına not (veya `_shared`'deki mevcut bileşeni kullan). Her blok
için: `schema.json`, `defaults.json`, `Render.jsx`, `thumb.png`, `Render.test.jsx`; ve Playwright
görsel karşılaştırması (`e2e/pageblocks/<key>.spec.js`: varsayılanlarla render ↔ şablon HTML
bölüm ekran görüntüsü, 1440 ve 390 genişlikte; eşik %2 piksel farkı — görsel yer tutucular
maskelenir). Grup ajanları framework iskeleti merge edildikten SONRA başlar.

| Grup | Bloklar | Kapsam özeti |
|---|---|---|
| **A — Slider, banner, içerik** | hero_slider, ads_block, full_banner, banner_two_columns, banner_grid_text_image, banner_mosaic, hero_tabs, deal_slider, features_list, half_banners, video_banner, text_block, instashop, rotating_text, countdown_bar | Katman animasyonları (fadeInDown-N gecikmeleri), full-bleed, odak noktalı arka planlar, eski blokların şemaya taşınması |
| **B — Fırsatlar ve ızgaralar** | deals_tabs, product_grid_212, products_6_1, deals_carousel, deals_week_limited, product_grid, banner_with_products_grid | Geri sayım/stok/kazanç rozeti, büyük ürün + küçük resim, sekmeli ızgaralar |
| **C — Ürün karuselleri** | best_sellers, product_slider, products_carousel_tabs, products_carousel_with_image, product_columns | Karusel davranış grubu (per_view, last-active, başlık okları), sekme içi karusel yeniden ölçme, kart varyantları |
| **D — Kategori, marka, kenar, içerik** | brands_carousel, home_list_categories, category_icon_cards, categories_icon_carousel, categories_brands_card, category_list_image_carousel, popular_search_tags, sidebar_image_ad, sidebar_product_list, sidebar_products_carousel, sidebar_features, sidebar_blog_carousel, page_hero, info_cards, team_grid, accordion, text_columns | Kategori/marka seçicileri, ikon galerisi, kenar çubuğu düzeni blokları, CMS içerik blokları |

Öncelik sırası her grupta: önce ★ varsayılan ana sayfa blokları (A: hero_slider, ads_block,
full_banner; B: deals_tabs, product_grid_212; C: best_sellers, product_slider, product_columns;
D: brands_carousel), sonra diğerleri.

---

## 8. Framework (global) işi — tek ajan, gruplardan önce

1. **Şema altyapısı**: `pageblocks/registry.js` (otomatik toplama), şema JSON-Schema meta
   doğrulayıcı (`scripts/validate_block_schemas.py` — her `schema.json`'ın §2 formatına uyduğunu ve
   `defaults.json`'ın şemaya uyduğunu test eder), `scripts/sync_block_schemas.py` (+ `--check`).
2. **`_fields/SchemaForm`** ve tüm widget'lar (§2.3 tablosu), sekmeler, `show_if`, responsive
   değer düzenleyici, alan başına "varsayılana sıfırla".
3. **`_shared` vitrin bileşenleri**: `SectionHeader`, `ProductCard` (7 varyant), `BlockCarousel`
   (`Carousel.jsx`'i `carousel` değeriyle sarar; min-width kırılımları; fade geçiş; last-active),
   `Countdown` (mevcut `electro/Countdown.jsx` genişletilir: birimler, etiketler, expiry),
   `StockBar`, `SavingsBadge`, `SmartImage` (focal, mobil kaynak, lazy, yer tutucu), `SmartLink`,
   `RichText` (güvenli), `useProductSource` (resolve-products + 60 sn TTL; önizlemede önbelleksiz),
   `BlockFrame` (ortak `_section/_visibility/_reveal` sarmalayıcısı: arka plan, boşluk, full-bleed,
   cihaz sınıfları 1200/768 kırılımlı, waypoint-benzeri IntersectionObserver reveal).
4. **Renderer**: `Home.jsx` → `PageRenderer` (registry'den `Render` seçer, `BlockFrame` ile sarar,
   container gruplama mantığı korunur, `sidebar` düzeni). Bilinmeyen/legacy tip render edilmez.
5. **Backend**: `backend/pageblocks` (yükleyici, doğrulayıcı, varsayılan, sanitize), §5.2 uçları,
   `page_layouts`/`page_layout_revisions`, public GET güvenlik düzeltmesi (inaktif bloklar
   dönmez), zamanlama süzmesinin repeater öğe düzeyine taşınması, `resolve-products`,
   `seed-default-home` kaldırma, `.to_list(50)` sınırı.
6. **Geçiş** (§6.2) + testleri + yedek/geri dönüş.
7. **Editör** (`PageDesign.jsx` yeniden yazımı, §5.1): liste + galeri + form + iframe önizleme +
   postMessage köprüsü + otomatik taslak + yayın + revizyonlar + geri al/ileri al + çakışma.
   Galeri küçük resimleri için `thumb.png` yoksa yer tutucu.
8. **Önizleme rotası** `/onizleme/sayfa/:page` (admin token, noindex, `pd:*` mesajları, tıkla-seç
   çerçevesi, blok arası "+").
9. **Global alanlar** (§4): `_global/*` şemaları ve Header/Footer/Topbar/Logo/Newsletter'ın
   şemadan okuması; `site_design` belgesi; `site_contact` tek kaynak; tema renkleri CSS
   değişkenleri (`--primary`, `--primary-dark`, …) `.electro` kapsamında; renk ön ayarları;
   FooterDesign ve site_menus verilerinin taşınması; Menü Yönetimi bağlantıları.
10. **Demo içerik** (`demo_content.py`): yeni alan yollarına (`slides[].background`, `items[].image`
    …) göre güncellenir.
11. **Eski kodun temizliği**: `HomeBlockFields.jsx`, `lib/homeLayout.js` (DEFAULT_HOME_BLOCKS →
    registry), `pageDesignDraft.js` save plan, PageDesign içindeki satır içi formlar.
12. **Testler / CI**: şema senkron testi, doğrulayıcı birim testleri, geçiş testleri, Playwright:
    (a) panelde alan değiştir → iframe'de anında görünür, (b) yayınla → vitrinde görünür,
    (c) önizleme ve vitrin ekran görüntüsü piksel eşit, (d) sıfırla → şablon görünümü,
    (e) geri al/revizyon geri yükleme.

## 9. Eşdeğerlik denetim listesi (son kabul)

Her blok için "vitrinde görünen her öğe → şema alanı" eşleme tablosu `Render.test.jsx` içinde
`data-pd-field="slides.0.title"` öznitelikleriyle doğrulanır: `Render.jsx` panelden gelen her
metin/görsel/bağlantıyı basan DOM düğümüne `data-pd-field` yazar (önizlemede çift tıklayınca o
alan formda odaklanır). Test: render edilen DOM'daki tüm görünür metin düğümlerinin ya
`data-pd-field` taşıdığı ya da ürün/kategori verisinden geldiği (`data-pd-data`) doğrulanır —
sabit kodlu metin bulunursa test kırılır. Bu, sahibin "%100 uyumluluk" şartının otomatik
güvencesidir.
