// Match backend/shipping_rules.py. Compare integer kuruş, including the boundary.

// Panel › Kargo Kuralları: sepet ARA TOPLAMINA uyan, en yüksek min_cart'lı aktif kural (yoksa null).
// Sunucu (shipping_rules.match_shipping_rule) aynı kuralı uygular → sepet = kasa = sipariş.
export function matchShippingRule(rules, cartTotal) {
  const total = Number(cartTotal) || 0;
  const active = (Array.isArray(rules) ? rules : []).filter((r) => r && r.is_active !== false);
  const sorted = [...active].sort((a, b) => (Number(b.min_cart) || 0) - (Number(a.min_cart) || 0));
  return sorted.find((r) => {
    const mx = Number(r.max_cart) || 0;
    return total >= (Number(r.min_cart) || 0) && (!mx || total <= mx);
  }) || null;
}

// Kampanya motoru sonucunda EŞİKTEN BAĞIMSIZ ücretsiz kargo veren promosyon var mı?
// Eşiği belirleyen otomatik kampanya (threshold_campaign) sayılmaz — onun minimumu eşikle uygulanır.
export function promoFreeShipping(applied) {
  return (applied || []).some((p) => p && p.free_shipping && !p.threshold_campaign);
}

// Kargo kararı (sunucu shipping_quote ile birebir):
// - discounts: kupon/kampanya indirimi ve puan. Ödeme yöntemi indirimi (havale vb.) EŞİK TABANINA
//   GİRMEZ — aksi halde "indirimli" havale ücretsiz kargoyu kaybettirip sepetten pahalıya geliyordu.
// - freeShippingPromotion: 'Kargo bedava' kuponu / koşullu kampanya → eşikten bağımsız ücretsiz.
// - rules: Kargo Kuralları; eşleşen kural ücreti belirler, 'Kargo bedava' kuralı ücretsiz yapar.
export function shippingQuote({ subtotal, discounts = [], threshold, fee, freeShippingPromotion = false, rules = null }) {
  const cents = (value) => Math.round((Number(value || 0) + Number.EPSILON) * 100);
  const basis = Math.max(0, cents(subtotal) - discounts.reduce((sum, d) => sum + cents(d), 0));
  const rule = rules ? matchShippingRule(rules, subtotal) : null;
  const effFee = rule && !rule.free_shipping ? Number(rule.shipping_cost) || 0 : fee;
  const free = Boolean(freeShippingPromotion)
    || Boolean(rule && rule.free_shipping)
    || (threshold != null && basis >= cents(threshold));
  return { basis: basis / 100, free, cost: free ? 0 : cents(effFee) / 100, fee: cents(effFee) / 100 };
}
