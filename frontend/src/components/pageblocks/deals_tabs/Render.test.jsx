import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = [
  { id: "p1", name: "4 Ton Lift", price: 100, sale_price: 80, stock: 3, images: [] },
  { id: "p2", name: "Kompresör", price: 50, stock: 1, images: [] },
  { id: "p3", name: "Balans Makinesi", price: 70, stock: 4, images: [] },
];

describe("deals_tabs", () => {
  test("v1 varsayılan: özel teklif (koyu kazanç kutusu, stok, geri sayım) + sekmeler; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_tabs", {});
    expect(container.querySelector(".pdb-onsale")).not.toBeNull();
    expect(container.querySelector('[data-pd-field="deal.title"]').textContent).toBe("Özel Teklif");
    expect(container.querySelector(".pdb-savings").textContent).toContain("Kazancınız");
    expect(container.querySelector(".pdb-savings__amount").textContent).toMatch(/20,00/);
    expect(container.querySelector('[data-pd-field="deal.stock.sold_label"]').textContent).toBe("Satılan:");
    expect(container.querySelector('[data-pd-field="deal.countdown.heading"]')).not.toBeNull();
    expect([...container.querySelectorAll(".pdb-tabs-v1 a")].map((a) => a.textContent)).toEqual(["Öne Çıkanlar", "İndirimdekiler", "Çok Satanlar"]);
    expect(container.querySelectorAll(".pdb-cols > .product-item").length).toBe(3);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("elle kazanç/stok, gizli öğeler, sekme değişimi", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_tabs", {
      deal: { savings: { mode: "manual", amount: "₺1.500" }, stock: { mode: "manual", sold: 10, available: 30 }, title: "Haftanın Ürünü" },
      tabs: [{ label: "A", source: { kind: "featured", limit: 2 } }, { label: "B", source: { kind: "newest", limit: 6 } }],
    });
    expect(container.querySelector(".pdb-savings__amount").textContent).toBe("₺1.500");
    expect(container.querySelector(".pdb-progress__sold strong").textContent).toBe("10");
    expect(container.querySelector(".pdb-progress__bar").style.width).toBe("25%");
    expect(container.querySelectorAll(".pdb-cols > .product-item").length).toBe(2);
    const b = container.querySelectorAll(".pdb-tabs-v1 a")[1];
    await act(async () => { b.click(); await new Promise((r) => setTimeout(r, 0)); });
    expect(b.className).toContain("active");
    expect(container.querySelectorAll(".pdb-cols > .product-item").length).toBe(3);
    unmount();
  });

  test("ürün yoksa: özel teklif çizilmez, boş sekme yazısı panelden", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("deals_tabs", {});
    expect(container.querySelector(".pdb-onsale")).toBeNull();
    expect(container.querySelector('[data-pd-field="empty_text"]').textContent).toBe("Bu sekmede henüz ürün yok.");
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("v2 ve discount_tabs varyantları", async () => {
    mockFetch(P);
    let r = await renderBlock("deals_tabs", { _variant: "v2" });
    expect(r.container.querySelector(".min-width-370")).not.toBeNull();
    expect(r.container.querySelector(".nav-classic")).not.toBeNull();
    expect(hardcodedTexts(r.container)).toEqual([]);
    r.unmount();
    r = await renderBlock("deals_tabs", { _variant: "discount_tabs" });
    expect(r.container.querySelector('[data-pd-field="header_title"]').textContent).toBe("Günün Fırsatlarını Yakalayın!");
    expect(r.container.querySelectorAll(".nav-tab-pill a").length).toBe(4);
    expect(r.container.querySelector('[data-pd-field="header_link.label"]')).not.toBeNull();
    expect(hardcodedTexts(r.container)).toEqual([]);
    r.unmount();
  });

  test("geri sayım bitince bloğu gizle", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("deals_tabs", { deal: { countdown: { end: "2020-01-01T00:00", on_expire: "hide_block" } } });
    expect(container.querySelector(".pdb-onsale")).toBeNull();
    unmount();
  });
});
