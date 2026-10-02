# Kurulum Rehberi — garajtek.com (SNET VDS + Cloudflare)

Bu rehber mağazayı **sıfırdan, tek bir sunucuda** yayına alır. Teknik geçmiş gerekmez; komutları
sırayla kopyala-yapıştır yapmanız yeterli.

**Gerekenler**

| | |
|---|---|
| Sunucu | SNET VDS — 2 vCPU, 2 GB RAM, 40 GB NVMe, **Ubuntu 24.04 LTS**, root SSH erişimi |
| Alan adı | `garajtek.com` (Cloudflare hesabına eklenecek — ücretsiz plan yeterli) |
| GitHub | Bu deponun bulunduğu hesap (kodu sunucuya otomatik göndermek için) |
| Bilgisayarınızda | Terminal (Windows: PowerShell veya Windows Terminal — `ssh` yerleşik gelir) |

Başka hiçbir hizmet (Railway, MongoDB Atlas, ayrı veritabanı sunucusu…) **gerekmez**. Veritabanı,
uygulamanın içinde çalışan SQLite dosyasıdır: `/opt/garajtek/data/store.db`.

> Tahmini süre: 1–2 saat (Cloudflare'in alan adını etkinleştirmesi birkaç dakika–birkaç saat sürebilir).

---

## 1. Altın kurallar

1. `/opt/garajtek/backend/.env` dosyasındaki **`SECRETS_MASTER_KEY` ve `JWT_SECRET`'i asla
   değiştirmeyin/kaybetmeyin.** Panelden girilen tüm entegrasyon şifreleri (iyzico, kargo, e-posta…)
   bu anahtarla şifrelenir. Gece yedekleri `.env`'i de içerir.
2. Uygulama **tek işçiyle** çalışır (`--workers 1`). Bunu artırmayın — gömülü veritabanı katmanı tek süreç varsayar.
3. Yedeklerin **sunucu dışına** da çıkması gerekir (§9). Sunucu giderse yalnız sunucudaki yedek de gider.
4. Canlıya almadan önce iyzico'yu **sandbox (test) modunda** deneyin.

## 2. Mimari (kısaca)

```
ziyaretçi ─▶ Cloudflare (turuncu bulut: SSL, önbellek, saldırı koruması)
              ─▶ VDS: nginx :443 ─┬─ /          React mağaza + panel (/var/www/garajtek)
                                  ├─ /media/    yüklenen görseller (/opt/garajtek/media)
                                  └─ /api/      Python API (garajtek-api, 127.0.0.1:8001) ─▶ SQLite
```

Mağaza ve API **aynı adreste** çalışır (`https://garajtek.com` ve `https://garajtek.com/api`).
Frontend GitHub'da derlenir ve sunucuya hazır gönderilir (2 GB RAM'li sunucuda derlemek yavaştır).

---

## 3. Cloudflare

### 3.1 Alan adını Cloudflare'e ekleyin
1. <https://dash.cloudflare.com> → **Add a domain** → `garajtek.com` → **Free** plan.
2. Cloudflare'in verdiği iki **nameserver**'ı alan adını aldığınız firmanın panelinde (ör. SNET /
   isimtescil / GoDaddy) eski nameserver'ların yerine yazın. Etkinleşince Cloudflare e-posta atar.

### 3.2 DNS kayıtları (DNS › Records)

| Tip | Ad | İçerik | Proxy |
|---|---|---|---|
| A | `@` (garajtek.com) | VDS IP adresi | **Turuncu (Proxied)** |
| A | `www` | VDS IP adresi | **Turuncu (Proxied)** |
| A | `api` | VDS IP adresi | Turuncu — *yalnız Seçenek B (§10) için; şimdilik gerekmez* |
| AAAA | `@`, `www` | VDS IPv6 adresi | Turuncu — *yalnız sunucunuzda IPv6 varsa* |

