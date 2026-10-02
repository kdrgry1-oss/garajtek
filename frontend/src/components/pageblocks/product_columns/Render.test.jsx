import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = [
  { id: "p1", name: "4 Ton Lift", price: 100, sale_price: 80, stock: 3, images: [], rating: 4 },
  { id: "p2", name: "Kompresör", price: 50, stock: 1, images: [] },
  { id: "p3", name: "Balans", price: 70, stock: 1, images: [] },
  { id: "p4", name: "Sökücü", price: 90, stock: 1, images: [] },
];

describe("product_columns", () => {
  test("varsayılan: 3 sütun başlığı, sütun başına 3 ürün, ≥992'de görünür; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_columns", {});
    expect(container.querySelector('[data-testid="product-columns"]').className).toBe("d-none d-lg-block");
    expect(container.querySelector('[data-pd-field="columns.0.title"]').textContent).toBe("Öne Çıkan Ürünler");
    expect(container.querySelector('[data-pd-field="columns.2.title"]').textContent).toBe("En Çok Beğenilenler");
    expect(container.querySelectorAll('[data-testid="pcol-0"] li.product-item__list').length).toBe(3);
    expect(container.querySelector('[data-testid="pcol-0"]').className).toContain("col-lg-4");
    expect(container.querySelector('[data-testid="pcol-0"]').className).toContain("col-wd-4");
    // indirimli üründe eski fiyat; yıldız yalnız 3. sütunda ve puanlı üründe
    expect(container.querySelector('[data-testid="pcol-0"] del')).not.toBeNull();
    expect(container.querySelector('[data-testid="pcol-0"] [data-testid="pcol-rating"]')).toBeNull();
    expect(container.querySelectorAll('[data-testid="pcol-2"] [data-testid="pcol-rating"] .fas.fa-star').length).toBe(4);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("tanıtım görseli (≥1480) + 4 sütun düzeni + eski fiyat kapalı", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_columns", { promo: { enabled: true }, columns: [{ title: "A", show_old_price: false }, { title: "B" }, { title: "C" }], min_screen: "all" });
    expect(container.querySelector('[data-testid="pcol-promo"]').className).toContain("d-wd-block");
    expect(container.querySelector('[data-testid="pcol-promo"] [data-pd-field="promo.image"]')).not.toBeNull();
    expect(container.querySelector('[data-testid="pcol-0"]').className).toContain("col-wd-3");
    expect(container.querySelector('[data-testid="pcol-0"] del')).toBeNull();
    expect(container.querySelector('[data-testid="product-columns"]').className).toBe("");
    unmount();
  });

  test("ürünsüz sütun vitrinde gizli, önizlemede not", async () => {
    mockFetch([]);
    const a = await renderBlock("product_columns", {});
    expect(a.container.querySelectorAll('[data-testid^="pcol-"]').length).toBe(0);
    a.unmount();
    mockFetch([]);
    const b = await renderBlock("product_columns", {}, { preview: true });
    expect(b.container.querySelectorAll('[data-testid="pc-empty"]').length).toBe(3);
    b.unmount();
  });
});
