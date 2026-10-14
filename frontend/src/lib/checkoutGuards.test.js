import {
  getIdemKey, clearIdemKeys, cartClearedElsewhere, resolvePaymentMethod, IDEM_TTL_MS,
} from "./checkoutGuards";

const memStorage = () => {
  const m = new Map();
  return {
    getItem: (k) => (m.has(k) ? m.get(k) : null),
    setItem: (k, v) => m.set(k, String(v)),
    removeItem: (k) => m.delete(k),
    key: (i) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
  };
};

test("aynı sepet iki sekmede aynı idempotency anahtarını alır (ortak depo)", () => {
  const shared = memStorage();   // localStorage sekmeler arasında ortak
  let n = 0;
  const make = () => `key-${++n}`;
  const tab1 = getIdemKey(shared, "store_idem_abc", make, 1000);
  const tab2 = getIdemKey(shared, "store_idem_abc", make, 2000);
  expect(tab2).toBe(tab1);
  // farklı sepet → farklı anahtar
  expect(getIdemKey(shared, "store_idem_xyz", make, 2000)).not.toBe(tab1);
});

test("süresi dolan ya da eski biçimli anahtar yenilenir", () => {
  const s = memStorage();
  let n = 0;
  const make = () => `key-${++n}`;
  const k1 = getIdemKey(s, "store_idem_a", make, 0);
  expect(getIdemKey(s, "store_idem_a", make, IDEM_TTL_MS + 1)).not.toBe(k1);
  s.setItem("store_idem_b", "duz-metin-uuid");
  expect(getIdemKey(s, "store_idem_b", make, 0)).not.toBe("duz-metin-uuid");
});

test("clearIdemKeys yalnız idem anahtarlarını siler", () => {
  const s = memStorage();
  s.setItem("store_idem_a", "x");
  s.setItem("store_idem_b", "y");
  s.setItem("cart", "[]");
  clearIdemKeys(s);
  expect(s.getItem("store_idem_a")).toBeNull();
  expect(s.getItem("store_idem_b")).toBeNull();
  expect(s.getItem("cart")).toBe("[]");
});

test("başka sekmede temizlenen sepet algılanır", () => {
  const s = memStorage();
  s.setItem("cart", "[]");
  expect(cartClearedElsewhere(s, 1)).toBe(true);
  expect(cartClearedElsewhere(s, 0)).toBe(false);
  s.setItem("cart", JSON.stringify([{ id: 1 }]));
  expect(cartClearedElsewhere(s, 1)).toBe(false);
  expect(cartClearedElsewhere(memStorage(), 1)).toBe(false); // kayıt yok → karar verme
});

test("hiç ödeme yöntemi yoksa seçim boşalır (kapıda ödeme bedeli eklenmesin)", () => {
  const none = { credit_card: false, bank_transfer: false, cash_on_delivery: false };
  expect(resolvePaymentMethod("cash_on_delivery", none)).toBe("");
  expect(resolvePaymentMethod("bank_transfer", { ...none, cash_on_delivery: true })).toBe("cash_on_delivery");
  expect(resolvePaymentMethod("bank_transfer", { ...none, bank_transfer: true, credit_card: true })).toBe("bank_transfer");
  expect(resolvePaymentMethod("", { ...none, credit_card: true })).toBe("credit_card");
});
