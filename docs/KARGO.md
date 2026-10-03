# Kargo Entegrasyonları — Aras Kargo, PTT Kargo

Bu belge, yönetim panelindeki **Ayarlar › Kargo Ayarları** sayfasında Aras Kargo ve PTT Kargo
entegrasyonlarının nasıl kurulacağını, hangi bilginin nereden alınacağını ve canlıya geçmeden
önceki test akışını anlatır. Desteklenen kargo entegrasyonları yalnızca Aras Kargo ve PTT Kargo'dur;
eski (MNG/DHL eCommerce vb.) entegrasyonlar kaldırılmıştır. Bu firmalarla gönderilmiş eski siparişlerde
kayıtlı firma adı, takip numarası ve takip linki görüntülenmeye devam eder. Kayıtlı varsayılan firma eski
bir entegrasyonsa açılışta otomatik olarak Aras Kargo yapılır (kayıtlı bilgiler silinmez).

---

## 1. Genel işleyiş

| Adım | Ne olur? |
|---|---|
| **Barkod Oluştur / Kargoya Ver** (sipariş detayı veya toplu seçim) | Seçili kargo firmasında gönderi kaydı açılır, siparişe barkod yazılır, sipariş **Hazırlanıyor** olur. |
| **Etiket Yazdır** | 10×15 cm etiket açılır. Aras/PTT etiketinde çubuklar **kargo firmasının okuttuğu barkodu** kodlar, altında sipariş numarası yazar. Kapıda ödemede tahsilat tutarı etikette görünür. |
| Şube paketi okutur | Her 30 dakikada bir çalışan senkron (veya **Takibi Yenile**) takip numarasını çeker, siparişi **Kargoya Verildi** yapar; teslimde **Teslim Edildi** yapar. Müşteriye SMS/e-posta, *Sipariş Durumları* ayarlarında açık olan kanallardan gider. |
| **Kargo Kaydını İptal Et** | Paket henüz kargoya verilmemişse kayıt kargo firmasında silinir, sipariş kargo bilgileri temizlenir (sipariş tekrar **Onaylandı** olur). |
| Müşteri takip sayfası | `Siparişlerim` ve `Sipariş Takip` ekranlarında firmanın takip linki gösterilir. |

**Varsayılan kargo firması:** Kargo Ayarları sayfasının en üstündeki *Kargo Firmaları ve
Varsayılanlar* kartından seçilir. Sipariş detayındaki ve toplu barkod çubuğundaki firma seçicisi bu
değerle açılır; istenirse sipariş bazında değiştirilebilir. Aynı anda birden fazla firma kullanılabilir.

**Desi / ağırlık:** Öncelik sırası → siparişe özel ölçü (`cargo_package`) → ürün kartındaki
genişlik × derinlik × yükseklik / 3000 (desi) ve ürün ağırlığı → firmaya özel varsayılan →
genel varsayılan (Kargo Ayarları kartı). Ürünlerde ölçü girilmemişse varsayılanları gerçekçi tutun.

**Kapıda ödeme:** Ödeme yöntemi *kapıda ödeme* olan siparişlerde tahsilat tutarı (sipariş toplamı)
otomatik gönderilir — Aras'ta `IsCod=1 / CodAmount`, PTT'de `OS` ek hizmeti + `odeme_sart_ucreti`.

**Güvenlik:** Şifreler veritabanında şifreli saklanır, ekranda `********` olarak görünür. Şifre
alanını değiştirmeden kaydetmek mevcut şifreyi korur.

---

## 2. Aras Kargo

Aras'ın **iki ayrı servisi ve genellikle iki ayrı kullanıcısı** vardır:

1. **Sevkiyat Entegrasyonu (SetOrder)** — gönderi kaydı açar ve iptal eder.
2. **Müşteri Bilgi Sorgulama Servisleri (GetQueryJSON)** — takip numarası ve durum sorgular.

### 2.1 Bilgileri nereden alırım?

