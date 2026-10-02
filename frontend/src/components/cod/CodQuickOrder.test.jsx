import { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import CodQuickOrder, { validateCodForm, buildCodOrderPayload, formatTrPhone, normalizeTrPhone, isValidTrMobile } from "./CodQuickOrder";
import { resetCodInfoCache } from "../../lib/cod";

const mockNavigate = jest.fn();
jest.mock("react-router-dom", () => ({ useNavigate: () => mockNavigate }), { virtual: true });
jest.mock("axios", () => ({ post: jest.fn() }));
jest.mock("../ProvinceDistrictSelect", () => {
  const React = require("react");
  return ({ onChange, testIdPrefix }) => React.createElement("button", {
    type: "button", "data-testid": `${testIdPrefix}-pds-mock`, onClick: () => onChange({ city: "İstanbul", district: "Kadıköy" }),
  }, "il-ilce");
});
jest.mock("../checkout/LegalModal", () => () => null);
jest.mock("../../utils/pixelEvents", () => ({ trackPurchase: jest.fn() }));
jest.mock("../../lib/dataLayer", () => ({ collectClickIds: () => ({}) }));

const QUOTE = { available: true, subtotal: 2990, discount: 0, shipping: 0, cod_fee: 49, total: 3039, promotions: [],
  lines: [{ product_id: "p1", variant_id: null, quantity: 1, price: 2990, name: "Somun Sökme", image: "", category_id: "7" }] };
const PRODUCT = { id: "p1", name: "Somun Sökme", price: 3490, sale_price: 2990, stock: 5, images: [] };

test("telefon biçimi ve doğrulama", () => {
  expect(normalizeTrPhone("0 (532) 123 45 67")).toBe("5321234567");
  expect(normalizeTrPhone("+90 532 123 45 67")).toBe("5321234567");
  expect(formatTrPhone("5321234567")).toBe("0 (532) 123 45 67");
  expect(isValidTrMobile("4321234567")).toBe(false);
  expect(isValidTrMobile("05321234567")).toBe(true);
});

test("form doğrulaması zorunlu alanları ve sözleşmeleri ister", () => {
  const e = validateCodForm({ name: "Ahmet", phone: "123", address: "kısa", email: "x@", acceptPre: false, acceptContract: false });
  expect(Object.keys(e).sort()).toEqual(["acceptContract", "acceptPre", "address", "city", "district", "email", "name", "phone"]);
  expect(validateCodForm({ name: "Ahmet Usta", phone: "5321234567", city: "İstanbul", district: "Kadıköy",
    address: "Sanayi Sitesi 12. Blok No 4", acceptPre: true, acceptContract: true })).toEqual({});
});

test("sipariş gövdesi kasa şemasıyla aynı (misafir, kapıda ödeme, set alanları)", () => {
  const body = buildCodOrderPayload({ name: "Ahmet Ali Usta", phone: "0532 123 45 67", city: "İstanbul", district: "Kadıköy",
    address: "Sanayi Sitesi 12", email: "a@b.co", mktEmail: true, note: "Akşam teslim" },
  { ...QUOTE, lines: [{ ...QUOTE.lines[0], set_id: "S1", set_slot: "p1" }] }, "codq-1");
  expect(body).toMatchObject({ payment_method: "cash_on_delivery", total: 3039, user_id: null, idempotency_key: "codq-1",
    shipping_address: { first_name: "Ahmet Ali", last_name: "Usta", phone: "5321234567", city: "İstanbul" },
    marketing_consent: { email: true, sms: false }, notes: "Akşam teslim" });
  expect(body.items[0]).toMatchObject({ product_id: "p1", quantity: 1, set_id: "S1", set_slot: "p1" });
});

describe("ürün sayfası butonu + modal", () => {
  let root, container;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; delete global.fetch; });
  beforeEach(() => {
    resetCodInfoCache();
    jest.clearAllMocks();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); });
  const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 260)); });
  const $ = (id) => document.querySelector(`[data-testid="${id}"]`);
  const type = (el, v) => {
    const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, v);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  };

  test("kapıda ödeme kapalıyken buton hiç görünmez", async () => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ enabled: false }) }));
    await act(async () => root.render(<CodQuickOrder product={PRODUCT} />));
    await flush();
    expect($("pdp-cod-order-btn")).toBeNull();
  });

  test("açıkken modal → doğrulama → normal sipariş yolu (POST /orders) → başarı sayfası", async () => {
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ enabled: true, fee: 49, excluded_category_ids: [] }) }));
    axios.post.mockImplementation((url) => {
      if (url.endsWith("/storefront/cod-check")) return Promise.resolve({ data: { available: true, blocked: [] } });
      if (url.endsWith("/storefront/cod-quote")) return Promise.resolve({ data: QUOTE });
      if (url.endsWith("/orders")) return Promise.resolve({ data: { order_number: "W10077", order_id: "o1" } });
      return Promise.resolve({ data: {} });
    });
    await act(async () => root.render(<CodQuickOrder product={PRODUCT} quantity={1} />));
    await flush();
    await act(async () => $("pdp-cod-order-btn").click());
    await flush();
    expect($("cod-quick-total").textContent).toContain("3.039,00");
    await act(async () => $("cod-quick-submit").click());
    expect(axios.post.mock.calls.some(([u]) => u.endsWith("/orders"))).toBe(false); // eksik form gönderilmez
    await act(async () => {
      type($("cod-quick-name"), "Ahmet Usta");
      type($("cod-quick-phone"), "05321234567");
      type($("cod-quick-address"), "Sanayi Sitesi 12. Blok No 4");
    });
    await act(async () => $("cod-quick-pds-mock").click());
    await act(async () => { $("cod-quick-accept-pre").click(); $("cod-quick-accept-contract").click(); });
    await act(async () => $("cod-quick-submit").click());
    await flush();
    const call = axios.post.mock.calls.find(([u]) => u.endsWith("/orders"));
    expect(call[1]).toMatchObject({ payment_method: "cash_on_delivery", total: 3039,
      shipping_address: { first_name: "Ahmet", last_name: "Usta", phone: "5321234567", district: "Kadıköy" } });
    expect(mockNavigate).toHaveBeenCalledWith("/order-success/W10077");
  });
});
