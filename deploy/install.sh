#!/usr/bin/env bash
# =============================================================================
# garajtek — tek sunucu kurulumu (Ubuntu 24.04 LTS, 2 vCPU / 2 GB RAM, root SSH)
#           Cloudflare (DNS + proxy + SSL) arkasında. İdempotent: tekrar çalıştırmak güvenlidir.
#
#   bash install.sh garajtek.com [--admin-email siz@ornek.com] [--cf-firewall] [--no-cf-lock]
#                                [--repo URL] [--branch main]
#
#   --admin-email   ilk yönetici e-postası (varsayılan: admin@<alan>) — yalnız .env ilk üretilirken
#   --cf-firewall   ufw: 80/443'ü YALNIZ Cloudflare IP'lerine aç. Aynı sunucuda posta/webmail
#                   (deploy/mail/) varsa KULLANMAYIN — mail.<alan> gri bulut, herkese açık olmalı.
#   --no-cf-lock    nginx'te "ana site yalnız Cloudflare üzerinden" kilidini kapat (test için)
#   --repo/--branch kod sunucuda yoksa klonlanacak depo (varsayılan: GitHub garajtek, main)
#
# Kurar: paketler, 2 GB swap, garajtek kullanıcısı, /opt/garajtek (kod + venv + data + media),
#        systemd garajtek-api (uvicorn, 1 işçi, 127.0.0.1:8001), nginx (SPA + /api + /media),
#        Cloudflare gerçek IP + kilit, ufw, fail2ban, gece yedeği (03:30), haftalık CF IP güncellemesi.
# =============================================================================
set -euo pipefail

DOMAIN="${1:-}"
[ -n "$DOMAIN" ] && [ "${DOMAIN#-}" = "$DOMAIN" ] || { sed -n '5,13p' "$0"; exit 2; }
shift
ADMIN_EMAIL=""; CF_FIREWALL=0; CF_LOCK=1
REPO_URL="${REPO_URL:-https://github.com/kdrgry1-oss/garajtek.git}"; BRANCH="${BRANCH:-main}"
while [ $# -gt 0 ]; do
  case "$1" in
    --admin-email) ADMIN_EMAIL="${2:?}"; shift ;;
    --cf-firewall) CF_FIREWALL=1 ;;
    --no-cf-lock) CF_LOCK=0 ;;
    --repo) REPO_URL="${2:?}"; shift ;;
    --branch) BRANCH="${2:?}"; shift ;;
    *) echo "bilinmeyen seçenek: $1" >&2; exit 2 ;;
  esac
  shift
done
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@$DOMAIN}"

APP=/opt/garajtek
APP_USER=garajtek
WEB=/var/www/garajtek
SSL_DIR=/etc/ssl/cloudflare
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC_ROOT=$(dirname "$SCRIPT_DIR")
STEP=0
step() { STEP=$((STEP + 1)); echo; echo "▶ $STEP) $*"; }
warn() { echo "!! $*" >&2; }

[ "$(id -u)" = 0 ] || { echo "root olarak çalıştırın: sudo bash $0 $DOMAIN" >&2; exit 1; }
for f in nginx/garajtek.conf nginx/default.conf nginx/proxy.conf nginx/security-headers.conf \
         systemd/garajtek-api.service env.example update.sh backup.sh restore.sh cloudflare-ips.sh; do
  [ -f "$SCRIPT_DIR/$f" ] || { echo "eksik dosya: $SCRIPT_DIR/$f (deploy/ klasörünün tamamı gerekli)" >&2; exit 1; }
done
# shellcheck disable=SC1091
. /etc/os-release
[ "${ID:-}" = ubuntu ] && [ "${VERSION_ID:-}" = "24.04" ] || warn "Ubuntu 24.04 bekleniyordu (bulunan: ${PRETTY_NAME:-?}) — devam ediliyor"

# -----------------------------------------------------------------------------
step "Sistem paketleri + saat dilimi (Europe/Istanbul)"
export DEBIAN_FRONTEND=noninteractive
timedatectl set-timezone Europe/Istanbul 2>/dev/null || ln -sf /usr/share/zoneinfo/Europe/Istanbul /etc/localtime
apt-get update -qq
apt-get install -y -qq --no-install-recommends \
  ca-certificates curl git rsync openssl sqlite3 nginx ufw fail2ban \
  python3 python3-venv python3-dev build-essential unattended-upgrades >/dev/null
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || { echo "Python 3.11+ gerekli ($(python3 -V)). Ubuntu 24.04 kullanın." >&2; exit 1; }

