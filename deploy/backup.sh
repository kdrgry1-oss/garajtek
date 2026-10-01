#!/usr/bin/env bash
# garajtek — gece yedeği (garajtek-backup.timer, her gün 03:30). Elle: garajtek-backup
#
# İçerik (tek dosya: /var/backups/garajtek/garajtek-YYYYmmdd-HHMMSS.tar.gz):
#   store.db  — SQLite ÇEVRİMİÇİ yedeği (servis durmadan; `python -m localdb.backup`)
#   dotenv    — backend/.env (SECRETS_MASTER_KEY olmadan panel şifreleri çözülemez!)
#   media/    — yüklenen görseller/videolar (MEDIA_DIR)
# Yerelde son BACKUP_KEEP (varsayılan 7) yedek tutulur. BACKUP_R2_BUCKET tanımlıysa sunucu
# DIŞINA (Cloudflare R2, özel bucket) da yüklenir; BACKUP_PASSPHRASE varsa AES-256 ile şifrelenir.
set -euo pipefail
umask 077

APP=/opt/garajtek
ENVF=$APP/backend/.env
DIR=/var/backups/garajtek
APP_USER=garajtek

envget() {  # .env'den tek değer oku (kaynak olarak çalıştırmadan)
  grep -E "^$1=" "$ENVF" 2>/dev/null | tail -n1 | cut -d= -f2- | sed -E 's/^"(.*)"$/\1/; s/^'"'"'(.*)'"'"'$/\1/' || true
}

[ "$(id -u)" = 0 ] || { echo "root olarak çalıştırın" >&2; exit 1; }
[ -f "$ENVF" ] || { echo "$ENVF yok" >&2; exit 1; }

DB_PATH=$(envget DB_PATH);   DB_PATH=${DB_PATH:-$APP/backend/data/store.db}
MEDIA_DIR=$(envget MEDIA_DIR)
KEEP=$(envget BACKUP_KEEP);  KEEP=${KEEP:-7}
STAMP=$(date +%Y%m%d-%H%M%S)
NAME="garajtek-$STAMP.tar.gz"
mkdir -p "$DIR"; chmod 700 "$DIR"

# Çalışma dizini uygulama kullanıcısına ait olmalı: yedek CLI'ı garajtek olarak çalışır
# (root olarak açmak DB'nin -wal/-shm dosyalarını root'a ait yaratıp uygulamayı kilitleyebilir).
WORK=$(mktemp -d /var/tmp/garajtek-backup.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
chown "$APP_USER:$APP_USER" "$WORK"

# ---- 1) SQLite çevrimiçi yedek -----------------------------------------------------
if [ -f "$DB_PATH" ]; then
  if ( cd "$APP/backend" && runuser -u "$APP_USER" -- env HOME="$APP" DB_PATH="$DB_PATH" \
        "$APP/venv/bin/python" -c 'import localdb.backup' ) >/dev/null 2>&1; then
    ( cd "$APP/backend" && runuser -u "$APP_USER" -- env HOME="$APP" DB_PATH="$DB_PATH" \
        "$APP/venv/bin/python" -m localdb.backup "$WORK/store.db" )
  else
    # Yedek: Python'un sqlite3 çevrimiçi backup API'si (WAL ile güvenli, servis durmaz)
    runuser -u "$APP_USER" -- python3 - "$DB_PATH" "$WORK/store.db" <<'PY'
import sqlite3, sys
src = sqlite3.connect(sys.argv[1], timeout=60)
dst = sqlite3.connect(sys.argv[2])
with dst:
    src.backup(dst)
dst.close(); src.close()
PY
  fi
  chk=$(python3 -c 'import sqlite3,sys; print(sqlite3.connect(sys.argv[1]).execute("PRAGMA quick_check").fetchone()[0])' "$WORK/store.db")
  [ "$chk" = ok ] || { echo "!! yedek veritabanı bütünlük denetimi başarısız: $chk" >&2; exit 1; }
else
  echo "uyarı: veritabanı dosyası yok ($DB_PATH) — yalnız .env ve medya yedekleniyor" >&2
fi

# ---- 2) Arşiv ---------------------------------------------------------------------
cp "$ENVF" "$WORK/dotenv"
members=(dotenv)
[ -f "$WORK/store.db" ] && members+=(store.db)
TAR_ARGS=(-C "$WORK" "${members[@]}")
if [ -n "$MEDIA_DIR" ] && [ -d "$MEDIA_DIR" ]; then
  TAR_ARGS+=(-C "$MEDIA_DIR" --transform 's,^\.,media,' .)
fi
tar -czf "$DIR/.$NAME.part" "${TAR_ARGS[@]}"
mv "$DIR/.$NAME.part" "$DIR/$NAME"
echo "yedek: $DIR/$NAME ($(du -h "$DIR/$NAME" | cut -f1))"

# ---- 3) Sunucu dışı kopya (Cloudflare R2, isteğe bağlı) -----------------------------
BUCKET=$(envget BACKUP_R2_BUCKET)
if [ -n "$BUCKET" ]; then
  UP="$DIR/$NAME"
  PASS=$(envget BACKUP_PASSPHRASE)
  if [ -n "$PASS" ]; then
    UP="$WORK/$NAME.enc"
    BACKUP_PASSPHRASE="$PASS" openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
      -in "$DIR/$NAME" -out "$UP" -pass env:BACKUP_PASSPHRASE
  fi
  EP=$(envget BACKUP_R2_ENDPOINT);          EP=${EP:-$(envget R2_ENDPOINT)}
  AK=$(envget BACKUP_R2_ACCESS_KEY_ID);     AK=${AK:-$(envget R2_ACCESS_KEY_ID)}
  SK=$(envget BACKUP_R2_SECRET_ACCESS_KEY); SK=${SK:-$(envget R2_SECRET_ACCESS_KEY)}
  if [ -z "$EP" ] || [ -z "$AK" ] || [ -z "$SK" ]; then
    echo "!! BACKUP_R2_BUCKET var ama uç nokta/anahtar eksik — R2'ye yüklenmedi" >&2
    exit 1
  fi
  if R2_EP="$EP" R2_AK="$AK" R2_SK="$SK" R2_BUCKET_NAME="$BUCKET" \
     "$APP/venv/bin/python" - "$UP" <<'PY'
import os, sys, pathlib, boto3
from botocore.config import Config
p = pathlib.Path(sys.argv[1])
s3 = boto3.client("s3", endpoint_url=os.environ["R2_EP"], aws_access_key_id=os.environ["R2_AK"],
                  aws_secret_access_key=os.environ["R2_SK"], region_name="auto",
                  config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}))
s3.upload_file(str(p), os.environ["R2_BUCKET_NAME"], f"backups/{p.name}")
print(f"R2'ye yüklendi: {os.environ['R2_BUCKET_NAME']}/backups/{p.name}")
PY
  then :; else
    echo "!! R2 yüklemesi başarısız (yerel kopya duruyor)" >&2
    RC=1
  fi
fi

# ---- 4) Yerel rotasyon ------------------------------------------------------------
# shellcheck disable=SC2012
ls -1t "$DIR"/garajtek-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
exit "${RC:-0}"
