import { shippingQuote, matchShippingRule, promoFreeShipping } from './shippingRules';

test.each([[3999.99, false], [4000, true], [4000.01, true]])('boundary %s', (subtotal, free) => {
  expect(shippingQuote({ subtotal, threshold: 4000, fee: 99 }))
    .toEqual({ basis: subtotal, free, cost: free ? 0 : 99, fee: 99 });
});
test('campaign and points reductions count; charges never count', () => {
  const base = { subtotal: 6000, threshold: 4000, fee: 99 };
  expect(shippingQuote({ ...base, discounts: [600, 1080, 321] })).toEqual({ basis: 3999, free: false, cost: 99, fee: 99 });
  expect(shippingQuote({ ...base, discounts: [600, 1080, 320] }).free).toBe(true);
});
test('free-shipping coupon applies even when a threshold exists (bulgu #19)', () => {
  expect(shippingQuote({ subtotal: 500, threshold: 3000, fee: 100, freeShippingPromotion: true }).cost).toBe(0);
});
test('no threshold and tenant-configured amount remain supported', () => {
  expect(shippingQuote({ subtotal: 100, threshold: 100, fee: 15 }).free).toBe(true);
  expect(shippingQuote({ subtotal: 5000, threshold: null, fee: 15 }).free).toBe(false);
});
test('shipping rules set the fee; a free rule waives it (bulgu #0)', () => {
  const rules = [
    { min_cart: 0, shipping_cost: 49, free_shipping: false },
    { min_cart: 1000, max_cart: 2000, shipping_cost: 0, free_shipping: true },
  ];
  expect(matchShippingRule(rules, 296.76).shipping_cost).toBe(49);
  expect(shippingQuote({ subtotal: 296.76, threshold: null, fee: 99, rules })).toMatchObject({ cost: 49, fee: 49, free: false });
  expect(shippingQuote({ subtotal: 1500, threshold: null, fee: 99, rules })).toMatchObject({ cost: 0, free: true });
  // max_cart aşılırsa alttaki kurala düşer
  expect(shippingQuote({ subtotal: 2500, threshold: null, fee: 99, rules }).cost).toBe(49);
  expect(shippingQuote({ subtotal: 100, threshold: null, fee: 99, rules: [] }).cost).toBe(99);
});
test('threshold-setting auto campaign flag is not counted separately', () => {
  expect(promoFreeShipping([{ free_shipping: true, threshold_campaign: true }])).toBe(false);
  expect(promoFreeShipping([{ free_shipping: true }, { free_shipping: false }])).toBe(true);
  expect(promoFreeShipping(null)).toBe(false);
});
