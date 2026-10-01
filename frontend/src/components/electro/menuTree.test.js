jest.mock("axios", () => ({ get: jest.fn() }));
import { buildTree } from "./useCategoryTree";
import { iconClassFor } from "./CategoryIcon";

describe("kategori ağacı (dikey menü)", () => {
  test("alt kategoriler köke düşmez; show_in_menu=false menü köklerinden çıkar", () => {
    const list = [
      { id: "1", name: "Liftler", parent_id: null, sort_order: 10 },
      { id: "2", name: "Test ve Arıza Tespit Cihazları", parent_id: null, sort_order: 110 },
      { id: "3", name: "Arıza Tespit Cihazları", parent_id: "2", sort_order: 10 },
      { id: "4", name: "İndirimli Ürünler", parent_id: null, sort_order: 150, show_in_menu: false },
      { id: "5", name: "İki Sütunlu Liftler", parent_id: "1", sort_order: 10 },
    ];
    const t = buildTree(list);
    expect(t.roots.map((r) => r.id)).toEqual(["1", "2", "4"]);
    expect(t.menuRoots.map((r) => r.id)).toEqual(["1", "2"]);
    expect(t.menuRoots[1].children.map((c) => c.name)).toEqual(["Arıza Tespit Cihazları"]);
  });

  test("seed ikon adları Font Awesome'a çevrilir, bilinmeyen ad isimden tahmin edilir", () => {
    expect(iconClassFor({ name: "Liftler", icon: "arrow-up-from-line" })).toBe("fas fa-car-side");
    expect(iconClassFor({ name: "Kompresörler", icon: "gauge" })).toBe("fas fa-tachometer-alt");
    expect(iconClassFor({ name: "El Aletleri", icon: "bilinmeyen-ikon" })).toBe("fas fa-wrench");
    expect(iconClassFor({ name: "X", icon: "ec ec-tvs" })).toBe("ec ec-tvs");
  });
});
