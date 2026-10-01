# GarajTek Mail Sunucusu (mail.garajtek.com)

Tek VDS (SNET, Ubuntu 24.04, 2 vCPU / 2 GB RAM) üzerinde, siteyle aynı sunucuda çalışan kendi posta sunucumuz.

| Bileşen | Görev | Port |
|---|---|---|
| **Postfix** | Posta alma/gönderme | 25 (MX), 587 (STARTTLS, giriş zorunlu), 465 (SSL, giriş zorunlu) |
| **Dovecot** | IMAP + LMTP teslimat + SASL + kota | 993 (SSL), 143 (STARTTLS zorunlu) |
| **OpenDKIM** | Giden postayı imzalar | 127.0.0.1:8891 |
| **Roundcube** | Webmail (resmi tarball, php-fpm, SQLite) | https://mail.garajtek.com |
| **nginx + Let's Encrypt** | Webmail + TLS sertifikası | 80/443 |
| **fail2ban** | postfix-sasl, dovecot, roundcube-auth kaba kuvvet koruması | — |

Posta kutuları **sanaldır** (Linux kullanıcısı yok): `/etc/dovecot/users` (SHA512-CRYPT) + `/etc/postfix/vmailbox`,
postalar `/var/mail/vhosts/garajtek.com/<kullanici>/` (Maildir, sahibi `vmail` uid/gid 5000).
Yönlendirmeler (alias) `/etc/postfix/virtual`.

```
İnternet ──25──▶ Postfix ──LMTP──▶ Dovecot ──▶ /var/mail/vhosts/...
Outlook/Telefon ──587/465 (SASL)──▶ Postfix ──OpenDKIM imza──▶ alıcı MX (veya relay)
Outlook/Telefon ──993──▶ Dovecot
Tarayıcı ──443──▶ nginx ──php-fpm──▶ Roundcube ──IMAP 143 / SMTP 587 (localhost)──▶ Dovecot/Postfix
Admin paneli ──▶ garajtek-api ──sudo -n──▶ /usr/local/sbin/garajtek-mail ──▶ users/vmailbox/virtual + postmap
Site bildirimleri ──SMTP 127.0.0.1:587 (noreply@)──▶ Postfix ──DKIM──▶ müşteri
```

---

## 1. Ön koşullar (kurulumdan ÖNCE)

### 1.1 Giden 25 portu açık mı?
```bash
timeout 5 bash -c 'exec 3<>/dev/tcp/gmail-smtp-in.l.google.com/25' && echo ACIK || echo KAPALI
```
- **ACIK** → doğrudan gönderim.
- **KAPALI** → SNET destekten açılmasını isteyin **veya** relay kullanın (bkz. §6). Alma + webmail yine çalışır.

### 1.2 PTR / rDNS
SNET müşteri panelinde sunucu IP'sinin **rDNS (PTR)** kaydını `mail.garajtek.com` yapın.
(DNS sağlayıcıda değil, hosting panelinde ayarlanır.) Kontrol:
```bash
dig +short -x SUNUCU_IP      # → mail.garajtek.com.
```
PTR yoksa Gmail/Outlook postaları reddedebilir veya spam'e atabilir → yapılamıyorsa relay kullanın.

### 1.3 DNS kayıtları (Cloudflare → garajtek.com → DNS)
> **mail** alt alan adı **DNS only (gri bulut)** olmalı. Turuncu bulut SMTP/IMAP'i keser ve sertifika alınamaz.

