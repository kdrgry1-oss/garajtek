import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";
import { clearCatalogBrands } from "../brands_carousel/Render";

beforeEach(() => { mockFetch([]); clearCatalogBrands(); });

test("varsayılan: Markalar satırı, + Tüm Markalar, 8 kutu (5 bağlantı + …), slider üstüne biner", async () => {
  const { container, unmount } = await renderBlock("categories_brands_card", {});
  const root = container.querySelector("[data-testid=categories-brands-card]");
  expect(root.className).toContain("mt-xl-n10");
  expect(container.querySelector('[data-pd-field="brands_label"]').textContent).toBe("Markalar:");
  expect(container.querySelector('[data-pd-field="more_brands.text"]').textContent).toBe("+ Tüm Markalar");
  expect(container.querySelectorAll(".pd-cbc__box").length).toBe(8);
  expect(container.querySelector('[data-pd-field="boxes.0.title"]').textContent).toBe("Araç Liftleri");
  expect(container.querySelectorAll(".pd-cbc__box")[0].querySelectorAll("li").length).toBe(6);
  expect(container.querySelector('[data-pd-field="boxes.0.header_image"][data-pd-placeholder]')).not.toBeNull();
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("elle logolar, marka satırı gizli, bindirme kapalı", async () => {
  let r = await renderBlock("categories_brands_card", { brands_source: "manual", brands: [{ logo: { url: "/api/uploads/x.png" }, name: "X", link: { kind: "none", url: "" } }] });
  expect(r.container.querySelector('[data-pd-field="brands.0.logo"] img').className).toContain("height-35");
  r.unmount();
  r = await renderBlock("categories_brands_card", { brands_source: "none", overlap_hero: false, show_more_link: false });
  expect(r.container.querySelector('[data-pd-field="brands_label"]')).toBeNull();
  expect(r.container.querySelector(".mt-xl-n10")).toBeNull();
  expect(r.container.querySelectorAll(".pd-cbc__box")[0].querySelectorAll("li").length).toBe(5);
  r.unmount();
});
