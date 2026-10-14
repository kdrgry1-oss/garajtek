/**
 * Sepete ekleme stok planı (saf fonksiyon).
 * CartContext.addToLines adedi stokla SESSİZCE sınırlar; ürün sayfası yalnız yeni seçilen
 * adedi stokla karşılaştırınca sepet zaten doluyken "sepete eklendi" diyordu. Burada
 * sepetteki mevcut adet de hesaba katılır → kaç adet gerçekten eklenebileceği bilinir.
 *
 * Döner: { stock, inCart, add } — add = gerçekten eklenecek adet (0 → stok sınırında).
 */
export function cartAddPlan(items, product, variant, quantity) {
  const qty = Math.max(0, Number(quantity) || 0);
  const rawStock = Number(variant ? variant.stock : product?.stock);
  const stock = Number.isFinite(rawStock) ? Math.max(0, rawStock) : Infinity;
  const inCart = (items || [])
    .filter((it) => !it.setId && !it.needsReplacement && (
      variant ? it.variantId === variant.id : it.productId === product?.id && !it.variantId
    ))
    .reduce((s, it) => s + (Number(it.quantity) || 0), 0);
  const add = Math.max(0, Math.min(qty, stock - inCart));
  return { stock, inCart, add };
}
