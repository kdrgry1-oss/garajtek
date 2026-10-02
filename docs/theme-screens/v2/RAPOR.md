# Vitrin Teması — Düzeltme Raporu (v2)

Şikâyet: *"temayı adam akıllı kur, tüm siteye bok gibi açılıyor, sitenin her yeri"*.
Hedef: vitrinin ThemeForest Electro HTML şablonuyla (v2.0 bileşenleri, v1.0 ana sayfa yapısı)
**her sayfada ve her genişlikte** birebir görünmesi, gerçek veriyle.

Bu rapordaki tüm kontroller **gerçek backend** (yerel SQLite, gerçek yükleme uç noktası,
MEDIA_DIR yerel depo) + **üretim derlemesi** (nginx gibi aynı-origin /api vekili) ile
Playwright (Chromium) üzerinde 1440 / 1280 / 1024 / 768 / 390 px genişliklerde yapıldı;
şablonun orijinal HTML sayfaları da aynı genişliklerde çekilip sayfa sayfa karşılaştırıldı.

---

## 1. Kök nedenler (sitenin her yerinin bozuk görünmesi)

| # | Kök neden | Etkisi | Çözüm |
|---|-----------|--------|-------|
| 1 | Tema CSS'i **budanıyordu** (purge: yalnız kaynakta geçen sınıflar tutuluyordu, 168 KB) | JS ile eklenen durum sınıfları (show/active/open…), CMS sayfalarındaki Bootstrap sınıfları, ızgara/yardımcı sınıflar, responsive varyantlar kayıp → sayfalar yer yer stilsiz | Budama kaldırıldı; şablonun **tam** CSS'i (`.electro` kapsamlı, küçültülmüş, ~100 KB gzip) yükleniyor. `scripts/purge-electro-css.js` silindi. |
| 2 | **Tailwind preflight** (CSS reset) tema öğelerine de uygulanıyordu | Görseller `display:block` (ortalanmıyor), tüm kenarlıklar 0/solid, liste girintileri/düğme varsayılanları sıfır → tema "kırık" | Preflight `.electro` **dışına** kapsamlandı (`scripts/tailwind-scoped-preflight.js`, özgüllük 0). `index.css`'teki genel `* {margin:0;padding:0}` ve eski `.btn-primary/.btn-secondary` da temaya sızmıyor. |
| 3 | Eski (giyim) tema kuralları | `storefront.css` form/düğme kuralları, `.sf-page h1` rengi, statik sayfa satır yüksekliği temanın üzerine yazıyordu | İlgili kurallar `.electro` dışına kapsamlandı / kaldırıldı; eski "uyum" yamaları silindi. |
| 4 | **Önbellek**: `electro.css?v=2` sabit sorgu | Tema güncellense de tarayıcı/Cloudflare eski CSS'i (1 gün) gösterebiliyordu | `?v=<içerik özeti>` (craco.config.js, her derlemede otomatik). |
| 5 | Yazı tipi Google Fonts'a bağlıydı | Font gecikmesi/engelinde sistem fontu | Open Sans (latin + latin-ext → Türkçe karakterler) `public/electro/fonts` altından, kendi sunucumuzdan. |
| 6 | Bazı sayfalar hiç tema kullanmıyordu | Sipariş Tamamlandı, Hesabım panelleri, iade/ödeme bildirimi, şifre sıfırlama eski siyah-beyaz giyim temasında; iade sayfalarında header/footer bile yoktu | Bu sayfalar tema bileşenlerine taşındı (bkz. §3). |

## 2. CSS yükleme stratejisi (yeni)

- `public/electro/electro.css` — şablonun tam CSS'i, tüm seçiciler `.electro` altında; yalnız
  vitrin rotalarında (`/admin` hariç) `<head>`'de parser-inserted yüklenir (FOUC yok).
  Yeniden üretmek: `node frontend/scripts/build-electro-css.js <şablon/2.0 klasörü>`.
- Tailwind: `corePlugins.preflight=false` + kapsamlı preflight eklentisi → admin ve ödeme
  (Tailwind) ekranları **aynı** kalır, tema ise orijinal HTML'deki gibi Bootstrap reboot +
  tarayıcı varsayılanlarıyla çalışır. Admin giriş ekranı karşılaştırması: `admin-giris-1440.jpg`
  (tek fark: "MAĞAZA" yer tutucu logosu yerine GarajTek logosu).
- Ödeme sayfası (`/odeme`, Shopify düzeni) kendi `.gt-checkout` kapsamındadır; 1440 ve 390'da
  kontrol edildi, global CSS bozulması yok (`odeme-1440.jpg`, `odeme-390.jpg`).
