# Yeni Marka — Tek Sunucu Kurulumu (2 GB RAM / 5 GB disk)

Pazaryeri, İYS ve veri senkronu OLMAYAN bir marka için tek VPS kurulumu.
Çalışanlar: mağaza + panel, iyzico ödeme, kargo, e-fatura, e-posta.

> Gereken: **Ubuntu 24.04 LTS** (22.04'teki Python 3.10 yetmez), **root/SSH erişimi**. (Yalnız cPanel paneli varsa bu kurulum
> yapılamaz — MongoDB kurulamaz ve sürekli çalışan süreç tutulamaz.)

## 1) DNS (alan adı sağlayıcısında)

| Kayıt | Tip | Hedef |
|---|---|---|
| `yenimarka.com` | A | VPS IP |
| `www` | A | VPS IP |
| `api` | A | VPS IP |

Görseller Cloudflare R2'de durur (`cdn.yenimarka.com` → R2 public bucket). Diskte görsel
tutmayın; 5 GB kısa sürede dolar.

## 2) Kurulum (tek komut)

```bash
ssh root@SUNUCU_IP
curl -fsSL https://raw.githubusercontent.com/<repo>/main/deploy/install.sh -o install.sh
# ya da dosyayı scp ile kopyalayın
bash install.sh yenimarka.com api.yenimarka.com
```

Script şunları yapar: 2 GB swap, MongoDB 8 (önbellek 512 MB'a sabit), Python sanal ortamı,
bağımlılıklar, systemd servisi, Caddy ile otomatik SSL, günlük yedek (03:00).

## 3) Ayarlar

`/opt/store/backend/.env` dosyasını doldurun (kurulumda `APP_SLUG` verdiyseniz `/opt/<APP_SLUG>`) (`deploy/env.example` kopyasıdır):
zorunlu olanlar `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `CORS_ORIGINS`, iyzico anahtarları,
R2 anahtarları, SMTP, `ADMIN_INITIAL_EMAIL` + `ADMIN_INITIAL_PASSWORD` (ilk yönetici). Sonra: `systemctl restart store-api`.

## 4) Panel içi kapatılacaklar (bu markada kullanılmayanlar)

Ayarlar → Entegrasyonlar: Trendyol, Hepsiburada, Amazon, Temu **bağlanmaz** (anahtar
girilmezse zamanlanmış işleri de çalışmaz). İYS/SMS kullanılmayacaksa NetGSM boş bırakılır.

## 5) Kaynak beklentisi (ölçüm)

| | |
|---|---|
| Backend (pazaryerisiz) | ~250–300 MB |
| MongoDB (önbellek 512 MB) | ~700 MB |
| İşletim sistemi + Caddy | ~250 MB |
| **Toplam** | **~1,2 GB / 2 GB** |

Disk: OS ~2 GB + Python paketleri ~0,7 GB + MongoDB ~0,4 GB → veri için ~1,8 GB kalır.
Pazaryeri aynaları olmadığı için veri yavaş büyür; yedekler sunucu dışına alınmalı.

## 6) Veritabanı aynı sunucuda — dikkat edilecek tek şey

MongoDB uygulamayla **aynı sunucuda** çalışır (kurulum bunu yapar): ek ücret yok, ağ
gecikmesi yok, yönetim tek yerden. Bedeli: sunucu giderse veri de gider. Bu yüzden
`deploy/backup.sh` her gece `mongodump` alır, **Cloudflare R2'ye yükler** (R2 anahtarları
.env'de tanımlıysa) ve diskte yalnız son 2 kopyayı bırakır — 5 GB'lık diskte yedekler yer
tutmasın diye.

Geri yükleme:
```bash
mongorestore --gzip --archive=/var/backups/store/<dosya>.gz --drop
```

MongoDB'yi ileride ayırmak isterseniz (MongoDB Atlas ücretsiz katman) tek yapılacak
`.env` içindeki `MONGO_URL`'i değiştirmek; kod değişmez.

## 7) Frontend

`frontend/` derlenip `/var/www/yenimarka` altına konur (Caddy servis eder) ya da
Cloudflare Pages'e verilir. Derleme sunucuda 2 GB RAM'i zorlar; **kendi bilgisayarınızda
derleyip** `build/` klasörünü kopyalamanız önerilir:

```bash
cd frontend && CI=true npx craco build
scp -r build/* root@SUNUCU_IP:/var/www/yenimarka/
```
