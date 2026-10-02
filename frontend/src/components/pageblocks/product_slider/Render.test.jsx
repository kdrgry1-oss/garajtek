import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";
import { bpOf, perViewAt } from "./viewport";

const P = Array.from({ length: 8 }, (_, i) => ({ id: `p${i}`, name: `Ürün ${i}`, price: 100 + i, stock: 2, images: [] }));

describe("product_slider", () => {
  test("varsayılan: Yeni Eklenenler başlığı, başlıkta oklar, tüm ürünler slayt; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_slider", {});
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Yeni Eklenenler");
    expect(container.querySelector('[data-testid="header-arrows"]')).not.toBeNull();
    expect(container.querySelectorAll(".js-slide .product-item").length).toBe(8);
    expect(container.querySelector(".pcs-badge-off")).not.toBeNull();
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("son görünen kartın ayırıcısı gizli (last-active), kapatılınca yok", async () => {
    mockFetch(P);
    const a = await renderBlock("product_slider", {});
    // jsdom 1024 px → 992 kırılımı → 3 ürün görünür → 3. kart last-active
    const slides = a.container.querySelectorAll(".js-slide > .products-group");
    expect(slides[2].classList.contains("pc-last-active")).toBe(true);
    expect(a.container.querySelectorAll(".pc-last-active").length).toBe(1);
    a.unmount();
    mockFetch(P);
    const b = await renderBlock("product_slider", { carousel: { last_active_divider: false } });
    expect(b.container.querySelectorAll(".pc-last-active").length).toBe(0);
    b.unmount();
  });

  test("oklar başlıkta değilse başlık sağı boş; rozet açılabilir; kart tipi uygulanır", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_slider", { carousel: { arrows: "side" }, show_discount_badge: true, header: { title: "Trend Ürünler" } });
    expect(container.querySelector('[data-testid="header-arrows"]')).toBeNull();
    expect(container.querySelector(".pcs-badge-on")).not.toBeNull();
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Trend Ürünler");
    unmount();
  });

  test("boş kaynak: vitrinde hiçbir şey, önizlemede not", async () => {
    mockFetch([]);
    const a = await renderBlock("product_slider", {});
    expect(a.container.textContent).toBe("");
    a.unmount();
    mockFetch([]);
    const b = await renderBlock("product_slider", {}, { preview: true });
    expect(b.container.querySelector('[data-testid="pc-empty"]')).not.toBeNull();
    b.unmount();
  });

  test("per_view kırılımları (Owl min-width) Bootstrap kırılımlarına eşlenir", () => {
    const pv = { 0: 1, 480: 2, 768: 2, 992: 3, 1200: 6, 1480: 6 };
    expect(bpOf(390)).toBe(0);
    expect(perViewAt(pv, 390)).toBe(1);
    expect(perViewAt(pv, 600)).toBe(2);
    expect(perViewAt(pv, 1000)).toBe(3);
    expect(perViewAt(pv, 1440)).toBe(6);
  });
});
