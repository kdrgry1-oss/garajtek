#!/usr/bin/env bash
# garajtek — yedekten geri yükleme. root olarak çalıştırın.
#
#   garajtek-restore /var/backups/garajtek/garajtek-20261001-033000.tar.gz
#   garajtek-restore garajtek-20261001-033000.tar.gz.enc          # şifreli (BACKUP_PASSPHRASE)
#   garajtek-restore r2:backups/garajtek-20261001-033000.tar.gz   # R2'den indirip yükle
#   garajtek-restore --list-r2                                    # R2'deki yedekleri listele
#
# Seçenekler:
#   --with-env   yedekteki .env'i de geri yükler (YENİ sunucuya taşırken; mevcut .env yedeklenir)
#   --no-media   medya dosyalarını geri yükleme
#   --yes        onay sorma
#
# Mevcut veritabanı önce /var/backups/garajtek/pre-restore-<zaman>/ altına kopyalanır.
set -euo pipefail
umask 077

APP=/opt/garajtek
ENVF=$APP/backend/.env
DIR=/var/backups/garajtek
APP_USER=garajtek
SVC=garajtek-api

die() { echo "!! $*" >&2; exit 1; }
envget() {
  grep -E "^$1=" "$ENVF" 2>/dev/null | tail -n1 | cut -d= -f2- | sed -E 's/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/' || true
}
r2py() {  # $1 = list | get, $2 = key, $3 = hedef
  local EP AK SK B
  B=$(envget BACKUP_R2_BUCKET)
  EP=$(envget BACKUP_R2_ENDPOINT);          EP=${EP:-$(envget R2_ENDPOINT)}
  AK=$(envget BACKUP_R2_ACCESS_KEY_ID);     AK=${AK:-$(envget R2_ACCESS_KEY_ID)}
  SK=$(envget BACKUP_R2_SECRET_ACCESS_KEY); SK=${SK:-$(envget R2_SECRET_ACCESS_KEY)}
  [ -n "$B" ] && [ -n "$EP" ] && [ -n "$AK" ] && [ -n "$SK" ] || die "BACKUP_R2_* (.env) eksik"
  R2_EP="$EP" R2_AK="$AK" R2_SK="$SK" R2_BUCKET_NAME="$B" "$APP/venv/bin/python" - "$@" <<'PY'
import os, sys, boto3
s3 = boto3.client("s3", endpoint_url=os.environ["R2_EP"], aws_access_key_id=os.environ["R2_AK"],
                  aws_secret_access_key=os.environ["R2_SK"], region_name="auto")
b = os.environ["R2_BUCKET_NAME"]
if sys.argv[1] == "list":
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=b, Prefix="backups/"):
        for o in page.get("Contents", []):
            print(f"r2:{o['Key']}\t{o['Size']/1e6:.1f} MB\t{o['LastModified']:%Y-%m-%d %H:%M}")
else:
    s3.download_file(b, sys.argv[2], sys.argv[3])
PY
}

[ "$(id -u)" = 0 ] || die "root olarak çalıştırın"
WITH_ENV=0; MEDIA=1; YES=0; SRC=""
while [ $# -gt 0 ]; do
  case "$1" in
    --with-env) WITH_ENV=1 ;;
    --no-media) MEDIA=0 ;;
    --yes|-y) YES=1 ;;
    --list-r2) r2py list; exit 0 ;;
    -h|--help) sed -n '2,17p' "$0"; exit 0 ;;
    *) [ -z "$SRC" ] || die "tek yedek dosyası verin"; SRC="$1" ;;
  esac
  shift
done
[ -n "$SRC" ] || { sed -n '2,17p' "$0"; echo; echo "Yerel yedekler:"; ls -1t "$DIR"/garajtek-*.tar.gz* 2>/dev/null || true; exit 2; }

