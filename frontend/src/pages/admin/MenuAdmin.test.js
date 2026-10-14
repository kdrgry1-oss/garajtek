import { autoMenuItems } from "./MenuAdmin";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

// 18 menü kökü (max_roots=14'ten fazla) + 1 menüde gizli kök.
const cats = [
  ...Array.from({ length: 18 }, (_, i) => ({ id: `r${i}`, name: `Kök ${i}`, slug: `kok-${i}`, parent_id: null, sort_order: i + 1 })),
  { id: "gizli", name: "Gizli", slug: "gizli", parent_id: null, sort_order: 50, show_in_menu: false },
  { id: "c1", name: "Alt", slug: "alt", parent_id: "r0", sort_order: 1 },
];

describe("MenuAdmin autoMenuItems (Tüm Kategoriler menüsü elle moda aktarım)", () => {
  it("departments: tüm menü köklerini aktarır, max_roots ile KIRPMAZ (vitrinde 'Tüm Kategoriler' bağlantısı kalır)", () => {
    const items = autoMenuItems("departments", { max_roots: 14 }, { cats });
    expect(items).toHaveLength(18);           // 18 > 14 → Header 'Tüm Kategoriler' bağlantısını çizer
    expect(items.map((x) => x.label)).not.toContain("Gizli");
    expect(items[0]).toMatchObject({ label: "Kök 0", link: "/kok-0" });
    expect(items[0].children[0]).toMatchObject({ label: "Alt", link: "/alt" });
  });
});
