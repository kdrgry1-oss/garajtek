import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 9 }, (_, i) => ({ id: `p${i}`, name: `Ürün ${i}`, price: 100 + i, sale_price: i % 2 ? 90 : 0, stock: 3,
  images: [`/static/a${i}.jpg`, `/static/b${i}.jpg`, `/static/c${i}.jpg`] }));

describe("product_grid_212", () => {
  test("2_1_2 varsayılan: container + nav (sabit + otomatik kategori) + 2/büyük/2; sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_grid_212", {});
    expect(container.querySelector(".container.pdb-212")).not.toBeNull();
    const nav = [...container.querySelectorAll(".pdb-212__nav a")].map((a) => a.textContent);
    expect(nav).toEqual(["En İyi Fırsatlar", "Liftler"]);
    expect(container.querySelector('[data-pd-field="nav_items.0.label"]')).not.toBeNull();
    const sides = container.querySelectorAll(".pdb-212__side");
    expect(sides.length).toBe(2);
    expect(sides[0].querySelectorAll(".product-item").length).toBe(2);
    expect(sides[1].querySelectorAll(".product-item").length).toBe(2);
    expect(container.querySelector(".pdb-212__mid .pdb-main .pdb-main__title").textContent).toBe("Ürün 0");
    expect(container.querySelector(".pdb-main__thumbs")).toBeNull();
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("küçük resimler + büyütme + sekme değişimi", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_grid_212", { main_thumbnails: true, lightbox: true });
    expect(container.querySelectorAll(".pdb-main__tn").length).toBe(3);
    await act(async () => { container.querySelector(".pdb-main__zoom").click(); });
    expect(document.querySelector('[data-testid="pdb-lightbox"]')).not.toBeNull();
    await act(async () => { document.querySelector('[data-testid="pdb-lightbox"]').click(); });
    const second = container.querySelectorAll(".pdb-212__nav a")[1];
    await act(async () => { second.click(); await new Promise((r) => setTimeout(r, 0)); });
    expect(second.className).toContain("active");
    unmount();
  });

  test("bağlantı modu: sekmeler kategori sayfasına gider", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_grid_212", { nav_mode: "links" });
    const links = [...container.querySelectorAll(".pdb-212__nav a")].map((a) => a.getAttribute("href"));
    expect(links).toEqual(["/sale", "/liftler"]);
    unmount();
  });

  test("4_1_4: 4 + büyük + 4, galeri açık", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("product_grid_212", { _variant: "4_1_4" });
    expect(container.querySelector(".products-group-4-1-4")).not.toBeNull();
    expect(container.querySelectorAll(".max-width-xl-100").length).toBe(8);
    expect(container.querySelectorAll(".pdb-main__tn").length).toBe(3);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("boş kaynak: panel yazısı", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("product_grid_212", {});
    expect(container.querySelector('[data-pd-field="empty_text"]')).not.toBeNull();
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });
});
