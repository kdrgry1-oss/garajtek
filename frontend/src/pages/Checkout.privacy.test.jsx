import { act } from "react";
import { createRoot } from "react-dom/client";
import Checkout from "./Checkout";
import axios from "axios";
import { trackAddPaymentInfo, trackPurchase } from "../utils/pixelEvents";
import { formatTRY } from "../components/checkout/utils";

let mockUser = null;
let mockTotal = 100;
const mockNavigate = jest.fn();
const mockSearch = new URLSearchParams();
const mockClearCart = jest.fn();
const mockCartItems = [{ id: "test", productId: "test", name: "Test Ürün", quantity: 1, price: 100 }];
jest.mock("react-router-dom", () => {
  const React = require("react");
  return {
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearch],
    Link: ({ to, children, ...p }) => React.createElement("a", { href: to, ...p }, children),
  };
}, { virtual: true });
jest.mock("../context/AuthContext", () => ({ useAuth: () => ({ user: mockUser }) }));
jest.mock("../context/CartContext", () => ({ useCart: () => ({ items: mockCartItems, total: mockTotal, clearCart: mockClearCart }) }));
jest.mock("../lib/shipping", () => ({ useShipping: () => ({ shippingFee: 99, freeShippingThreshold: 4000 }) }));
jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);
// İl/İlçe combobox'ı yerine tek tıkla İstanbul/Kadıköy seçen basit bir buton.
jest.mock("../components/ProvinceDistrictSelect", () => {
  const React = require("react");
  return ({ onChange, testIdPrefix }) => React.createElement("button", {
    type: "button", "data-testid": `${testIdPrefix}-pds-mock`,
    onClick: () => onChange({ city: "İstanbul", district: "Kadıköy" }),
  }, "il-ilce");
});
jest.mock("../utils/pixelEvents", () => ({ trackInitiateCheckout: jest.fn(), trackPurchase: jest.fn(), trackAddPaymentInfo: jest.fn(), trackAddShippingInfo: jest.fn() }));
jest.mock("../lib/dataLayer", () => ({ collectClickIds: () => ({}) }));
jest.mock("../lib/attribution", () => ({ getSessionId: () => "test-session" }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn(), info: jest.fn(), warning: jest.fn() } }));
jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn() }));

const $ = (c, id) => c.querySelector(`[data-testid="${id}"]`);
function typeInto(el, value) {
  const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
  Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
  el.dispatchEvent(new Event("input", { bubbles: true }));
}
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