WORK=$(mktemp -d /var/tmp/garajtek-restore.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

# ---- 1) Yedeği hazırla ---------------------------------------------------------------
case "$SRC" in
  r2:*)
    KEY=${SRC#r2:}
    echo "▶ R2'den indiriliyor: $KEY"
    r2py get "$KEY" "$WORK/$(basename "$KEY")"
    SRC="$WORK/$(basename "$KEY")" ;;
  /*|./*) ;;
  *) [ -f "$SRC" ] || SRC="$DIR/$SRC" ;;
esac
[ -f "$SRC" ] || die "yedek bulunamadı: $SRC"

ARCHIVE="$SRC"
if [[ "$SRC" == *.enc ]]; then
  PASS=$(envget BACKUP_PASSPHRASE)
  if [ -z "$PASS" ]; then read -r -s -p "BACKUP_PASSPHRASE: " PASS; echo; fi
  ARCHIVE="$WORK/backup.tar.gz"
  BACKUP_PASSPHRASE="$PASS" openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -in "$SRC" -out "$ARCHIVE" -pass env:BACKUP_PASSPHRASE || die "şifre çözülemedi (parola yanlış?)"
fi

mkdir -p "$WORK/x"
tar -xzf "$ARCHIVE" -C "$WORK/x"
HAS_DB=0
if [ -f "$WORK/x/store.db" ]; then
  chk=$(python3 -c 'import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute("PRAGMA quick_check").fetchone()[0])' "$WORK/x/store.db")
  [ "$chk" = ok ] || die "yedekteki veritabanı bozuk: $chk"
  HAS_DB=1
fi

if [ "$WITH_ENV" = 1 ] && [ -f "$WORK/x/dotenv" ]; then ENV_SOURCE="$WORK/x/dotenv"; else ENV_SOURCE="$ENVF"; fi
DB_PATH=$(grep -E '^DB_PATH=' "$ENV_SOURCE" 2>/dev/null | tail -n1 | cut -d= -f2- || true)
DB_PATH=${DB_PATH:-$APP/backend/data/store.db}
MEDIA_DIR=$(grep -E '^MEDIA_DIR=' "$ENV_SOURCE" 2>/dev/null | tail -n1 | cut -d= -f2- || true)

echo "Geri yüklenecek: $(basename "$SRC")"
echo "  veritabanı : $([ $HAS_DB = 1 ] && echo "evet → $DB_PATH" || echo yok)"
echo "  medya      : $([ $MEDIA = 1 ] && [ -d "$WORK/x/media" ] && echo "evet → ${MEDIA_DIR:-?}" || echo hayır)"
echo "  .env       : $([ $WITH_ENV = 1 ] && echo evet || echo hayır)"
if [ "$YES" != 1 ]; then
  read -r -p "Servis durdurulup MEVCUT veriler bu yedekle değiştirilecek. Devam? (evet/hayır) " a
  [ "$a" = evet ] || die "iptal edildi"
fi

# ---- 2) Durdur + güvenlik kopyası ----------------------------------------------------
STAMP=$(date +%Y%m%d-%H%M%S)
SAFE="$DIR/pre-restore-$STAMP"
mkdir -p "$SAFE"
echo "▶ servis durduruluyor"
systemctl stop "$SVC" || true
for f in "$DB_PATH" "$DB_PATH-wal" "$DB_PATH-shm"; do [ -f "$f" ] && cp -a "$f" "$SAFE/"; done
cp -a "$ENVF" "$SAFE/dotenv" 2>/dev/null || true
echo "   mevcut durum kopyalandı: $SAFE"

# ---- 3) Geri yükle -----------------------------------------------------------------------
if [ "$WITH_ENV" = 1 ] && [ -f "$WORK/x/dotenv" ]; then
  install -o "$APP_USER" -g "$APP_USER" -m 600 "$WORK/x/dotenv" "$ENVF"
  echo "   .env geri yüklendi"
fi
if [ "$HAS_DB" = 1 ]; then
  install -d -o "$APP_USER" -g "$APP_USER" -m 700 "$(dirname "$DB_PATH")"
  rm -f "$DB_PATH-wal" "$DB_PATH-shm"
  install -o "$APP_USER" -g "$APP_USER" -m 600 "$WORK/x/store.db" "$DB_PATH"
  echo "   veritabanı geri yüklendi"
fi
if [ "$MEDIA" = 1 ] && [ -d "$WORK/x/media" ] && [ -n "$MEDIA_DIR" ]; then
  install -d -o "$APP_USER" -g "$APP_USER" -m 755 "$MEDIA_DIR"
  rsync -a "$WORK/x/media/" "$MEDIA_DIR/"
  chown -R "$APP_USER:$APP_USER" "$MEDIA_DIR"
  chmod -R a+rX "$MEDIA_DIR"
  echo "   medya geri yüklendi"
fi

# ---- 4) Başlat + sağlık ------------------------------------------------------------------
echo "▶ servis başlatılıyor"
systemctl start "$SVC"
for _ in $(seq 1 90); do
  if out=$(curl -fsS --noproxy "*" --max-time 5 http://127.0.0.1:8001/api/health 2>/dev/null); then
    echo "✔ geri yükleme tamam — $out"
    exit 0
  fi
  sleep 2
done
journalctl -u "$SVC" -n 40 --no-pager >&2 || true
die "servis sağlıklı açılmadı. Eski veriler: $SAFE"