1. Aras Kargo kurumsal müşterisi olun (bağlı olduğunuz şube / müşteri temsilcisi).
2. <https://esasweb.araskargo.com.tr> adresine kurumsal kullanıcınızla girin.
3. **Tanımlamalar › Entegrasyonlar › XML Servisleri** sayfasından:
   - *Sevkiyat (SetOrder) web servis* üyeliği → **Sevkiyat kullanıcı adı / şifresi**
     (canlı bilgiler test sonrası müşteri temsilciniz tarafından verilir),
   - *Bilgi sorgulama XML servisi* üyeliği → **sorgulama kullanıcı adı / şifresi** ve
     **Müşteri Kodu (CustomerCode)** (kayıt olduğunuz sayfada yazar).
4. Müşteri temsilcinizden şubenizde **entegrasyon kodu (sipariş numarası = MÖK)** ile işlem yapılması
   gerektiğini teyit edin. Şube paket üzerindeki **parça barkodunu** okutarak irsaliye keser;
   Aras kargo takip numarası o anda oluşur.
5. (İsteğe bağlı) Birden fazla çıkış adresiniz varsa **SenderAccountAddressId** değerini isteyin.

### 2.2 Panelde nereye ne girilir?

**Ayarlar › Kargo Ayarları › (listeden) Aras Kargo**

| Alan | Değer |
|---|---|
| Sevkiyat Servisi Kullanıcı Adı / Şifresi | SetOrder kullanıcısı. Test ortamı için Aras'ın dokümandaki ortak test hesabı: `neodyum` / `nd2580` |
| Müşteri Kodu (CustomerCode) | Sorgulama servisinin müşteri kodu (takip senkronu için **zorunlu**) |
| Sorgulama Servisi Kullanıcı Adı / Şifresi | Bilgi sorgulama kullanıcısı (boşsa sevkiyat kullanıcısı denenir) |
| Ortam | **Test** veya **Canlı** |
| Kargo Ücretini Kim Öder | 1 = gönderici, 2 = alıcı (kapıda ödemede Aras kuralı gereği her zaman 1) |
| Kapıda Ödeme Tahsilat Tipi | 0 = nakit, 1 = kredi kartı |
| Varsayılan Desi / Ağırlık | Ürün ölçüsü yoksa kullanılır |

Kaydedip **Bağlantıyı Test Et**'e basın. Test hem sevkiyat hem sorgulama servisine gerçek istek atar.

### 2.3 Teknik ayrıntılar

| | Test | Canlı |
|---|---|---|
| Sevkiyat (ASMX) | `https://customerservicestest.araskargo.com.tr/arascargoservice/arascargoservice.asmx` | `https://customerws.araskargo.com.tr/arascargoservice.asmx` |
| Sorgulama (WCF) | `https://customerservicestest.araskargo.com.tr/ArasCargoIntegrationService.svc` | `https://customerservices.araskargo.com.tr/ArasCargoCustomerIntegrationService/ArasCargoIntegrationService.svc` |

- `SetOrder`: IntegrationCode = sipariş no, TradingWaybillNumber = sipariş no, parça barkodu =
  `sipariş no + 01, 02…` (örn. `W1006301`). Aynı sipariş en fazla 20 kez güncellenebilir.
- `CancelDispatch(integrationCode)`: irsaliyesi kesilmiş gönderi iptal edilemez (kod 999).
- Takip: `GetQueryJSON` QueryType=1 + IntegrationCode → `KARGO_TAKIP_NO`, `DURUM_KODU`
  (1 çıkış şubesinde, 2 yolda, 3 teslimat şubesinde, 4 dağıtımda, 5 parçalı teslim, 6 teslim edildi,
  7 yönlendirildi), `TIP_KODU`=3 → iade.
- Müşteri takip linki: `https://kargotakip.araskargo.com.tr/mainpage.aspx?code=<takip no>`.

---

## 3. PTT Kargo