| Tür | Ad | Değer | Not |
|---|---|---|---|
| A | `mail` | `SUNUCU_IP` | **Proxy KAPALI** — certbot'tan ÖNCE eklenmeli |
| MX | `@` | `mail.garajtek.com` | öncelik **10** |
| TXT | `@` | `v=spf1 mx a ip4:SUNUCU_IP ~all` | tek SPF kaydı! (relay Brevo ise sonuna ` include:spf.brevo.com` ekleyin) |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:info@garajtek.com` | birkaç hafta sonra `p=quarantine` |
| TXT | `default._domainkey` | `v=DKIM1; h=sha256; k=rsa; p=MIIBIjANB...` | kurulum sonunda **tek satır** olarak yazdırılır |

Eski posta sağlayıcınızın (ör. Zoho) MX/SPF kayıtlarını kaldırın; aynı alan adında iki MX sağlayıcısı olmaz.
Mevcut bir SPF kaydı varsa ikinci bir `v=spf1` eklemeyin, birleştirin.

---

## 2. Kurulum

Önce site kurulumu (`deploy/install.sh` — nginx, `garajtek` kullanıcısı, ufw). Sonra **root** olarak:

```bash
cd /opt/garajtek/deploy/mail
bash mail-kur.sh garajtek.com mail.garajtek.com
```

Relay ile (25 kapalı / PTR yok):
```bash
echo 'BREVO_SMTP_ANAHTARI' > /root/relay.pass && chmod 600 /root/relay.pass
bash mail-kur.sh garajtek.com mail.garajtek.com \
  --relay-host smtp-relay.brevo.com:587 --relay-user BREVO_LOGIN --relay-pass-file /root/relay.pass
```

Diğer seçenekler: `--ip IP`, `--le-email siz@ornek.com`, `--no-relay` (relay'i kaldır), `--api-user garajtek`,
`--no-fail2ban`, `--skip-dns-check`, `--dry-run DIZIN` (hiçbir şey kurmadan tüm yapılandırmaları DIZIN'e üretir).
Ortam: `RC_VERSION=1.6.x` (Roundcube sürümü), `RC_SHA256=...` (verilirse tarball doğrulanır).

Betik **idempotenttir**; tekrar çalıştırmak posta kutularını, DKIM anahtarını, Roundcube `des_key`'ini ve sertifikayı korur.

Betiğin yaptıkları:
1. Ön kontroller: root, Ubuntu sürümü, genel IP, **giden 25 testi**, (sonda) **PTR testi**.
2. Paketler `--no-install-recommends` ile; Postfix debconf ile sessiz ("Internet Site", mailname `mail.garajtek.com`).
   **apt `roundcube` paketi KURULMAZ** (apache2 çeker, nginx ile çakışır).
3. `vmail` (5000) kullanıcı/grubu, `/var/mail/vhosts`.
4. nginx geçici HTTP bloğu → `dig mail.garajtek.com` = sunucu IP mi? (değilse açık mesajla durur) →
   `certbot certonly --webroot -w /var/www/html -d mail.garajtek.com` → yenileme kancası (postfix/dovecot/nginx reload).
5. OpenDKIM: `opendkim-genkey -b 2048 -d garajtek.com -s default`, `inet:8891@127.0.0.1`.
6. Postfix (`postconf -e`): sanal alan, LMTP, LE sertifikası, Dovecot SASL, `inet_protocols = ipv4`,
   25 MB ileti sınırı, açık röle (open relay) koruması; master.cf'de **submission (587)** ve **smtps (465)**
   yalnız giriş yapmış istemcilere açık. Giriş yapan kullanıcı yalnız kendi adresiyle gönderebilir
   (`info@` ve `noreply@` tüm alan adı adresleriyle gönderebilir — site bildirimleri `siparis@` vb. için).
7. Dovecot `/etc/dovecot/local.conf`: `ssl = required`, düz metin giriş kapalı, passwd-file, LMTP/auth soketleri
   Postfix'e, kota (varsayılan 1 GB, kutu bazında), Sent/Drafts/Trash/Junk otomatik. Sistem (PAM) girişi kapatılır.
8. Roundcube resmi **complete** tarball → `/var/www/roundcube`, SQLite (`db_dsnw = sqlite:////var/www/roundcube/db/sqlite.db`),
   `tls://localhost:143` / `tls://localhost:587`, Türkçe (`tr_TR`), "GarajTek Webmail", rastgele `des_key`, `installer/` silinir.
   Ayrı php-fpm havuzu (`pm = ondemand`, `max_children = 3`).
