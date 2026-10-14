import { withActiveVariants } from "./activeVariants";

test("pasif varyant atılır, üst stok aktiflerden hesaplanır", () => {
  const p = { id: 9371, stock: 8, variants: [
    { id: 23, size: "S1", stock: 5, is_active: false },
    { id: 24, size: "S2", stock: 3 },
  ] };
  const out = withActiveVariants(p);
  expect(out.variants.map((v) => v.id)).toEqual([24]);
  expect(out.stock).toBe(3);
  expect(p.variants).toHaveLength(2); // girdi değişmez
});

test("tüm varyantlar pasifse ürün tükendi görünür", () => {
  const out = withActiveVariants({ id: 1, stock: 5, variants: [{ id: 2, stock: 5, is_active: false }] });
  expect(out.variants).toEqual([]);
  expect(out.stock).toBe(0);
});

test("pasif yoksa nesne aynen döner", () => {
  const p = { id: 1, stock: 2, variants: [{ id: 2, stock: 2, is_active: true }, { id: 3, stock: 0 }] };
  expect(withActiveVariants(p)).toBe(p);
  expect(withActiveVariants(null)).toBe(null);
});