describe("checkout address isolation", () => {
  let root, container;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; });
  beforeEach(() => {
    mockUser = null;
    mockTotal = 100;
    Object.assign(mockCartItems[0], {price: 100, listPrice: 100, campaignPct: 0});
    localStorage.clear();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    axios.get.mockResolvedValue({ data: {} });
    axios.post.mockResolvedValue({ data: { applied: [], eligible: [], discount: 0 } });
  });
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); jest.clearAllMocks(); });

  test("guest checkout deletes the legacy address and never displays it", async () => {
    localStorage.setItem("store_last_address", JSON.stringify({ first_name: "PRIVATE_PREVIOUS_CUSTOMER", address: "PRIVATE_ADDRESS" }));
    await act(async () => root.render(<Checkout />));
    expect(localStorage.getItem("store_last_address")).toBeNull();
    expect(container.textContent).not.toContain("PRIVATE_PREVIOUS_CUSTOMER");
    expect(container.textContent).not.toContain("PRIVATE_ADDRESS");
    container.querySelectorAll("input").forEach((i) => {
      expect(i.value).not.toContain("PRIVATE");
    });
  });

  test.each([[4210.52, false], [4210.53, true]])('rendered checkout includes bank discount at %s boundary', async (total, free) => {
    mockTotal = total;
    axios.post.mockResolvedValue({ data: { applied: [{ code: 'KARGO0', title: 'Ücretsiz Kargo', free_shipping: true, discount: 0 }], total_discount: 0 } });
    await act(async () => root.render(<Checkout />));
    const row = $(container, "shipping-cost");
    expect(row.textContent.includes('Ücretsiz')).toBe(free);
    expect(row.textContent).toContain(formatTRY(99));
    const promos = $(container, "applied-promotions");
    expect(promos.textContent.includes('Ücretsiz Kargo')).toBe(free);
  });

  test("account switch clears address and ignores the former account's delayed response", async () => {
    let resolveOld;
    mockUser = { id: "old", email: "old@example.test" };
    axios.get.mockImplementation((url) => url.endsWith("/my-addresses")
      ? new Promise((r) => { resolveOld = r; }) : Promise.resolve({ data: {} }));
    await act(async () => root.render(<Checkout />));
    mockUser = { id: "new", email: "new@example.test" };
    axios.get.mockResolvedValue({ data: {} });
    await act(async () => root.render(<Checkout />));
    await act(async () => resolveOld({ data: { addresses: [{ first_name: "PRIVATE_PREVIOUS_CUSTOMER", address: "PRIVATE_ADDRESS" }] } }));
    expect(container.textContent).not.toContain("PRIVATE_PREVIOUS_CUSTOMER");
    expect(container.textContent).not.toContain("PRIVATE_ADDRESS");
    container.querySelectorAll("input").forEach((i) => {
      expect(i.value).not.toContain("PRIVATE");
    });
    expect(localStorage.getItem("store_last_address")).toBeNull();
  });

  test.each([
    [3790, 3790, 758, 303.2, 2691.36],
    // Backend cap/scope can differ from the cached product badge: never recalculate it.
    [3790, 3790, 400, 339, 2997.45],
    // Embedded sale price stays separate from campaign discounts.
    [4000, 3790, 0, 379, 3339.45],
    // Campaign removed: cached 20% badge must not produce a phantom discount.
    [3790, 3790, 0, 0, 3699.5],
  ])('both summaries use authoritative discounts (%s/%s/%s/%s)', async (listPrice, total, launch, welcome, final) => {
    mockTotal = total;
    Object.assign(mockCartItems[0], {price: total, listPrice, campaignPct: 20});
    const applied = [
      {coupon_id: 'launch', code: 'LAUNCH', title: 'Lansman %20', discount: launch},
      {coupon_id: 'welcome', code: 'WELCOME', title: 'Hoş geldin %10', discount: welcome},
    ].filter(p => p.discount > 0);
    axios.post.mockResolvedValue({data: {applied, total_discount: launch + welcome}});
    await act(async () => root.render(<Checkout />));
    const lower = $(container, "promotion-totals");
    expect(lower.children).toHaveLength(applied.length);
    applied.forEach((p, i) => {
      expect(lower.children[i].textContent.trim()).toBe(`${p.title}-${formatTRY(p.discount)}`);
      expect($(container, "applied-promotions").textContent).toContain(`${p.title}-${formatTRY(p.discount)}`);
    });
    expect($(container, "grand-total").textContent).toContain(formatTRY(final));
    expect($(container, "summary-toggle-total").textContent).toBe(formatTRY(final));
    expect(container.textContent).not.toContain('682,20');
    if (listPrice > total) expect(container.textContent).toContain(`Ürün fiyat indirimi-${formatTRY(210)}`);
  });
});

