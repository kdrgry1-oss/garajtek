import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = [{ id: "p1", name: "4 Ton Lift", price: 100, sale_price: 80, stock: 3, images: [] }, { id: "p2", name: "Kompresör", price: 50, sale_price: 40, stock: 1, images: [] }];

describe("deals_week_limited", () => {
  test("v4 varsayılan: başlık, % simgesi, saat/dk/sn geri sayım, gri bant, kart karuseli; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_week_limited", {});
    expect(container.querySelector('[data-pd-field="left.title"]').innerHTML).toContain("<strong>Sınırlı</strong>");
    expect(container.querySelector('[data-pd-field="left.big_symbol"]').textContent).toBe("%");
    expect(container.querySelectorAll('[data-testid="deal-countdown"] .min-width-46').length).toBe(3);
    expect(container.querySelector(".pdb-wdl").style.backgroundColor).toBe("rgb(245, 245, 245)");
    expect(container.querySelectorAll(".js-slide .product-item").length).toBe(2);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("v11: teklif + düğme, simge yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_week_limited", { _variant: "v11" });
    expect(container.querySelector('[data-pd-field="left.offer.value"]').textContent).toBe("70");
    expect(container.querySelector('[data-pd-field="left.offer.sub"]').textContent).toBe("İNDİRİM!");
    expect(container.querySelector('[data-pd-field="left.button.text"]').getAttribute("href")).toBe("/sale");
    expect(container.querySelector('[data-pd-field="left.big_symbol"]')).toBeNull();
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("ürün yoksa gizli; 'boşken göster' açıkken sol bölüm görünür", async () => {
    mockFetch([]);
    const a = await renderBlock("deals_week_limited", {});
    expect(a.container.textContent).toBe("");
    a.unmount();
    const b = await renderBlock("deals_week_limited", { show_when_empty: true });
    expect(b.container.querySelector('[data-pd-field="left.title"]')).not.toBeNull();
    b.unmount();
  });
});
