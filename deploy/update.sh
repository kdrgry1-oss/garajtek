#!/usr/bin/env bash
# garajtek — uygulama güncelleme / dağıtım (idempotent). root olarak çalıştırın.
#
#   bash /opt/garajtek/deploy/update.sh                 # git pull + bağımlılıklar + yeniden başlat + sağlık
#   bash /opt/garajtek/deploy/update.sh --no-pull       # kod zaten yerinde (GitHub Actions rsync'i / scp)
#   bash /opt/garajtek/deploy/update.sh --frontend DIR  # hazır derlenmiş frontend'i (DIR/index.html) yayınla
#   bash /opt/garajtek/deploy/update.sh --build-frontend  # frontend'i SUNUCUDA derle (Node 20 gerekir; 2 GB'ta yavaş)
#
# Diğer: --no-restart (yalnız hazırla), --skip-health
set -euo pipefail

APP=/opt/garajtek
WEB=/var/www/garajtek
SVC=garajtek-api
APP_USER=garajtek
PORT=8001
CONF=/etc/garajtek/deploy.conf

PULL=1; FRONT=""; BUILD=0; RESTART=1; HEALTH=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-pull) PULL=0 ;;
    --frontend) FRONT="${2:?--frontend DIZIN gerekli}"; shift ;;
    --build-frontend) BUILD=1 ;;
    --no-restart) RESTART=0 ;;
    --skip-health) HEALTH=0 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "bilinmeyen seçenek: $1" >&2; exit 2 ;;
  esac
  shift
done

die() { echo "!! $*" >&2; exit 1; }
log() { echo "▶ $*"; }
as_app() { runuser -u "$APP_USER" -- env HOME="$APP" "$@"; }

[ "$(id -u)" = 0 ] || die "root olarak çalıştırın (sudo bash $0)"
id "$APP_USER" >/dev/null 2>&1 || die "'$APP_USER' kullanıcısı yok — önce deploy/install.sh çalıştırın"
[ -d "$APP/backend" ] || die "$APP/backend yok — kod yerinde değil"
[ -f "$APP/backend/.env" ] || die "$APP/backend/.env yok — önce deploy/install.sh çalıştırın"
DOMAIN=""
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

exec 9>/run/garajtek-update.lock
flock -n 9 || die "başka bir güncelleme sürüyor"

# ---- 1) Kod ---------------------------------------------------------------------
BEFORE=""
if [ "$PULL" = 1 ] && [ -d "$APP/.git" ]; then
  chown -R "$APP_USER:$APP_USER" "$APP/.git"
  BEFORE=$(as_app git -C "$APP" rev-parse HEAD 2>/dev/null || true)
  log "git pull ($(as_app git -C "$APP" rev-parse --abbrev-ref HEAD))"
  as_app git -C "$APP" pull --ff-only \
    || die "git pull başarısız (yerel değişiklik veya erişim sorunu). Özel depo ise GitHub Actions ile dağıtın (KURULUM.md §7)."
elif [ "$PULL" = 1 ]; then
  log "git deposu değil — kod olduğu gibi kullanılıyor (--no-pull)"
fi
SHA=$(as_app git -C "$APP" rev-parse HEAD 2>/dev/null || cat "$APP/REVISION" 2>/dev/null || echo "")

# ---- 2) Sahiplik / izinler --------------------------------------------------------
log "izinler"
mkdir -p "$APP/data" "$APP/media"
chown -R "$APP_USER:$APP_USER" "$APP"
chmod 755 "$APP" "$APP/media"
chmod 700 "$APP/data"
chmod 600 "$APP/backend/.env"

# ---- 3) Python sanal ortamı + bağımlılıklar --------------------------------------
PY=$(command -v python3.12 || command -v python3)
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' \
  || die "Python 3.11+ gerekli ($("$PY" -V 2>&1)). Ubuntu 24.04 kullanın."
if [ ! -x "$APP/venv/bin/python" ]; then
  log "sanal ortam oluşturuluyor ($("$PY" -V))"
  as_app "$PY" -m venv "$APP/venv"
fi
REQ="$APP/backend/requirements.txt"
REQ_HASH=$(sha256sum "$REQ" | cut -d' ' -f1)
if [ "$(cat "$APP/venv/.req.sha256" 2>/dev/null)" != "$REQ_HASH" ]; then
  log "Python bağımlılıkları kuruluyor (ilk kurulumda 3-8 dk)"
  # requirements.txt'deki --extra-index-url (eski barındırma ortamına ait özel indeks) atlanır;
  # tüm paketler PyPI'da mevcuttur.
  grep -vE '^[[:space:]]*--(extra-)?index-url' "$REQ" > "$APP/venv/requirements.pypi.txt"
  chown "$APP_USER:$APP_USER" "$APP/venv/requirements.pypi.txt"
  as_app "$APP/venv/bin/pip" install -q --no-cache-dir --disable-pip-version-check --upgrade pip wheel
  as_app "$APP/venv/bin/pip" install -q --no-cache-dir --disable-pip-version-check -r "$APP/venv/requirements.pypi.txt"
  echo "$REQ_HASH" > "$APP/venv/.req.sha256"
  chown "$APP_USER:$APP_USER" "$APP/venv/.req.sha256"
