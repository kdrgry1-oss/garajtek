# Kurulum Rehberi — Yeni Marka

Bu rehber, platformu yeni bir işletme için sıfırdan ayağa kaldırır. Varsayılan dağıtım:
**MongoDB Atlas** (veritabanı) + **Railway** (backend) + **Cloudflare Pages** (vitrin/panel)
+ **Cloudflare R2** (görseller). Kendi sunucunuza kurmak için `deploy/` betiklerine bakın (**Ubuntu 24.04 LTS**, root/SSH; 22.04 desteklenmez).

> Tahmini süre: altyapı 1–2 saat; entegrasyon hesaplarının (iyzico, pazaryeri, e-fatura, SMS)
> onayları firmaya göre birkaç gün sürebilir.

---

## 1. Altın kurallar

1. **Her marka ayrı veritabanı + ayrı `JWT_SECRET` + ayrı `SECRETS_MASTER_KEY`** kullanır.
   Başka bir kurulumun anahtarını asla kopyalamayın.
2. Entegrasyon şifreleri (iyzico, pazaryeri, kargo, SMS, e-fatura) **panelden** girilir ve
   veritabanında `SECRETS_MASTER_KEY` ile şifreli saklanır. Env'e yalnız altyapı sırları yazılır.
3. Canlıya almadan önce iyzico/pazaryerlerini **test (sandbox) modunda** doğrulayın.

## 2. Veritabanı (MongoDB Atlas)

1. Yeni bir cluster (M10+ önerilir) ve bir veritabanı kullanıcısı oluşturun.
2. Network Access'e Railway çıkış IP'lerini (veya geçici olarak 0.0.0.0/0) ekleyin.
3. Bağlantı dizesini (`mongodb+srv://…`) ve veritabanı adını not edin.

## 3. Görsel depolama (Cloudflare R2)

1. R2'de bir bucket açın (ör. `magaza-media`), bir API token (Object Read & Write) üretin.
2. Bucket'a özel bir alan adı bağlayın (ör. `cdn.magaza.com`) — ürün görselleri buradan sunulur.
3. `R2_*` ve `CDN_URL` değişkenlerini aşağıdaki tabloya göre doldurun.

## 4. Backend (Railway)

1. Bu repoyu Railway'e bağlayın; **Root Directory = `backend`**. `Procfile` başlatma komutunu içerir
   (`uvicorn server:app`), Python sürümü `runtime.txt`'dedir.
2. Ortam değişkenleri (`backend/.env.example` tam listedir):

| Değişken | Zorunlu | Açıklama |
|---|---|---|
| `MONGO_URL`, `DB_NAME` | ✅ | Atlas bağlantısı ve veritabanı adı |
| `JWT_SECRET` | ✅ | En az 32 karakter rastgele (`openssl rand -hex 32`) |
| `SECRETS_MASTER_KEY` | ✅ | Fernet anahtarı: `python -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())"` |
| `SITE_URL` | ✅ | Vitrin adresi, ör. `https://magaza.com` |
| `PUBLIC_API_URL` | ✅ | Backend'in herkese açık adresi, ör. `https://api.magaza.com` |
| `CORS_ORIGINS` | ✅ | `https://magaza.com,https://www.magaza.com` |
| `ADMIN_INITIAL_EMAIL`, `ADMIN_INITIAL_PASSWORD` | ✅ (ilk açılış) | İlk süper yönetici; parola ≥ 12 karakter. İlk girişte parola değişimi istenir. Kurulumdan sonra parolayı env'den silin. |
| `OWNER_SUPER_ADMIN_EMAILS` | önerilir | Süper yönetici yetkisi korunacak hesap(lar) |
| `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`, `R2_PUBLIC_URL`, `CDN_URL` | ✅ | Görsel depolama |
| `CF_EDGE_SECRET` | önerilir | Cloudflare'in origin'e eklediği gizli başlık (gerçek istemci IP doğrulaması, rate-limit) |
| `ADMIN_MFA_ENFORCE` | önerilir | `1` → yöneticilere iki adımlı doğrulama zorunlu |
| `ALERT_SMTP_*`, `ALERT_TO_EMAIL` | önerilir | Sistem uyarı e-postaları |
| `SUPPORT_AUDIT_KEY` | opsiyonel | Boşsa destek teşhis uçları kapalıdır. Kullanacaksanız uzun rastgele değer verin, düzenli değiştirin. |
| `ENABLE_API_DOCS` | opsiyonel | `1` → /docs açık (canlıda kapalı tutun) |

3. Özel alan adı: Railway servisine `api.magaza.com` bağlayın.
4. İlk açılışta backend indeksleri ve varsayılan ayarları oluşturur; loglarda
   `Admin olusturuldu` satırını görün.

## 5. Vitrin + panel (Cloudflare Pages)

