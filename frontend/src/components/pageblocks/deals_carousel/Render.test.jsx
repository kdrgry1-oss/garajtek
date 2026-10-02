import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = [
  { id: "p1", name: "4 Ton Lift", price: 100, sale_price: 80, stock: 3, images: ["/static/1.jpg", "/static/2.jpg", "/static/3.jpg"] },
  { id: "p2", name: "Kompresör", price: 50, sale_price: 45, stock: 1, images: ["/static/4.jpg"] },
];

describe("deals_carousel", () => {
  test("galeri varsayılan: 2 otomatik fırsat, önceki/sonraki yazıları, kazanç/stok/geri sayım; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_carousel", {});
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Haftanın Fırsatları");
    expect(container.querySelectorAll('[data-testid^="dow-slide-"]').length).toBe(2);
    expect(container.querySelector('[data-pd-field="prev_label"]').textContent).toBe("Önceki Fırsat");
    expect(container.querySelector('[data-pd-field="deals.0.savings.label"]').textContent).toBe("Kazancınız");
    expect(container.querySelector('[data-pd-field="deals.1.stock.sold_label"]')).not.toBeNull();
    expect(container.querySelectorAll('[data-testid="dow-slide-0"] .pdb-dow__thumbs button').length).toBe(3);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("tek fırsat: gezinme bağlantıları gizli; elle görsel alanı", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_carousel", { deals: [{ main_image: { url: "/static/x.jpg" }, title_override: "<strong>Süper</strong> Fırsat" }] });
    expect(container.querySelector(".pdb-dow__nav")).toBeNull();
    expect(container.querySelector('[data-pd-field="deals.0.main_image"]')).not.toBeNull();
    expect(container.querySelector('[data-pd-field="deals.0.title_override"]').innerHTML).toContain("<strong>Süper</strong>");
    unmount();
  });

  test("kartlar varyantı: başlıkta geri sayım + bağlantı, kart karuseli", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_carousel", { _variant: "cards" });
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Günün Fırsatları");
    expect(container.querySelector('[data-pd-field="header_countdown.heading"]').textContent).toBe("Bitimine:");
    expect(container.querySelector('[data-pd-field="header.link.label"]')).not.toBeNull();
    expect(container.querySelectorAll(".js-slide .product-item").length).toBe(2);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("ürün yoksa hiçbir şey çizilmez", async () => {
    mockFetch([]);
    const a = await renderBlock("deals_carousel", {});
    expect(a.container.textContent).toBe("");
    a.unmount();
    const b = await renderBlock("deals_carousel", { _variant: "cards" });
    expect(b.container.textContent).toBe("");
    b.unmount();
  });
});
