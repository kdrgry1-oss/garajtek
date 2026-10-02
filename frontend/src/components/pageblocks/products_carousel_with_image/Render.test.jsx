import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 7 }, (_, i) => ({ id: `p${i}`, name: `Balans ${i}`, price: 900 + i, stock: 2, images: [] }));

describe("products_carousel_with_image", () => {
  test("varsayılan: 665×616 yan görsel yer tutucu, başlık + oklar, 7 ürün; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("products_carousel_with_image", {});
    expect(container.querySelector('[data-pd-field="side_image"]').textContent).toContain("665 × 616");
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Lastik ve Balans Ekipmanları");
    expect(container.querySelector('[data-testid="header-arrows"]')).not.toBeNull();
    expect(container.querySelectorAll(".js-slide .product-item").length).toBe(7);
    expect(container.querySelector(".pcwi__bg")).toBeNull();
    expect(container.querySelector(".pd-carousel").style.getPropertyValue("--el-gutter")).toBe("30px");
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("arka plan görseli + sağda görsel", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("products_carousel_with_image", {
      background_image: { url: "/static/bg.jpg", focal: { x: 0.2, y: 0.8 } }, side_image: { url: "/static/tv.png" }, image_position: "right" });
    const bg = container.querySelector('[data-pd-field="background_image"]');
    expect(bg.style.backgroundImage).toContain("bg.jpg");
    expect(bg.style.backgroundPosition).toBe("20% 80%");
    expect(container.querySelector(".row").className).toContain("flex-md-row-reverse");
    expect(container.querySelector('[data-pd-field="side_image"] img').getAttribute("src")).toContain("tv.png");
    unmount();
  });

  test("boş kaynak: vitrinde gizli", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("products_carousel_with_image", {});
    expect(container.textContent).toBe("");
    unmount();
  });
});
