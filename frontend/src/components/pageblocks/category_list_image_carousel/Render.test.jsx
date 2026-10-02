import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: başlık + oklar, 2 slayt, gruplar / orta liste / 840×370 görsel", async () => {
  const { container, unmount } = await renderBlock("category_list_image_carousel", {});
  expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Lift ve Kaldırma Sistemleri");
  expect(container.querySelector("[data-testid=header-arrows]")).not.toBeNull();
  expect(container.querySelectorAll(".pd-clic__slide").length).toBe(2);
  expect(container.querySelector('[data-pd-field="slides.0.groups.0.title"]').textContent).toBe("Araç Liftleri");
  expect(container.querySelectorAll('[data-pd-field^="slides.0.groups.0.links."]').length).toBe(7);
  expect(container.querySelectorAll('[data-pd-field^="slides.0.links."]').length).toBe(7);
  expect(container.querySelector('[data-pd-field="slides.0.image"]')).not.toBeNull();
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("renk ayarları + boş durum", async () => {
  let r = await renderBlock("category_list_image_carousel", { box_background: "#eeeeee", radius: 0 });
  expect(r.container.querySelector(".pd-clic").style.getPropertyValue("--pd-clic-box")).toBe("#eeeeee");
  expect(r.container.querySelector(".pd-clic").style.getPropertyValue("--pd-clic-r")).toBe("0px");
  r.unmount();
  r = await renderBlock("category_list_image_carousel", { slides: [] });
  expect(r.container.textContent).toBe("");
  r.unmount();
});