- Konsol / 404 kontrolü: tüm sayfalarda CSS, font (font-electro, Font Awesome, Open Sans) ve
  görsel isteklerinde 404 yok; ikon glifleri kutu olarak görünmüyor.

## 3. Bulunan ve düzeltilen hatalar

**Genel / tüm sayfalar**
1. Tema CSS'inde eksik sınıflar (budama) → tam CSS.
2. Tailwind preflight'ın temayı bozması (görsel hizası, kenarlıklar, listeler, düğmeler).
3. `storefront.css` ve `index.css`'ten sızan eski tema kuralları.
4. Sabit `?v=2` önbellek anahtarı → içerik özeti.
5. Google Fonts bağımlılığı → kendi sunucumuzdan Open Sans (Türkçe karakterler dahil).
6. `public/logo.png|webp` "MAĞAZA" yer tutucusuydu (ödeme başlığı, admin girişi) → GarajTek logosu.
7. Footer ödeme alanında metin rozetleri → iyzico'nun resmi **"iyzico ile Öde" + Mastercard / Visa / American Express / Troy** logo bandı (görseller iyzico'nun kendi entegrasyon paketlerinden; retina için yüksek çözünürlük). Ödeme sayfasında kartla ödemede "Şimdi öde" altında da gösteriliyor. Farklı bir bant görseli Footer Tasarımı'ndan verilebilir.
8. Footer varsayılan sütunlarında giyim mağazasından kalma "Elbise/Pantolon/Ceket/Aksesuar" bağlantıları ve "Yeni koleksiyonlar" bülten metni → garaj ekipmanına uygun bağlantılar/metin.
9. Footer alt şeridine geliştirici künyesi: "Designed by" + roofcommerce logosu (https://roofcommerce.com.tr/, yeni sekme). Logo dosyası `frontend/public/roofcommerce-logo.svg` (yer tutucu kelime logo; gerçek logo aynı adla ya da `roofcommerce-logo.png` olarak konabilir).
10. Panelde görünen "Emergent" kalıntıları (kampanya e-posta şablonundaki örnek alan adı, AI anahtar etiketi) kaldırıldı. Kullanıcıya görünen hiçbir yerde "Electro" yazmıyor (yalnız iç CSS sınıf/dosya adları).

**Ana sayfa**
11. Şablonun **v1.0 ana sayfa yapısı** kuruldu: tam genişlik slider (1920×466) + solda açık "Tüm Kategoriler", 3'lü reklam bannerları (410×281, 410×281, 714×486), Günün Fırsatı + Öne Çıkanlar/İndirimdekiler/Çok Satanlar, 2-1-2 kategori ızgarası, Çok Satanlar karuseli, tam banner (1170×207), Son Eklenenler, Markalar, alt ürün sütunları.
12. Slider yazısı sarı görünüyordu (tüm slayt `<a>` içindeydi → bağlantı rengi) → koyu metin, buton `stretched-link`.
13. Günün Fırsatı kartı 1000 px'lik ürün görseliyle sayfa genişliğine taşıyordu → sabit 370/300 px kart, görsel kutusunda `object-fit: contain`.
14. Sekme başlıkları alt satıra kırılıyordu / mobilde sola kesiliyordu → tek satır, mobilde kaydırılabilir.
15. Tablet (768/1024): reklam kartı yazıları kelime ortasından bölünüyordu ("FIRSATLA R"), fiyatlar sepete-ekle düğmesine biniyordu → yerleşim ve yazı boyutları düzeltildi.
16. 390 px'de marka karuseli okları 9 px yatay taşma yapıyordu → giderildi.
17. Görseli girilmemiş alanlar artık şablon ölçüsünde nötr yer tutucu gösteriyor (sayfa düzeni bozulmuyor).

**Kategori / arama / ürün**
18. Ürün detayında indirimli fiyat kırmızı ve şablondan farklıydı → şablondaki gibi koyu büyük fiyat + üstü çizili eski fiyat.
19. Tüm ürün görselleri sabit oranlı kutularda, kırpılmadan/bozulmadan (dikey/yatay farklı oranlı yüklemelerle test edildi).
20. SSS'de uzun sorular mobilde 7 px yatay taşma yapıyordu (düğme `nowrap`) → satır kırılır.

**Üye / sipariş sayfaları**
21. Sipariş Tamamlandı sayfası eski giyim temasındaydı → breadcrumb, sipariş durumu adımları, ürün tablosu, özet ve tema düğmeleri.
22. Hesabım panelleri (profil, siparişler, adresler, favoriler, şifre): büyük harf/aralıklı siyah düğmeler ve "Yeni koleksiyon / kombin" metinleri → tema renkleri (sarı birincil düğme), Open Sans, garaj ekipmanına uygun metin; menü bağlantıları sarı görünüyordu → koyu.
23. Şifremi Unuttum / Şifre Sıfırla → tema kartı + breadcrumb.
24. İade İşlemleri, İade Talebi, Ödeme Bildirimi sayfalarında **header/footer yoktu** → tema iskeletine (`PageShell`) alındı.
25. Hamburger menüde orta menü sekmeleri ile kategoriler aynı adla iki kez listeleniyordu → tekrar kaldırıldı.

## 4. Akış testleri (gerçek backend, Playwright)

| Akış | 1440 | 390 |
|------|:----:|:----:|
| Ürün detay: galeri küçük resim, varyant seçimi, adet, sekmeler (Açıklama/Özellikler/Kargo & İade/Değerlendirmeler) | ✅ | ✅ |
| Stokta olmayan ürün sayfası (sepete ekle kapalı, "Tükendi") | ✅ | ✅ |
| Sepete ekle → sepet çekmecesi / mini sepet | ✅ | ✅ |
| Sepet sayfası (dolu, adet artırma) | ✅ | ✅ |
| Misafir ödeme: adres + il/ilçe + **Havale/EFT** → sipariş | ✅ | ✅ |
| Sipariş Tamamlandı sayfası | ✅ | ✅ |
| Üye ol | ✅ | ✅ |
| Hesabım: profil / siparişler / adresler / favoriler / şifre sekmeleri | ✅ | ✅ |
| Adres ekle + düzenle | ✅ | ✅ |
| Favorilere ekle → Favorilerim | ✅ | ✅ |
| Bilgilerim kaydet | ✅ | ✅ |
| Çıkış / giriş | ✅ | ✅ |
| Üye ödeme: **kayıtlı adres** + **Kapıda Ödeme** (yerelde açılarak) → sipariş | ✅ | ✅ |
| Siparişlerim listesi + sipariş detayı | ✅ | ✅ |
| Şifremi Unuttum / Şifre Sıfırla sayfaları | ✅ | ✅ |
| Sipariş takip (numara ile) | ✅ | ✅ |
| İade işlemleri sayfası | ✅ | ✅ |

Not: Aynı telefonla ödenmemiş havale siparişi varken yeni sipariş reddediliyor — bu bilinçli bir
iş kuralıdır (test sırasında görüldü, hata değil).

**Etkileşimler** (17/17 ✅): dikey "Tüm Kategoriler" mega paneli (hover), orta menü mega menüsü,
hamburger menü masaüstünde aç/kapa, canlı arama önerileri + kategori seçimi, arama sonuç
sayfası, yapışkan header, sıralama, sayfalama, liste görünümü, galeri, ürün sekmeleri, varyant
seçimi (adet artırma sepet akışında test edildi); mobilde menü aç/kapa + alt menü, mobil arama, mobil filtre paneli.

**Testler / derleme**: `CI=true yarn test --watchAll=false --runInBand` ✅ · `CI=true npx craco build` ✅ ·
backend `tests/test_demo_content.py`, `tests/test_site_menus_layout.py`, `tests/test_media_storage.py` ✅.

## 5. Panel — sahibinin yapacakları

### Ana sayfa (Tasarım › Sayfa Tasarımı)
- Ana sayfanın her bölümü soldaki akışta bir **blok**: sürükleyerek sıralayın, göz ikonuyla
  yayından alın/yayınlayın, kopyala ikonuyla çoğaltın, kalemle düzenleyin.
- Görsel alanlarında **"Önerilen: G × Y px"** yazar (slider 1920×466, mobil 800×860; reklam
  kartları 410×281 / 410×281 / 714×486; tam banner 1170×207; marka logosu 200×60).
- Slider slaytlarına başlık, alt başlık, fiyat etiketi/fiyat ve buton yazısı girilir; bağlantı
  görselin altındaki kutudan.
- Sekmeli bloklarda (Günün Fırsatı + Sekmeler, Kategori Izgarası, Çok Satanlar, Alt Ürün
  Sütunları) ürün kaynağı seçilir: öne çıkan / indirimli / çok satan / en yeni / seçili
  kategoriler / elle seçilen ürünler.
- **"Taslağı Sitede Önizle"**: kaydetmeden sitede yeni sekmede görürsünüz. **"Tümünü Kaydet"** ile yayınlanır.
- **"Şablon Düzenini Yükle"**: ana sayfayı şablon düzenine (tüm bölümler) geri kurar.
- Canlı sitede ana sayfa tasarımı boşsa ya da yalnız eski el değmemiş iskelet varsa bu düzen
  ilk açılışta **bir kez** otomatik kurulur; düzenlediğiniz bir tasarımın üzerine yazılmaz.

### Menüler (Tasarım › Menü Yönetimi)
Tek ekranda tüm menü grupları; her kartta menünün sitede **nerede** olduğunu gösteren şema
(ilgili alan kırmızı) ve **"Sitede göster"** bağlantısı (siteyi o alan vurgulu açar):
- **Üst Bar Bağlantıları** — en üstteki ince şerit (hoş geldiniz yazısı + bağlantılar, ikon seçimi).
- **Hamburger (Yan) Menü** — logonun yanındaki ☰ ile açılan panel (otomatik veya elle).
- **Tüm Kategoriler (Sol Menü)** — otomatik kategori ağacı veya elle menü; üste sabit hızlı bağlantılar.
- **Orta Menü (Ana Navigasyon)** — sekmeler + mega menü kolonları + sağdaki kampanya yazısı.
- **Mobil Menü** — hamburger menüyle aynı ya da ayrı liste.
- **Footer Sütunları** — Footer Tasarımı ekranına yönlendirir.
Öğeler 3 seviyeye kadar alt öğe alır; bağlantı kutusunun yanındaki "Seç…" ile kategori/sayfa seçilir.

### Demo içerik
Sayfa Tasarımı'nın sol altındaki **Demo İçerik** kartından "Demo İçerik Yükle" / "Kaldır"
(yalnız süper yönetici). Ayrıntı: KURULUM.md › Demo içerik.

### Ödeme logo bandı
Varsayılan iyzico bandı otomatik gösterilir. Farklı bir görsel için Footer Tasarımı › Ödeme Logo Bandı.

## 6. Kalan farklar ve nedenleri

- **Şablon v1.0 ana sayfa yapısı, v2.0 bileşenleriyle**: v1.0'ın kendi CSS'i (Bootstrap 3 /
  WooCommerce işaretlemesi) ile v2.0 CSS'i birlikte yüklenemez; v1.0 bölümleri v2.0'ın aynı
  tasarım dilindeki bileşenleriyle kuruldu. Görsel olarak aynı aile; ince farklar (ör. 2-1-2
  ızgaranın gri zemini) bu yüzdendir.
- **Ürün kartlarında indirim rozeti (%) ve "Kapıda Ödeme" etiketleri**: şablonda yok, işletme
  ihtiyacı olduğu için korundu.
- **Sepete eklenince sağdan açılan sepet çekmecesi**: şablonda yalnız açılır mini sepet var;
  mobil kullanılabilirlik için korundu (masaüstünde mini sepet de çalışıyor).
- **Hesabım panelleri** şablonda karşılığı olmayan (şablonda yalnız giriş/kayıt sayfası var)
  işlevler içerdiği için tema renk/yazı diliyle yeniden biçimlendirildi, birebir şablon sayfası değildir.
- **Ödeme sayfası** bilinçli olarak kendi (Shopify tarzı) tasarımında bırakıldı.
- Şablonun kendi SSS sayfası da 390 px'de 15 px taşma yapıyor (şablon hatası); bizde giderildi.
- "Tüm Kategoriler" menüsünde 14 ana kategori + 3 hızlı bağlantı şablondaki ~11 öğeden uzun
  olduğu için slider yüksekliği menüyü kapsayacak kadar uzar (Menü Yönetimi'nden ana kategori
  sayısı düşürülürse 466 px'e döner).

## 7. Ekran görüntüleri (bu klasör)

GarajTek (solda) ↔ şablon orijinali (sağda), 1440 ve 390 px:
`anasayfa-*` (şablon v1.0 ana sayfa ile), `kategori-*`, `urun-detay-*`, `sepet-*`,
`giris-uye-ol-*`, `sss-*`, `404-*`; yalnız GarajTek: `odeme-*`, `siparis-tamamlandi-*`,
`hesabim-siparisler-*`; panel: `admin-sayfa-tasarimi-1440`, `admin-sayfa-tasarimi-reklam-blok`,
`admin-menu-yonetimi-1440`, `admin-giris-1440`.

## 8. Yayına alma (sunucuda)

```bash
garajtek-update --build-frontend
```
(git pull → backend bağımlılıkları → frontend'i sunucuda derler → servisi yeniden başlatır.)
Tema CSS'inin adresi her derlemede değişen bir özet taşıdığından tarayıcı/Cloudflare önbelleğini
temizlemeye gerek yoktur.
