import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";
import { itemClass, pageLayout } from "./Render";

const P = Array.from({ length: 12 }, (_, i) => ({ id: `p${i}`, name: `Lift ${i}`, price: 1000 + i, stock: 2, images: [] }));

describe("best_sellers", () => {
  test("varsayılan: başlık + İlk 20 + otomatik kategori hapı, 3×2 sayfalar, sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("best_sellers", {});
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Çok Satanlar");
    expect(container.querySelector('[data-pd-field="header.pills.0.label"]').textContent).toBe("İlk 20");
    expect(container.querySelector('[data-pd-field="header.pills.1.label"]').textContent).toBe("Liftler");
    const pages = container.querySelectorAll("ul.products-group");
    expect(pages.length).toBe(2); // jsdom 1024 px: 3 sütun × 2 satır = 6
    expect(pages[0].querySelectorAll("li.product-item").length).toBe(6);
    expect(pages[1].querySelectorAll("li.product-item").length).toBe(6);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("hap sekme gibi: tıklanınca kategori kaynağı istenir", async () => {
    const f = mockFetch(P);
    const { container, unmount } = await renderBlock("best_sellers", {});
    await act(async () => { container.querySelector('[data-pd-field="header.pills.1.label"]').click(); });
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
    const bodies = f.mock.calls.map((c) => JSON.parse(c[1].body)).flatMap((b) => b.sources);
    expect(bodies.some((s) => s.kind === "category" && s.category_ids[0] === "c1")).toBe(true);
    expect(container.querySelector('[data-pd-field="header.pills.1.label"]').className).toContain("btn-outline-primary");
    unmount();
  });

  test("başlıkta oklar (sağ taraf: oklar + karusel okları başlıkta)", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("best_sellers", { header: { title: "Çok Satanlar", right: "arrows", pills: [] }, carousel: { arrows: "header" } });
    expect(container.querySelector('[data-testid="header-arrows"] button[aria-label="Sonraki"]')).toBeTruthy();
    expect(container.querySelectorAll('[data-pd-field="header.title"]').length).toBe(1);
    unmount();
    const r2 = await renderBlock("best_sellers", { header: { title: "Çok Satanlar", right: "arrows", pills: [] }, carousel: { arrows: "none" } });
    expect(r2.container.querySelector('[data-testid="header-arrows"]')).toBeFalsy();
    r2.unmount();
  });

  test("sayfa düzeni: mobil / tablet / geniş ekran", () => {
    const st = { columns: "3", columns_wide: "4", rows_per_slide: 2, mobile_per_slide: 3 };
    expect(pageLayout(st, 390).perPage).toBe(3);
    expect(pageLayout(st, 1440).perPage).toBe(6);
    expect(pageLayout(st, 1600).perPage).toBe(8);
    expect(pageLayout({ ...st, rows_per_slide: 1, columns: "4" }, 1000).perPage).toBe(4);
  });

  test("otomatik haplar kapalı + ızgara kartı", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("best_sellers", { pills_auto_categories: { enabled: false }, card: "grid" });
    expect(container.querySelector('[data-pd-field="header.pills.1.label"]')).toBeNull();
    expect(container.querySelectorAll("li.product-item").length).toBe(12);
    unmount();
  });

  test("kart sınıfları şablonla aynı (col-wd-3 col-md-4, remove-divider-xl/wd, mobil alt çizgi)", () => {
    const c = Array.from({ length: 6 }, (_, i) => itemClass(i, 6, 3, 4, false));
    expect(c[0]).toBe("col-md-4 col-wd-3 border-bottom border-md-bottom-0");
    expect(c[2]).toContain("remove-divider-xl");
    expect(c[3]).toContain("remove-divider-wd");
    expect(c[5]).not.toContain("border-bottom");
    expect(itemClass(0, 4, 4, 6, true)).toContain("col-6 col-md-3 col-wd-2");
  });

  test("boş kaynak: vitrinde gizli", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("best_sellers", {});
    expect(container.textContent).toBe("");
    unmount();
  });
});
