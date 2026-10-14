import { effectivePct, paymentTypeDiscount } from "./paymentDiscounts";

test("boş/geçersiz havale yüzdesi sunucu ile aynı: varsayılan %5 (bulgu #1)", () => {
  expect(effectivePct("")).toBe(5);
  expect(effectivePct(null)).toBe(5);
  expect(effectivePct(undefined)).toBe(5);
  expect(effectivePct("abc")).toBe(5);
  expect(effectivePct(0)).toBe(0);
  expect(effectivePct("7,5")).toBe(7.5);
  expect(effectivePct(120)).toBe(90);
});

test("ödeme tipi indirimi: yüzde, sabit, min sepet (bulgu #2)", () => {
  const pct = { type: "percent", percent: 10, amount: 0, min_cart: 0 };
  expect(paymentTypeDiscount(pct, 296.76)).toBe(29.68);
  expect(paymentTypeDiscount(pct, 678.3)).toBe(67.83);
  expect(paymentTypeDiscount({ type: "percent", percent: 5 }, 678.3)).toBe(33.92);
  expect(paymentTypeDiscount({ type: "fixed", amount: 25, percent: 0 }, 296.76)).toBe(25);
  expect(paymentTypeDiscount({ type: "fixed", amount: 500 }, 296.76)).toBe(296.76);
  expect(paymentTypeDiscount({ ...pct, min_cart: 500 }, 296.76)).toBe(0);
  expect(paymentTypeDiscount(null, 100)).toBe(0);
});
