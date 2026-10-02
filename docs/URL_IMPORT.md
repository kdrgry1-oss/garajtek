# URL'den Ürün Aktar (geçici demo)

> **Uyarı:** Bu araçla aktarılan içerik ve görseller kaynak sitelere aittir; yalnız geçici demo
> amaçlı kullanın, canlı satıştan önce kaldırın.

Müşteriye mağazayı gerçek ürünlerle dolu göstermek için referans mağazaların (ör.
`https://www.grayzer.net/kategori/liftler`, `https://www.algikitelli.com.tr/`) ürün ya da kategori
sayfalarını okuyup ürünleri mağazaya **demo** olarak ekler. Sayfaları **sunucu** okur (tarayıcınız
değil); geliştirme ortamı bu sitelere erişemese de canlı sunucu erişebilir.

## Kullanım

1. Panel › **Katalog › URL'den Ürün Aktar**.
2. Kutuya her satıra bir adres yapıştırın. Ürün sayfası da olur, kategori/liste sayfası da (liste
   sayfalarında sonraki sayfalar da taranır).
3. Seçenekler:
   - **Hedef kategori:** *Otomatik eşle* kaynak sayfanın kırıntısı (Anasayfa › Liftler › …) ve ürün
     adından en uygun garaj kategorisini bulur (üst kategoriler de eklenir). Eşleşmezse listeden
     seçtiğiniz kategori yedek olarak kullanılır. *Hepsini seçilen kategoriye* her ürünü aynı yere koyar.
   - **Kategori sayfası başına en çok ürün:** varsayılan 30 (iş başına üst sınır 200 ürün).
   - **Fiyat çarpanı** (ör. `0,95`) ya da **sabit fiyat** — isteğe bağlı.
   - **Görselleri indir:** ürün başına en çok 6 görsel indirilir, WebP'ye çevrilip (en çok 1600 px)
     kendi depomuza yazılır — kaynak siteye bağlantı (hotlink) verilmez.
   - **Hemen yayınla:** açık değilse ürünler taslak kalır. Fiyatı bulunamayan ürün her zaman taslak kalır.
   - **Demo olarak işaretle:** zorunlu, kapatılamaz.
4. **İçe Aktarmayı Başlat** — ilerleme canlı görünür: bulunan / eklenen / güncellenen / başarısız /
   atlanan sayıları, her adresin sonucu ve her ürün için düzenleme linki. Sunucu kaynak siteye
   saniyede en çok 1 istek atar; 30 ürünlük bir kategori görsellerle birlikte birkaç dakika sürebilir.
5. Aynı adresi yeniden aktarmak yeni ürün açmaz; mevcut demo ürünü günceller (eski görseller silinir).

Her aktarılan ürün: `demo` etiketli, **arama motorlarına kapalı** (`noindex,nofollow`), sitemap.xml ve
XML ürün feed'lerinde **yer almaz**; ürün sayfasında ana görselin altında küçük bir
"Görsel: kaynak-site" notu görünür. Stok varsayılan 10'dur (kaynakta "stokta yok" ise 0). Stok kodu
yoksa `IMP-` ile başlayan bir kod üretilir. Teknik tablo satırları bilinen alanlara (kapasite, motor
gücü, voltaj…) eşlenir; eşlenemeyenler "Ek Teknik Özellikler"e yazılır. Ürünleri panelden normal
ürün gibi düzenleyebilirsiniz.

## Kaldırma

İkisinden biri yeterli (ikisi de yalnız aktarılan ürünleri ve indirilen görselleri siler, başka hiçbir
şeye dokunmaz):

- **Katalog › URL'den Ürün Aktar › İçe aktarılanları sil**
- **Tasarım › Sayfa Tasarımı › Demo İçerik › Kaldır** (yerleşik demo içerikle birlikte)

**Canlı satışa başlamadan önce mutlaka kaldırın.**

## Sorun giderme

- *"İç/özel ağ adresi engellendi"*, *"Standart dışı port"*: güvenlik gereği yalnız internetteki
  http/https adresleri (80/443) okunur.
- *"HTTP 403/429"*: kaynak site isteği reddetti; bir süre sonra daha az adresle tekrar deneyin.
- *"Ürün sayfası değil"*: sayfada ürün adı/fiyatı bulunamadı (kampanya, blog vb. sayfa).
- *"Görsel atlandı"*: görsel jpg/png/webp değil, 5 MB'tan büyük ya da çok küçük (logo/ikon).
- Kategori yanlış eşlendiyse ürünü panelden düzenleyin ya da *Hepsini seçilen kategoriye* ile
  yeniden aktarın.

## Teknik notlar (geliştirici)

- Kod: `backend/url_import/` (fetcher, parser, sanitize, specs_map, catmap, job), uçlar
  `backend/routes/url_import.py` (`/api/admin/url-import/*`, yetki `products.url_import`), sayfa
  `frontend/src/pages/admin/UrlImport.jsx`.
- İş uygulama sürecinde arka plan görevi olarak çalışır (localdb tek-süreç kuralı); aynı anda tek iş.
  Sunucu yeniden başlarsa yarım iş "Yarım kaldı" görünür; tekrar başlatmak güvenlidir (dedupe).
- `URL_IMPORT_ALLOW_PRIVATE=1` **yalnız yerel test içindir** (loopback/özel IP ve standart dışı porta
  izin verir). Üretimde **asla** ayarlamayın; varsayılan kapalıdır.
