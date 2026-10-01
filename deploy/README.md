# deploy/ — garajtek.com tek sunucu dağıtımı

Hedef: **1 × SNET VDS** (2 vCPU, 2 GB RAM, 40 GB NVMe, Ubuntu 24.04 LTS, root SSH) + **Cloudflare**
(DNS, proxy, SSL; isteğe bağlı R2 ve Pages). Ayrı veritabanı sunucusu, Railway, MongoDB **yok** —
veri gömülü SQLite dosyasındadır (`DB_PATH=/opt/garajtek/data/store.db`).

Adım adım (yeni başlayanlar için) kurulum rehberi: **[../KURULUM.md](../KURULUM.md)**.

## Mimari

```
ziyaretçi ──HTTPS──▶ Cloudflare (turuncu bulut, SSL: Full (strict), önbellek, WAF)
                         │  Origin Certificate ile HTTPS + X-Edge-Secret başlığı
                         ▼
                 VDS :443  nginx ──┬── /            → /var/www/garajtek  (React SPA, index.html fallback)
                                   ├── /static/     → 1 yıl immutable önbellek
                                   ├── /media/      → /opt/garajtek/media (yüklenen görseller)
                                   └── /api/, /sitemap.xml, /robots.txt, /llms.txt
                                                    → 127.0.0.1:8001 uvicorn (garajtek-api, 1 işçi)
                                                         └── SQLite: /opt/garajtek/data/store.db
```

* **Aynı köken (same-origin)**: mağaza ve API `https://garajtek.com` altında; frontend
  `REACT_APP_BACKEND_URL=https://garajtek.com` ile derlenir → CORS derdi yok.
  `api.garajtek.com` de aynı nginx'te tanımlıdır (Seçenek B için; DNS kaydı açılmazsa kullanılmaz).
* **Gerçek ziyaretçi IP'si**: nginx `real_ip_header CF-Connecting-IP` (yalnız Cloudflare
  aralıklarından), API'ye `X-Forwarded-For` olarak **üzerine yazarak** iletir; uvicorn
  `--proxy-headers --forwarded-allow-ips 127.0.0.1`. Backend ayrıca `CF_EDGE_SECRET` ile
  isteğin Cloudflare'den geldiğini doğrular (Cloudflare Transform Rule `X-Edge-Secret` ekler).
* **Cloudflare kilidi**: ana site sunucu bloğu, Cloudflare dışından gelen bağlantıyı kapatır
  (`/etc/nginx/snippets/garajtek-cf-lock.conf`). ufw 80/443'ü varsayılan olarak herkese açar,
  çünkü aynı sunucudaki posta/webmail (`deploy/mail/`, `mail.garajtek.com`, gri bulut) buna ihtiyaç
  duyar. Posta yoksa `--cf-firewall` ile 80/443 ufw'de de yalnız Cloudflare'e açılır.
* **Medya**: R2 tanımlı değilse yüklemeler `MEDIA_DIR`'e yazılır ve `https://garajtek.com/media/...`
  adresinden servis edilir (Cloudflare önbelleğe alır). `R2_*` doldurulursa yeni yüklemeler R2'ye gider.

## Dosyalar

| Dosya | Sunucudaki yeri / görevi |
|---|---|
| `install.sh` | İlk kurulum (idempotent): paketler, 2 GB swap, `garajtek` kullanıcısı, `/opt/garajtek`, `.env` üretimi (gizli anahtarlar otomatik), geçici sertifika, nginx, systemd, ufw, fail2ban, zamanlayıcılar |
| `update.sh` | `garajtek-update`: git pull → pip (yalnız requirements değiştiyse) → sözdizimi denetimi → (frontend yayınla) → yeniden başlat → sağlık kontrolü |
| `backup.sh` | `garajtek-backup`: SQLite çevrimiçi yedek + medya + .env → `/var/backups/garajtek` (7 gün), isteğe bağlı şifreli R2 kopyası |
| `restore.sh` | `garajtek-restore <dosya \| r2:anahtar>`: güvenlik kopyası alıp geri yükler |
| `cloudflare-ips.sh` | `garajtek-cloudflare-ips`: CF IP aralıklarını nginx (realip + kilit) ve isteğe bağlı ufw için günceller (haftalık) |
| `nginx/garajtek.conf` | `/etc/nginx/sites-available/garajtek` (ana site + www yönlendirme + api alt alan adı) |
| `nginx/default.conf` | `/etc/nginx/sites-available/garajtek-default` (:80 ACME `/var/www/html` + HTTPS yönlendirme, :443 bilinmeyen ad reddi) |
| `nginx/proxy.conf`, `nginx/security-headers.conf` | `/etc/nginx/snippets/garajtek-*.conf` |
| `systemd/*` | `garajtek-api.service`, `garajtek-backup.timer` (03:30), `garajtek-cloudflare-ips.timer` (haftalık) |
| `env.example` | `/opt/garajtek/backend/.env` şablonu |
| `mail/` | Aynı sunucuda posta (Postfix/Dovecot/Roundcube) — bkz. `mail/README.md` |

## Hızlı komutlar

```bash
# İlk kurulum (kod sunucudaysa)
bash /opt/garajtek/deploy/install.sh garajtek.com --admin-email siz@ornek.com

systemctl status garajtek-api          # durum
journalctl -u garajtek-api -f          # canlı log
garajtek-update                        # git pull + yeniden başlat (sunucuda git deposu varsa)
garajtek-backup                        # şimdi yedek al
garajtek-restore                       # yedekleri listele / geri yükle
systemctl list-timers 'garajtek*'      # zamanlayıcılar
nginx -t && systemctl reload nginx     # nginx ayarını yeniden yükle
```

## Frontend nerede derlenir?

| Yol | Ne zaman |
|---|---|
| **GitHub Actions** (`.github/workflows/deploy.yml`) — **önerilen** | `main`'e push → GitHub'da derlenir, rsync ile gönderilir, `update.sh` çalışır. Sunucuda Node gerekmez. |
| Kendi bilgisayarınızda | `cd frontend && REACT_APP_BACKEND_URL=https://garajtek.com yarn build` → `rsync -a build/ root@IP:/opt/garajtek/frontend-build/` → sunucuda `garajtek-update --no-pull --frontend /opt/garajtek/frontend-build` |
| Sunucuda (`update.sh --build-frontend`) | Son çare: Node 20 kurulmalı, 2 GB RAM'de 5–15 dk sürer ve swap'a düşer; site bu sırada yavaşlar. |
| **Cloudflare Pages** (Seçenek B) | Frontend Pages'te, API `api.garajtek.com` → VDS. Kenar SEO fonksiyonları (`frontend/functions/`) çalışır. Bkz. KURULUM.md §10. |

## Kaynak beklentisi (2 GB RAM)

| Bileşen | Bellek |
|---|---|
| garajtek-api (uvicorn, 1 işçi, SQLite dahil) | ~300–500 MB (sert sınır `MemoryMax=900M`) |
| nginx | ~15 MB |
| İşletim sistemi + journald + fail2ban | ~250 MB |
| Posta yığını (opsiyonel: Postfix + Dovecot + OpenDKIM + php-fpm/Roundcube) | ~150–250 MB |
| **Toplam** | **~0,8–1,1 GB** — geri kalanı disk önbelleği; 2 GB swap tepe anlar için |

Disk (40 GB): OS ~3 GB, Python ortamı ~0,6 GB, veritabanı + medya büyüdükçe; yedekler 7 gün.
