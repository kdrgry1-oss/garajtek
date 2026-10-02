import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan v1: 5 sütun çerçeveli şerit, ikonlar ve metinler", async () => {
  const { container, unmount } = await renderBlock("features_list", {});
  expect(container.querySelectorAll(".pd-feat__item").length).toBe(5);
  expect(container.querySelector(".pd-feat").className).toContain("pd-feat--border");
  expect(container.querySelector(".pd-feat").style.getPropertyValue("--pd-feat-w")).toBe("20%");
  expect(container.querySelector('[data-pd-field="items.0.icon"]').className).toContain("ec-transport");
  expect(container.querySelector('[data-pd-field="items.1.icon"]').className).toContain("pd-feat__i--lg");
  expect(container.querySelector('[data-pd-field="items.0.strong_text"]').textContent).toBe("Ücretsiz Kargo");
  expect(container.querySelector('[data-pd-field="items.0.text"]').textContent).toBe("2.500 TL üzeri");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("ayarlar: 4 sütun, ikon rengi, çerçevesiz, dikey, v2", async () => {
  let r = await renderBlock("features_list", { columns: "4", icon_color: "#ff0000", border: false });
  expect(r.container.querySelector(".pd-feat").style.getPropertyValue("--pd-feat-w")).toBe("25%");
  expect(r.container.querySelector(".pd-feat").style.getPropertyValue("--pd-feat-icon")).toBe("#ff0000");
  expect(r.container.querySelector(".pd-feat--border")).toBeNull();
  r.unmount();
  r = await renderBlock("features_list", { layout: "vertical" });
  expect(r.container.querySelector(".pd-feat--vertical")).not.toBeNull();
  r.unmount();
  r = await renderBlock("features_list", { _variant: "v2" });
  expect(r.container.querySelectorAll(".media.col").length).toBe(5);
  expect(hardcodedTexts(r.container)).toEqual([]);
  r.unmount();
});

test("yüklenen ikon görseli ve bağlantı", async () => {
  const { container, unmount } = await renderBlock("features_list", {
    items: [{ icon: { image: { url: "/api/uploads/i.png" } }, strong_text: "A", text: "b", link: { kind: "url", url: "/kargo" } }],
  });
  expect(container.querySelector('[data-pd-field="items.0.icon"] img')).not.toBeNull();
  expect(container.querySelector("a.pd-feat__item").getAttribute("href")).toBe("/kargo");
  unmount();
});
