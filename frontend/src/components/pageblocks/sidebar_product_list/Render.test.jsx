import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 5 }, (_, i) => ({ id: `p${i}`, name: `Lift ${i}`, price: 1000 + i, sale_price: i === 0 ? 900 : undefined, stock: 2, images: [] }));

test("varsayılan: Son Eklenenler, 5 ürün, fiyat", async () => {
  mockFetch(P);
  const { container, unmount } = await renderBlock("sidebar_product_list", {});
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Son Eklenenler");
  expect(container.querySelectorAll("li.product-item__list").length).toBe(5);
  expect(container.querySelector(".product-item__title").textContent).toBe("Lift 0");
  expect(hardcodedTexts(container)).toEqual([]);
  const body = JSON.parse(global.fetch.mock.calls.find((c) => String(c[0]).includes("resolve-products"))[1].body);
  expect(body.sources[0]).toMatchObject({ kind: "newest", limit: 5 });
  unmount();
});

test("sayfalı karusel: başlıkta oklar; ürün yokken boş yazısı", async () => {
  mockFetch(P);
  let r = await renderBlock("sidebar_product_list", { per_page: 2 });
  expect(r.container.querySelector("[data-testid=header-arrows]")).not.toBeNull();
  expect(r.container.querySelectorAll("ul.products-group").length).toBe(3);
  r.unmount();
  mockFetch([]);
  r = await renderBlock("sidebar_product_list", { empty_text: "Yakında" });
  expect(r.container.querySelector('[data-pd-field="empty_text"]').textContent).toBe("Yakında");
  r.unmount();
  mockFetch([]);
  r = await renderBlock("sidebar_product_list", {});
  expect(r.container.textContent).toBe("");
  r.unmount();
});