Posta kullanacaksanız (`mail.garajtek.com`, MX, SPF, DKIM, DMARC) kayıtları §11'deki rehberdedir;
**`mail` kaydı gri bulut (DNS only) olmalıdır.**

### 3.3 Origin Certificate (Cloudflare ↔ sunucu arası şifreleme)
1. **SSL/TLS › Origin Server › Create Certificate**.
2. "Generate private key and CSR with Cloudflare", anahtar türü **RSA (2048)**,
   host adları: `garajtek.com` ve `*.garajtek.com`, geçerlilik **15 yıl** → **Create**.
3. Ekranda iki kutu çıkar: **Origin Certificate** ve **Private Key**. Sayfayı kapatmayın —
   özel anahtar bir daha gösterilmez. Bunları sunucu kurulduktan sonra (§5'ten sonra) yapıştıracaksınız:

```bash
ssh root@SUNUCU_IP
nano /etc/ssl/cloudflare/garajtek.com.pem     # "Origin Certificate" kutusunun TAMAMI (BEGIN…END dahil)
nano /etc/ssl/cloudflare/garajtek.com.key     # "Private Key" kutusunun TAMAMI
rm -f /etc/ssl/cloudflare/garajtek.com.GECICI
nginx -t && systemctl reload nginx             # "syntax is ok" görmelisiniz
```

> nano: yapıştırmak için sağ tık / Ctrl+Shift+V, kaydetmek için **Ctrl+O, Enter**, çıkmak için **Ctrl+X**.
> Kurulum betiği bu dosyalar yoksa geçici (self-signed) bir sertifika üretir; site o hâliyle
> yalnız "Full" modunda çalışır. Origin Certificate'ı yapıştırdıktan sonra 3.4'e geçin.

### 3.4 SSL/TLS ayarları
- **SSL/TLS › Overview → Full (strict)** (Origin Certificate yapıştırılmadan önce geçici olarak "Full").
  **"Flexible" KULLANMAYIN** — sonsuz yönlendirme döngüsü oluşur.
- **SSL/TLS › Edge Certificates**: *Always Use HTTPS* = Açık, *Minimum TLS Version* = 1.2,
  *Automatic HTTPS Rewrites* = Açık.

### 3.5 Transform Rule: X-Edge-Secret (gerçek ziyaretçi IP doğrulaması)
Backend, isteğin gerçekten Cloudflare'den geldiğini bu gizli başlıkla doğrular (hız sınırı,
hesap kilitleme, ödeme sağlayıcılarına giden IP'ler doğru olur).

1. Sunucuda değeri öğrenin: `grep CF_EDGE_SECRET /opt/garajtek/backend/.env`
   (kurulum bunu otomatik üretir; `/root/garajtek-ilk-giris.txt` içinde de yazar).
2. **Rules › Transform Rules › Modify Request Header › Create rule**
   - Ad: `edge secret`
   - *If incoming requests match…*: **All incoming requests**
   - *Then…*: **Set static** — Header name: `X-Edge-Secret` — Value: (1. adımdaki değer)
   - **Deploy**.

Bu kural yoksa site yine çalışır (nginx gerçek IP'yi zaten `CF-Connecting-IP`'den çözer); kural,
ikinci bir güvenlik katmanıdır.

### 3.6 Önbellek ve sınırlar
- Varsayılan önbellek ayarları doğrudur: `/static/*` ve `/media/*` dosyaları uzantısından dolayı
  Cloudflare'de önbelleğe alınır; `/api/*` alınmaz. **"Cache Everything" kuralını `/api`, `/admin`
  veya tüm siteye uygulamayın.**
- Ücretsiz planda tek istek en fazla **100 MB** olabilir (video yükleme sınırı da 100 MB).
- *Speed › Optimization*: Brotli açık. Rocket Loader **kapalı** kalsın (React ile sorun çıkarır).

---

## 4. Sunucuya ilk bağlantı

SNET panelinden sunucunun IP adresini ve root parolasını alın.

```bash
ssh root@SUNUCU_IP        # ilk bağlantıda "yes" yazın, parolayı girin
apt update && apt -y upgrade && reboot      # güncelle ve yeniden başlat (1 dk sonra tekrar bağlanın)
```

**Önerilir — parola yerine SSH anahtarı:** kendi bilgisayarınızda `ssh-keygen -t ed25519` ve
`ssh-copy-id root@SUNUCU_IP` (Windows'ta: `type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@SUNUCU_IP "cat >> ~/.ssh/authorized_keys"`).

---

## 5. Kurulum

İki yol var; **A önerilir** (sonraki güncellemeler de otomatik olur).

### 5.A GitHub Actions ile (önerilen)
1. Dağıtım için bir SSH anahtarı üretin (kendi bilgisayarınızda):
   ```bash
   ssh-keygen -t ed25519 -N "" -f garajtek-deploy -C github-deploy
   ```
2. Açık anahtarı sunucuya ekleyin:
   ```bash
   ssh root@SUNUCU_IP "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys" < garajtek-deploy.pub
   ```
3. GitHub → depo → **Settings › Secrets and variables › Actions › New repository secret**:

   | Secret | Değer |
   |---|---|
   | `VDS_HOST` | Sunucu IP adresi (alan adı değil) |
   | `VDS_USER` | `root` |
   | `VDS_SSH_KEY` | `garajtek-deploy` dosyasının (özel anahtar) **tüm** içeriği |
   | `VDS_KNOWN_HOSTS` | *(önerilir)* `ssh-keyscan -H SUNUCU_IP` çıktısı |

   *Variables* sekmesine isterseniz `REACT_APP_SITE_NAME` = `Garajtek` ekleyin.
4. **Actions › Deploy (VDS) › Run workflow**. İlk çalıştırma 10–15 dk sürer: frontend derlenir,
   kod gönderilir, sunucuda `deploy/install.sh garajtek.com` otomatik çalışır.
5. Bittiğinde sunucuda ilk giriş bilgilerini okuyun: `ssh root@SUNUCU_IP cat /root/garajtek-ilk-giris.txt`

İlk yönetici e-postası varsayılan olarak `admin@garajtek.com` olur. Kendi adresinizi kullanmak için
4. adımdan **önce** *Variables* sekmesine `ADMIN_EMAIL` = `siz@ornek.com` ekleyin (yalnız ilk kurulumda okunur).

### 5.B Sunucuda doğrudan (depo herkese açıksa ya da kodu kendiniz kopyalarsanız)
```bash
ssh root@SUNUCU_IP
git clone https://github.com/kdrgry1-oss/garajtek.git /opt/garajtek
#  (özel depo: kendi bilgisayarınızdan  scp -r garajtek root@SUNUCU_IP:/opt/garajtek )
bash /opt/garajtek/deploy/install.sh garajtek.com --admin-email siz@ornek.com
cat /root/garajtek-ilk-giris.txt
```
Frontend'i ardından §7.2 ya da §5.A ile gönderin (kurulum o zamana kadar "Mağaza hazırlanıyor"
sayfası gösterir).

### Kurulum betiği ne yapar?
2 GB swap, saat dilimi (İstanbul), gerekli paketler, `garajtek` sistem kullanıcısı, Python 3.12
sanal ortamı + bağımlılıklar, `.env` (gizli anahtarlar otomatik üretilir), geçici sertifika,
nginx, `garajtek-api` servisi, güvenlik duvarı (ufw: SSH + 80 + 443), fail2ban (SSH kaba kuvvet
koruması), gece yedeği (03:30) ve haftalık Cloudflare IP güncellemesi. Tekrar çalıştırmak güvenlidir;
mevcut `.env` ve veriler korunur.

Seçenekler: `--cf-firewall` (80/443'ü güvenlik duvarında da yalnız Cloudflare'e aç — **posta
kuruluysa kullanmayın**), `--no-cf-lock` (sitenin doğrudan IP ile açılmasına izin ver — test için).

### Kurulumdan sonra
1. §3.3: Origin Certificate'ı yapıştırın → §3.4: SSL modunu **Full (strict)** yapın.
2. §3.5: Transform Rule'u ekleyin.
3. Kontrol: tarayıcıda `https://garajtek.com` ve `https://garajtek.com/api/health`
   (`{"status":"healthy",…}` görmelisiniz).

---

## 6. İlk yönetici girişi ve panel ayarları

`https://garajtek.com/admin` → `/root/garajtek-ilk-giris.txt`'teki e-posta + parola →
**parolayı değiştirin** → **MFA'yı (iki adımlı doğrulama) açın**. Sonra sunucuda:

```bash
nano /opt/garajtek/backend/.env      # ADMIN_INITIAL_PASSWORD= satırını boşaltın
systemctl restart garajtek-api
rm /root/garajtek-ilk-giris.txt
```

Panelde sırasıyla:
1. **Ayarlar › İşletme Ayarları › Şirket Bilgileri:** mağaza adı, unvan, logo, site adresi
   (`https://garajtek.com`), iletişim, adres, vergi bilgileri, IBAN. E-postalar, faturalar ve footer buradan beslenir.
2. **Ayarlar › Ödeme:** iyzico anahtarları (önce sandbox), havale hesapları.
3. **Ayarlar › Kargo:** kargo hesabı, ücret ve ücretsiz kargo eşiği.
4. **Ayarlar › Bildirimler:** e-posta sağlayıcısı (SMTP — §11'deki kendi posta sunucunuz olabilir).
5. **Tasarım:** ana sayfa, menü, footer; **CMS sayfaları** (KVKK, gizlilik, mesafeli satış, iade) —
   **hukuki metinleri firmanıza göre mutlaka düzenleyin.**
6. **Katalog:** kategoriler → ürünler (Excel içe aktarma). Görseller sunucu diskine
   (`/opt/garajtek/media`) kaydedilir ve Cloudflare üzerinden hızlıca sunulur.
7. **Kullanıcılar & Roller:** personel hesapları.
8. **Entegrasyonlar › BirFatura (e-Fatura):** token oluşturun, BirFatura panelinde "Özel Entegrasyon"
   mağazası açıp site adresini + token'ı girin, test edip açın. Ayrıntı: [`docs/BIRFATURA.md`](docs/BIRFATURA.md).

Kullanılmayan entegrasyonlar (ör. NetGSM SMS/İYS, WhatsApp, Instagram) boş bırakılır;
anahtar girilmedikçe ilgili zamanlanmış işler çalışmaz.

---

## 7. Güncellemeler

### 7.1 Otomatik (önerilen)
`main` dalına her push'ta **Deploy (VDS)** iş akışı çalışır: frontend derlenir, sunucuya gönderilir,
bağımlılıklar (yalnız değiştiyse) kurulur, servis yeniden başlatılır ve sağlık kontrolü yapılır.
Sağlık kontrolü başarısız olursa iş akışı kırmızı olur ve son loglar Actions çıktısında görünür.
Yayın sırasında site ~5–15 saniye "502" verebilir (tek işçi yeniden başlarken).

### 7.2 Frontend'i kendi bilgisayarınızda derleyip göndermek
```bash
cd frontend
yarn install --frozen-lockfile
REACT_APP_BACKEND_URL=https://garajtek.com REACT_APP_SITE_URL=https://garajtek.com REACT_APP_SITE_NAME=Garajtek npx craco build
rsync -a --delete build/ root@SUNUCU_IP:/opt/garajtek/frontend-build/
ssh root@SUNUCU_IP garajtek-update --no-pull --frontend /opt/garajtek/frontend-build
```

### 7.3 Sunucuda git ile (5.B kurulumu)
```bash
garajtek-update                     # git pull + bağımlılık + yeniden başlat + sağlık kontrolü
garajtek-update --build-frontend    # frontend'i SUNUCUDA derler — önce Node 20 kurun:
#   curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt install -y nodejs && corepack enable
#   2 GB RAM'de 5–15 dk sürer, bu sırada site yavaşlar. Mümkünse 7.1 / 7.2'yi kullanın.
```

---

## 8. Ortam değişkenleri (`/opt/garajtek/backend/.env`)

Tam liste ve açıklamalar: [`deploy/env.example`](deploy/env.example). Değiştirdikten sonra
`systemctl restart garajtek-api`. **Yorumları ayrı satıra yazın** (`ANAHTAR=değer # yorum` yazmayın).

| Değişken | Açıklama |
|---|---|
| `DB_PATH` | SQLite dosyası — `/opt/garajtek/data/store.db` |
| `SITE_URL`, `PUBLIC_API_URL`, `CORS_ORIGINS` | `https://garajtek.com` (Seçenek B'de API `https://api.garajtek.com`) |
| `JWT_SECRET`, `SECRETS_MASTER_KEY` | Otomatik üretilir — **değiştirmeyin** |
| `ADMIN_INITIAL_EMAIL` / `_PASSWORD` | İlk süper yönetici (e-posta kalıcı; parola ilk girişten sonra silinir) |
| `CF_EDGE_SECRET` | Cloudflare Transform Rule değeri (§3.5) |
| `MEDIA_DIR`, `MEDIA_PUBLIC_URL` | Görsel deposu (sunucu diski). `MEDIA_PUBLIC_URL` boşsa `SITE_URL/media` |
| `R2_*` | *İsteğe bağlı* — görselleri Cloudflare R2'de tutmak için (hepsi dolu olmalı) |
| `BACKUP_R2_*`, `BACKUP_PASSPHRASE` | Sunucu dışı yedek (§9) |
| `ALERT_SMTP_*`, `ALERT_TO_EMAIL` | Sistem uyarı e-postaları |
| `ADMIN_MFA_ENFORCE` | `1` → yöneticilere MFA zorunlu |

---

## 9. Yedekleme ve geri yükleme

Her gece **03:30**'da `garajtek-backup` çalışır: veritabanının çevrimiçi kopyası (site durmaz) +
yüklenen görseller + `.env` tek bir dosyada → `/var/backups/garajtek/garajtek-YYYYAAGG-SSDDss.tar.gz`.
Son **7** yedek tutulur.

```bash
garajtek-backup                          # şimdi yedek al
ls -lh /var/backups/garajtek/            # yedekler
systemctl list-timers garajtek-backup    # bir sonraki çalışma
journalctl -u garajtek-backup -n 50      # son yedeğin çıktısı
```

**Sunucu dışı yedek (şiddetle önerilir) — Cloudflare R2, ilk 10 GB ücretsiz:**
1. Cloudflare › **R2** › *Create bucket* → `garajtek-yedek` (**public erişim AÇMAYIN**).
2. R2 › *Manage API Tokens* › *Create API token* → izin: **Object Read & Write**, yalnız bu bucket.
   Verilen *Access Key ID*, *Secret Access Key* ve *S3 endpoint* (`https://<hesap-id>.r2.cloudflarestorage.com`) değerlerini not edin.
3. `.env`'e yazın:
   ```
   BACKUP_R2_BUCKET=garajtek-yedek
   BACKUP_R2_ENDPOINT=https://<hesap-id>.r2.cloudflarestorage.com
   BACKUP_R2_ACCESS_KEY_ID=...
   BACKUP_R2_SECRET_ACCESS_KEY=...
   BACKUP_PASSPHRASE=uzun-rastgele-bir-parola
   ```
   `BACKUP_PASSPHRASE`'i parola yöneticinize de kaydedin — onsuz şifreli yedek açılamaz.
4. Deneyin: `garajtek-backup` → çıktıda "R2'ye yüklendi" görmelisiniz.
5. (Önerilir) Bucket › *Settings* › *Object lifecycle rules*: `backups/` önekini 30 gün sonra sil.

**Geri yükleme:**
```bash
garajtek-restore                                         # yerel yedekleri listeler
garajtek-restore garajtek-20261001-033000.tar.gz         # yerel yedekten
garajtek-restore --list-r2                               # R2'deki yedekler
garajtek-restore r2:backups/garajtek-20261001-033000.tar.gz.enc
```
Geri yükleme önce mevcut veritabanını `/var/backups/garajtek/pre-restore-…` altına kopyalar.
**Yeni bir sunucuya taşıma:** yeni sunucuda kurulumu yapın (§5), sonra
`garajtek-restore r2:… --with-env` (eski `.env` ve anahtarlar da gelir) — `.env`'e önce
`BACKUP_R2_*` ve `BACKUP_PASSPHRASE` değerlerini elle yazın.

---

## 10. Seçenek B: Frontend Cloudflare Pages'te

Varsayılan kurulumda (Seçenek A) her şey VDS'tedir — en az parça, CORS yok, tek yerden yönetim.
**Öneri: A ile başlayın.** B'nin artısı: `frontend/functions/` kenar fonksiyonları çalışır (her ürün/
kategori sayfası için ilk HTML'e doğru başlık/açıklama/JSON-LD enjekte eder → daha iyi SEO önizlemesi)
ve statik dosyalar sunucuya hiç uğramaz. Eksisi: iki ayrı dağıtım yeri ve bir alt alan adı.

1. DNS: `api` A kaydı → VDS IP (turuncu). `garajtek.com`/`www` kayıtlarını Pages'e devredeceksiniz.
2. Cloudflare › **Workers & Pages › Create › Pages › Connect to Git** → bu depo:
   - Root directory: `frontend` — Build command: `yarn install --frozen-lockfile && npx craco build` — Output: `build`
   - Ortam değişkenleri: `REACT_APP_BACKEND_URL=https://api.garajtek.com`, `REACT_APP_SITE_URL=https://garajtek.com`,
     `REACT_APP_SITE_NAME=Garajtek`, `NODE_VERSION=20`, kenar fonksiyonları için `API_BASE=https://api.garajtek.com`.
   - *Custom domains*: `garajtek.com`, `www.garajtek.com`.
3. Sunucuda `.env`: `PUBLIC_API_URL=https://api.garajtek.com`, `BACKEND_URL=https://api.garajtek.com`,
   `MEDIA_PUBLIC_URL=https://api.garajtek.com/media` → `systemctl restart garajtek-api`.
4. GitHub › Settings › Variables: `FRONTEND_ON_PAGES=true` (Actions artık yalnız backend'i gönderir).

---

## 11. E-posta sunucusu (isteğe bağlı, aynı VDS)

`info@garajtek.com` gibi adresler ve webmail (`https://mail.garajtek.com`) için Postfix + Dovecot +
OpenDKIM + Roundcube kurulumu: **[deploy/mail/README.md](deploy/mail/README.md)**.
Notlar: `mail.garajtek.com` DNS kaydı **gri bulut** olmalı; posta kuruluysa `install.sh`'i
`--cf-firewall` ile çalıştırmayın (webmail ve sertifika için 80/443 herkese açık kalmalı — ana site
yine nginx seviyesinde yalnız Cloudflare'e açıktır). SNET'ten sunucu IP'si için **PTR (ters DNS)**
kaydını `mail.garajtek.com` olarak isteyin; çoğu VDS'te 25. port da talep üzerine açılır.

---

## 12. Sorun giderme

| Belirti | Kontrol |
|---|---|
| **Cloudflare 521** (Web server is down) | `systemctl status nginx`; `ufw status` (80/443 açık mı?); DNS IP doğru mu? |
| **Cloudflare 525/526** (SSL handshake / invalid certificate) | §3.3 sertifika dosyaları doğru mu (`.pem` = sertifika, `.key` = anahtar)? `nginx -t`. Geçici sertifikayla mod "Full (strict)" ise "Full"a alın. |
| **Cloudflare 522** (timeout) | Sunucu açık mı (SNET panel)? `ufw status`; `--cf-firewall` kullandıysanız `garajtek-cloudflare-ips` |
| **502 Bad Gateway** | API çalışmıyor: `systemctl status garajtek-api`, `journalctl -u garajtek-api -n 100` |
| **Sonsuz yönlendirme (ERR_TOO_MANY_REDIRECTS)** | Cloudflare SSL modu "Flexible" olmamalı → **Full (strict)** |
| Sunucu IP'siyle site açılmıyor | Normal: ana site yalnız Cloudflare üzerinden açılır (`--no-cf-lock` ile kapatılabilir) |
| Panel açılıyor ama veriler gelmiyor | `curl -s https://garajtek.com/api/health`; tarayıcı konsolunda `/api` istekleri `https://garajtek.com/api/...` adresine mi gidiyor? (Frontend `REACT_APP_BACKEND_URL` ile derlenmiş olmalı) |
| Görsel yükleniyor ama görünmüyor | `.env`'de `MEDIA_DIR=/opt/garajtek/media` ve `SITE_URL=https://garajtek.com` mi? `ls /opt/garajtek/media/uploads` |
| Büyük video yüklenmiyor (413) | Cloudflare ücretsiz plan sınırı 100 MB |
| Bellek | `free -h`; `systemctl status garajtek-api` (Memory satırı). API 900 MB'ı aşarsa systemd yeniden başlatır. |
| Disk | `df -h`; `du -sh /opt/garajtek/* /var/backups/garajtek` |
| Yedek çalıştı mı? | `journalctl -u garajtek-backup -n 50` |

Faydalı komutlar: `journalctl -u garajtek-api -f` (canlı log), `systemctl restart garajtek-api`,
`tail -f /var/log/nginx/garajtek.error.log`, `nginx -t && systemctl reload nginx`.

---

## 13. Kaynak beklentisi (2 GB RAM / 40 GB disk)

| Bileşen | Bellek |
|---|---|
| garajtek-api (Python, tek işçi, SQLite dahil) | ~300–500 MB (sınır 900 MB) |
| nginx + işletim sistemi + fail2ban | ~270 MB |
| Posta yığını (kuruluysa) | ~150–250 MB |
| **Toplam** | **~0,8–1,1 GB** + 2 GB swap tepe anlar için |

Bu yapı günde birkaç bin ziyaretçiyi rahatça taşır; statik dosyalar ve görseller Cloudflare
önbelleğinden sunulduğu için sunucuya yalnız API istekleri düşer. Disk: işletim sistemi ~3 GB,
uygulama ~1 GB; geri kalanı veritabanı, görseller ve 7 günlük yedek içindir.

---

## 14. Canlıya çıkış kontrol listesi

- [ ] `https://garajtek.com` açılıyor, `https://www.garajtek.com` → `garajtek.com`'a yönleniyor.
- [ ] Cloudflare SSL modu **Full (strict)**, Origin Certificate yüklü (`ls /etc/ssl/cloudflare/` içinde `.GECICI` yok).
- [ ] Transform Rule (`X-Edge-Secret`) etkin.
- [ ] `ADMIN_INITIAL_PASSWORD` boşaltıldı, MFA açık, `ENABLE_API_DOCS=0`.
- [ ] Test kart siparişi: `Ödeme Bekleniyor` → 3D Secure → `Onaylandı`; başarısız ödeme siparişi ödenmiş görünmüyor.
- [ ] Havale siparişi: banka bilgisi e-postası gidiyor.
- [ ] E-postalarda kendi marka adınız görünüyor.
- [ ] Görsel yükleme çalışıyor, görsel `https://garajtek.com/media/...` adresinden açılıyor.
- [ ] `garajtek-backup` çalışıyor ve **R2'ye yüklüyor**; bir kez `garajtek-restore` ile geri yükleme denendi.
- [ ] iyzico canlı moda alındı (`IYZICO_MODE=live` / panel).
