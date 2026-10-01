#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# GarajTek self-hosted mail sunucusu kurulumu (Ubuntu 24.04, 2 GB RAM'e göre ayarlı)
#
#   Postfix (25/465/587)  ·  Dovecot (IMAP 993/143 + LMTP)  ·  OpenDKIM
#   Roundcube (resmi "complete" tarball, php-fpm, SQLite)  ·  nginx + Let's Encrypt
#   Sanal posta kutuları (Linux kullanıcısı YOK) — vmail (uid/gid 5000)
#
# Kullanım (root):
#   bash mail-kur.sh [ALAN_ADI] [MAIL_HOST] [seçenekler]
#   bash mail-kur.sh garajtek.com mail.garajtek.com
#   bash mail-kur.sh garajtek.com mail.garajtek.com \
#        --relay-host smtp-relay.brevo.com:587 --relay-user KULLANICI --relay-pass-file /root/brevo.pass
#
# Seçenekler:
#   --ip IP                 Sunucunun genel IPv4 adresi (varsayılan: otomatik bulunur)
#   --le-email E            Let's Encrypt bildirim e-postası (varsayılan: info@ALAN_ADI değil,
#                           henüz posta kutusu çalışmadığı için kayıtsız; verirseniz kullanılır)
#   --relay-host H:P        Giden postayı bir smarthost üzerinden gönder (25 kapalı / PTR yoksa)
#   --relay-user U          Relay SMTP kullanıcı adı
#   --relay-pass P          Relay şifresi (komut geçmişinde görünür! tercihen --relay-pass-file
#                           veya RELAY_PASS ortam değişkeni)
#   --relay-pass-file F     Relay şifresini dosyadan oku
#   --no-relay              Daha önce ayarlanmış relay'i kaldır (doğrudan gönderim)
#   --api-user U            Admin panelini çalıştıran Linux kullanıcısı (varsayılan: garajtek)
#   --skip-dns-check        mail host A kaydı kontrolünü atla (önerilmez)
#   --no-fail2ban           fail2ban kurma
#   --dry-run DIR           Hiçbir şeyi kurmadan tüm yapılandırma dosyalarını DIR altına üret
#   -h | --help
# Ortam: RC_VERSION (Roundcube sürümü), RC_SHA256 (tarball SHA256 — verilirse doğrulanır),
#        RELAY_HOST / RELAY_USER / RELAY_PASS
#
# Betik idempotenttir: tekrar çalıştırmak mevcut posta kutularını, DKIM anahtarını,
# Roundcube des_key'ini ve sertifikayı korur.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail
umask 022

DOMAIN="garajtek.com"
HOST="mail.garajtek.com"
PUBLIC_IP=""
LE_EMAIL=""
RELAY_HOST="${RELAY_HOST:-}"
RELAY_USER="${RELAY_USER:-}"
RELAY_PASS="${RELAY_PASS:-}"
NO_RELAY=0
API_USER="garajtek"
SKIP_DNS=0
WITH_F2B=1
DRY=0
ROOT=""
RC_VERSION="${RC_VERSION:-1.6.11}"
RC_SHA256="${RC_SHA256:-}"
RC_DIR="/var/www/roundcube"
VMAIL_UID=5000
VMAIL_HOME="/var/mail/vhosts"
DKIM_SELECTOR="default"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CRED_FILE="/root/garajtek-mail-credentials.txt"
PHP_VER=""

# ───────────────────────────── yardımcılar ─────────────────────────────
c_ok=$'\e[32m'; c_warn=$'\e[33m'; c_err=$'\e[31m'; c_b=$'\e[1m'; c_0=$'\e[0m'
step() { printf '\n%s▶ %s%s\n' "$c_b" "$*" "$c_0"; }
ok()   { printf '  %s✔%s %s\n' "$c_ok" "$c_0" "$*"; }
warn() { printf '  %s!%s %s\n' "$c_warn" "$c_0" "$*"; WARNINGS+=("$*"); }
die()  { printf '\n%s✖ HATA:%s %s\n' "$c_err" "$c_0" "$*" >&2; exit 1; }
WARNINGS=()

usage() { sed -n '2,36p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0; }

# Dosya yaz: içerik stdin'den; dry-run'da ROOT altına
wfile() {  # wfile PATH MODE [OWNER:GROUP]
  local path="$ROOT$1" mode="$2" owner="${3:-}"
  mkdir -p "$(dirname "$path")"
  cat > "$path.tmp.$$"
  chmod "$mode" "$path.tmp.$$"
  if [ "$DRY" -eq 0 ] && [ -n "$owner" ]; then chown "$owner" "$path.tmp.$$"; fi
  mv -f "$path.tmp.$$" "$path"
}

# postconf -e (dry-run: komutları dosyaya yaz)
pc() {
  if [ "$DRY" -eq 1 ]; then
    local a; for a in "$@"; do printf 'postconf -e %q\n' "$a"; done >> "$ROOT/postconf-commands.sh"
  else
    postconf -e "$@"
  fi
}
pcM() {
  if [ "$DRY" -eq 1 ]; then printf 'postconf -M %q\n' "$1" >> "$ROOT/postconf-commands.sh"; else postconf -M "$1"; fi
}
pcP() {
  if [ "$DRY" -eq 1 ]; then
    local a; for a in "$@"; do printf 'postconf -P %q\n' "$a"; done >> "$ROOT/postconf-commands.sh"
  else
    postconf -P "$@"
  fi
}

valid_domain() { [[ "$1" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$ ]]; }
valid_ipv4()   { [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; }

# ───────────────────────────── argümanlar ─────────────────────────────
POS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --ip) PUBLIC_IP="${2:?--ip değeri}"; shift 2 ;;
    --le-email) LE_EMAIL="${2:?--le-email değeri}"; shift 2 ;;
    --relay-host) RELAY_HOST="${2:?--relay-host değeri}"; shift 2 ;;
    --relay-user) RELAY_USER="${2:?--relay-user değeri}"; shift 2 ;;
    --relay-pass) RELAY_PASS="${2:?--relay-pass değeri}"; shift 2 ;;
    --relay-pass-file) RELAY_PASS="$(head -n1 "${2:?--relay-pass-file değeri}")"; shift 2 ;;
    --no-relay) NO_RELAY=1; shift ;;
    --api-user) API_USER="${2:?--api-user değeri}"; shift 2 ;;
    --skip-dns-check) SKIP_DNS=1; shift ;;
    --no-fail2ban) WITH_F2B=0; shift ;;
    --dry-run) DRY=1; ROOT="$(mkdir -p "${2:?--dry-run DIZIN}" && cd "$2" && pwd)"; shift 2 ;;
    -h|--help) usage ;;
    --*) die "Bilinmeyen seçenek: $1 (yardım: --help)" ;;
    *) POS+=("$1"); shift ;;
  esac
