import { act } from "react";
import { createRoot } from "react-dom/client";
import { PendingLineBox, SetPendingGuard, OOS_MESSAGE } from "./SetCartParts";

const mockNavigate = jest.fn();
const mockReplace = jest.fn(() => true);
const mockRemove = jest.fn();
const mockRefresh = jest.fn();
let mockPending = [];
jest.mock("react-router-dom", () => {
  const React = require("react");
  return {
    useNavigate: () => mockNavigate,
    Link: ({ to, children, ...p }) => React.createElement("a", { href: to, ...p }, children),
  };
}, { virtual: true });
jest.mock("../../context/CartContext", () => ({
  useCart: () => ({ pendingItems: mockPending, items: [], replacePending: mockReplace, removeItem: mockRemove,
    refreshStock: mockRefresh, setIsOpen: jest.fn() }),
}));
jest.mock("sonner", () => ({ toast: { success: jest.fn() } }));

const LINE = { id: "set:S1:A", productId: "A", setId: "S1", setSlot: "A", setName: "Atölye Seti", name: "94 Parça Lokma",
  quantity: 1, needsReplacement: true, replaceCategory: { id: "11", slug: "lokma-setleri", name: "Lokma Setleri" } };

describe("tükenen kalem kutusu", () => {
  let root, container;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; delete global.fetch; });
  beforeEach(() => {
    sessionStorage.clear();
    jest.clearAllMocks();
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [
      { id: "C", name: "108 Parça Lokma", slug: "lokma-108", price: 900, stock: 7, images: ["/c.webp"], variants: [] },
    ] }) }));
    container = document.createElement("div");
    root = createRoot(container);
  });
  afterEach(async () => { await act(async () => root.unmount()); });
  const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

  test("mesaj, 'Bu ürünü değiştir' kategoriye götürür, öneri seçilince kalem değişir", async () => {
    await act(async () => root.render(<PendingLineBox line={LINE} />));
    await flush();
    expect(container.textContent).toContain(OOS_MESSAGE);
    expect(container.textContent).toContain("Bu ürünü değiştir");
    await act(async () => container.querySelector('[data-testid="set-replace-A"]').click());
    expect(mockNavigate).toHaveBeenCalledWith("/lokma-setleri?degistir=S1%3AA");
    expect(JSON.parse(sessionStorage.getItem("set_replace_ctx"))).toMatchObject({ lineId: "set:S1:A", categoryId: "11" });
    expect(global.fetch.mock.calls[0][0]).toContain("/storefront/alternatives?product_id=A");
    await act(async () => container.querySelector('[data-testid="alt-pick-C"]').click());
    expect(mockReplace).toHaveBeenCalledWith("set:S1:A", expect.objectContaining({ id: "C" }), null);
  });

  test("kasa koruması: bekleyen kalem varken uyarı + stok tazeleme + kaldırma", async () => {
    mockPending = [LINE];
    await act(async () => root.render(<SetPendingGuard />));
    await flush();
    expect(mockRefresh).toHaveBeenCalled();
    expect(container.querySelector('[data-testid="checkout-set-guard"]')).not.toBeNull();
    await act(async () => container.querySelector('[data-testid="guard-remove-pending"]').click());
    expect(mockRemove).toHaveBeenCalledWith("set:S1:A");
    mockPending = [];
  });
});
