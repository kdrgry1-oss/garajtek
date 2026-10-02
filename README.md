# E-Ticaret Platformu (Beyaz Etiket)

Türkiye pazarına göre kurulmuş, çok kanallı bir moda/perakende e-ticaret platformu:
vitrin (web), yönetim paneli, e-fatura, kargo, ödeme,
pazarlama ve raporlama. **Firmaya özel hiçbir değer kodda sabit değildir** — marka,
iletişim, alan adı ve entegrasyon kimlikleri ortam değişkenleri ve yönetim panelinden gelir.

Kurulum adımları: **[KURULUM.md](KURULUM.md)**

## Barındırma (garajtek.com)

Tek bir **SNET VDS** (2 vCPU / 2 GB RAM / Ubuntu 24.04) + **Cloudflare** (DNS, proxy, SSL). Mağaza,
yönetim paneli ve API aynı adreste (`https://garajtek.com`, API `/api`) nginx arkasında çalışır;
veritabanı sunucudaki SQLite dosyasıdır, görseller sunucu diskinde (`/media/`, Cloudflare önbellekli)
veya isteğe bağlı Cloudflare R2'de durur. Her gece 03:30'da yedek alınır (isteğe bağlı şifreli R2 kopyası).
`main`'e push → GitHub Actions frontend'i derler ve sunucuya dağıtır. Ayrıntılar: [`deploy/README.md`](deploy/README.md).

## Bileşenler

| Katman | Teknoloji | Dizin |
|---|---|---|
| Backend API + zamanlayıcı | Python 3.12, FastAPI, gömülü SQLite veritabanı (`backend/localdb`), APScheduler | `backend/` |
| Vitrin + yönetim paneli | React (CRA + craco), Tailwind | `frontend/` |
| Kenar (SEO/OG) katmanı (yalnız frontend Cloudflare Pages'te ise) | Cloudflare Pages Functions | `frontend/functions/` |
| Sunucu kurulumu + yedek + güncelleme | Ubuntu 24.04, nginx, systemd, Cloudflare | `deploy/`, `.github/workflows/deploy.yml` |

## Başlıca modüller

- **Vitrin:** kategori/ürün, arama, favoriler, sepet, paylaşılan sepet, kombin, üyelere özel kategoriler, SALE menüsü (kampanya sayfaları), çok dilli SEO ve yapılandırılmış veri.
- **Ödeme:** iyzico 3D Secure (kendi kart formu), havale/EFT (dekont bildirimi), kapıda ödeme (opsiyonel), hediye çeki, puan.
- **Kampanya motoru:** yüzde/tutar indirim, X al Y öde, kupon, ilk sipariş, ödeme yöntemine göre indirim, istiflenebilirlik kuralları.
- **Sipariş & operasyon:** sipariş durumu yaşam döngüsü, iade/iptal, stok hareket defteri, otomatik iptal + mutabakat, ödeme mutabakatı.
- **Entegrasyonlar:** iyzico; DHL E-Commerce (MNG), Aras ve PTT kargo; BirFatura (e-Arşiv/e-Fatura); NetGSM SMS + İYS; Brevo/SES/SMTP e-posta; Meta/TikTok/Google piksel + CAPI; WhatsApp Business ve Instagram.
- **Pazarlama:** e-posta kampanyaları, terkedilmiş sepet e-postası (izinli üyelere), atıf (UTM) raporları.
- **Raporlar:** satış, kâr & stok değeri, kategori içgörüleri, iade/iptal, ödeme, lokasyon.
- **Güvenlik:** RBAC, admin MFA, hesap/IP kilitleme, rate-limit, şifreli sır kasası (Fernet), olay/uyarı kayıtları, olay döngüsü kilitlenme izleyicisi.

## Lisans / kullanım

Bu kopya tek bir işletmenin kurulumu için hazırlanmıştır. Her kurulum **kendi veritabanı,
kendi sır anahtarları ve kendi entegrasyon hesaplarıyla** çalışmalıdır (bkz. KURULUM.md §1).
