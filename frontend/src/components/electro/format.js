// Electro vitrin yardımcıları — fiyat biçimi, ürün linki, kategori adı.
import { priceView } from "../../lib/price";

/** 1234.5 → "1.234,50 ₺" (Electro'daki "$685,00" görünümünün TR karşılığı). */
export function fmtPrice(n) {
  const v = Number(n) || 0;
  return `${v.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₺`;
}

export function productHref(p) {
  return `/${(p && (p.slug || p.id)) || ""}`;
}

export function categoryHref(c) {
  return `/${(c && (c.slug || c.id)) || ""}`;
}

/** Ürün kartı fiyat görünümü (lib/price tek kaynağı). */
export function priceOf(p) {
  return priceView(p);
}

/** Varyant/ürün stok toplamı → tükendi mi. */
export function isSoldOut(p) {
  const vs = (p && p.variants) || [];
  if (vs.length) return vs.reduce((s, v) => s + (Number(v.stock) || 0), 0) <= 0;
  return (Number(p && p.stock) || 0) <= 0;
}

/** Ürünün bedeni/seçimi gereken varyantı var mı (kartta doğrudan sepete eklenemez). */
export function needsVariantChoice(p) {
  const vs = (p && p.variants) || [];
  return vs.filter((v) => v && v.id).length > 1;
}
