import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 4 }, (_, i) => ({ id: `p${i}`, name: `Kompresör ${i}`, price: 500 + i, stock: 2, images: [], category_name: "Kompresörler" }));

test("varsayılan: Öne Çıkan Ürünler, 1'li karusel, başlıkta oklar, kategori adı", async () => {
  mockFetch(P);
  const { container, unmount } = await renderBlock("sidebar_products_carousel", {});
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Öne Çıkan Ürünler");
  expect(container.querySelector("[data-testid=header-arrows]")).not.toBeNull();
  expect(container.querySelectorAll(".product-item.remove-divider").length).toBe(4);
  expect(container.querySelector(".text-gray-5").textContent).toBe("Kompresörler");
  expect(hardcodedTexts(container)).toEqual([]);
  const body = JSON.parse(global.fetch.mock.calls.find((c) => String(c[0]).includes("resolve-products"))[1].body);
  expect(body.sources[0]).toMatchObject({ kind: "featured", limit: 4 });
  unmount();
});

test("kategori gizli, oklar kapalı, boş durum", async () => {
  mockFetch(P);
  let r = await renderBlock("sidebar_products_carousel", { show_category: false, carousel: { arrows: "none" } });
  expect(r.container.querySelector(".text-gray-5")).toBeNull();
  expect(r.container.querySelector("[data-testid=header-arrows]")).toBeNull();
  r.unmount();
  mockFetch([]);
  r = await renderBlock("sidebar_products_carousel", {});
  expect(r.container.textContent).toBe("");
  r.unmount();
});