describe("shopify-style checkout behaviour", () => {
  let root, container;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; });
  beforeEach(() => {
    mockUser = null;
    mockTotal = 100;
    Object.assign(mockCartItems[0], { price: 100, listPrice: 100, campaignPct: 0 });
    localStorage.clear();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    axios.get.mockResolvedValue({ data: {} });
    axios.post.mockResolvedValue({ data: { applied: [], eligible: [], total_discount: 0 } });
  });
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); jest.clearAllMocks(); });

  test("renders its own slim header and no site header/footer, policy links at the bottom", async () => {
    await act(async () => root.render(<Checkout />));
    expect($(container, "checkout-header").textContent).toContain("Güvenli Ödeme");
    expect($(container, "checkout-back-btn").getAttribute("href")).toBe("/sepet");
    const footer = $(container, "checkout-footer");
    ["İade politikası", "Gizlilik politikası", "Mesafeli Satış Sözleşmesi"].forEach((t) => expect(footer.textContent).toContain(t));
  });

  test("switching payment method expands that method's content inline and fires add_payment_info", async () => {
    await act(async () => root.render(<Checkout />));
    // Varsayılan: Havale/EFT seçili ve içeriği açık
    expect($(container, "pm-bank_transfer-content")).not.toBeNull();
    expect($(container, "card-form")).toBeNull();
    expect($(container, "bank-discount-row")).not.toBeNull();
    expect($(container, "place-order-btn").textContent).toBe("Siparişi tamamla");

    await act(async () => { $(container, "pm-credit_card").querySelector("input[type=radio]").click(); });
    expect($(container, "card-form")).not.toBeNull();
    expect($(container, "pm-bank_transfer-content")).toBeNull();
    expect($(container, "bank-discount-row")).toBeNull();
    expect($(container, "pm-credit_card").className).toContain("is-selected");
    expect($(container, "place-order-btn").textContent).toBe("Şimdi öde");
    expect(trackAddPaymentInfo).toHaveBeenCalledWith(expect.objectContaining({ payment_type: "credit_card", currency: "TRY" }));
  });

  test("cash on delivery only appears when enabled in settings, with its fee", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/settings")
      ? { payment_methods: { credit_card: true, bank_transfer: true, cash_on_delivery: true } }
      : url.endsWith("/business-rules") ? { "shipping.cod_fee": 25 } : {} }));
    await act(async () => root.render(<Checkout />));
    const cod = $(container, "pm-cash_on_delivery");
    expect(cod).not.toBeNull();
    await act(async () => { cod.querySelector("input[type=radio]").click(); });
    expect($(container, "pm-cash_on_delivery-content").textContent).toContain(formatTRY(25));
    expect($(container, "cod-fee-row").textContent).toContain(formatTRY(25));
  });

  test("cash on delivery is hidden by default", async () => {
    await act(async () => root.render(<Checkout />));
    expect($(container, "pm-cash_on_delivery")).toBeNull();
  });

  test("mobile order summary toggles open and shows the total", async () => {
    await act(async () => root.render(<Checkout />));
    const toggle = $(container, "summary-toggle");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect($(container, "order-summary").className).not.toContain("is-open");
    expect(toggle.textContent).toContain("Sipariş özetini göster");
    await act(async () => { toggle.click(); });
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect($(container, "order-summary").className).toContain("is-open");
    expect(toggle.textContent).toContain("Sipariş özetini gizle");
    // 100 - %5 havale + 99 kargo
    expect($(container, "summary-toggle-total").textContent).toBe(formatTRY(194));
  });

  test("submitting an empty form shows inline field errors and does not create an order", async () => {
    await act(async () => root.render(<Checkout />));
    await act(async () => { $(container, "place-order-btn").click(); });
    expect($(container, "checkout-error-banner")).not.toBeNull();
    expect($(container, "contact-email").getAttribute("aria-invalid")).toBe("true");
    expect($(container, "shipping-first-name").getAttribute("aria-invalid")).toBe("true");
    expect($(container, "shipping-phone").getAttribute("aria-invalid")).toBe("true");
    expect($(container, "accept-terms-checkbox").getAttribute("aria-invalid")).toBe("true");
    expect(container.textContent).toContain("İl seçin");
    expect(axios.post.mock.calls.some(([u]) => u.endsWith("/orders"))).toBe(false);

    // Hata, alan düzeltilince kalkar
    await act(async () => { typeInto($(container, "shipping-first-name"), "Ayşe"); });
    expect($(container, "shipping-first-name").getAttribute("aria-invalid")).toBeNull();
  });

  test("card payment validates card fields and corporate TCKN", async () => {
    await act(async () => root.render(<Checkout />));
    await act(async () => { $(container, "pm-credit_card").querySelector("input[type=radio]").click(); });
    await act(async () => { $(container, "corporate-invoice-checkbox").querySelector("input").click(); });
    await act(async () => { typeInto($(container, "corp-tax-number-input"), "12345678901"); });
    await act(async () => { $(container, "place-order-btn").click(); });
    expect($(container, "card-number").getAttribute("aria-invalid")).toBe("true");
    expect($(container, "card-cvc").getAttribute("aria-invalid")).toBe("true");
    expect(container.textContent).toContain("Geçerli bir TC kimlik numarası girin");
  });

  test("discount code apply calls the campaign engine with the folded code", async () => {
    axios.post.mockImplementation((url, body) => Promise.resolve({ data: url.endsWith("/coupons/evaluate") && body.code
      ? { applied: [{ coupon_id: "c1", code: "HOSGELDIN10", title: "Hoş geldin", discount: 10 }], total_discount: 10 }
      : { applied: [], eligible: [], total_discount: 0 } }));
    await act(async () => root.render(<Checkout />));
    await act(async () => { typeInto($(container, "manual-coupon-input"), "hoşgeldin"); });
    await act(async () => { $(container, "apply-coupon-btn").click(); });
    await flush();
    const call = axios.post.mock.calls.find(([u, b]) => u.endsWith("/coupons/evaluate") && b.code);
    expect(call[1]).toEqual(expect.objectContaining({ code: "HOSGELDIN10", payment_method: "bank_transfer", cart_total: 100 }));
    expect($(container, "coupon-message").textContent).toContain("Kupon uygulandı");
    expect($(container, "remove-coupon-btn")).not.toBeNull();
    expect($(container, "promotion-totals").textContent).toContain(`Hoş geldin-${formatTRY(10)}`);
  });

  test("invalid code falls back to gift card check and shows inline error", async () => {
    axios.post.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/gift-cards/check")
      ? { valid: false } : { applied: [], rejected: [], total_discount: 0 } }));
    await act(async () => root.render(<Checkout />));
    await act(async () => { typeInto($(container, "manual-coupon-input"), "YOKBOYLE"); });
    await act(async () => { $(container, "apply-coupon-btn").click(); });
    await flush();
    expect(axios.post.mock.calls.some(([u]) => u.endsWith("/gift-cards/check"))).toBe(true);
    expect($(container, "coupon-message").textContent).toContain("geçersiz");
  });

  test("legal documents open in a modal from the agreement checkbox", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/pages/mesafeli-satis")
      ? { title: "Mesafeli Satış Sözleşmesi", content: "<p>MADDE 1</p>" } : {} }));
    await act(async () => root.render(<Checkout />));
    await act(async () => { $(container, "open-distance-sales").click(); });
    await flush();
    expect($(container, "legal-modal").textContent).toContain("MADDE 1");
    expect($(container, "accept-terms-checkbox").checked).toBe(false);
    await act(async () => { $(container, "legal-modal-close").click(); });
    expect($(container, "legal-modal")).toBeNull();
  });

  test("valid guest bank-transfer order posts the full payload and redirects to order success", async () => {
    axios.post.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/orders")
      ? { order_id: "o1", order_number: "FC123", payment_status: "pending", total: 194 }
      : { applied: [], eligible: [], total_discount: 0 } }));
    await act(async () => root.render(<Checkout />));
    await act(async () => {
      typeInto($(container, "contact-email"), "musteri@example.test");
      typeInto($(container, "shipping-first-name"), "Ayşe");
      typeInto($(container, "shipping-last-name"), "Yılmaz");
      typeInto($(container, "shipping-address"), "Moda Cad. No 5");
      typeInto($(container, "shipping-address2"), "Daire 3");
      typeInto($(container, "shipping-phone"), "0532 111 22 33");
    });
    await act(async () => { $(container, "shipping-pds-mock").click(); });
    expect($(container, "shipping-methods")).not.toBeNull();
    await act(async () => { $(container, "consent-email").click(); });
    await act(async () => { $(container, "accept-terms-checkbox").click(); });
    await act(async () => { $(container, "place-order-btn").click(); });
    await flush();
    const call = axios.post.mock.calls.find(([u]) => u.endsWith("/orders"));
    expect(call).toBeTruthy();
    const body = call[1];
    expect(body.payment_method).toBe("bank_transfer");
    expect(body.shipping_address).toEqual(expect.objectContaining({
      email: "musteri@example.test", first_name: "Ayşe", last_name: "Yılmaz",
      address: "Moda Cad. No 5 Daire 3", city: "İstanbul", district: "Kadıköy", phone: "05321112233",
    }));
    expect(body.shipping_address.address2).toBeUndefined();
    expect(body.billing_same_as_shipping).toBe(true);
    expect(body.billing_address.address).toBe("Moda Cad. No 5 Daire 3");
    expect(body.marketing_consent).toEqual({ email: true, sms: false, otp_verified: false });
    expect(body.billing_info).toEqual({ is_corporate: false });
    expect(typeof body.idempotency_key).toBe("string");
    expect(body.total).toBe(194);
    expect(trackPurchase).toHaveBeenCalledWith(expect.objectContaining({ order_id: "FC123", payment_type: "bank_transfer" }));
    expect(mockClearCart).toHaveBeenCalled();
    expect(mockNavigate).toHaveBeenCalledWith("/order-success/FC123", { replace: true });
  });

  test("server error is shown in a Shopify-like banner", async () => {
    axios.post.mockImplementation((url) => (url.endsWith("/orders")
      ? Promise.reject({ response: { data: { detail: "Stok yetersiz" } } })
      : Promise.resolve({ data: { applied: [], eligible: [], total_discount: 0 } })));
    window.scrollTo = jest.fn();
    await act(async () => root.render(<Checkout />));
    await act(async () => {
      typeInto($(container, "contact-email"), "m@example.test");
      typeInto($(container, "shipping-first-name"), "A");
      typeInto($(container, "shipping-last-name"), "B");
      typeInto($(container, "shipping-address"), "Adres 1");
      typeInto($(container, "shipping-phone"), "05321112233");
    });
    await act(async () => { $(container, "shipping-pds-mock").click(); });
    await act(async () => { $(container, "accept-terms-checkbox").click(); });
    await act(async () => { $(container, "place-order-btn").click(); });
    await flush();
    expect($(container, "checkout-error-banner").textContent).toContain("Stok yetersiz");
    expect(mockNavigate).not.toHaveBeenCalledWith(expect.stringContaining("/order-success"), expect.anything());
  });
});