9. ufw: 25, 465, 587, 993, 143, 80, 443 (idempotent). fail2ban jail'leri.
10. `garajtek-mail` CLI, `/etc/sudoers.d/garajtek-mail` (`visudo -c` ile doğrulanır), günlük yedek cron'u.
11. `info@` ve `noreply@` kutuları rastgele şifreyle; `postmaster@` ve `abuse@` → `info@` yönlendirmesi.
    **Şifreler yalnız bir kez ekrana basılır** ve `/root/garajtek-mail-credentials.txt` (0600) dosyasına eklenir.
12. Servis/port doğrulaması + **eklenecek DNS kayıtlarının tam listesi** (DKIM tek satır).

---

## 3. DKIM adımı

Kurulum sonunda yazdırılan değeri Cloudflare'de `default._domainkey` TXT kaydı olarak ekleyin
(Cloudflare 255 karakterden uzun değeri kendisi böler; tırnaksız, tek parça yapıştırın). Tekrar görmek için:
```bash
garajtek-mail dkim-record          # veya Admin › Ayarlar › Mail Yönetimi › DNS sekmesi (kopyala butonu)
```

---

## 4. Test

```bash
systemctl is-active postfix dovecot opendkim nginx php8.3-fpm fail2ban
ss -ltnp | grep -E ':(25|143|465|587|993|443|8891) '
garajtek-mail status | less
garajtek-mail dns-check            # SPF/DKIM/DMARC/MX/A/PTR/port25 → hepsi PASS olmalı
garajtek-mail test-send adresiniz@gmail.com
```
- Gmail'de mesajı açın → ⋮ → **Orijinali göster**: `SPF: PASS`, `DKIM: PASS`, `DMARC: PASS`.
- https://www.mail-tester.com adresine `test-send` ile gönderip **10/10** hedefleyin.
- Alma testi: Gmail'den `info@garajtek.com`'a yazın → https://mail.garajtek.com'da görün.
- Kara liste: https://mxtoolbox.com/blacklists.aspx (IP'yi girin).

---

## 5. Teslim edilebilirlik ipuçları
- PTR = `mail.garajtek.com`, A kaydı aynı IP, SPF/DKIM/DMARC PASS — üçü olmadan Gmail/Outlook güvenmez.
- **IP ısınması**: yeni IP'den ilk 2-3 hafta günde az sayıda (≈50-100) gerçek mail; toplu pazarlama
  maillerini bu sunucudan **değil**, Brevo/SES (Pazarlama › E-posta Pazarlama) üzerinden gönderin.
- DMARC raporlarını (rua → info@) birkaç hafta izleyin, sorun yoksa `p=quarantine`.
- Postfix'e RBL (zen.spamhaus.org) eklenmedi: genel DNS çözücülerle Spamhaus sorguları engellenir ve tüm postayı
  reddettirebilir. Gerekirse yerel bir çözümleyici (unbound) ile birlikte eklenmeli.

---

## 6. Relay (25 kapalı / PTR yok)
Postfix giden postayı Brevo/Resend gibi bir smarthost'a SASL ile verir; **alma ve webmail yine bu sunucuda**.
DKIM imzası yine bizim anahtarımızla atılır.
```bash
bash mail-kur.sh garajtek.com mail.garajtek.com --relay-host smtp-relay.brevo.com:587 \
     --relay-user LOGIN --relay-pass-file /root/relay.pass
# Resend: --relay-host smtp.resend.com:587 --relay-user resend --relay-pass-file /root/resend.key
bash mail-kur.sh garajtek.com mail.garajtek.com --no-relay      # doğrudan gönderime dön
```
Relay sağlayıcısında alan adını doğrulayın ve SPF'ye onların `include:` değerini ekleyin
(Brevo: `include:spf.brevo.com`). Şifre `/etc/postfix/sasl_passwd` (0600) içinde durur.

---

## 7. Panel kullanımı (Admin › Ayarlar › Mail Yönetimi)
Yetki: `settings.mail_server` (Rol yönetiminden verilir; süper-admin her zaman görür).

