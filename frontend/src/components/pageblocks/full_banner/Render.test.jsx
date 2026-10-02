import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("v1 görsel: 1170×207 yer tutucu + bağlantı", async () => {
  const { container, unmount } = await renderBlock("full_banner", {});
  const ph = container.querySelector('[data-pd-field="image"][data-pd-placeholder]');
  expect(ph).not.toBeNull();
  expect(ph.textContent).toContain("1170 × 207");
  expect(container.querySelector("a").getAttribute("href")).toBe("/sale");
  unmount();
});

test("görsel ve bağlantı ayarları", async () => {
  const { container, unmount } = await renderBlock("full_banner", {
    image: { url: "/api/uploads/b.jpg", alt: "Kampanya", w: 1170, h: 300 }, link: { kind: "category", url: "/liftler", slug: "liftler" },
  });
  const img = container.querySelector('[data-pd-field="image"] img');
  expect(img.getAttribute("alt")).toBe("Kampanya");
  expect(img.style.aspectRatio).toBe("1170 / 300");
  expect(container.querySelector("a").getAttribute("href")).toBe("/liftler");
  unmount();
});

test("text_overlay: başlık + fiyat kutusu, sabit metin yok", async () => {
  const { container, unmount } = await renderBlock("full_banner", { _variant: "text_overlay", price_box_color: "#00ff00" });
  expect(container.querySelector('[data-pd-field="title"]').innerHTML).toContain("<strong>YENİLEYİN</strong>");
  expect(container.querySelector('[data-pd-field="price"]').textContent).toBe("₺7.999");
  expect(container.querySelector('[data-pd-field="price_label"]').parentElement.style.backgroundColor).toBe("rgb(0, 255, 0)");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});
