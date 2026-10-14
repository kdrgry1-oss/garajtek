import {
  DEFAULT_VAT_RATE, normalizeVatRate, buildVariantsPayload,
  resolveFormCategories, stripUnresolvedCategories,
} from "./Products";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
// react-router v7 paket "exports" eşlemesi CRA jest'inde çözülmüyor → yalın taklit
jest.mock("react-router-dom", () => ({
  useSearchParams: () => [new URLSearchParams(), jest.fn()],
  useParams: () => ({}),
  useNavigate: () => jest.fn(),
  Link: ({ children }) => children,
}), { virtual: true });
// Yalnız saf yardımcılar test ediliyor; shadcn bileşenlerinin "@/" alias'ı CRA jest'inde
// çözülmüyor → yalın cn taklidi.
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });

describe("Products.jsx yardımcıları — regresyon", () => {
  // #36: %0 KDV korunur, ondalık kırpılmaz, yeni ürün varsayılanı %20
  it("normalizeVatRate: 0 ve ondalıklı oranlar korunur, boşta varsayılan %20", () => {
    expect(DEFAULT_VAT_RATE).toBe(20);
    expect(normalizeVatRate(0)).toBe(0);
    expect(normalizeVatRate("0")).toBe(0);
    expect(normalizeVatRate(8.5)).toBe(8.5);
    expect(normalizeVatRate(10)).toBe(10);
    expect(normalizeVatRate(null)).toBe(20);
    expect(normalizeVatRate(undefined)).toBe(20);
    expect(normalizeVatRate("")).toBe(20);
    expect(normalizeVatRate("abc")).toBe(20);
  });

  // #31: varyanta özel stok kodu ana kodla EZİLMEZ
  it("buildVariantsPayload: varyant kodu korunur, yalnız boş olana ana kod yazılır", () => {
    const out = buildVariantsPayload([
      { stock_code: "GT-IZL-YIA-0607", sku: "a", _priceInput: "1" },
      { stock_code: "", sku: "b" },
      { sku: "c" },
    ], "GT-IZL-YIA");
    expect(out.map((v) => v.stock_code)).toEqual(["GT-IZL-YIA-0607", "GT-IZL-YIA", "GT-IZL-YIA"]);
    expect(out[0]).not.toHaveProperty("_priceInput");
    expect(buildVariantsPayload(undefined, "X")).toEqual([]);
  });

  // #27: yalnız category_name taşıyan ürün
  const cats = [{ id: 2602, name: "Penseler", parent_id: null }];
  const product = { id: "7962", category_name: "Penseler", categories: [], category_id: null };

  it("resolveFormCategories: yüklü listeyle category_name → id eşlenir", () => {
    expect(resolveFormCategories(product, cats)).toEqual(["2602"]);
    expect(resolveFormCategories(product, [])).toEqual([]);
  });

  it("stripUnresolvedCategories: çözülemeyen boş seçim gönderilmez (backend kategoriyi silmez)", () => {
    const p = stripUnresolvedCategories({ name: "x", category_name: "Penseler", categories: [], category_id: null });
    expect(p).not.toHaveProperty("categories");
    expect(p).not.toHaveProperty("category_id");
    expect(p.category_name).toBe("Penseler");
    // Admin tüm kategorileri gerçekten kaldırdıysa (category_name de boş) → boş seçim GİDER
    const cleared = stripUnresolvedCategories({ category_name: "", categories: [], category_id: null });
    expect(cleared.categories).toEqual([]);
    // Seçim doluysa dokunulmaz
    const sel = stripUnresolvedCategories({ category_name: "Penseler", categories: ["2602"] });
    expect(sel.categories).toEqual(["2602"]);
  });
});
