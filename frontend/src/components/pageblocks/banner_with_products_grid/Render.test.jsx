import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 8 }, (_, i) => ({ id: `p${i}`, name: `Ürün ${i}`, price: 10 + i, stock: 1, images: [`/static/${i}.jpg`] }));

describe("banner_with_products_grid", () => {
  test("varsayılan: başlık + sekme hapları, kategori listesi, 360×616 banner yer tutucusu, 8 ürün; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("banner_with_products_grid", {});
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Lift ve Kaldırma Ekipmanları");
    expect([...container.querySelectorAll(".nav-tab-pill a")].map((a) => a.getAttribute("data-pd-field"))).toEqual(["tabs.0.label", "tabs.1.label", "tabs.2.label", "tabs.3.label"]);
    expect(container.querySelectorAll(".list-group-item").length).toBe(8);
    expect(container.querySelector('[data-pd-placeholder][data-pd-field="banner.image"]')).not.toBeNull();
    expect(container.querySelectorAll(".pdb-cols .product-item").length).toBe(8);
    expect(hardcodedTexts(container)).toEqual([]);
    const second = container.querySelectorAll(".nav-tab-pill a")[1];
    await act(async () => { second.click(); });
    expect(second.className).toContain("active");
    unmount();
  });

  test("menü ve büyük ürün varyantları, sağda yan alan", async () => {
    mockFetch(P);
    let r = await renderBlock("banner_with_products_grid", { _variant: "menu", side_position: "right" });
    expect(r.container.querySelector('[data-pd-field="menu_title"]').textContent).toBe("Ürün Grupları");
    expect(r.container.querySelector(".row.flex-row-reverse")).not.toBeNull();
    expect(hardcodedTexts(r.container)).toEqual([]);
    r.unmount();
    r = await renderBlock("banner_with_products_grid", { _variant: "featured", featured_product: "p3" });
    expect(r.container.querySelector(".pdb-main")).not.toBeNull();
    r.unmount();
  });

  test("tek sekme: hap yok; boş kaynak: panel yazısı", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("banner_with_products_grid", { tabs: [{ label: "Tek", source: { kind: "featured", limit: 8 } }] });
    expect(container.querySelector(".nav-tab-pill")).toBeNull();
    expect(container.querySelector('[data-pd-field="empty_text"]')).not.toBeNull();
    unmount();
  });

  test("başlık sağ tarafı panelden: hap bağlantıları eklenir, 'Tümünü gör' ve 'Hiçbiri' işler", async () => {
    mockFetch(P);
    let r = await renderBlock("banner_with_products_grid", { header: { right: "pills", pills: [{ label: "Kampanyalar", link: { kind: "url", url: "/sale" } }] } });
    const extra = r.container.querySelector('[data-pd-field="header.pills.0.label"]');
    expect(extra.textContent).toBe("Kampanyalar");
    expect(extra.getAttribute("href")).toBe("/sale");
    r.unmount();
    r = await renderBlock("banner_with_products_grid", { header: { right: "link" } });
    expect(r.container.querySelectorAll(".nav-tab-pill a").length).toBe(4);
    expect(r.container.querySelector('[data-pd-field="header.link.label"]')).not.toBeNull();
    r.unmount();
    r = await renderBlock("banner_with_products_grid", { header: { right: "none" } });
    expect(r.container.querySelector(".nav-tab-pill")).toBeNull();
    expect(r.container.querySelectorAll(".pdb-cols .product-item").length).toBe(8);
    r.unmount();
  });
});
