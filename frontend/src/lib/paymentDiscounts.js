// Ödeme yöntemine bağlı indirimler — sunucu ile AYNI yorum (gösterilen = çekilen).

// Havale/öğrenci indirim yüzdesi: ayar sayfası ve sunucu (settings.effective_pct_setting) ile aynı.
// Yok / boş / sayı değil → varsayılan %5; aksi halde 0–90 (0 = kapalı).
export function effectivePct(value, dflt = 5) {
  if (value === null || value === undefined || typeof value === "boolean") return dflt;
  if (typeof value === "string" && !value.trim()) return dflt;
  const n = Number(typeof value === "string" ? value.replace(",", ".") : value);
  if (!Number.isFinite(n)) return dflt;
  return Math.min(90, Math.max(0, n));
}

// Ödeme Tipi İndirimi (Panel › Kargo & Ödeme Kampanyaları) — sunucu
// catalog_extras.payment_type_discount_amount ile aynı: taban = ara toplam − kupon/kampanya
// indirimi; taban min_cart altındaysa 0; yüzde kuruşta yarım-yukarı; sabit tutar tabanı geçmez.
export function paymentTypeDiscount(rule, base) {
  if (!rule) return 0;
  const cents = Math.max(0, Math.round((Number(base) || 0) * 100));
  if (cents <= 0 || cents < Math.round((Number(rule.min_cart) || 0) * 100)) return 0;
  const pct = Number(rule.percent) || 0;
  if (rule.type === "percent" && pct > 0) {
    return Math.min(Math.round((cents * pct) / 100), cents) / 100;
  }
  return Math.min(Math.round((Number(rule.amount) || 0) * 100), cents) / 100;
}
