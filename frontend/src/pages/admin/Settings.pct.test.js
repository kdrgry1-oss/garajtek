import { normalizePctSettings, normalizePaymentMethods, DEFAULT_VAT_RATE } from "./Settings";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn() }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

describe("normalizePctSettings", () => {
  it("boş havale/öğrenci indirimini varsayılan 5'e çevirir ('' kaydedilmez)", () => {
    const out = normalizePctSettings({ bank_transfer_discount_pct: "", edu_discount_pct: null, site_name: "x" });
    expect(out.bank_transfer_discount_pct).toBe(5);
    expect(out.edu_discount_pct).toBe(5);
    expect(out.site_name).toBe("x");
  });

  it("geçerli değerleri korur, aralığı 0–90'a sıkıştırır", () => {
    expect(normalizePctSettings({ bank_transfer_discount_pct: 0 }).bank_transfer_discount_pct).toBe(0);
    expect(normalizePctSettings({ bank_transfer_discount_pct: 7.5 }).bank_transfer_discount_pct).toBe(7.5);
    expect(normalizePctSettings({ bank_transfer_discount_pct: 120 }).bank_transfer_discount_pct).toBe(90);
  });

  it("alan yoksa eklemez", () => {
    expect(normalizePctSettings({ a: 1 })).toEqual({ a: 1 });
  });

  it("varsayılan KDV %20", () => {
    expect(DEFAULT_VAT_RATE).toBe(20);
  });
});

describe("normalizePaymentMethods (bulgu #3: panel = vitrin)", () => {
  it("eksik kart/havale anahtarı vitrindeki gibi AÇIK, kapıda ödeme yalnız true ise açık", () => {
    expect(normalizePaymentMethods(undefined)).toEqual({ credit_card: true, bank_transfer: true, cash_on_delivery: false });
    expect(normalizePaymentMethods({ cash_on_delivery: true }))
      .toEqual({ credit_card: true, bank_transfer: true, cash_on_delivery: true });
  });
  it("açıkça kapatılanı korur", () => {
    expect(normalizePaymentMethods({ credit_card: false, bank_transfer: false, cash_on_delivery: "x" }))
      .toEqual({ credit_card: false, bank_transfer: false, cash_on_delivery: false });
  });
});
