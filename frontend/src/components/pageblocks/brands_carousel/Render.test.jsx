import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";
import { clearCatalogBrands } from "./Render";

beforeEach(() => { mockFetch([]); clearCatalogBrands(); });

const logos = [
  { logo: { url: "/api/uploads/b1.png", alt: "" }, name: "Liftmax", link: { kind: "search", url: "/arama?q=Liftmax" } },
  { logo: { url: "/api/uploads/b2.png", alt: "" }, name: "Air Pro", link: { kind: "none", url: "" } },
  { logo: null, name: "Yalnız Ad", link: { kind: "none", url: "" } },
];

test("varsayılan: şablon v1 karusel ayarları ve 85 px alt boşluk", async () => {
  const { container, unmount } = await renderBlock("brands_carousel", {});
  // katalogda marka yok → vitrinde bölüm çizilmez
  expect(container.querySelector("[data-testid=brands-carousel]")).toBeNull();
  unmount();
  const d = require("./defaults.json");
  expect(d.carousel.per_view).toEqual({ 0: 1, 480: 1, 768: 2, 992: 3, 1200: 5 });
  expect(d.carousel).toMatchObject({ arrows: "outer", dots: false, rewind: true, autoplay: false, pause_on_hover: true, drag: false });
  expect(d._section.margin_bottom.desktop).toBe(85);
});

test("elle logolar: gri ton, ad katmanı, yalnız adı olan marka yazı olarak, data-pd-field", async () => {
  const { container, unmount } = await renderBlock("brands_carousel", { source: "manual", brands: logos });
  const root = container.querySelector("[data-testid=brands-carousel]");
  expect(root.className).toContain("pd-brands--v1");
  expect(root.className).toContain("pd-brands--gray");
  expect(root.className).toContain("pd-brands--names");
  expect(container.querySelectorAll(".pd-brands__item").length).toBe(3);
  expect(container.querySelector('[data-pd-field="brands.0.logo"] img').getAttribute("src")).toContain("b1.png");
  expect(container.querySelector('[data-pd-field="brands.0.name"]').textContent).toBe("Liftmax");
  expect(container.querySelector('[data-pd-field="brands.2.name"]').className).toContain("pd-brands__word");
  expect(container.querySelector('a[href="/arama?q=Liftmax"]')).not.toBeNull();
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Markalar");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("ayarlar: gri ton kapalı, ad kapalı, saydamlık, yükseklik, v2 görünüm", async () => {
  let r = await renderBlock("brands_carousel", { source: "manual", brands: logos, grayscale: false, show_name_overlay: false, logo_opacity: 80, item_height: 70 });
  const root = r.container.querySelector("[data-testid=brands-carousel]");
  expect(root.className).not.toContain("pd-brands--gray");
  expect(r.container.querySelector(".pd-brands__name")).toBeNull();
  expect(root.style.getPropertyValue("--pd-brands-op")).toBe("0.8");
  expect(root.style.getPropertyValue("--pd-brands-h")).toBe("70px");
  r.unmount();
  r = await renderBlock("brands_carousel", { _variant: "v2", source: "manual", brands: logos });
  expect(r.container.querySelectorAll("a.link-hover__brand, div.link-hover__brand").length).toBe(3);
  expect(r.container.querySelector(".py-2.border-top.border-bottom")).not.toBeNull();
  r.unmount();
});

test("katalog kaynağı: /page-blocks/brands logoları data-pd-data ile; önizlemede boşken yer tutucu", async () => {
  global.fetch = jest.fn((url) => Promise.resolve({ ok: true, json: () => Promise.resolve(String(url).includes("/page-blocks/brands")
    ? { items: [{ name: "Bosch", logo: "/api/uploads/bosch.png", url: "/arama?q=Bosch" }, { name: "Launch", logo: "", url: "/arama?q=Launch" }] } : { results: [] }) }));
  let r = await renderBlock("brands_carousel", { catalog_limit: 1 });
  expect(r.container.querySelectorAll(".pd-brands__item").length).toBe(1);
  expect(r.container.querySelector("img[data-pd-data]").getAttribute("alt")).toBe("Bosch");
  expect(hardcodedTexts(r.container)).toEqual([]);
  r.unmount();
  clearCatalogBrands();
  mockFetch([]);
  r = await renderBlock("brands_carousel", { source: "manual", brands: [] }, { preview: true });
  expect(r.container.querySelectorAll("[data-pd-placeholder]").length).toBe(5);
  r.unmount();
});
