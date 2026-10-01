// Yatay header menüsü sığdırma (Header.jsx HorizontalNav) — saf fonksiyon, test edilebilir.

/** Sığdırma: öncelik sırası = önce SALE stilli sekme (her zaman öne alınır), sonra menü sırası.
 * widths[i]: i. sekmenin genişliği; budget: kullanılabilir genişlik; moreW: "Daha Fazla" genişliği.
 * Dönüş: görünür sekme indeksleri (Set). Genişlik bilinmiyorsa (0) yalnız max uygulanır. */
export function fitTabs(tabs, widths, budget, moreW, max) {
  const order = tabs.map((t, i) => i);
  const saleIdx = tabs.findIndex((t) => t && t.style === "sale");
  if (saleIdx > 0) { order.splice(saleIdx, 1); order.unshift(saleIdx); }
  const chosen = new Set();
  let used = 0;
  for (const i of order) {
    if (chosen.size >= max) break;
    const w = widths[i] || 0;
    const needMore = chosen.size + 1 < tabs.length;
    if (budget > 0 && used + w + (needMore ? moreW : 0) > budget) break;
    chosen.add(i);
    used += w;
  }
  return chosen;
}