# -----------------------------------------------------------------------------
step "Swap (2 GB) + bellek ayarları"
if ! swapon --show=NAME --noheadings | grep -q .; then
  if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none
    chmod 600 /swapfile
    mkswap -q /swapfile
  fi
  swapon /swapfile 2>/dev/null || warn "swap etkinleştirilemedi (sanallaştırma izin vermiyor olabilir)"
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
cat > /etc/sysctl.d/99-garajtek.conf <<'EOF'
vm.swappiness=10
vm.vfs_cache_pressure=50
EOF
sysctl -q --system >/dev/null 2>&1 || true
mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=300M\n' > /etc/systemd/journald.conf.d/garajtek.conf
systemctl restart systemd-journald 2>/dev/null || true

# -----------------------------------------------------------------------------
step "Kullanıcı ve uygulama kodu ($APP)"
if ! id "$APP_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP" --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi
CODE=1
if [ -d "$APP/backend/routes" ]; then
  echo "   kod mevcut"
elif [ -d "$SRC_ROOT/backend/routes" ] && [ "$SRC_ROOT" != "$APP" ]; then
  echo "   kod kopyalanıyor: $SRC_ROOT → $APP"
  mkdir -p "$APP"
  rsync -a --exclude node_modules --exclude 'frontend/build' --exclude 'backend/.env' \
        --exclude 'backend/data/' --exclude '__pycache__' "$SRC_ROOT"/ "$APP"/
elif [ ! -e "$APP" ] || [ -z "$(ls -A "$APP" 2>/dev/null)" ]; then
  echo "   klonlanıyor: $REPO_URL ($BRANCH)"
  if ! GIT_TERMINAL_PROMPT=0 git clone -q --branch "$BRANCH" "$REPO_URL" "$APP"; then
    warn "depo klonlanamadı (özel depo olabilir). Sistem kurulumu sürüyor; kodu GitHub Actions ile gönderin (KURULUM.md §7)."
    CODE=0
  fi
else
  warn "$APP dolu ama backend/ yok — kod atlanıyor"
  CODE=0
fi
mkdir -p "$APP/backend" "$APP/data" "$APP/media" "$WEB" /var/www/html /var/backups/garajtek /etc/garajtek
chown -R "$APP_USER:$APP_USER" "$APP"
chmod 755 "$APP" "$APP/media"
chmod 700 "$APP/data" /var/backups/garajtek

cat > /etc/garajtek/deploy.conf <<EOF
# install.sh üretti — update.sh / garajtek-cloudflare-ips okur.
DOMAIN=$DOMAIN
CF_LOCK=$CF_LOCK
CF_FIREWALL=$CF_FIREWALL
EOF

# -----------------------------------------------------------------------------
step "Ortam dosyası ($APP/backend/.env)"
CREDS=/root/garajtek-ilk-giris.txt
if [ -f "$APP/backend/.env" ]; then
  echo "   mevcut .env korunuyor"
  if grep -qE '^(MONGO_URL|DB_NAME)=' "$APP/backend/.env" && ! grep -q '^DB_PATH=' "$APP/backend/.env"; then
    echo "DB_PATH=$APP/data/store.db" >> "$APP/backend/.env"
    echo "   DB_PATH eklendi"
  fi
  grep -q '^MEDIA_DIR=' "$APP/backend/.env" || echo "MEDIA_DIR=$APP/media" >> "$APP/backend/.env"
else
  JWT=$(openssl rand -hex 32)
  FERNET=$(openssl rand -base64 32 | tr '+/' '-_')
  EDGE=$(openssl rand -hex 24)
  ADMIN_PW="Gt$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 16)!7"
  sed -e "s|__JWT_SECRET__|$JWT|" -e "s|__SECRETS_MASTER_KEY__|$FERNET|" \
      -e "s|__CF_EDGE_SECRET__|$EDGE|" -e "s|__ADMIN_PASSWORD__|$ADMIN_PW|" \
      -e "s|__ADMIN_EMAIL__|$ADMIN_EMAIL|g" -e "s|garajtek\.com|$DOMAIN|g" \
      "$SCRIPT_DIR/env.example" > "$APP/backend/.env"
  umask 077
  cat > "$CREDS" <<EOF
