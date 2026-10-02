import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan v4: başlık + 10 döndürülmüş kart, 5/3/1 sütun, gri bant", async () => {
  const { container, unmount } = await renderBlock("category_icon_cards", {});
  const root = container.querySelector("[data-testid=category-icon-cards]");
  expect(container.querySelectorAll(".pd-cic__col").length).toBe(10);
  expect(root.style.getPropertyValue("--pd-cic-d")).toBe("5");
  expect(root.style.getPropertyValue("--pd-cic-rot")).toBe("15deg");
  expect(container.querySelector('[data-pd-field="tiles.0.label"]').textContent).toBe("Araç Liftleri");
  expect(container.querySelector('[data-pd-field="tiles.0.label"]').tagName).toBe("H6");
  expect(container.querySelector(".shadow-on-hover")).not.toBeNull();
  expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Bu Haftanın Popüler Kategorileri");
  expect(require("./defaults.json")._section.background).toBe("#f9f9f9");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("v5 / v8 varyantları ve ayarlar", async () => {
  let r = await renderBlock("category_icon_cards", { _variant: "v5", header: { title: "" }, tiles: [{ label: "Lift", image: { url: "/api/uploads/a.png" }, link: { kind: "url", url: "/lift" } }], rotation: 0 });
  expect(r.container.querySelector('[data-pd-field="tiles.0.label"]').tagName).toBe("H4");
  expect(r.container.querySelector('[data-pd-field="header.title"]')).toBeNull();
  expect(r.container.querySelector('a[href="/lift"]')).not.toBeNull();
  r.unmount();
  r = await renderBlock("category_icon_cards", { _variant: "v8" });
  expect(r.container.querySelector(".pd-cic__lead")).not.toBeNull();
  expect(r.container.querySelector('[data-pd-field="lead_banner.label"]').textContent).toBe("Araç Liftleri");
  expect(hardcodedTexts(r.container)).toEqual([]);
  r.unmount();
});

test("boş durum", async () => {
  const r = await renderBlock("category_icon_cards", { tiles: [] });
  expect(r.container.textContent).toBe("");
  r.unmount();
});
