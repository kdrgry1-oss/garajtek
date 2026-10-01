# E-Ticaret Platformu (Beyaz Etiket)

Türkiye pazarına göre kurulmuş, çok kanallı bir moda/perakende e-ticaret platformu:
vitrin (web), yönetim paneli, pazaryeri entegrasyonları, e-fatura, kargo, ödeme,
pazarlama ve raporlama. **Firmaya özel hiçbir değer kodda sabit değildir** — marka,
iletişim, alan adı ve entegrasyon kimlikleri ortam değişkenleri ve yönetim panelinden gelir.

Kurulum adımları: **[KURULUM.md](KURULUM.md)**

## Bileşenler

| Katman | Teknoloji | Dizin |
|---|---|---|
| Backend API + zamanlayıcı | Python 3.11, FastAPI, MongoDB (motor), APScheduler | `backend/` |
| Vitrin + yönetim paneli | React (CRA + craco), Tailwind | `frontend/` |
| Kenar (SEO/OG) katmanı | Cloudflare Pages Functions | `functions/` |
| Mobil (opsiyonel) | Capacitor | `frontend/ios`, `frontend/android`, `mobile-customer/` |
| Sunucu kurulum betikleri (opsiyonel, VPS) | systemd + nginx | `deploy/` |

## Başlıca modüller

- **Vitrin:** kategori/ürün, arama, favoriler, sepet, paylaşılan sepet, kombin, üyelere özel kategoriler, SALE menüsü (kampanya sayfaları), çok dilli SEO ve yapılandırılmış veri.
- **Ödeme:** iyzico 3D Secure (kendi kart formu), havale/EFT (dekont bildirimi), kapıda ödeme (opsiyonel), hediye çeki, puan.
- **Kampanya motoru:** yüzde/tutar indirim, X al Y öde, kupon, ilk sipariş, ödeme yöntemine göre indirim, istiflenebilirlik kuralları.
- **Sipariş & operasyon:** sipariş durumu yaşam döngüsü, iade/iptal, stok hareket defteri, otomatik iptal + mutabakat, ödeme mutabakatı.
- **Entegrasyonlar:** Trendyol, Hepsiburada, Amazon SP-API, Temu; MNG/DHL kargo; Doğan e-Dönüşüm (e-Arşiv/e-Fatura); NetGSM SMS + İYS; Brevo/SES/SMTP e-posta; Meta/TikTok/Google CAPI; WhatsApp Business.
- **Pazarlama:** e-posta kampanyaları, terkedilmiş sepet e-postası (izinli üyelere), influencer/PR takibi, atıf (UTM) raporları.
- **Raporlar:** satış, kâr & stok değeri, kategori içgörüleri, iade/iptal, ödeme, lokasyon.
- **Güvenlik:** RBAC, admin MFA, hesap/IP kilitleme, rate-limit, şifreli sır kasası (Fernet), olay/uyarı kayıtları, olay döngüsü kilitlenme izleyicisi.

## Lisans / kullanım

Bu kopya tek bir işletmenin kurulumu için hazırlanmıştır. Her kurulum **kendi veritabanı,
kendi sır anahtarları ve kendi entegrasyon hesaplarıyla** çalışmalıdır (bkz. KURULUM.md §1).
