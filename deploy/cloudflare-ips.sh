#!/usr/bin/env bash
# Cloudflare IP aralıklarını günceller (haftalık systemd zamanlayıcısıyla da çalışır).
#   /usr/local/sbin/garajtek-cloudflare-ips
#
# Üretir:
#   /etc/nginx/conf.d/garajtek-cloudflare.conf
#     - set_real_ip_from <CF aralıkları> + real_ip_header CF-Connecting-IP
#       → nginx'te $remote_addr = gerçek ziyaretçi IP'si (yalnız CF'den gelen bağlantılarda)
#     - geo $garajtek_from_cf → ana site "yalnız Cloudflare" kilidi için (snippets/garajtek-cf-lock.conf)
#   CF_FIREWALL=1 ise (/etc/garajtek/deploy.conf) ufw'de 80/443'ü YALNIZ CF aralıklarına açar.
#   (Posta sunucusu / webmail aynı makinedeyse CF_FIREWALL=0 bırakın: mail.<alan> gri bulut olup
#    80/443'e herkesten erişilmelidir. Kilit bu durumda nginx seviyesinde uygulanır.)
set -euo pipefail

CONF=/etc/garajtek/deploy.conf
CF_FIREWALL=0
# shellcheck disable=SC1090
[ -f "$CONF" ] && . "$CONF"

OUT=/etc/nginx/conf.d/garajtek-cloudflare.conf

# Yedek liste (https://www.cloudflare.com/ips/ — indirme başarısız olursa kullanılır)
FALLBACK_V4="173.245.48.0/20 103.21.244.0/22 103.22.200.0/22 103.31.4.0/22 141.101.64.0/18
108.162.192.0/18 190.93.240.0/20 188.114.96.0/20 197.234.240.0/22 198.41.128.0/17
162.158.0.0/15 104.16.0.0/13 104.24.0.0/14 172.64.0.0/13 131.0.72.0/22"
FALLBACK_V6="2400:cb00::/32 2606:4700::/32 2803:f800::/32 2405:b500::/32 2405:8100::/32
2a06:98c0::/29 2c0f:f248::/32"

fetch() {
  curl -fsS --max-time 20 --retry 2 "$1" 2>/dev/null | tr -d '\r' | grep -E '^[0-9a-fA-F:.]+/[0-9]{1,3}$' || true
}

V4=$(fetch https://www.cloudflare.com/ips-v4)
V6=$(fetch https://www.cloudflare.com/ips-v6)
if [ "$(printf '%s\n' "$V4" | grep -c .)" -lt 5 ] || [ "$(printf '%s\n' "$V6" | grep -c .)" -lt 3 ]; then
  echo "!! Cloudflare IP listesi indirilemedi — yerleşik yedek liste kullanılıyor." >&2
  V4=$(printf '%s\n' $FALLBACK_V4)
  V6=$(printf '%s\n' $FALLBACK_V6)
fi
ALL=$(printf '%s\n%s\n' "$V4" "$V6" | grep . | sort -u)

TMP=$(mktemp)
{
  echo "# OTOMATİK ÜRETİLDİ — garajtek-cloudflare-ips ($(date -u +%F)). Elle düzenlemeyin."
  echo "# Gerçek ziyaretçi IP'si: yalnız Cloudflare'den gelen bağlantılarda CF-Connecting-IP'ye güvenilir."
  for ip in $ALL; do echo "set_real_ip_from $ip;"; done
  echo "real_ip_header CF-Connecting-IP;"
  echo
  echo "# Bağlantı gerçekten Cloudflare'den mi? (realip ÖNCESİ adres üzerinden)"
  echo 'geo $realip_remote_addr $garajtek_from_cf {'
  echo "    default 0;"
  echo "    127.0.0.1 1;"
  echo "    ::1 1;"
  for ip in $ALL; do echo "    $ip 1;"; done
  echo "}"
} > "$TMP"

changed=1
if [ -f "$OUT" ] && diff -q <(grep -v '^# OTOMATİK' "$OUT") <(grep -v '^# OTOMATİK' "$TMP") >/dev/null; then
  changed=0
fi

if [ "$changed" = 1 ]; then
  BAK=""
  [ -f "$OUT" ] && BAK=$(mktemp) && cp "$OUT" "$BAK"
  install -m 0644 "$TMP" "$OUT"
  if nginx -t >/dev/null 2>&1; then
    systemctl is-active --quiet nginx && systemctl reload nginx
    echo "nginx Cloudflare aralıkları güncellendi ($(echo "$ALL" | wc -l) aralık)."
  else
    echo "!! nginx -t başarısız; eski dosya geri yüklendi." >&2
    if [ -n "$BAK" ]; then cp "$BAK" "$OUT"; else rm -f "$OUT"; fi
  fi
  [ -n "$BAK" ] && rm -f "$BAK"
fi
rm -f "$TMP"

# ---- ufw (isteğe bağlı) -------------------------------------------------------
command -v ufw >/dev/null || exit 0
delete_cf_rules() {
  local n
  while n=$(ufw status numbered 2>/dev/null | grep -F '# garajtek-cloudflare' | head -n1 | sed -E 's/^\[ *([0-9]+)\].*/\1/') && [ -n "$n" ]; do
    ufw --force delete "$n" >/dev/null
  done
}
if [ "${CF_FIREWALL:-0}" = 1 ]; then
  delete_cf_rules
  for ip in $ALL; do
    ufw allow proto tcp from "$ip" to any port 80,443 comment garajtek-cloudflare >/dev/null
  done
  # Herkese açık 80/443 kurallarını kaldır (yalnız CF erişsin)
  for r in 80/tcp 443/tcp 'Nginx Full' 'Nginx HTTP' 'Nginx HTTPS' 80 443; do
    ufw --force delete allow "$r" >/dev/null 2>&1 || true
  done
  echo "ufw: 80/443 yalnız Cloudflare aralıklarına açık."
else
  # Varsayılan: 80/443 herkese açık (posta ACME/webmail için de gerekli); CF kilidi nginx'te.
  if ufw status 2>/dev/null | grep -q '^Status: active'; then
    ufw allow 80/tcp >/dev/null
    ufw allow 443/tcp >/dev/null
  fi
  if ufw status 2>/dev/null | grep -qF 'garajtek-cloudflare'; then
    delete_cf_rules
  fi
fi
