import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 14 }, (_, i) => ({ id: `p${i}`, name: `Ürün ${i}`, price: 10 + i, stock: 1, images: [] }));

describe("product_grid", () => {
  test("varsayılan: başlık + 'Tüm önerileri gör', 6/4/2 sütun, sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_grid", {});
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Size Özel Öneriler");
    expect(container.querySelector('[data-pd-field="header.link.label"]').getAttribute("href")).toBe("/tum-urunler");
    const ul = container.querySelector(".pdb-cols");
    expect(ul.style.getPropertyValue("--pdb-cd")).toBe("6");
    expect(ul.style.getPropertyValue("--pdb-cm")).toBe("2");
    expect(ul.querySelectorAll(".product-item").length).toBe(14);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("sayfalama ve 'Daha Fazla Göster'", async () => {
    mockFetch(P);
    let r = await renderBlock("product_grid", { pagination: true, page_size: 5 });
    expect(r.container.querySelectorAll(".page-link").length).toBe(3);
    expect(r.container.querySelectorAll(".pdb-cols .product-item").length).toBe(5);
    await act(async () => { r.container.querySelectorAll(".page-link")[2].click(); });
    expect(r.container.querySelectorAll(".pdb-cols .product-item").length).toBe(4);
    r.unmount();
    r = await renderBlock("product_grid", { show_more_button: { enabled: true, initial: 6, step: 6 } });
    expect(r.container.querySelectorAll(".pdb-cols .product-item").length).toBe(6);
    const btn = r.container.querySelector('[data-pd-field="show_more_button.text"]');
    expect(btn.textContent).toBe("Daha Fazla Göster");
    await act(async () => { btn.click(); });
    expect(r.container.querySelectorAll(".pdb-cols .product-item").length).toBe(12);
    expect(hardcodedTexts(r.container)).toEqual([]);
    r.unmount();
  });

  test("son bakılanlar varyantı: yalnız görsel kart; ürün yoksa gizli", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("product_grid", { _variant: "recently_viewed" });
    expect(container.textContent).toBe("");
    unmount();
  });
});
