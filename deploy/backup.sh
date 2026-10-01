#!/usr/bin/env bash
# Günlük yedek: mongodump → yerelde 2 kopya + (R2 anahtarları varsa) buluta yükle.
# Veritabanı uygulamayla AYNI sunucuda durduğu için yedeğin sunucu DIŞINA çıkması şarttır:
# disk/sunucu giderse yedek de gitmesin.
set -euo pipefail
APP_SLUG="${APP_SLUG:-store}"
APP=/opt/$APP_SLUG
DIR=/var/backups/$APP_SLUG
ENVF="$APP/backend/.env"
mkdir -p "$DIR"

DB=$(grep -E '^DB_NAME=' "$ENVF" 2>/dev/null | cut -d= -f2- | tr -d '"' || true)
STAMP=$(date +%F-%H%M)
FILE="$DIR/${DB:-$APP_SLUG}-$STAMP.gz"

mongodump --quiet ${DB:+--db "$DB"} --archive="$FILE" --gzip
echo "yedek: $FILE ($(du -h "$FILE" | cut -f1))"

# Buluta (Cloudflare R2) yükle — anahtarlar .env'de varsa. boto3 zaten sanal ortamda kurulu.
if grep -q '^R2_ACCESS_KEY_ID=.\+' "$ENVF" 2>/dev/null; then
  "$APP/venv/bin/python" - "$FILE" "$ENVF" <<'PY' || echo "!! R2 yüklemesi başarısız (yerel kopya duruyor)"
import os, sys, pathlib
env = {}
for line in pathlib.Path(sys.argv[2]).read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip().strip('"')
import boto3
s3 = boto3.client("s3",
    endpoint_url=f"https://{env['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=env["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=env["R2_SECRET_ACCESS_KEY"], region_name="auto")
p = pathlib.Path(sys.argv[1])
s3.upload_file(str(p), env["R2_BUCKET"], f"backups/{p.name}")
print(f"R2'ye yüklendi: backups/{p.name}")
PY
fi

# Yerelde yalnız son 2 yedek kalsın (5 GB diskte yer tutmasın)
ls -1t "$DIR"/*.gz 2>/dev/null | tail -n +3 | xargs -r rm -f
