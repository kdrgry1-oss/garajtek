import { cartAddPlan } from "./cartStock";

const product = { id: 3866, stock: 50 };
const v15 = { id: 15, size: "10x11 mm", stock: 6 };

test("sepette stok kadar varsa eklenecek adet 0 (sahte 'sepete eklendi' yok)", () => {
  const items = [{ productId: 3866, variantId: 15, quantity: 6 }];
  expect(cartAddPlan(items, product, v15, 2)).toEqual({ stock: 6, inCart: 6, add: 0 });
});

test("kısmen sığıyorsa yalnız kalan stok kadar eklenir", () => {
  const items = [{ productId: 3866, variantId: 15, quantity: 4 }];
  expect(cartAddPlan(items, product, v15, 5)).toEqual({ stock: 6, inCart: 4, add: 2 });
});

test("başka varyant / set kalemi sayılmaz; varyantsız ürün ürün stoğuna bakar", () => {
  const items = [
    { productId: 3866, variantId: 16, quantity: 6 },
    { productId: 3866, variantId: 15, quantity: 3, setId: "s1" },
  ];
  expect(cartAddPlan(items, product, v15, 2).add).toBe(2);
  const plain = { id: 7, stock: 3 };
  expect(cartAddPlan([{ productId: 7, variantId: null, quantity: 3 }], plain, null, 1).add).toBe(0);
  expect(cartAddPlan([], { id: 8 }, null, 4).add).toBe(4); // stok bilinmiyor → sınırsız
});