done
[ "${#POS[@]}" -ge 1 ] && DOMAIN="${POS[0],,}"
[ "${#POS[@]}" -ge 2 ] && HOST="${POS[1],,}"
valid_domain "$DOMAIN" || die "Geçersiz alan adı: $DOMAIN"
valid_domain "$HOST" || die "Geçersiz mail host: $HOST"
[[ "$HOST" == *".$DOMAIN" ]] || die "Mail host ($HOST) $DOMAIN alt alan adı olmalı (ör. mail.$DOMAIN)"
[[ "$API_USER" =~ ^[a-z_][a-z0-9_-]{0,31}$ ]] || die "Geçersiz --api-user"
[[ "$RC_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "Geçersiz RC_VERSION"
if [ -n "$RELAY_HOST" ]; then
  [[ "$RELAY_HOST" =~ ^[A-Za-z0-9.-]+:[0-9]{2,5}$ ]] || die "--relay-host HOST:PORT biçiminde olmalı (ör. smtp-relay.brevo.com:587)"
  [ -n "$RELAY_USER" ] && [ -n "$RELAY_PASS" ] || die "--relay-host için --relay-user ve --relay-pass(-file) gerekli"
  [[ "$RELAY_USER$RELAY_PASS" =~ [[:space:]] ]] && die "Relay kullanıcı/şifre boşluk içeremez"
fi
[ -n "$LE_EMAIL" ] && { [[ "$LE_EMAIL" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[a-z]{2,}$ ]] || die "Geçersiz --le-email"; }
SENDER_ADMINS="info@$DOMAIN, noreply@$DOMAIN"

# ───────────────────────────── ön kontroller ─────────────────────────────
detect_ip() {
  [ -n "$PUBLIC_IP" ] && return 0
  PUBLIC_IP="$(curl -4 -fsS --max-time 6 https://api.ipify.org 2>/dev/null || true)"
  valid_ipv4 "$PUBLIC_IP" || PUBLIC_IP="$(curl -4 -fsS --max-time 6 https://ifconfig.me 2>/dev/null || true)"
  valid_ipv4 "$PUBLIC_IP" || PUBLIC_IP="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')"
  valid_ipv4 "$PUBLIC_IP" || die "Genel IP bulunamadı — --ip ile verin"
}

PORT25="?"

prechecks() {
  step "1/12 Ön kontroller"
  [ "$(id -u)" -eq 0 ] || die "root olarak çalıştırın: sudo bash mail-kur.sh ..."
  if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    [ "${ID:-}" = "ubuntu" ] || warn "Ubuntu dışı sistem (${ID:-?}) — Ubuntu 24.04 için yazıldı"
    [ "${VERSION_ID:-}" = "24.04" ] || warn "Ubuntu ${VERSION_ID:-?} — 24.04 önerilir"
  fi
  detect_ip
  ok "Genel IP: $PUBLIC_IP"
  local mem_mb; mem_mb=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
  ok "RAM: ${mem_mb} MB"

  # Giden 25 portu (sahibin testiyle birebir)
  if timeout 5 bash -c 'exec 3<>/dev/tcp/gmail-smtp-in.l.google.com/25' 2>/dev/null; then
    PORT25="ACIK"; ok "Giden 25 portu: ACIK"
  else
    PORT25="KAPALI"
    if [ -n "$RELAY_HOST" ]; then
      warn "Giden 25 portu KAPALI — relay ($RELAY_HOST) kullanılacak, sorun değil."
    else
      warn "Giden 25 portu KAPALI! Dış dünyaya posta GİDEMEZ. SNET destekten açtırın ya da --relay-host ile Brevo/Resend kullanın. (Alma + webmail yine çalışır.)"
    fi
  fi
}

check_ptr() {
  command -v dig >/dev/null || return 0
  local ptr; ptr="$(dig +short +time=3 +tries=2 -x "$PUBLIC_IP" @1.1.1.1 2>/dev/null | sed 's/\.$//' | tr '[:upper:]' '[:lower:]')"
  if [ "$ptr" = "$HOST" ]; then
    ok "PTR/rDNS: $PUBLIC_IP → $ptr"
  else
    warn "PTR/rDNS: $PUBLIC_IP → '${ptr:-yok}' (beklenen $HOST). SNET panelinden IP'nin rDNS kaydını $HOST yapın; yapılmazsa Gmail/Outlook postaları reddedebilir/spam'e atabilir.${RELAY_HOST:+ (Relay kullanıldığı için giden posta etkilenmez.)}"
  fi
}

check_dns_a() {
  [ "$SKIP_DNS" -eq 1 ] && { warn "DNS kontrolü atlandı (--skip-dns-check)"; return 0; }
  local a; a="$(dig +short +time=3 +tries=2 A "$HOST" @1.1.1.1 2>/dev/null | tr '\n' ' ')"
  if [[ " $a " != *" $PUBLIC_IP "* ]]; then  # (grep -q | pipefail → SIGPIPE tuzağından kaçınılır)
    cat >&2 <<MSG

${c_err}✖ DNS hazır değil:${c_0} $HOST → '${a:-çözümlenmiyor}' (beklenen $PUBLIC_IP)

  Cloudflare (veya DNS sağlayıcınız) üzerinde şu kaydı ekleyin ve 1-5 dk bekleyin:
      Tür: A    Ad: ${HOST%."$DOMAIN"}    Değer: $PUBLIC_IP    Proxy: KAPALI (DNS only / gri bulut)

  Turuncu bulut (proxied) açıksa Cloudflare IP'leri döner — mail için mutlaka GRİ olmalı.
  Ardından betiği tekrar çalıştırın (idempotent). Let's Encrypt sertifikası DNS olmadan alınamaz.
MSG
    exit 1
  fi
  ok "DNS: $HOST → $PUBLIC_IP"
}

check_port80() {
  local holder
  holder="$(ss -ltnpH 'sport = :80' 2>/dev/null | sed -n 's/.*users:(("\([^"]*\)".*/\1/p' | sort -u | tr '\n' ' ')"
  if [ -n "$holder" ] && [[ " $holder " != *" nginx "* ]]; then
    die "80 portunu '$holder' kullanıyor. Bu kurulum nginx bekler (Caddy vb. ile çakışır). Önce web sunucusunu nginx'e taşıyın (deploy/install.sh)."
  fi
}

# ───────────────────────────── paketler ─────────────────────────────
install_packages() {
  step "2/12 Paketler (--no-install-recommends)"
  export DEBIAN_FRONTEND=noninteractive
  echo "postfix postfix/main_mailer_type select Internet Site" | debconf-set-selections
  echo "postfix postfix/mailname string $HOST" | debconf-set-selections
  apt-get update -qq
  local pkgs=(postfix postfix-pcre dovecot-core dovecot-imapd dovecot-lmtpd opendkim opendkim-tools
              certbot python3-certbot-nginx nginx php-fpm php-cli php-sqlite3 php-intl php-mbstring
              php-xml php-gd php-zip php-curl libsasl2-modules dnsutils curl ca-certificates rsyslog
              ssl-cert openssl tar)
  [ "$WITH_F2B" -eq 1 ] && pkgs+=(fail2ban python3-systemd)
  # ÖNEMLİ: apt 'roundcube' metapaketi KURULMAZ (apache2 çeker, nginx ile çakışır).
  apt-get install -y -qq --no-install-recommends "${pkgs[@]}" >/dev/null
  PHP_VER="$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')"
  ok "Paketler kuruldu (PHP $PHP_VER)"
}

# ───────────────────────────── vmail ─────────────────────────────
setup_vmail() {
  step "3/12 vmail kullanıcısı ve dizinler"
  getent group vmail >/dev/null || groupadd -g "$VMAIL_UID" vmail
  getent passwd vmail >/dev/null || useradd -u "$VMAIL_UID" -g vmail -d "$VMAIL_HOME" -s /usr/sbin/nologin -M vmail
  [ "$(id -u vmail)" = "$VMAIL_UID" ] || warn "vmail uid'i $VMAIL_UID değil ($(id -u vmail)) — local.conf buna göre ayarlandı"
  install -d -o vmail -g vmail -m 0770 "$VMAIL_HOME" "$VMAIL_HOME/$DOMAIN"
  install -d -m 0755 /etc/garajtek-mail /var/lib/garajtek-mail
  printf '%s\n' "$HOST" > /etc/mailname
  [ -f /etc/dovecot/users ] || install -m 0640 -o root -g dovecot /dev/null /etc/dovecot/users
  chown root:dovecot /etc/dovecot/users; chmod 0640 /etc/dovecot/users
  [ -f /etc/postfix/vmailbox ] || install -m 0644 /dev/null /etc/postfix/vmailbox
  [ -f /etc/postfix/virtual ] || install -m 0644 /dev/null /etc/postfix/virtual
  postmap hash:/etc/postfix/vmailbox
  postmap hash:/etc/postfix/virtual
  ok "vmail ($VMAIL_UID) + $VMAIL_HOME"
}

render_conf() {
  wfile /etc/garajtek-mail/mail.conf 0644 root:root <<EOF
# garajtek-mail yapılandırması — mail-kur.sh tarafından üretildi
DOMAIN=$DOMAIN
HOST=$HOST
PUBLIC_IP=$PUBLIC_IP
VMAIL_HOME=$VMAIL_HOME
DKIM_SELECTOR=$DKIM_SELECTOR
DEFAULT_QUOTA=1G
WEBMAIL_URL=https://$HOST
BACKUP_DIR=/var/backups/garajtek
BACKUP_KEEP=2
EOF
}

# ───────────────────────────── nginx + TLS ─────────────────────────────
NGINX_SITE="/etc/nginx/sites-available/$HOST.conf"

render_nginx_http() {
  wfile "$NGINX_SITE" 0644 root:root <<EOF
# $HOST — geçici HTTP bloğu (yalnız Let's Encrypt doğrulaması için). mail-kur.sh
server {
    listen 80;
    server_name $HOST;
    root /var/www/html;
    location ^~ /.well-known/acme-challenge/ { default_type text/plain; }
    location / { return 404; }
}
EOF
}

render_nginx_https() {
  local sock="/run/php/roundcube.sock"
  wfile "$NGINX_SITE" 0644 root:root <<EOF
# $HOST — Roundcube webmail (php-fpm). mail-kur.sh tarafından üretildi.
server {
    listen 80;
    server_name $HOST;
    location ^~ /.well-known/acme-challenge/ { root /var/www/html; default_type text/plain; }
    location / { return 301 https://\$host\$request_uri; }
}

server {
    listen 443 ssl http2;
    server_name $HOST;

    ssl_certificate     /etc/letsencrypt/live/$HOST/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$HOST/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_cache shared:mailssl:2m;
    ssl_session_timeout 1h;

    root $RC_DIR;
    index index.php;
    client_max_body_size 26m;
    server_tokens off;

    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;

    access_log /var/log/nginx/mail.access.log;
    error_log  /var/log/nginx/mail.error.log warn;

    # Roundcube iç dizinleri ve gizli dosyalar web'e kapalı
    location ~ /\.(?!well-known/) { deny all; }
    location ~ ^/(config|temp|logs|db|SQL|bin|installer|vendor)(/|\$) { deny all; return 404; }
    location ~ ^/(README|INSTALL|LICENSE|CHANGELOG|UPGRADING|SECURITY|composer\.)  { deny all; return 404; }

    location / { try_files \$uri \$uri/ /index.php\$is_args\$args; }

    location ~ \.php\$ {
        include snippets/fastcgi-php.conf;
        fastcgi_pass unix:$sock;
        fastcgi_read_timeout 120s;
    }

    location ~* \.(?:css|js|png|jpe?g|gif|svg|ico|woff2?)\$ { expires 7d; access_log off; }
}
EOF
  if [ "$DRY" -eq 0 ]; then
    ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/$HOST.conf"
  fi
}

nginx_reload() {
  ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/$HOST.conf"
  nginx -t -q || die "nginx yapılandırması hatalı (nginx -t)"
  systemctl enable --now nginx >/dev/null 2>&1 || true
  systemctl reload nginx
}

render_certbot_hook() {
  wfile /etc/letsencrypt/renewal-hooks/deploy/garajtek-mail.sh 0755 root:root <<EOF
#!/bin/sh
# Sertifika yenilenince mail servisleri yeni sertifikayı yüklesin. (mail-kur.sh)
case " \$RENEWED_DOMAINS " in
  *" $HOST "*) systemctl reload postfix dovecot nginx || true ;;
esac
EOF
}

setup_tls() {
  step "4/12 nginx + Let's Encrypt ($HOST)"
  check_port80
  mkdir -p /var/www/html/.well-known/acme-challenge
  if [ ! -f "/etc/letsencrypt/live/$HOST/fullchain.pem" ]; then
    render_nginx_http
    nginx_reload
    check_dns_a
    local em=(--register-unsafely-without-email)
    [ -n "$LE_EMAIL" ] && em=(-m "$LE_EMAIL")
    certbot certonly --webroot -w /var/www/html -d "$HOST" --non-interactive --agree-tos \
      "${em[@]}" --keep-until-expiring \
      || die "certbot başarısız. DNS ($HOST → $PUBLIC_IP, gri bulut) ve 80 portunu (ufw) kontrol edin."
    ok "Sertifika alındı"
  else
    ok "Sertifika zaten var (certbot renew otomatik yeniler)"
  fi
  render_certbot_hook
}

# ───────────────────────────── OpenDKIM ─────────────────────────────
render_opendkim() {
  wfile /etc/opendkim.conf 0644 root:root <<EOF
# OpenDKIM — mail-kur.sh tarafından üretildi
Syslog                  yes
SyslogSuccess           yes
LogWhy                  no
UMask                   007
UserID                  opendkim
PidFile                 /run/opendkim/opendkim.pid
Mode                    sv
Canonicalization        relaxed/simple
SubDomains              no
OversignHeaders         From
Domain                  $DOMAIN
Selector                $DKIM_SELECTOR
KeyFile                 /etc/opendkim/keys/$DOMAIN/$DKIM_SELECTOR.private
Socket                  inet:8891@127.0.0.1
InternalHosts           127.0.0.1, localhost
TrustAnchorFile         /usr/share/dns/root.key
EOF
}

setup_opendkim() {
  step "5/12 OpenDKIM (2048 bit, seçici: $DKIM_SELECTOR)"
  local kd="/etc/opendkim/keys/$DOMAIN"
  install -d -o opendkim -g opendkim -m 0750 /etc/opendkim /etc/opendkim/keys "$kd"
  if [ ! -f "$kd/$DKIM_SELECTOR.private" ]; then
    opendkim-genkey -b 2048 -d "$DOMAIN" -s "$DKIM_SELECTOR" -D "$kd"
    ok "Yeni DKIM anahtarı üretildi"
  else
    ok "Mevcut DKIM anahtarı korunuyor"
  fi
  chown opendkim:opendkim "$kd"/*; chmod 0600 "$kd/$DKIM_SELECTOR.private"; chmod 0644 "$kd/$DKIM_SELECTOR.txt"
  render_opendkim
  [ -f /usr/share/dns/root.key ] || sed -i 's/^TrustAnchorFile/#TrustAnchorFile/' /etc/opendkim.conf
  # Debian/Ubuntu: /etc/default/opendkim içindeki SOCKET, conf'taki Socket'i ezer → eşitle
  if [ -f /etc/default/opendkim ]; then
    if grep -qE '^SOCKET=' /etc/default/opendkim; then
      sed -i 's|^SOCKET=.*|SOCKET=inet:8891@127.0.0.1|' /etc/default/opendkim
    else
      echo 'SOCKET=inet:8891@127.0.0.1' >> /etc/default/opendkim
    fi
    if [ -x /lib/opendkim/opendkim.service.generate ]; then
      /lib/opendkim/opendkim.service.generate >/dev/null 2>&1 || true
    fi
    systemctl daemon-reload
  fi
  install -d -o opendkim -g opendkim -m 0755 /run/opendkim
  systemctl enable opendkim >/dev/null 2>&1 || true
  systemctl restart opendkim
}

# ───────────────────────────── Postfix ─────────────────────────────
render_postfix_maps() {
  local dre="${DOMAIN//./\\.}"
  wfile /etc/postfix/sender_login_maps.pcre 0644 root:root <<EOF
# Kimlik doğrulamalı kullanıcı yalnız kendi adresiyle gönderebilir.
# $SENDER_ADMINS ise alan adındaki her adresle gönderebilir (panel / site bildirimleri).
/^(.+)@${dre}\$/    \${1}@$DOMAIN, $SENDER_ADMINS
EOF
}

setup_postfix() {
  step "6/12 Postfix (25 / 587 STARTTLS / 465 SMTPS)"
  local le="/etc/letsencrypt/live/$HOST"
  render_postfix_maps
  pc "myhostname = $HOST" \
     "mydomain = $DOMAIN" \
     "myorigin = /etc/mailname" \
     "mydestination = \$myhostname, localhost.localdomain, localhost" \
     "mynetworks = 127.0.0.0/8" \
     "inet_interfaces = all" \
     "inet_protocols = ipv4" \
     "smtpd_banner = \$myhostname ESMTP" \
     "biff = no" \
     "append_dot_mydomain = no" \
     "recipient_delimiter = +" \
     "alias_maps = hash:/etc/aliases" \
     "alias_database = hash:/etc/aliases" \
     "message_size_limit = 26214400" \
     "mailbox_size_limit = 0" \
     "virtual_mailbox_domains = $DOMAIN" \
     "virtual_mailbox_maps = hash:/etc/postfix/vmailbox" \
     "virtual_alias_maps = hash:/etc/postfix/virtual" \
     "virtual_transport = lmtp:unix:private/dovecot-lmtp" \
     "smtpd_tls_cert_file = $le/fullchain.pem" \
     "smtpd_tls_key_file = $le/privkey.pem" \
     "smtpd_tls_security_level = may" \
     "smtpd_tls_auth_only = yes" \
     "smtpd_tls_loglevel = 1" \
     "smtpd_tls_received_header = yes" \
     "smtpd_tls_protocols = !SSLv2, !SSLv3" \
     "smtpd_tls_mandatory_protocols = !SSLv2, !SSLv3, !TLSv1, !TLSv1.1" \
     "smtp_tls_security_level = may" \
     "smtp_tls_loglevel = 1" \
     "smtp_tls_CApath = /etc/ssl/certs" \
     "smtpd_sasl_type = dovecot" \
     "smtpd_sasl_path = private/auth" \
     "smtpd_sasl_auth_enable = no" \
     "smtpd_sasl_security_options = noanonymous" \
     "smtpd_sender_login_maps = pcre:/etc/postfix/sender_login_maps.pcre" \
     "smtpd_helo_required = yes" \
     "disable_vrfy_command = yes" \
     "smtpd_delay_reject = yes" \
     "smtpd_helo_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_invalid_helo_hostname, reject_non_fqdn_helo_hostname" \
     "smtpd_sender_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_non_fqdn_sender, reject_unknown_sender_domain" \
     "smtpd_relay_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_unauth_destination" \
     "smtpd_recipient_restrictions = permit_mynetworks, permit_sasl_authenticated, reject_non_fqdn_recipient, reject_unknown_recipient_domain, reject_unlisted_recipient, reject_unauth_destination" \
     "smtpd_data_restrictions = reject_unauth_pipelining" \
     "smtpd_milters = inet:127.0.0.1:8891" \
     "non_smtpd_milters = \$smtpd_milters" \
     "milter_default_action = accept" \
     "milter_protocol = 6"

  # master.cf: submission (587, STARTTLS zorunlu) + smtps (465, TLS wrapper) — ikisi de SASL zorunlu
  local svc
  pcM "submission/inet=submission inet n - y - - smtpd"
  pcM "smtps/inet=smtps inet n - y - - smtpd"
  for svc in submission smtps; do
    pcP "$svc/inet/syslog_name=postfix/$svc" \
        "$svc/inet/smtpd_sasl_auth_enable=yes" \
        "$svc/inet/smtpd_tls_auth_only=yes" \
        "$svc/inet/smtpd_client_restrictions=permit_sasl_authenticated,reject" \
        "$svc/inet/smtpd_helo_restrictions=" \
        "$svc/inet/smtpd_sender_restrictions=reject_sender_login_mismatch,permit_sasl_authenticated,reject" \
        "$svc/inet/smtpd_relay_restrictions=permit_sasl_authenticated,reject" \
        "$svc/inet/smtpd_recipient_restrictions=permit_sasl_authenticated,reject" \
        "$svc/inet/milter_macro_daemon_name=ORIGINATING"
  done
  pcP "submission/inet/smtpd_tls_security_level=encrypt" "smtps/inet/smtpd_tls_wrappermode=yes"

  setup_relay

  if [ "$DRY" -eq 0 ]; then
    # root/postmaster yerel postası → info@
    grep -q '^root:' /etc/aliases 2>/dev/null || echo "root: info@$DOMAIN" >> /etc/aliases
    grep -q '^postmaster:' /etc/aliases 2>/dev/null || echo "postmaster: root" >> /etc/aliases
    newaliases
    postfix check || die "postfix check başarısız"
  fi
}

setup_relay() {
  if [ -n "$RELAY_HOST" ]; then
    local rh="[${RELAY_HOST%:*}]:${RELAY_HOST##*:}"
    printf '%s %s:%s\n' "$rh" "$RELAY_USER" "$RELAY_PASS" | wfile /etc/postfix/sasl_passwd 0600 root:root
    [ "$DRY" -eq 0 ] && postmap hash:/etc/postfix/sasl_passwd && chmod 0600 /etc/postfix/sasl_passwd.db
    pc "relayhost = $rh" \
       "smtp_sasl_auth_enable = yes" \
       "smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd" \
       "smtp_sasl_security_options = noanonymous" \
       "smtp_sasl_tls_security_options = noanonymous" \
       "smtp_tls_security_level = encrypt"
    ok "Giden posta relay üzerinden: $rh"
  elif [ "$NO_RELAY" -eq 1 ]; then
    pc "relayhost =" "smtp_sasl_auth_enable = no" "smtp_tls_security_level = may"
    rm -f "$ROOT/etc/postfix/sasl_passwd" "$ROOT/etc/postfix/sasl_passwd.db"
    ok "Relay kaldırıldı — doğrudan gönderim"
  fi
}

# ───────────────────────────── Dovecot ─────────────────────────────
render_dovecot() {
  wfile /etc/dovecot/local.conf 0644 root:root <<EOF
# Dovecot — mail-kur.sh tarafından üretildi (Dovecot 2.3). Elle değişiklik yapmayın;
# betiği yeniden çalıştırmak bu dosyayı yeniden yazar.
protocols = imap lmtp
listen = *

mail_location = maildir:$VMAIL_HOME/%d/%n
mail_uid = vmail
mail_gid = vmail
mail_privileged_group = vmail
first_valid_uid = $VMAIL_UID
last_valid_uid = $VMAIL_UID
first_valid_gid = $VMAIL_UID
last_valid_gid = $VMAIL_UID

# Kimlik doğrulama: yalnız TLS üzerinden, sanal kullanıcılar (/etc/dovecot/users)
auth_username_format = %Lu
disable_plaintext_auth = yes
auth_mechanisms = plain login
auth_failure_delay = 2 secs

passdb {
  driver = passwd-file
  args = scheme=SHA512-CRYPT username_format=%Lu /etc/dovecot/users
}
userdb {
  driver = passwd-file
  args = username_format=%Lu /etc/dovecot/users
  default_fields = uid=vmail gid=vmail home=$VMAIL_HOME/%d/%n
}

ssl = required
ssl_cert = </etc/letsencrypt/live/$HOST/fullchain.pem
ssl_key = </etc/letsencrypt/live/$HOST/privkey.pem
ssl_min_protocol = TLSv1.2
ssl_prefer_server_ciphers = yes

postmaster_address = postmaster@$DOMAIN
hostname = $HOST
login_greeting = GarajTek Mail hazir.

namespace inbox {
  inbox = yes
  mailbox Drafts {
    special_use = \Drafts
    auto = subscribe
  }
  mailbox Sent {
    special_use = \Sent
    auto = subscribe
  }
  mailbox Junk {
    special_use = \Junk
    auto = subscribe
  }
  mailbox Trash {
    special_use = \Trash
    auto = subscribe
  }
}

# Kota (kullanıcı başına: /etc/dovecot/users → userdb_quota_rule=*:storage=1G)
mail_plugins = \$mail_plugins quota
protocol imap {
  mail_plugins = \$mail_plugins imap_quota
  mail_max_userip_connections = 20
}
protocol lmtp {
  mail_plugins = \$mail_plugins
}
lmtp_rcpt_check_quota = yes
plugin {
  quota = count:User quota
  quota_vsizes = yes
  quota_rule = *:storage=1G
  quota_rule2 = Trash:storage=+100M
  quota_grace = 10%%
  quota_exceeded_message = Alicinin posta kutusu dolu / Mailbox is full
}

# Postfix entegrasyonu
service lmtp {
  unix_listener /var/spool/postfix/private/dovecot-lmtp {
    mode = 0600
    user = postfix
    group = postfix
  }
}
service auth {
  unix_listener /var/spool/postfix/private/auth {
    mode = 0660
    user = postfix
    group = postfix
  }
  unix_listener auth-userdb {
    mode = 0600
    user = vmail
  }
}
service auth-worker {
  user = \$default_internal_user
}

# 2 GB RAM: süreç sayıları düşük tutulur
service imap-login {
  inet_listener imap {
    port = 143
  }
  inet_listener imaps {
    port = 993
    ssl = yes
  }
  process_limit = 64
}
service imap {
  process_limit = 64
}
default_vsz_limit = 256M
EOF
}

setup_dovecot() {
  step "7/12 Dovecot (IMAP 993/143, LMTP, kota)"
  render_dovecot
  # Sistem (PAM) kullanıcılarıyla girişi kapat — yalnız sanal kutular
  if grep -qE '^!include auth-system\.conf\.ext' /etc/dovecot/conf.d/10-auth.conf; then
    sed -i 's/^!include auth-system\.conf\.ext/#!include auth-system.conf.ext  # mail-kur.sh: kapatildi/' \
      /etc/dovecot/conf.d/10-auth.conf
  fi
  doveconf -n >/dev/null || die "Dovecot yapılandırması hatalı (doveconf -n)"
  systemctl enable dovecot >/dev/null 2>&1 || true
  systemctl restart dovecot
  ok "Dovecot hazır"
}

# ───────────────────────────── Roundcube ─────────────────────────────
render_roundcube_config() {
  local des_key="$1"
  wfile "$RC_DIR/config/config.inc.php" 0640 root:www-data <<EOF
<?php
// Roundcube — mail-kur.sh tarafından üretildi. des_key yeniden çalıştırmada korunur.
\$config = [];
\$config['db_dsnw'] = 'sqlite:///$RC_DIR/db/sqlite.db?mode=0640';
\$config['imap_host'] = 'tls://localhost:143';
\$config['smtp_host'] = 'tls://localhost:587';
\$config['smtp_user'] = '%u';
\$config['smtp_pass'] = '%p';
// localhost'a bağlanırken sertifika adı (mail host) eşleşmez → yalnız yerel bağlantıda doğrulama kapalı
\$config['imap_conn_options'] = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false, 'allow_self_signed' => true]];
\$config['smtp_conn_options'] = ['ssl' => ['verify_peer' => false, 'verify_peer_name' => false, 'allow_self_signed' => true]];
\$config['username_domain'] = '$DOMAIN';
\$config['mail_domain'] = '$DOMAIN';
\$config['product_name'] = 'GarajTek Webmail';
\$config['support_url'] = '';
\$config['des_key'] = '$des_key';
\$config['language'] = 'tr_TR';
\$config['skin'] = 'elastic';
\$config['plugins'] = ['archive', 'zipdownload'];
\$config['enable_installer'] = false;
\$config['use_https'] = true;
\$config['ip_check'] = true;
\$config['session_lifetime'] = 60;
\$config['login_autocomplete'] = 2;
\$config['x_frame_options'] = 'sameorigin';
\$config['max_message_size'] = '25M';
\$config['log_driver'] = 'file';
\$config['log_dir'] = '/var/log/roundcube/';
\$config['temp_dir'] = '$RC_DIR/temp/';
\$config['draft_autosave'] = 120;
\$config['mime_param_folding'] = 0;
EOF
}

render_php_pool() {
  local v="${PHP_VER:-8.3}"
  wfile "/etc/php/$v/fpm/pool.d/roundcube.conf" 0644 root:root <<EOF
; Roundcube için ayrı, hafif php-fpm havuzu (2 GB RAM). mail-kur.sh
[roundcube]
user = www-data
group = www-data
listen = /run/php/roundcube.sock
listen.owner = www-data
listen.group = www-data
listen.mode = 0660
pm = ondemand
pm.max_children = 3
pm.process_idle_timeout = 30s
pm.max_requests = 200
php_admin_value[memory_limit] = 128M
php_admin_value[upload_max_filesize] = 25M
php_admin_value[post_max_size] = 26M
php_admin_value[date.timezone] = Europe/Istanbul
php_admin_value[session.gc_maxlifetime] = 21600
php_admin_flag[log_errors] = on
php_admin_flag[expose_php] = off
EOF
  wfile "/etc/php/$v/fpm/conf.d/99-garajtek-mail.ini" 0644 root:root <<EOF
; mail-kur.sh — düşük bellek
opcache.memory_consumption=32
opcache.interned_strings_buffer=4
opcache.max_accelerated_files=4000
EOF
}

setup_roundcube() {
  step "8/12 Roundcube $RC_VERSION (resmi complete tarball → $RC_DIR, SQLite)"
  local cur="" tmp url sum
  [ -f "$RC_DIR/.garajtek-version" ] && cur="$(cat "$RC_DIR/.garajtek-version")"
  if [ "$cur" != "$RC_VERSION" ]; then
    tmp="$(mktemp -d)"
    url="https://github.com/roundcube/roundcubemail/releases/download/$RC_VERSION/roundcubemail-$RC_VERSION-complete.tar.gz"
    curl -fsSL --retry 3 -o "$tmp/rc.tar.gz" "$url" || die "Roundcube indirilemedi: $url"
    sum="$(sha256sum "$tmp/rc.tar.gz" | awk '{print $1}')"
    if [ -n "$RC_SHA256" ]; then
      [ "$sum" = "$RC_SHA256" ] || die "Roundcube SHA256 uyuşmuyor! beklenen $RC_SHA256, gelen $sum"
      ok "SHA256 doğrulandı"
    else
      warn "Roundcube SHA256 = $sum — roundcube.net/download sayfasındakiyle karşılaştırın (RC_SHA256=... ile zorunlu doğrulama yapılabilir)"
    fi
    tar -xzf "$tmp/rc.tar.gz" -C "$tmp" || die "Roundcube arşivi bozuk"
    local src="$tmp/roundcubemail-$RC_VERSION"
    [ -f "$src/index.php" ] || die "Beklenmeyen arşiv yapısı"
    if [ -f "$RC_DIR/index.php" ]; then
      # Yükseltme: resmi installto.sh (config + db korunur, şema güncellenir)
      "$src/bin/installto.sh" "$RC_DIR" <<< "y" || die "Roundcube yükseltmesi başarısız"
      ok "Roundcube $cur → $RC_VERSION yükseltildi"
    else
      mkdir -p "$(dirname "$RC_DIR")"
      rm -rf "$RC_DIR"
      mv "$src" "$RC_DIR"
    fi
    rm -rf "$tmp"
    printf '%s\n' "$RC_VERSION" > "$RC_DIR/.garajtek-version"
  else
    ok "Roundcube $RC_VERSION zaten kurulu"
  fi

  # des_key: varsa koru, yoksa üret (24 karakter). NOT: tr|head yerine openssl (pipefail/SIGPIPE tuzağı)
  local des_key=""
  if [ -f "$RC_DIR/config/config.inc.php" ]; then
    des_key="$(sed -n "s/^\$config\['des_key'\] = '\([^']*\)';/\1/p" "$RC_DIR/config/config.inc.php")"
  fi
  [ ${#des_key} -eq 24 ] || des_key="$(openssl rand -hex 12)"
  render_roundcube_config "$des_key"

  install -d -o www-data -g www-data -m 0750 "$RC_DIR/db" "$RC_DIR/temp" "$RC_DIR/logs" /var/log/roundcube
  touch /var/log/roundcube/errors.log && chown www-data:www-data /var/log/roundcube/errors.log
  chown -R root:root "$RC_DIR"
  chown -R www-data:www-data "$RC_DIR/db" "$RC_DIR/temp" "$RC_DIR/logs"
  chown root:www-data "$RC_DIR/config/config.inc.php"; chmod 0640 "$RC_DIR/config/config.inc.php"
  rm -rf "$RC_DIR/installer"   # kurulum sihirbazı devre dışı

  if [ ! -s "$RC_DIR/db/sqlite.db" ]; then
    runuser -u www-data -- php "$RC_DIR/bin/initdb.sh" --dir="$RC_DIR/SQL" >/dev/null \
      || die "Roundcube veritabanı oluşturulamadı"
    ok "Roundcube SQLite veritabanı oluşturuldu"
  fi

  wfile /etc/logrotate.d/roundcube-garajtek 0644 root:root <<'EOF'
/var/log/roundcube/*.log {
    weekly
    rotate 4
    compress
    missingok
    notifempty
    su www-data www-data
    create 0640 www-data www-data
}
EOF

  render_php_pool
  # Varsayılan www havuzu da talep üzerine çalışsın (boşta RAM yemesin)
  local www="/etc/php/$PHP_VER/fpm/pool.d/www.conf"
  if [ -f "$www" ]; then
    sed -i -e 's/^pm = .*/pm = ondemand/' -e 's/^pm.max_children = .*/pm.max_children = 2/' "$www"
  fi
  systemctl enable "php$PHP_VER-fpm" >/dev/null 2>&1 || true
  systemctl restart "php$PHP_VER-fpm"
  ok "php$PHP_VER-fpm (ondemand, max_children 3)"
}

# ───────────────────────────── güvenlik duvarı + fail2ban ─────────────────────────────
render_fail2ban() {
  wfile /etc/fail2ban/jail.d/garajtek-mail.local 0644 root:root <<'EOF'
# mail-kur.sh — hafif mail jail'leri
[postfix-sasl]
enabled  = true
backend  = auto
logpath  = /var/log/mail.log
maxretry = 5
findtime = 10m
bantime  = 1h

[dovecot]
enabled  = true
backend  = auto
logpath  = /var/log/mail.log
maxretry = 5
findtime = 10m
bantime  = 1h

[roundcube-auth]
enabled  = true
backend  = auto
port     = http,https
logpath  = /var/log/roundcube/errors.log
maxretry = 5
findtime = 10m
bantime  = 1h
EOF
}

setup_firewall() {
  step "9/12 Güvenlik duvarı (ufw) + fail2ban"
  if command -v ufw >/dev/null; then
    local p
    for p in 25 465 587 993 143 80 443; do ufw allow "$p/tcp" >/dev/null; done
    if ufw status 2>/dev/null | grep -q "Status: active"; then
      ok "ufw: 25,465,587,993,143,80,443 açık"
    else
      warn "ufw kurallar eklendi ama ufw AKTİF DEĞİL (deploy/install.sh etkinleştirir; elle: ufw allow OpenSSH && ufw enable)"
    fi
  else
    warn "ufw yok — sağlayıcı güvenlik duvarında 25,465,587,993,143,80,443 açık olmalı"
  fi
  if [ "$WITH_F2B" -eq 1 ]; then
    systemctl enable --now rsyslog >/dev/null 2>&1 || true
    touch /var/log/mail.log
    render_fail2ban
    systemctl enable fail2ban >/dev/null 2>&1 || true
    systemctl restart fail2ban || warn "fail2ban başlatılamadı (journalctl -u fail2ban)"
    ok "fail2ban: postfix-sasl, dovecot, roundcube-auth"
  fi
}

# ───────────────────────────── CLI + sudoers + kutular ─────────────────────────────
render_sudoers() {
  wfile /etc/sudoers.d/garajtek-mail.new 0440 root:root <<EOF
# Admin paneli (garajtek-api servisi, kullanıcı: $API_USER) YALNIZ bu aracı root olarak çalıştırabilir.
# Araç tüm girdileri kendisi doğrular. mail-kur.sh tarafından üretildi.
$API_USER ALL=(root) NOPASSWD: /usr/local/sbin/garajtek-mail *
EOF
  if command -v visudo >/dev/null; then
    visudo -cf "$ROOT/etc/sudoers.d/garajtek-mail.new" >/dev/null \
      || { rm -f "$ROOT/etc/sudoers.d/garajtek-mail.new"; die "sudoers doğrulaması başarısız (visudo -c)"; }
  fi
  mv -f "$ROOT/etc/sudoers.d/garajtek-mail.new" "$ROOT/etc/sudoers.d/garajtek-mail"
}

install_cli() {
  step "10/12 Yönetim aracı (garajtek-mail) + sudoers + yedek"
  [ -f "$SCRIPT_DIR/garajtek-mail" ] || die "$SCRIPT_DIR/garajtek-mail bulunamadı"
  install -m 0755 -o root -g root "$SCRIPT_DIR/garajtek-mail" /usr/local/sbin/garajtek-mail
  render_conf
  render_sudoers
  id "$API_USER" >/dev/null 2>&1 || warn "'$API_USER' kullanıcısı yok — panel servisi farklı kullanıcıyla çalışıyorsa: --api-user KULLANICI"
  # Günlük yedek (03:00 civarı cron.daily) → /var/backups/garajtek/mail-*.tar.gz
  wfile /etc/cron.daily/garajtek-mail-backup 0755 root:root <<'EOF'
#!/bin/sh
/usr/local/sbin/garajtek-mail backup >> /var/log/garajtek-mail-backup.log 2>&1
EOF
  ok "/usr/local/sbin/garajtek-mail, /etc/sudoers.d/garajtek-mail, /etc/cron.daily/garajtek-mail-backup"
}

NEW_CREDS=()
ensure_mailbox() {
  local addr="$1" list res pw
  list="$(/usr/local/sbin/garajtek-mail list --json)"
  if [[ "$list" == *"\"$addr\""* ]]; then
    ok "$addr zaten var"
    return 0
  fi
  res="$(/usr/local/sbin/garajtek-mail add "$addr" --random --quota 1G --json)" || die "$addr oluşturulamadı: $res"
  pw="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["password"])' <<< "$res")"
  NEW_CREDS+=("$addr  $pw")
  ok "$addr oluşturuldu"
}

ensure_alias() {
  local src="$1" dst="$2" list
  list="$(/usr/local/sbin/garajtek-mail alias-list --json)"
  [[ "$list" == *"\"$src\""* ]] && return 0
  /usr/local/sbin/garajtek-mail alias-add "$src" "$dst" --json >/dev/null
}

setup_mailboxes() {
  step "11/12 İlk posta kutuları"
  ensure_mailbox "info@$DOMAIN"
  ensure_mailbox "noreply@$DOMAIN"
  ensure_alias "postmaster@$DOMAIN" "info@$DOMAIN"
  ensure_alias "abuse@$DOMAIN" "info@$DOMAIN"
  if [ "${#NEW_CREDS[@]}" -gt 0 ]; then
    ( umask 077
      { echo "# GarajTek mail — $(date -Is) — ilk şifreler (değiştirmeniz önerilir)"
        printf '%s\n' "${NEW_CREDS[@]}"
        echo; } >> "$CRED_FILE" )
    chmod 0600 "$CRED_FILE"
  fi
}

start_services() {
  systemctl restart opendkim dovecot
  systemctl restart postfix
  nginx_reload
  sleep 2
}

# ───────────────────────────── çıktı ─────────────────────────────
dkim_value() {
  local f="$ROOT/etc/opendkim/keys/$DOMAIN/$DKIM_SELECTOR.txt"
  if [ -f "$f" ]; then
    # Tırnak içindeki parçaları birleştir → tek satır
    tr -d '\n' < "$f" | grep -o '"[^"]*"' | tr -d '"\n' | sed 's/[[:space:]]\{1,\}/ /g; s/; */; /g'
  else
    echo "v=DKIM1; h=sha256; k=rsa; p=<opendkim-genkey çıktısı>"
  fi
}

print_dns() {
  local spf="v=spf1 mx a ip4:$PUBLIC_IP ~all" sub="${HOST%."$DOMAIN"}"
  if [[ "$RELAY_HOST" == *brevo* ]]; then spf="v=spf1 mx a ip4:$PUBLIC_IP include:spf.brevo.com ~all"; fi
  cat <<EOF

${c_b}════════ DNS KAYITLARI (Cloudflare → $DOMAIN → DNS) ════════${c_0}
 Tür  Ad                   Değer                                         Not
 A    $sub                 $PUBLIC_IP                                    Proxy KAPALI (gri bulut)
 MX   @                    $HOST  (öncelik 10)
 TXT  @                    "$spf"
 TXT  _dmarc               "v=DMARC1; p=none; rua=mailto:info@$DOMAIN"
 TXT  $DKIM_SELECTOR._domainkey    (aşağıdaki tek satır değer)

 DKIM değeri (tek parça, tırnaksız yapıştırın):
$(dkim_value)

 PTR / rDNS: $PUBLIC_IP → $HOST   ← DNS'te değil, SNET müşteri panelinde ayarlanır.
EOF
  [ -n "$RELAY_HOST" ] && [[ "$RELAY_HOST" != *brevo* ]] && \
    echo " Relay ($RELAY_HOST) kullanıyorsanız sağlayıcının SPF include'unu da SPF kaydına ekleyin."
  echo " Mevcut bir SPF kaydı varsa İKİNCİ kayıt eklemeyin; tek kayıtta birleştirin."
  echo " Kontrol: garajtek-mail dns-check   (Admin › Ayarlar › Mail Yönetimi › DNS sekmesi)"
}

summary() {
  step "12/12 Doğrulama"
  local s st
  for s in postfix dovecot opendkim nginx "php$PHP_VER-fpm"; do
    st="$(systemctl is-active "$s" 2>/dev/null || true)"
    if [ "$st" = "active" ]; then ok "$s: active"; else warn "$s: $st (journalctl -u $s)"; fi
  done
  local listening; listening="$(ss -ltnH | awk '{print $4}' | sed 's/.*://' | sort -un | tr '\n' ' ')"
  for s in 25 143 465 587 993 443 8891; do
    if [[ " $listening " == *" $s "* ]]; then ok "port $s dinleniyor"; else warn "port $s dinlenmiyor"; fi
  done
  check_ptr
  print_dns
  cat <<EOF

${c_b}════════ ÖZET ════════${c_0}
 Webmail:  https://$HOST   (kullanıcı: info  veya  info@$DOMAIN)
 İstemci:  IMAP $HOST 993 SSL/TLS · SMTP $HOST 465 SSL/TLS veya 587 STARTTLS (kullanıcı = tam adres)
 Giden 25: $PORT25 ${RELAY_HOST:+(relay: $RELAY_HOST)}
EOF
  if [ "${#NEW_CREDS[@]}" -gt 0 ]; then
    echo
    echo " ${c_warn}YENİ ŞİFRELER (yalnız şimdi gösterilir; $CRED_FILE içine de kaydedildi, 0600):${c_0}"
    printf '   %s\n' "${NEW_CREDS[@]}"
  fi
  cat <<EOF

 Site bildirimleri bu sunucudan gitsin:
   Admin › Ayarlar › Mail Yönetimi › "Site bildirimlerini bu sunucudan gönder" butonu
   (veya elle: SMTP 127.0.0.1 : 587 STARTTLS, kullanıcı noreply@$DOMAIN, şifre yukarıda)
 Test:  garajtek-mail test-send adresiniz@gmail.com   →  Gmail › Orijinali göster: SPF/DKIM/DMARC = PASS
EOF
  if [ "${#WARNINGS[@]}" -gt 0 ]; then
    echo; echo " ${c_warn}Uyarılar:${c_0}"; printf '   - %s\n' "${WARNINGS[@]}"
  fi
}

# ───────────────────────────── dry-run ─────────────────────────────
dry_run() {
  echo "DRY-RUN: yapılandırmalar $ROOT altına üretiliyor (sistem DEĞİŞTİRİLMEZ)"
  [ -n "$PUBLIC_IP" ] || PUBLIC_IP="203.0.113.10"
  PHP_VER="${PHP_VER:-8.3}"
  : > "$ROOT/postconf-commands.sh"
  render_conf
  render_nginx_http; cp "$ROOT$NGINX_SITE" "$ROOT$NGINX_SITE.http-only"
  render_nginx_https
  render_certbot_hook
  render_opendkim
  render_postfix_maps
  setup_postfix
  render_dovecot
  render_roundcube_config "$(openssl rand -hex 12)"
  render_php_pool
  render_fail2ban
  render_sudoers
  print_dns
  echo; echo "Üretilen dosyalar:"; (cd "$ROOT" && find . -type f | sort)
}

main() {
  if [ "$DRY" -eq 1 ]; then dry_run; exit 0; fi
  prechecks
  install_packages
  setup_vmail
  setup_tls
  setup_opendkim
  setup_postfix
  setup_dovecot
  setup_roundcube
  render_nginx_https
  setup_firewall
  install_cli
  start_services
  setup_mailboxes
  summary
}

main "$@"
