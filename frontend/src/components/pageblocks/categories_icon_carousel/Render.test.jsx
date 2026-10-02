import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan v8: ana renk bant, 12 ikon, şablon kırılımları", async () => {
  const { container, unmount } = await renderBlock("categories_icon_carousel", {});
  expect(container.querySelector(".bg-primary.border-color-8 .container")).not.toBeNull();
  expect(container.querySelectorAll(".pd-cicar__item").length).toBe(12);
  expect(container.querySelector('[data-pd-field="items.0.icon"]').className).toContain("fa-car");
  expect(container.querySelector('[data-pd-field="items.0.label"]').textContent).toBe("Araç Liftleri");
  const d = require("./defaults.json");
  expect(d.carousel.per_view).toEqual({ 0: 2, 554: 3, 768: 5, 992: 6, 1200: 10 });
  expect(d.carousel).toMatchObject({ arrows: "side", dots: "mobile", rewind: false });
  const v6 = require("./schema.json").variants.find((v) => v.value === "v6").defaults_patch;
  expect(v6.carousel.per_view).toEqual({ 0: 2, 554: 3, 768: 5, 992: 6, 1200: 8, 1600: 10 });
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("v6 kutulu görünüm, renkler, yüklenen ikon görseli", async () => {
  const r = await renderBlock("categories_icon_carousel", { _variant: "v6", band_color: "#ff0000", icon_size: 50,
    items: [{ icon: { image: { url: "/api/uploads/i.png" } }, label: "Lift", link: { kind: "url", url: "/lift" } }] });
  expect(r.container.querySelector(".bg-on-hover .rounded-circle-top")).not.toBeNull();
  expect(r.container.querySelector('[data-pd-field="items.0.icon"] img')).not.toBeNull();
  expect(r.container.querySelector(".pd-cicar").style.getPropertyValue("--pd-cicar-isz")).toBe("50px");
  r.unmount();
});

test("noktalar: “Yalnız mobil” 1200 px altı (d-xl-none), “Göster” her genişlikte", async () => {
  let r = await renderBlock("categories_icon_carousel", {});
  const ul = r.container.querySelector("ul.js-pagination");
  if (ul) { expect(ul.className).toContain("d-xl-none"); expect(ul.className).toContain("pd-cicar__dots-lg"); }
  r.unmount();
  r = await renderBlock("categories_icon_carousel", { carousel: { ...require("./defaults.json").carousel, dots: true } });
  const ul2 = r.container.querySelector("ul.js-pagination");
  if (ul2) expect(ul2.className).not.toContain("d-xl-none");
  r.unmount();
});
