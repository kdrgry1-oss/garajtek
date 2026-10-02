import { act } from "react";
import { createRoot } from "react-dom/client";
import { CodBadge, CodInfoRow } from "./CodInfo";
import { productCodAllowed, resetCodInfoCache } from "../../lib/cod";
import axios from "axios";

jest.mock("axios", () => ({ post: jest.fn() }));

const INFO_ON = { enabled: true, fee: 25, min_total: 0, max_total: 0, card_badge: true, excluded_category_ids: ["9"] };

function mockFetch(info, check = { available: true, blocked: [] }) {
  global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve(info) }));
  axios.post.mockResolvedValue({ data: check });
}

describe("kapıda ödeme görünürlüğü", () => {
  let root, container;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; delete global.fetch; });
  beforeEach(() => {
    resetCodInfoCache();
    container = document.createElement("div");
    root = createRoot(container);
  });
  afterEach(async () => { await act(async () => root.unmount()); });
  const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

  test("productCodAllowed: ürün ve kategori kapatması", () => {
    expect(productCodAllowed({ id: "1", category_ids: ["3"] }, INFO_ON)).toBe(true);
    expect(productCodAllowed({ id: "1", cod_disabled: true }, INFO_ON)).toBe(false);
    expect(productCodAllowed({ id: "1", category_ids: ["3", "9"] }, INFO_ON)).toBe(false);
    expect(productCodAllowed({ id: "1" }, { ...INFO_ON, enabled: false })).toBe(false);
  });

  test("kart rozeti: açıkken görünür, kapalı üründe ve COD kapalıyken gizli", async () => {
    mockFetch(INFO_ON);
    await act(async () => root.render(<div><CodBadge product={{ id: "p1" }} /><CodBadge product={{ id: "p2", cod_disabled: true }} /></div>));
    await flush();
    expect(container.querySelector('[data-testid="cod-badge-p1"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="cod-badge-p2"]')).toBeNull();

    await act(async () => root.unmount());
    resetCodInfoCache();
    mockFetch({ enabled: false });
    root = createRoot(container);
    await act(async () => root.render(<CodBadge product={{ id: "p1" }} />));
    await flush();
    expect(container.querySelector('[data-testid="cod-badge-p1"]')).toBeNull();
  });

  test("ürün sayfası satırı: bedel gösterir; kapalı üründe uyarı", async () => {
    mockFetch(INFO_ON);
    await act(async () => root.render(<CodInfoRow product={{ id: "p1", price: 100 }} />));
    await flush();
    const row = container.querySelector('[data-testid="pdp-cod-row"]');
    expect(row).not.toBeNull();
    expect(row.textContent).toContain("Kapıda Ödeme");
    expect(row.textContent).toContain("25,00 ₺ hizmet bedeli");

    await act(async () => root.unmount());
    mockFetch(INFO_ON, { available: false, blocked: ["Lift"], reason: "x" });
    root = createRoot(container);
    await act(async () => root.render(<CodInfoRow product={{ id: "lift", price: 100, cod_disabled: true }} />));
    await flush();
    expect(container.querySelector('[data-testid="pdp-cod-unavailable"]')).not.toBeNull();
  });
});