| Sekme | İçerik |
|---|---|
| Genel Durum | servis rozetleri, portlar, kuyruk sayısı, sertifika bitişi, disk, webmail linki, Outlook/telefon ayarları, **"Site bildirimlerini bu sunucudan gönder"** |
| Posta Kutuları | liste + kullanım/kota çubuğu, yeni kutu, kota değiştir, **şifre sıfırla (tek seferlik şifre + kopyala)**, sil (isteğe bağlı postalarla birlikte) |
| Yönlendirmeler | `siparis@ → info@, ortak@gmail.com` gibi alias/forward |
| DNS & Teslim Edilebilirlik | SPF/DKIM/DMARC/MX/A/PTR/port25 PASS/FAIL + eklenecek kaydın tam değeri (kopyala) |
| Kuyruk | bekleyen postalar ve sebepleri, flush, sil, test maili, port 25 testi |

**Panel ↔ sunucu:** API (`garajtek-api`, kullanıcı `garajtek`) yalnız şunu çalıştırabilir:
```
garajtek ALL=(root) NOPASSWD: /usr/local/sbin/garajtek-mail *
```
Kabuk kullanılmaz (`asyncio.create_subprocess_exec`), şifreler **stdin** ile (`--password-stdin`) gider, tüm
girdiler hem API'de hem CLI'da doğrulanır (e-posta regex'i, alan adı = garajtek.com, `--` ile seçenek enjeksiyonu
engellenir), dosyalar `flock` ile kilitlenir ve atomik yazılır; hata olursa geri alınır. CLI kurulu değilse panel
"Mail sunucusu kurulu değil" (503) gösterir. `garajtek-api.service`'te `NoNewPrivileges` **kullanılmamalı** (sudo'yu engeller).

### Site bildirimleri (sipariş/üyelik/şifre mailleri)
Panelde **Genel Durum › "Site bildirimlerini bu sunucudan gönder"** → `noreply@garajtek.com` şifresi yenilenir ve
e-posta ayarı otomatik `127.0.0.1:587 STARTTLS` olur (önceki ZeptoMail ayarı `email_smtp_previous` olarak saklanır).
Elle yapmak isterseniz `settings.email_smtp` değerleri: host `127.0.0.1`, port `587`, secure `starttls`,
kullanıcı `noreply@garajtek.com`, şifre = noreply şifresi (`garajtek-mail passwd noreply@garajtek.com --random`).
`backend/email_smtp.py` host `127.0.0.1`/`localhost` (veya `transport=smtp`) görünce ZeptoMail yerine SMTP kullanır.
> Not: Ayarlar › E-posta (ZeptoMail) sayfasında tekrar "Kaydet"e basmak host'u ZeptoMail'e geri çevirir.

### CLI (sunucuda, root)
```bash
garajtek-mail list [--json]
garajtek-mail add satis@garajtek.com --random --quota 2G
echo 'YeniSifre123!' | garajtek-mail passwd satis@garajtek.com --password-stdin
garajtek-mail quota satis@garajtek.com 5G          # 0 = sınırsız
garajtek-mail del satis@garajtek.com [--purge]     # --purge: postaları da siler
garajtek-mail alias-add siparis@garajtek.com info@garajtek.com,ortak@gmail.com
garajtek-mail alias-list | alias-del siparis@garajtek.com
garajtek-mail status | dns-check | port25-check | queue | queue-flush | queue-delete ID|ALL
garajtek-mail test-send adres@gmail.com | dkim-record | backup
```
(Eski `estoril-mail add/passwd/del/list` komutlarının karşılığıdır; tüm komutlar `--json` destekler.)

---

## 8. Yedekleme
- `garajtek-mail backup` → `/var/backups/garajtek/mail-YYYYmmdd-HHMM.tar.gz` (0600; son 2 kopya; yetersiz diskte
  yedek almaz). `/etc/cron.daily/garajtek-mail-backup` her gün çalıştırır.