else
  log "Python bağımlılıkları güncel"
fi

log "sözdizimi denetimi"
as_app "$APP/venv/bin/python" -m compileall -q "$APP/backend" >/dev/null \
  || die "backend derlenemedi (sözdizimi hatası) — servis yeniden BAŞLATILMADI"

# ---- 4) Yardımcı betikler + systemd birimleri (depodaki sürümle eşitle) ----------
if [ -d "$APP/deploy" ]; then
  install -m 0755 "$APP/deploy/backup.sh"         /usr/local/sbin/garajtek-backup
  install -m 0755 "$APP/deploy/restore.sh"        /usr/local/sbin/garajtek-restore
  install -m 0755 "$APP/deploy/cloudflare-ips.sh" /usr/local/sbin/garajtek-cloudflare-ips
  install -m 0755 "$APP/deploy/update.sh"         /usr/local/sbin/garajtek-update
  units_changed=0
  for u in "$APP"/deploy/systemd/*.service "$APP"/deploy/systemd/*.timer; do
    [ -f "$u" ] || continue
    dst="/etc/systemd/system/$(basename "$u")"
    if ! cmp -s "$u" "$dst"; then install -m 0644 "$u" "$dst"; units_changed=1; fi
  done
  [ "$units_changed" = 1 ] && systemctl daemon-reload
fi

# ---- 5) Frontend -----------------------------------------------------------------
if [ "$BUILD" = 1 ]; then
  command -v node >/dev/null || die "Node.js yok. Sunucuda derlemek yerine GitHub Actions'ı kullanın ya da: KURULUM.md §7.3"
  command -v yarn >/dev/null || corepack enable >/dev/null 2>&1 || npm i -g yarn >/dev/null
  log "frontend sunucuda derleniyor (2 GB RAM'de 5-15 dk; swap kullanır)"
  set -a
  # shellcheck disable=SC1091
  [ -f /etc/garajtek/frontend.env ] && . /etc/garajtek/frontend.env
  set +a
  ( cd "$APP/frontend" && as_app yarn install --frozen-lockfile --network-timeout 600000 \
    && as_app env NODE_OPTIONS=--max-old-space-size=1280 GENERATE_SOURCEMAP=false CI=false npx craco build )
  FRONT="$APP/frontend/build"
fi
if [ -n "$FRONT" ]; then
  [ -f "$FRONT/index.html" ] || die "$FRONT/index.html yok — geçerli bir frontend derlemesi değil"
  log "frontend yayınlanıyor → $WEB"
  mkdir -p "$WEB"
  # Önce varlıklar (eski hash'li dosyalar SİLİNMEZ → açık sekmeler kırılmaz), en son index.html.
  rsync -a --exclude index.html "$FRONT"/ "$WEB"/
  cp "$FRONT/index.html" "$WEB/.index.html.new" && mv -f "$WEB/.index.html.new" "$WEB/index.html"
  # 30 günden eski, artık kullanılmayan paketleri temizle
  find "$WEB/static" -type f -mtime +30 -delete 2>/dev/null || true
  chown -R root:root "$WEB"
  chmod -R a+rX "$WEB"
fi

# ---- 6) Sürüm bilgisi + yeniden başlat --------------------------------------------
echo "GIT_SHA=$SHA" > "$APP/.deploy.env"
chown "$APP_USER:$APP_USER" "$APP/.deploy.env"

if [ "$RESTART" = 0 ]; then
  log "hazır (servis yeniden başlatılmadı: --no-restart)"
  exit 0
fi

log "servis yeniden başlatılıyor ($SVC)"
systemctl enable "$SVC" >/dev/null 2>&1 || true
systemctl restart "$SVC"

[ "$HEALTH" = 1 ] || exit 0
log "sağlık kontrolü (en fazla 3 dk)"
ok=0
for _ in $(seq 1 90); do
  if out=$(curl -fsS --noproxy "*" --max-time 5 "http://127.0.0.1:$PORT/api/health" 2>/dev/null); then ok=1; break; fi
  sleep 2
done
if [ "$ok" != 1 ]; then
  echo "!! API sağlık kontrolünden geçmedi. Son loglar:" >&2
  journalctl -u "$SVC" -n 60 --no-pager >&2 || true
  [ -n "$BEFORE" ] && echo "Geri almak için: sudo -u $APP_USER git -C $APP checkout $BEFORE && bash $0 --no-pull" >&2
  exit 1
fi
echo "   API: $out"
case "$out" in *degraded*) echo "!! API ayakta ama veritabanı 'degraded' — journalctl -u $SVC" >&2 ;; esac

if [ -n "$DOMAIN" ] && systemctl is-active --quiet nginx; then
  code=$(curl -sk --noproxy "*" -o /dev/null -w '%{http_code}' --max-time 10 \
    --resolve "$DOMAIN:443:127.0.0.1" "https://$DOMAIN/api/health" || true)
  echo "   nginx → API (https://$DOMAIN/api/health, yerel): HTTP $code"
  [ "$code" = 200 ] || echo "!! nginx üzerinden API'ye ulaşılamadı — nginx -t; tail /var/log/nginx/garajtek.error.log" >&2
fi
log "tamam (sürüm ${SHA:0:12})"
