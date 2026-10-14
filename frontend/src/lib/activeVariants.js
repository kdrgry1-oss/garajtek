/**
 * Vitrin ürün sayfası için PASİF varyantları ayıklar (saf fonksiyon).
 * Panelde "Pasif" yapılan varyant (variants[].is_active === false) ürün sayfasında seçenek
 * olarak çıkıyor, varsayılan seçili gelip sepete eklenebiliyordu. Burada pasifler atılır ve
 * varyantlı ürünün üst stoğu YALNIZ aktif varyantlardan yeniden hesaplanır (üst stok
 * Σtüm-varyant olduğundan, tek aktif varyant tükenince ürün "stokta" görünmesin).
 * Tüm varyantlar pasifse ürün varyantsız + stok 0 (Tükendi) döner.
 */
export function withActiveVariants(product) {
  if (!product || !Array.isArray(product.variants) || !product.variants.length) return product;
  const active = product.variants.filter((v) => v && v.is_active !== false);
  if (active.length === product.variants.length) return product;
  const stock = active.reduce((s, v) => s + Math.max(0, Number(v.stock) || 0), 0);
  return { ...product, variants: active, stock };
}
