import { buildTree } from "./useCategoryTree";

jest.mock("axios", () => ({ get: jest.fn() }));

test("sıra 0 olan kategori en önde (eskiden 999 sayılıp menü dışına düşüyordu)", () => {
  const { roots } = buildTree([
    { id: 1, name: "Beş", parent_id: null, sort_order: 5 },
    { id: 2, name: "Sıfır", parent_id: null, sort_order: 0 },
    { id: 3, name: "Boş", parent_id: null },
    { id: 4, name: "Bir", parent_id: null, sort_order: "1" },
  ]);
  expect(roots.map((r) => r.name)).toEqual(["Sıfır", "Bir", "Beş", "Boş"]);
});
