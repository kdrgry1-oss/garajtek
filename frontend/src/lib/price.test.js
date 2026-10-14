import { cartLineView, cartSummary, promoSummaryRows } from "./price";

// #24 — set + otomatik %10 kampanya: sepet özeti "Set İndirimi" ve kampanya adını AYRI satırda,
// /coupons/evaluate tutarlarıyla göstermeli (eskiden tek satır: "Set İndirimi … -677,22").
const applied = [
  { type: "set", title: "Set İndirimi — SYNC-Set Ikili (%20)", discount: 483.73 },
  { type: "percent", title: "SYNC-Yuzde10", discount: 193.49 },
];
const setLines = [
  { id: "set:S:A", productId: "A", price: 1956.63, listPrice: 1956.63, quantity: 1, setId: "S", campaignPct: 10 },
  { id: "set:S:B", productId: "B", price: 462, listPrice: 462, quantity: 1, setId: "S", campaignPct: 10 },
];

test("set kaleminde otomatik kampanya yüzdesi satır fiyatına uygulanmaz", () => {
  expect(cartLineView(setLines[0]).unit).toBe(1956.63);
  expect(cartLineView(setLines[0]).campaignPct).toBe(0);
  expect(cartLineView({ price: 100, quantity: 1, campaignPct: 10 }).unit).toBe(90);
});

test("set + yüzde kampanya ayrı satırlar, toplam evaluate ile aynı", () => {
  const { extraDisc, grand } = cartSummary(setLines, 677.22);
  expect(extraDisc).toBe(677.22);
  expect(grand).toBe(1741.41);
  expect(promoSummaryRows(applied, 677.22, extraDisc)).toEqual([
    { title: "Set İndirimi — SYNC-Set Ikili (%20)", amount: 483.73 },
    { title: "SYNC-Yuzde10", amount: 193.49 },
  ]);
});

test("kalemde gösterilen yüzde kampanya özet satırından mahsup edilir", () => {
  const items = [{ price: 1000, listPrice: 1000, quantity: 1, campaignPct: 10 }];
  const promos = [{ type: "percent", title: "Yüzde10", discount: 100 }, { type: "nth_discount", title: "3 Al 2 Öde", discount: 50 }];
  const { extraDisc } = cartSummary(items, 150);
  expect(promoSummaryRows(promos, 150, extraDisc)).toEqual([{ title: "3 Al 2 Öde", amount: 50 }]);
});

test("evaluate ayrıntısı yoksa genel kampanya satırı", () => {
  expect(promoSummaryRows([], 40, 40)).toEqual([{ title: "Kampanya İndirimi", amount: 40 }]);
});