1. Cloudflare Pages'te projeyi bu repoya bağlayın:
   - Root directory: `frontend`
   - Build command: `yarn install --frozen-lockfile && yarn build`
   - Build output: `build`
   - Pages Functions: root `frontend` olduğunda `frontend/functions/` kullanılır (kenar SEO/OG +
     `llms.txt`). Repo kökündeki `functions/` yalnız root dizini repo kökü seçilirse devreye girer.
2. Ortam değişkenleri (`frontend/.env.example`):

| Değişken | Açıklama |
|---|---|
| `REACT_APP_BACKEND_URL` | `https://api.magaza.com` |
| `REACT_APP_SITE_NAME` | Marka adı (sekme başlığı, alt metinler) |
| `REACT_APP_SITE_URL` | `https://magaza.com` |
| `REACT_APP_CANONICAL_HOST` | `magaza.com` (www → çıplak alan adı yönlendirmesi; boşsa kapalı) |
| `REACT_APP_DEFAULT_OG_IMAGE` | Sosyal paylaşım görseli URL'i |
| `API_URL`, `SITE_URL`, `SITE_NAME` | Kenar SEO fonksiyonu (`functions/_middleware.js`) için |

3. `magaza.com` ve `www.magaza.com` alan adlarını Pages projesine bağlayın.
4. **Marka görselleri:** `frontend/public/` altındaki `logo.png`, `logo.webp`, `og-image.jpg`,
   favicon dosyaları ve `apple-touch-icon.png` yer tutucudur — aynı adlarla kendi görsellerinizi koyun.

## 6. Panelden ilk ayarlar (sırasıyla)

`https://magaza.com/admin` → `ADMIN_INITIAL_EMAIL` ile giriş → parolayı değiştirin → MFA'yı açın.

1. **Ayarlar › İşletme Ayarları › Şirket Bilgileri:** mağaza adı, unvan, logo URL, site adresi,
   iletişim e-posta/telefon/WhatsApp, adres, vergi dairesi/no, IBAN, sosyal medya.
   E-postalar, SMS'ler, faturalar, kargo etiketi ve footer bu bilgilerden beslenir.
2. **Ayarlar › Ödeme:** iyzico API anahtarları (önce sandbox), havale banka hesapları, kapıda ödeme açık/kapalı.
3. **Ayarlar › Kargo:** MNG/DHL hesap bilgileri, kargo ücreti ve ücretsiz kargo eşiği.
4. **Ayarlar › Bildirimler:** e-posta sağlayıcısı (SMTP/SES/Brevo), NetGSM SMS + İYS marka kodu/alt kullanıcı.
5. **Entegrasyonlar:** Doğan e-Dönüşüm (e-Arşiv), Trendyol/Hepsiburada/Amazon/Temu satıcı hesapları,
   Meta/TikTok/Google piksel + CAPI token'ları, WhatsApp Business.
6. **Ayarlar › İşletme Kuralları:** iptal süreleri, stok eşikleri, terkedilmiş sepet e-postası,
   rapor eşikleri — varsayılanlar genel değerlerdir, işletmenize göre güncelleyin.
7. **Tasarım:** ana sayfa blokları, menü, footer, popup, e-posta şablonları; **CMS sayfaları**
   (KVKK, gizlilik, mesafeli satış, iade koşulları, SSS) — **hukuki metinleri kendi firmanıza
   göre mutlaka düzenleyin**.
8. **Katalog:** kategoriler → ürünler (Excel içe aktarma veya pazaryerinden çekme).
9. **Kullanıcılar & Roller:** personel hesapları ve rol yetkileri.

## 7. Canlıya çıkış kontrol listesi

- [ ] Test kart siparişi: sipariş `Ödeme Bekleniyor` başlar, 3D Secure sonrası `Onaylandı` olur.
- [ ] Başarısız/yarıda kalan kart ödemesi: sipariş ödenmiş görünmez, süre dolunca otomatik iptal + stok iadesi.
- [ ] Havale siparişi: banka bilgisi e-postası gider, dekont bildirimi panele düşer.
- [ ] Sipariş e-postaları ve SMS'lerde **kendi marka adınız** görünür.
- [ ] e-Arşiv test faturası kesilir (test modunda).
- [ ] Pazaryeri sipariş çekme ve stok gönderimi test hesabıyla çalışır.
- [ ] `ADMIN_INITIAL_PASSWORD` env'den silindi, MFA açık, `ENABLE_API_DOCS` kapalı.
- [ ] Yedekleme: Atlas otomatik yedek/point-in-time açık.

## 8. Güncelleme

Backend Railway'de, frontend Cloudflare Pages'te `main` dalına her push'ta otomatik yayınlanır.
Değişiklikleri önce ayrı bir dalda/test ortamında (ayrı DB) deneyin.
