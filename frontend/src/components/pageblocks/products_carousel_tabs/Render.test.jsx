import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 5 }, (_, i) => ({ id: `p${i}`, name: `Kompresör ${i}`, price: 500 + i, stock: 2, images: [] }));

describe("products_carousel_tabs", () => {
  test("ortalı varsayılan: gizli başlık, 3 sekme, ilk sekme etkin, karusel; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("products_carousel_tabs", {});
    expect(container.querySelector("h2.sr-only").textContent).toBe("Ürün Sekmeleri");
    const tabs = container.querySelectorAll(".nav-tab .nav-link");
    expect(tabs.length).toBe(3);
    expect(tabs[0].classList.contains("active")).toBe(true);
    expect(container.querySelector('[data-pd-field="tabs.1.label"]').textContent).toBe("İndirimdekiler");
    expect(container.querySelector(".nav-tab").className).toContain("justify-content-md-center");
    expect(container.querySelectorAll(".js-slide .product-item").length).toBe(5);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("sekme değişince yalnız etkin bölme (karusel yeniden kurulur)", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("products_carousel_tabs", {});
    expect(container.querySelector('[data-testid="pct-pane-0"]')).not.toBeNull();
    await act(async () => { container.querySelectorAll(".nav-tab .nav-link")[2].click(); });
    expect(container.querySelector('[data-testid="pct-pane-0"]')).toBeNull();
    expect(container.querySelector('[data-testid="pct-pane-2"]')).not.toBeNull();
    expect(container.querySelectorAll(".nav-tab .nav-link")[2].classList.contains("active")).toBe(true);
    unmount();
  });

  test("varyantlar: sola yaslı; hap başlık + yan banner yer tutucu + bağlantı", async () => {
    mockFetch(P);
    const a = await renderBlock("products_carousel_tabs", { _variant: "left" });
    expect(a.container.querySelector(".nav-tab").className).toContain("justify-content-start");
    a.unmount();
    mockFetch(P);
    const b = await renderBlock("products_carousel_tabs", { _variant: "pill_header", header: { link: { label: "Tümünü gör", link: { kind: "url", url: "/x" } } } });
    expect(b.container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Atölye Ekipmanları");
    expect(b.container.querySelectorAll(".nav-tab-pill .nav-link").length).toBe(3);
    expect(b.container.querySelector('[data-testid="pct-banner"] [data-pd-placeholder]')).not.toBeNull();
    expect(b.container.querySelector('[data-pd-field="header.link.label"]')).not.toBeNull();
    expect(hardcodedTexts(b.container)).toEqual([]);
    b.unmount();
  });

  test("ızgara gösterimi ve varsayılan sekme", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("products_carousel_tabs", { display: "grid", default_tab: 1 });
    expect(container.querySelector(".pct-grid")).not.toBeNull();
    expect(container.querySelectorAll(".pct-grid > .product-item").length).toBe(5);
    expect(container.querySelectorAll(".nav-tab .nav-link")[1].classList.contains("active")).toBe(true);
    unmount();
  });

  test("hiç ürün yok: vitrinde gizli", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("products_carousel_tabs", {});
    expect(container.textContent).toBe("");
    unmount();
  });
});