garajtek ilk giriş bilgileri — $(date '+%F %T')
Panel     : https://$DOMAIN/admin
E-posta   : $ADMIN_EMAIL
Parola    : $ADMIN_PW   (ilk girişte değiştirin, sonra .env'deki ADMIN_INITIAL_PASSWORD satırını boşaltın)

Cloudflare Transform Rule (KURULUM.md §3.5) — istek başlığı ekle:
  Başlık adı : X-Edge-Secret
  Değer      : $EDGE

Bu dosyayı okuduktan sonra silin:  rm $CREDS
EOF
  umask 022
  echo "   .env üretildi; ilk giriş bilgileri: $CREDS"
fi
chown "$APP_USER:$APP_USER" "$APP/backend/.env"
chmod 600 "$APP/backend/.env"

if [ ! -f /etc/garajtek/frontend.env ]; then
  cat > /etc/garajtek/frontend.env <<EOF
# Frontend derleme değişkenleri (yalnız sunucuda derlerken: update.sh --build-frontend).
# GitHub Actions bunun yerine depo Variables'ını kullanır (.github/workflows/deploy.yml).
REACT_APP_BACKEND_URL=https://$DOMAIN
REACT_APP_SITE_URL=https://$DOMAIN
REACT_APP_SITE_NAME=Garajtek
EOF
fi

# -----------------------------------------------------------------------------
step "TLS sertifikası (Cloudflare Origin Certificate)"
install -d -m 755 "$SSL_DIR"
if [ ! -s "$SSL_DIR/$DOMAIN.pem" ] || [ ! -s "$SSL_DIR/$DOMAIN.key" ]; then
  openssl req -x509 -nodes -newkey rsa:2048 -days 3650 -subj "/CN=$DOMAIN" \
    -addext "subjectAltName=DNS:$DOMAIN,DNS:*.$DOMAIN" \
    -keyout "$SSL_DIR/$DOMAIN.key" -out "$SSL_DIR/$DOMAIN.pem" 2>/dev/null
  touch "$SSL_DIR/$DOMAIN.GECICI"
  warn "GEÇİCİ (self-signed) sertifika üretildi. Cloudflare SSL modu 'Full' ile çalışır; 'Full (strict)'"
  warn "için Origin Certificate'ı $SSL_DIR/$DOMAIN.pem ve .key dosyalarına yapıştırın (KURULUM.md §3.3)."
else
  echo "   mevcut sertifika kullanılıyor ($SSL_DIR/$DOMAIN.pem)"
fi
chmod 644 "$SSL_DIR/$DOMAIN.pem"
chmod 600 "$SSL_DIR/$DOMAIN.key"

# -----------------------------------------------------------------------------
step "nginx (SPA + /api + /media, Cloudflare gerçek IP)"
install -m 0644 "$SCRIPT_DIR/nginx/proxy.conf"            /etc/nginx/snippets/garajtek-proxy.conf
install -m 0644 "$SCRIPT_DIR/nginx/security-headers.conf" /etc/nginx/snippets/garajtek-security-headers.conf
if [ "$CF_LOCK" = 1 ]; then
  cat > /etc/nginx/snippets/garajtek-cf-lock.conf <<'EOF'
# Ana site yalnız Cloudflare üzerinden: CF dışından (doğrudan IP) gelen bağlantı kapatılır.
# Kapatmak için: install.sh ... --no-cf-lock   (ya da bu satırı silip nginx'i yeniden yükleyin)
if ($garajtek_from_cf = 0) { return 444; }
EOF
else
  echo "# CF kilidi kapalı (--no-cf-lock)" > /etc/nginx/snippets/garajtek-cf-lock.conf
fi
printf 'server_tokens off;\n' > /etc/nginx/conf.d/garajtek-tuning.conf
sed "s/__DOMAIN__/$DOMAIN/g" "$SCRIPT_DIR/nginx/garajtek.conf" > /etc/nginx/sites-available/garajtek
install -m 0644 "$SCRIPT_DIR/nginx/default.conf" /etc/nginx/sites-available/garajtek-default
if [ ! -f /proc/net/if_inet6 ]; then   # IPv6 kapalı çekirdek: [::] dinleyicilerini çıkar
  sed -i '/listen \[::\]/d' /etc/nginx/sites-available/garajtek /etc/nginx/sites-available/garajtek-default
fi
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/garajtek-default /etc/nginx/sites-enabled/garajtek-default
ln -sf /etc/nginx/sites-available/garajtek /etc/nginx/sites-enabled/garajtek
install -m 0755 "$SCRIPT_DIR/cloudflare-ips.sh" /usr/local/sbin/garajtek-cloudflare-ips
/usr/local/sbin/garajtek-cloudflare-ips || warn "Cloudflare IP güncellemesi başarısız"
if [ ! -f "$WEB/index.html" ]; then
  cat > "$WEB/index.html" <<EOF
<!doctype html><html lang="tr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>$DOMAIN</title><body style="font-family:system-ui;text-align:center;padding:15vh 1rem">
<h1>$DOMAIN</h1><p>Mağaza hazırlanıyor — yakında burada.</p></body></html>
EOF
fi
chmod -R a+rX "$WEB" /var/www/html
nginx -t
systemctl enable --now nginx >/dev/null 2>&1
systemctl reload nginx

# -----------------------------------------------------------------------------
step "systemd: garajtek-api + zamanlayıcılar"
install -m 0755 "$SCRIPT_DIR/backup.sh"  /usr/local/sbin/garajtek-backup
install -m 0755 "$SCRIPT_DIR/restore.sh" /usr/local/sbin/garajtek-restore
install -m 0755 "$SCRIPT_DIR/update.sh"  /usr/local/sbin/garajtek-update
for u in "$SCRIPT_DIR"/systemd/*.service "$SCRIPT_DIR"/systemd/*.timer; do
  install -m 0644 "$u" "/etc/systemd/system/$(basename "$u")"
done
systemctl daemon-reload
systemctl enable garajtek-api >/dev/null 2>&1
systemctl enable --now garajtek-backup.timer garajtek-cloudflare-ips.timer >/dev/null 2>&1

# -----------------------------------------------------------------------------
step "Güvenlik duvarı (ufw) + fail2ban"
SSH_PORTS=$( (sshd -T 2>/dev/null || true) | awk '/^port /{print $2}' | sort -u)
[ -n "$SSH_PORTS" ] || SSH_PORTS=22
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
for p in $SSH_PORTS; do ufw allow "$p/tcp" comment ssh >/dev/null; done
if [ "$CF_FIREWALL" = 1 ]; then
  echo "   80/443 yalnız Cloudflare'e açılıyor (--cf-firewall)"
else
  ufw allow 80/tcp >/dev/null
  ufw allow 443/tcp >/dev/null
fi
ufw --force enable >/dev/null
/usr/local/sbin/garajtek-cloudflare-ips >/dev/null || true   # ufw CF kurallarını eşitle
systemctl enable --now fail2ban >/dev/null 2>&1 || true
echo "   SSH portları: $SSH_PORTS"

# -----------------------------------------------------------------------------
step "Uygulama (Python ortamı, bağımlılıklar, servis)"
APP_OK=0
if [ "$CODE" = 1 ] && [ -d "$APP/backend/routes" ]; then
  if bash "$SCRIPT_DIR/update.sh" --no-pull; then APP_OK=1; else warn "uygulama başlatılamadı — journalctl -u garajtek-api -n 100"; fi
else
  warn "kod yok — uygulama adımı atlandı. Kod geldikten sonra: bash $APP/deploy/update.sh --no-pull"
fi

# -----------------------------------------------------------------------------
echo
echo "================================================================================"
echo "✔ Kurulum tamamlandı — $DOMAIN"
echo "================================================================================"
[ "$APP_OK" = 1 ] && echo "  API          : çalışıyor (systemctl status garajtek-api)"
[ -f "$CREDS" ]   && echo "  İlk giriş    : cat $CREDS   (okuduktan sonra silin)"
[ -f "$SSL_DIR/$DOMAIN.GECICI" ] && echo "  SERTİFİKA    : GEÇİCİ — Origin Certificate'ı yapıştırın (KURULUM.md §3.3)"
grep -q 'Mağaza hazırlanıyor' "$WEB/index.html" 2>/dev/null && \
  echo "  Frontend     : henüz yok — GitHub Actions 'Deploy' iş akışını çalıştırın (KURULUM.md §7)"
echo "  Ayarlar      : nano $APP/backend/.env  →  systemctl restart garajtek-api"
echo "  Yedek        : her gece 03:30 → /var/backups/garajtek (elle: garajtek-backup)"
echo "  Güncelleme   : garajtek-update   (ya da GitHub'a push → otomatik)"
echo "  Loglar       : journalctl -u garajtek-api -f"
