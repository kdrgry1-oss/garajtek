import { cardPaymentAvailable } from "./paymentAvailability";

jest.mock("axios", () => ({ get: jest.fn() }));

test("iyzico yapılandırılmamışsa kartla/taksitli ödeme yok", () => {
  expect(cardPaymentAvailable({ payment_methods: { credit_card: true } }, { configured: false })).toBe(false);
});

test("admin kartı kapattıysa yok", () => {
  expect(cardPaymentAvailable({ payment_methods: { credit_card: false } }, { configured: true })).toBe(false);
});

test("ikisi de uygunsa var; sinyal bilinmiyorsa karar yok", () => {
  expect(cardPaymentAvailable({ payment_methods: { credit_card: true } }, { configured: true })).toBe(true);
  expect(cardPaymentAvailable({}, {})).toBe(true); // varsayılanlar: açık
  expect(cardPaymentAvailable(undefined, { configured: true })).toBeNull();
});
