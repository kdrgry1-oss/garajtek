import { orderExtraFeeRows, orderHasEmail } from "./orderSummary";

test("kapıda ödeme bedeli ve hediye paketi özet satırı olarak çıkar; satırlar toplamı tutar", () => {
  // W10010: 23386 + 99 + 130 + 25 = 23640
  const order = { subtotal: 23386, shipping_cost: 99, gift_wrap: true, gift_wrap_price: 130, cod_fee: 25, total: 23640 };
  const rows = orderExtraFeeRows(order);
  expect(rows.map((r) => r.key)).toEqual(["gift_wrap", "cod_fee"]);
  const sum = order.subtotal + order.shipping_cost + rows.reduce((s, r) => s + r.amount, 0);
  expect(sum).toBe(order.total);
});

test("ücret yoksa / sıfırsa ek satır yok", () => {
  expect(orderExtraFeeRows({ cod_fee: 0, gift_wrap_price: 0 })).toEqual([]);
  expect(orderExtraFeeRows({})).toEqual([]);
  expect(orderExtraFeeRows(null)).toEqual([]);
  expect(orderExtraFeeRows({ cod_fee: "10" })).toEqual([{ key: "cod_fee", label: "Kapıda Ödeme Hizmet Bedeli", amount: 10 }]);
});

test("e-posta yoksa 'e-postanıza gönderildi' denmez", () => {
  expect(orderHasEmail({ shipping_address: { email: "" } })).toBe(false);
  expect(orderHasEmail({})).toBe(false);
  expect(orderHasEmail({ shipping_address: { email: "ab***@example.com" } })).toBe(true);
  expect(orderHasEmail({ shipping_address: {}, email: "ab***@example.com" })).toBe(true);
});
