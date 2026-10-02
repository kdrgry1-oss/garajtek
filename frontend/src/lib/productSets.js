// Ürün Setleri — sepet kalemi yardımcıları (CartContext + set bileşenleri ortak kullanır).
//
// KURAL (sunucuyla aynı — backend/product_sets.py):
//  • "Seti Sepete Ekle" setteki HER ürünü ayrı kalem olarak ekler; kalemler setId / setSlot
//    (setteki orijinal ürünün id'si) / setName taşır ve sepette set başlığı altında gruplanır.
//  • Stokta olmayan bileşen "değiştirilmesi gerekiyor" kalemi olur (needsReplacement): satın
//    alınamaz, toplama girmez. "Bu ürünü değiştir" → ürünün EN ALT kategorisi açılır
//    (?degistir=<setId>:<ürünId>); oradan eklenen ürün bu yuvaya yazılır.
//  • Set indirimi yalnız setin tüm yuvaları doluyken (orijinal ya da aynı alt kategoriden yedek)
//    uygulanır; sunucu (kampanya motoru + sipariş) hesaplar, istemci yalnız gösterir.

const CTX_KEY = "set_replace_ctx";

export const setLineId = (setId, slot) => `set:${setId}:${slot}`;

function baseFromComponent(set, c, quantity) {
  const v = c.variant || null;
  const listBase = Number(c.price) || 0;
  const sp = Number(c.sale_price) || 0;
  const saleBase = sp > 0 && sp < listBase ? sp : listBase;
  const pd = Number(v?.price_diff) || 0;
  return {
    id: setLineId(set.id, c.product_id),
    productId: c.product_id,
    categoryId: c.category_id || null,
    slug: c.slug || c.product_id,
    variantId: c.variant_id || null,
    name: c.name,
    price: Math.round((saleBase + pd) * 100) / 100,
    listPrice: Math.round((listBase + pd) * 100) / 100,
    campaignPct: Number(c.campaign_discount_percent || 0),
    image: c.image || "",
    size: v?.size || null,
    color: v?.color || null,
    stockCode: v?.stock_code || c.stock_code || null,
    barcode: v?.barcode || c.barcode || null,
    stock: Number(c.stock) || 0,
    quantity: (Number(c.quantity) || 1) * quantity,
    setId: set.id,
    setSlot: c.product_id,
    setName: set.name,
    setSlug: set.slug || set.id,
    setQty: Number(c.quantity) || 1,
  };
}

/** /api/product-sets/{id} yanıtından sepet kalemleri üretir. */
export function buildSetLines(data, quantity = 1) {
  const set = data?.set;
  const comps = data?.components || [];
  if (!set || !comps.length) return [];
  const q = Math.max(1, Number(quantity) || 1);
  return comps.map((c) => {
    const line = baseFromComponent(set, c, q);
    if (c.in_stock && line.stock >= line.quantity) return line;
    if (c.in_stock) return { ...line, quantity: Math.max(1, Math.floor(line.stock / line.setQty) * line.setQty) || line.stock };
    return {
      ...line,
      needsReplacement: true,
      stock: 0,
      replaceCategory: c.leaf_category || null,
    };
  });
}

/** Mevcut sepete set kalemlerini ekler: aynı set yuvası varsa adet artar (stok tavanıyla). */
export function mergeSetLines(prev, built) {
  const next = [...prev];
  built.forEach((line) => {
    const i = next.findIndex((it) => it.id === line.id);
    if (i === -1) {
      next.push(line);
      return;
    }
    const cur = next[i];
    if (cur.needsReplacement || line.needsReplacement) return; // bekleyen yuva tekrar eklenmez
    const cap = cur.stock || Infinity;
    next[i] = { ...cur, quantity: Math.min(cur.quantity + line.quantity, cap) };
  });
  return next;
}

/** Bekleyen yuvayı seçilen ürünle doldurur (set bilgisi korunur). */
export function setLineFrom(pending, product, variant = null) {
  const listBase = Number(product.price) || 0;
  const sp = Number(product.sale_price) || 0;
  const saleBase = sp > 0 && sp < listBase ? sp : listBase;
  const pd = Number(variant?.price_diff || variant?.price_adjustment || 0);
  const stock = Number(variant ? variant.stock : product.stock) || 0;
  const qty = Math.max(1, Math.min(pending.setQty || pending.quantity || 1, stock || Infinity));
  const { needsReplacement, replaceCategory, ...rest } = pending; // eslint-disable-line no-unused-vars
  return {
    ...rest,
    productId: product.id,
    categoryId: product.category_id || null,
    slug: product.slug || product.id,
    variantId: variant?.id || null,
    name: product.name,
    price: Math.round((saleBase + pd) * 100) / 100,
    listPrice: Math.round((listBase + pd) * 100) / 100,
    campaignPct: Number(product.campaign_discount_percent || 0),
    image: product.images?.[0] || "",
    size: variant?.size || null,
    color: variant?.color || null,
    stockCode: variant?.stock_code || product.stock_code || null,
    barcode: variant?.barcode || product.barcode || null,
    stock,
    quantity: qty,
    replacedFrom: pending.name,
  };
}

export function productInCategory(product, categoryId) {
  if (!categoryId) return true;
  const ids = [...(product?.category_ids || []), product?.category_id].filter(Boolean).map(String);
  // Kart verisinde kategori yoksa (eski önbellek) engelleme — sunucu yine doğrular.
  if (!ids.length) return true;
  return ids.includes(String(categoryId));
}

export function readReplaceCtx() {
  try {
    const raw = sessionStorage.getItem(CTX_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function writeReplaceCtx(ctx) {
  try { sessionStorage.setItem(CTX_KEY, JSON.stringify(ctx)); } catch { /* yoksay */ }
  try { window.dispatchEvent(new Event("set-replace-ctx")); } catch { /* yoksay */ }
}

export function clearReplaceCtx() {
  try { sessionStorage.removeItem(CTX_KEY); } catch { /* yoksay */ }
  try { window.dispatchEvent(new Event("set-replace-ctx")); } catch { /* yoksay */ }
}

/** "Bu ürünü değiştir" hedefi: bileşenin en alt kategorisi + bağlam parametresi. */
export function replaceHref(line) {
  const slug = line?.replaceCategory?.slug;
  const q = `degistir=${encodeURIComponent(line.setId ? `${line.setId}:${line.setSlot}` : `urun:${line.productId}`)}`;
  return slug ? `/${slug}?${q}` : `/arama?q=${encodeURIComponent(line?.name || "")}&${q}`;
}

/** Kampanya motoru / sipariş yükü için set alanları. */
export const setPayload = (it) => (it && it.setId ? { set_id: it.setId, set_slot: it.setSlot } : {});

/** ?degistir= değerine karşılık gelen bekleyen kalem (set yuvası ya da tükenen tekil ürün). */
export function findPendingByParam(pendingItems, raw) {
  if (!raw) return null;
  const [a, b] = String(raw).split(":");
  return (pendingItems || []).find((p) => (a === "urun"
    ? !p.setId && String(p.productId) === b
    : String(p.setId) === a && String(p.setSlot) === b)) || null;
}