### 3.1 Bilgileri nereden alırım?

1. Bölgenizdeki **PTT Başmüdürlüğü** ile kurumsal kargo sözleşmesi yapın (e-ticaret / kurumsal müşteri).
2. Başmüdürlükten **3. taraf gizlilik taahhütnamesini** imzalayıp şunları isteyin:
   - **Müşteri Numarası (musteriId)** — 9-10 hane,
   - **Web servis şifresi**,
   - **Barkod aralığı** — 12 haneli başlangıç ve bitiş numarası (13. hane = kontrol hanesi,
     sistem otomatik hesaplar),
   - Sözleşmenizdeki **ek hizmet kodları** (örn. `SB` SMS ile bilgilendirme, `OS` ödeme şartlı
     = kapıda ödeme, `DK` değer konulmuş) ve **ödeme şekli** (MH mahsup / N nakit / UA ücreti alıcıdan),
   - Kapıda ödeme tahsilatı posta çeki hesabına yatacaksa **posta çeki numarası**.
3. Web servis erişimi için sunucunuzun çıkış IP adresinin PTT tarafında tanımlanması gerekebilir.

### 3.2 Panelde nereye ne girilir?

**Ayarlar › Kargo Ayarları › (listeden) PTT Kargo**

| Alan | Değer |
|---|---|
| Müşteri Numarası (musteriId) | PTT'nin verdiği müşteri no |
| Web Servis Şifresi | PTT'nin verdiği şifre |
| Ortam | Test / Canlı |
| Barkod Aralığı Başlangıç / Bitiş | 12 haneli değerler (13 hane girilirse son hane yok sayılır) |
| Ödeme Şekli | Sözleşmenize göre (çoğunlukla **MH**) |
| Ek Hizmet Kodları | Her gönderiye eklenecek kodlar, bitişik yazılır (örn. `SB`) |
| Kapıda Ödeme Ek Hizmet Kodu | Varsayılan `OS`; kapıda ödemeli siparişlerde otomatik eklenir |
| Posta Çeki No | İsteğe bağlı (rezerve1, 8 hane) |
| Gönderici Bilgisini Gönder | *Hayır* → PTT'de kayıtlı müşteri bilgisi; *Evet* → Mağaza/Gönderici Adresi bilgileri |
| Varsayılan Desi / Ağırlık | Ürün ölçüsü yoksa |

**Barkod sayacı:** Her gönderide aralıktan sıradaki numara kullanılır (atomik sayaç). Başarısız
istekte ayrılan barkod siparişte saklanır ve tekrar denemede aynı numara kullanılır. Yeni bir
aralık girildiğinde sayaç o aralığın başından başlar; aralık bitince sistem uyarır.

### 3.3 Teknik ayrıntılar

| | Test | Canlı |
|---|---|---|
| Veri yükleme | `https://pttws.ptt.gov.tr/PttVeriYuklemeTest/services/Sorgu` | `https://pttws.ptt.gov.tr/PttVeriYukleme/services/Sorgu` |
| Gönderi takip | `https://pttws.ptt.gov.tr/GonderiTakipV2Test/services/Sorgu` | `https://pttws.ptt.gov.tr/GonderiTakipV2/services/Sorgu` |

- `kabulEkle2`: kullanici=`PttWs`, gonderiTur=`KARGO`, gonderiTip=`NORMAL`, dosyaAdi her çağrıda
  benzersiz (`siparişNo-barkod`), ağırlık **gram**, desi = en×boy×yükseklik/3000.
- `barkodVeriSil`: PTT'nin henüz kabul etmediği gönderiyi siler.
- `gonderiSorgu`: hareket satırları (IKODU / ISLEM / ITARIH / ISAAT / IMERK) → kabul, sevk,
  dağıtım, teslim, iade, teslim edilemedi.
- Kontrol hanesi: 12 hane soldan 1,3,1,3… ile çarpılıp toplanır; toplamı bir üst 10'un katına
  tamamlayan rakam (örn. `275036569845` → `2750365698456`).
