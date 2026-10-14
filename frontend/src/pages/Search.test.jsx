import { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import Search from "./Search";

const mockSearch = new URLSearchParams("q=a");
jest.mock("axios", () => ({ get: jest.fn() }));
jest.mock("react-router-dom", () => ({
  useSearchParams: () => [mockSearch],
  useNavigate: () => jest.fn(),
  Link: ({ children, to, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });
jest.mock("../components/Header", () => () => null);
jest.mock("../components/Footer", () => () => null);
jest.mock("../components/electro/Breadcrumb", () => () => null);
jest.mock("../components/electro/useCategoryTree", () => ({ __esModule: true, default: () => [], findBySlug: () => null }));
jest.mock("../lib/dataLayer", () => ({ trackSearch: jest.fn() }));
jest.mock("../components/ProductCard", () => ({ product }) => <li data-testid="pc">{product.name}</li>);

const mk = (from, n) => Array.from({ length: n }, (_, i) => ({ id: `p${from + i}`, name: `Ürün ${from + i}` }));

describe("arama sayfalama", () => {
  let root, container;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; });
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); jest.clearAllMocks(); });

  test("40'tan fazla sonuçta 'Daha fazla göster' kalan ürünleri ekler", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.includes("page=2")
      ? { products: mk(40, 12), total: 52, page: 2, pages: 2 }
      : { products: mk(0, 40), total: 52, page: 1, pages: 2 } }));
    await act(async () => root.render(<Search />));
    expect(axios.get.mock.calls[0][0]).toContain("page=1");
    expect(container.querySelectorAll('[data-testid="pc"]').length).toBe(40);
    const more = container.querySelector('[data-testid="search-load-more"]');
    expect(more).not.toBeNull();
    await act(async () => { more.click(); });
    expect(axios.get.mock.calls[1][0]).toContain("page=2");
    expect(container.querySelectorAll('[data-testid="pc"]').length).toBe(52);
    expect(container.querySelector('[data-testid="search-load-more"]')).toBeNull();
  });

  test("tek sayfalık sonuçta buton yok", async () => {
    axios.get.mockResolvedValue({ data: { products: mk(0, 5), total: 5, page: 1, pages: 1 } });
    await act(async () => root.render(<Search />));
    expect(container.querySelectorAll('[data-testid="pc"]').length).toBe(5);
    expect(container.querySelector('[data-testid="search-load-more"]')).toBeNull();
  });
});
