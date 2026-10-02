# Sayfa Tasarımı — Kullanım Kılavuzu (mağaza sahibi için)

Bu kılavuz, ana sayfanın **kod yazmadan** nasıl düzenleneceğini anlatır. Ana sayfadaki her bölüm,
yazı, görsel, bağlantı, ürün listesi, sekme, geri sayım, banner ve menü panelden değiştirilebilir.
Panelde gördüğünüz önizleme, vitrindekinin aynısıdır.

- Panel adresi: **Yönetim › Tasarım › Sayfa Tasarımı** (`/admin/sayfa-tasarimi`)
- Menü öğeleri: **Yönetim › Tasarım › Menü Yönetimi** (`/admin/menu-yonetimi`)
- Kategori adları, görselleri ve ikonları: **Yönetim › Kategoriler**
- Telefon, e-posta, adres, mağaza adı: **Sayfa Tasarımı › Genel Alanlar › İletişim Bilgileri**
  (boş bırakılan alanlar **Ayarlar › Genel Ayarlar**'daki firma bilgilerinden gelir)

---

## 1. Ekranın bölümleri

| Bölüm | Ne işe yarar |
|---|---|
| **Üst çubuk** | Cihaz seçimi (Masaüstü 1440 / Tablet 1024 / Mobil 390), ↶ Geri al (Ctrl+Z), ↷ İleri al (Ctrl+Shift+Z), **Revizyonlar**, **Önizle ↗** (yeni sekmede tam sayfa), **Taslağı at**, **Yayınla**. Durum yazısı taslağın ne zaman kaydedildiğini gösterir. |
| **Sol panel › Bloklar** | Ana sayfadaki bölümlerin (blokların) listesi. Sürükleyerek sıralayın; her satırda göz (gizle/göster), cihaz simgeleri, ⧉ Çoğalt, 🗑 Sil, ⏱ zamanlı yayın rozeti vardır. Sarı nokta = şablon varsayılanından değiştirilmiş. |
| **Sol panel › Genel Alanlar** | Tüm sitede ortak olan alanlar: Tema, Sayfa Düzeni, İletişim Bilgileri, Üst Bar, Header, Dikey Menü, Ana/İkincil Menü, E-Bülten, Footer Ürün Sütunları, Footer İletişim, Footer Bağlantıları, Footer Alt Şerit. |
| **Sağ taraf › Canlı önizleme** | Vitrinin kendisi. Bir bölüme **tıklayınca** soldaki formu açılır; bir yazıya/görsele tıklayınca formda o alan sarıyla vurgulanır. Bloklar arasındaki **+ Blok ekle** çizgisi oraya yeni blok ekler. |

## 2. Taslak → Yayın (en önemli kural)

1. Yaptığınız **her değişiklik otomatik olarak taslağa kaydedilir** (birkaç saniye içinde). Taslak
   **vitrinde görünmez**; yalnız sizin önizlemenizde görünür.
2. Beğendiğinizde **Yayınla**'ya basın → değişiklikler vitrine tek seferde geçer. Formda kırmızı hata
   varsa Yayınla pasif olur ve hatalar listelenir (ör. "Ana Slider › Slayt 2 › Düğme bağlantısı geçersiz").
3. **Taslağı at** → taslaktaki tüm değişiklikler silinir, yayındaki hâle dönülür.
4. **Revizyonlar** → her yayın kaydedilir (son 50). "Bu sürümü önizle" ve "Bu sürüme geri dön" ile eski
   bir yayını taslağa yükleyip tekrar yayınlayabilirsiniz. En alttaki **"Geçiş öncesi yedek"** eski
   sistemden gelen orijinal düzendir.
5. Aynı anda iki yönetici düzenlerse "Başka bir yönetici değişiklik yaptı" uyarısı çıkar:
   **Birleştir**, **Üzerine yaz** veya **Vazgeç (onların sürümü)** seçin.

## 3. Şablona sıfırlama

- **Tüm sayfa:** Bloklar sekmesinde **Şablon düzeni** → ana sayfa, Electro v1.0 `home.html` düzenine
  (9 bölüm) taslak olarak döner. Yayınlamadan önce kontrol edebilirsiniz.
- **Tek blok:** blok formunun üstündeki **Şablon varsayılanına sıfırla**.
- **Tek alan:** alanın yanındaki **↺** simgesi (yalnız değer şablondan farklıysa görünür).
  Slayt/kutu gibi tekrarlanan öğelerde ↺, şablondaki aynı sıradaki öğenin değerine döner.

Varsayılan ana sayfa (şablon v1.0 sırası):

| # | Blok | Şablondaki karşılığı |
|---|---|---|
| 1 | Ana Slider | home-v1-slider |
| 2 | Reklam Kutuları (3'lü) | home-v1-ads-block |
| 3 | Özel Teklif + Ürün Sekmeleri | deals-and-tabs |
| 4 | 2-1-2 Ürün Izgarası | 2-1-2-product-grid |
| 5 | Ürün Kartları Karuseli (Çok Satanlar) | best-sellers-products-cards-carousel |
| 6 | Tam Genişlik Banner | home-banner |
| 7 | Ürün Karuseli (Yeni Eklenenler) | recently-added-products-carousel |
| 8 | Marka Logoları Karuseli | brands-carousel |
| 9 | Alt Ürün Sütunları | footer-widgets (Öne Çıkanlar / İndirimdekiler / En Çok Puan Alanlar) |

## 4. Her bloğun ortak ayarları

Her blok formunda (blok tipine göre) şu sekmeler bulunur: **İçerik, Ürünler, Görünüm, Karusel,
Gelişmiş, Görünürlük**. Boş sekmeler gizlenir.

- **Görünüm (Varyant):** "Görünüm" seçicisi bloğun şablondaki farklı tasarımlarına geçirir (ör. Reklam
  Kutuları v1 3'lü / v2 2'li / v3 / 4'lü gri kart). Yazdıklarınız korunur.
- **Bölüm (Görünüm sekmesi):** genişlik (konteyner / tam genişlik / geniş 1430 px), bant arka plan rengi
  ve görseli, iç boşluk, **alttaki boşluk** (cihaz başına), yazı rengi, bağlantı hedefi (`#kampanyalar`).
- **Görünürlük:** Masaüstü (≥1200 px) / Tablet (768–1199) / Mobil (<768) aç-kapa, **başlangıç–bitiş
  tarihi** (zamanlı yayın), kitle (herkes / yalnız ziyaretçi / yalnız üye).
- **Giriş animasyonu:** sayfa kaydırıldıkça bloğun beliriş efekti (Tema'dan tümüyle kapatılabilir).
- **Tekrarlanan öğeler** (slayt, kutu, sekme, logo…): sürükle-sırala, çoğalt, gizle (göz), sil; slaytlarda
  öğe başına yayın zamanı.
- **Ürün kaynağı:** Elle seçim / Kategori / İndirimdekiler / En yeniler / Çok satanlar / Öne çıkanlar /
  En çok puan alanlar / Etiket / Marka / Son görüntülenenler; adet, sıralama, stokta olmayanları gizle,
  hariç tutulacak ürünler, "liste dolmazsa şununla tamamla". Alanın altında "eşleşen ürün sayısı" görünür.
- **Karusel:** kırılım başına görünen adet tablosu (ör. 0 px → 2, 992 px → 3, 1400 px → 5), kaydırma
  adımı, satır sayısı, boşluk, otomatik oynat + aralık, üzerindeyken dur, döngü / başa sar, geçiş
  (kaydır / belir), hız, noktalar (göster / gizle / yalnız mobil), oklar (yok / başlıkta / iki yanda / dışta),
  sürükleme, son kartın ayırıcısını gizle.
- **Geri sayım:** bitiş tarihi (boşsa "her gün 23:59 + N gün"), üst yazı, birimler (gün/saat/dk/sn),
  birim etiketleri, "gün 0 ise gizle", iki haneli gösterim, **süre bitince** (bloğu gizle / sayacı gizle /
  yazı göster / 00:00 olarak kalsın).
- **Başlık satırı:** başlık, H2/H3/gizli, hizalama, ana renk alt çizgi, sağ taraf (bloğun desteklediği
  seçenekler: hap/sekme bağlantıları, "Tümünü gör" bağlantısı, oklar).

## 5. Ana sayfa bölümleri — ne nereden düzenlenir

| Vitrinde gördüğünüz | Nereden düzenlenir |
|---|---|
| En üstteki kayan duyuru şeridi | Bloklar › **Dönen Duyuru Şeridi** (mesajlar + bağlantı, süre, renkler, konum: üst barın üstü/altı, cihaz görünürlüğü) |
| En üstteki geri sayım şeridi | Bloklar › **Geri Sayım Şeridi** (yazı, geri sayım, bağlantı, renkler, süre bitince davranışı) |
| Üst bar: "Hoş geldiniz" yazısı, Mağazamız / Sipariş Takibi / Hesabım, para birimi | Genel Alanlar › **Üst Bar** (yazı, bağlantı, sağ bağlantılar + ikon, stil, hangi ekranda gizlensin) |
| Logo, arama kutusu (yer tutucu, "Tüm Kategoriler" seçicisi), karşılaştır/favori/sepet simgeleri, mini sepet yazıları, Destek | Genel Alanlar › **Header** |
| Sarı "Tüm Kategoriler" dikey menü (başlık, ikon, ana sayfada açık mı, açılır panel "Tüm …" bağlantısı yazıları) | Genel Alanlar › **Dikey Menü**; menünün öğeleri: **Menü Yönetimi › Sol (dikey) menü** (otomatik kategori ağacı ya da elle; hızlı bağlantılar "Günün Fırsatları" vb.; elle modda öğe başına ikon ve **açılır panel arka plan görseli 540×460**) |
| Yatay menü (Kampanyalar, Yeni Ürünler, kategoriler) ve sağdaki "Ücretsiz kargo" yazısı | Menü Yönetimi › Orta menü; sağ yazı: Genel Alanlar › **Ana / İkincil Menü** |
| Mobil / hamburger menü | Menü Yönetimi › Hamburger / Mobil |
| Ana slider (slayt görseli, mobil görsel, odak noktası, üst başlık, başlık, alt başlık, fiyat, düğme yazısı + bağlantısı, yazı rengi, hizalama, katman animasyonları, yükseklik, otomatik geçiş) | Bloklar › **Ana Slider** |
| 3 reklam kutusu (görsel, yazı, "Hemen İncele" / "%'ye varan 20" / "başlayan 749,99 ₺", bağlantı) | Bloklar › **Reklam Kutuları** |
| Özel Teklif kartı (ürün otomatik/elle, başlık, görsel, kazanç rozeti, satılan/kalan çubuğu, geri sayım, çerçeve rengi) + 3 ürün sekmesi | Bloklar › **Özel Teklif + Ürün Sekmeleri** |
| 2-1-2 ızgara (sekmeler / kategori bağlantıları, büyük ürün) | Bloklar › **2-1-2 Ürün Izgarası** |
| Çok Satanlar kart karuseli (başlık, haplar "İlk 20" + kategoriler) | Bloklar › **Ürün Kartları Karuseli** |
| Tam genişlik banner | Bloklar › **Tam Genişlik Banner** (görsel + mobil görsel + bağlantı; metinli varyantta başlık ve fiyat kutusu) |
| Yeni Eklenenler karuseli | Bloklar › **Ürün Karuseli** |
| Marka logoları | Bloklar › **Marka Logoları Karuseli** (elle logo + bağlantı ya da katalogdaki logolu markalar; "tüm sayfalarda footer üstünde göster") |
| Footer üstündeki 3 ürün sütunu (Öne Çıkanlar / İndirimdekiler / En Çok Puan Alanlar, yıldızlar) | Bloklar › **Alt Ürün Sütunları** (bu blok sayfadaysa Genel Alanlar › Footer Ürün Sütunları gizlenir) |
| Bülten bandı (başlık, açıklama, yer tutucu, düğme, başarı/hata yazıları, KVKK onayı, renk) | Genel Alanlar › **E-Bülten** |
| Footer: logo, "Sorunuz mu var?" + telefonlar, adres başlığı + adres, sosyal medya | Genel Alanlar › **Footer İletişim** (telefon/e-posta/adres: **İletişim Bilgileri**) |
| Footer bağlantı sütunları ("Hızlı Erişim", "Müşteri Hizmetleri"…) | Genel Alanlar › **Footer Bağlantıları** (sütun + bağlantılar, kategorilerden otomatik doldurma) |
| Telif yazısı, ödeme logoları/bandı, ek bağlantılar (KVKK, Mesafeli Satış), ETBİS karekodu | Genel Alanlar › **Footer Alt Şerit** (`{yıl}` ve `{mağaza}` otomatik dolar) |
| Ana renk, yazı tipi, yazı boyutu, sayfa genişliği, ürün kartında favori/karşılaştır/kategori/eski fiyat/indirim rozeti ve **"Sepete Ekle" / "Favori" / "Karşılaştır" yazıları**, yukarı çık düğmesi | Genel Alanlar › **Tema** (renk ön ayarları: sarı, mavi, kırmızı, turuncu, yeşil…) |
| Ana sayfa tam genişlik mi, sol kenar çubuklu mu | Genel Alanlar › **Sayfa Düzeni** (sol kenar çubuklu düzende "Kenar Çubuğu" blokları 1200 px ve üstünde sol sütuna yerleşir) |

Katalogdan gelen bilgiler (ürün adı, fiyatı, ürün görseli, kategori adları, stok) ürün/kategori
ekranlarından düzenlenir; Sayfa Tasarımı yalnız **hangi** ürünlerin **nasıl** gösterileceğini seçer.

## 6. Eklenebilecek diğer bloklar (şablonun tüm ana sayfa çeşitlerinden)

**+ Blok Ekle** galerisi kategorilere ayrılmıştır; her kartta şablondaki görünümün küçük resmi vardır.
Eklenen blok şablon içeriğiyle dolu gelir.

| Galeri kategorisi | Bloklar |
|---|---|
| Slider | Ana Slider (v1, v2, v3, ürün görselli, kutulu + yan bannerlı, yuvarlak + fırsat kartlı, tam ekran, menü şeritli), Sekmeli Hero + Ürün Karuseli |
| Banner | Reklam Kutuları, Tam Genişlik Banner, İki Kolonlu Görsel Banner, Metinli/Görselli Banner Izgarası, Banner Mozaiği (1+6), Video Banner, İki Banner (eski) |
| Fırsat | Özel Teklif + Ürün Sekmeleri (v1 / v2 / indirim sekmeleri), Haftanın Fırsatları Karuseli, Sınırlı Haftalık Fırsatlar, Haftanın Fırsatı Slider |
| Ürün | 2-1-2 / 4-1-4 Ürün Izgarası, 6+1 / 8+1 Çok Satanlar, Ürün Izgarası (öneriler / son bakılanlar / sayfalı), Banner + Ürün Izgarası, Ürün Kartları Karuseli, Ürün Karuseli, Sekmeli Ürün Karuseli, Arka Plan Görselli Ürün Karuseli, Alt Ürün Sütunları |
| Kategori | Bu Ayın Popüler Kategorileri, Kategori Kartları, İkonlu Kategori Karuseli, Markalar + Kategori Kutuları Kartı, Kategori Listesi + Büyük Görsel Karuseli |
| Marka | Marka Logoları Karuseli |
| İçerik | Özellikler / Avantajlar Şeridi, Metin Bloğu, Metin Sütunları, Bilgi Kartları, Ekip Izgarası, Sıkça Sorulanlar, Sayfa Başlığı, Popüler Aramalar, Atölyemizden (görsel ızgara) |
| Kenar Çubuğu | Kenar Reklam Görseli, Kenar Ürün Listesi, Kenar Ürün Karuseli, Kenar Avantajlar |
| Üst Bar | Dönen Duyuru Şeridi, Geri Sayım Şeridi |

## 7. Görsel ölçüleri

Yükleme alanı önerilen ölçüyü gösterir; küçük görselde sarı uyarı, oranı farklı görselde "kırpılacak"
uyarısı çıkar. "Önerilen orana kırp" seçeneği ve **odak noktası** (görselde tıklayın — dar ekranlarda
görselin o noktası ortada kalır) vardır. Görseller yüklenirken otomatik sıkıştırılır (2400 px).
JPG/WEBP fotoğraf, logolar için şeffaf PNG/SVG önerilir.

| Blok › alan | Önerilen ölçü (px) | Mobil görsel (ops.) |
|---|---|---|
| Ana Slider › slayt arka planı | **1920 × 466** | 800 × 860 |
| Ana Slider › ürün görseli (ürünlü/kutulu varyant) | 416 × 420 | — |
| Ana Slider › yan bannerlar / kategori şeridi | 246 × 176 / 300 × 300 | — |
| Reklam Kutuları › kutu görseli | **410 × 281** | — |
| Tam Genişlik Banner | **1170 × 207** | 750 × 300 |
| İki Kolonlu Görsel Banner | 690 × 150 | 690 × 250 |
| İki Banner (eski) | 570 × 300 | — |
| Metinli/Görselli Banner Izgarası | 446 × 262 | — |
| Banner Mozaiği › büyük / küçük | 552 × 325 / 268 × 155 | — |
| Video Banner › kapak görseli | 1170 × 500 | — |
| Sekmeli Hero › arka plan / sekme görseli | 1920 × 714 / 724 × 360 | — |
| Haftanın Fırsatı Slider › arka plan / ürün | 1400 × 420 / 400 × 400 | — |
| Haftanın Fırsatları Karuseli › büyük / küçük resim | 600 × 600 / 180 × 180 | — |
| Özel Teklif › ürün görseli yerine | 250 × 232 | — |
| Banner + Ürün Izgarası › banner | 360 × 616 | — |
| Sekmeli Ürün Karuseli › yan banner | 390 × 370 | — |
| Arka Plan Görselli Ürün Karuseli › arka plan / yan görsel | 1919 × 1026 / 665 × 616 (şeffaf PNG) | — |
| Alt Ürün Sütunları › tanıtım görseli (≥1480 px) | 330 × 360 | — |
| Marka logoları | 200 × 60 (şeffaf PNG/SVG) | — |
| Kategori Kartları / Popüler Kategoriler | 300 × 300 / 250 × 232 | — |
| Kategori Listesi + Büyük Görsel | 840 × 370 | — |
| Markalar + Kategori Kutuları › kutu başlık görseli | 350 × 92 | — |
| Atölyemizden (görsel ızgara) | 600 × 600 | — |
| Kenar Reklam Görseli | 270 × 428 | — |
| Metin Bloğu görseli / Bilgi Kartları / Ekip fotoğrafı | 570 × 400 / 500 × 300 / 300 × 300 | — |
| Sayfa Başlığı arka planı, her bloğun bant arka plan görseli | 1920 × 600 | — |
| Avantaj/kategori ikonu yerine görsel | 64 × 64 (şeffaf PNG/SVG) | — |
| Dikey menü açılır panel arka planı (Menü Yönetimi) | 540 × 460 | — |
| Header › logo / mobil logo / footer logosu | 176 × 43 / 130 × 32 / 156 × 37 (SVG/PNG) | — |
| Footer Alt Şerit › ödeme logosu / ETBİS karekodu | 52 × 32 / 80 × 80 | — |

## 8. Menüler

**Menü Yönetimi** menülerin ağaç yapısını tutar (Sayfa Tasarımı içinden "Menüyü düzenle →" ile gidilir):

- **Üst bar** sağ bağlantıları ve "Hoş geldiniz" yazısı (Sayfa Tasarımı › Üst Bar ile aynı veri).
- **Sol (dikey) menü:** Otomatik (Kategoriler ekranındaki sıra ve "menüde göster") ya da elle; en fazla
  ana kategori sayısı; üste sabit hızlı bağlantılar. Elle modda alt öğeler açılır panelde sütun olur;
  her ana öğeye ikon ve panel arka plan görseli verilebilir. Otomatik modda panel görseli kategori görselidir.
- **Orta (yatay) menü:** sekmeler, kolonlu açılır menüler, sağdaki kargo yazısı.
- **Hamburger** ve **Mobil** menüler.

Menü değişiklikleri kaydedildiği anda vitrine yansır (taslak/yayın yalnız Sayfa Tasarımı içindir).

## 9. İpuçları

- Bir bloğu geçici kaldırmak için silmek yerine **göz** simgesiyle gizleyin.
- Kampanya bloklarında **Görünürlük › Başlangıç/Bitiş** kullanın; süre dolunca blok kendiliğinden kalkar.
- Mobilde farklı görsel için görsel alanındaki **Mobil görsel** seçeneğini kullanın.
- **Önizle ↗** taslağı yeni sekmede tam ekran gösterir; ziyaretçiler görmez.
- Eski sistemden kalan ve artık desteklenmeyen bir blok varsa listede "Desteklenmeyen eski blok"
  uyarısıyla görünür, vitrinde çizilmez; silip silmemek size kalmıştır.

## 10. Sunucuya yükleme (geliştirici/teknik kişi için)

Kod güncellemesinden sonra sunucuda:

```
garajtek-update --build-frontend
```

İlk açılışta eski ana sayfa blokları ve menü/footer ayarları yeni sisteme **otomatik ve bir kez**
taşınır; yönetici tarafından girilmiş hiçbir yazı/görsel/bağlantı kaybolmaz. Taşınma öncesi düzen
**Revizyonlar › "Geçiş öncesi yedek"** olarak saklanır ve oradan geri yüklenebilir.

## 11. Bilinen sınırlar

- Kırpma, önerilen orana otomatik kırpma + odak noktası şeklindedir; serbest kırpma çerçevesi yoktur.
- Header görünümleri v1, v2, v3 ve v3 tam renk hazırdır; şablonun v4–v11 header'ları henüz yoktur.
- "Kenar Çubuğu Blog Karuseli" sitede blog modülü olmadığı için galeride gizlidir.
- Şablon v1.0 (Bootstrap 3) ile vitrin (Bootstrap 4) arasında 992–1199 px aralığında sayfa genişliği
  10 px farklıdır; bu aralıkta bazı bloklar şablondan birkaç piksel dar görünür.
- Çerez onayı bandı ve "Designed by" geliştirici künyesi Sayfa Tasarımı'nın dışındadır (KVKK modülü /
  sözleşme gereği sabittir).