- Müşteri takip linki: `https://gonderitakip.ptt.gov.tr/Track/Verify?q=<barkod>`.

---

## 4. Test akışı (canlıya geçmeden önce)

1. İlgili firmayı **Ortam = Test** ile kaydedin, **Bağlantıyı Test Et** → yeşil mesaj bekleyin.
2. Kargo Ayarları üst kartında varsayılan firmayı seçin, varsayılan desi/kg'yi kontrol edin.
3. Gerçek adresli bir **test siparişi** oluşturun (telefon 10 hane, il/ilçe dolu).
   Kapıda ödeme senaryosunu da ayrıca deneyin.
4. Sipariş detayında **Barkod Oluştur / Kargoya Ver** → barkod ve **TEST** rozeti görünmeli.
5. **Etiket Yazdır** → barkodun okunduğunu bir barkod okuyucu/telefonla doğrulayın.
6. **Kargo Kaydını İptal Et** → kaydın silindiğini doğrulayın; tekrar oluşturun.
7. Test ortamında takip verisi genelde gelmez; Aras/PTT entegrasyon ekibiyle karşılıklı test
   yapıp onay alın (Aras test sonrası canlı kullanıcıyı verir).
8. **Ortam = Canlı** yapıp canlı bilgileri girin, tekrar bağlantı testi yapın; ilk canlı gönderide
   şubenin barkodu okuttuğunu ve 30 dk içinde takip numarasının siparişe düştüğünü kontrol edin.
   Beklemek istemezseniz *Aras/PTT takibini şimdi senkronla* düğmesini kullanın.

## 5. Sorun giderme

| Belirti | Olası neden |
|---|---|
| Aras `1000 Kullanıcı adı ve şifreniz yanlış` | Sevkiyat kullanıcısı yanlış veya test/canlı ortam karışık |
| Aras `1002 Aras şube bilginiz tanımlı değil` | Müşteri temsilcisi entegrasyonu şubeye tanımlamalı |
| Aras takip "müşteri kodu girilmemiş" | Sorgulama servisi Müşteri Kodu boş |
| PTT `SOAP Fault` / şifre-yetki mesajı | Müşteri no / şifre hatalı ya da IP izni yok |
| PTT "barkod aralığı tükendi / tanımlı değil" | PTT'den yeni aralık alıp girin |
| Etiket barkodu okunmuyor | Yazıcı ölçeği %100 / "gerçek boyut" olmalı |

Ayrıntılı kayıtlar: `cargo_logs` koleksiyonu (`GET /api/orders/cargo/logs`) ve sipariş işlem geçmişi.

## 6. Kod haritası

- `backend/aras_kargo_client.py`, `backend/ptt_kargo_client.py` — SOAP istemcileri (saf, test edilebilir)
- `backend/cargo_carriers/registry.py` — taşıyıcı arayüzü (ARAS/PTT), ayar okuma, varsayılan firma, eski varsayılan → Aras başlangıç migrasyonu
- `backend/cargo_carriers/service.py` — oluştur / iptal / takip / zamanlanmış senkron
- `backend/routes/cargo_carriers.py` — `/api/cargo-carriers/*` uçları
- `backend/routes/orders.py` — `cargo-barcode`, `cargo-refresh`, `cargo-label` Aras/PTT'ye yönlenir
- `frontend/src/components/admin/OrderCargoActions.jsx`, `frontend/src/pages/admin/CargoSettings.jsx`
- Testler: `backend/tests/test_aras_kargo.py`, `test_ptt_kargo.py`, `test_cargo_carriers.py`

Kaynak dokümanlar: Aras Kargo “Sevkiyat Entegrasyonu Web Servis Dökümanı”, “Müşteri Bilgi
Sorgulama Servisleri”, “Kargo Takip Entegrasyonu”; PTT “Veri Yükleme Web Servisi Kullanım Dokümanı”.