- Yedeklenen yollar: `deploy/mail/backup-paths.txt` (posta verisi `/var/mail/vhosts`, `/etc/dovecot/users`,
  `/etc/postfix/vmailbox`, `/etc/postfix/virtual`, **`/etc/opendkim` anahtarları**, Roundcube config + SQLite db ...).
- **Sunucu dışı kopya (R2)**: `deploy/backup.sh` (gece yedeği) posta yedeğini `mail.tar.gz` olarak ana arşive
  ekler; böylece aynı (şifreli) R2 akışına girer. Ek ayar gerekmez.
- Geri yükleme: `tar -xzpf mail-....tar.gz -C / --absolute-names` → `postmap /etc/postfix/vmailbox /etc/postfix/virtual`
  → `chown -R vmail:vmail /var/mail/vhosts` → `systemctl restart opendkim dovecot postfix`.

---

## 9. Bellek (2 GB RAM)
| Servis | Tipik RSS |
|---|---|
| Postfix (master + qmgr + pickup + tlsmgr) | 20–40 MB |
| Dovecot (master + auth + birkaç imap) | 20–50 MB |
| OpenDKIM | 5–10 MB |
| php-fpm (ondemand, en çok 3 işçi, opcache 32 MB) | 0 (boşta) – 120 MB |
| fail2ban | 30–50 MB |
| **Toplam** | **≈150–250 MB** |

Ayarlar: php-fpm `pm = ondemand`, `pm.max_children = 3`, varsayılan `www` havuzu da ondemand (2);
Dovecot `process_limit = 64`, `default_vsz_limit = 256M`; ClamAV/SpamAssassin/Rspamd **kurulmadı** (her biri 300 MB–1 GB).
API (`MemoryMax=900M`) + nginx + posta birlikte 2 GB + 2 GB swap'ta rahat çalışır.

---

## 10. Sorun giderme ve bilinen tuzaklar
- **`tr ... | head` + `set -o pipefail`** → SIGPIPE betiği öldürür. Rastgele değerler `openssl rand -hex` / Python `secrets` ile üretilir; betikte `grep -q` boru hattı kullanılmaz.
- **apt `roundcube` paketi** apache2 kurar ve 80/443'te nginx ile çakışır → yalnız resmi tarball + php-fpm.
- **Turuncu bulut**: `mail` kaydı proxied ise `dig mail.garajtek.com` Cloudflare IP'si döner → betik certbot'tan önce durur.
- **DNS certbot'tan önce**: A kaydı yayılmadan certbot başarısız olur; betik önce `dig` ile kontrol eder.
- **IPv6**: `inet_protocols = ipv4` (AAAA/PTR6 olmadığı için IPv6 gönderim Gmail'de reddedilir).
- `deploy/install.sh --cf-firewall` 80/443'ü yalnız Cloudflare'e açar; mail.garajtek.com gri bulut olduğu için
  `mail-kur.sh` 80/443'ü herkese açar (webmail + Let's Encrypt için gerekli).
- 80 portunu nginx dışı bir süreç (Caddy) tutuyorsa betik durur.
- Yeni kutu/şifre ~1 saniye içinde geçerli olur (Dovecot users dosyasını saniyede bir yeniden okur).
- Loglar: `journalctl -u postfix@- -u dovecot -u opendkim`, `/var/log/mail.log`, `/var/log/roundcube/errors.log`,
  `/var/log/nginx/mail.error.log`. Yapılandırma: `postconf -n`, `doveconf -n`, `postfix check`.
- Gönderim "Sender address rejected: not owned by user": giriş yapan kutu yalnız kendi adresiyle gönderebilir.
- Kuyrukta "Connection timed out (port 25)": giden 25 kapalı → §6 relay.
- Roundcube "Veritabanı hatası": `/var/www/roundcube/db` sahibi `www-data` olmalı.
- Banlanan IP'yi açma: `fail2ban-client set dovecot unbanip IP`.
- Roundcube sürüm yükseltme: `RC_VERSION=1.6.x bash mail-kur.sh ...` (resmi `installto.sh` ile config+db korunur).
