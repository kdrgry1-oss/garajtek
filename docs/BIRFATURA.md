# BirFatura e-Fatura / e-Arşiv Entegrasyonu

garajtek.com faturalarını **BirFatura** keser. Entegrasyon BirFatura'nın **Özel Entegrasyon (API)**
modeliyle çalışır: BirFatura siparişleri belirli aralıklarla bizim sitemizden **çeker**, alıcı
e-Fatura mükellefiyse e-Fatura, değilse e-Arşiv keser ve fatura bağlantısını siparişe **geri yazar**.
Fatura, panelde sipariş detayında ve müşterinin "Siparişlerim" ekranında görünür.

## 1. Panelde hazırlık (garajtek yönetim paneli)

1. **Entegrasyonlar → BirFatura (e-Fatura)** sayfasını açın.
2. **Token oluştur**'a basın. Token yalnız o anda gösterilir; kopyalayın (sonra yalnız son 4 hanesi görünür).
   Token veritabanında şifreli saklanır (`SECRETS_MASTER_KEY`).
3. **Sipariş durumu eşlemesi**: BirFatura'da seçilecek durum gruplarını kontrol edin. Varsayılan:
   - `1` Onaylandı (faturalanabilir) → Onaylandı, Hazırlanıyor, İşleme Alındı, Kargoya Hazır, Kargoya Verildi, Taşınıyor, Dağıtımda, Teslim Edildi
   - `2` Kargoya Verildi → Kargoya Verildi, Taşınıyor, Dağıtımda
   - `3` Teslim Edildi → Teslim Edildi

   Ödeme bekleyen (havale onaylanmamış), iptal ve iade durumları hiçbir grupta yoktur → faturalanmaz.
   Grup Id'leri BirFatura'da saklandığı için değişmez.
4. **Fatura ayarları**: iskonto gösterimi (önerilen: indirimli birim fiyat), varsayılan/kargo/hizmet KDV
   oranları, TCKN'siz müşteri için `11111111111`, fatura açıklaması.
5. **Entegrasyon açık** kutusunu işaretleyin.

## 2. BirFatura panelinde

1. BirFatura → **Mağazalar / Entegrasyonlar → Yeni mağaza ekle → "Özel Entegrasyon" (API / özel yazılım)**.
2. **Site adresi**: panel sayfasındaki "Site adresi" değeri, ör. `https://garajtek.com/api/birfatura`
   (BirFatura `/api/orderStatus`, `/api/paymentMethods`, `/api/orders`, `/api/invoiceLinkUpdate`,
   `/api/orderCargoUpdate` yollarını kendisi ekler). Panel uçları tek tek istiyorsa sayfadaki tam
   adresleri kopyalayın.
3. **API şifresi**: oluşturduğunuz token.
4. Kaydedince BirFatura sipariş durumlarını ve ödeme yöntemlerini çeker. **Faturalanacak sipariş durumu**
   olarak `Onaylandı (faturalanabilir)` (Id 1) seçin; ödeme yöntemlerini BirFatura tarafındaki karşılıklarıyla
   eşleyin (1 Kredi Kartı, 2 Banka EFT-Havale, 3 Kapıda Ödeme).
5. Sipariş çekme sıklığı / tarih aralığını ayarlayın (tek çekimde en fazla 31 gün; panelden değiştirilebilir).
6. e-Fatura / e-Arşiv seçimi BirFatura'da **otomatik** kalsın: kurumsal siparişlerde VKN (`TaxNo`) ve vergi
   dairesi gönderilir, BirFatura GİB mükellef sorgusuna göre e-Fatura ya da e-Arşiv düzenler.
7. "Faturayı otomatik resmileştir" seçeneğini ilk günlerde **kapalı** tutup birkaç taslağı kontrol edin.

## 3. Test akışı

1. Panelde **Bağlantıyı test et**: kayıtlı token ile sipariş çekimini içeriden çalıştırır, BirFatura'nın
   göreceği JSON'dan örnek gösterir ve genel adresin (`PUBLIC_API_URL`) dışarıdan erişilebilir olduğunu dener.
2. Siteden bir test siparişi verin, panelde **Onaylandı**'ya alın.
3. BirFatura'da mağazayı "Siparişleri şimdi çek" ile tetikleyin; sipariş BirFatura'da görünmeli. Taslak
   faturada kalemler, KDV oranları (ürünün KDV'si; kargo ve hizmet bedelleri %20), indirim ve toplam
   **siparişteki ödenen tutarla** aynı olmalı.
4. Faturayı resmileştirin → birkaç dakika içinde sipariş detayında **Fatura** kutusu (numara + PDF bağlantısı)
   belirir. Panel sayfasındaki **Son çağrılar** tablosu her BirFatura isteğini (HTTP kodu, adet, atlanan
   siparişler ve nedenleri) gösterir.

Sorun giderme: `401` → BirFatura'daki API şifresi panel token'ıyla aynı değil (token yenilendiyse BirFatura'da da
güncelleyin). `404` → entegrasyon kapalı. `422 faturaUrl` → fatura bağlantısı güvenilen host listesinde değil
(varsayılan `birfatura.com`, `*.birfatura.com`; panelden eklenebilir). Sipariş gelmiyorsa test sonucundaki
"Atlananlar" listesine bakın (pazaryeri siparişi, tutar 0, başka yoldan faturalanmış, zorunlu alan boş).

## Teknik notlar

- Uçlar: `backend/routes/integrations_birfatura.py`; eşleme: `backend/services/birfatura.py`; testler:
  `backend/tests/test_birfatura.py`.
- Kimlik doğrulama: `token` HTTP başlığı, sabit-süreli karşılaştırma; aynı IP'den dakikada 10 hatalı deneme → 429.
- Tarihler `dd.MM.yyyy HH:mm:ss`, Türkiye saati. `OrderId` = sipariş numarasının sayısal kısmı (`W10234` → `10234`).
- Fatura matrahı: kupon/kampanya/havale indirimi, hediye çeki ve puan iskonto olarak ürün satırlarına dağıtılır
  (checkout'ta dondurulan kalem indirimi esas); hediye paketi ayrı satır, kargo `ShippingChargeTotal`, kapıda
  ödeme bedeli `PayingAtTheDoorChargeTotal`, taksit vade farkı `InstallmentChargeTotal` (malın KDV oranıyla).
- Sözleşme kaynağı: BirFatura resmî "Özel Entegrasyon API" dokümanı
  (developers.birfatura.com) — alan adları resmî şemadan türetilmiş açık kaynak paketlerle doğrulandı
  (github.com/aenzenith/laravel-birfatura, github.com/gurkanbicer/birfatura-whmcs).
