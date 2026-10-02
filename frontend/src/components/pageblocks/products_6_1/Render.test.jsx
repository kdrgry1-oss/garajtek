import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = Array.from({ length: 9 }, (_, i) => ({ id: `p${i}`, name: `Ürün ${i}`, price: 100 + i, stock: 2, images: [`/static/a${i}.jpg`, `/static/b${i}.jpg`, `/static/c${i}.jpg`, `/static/d${i}.jpg`] }));

describe("products_6_1", () => {
  test("6+1 varsayılan: başlık + haplar, 6 kart + büyük ürün (367 px, 3 küçük resim); sabit metin yok", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("products_6_1", {});
    expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Çok Satanlar");
    expect(container.querySelectorAll('[data-pd-field^="header.pills."]').length).toBe(4);
    expect(container.querySelectorAll(".pdb-61__grid > li").length).toBe(6);
    expect(container.querySelector(".pdb-main__title").textContent).toBe("Ürün 0");
    expect(container.querySelector(".pdb-main__fixed").style.height).toBe("367px");
    expect(container.querySelectorAll(".pdb-main__tn").length).toBe(3);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });

  test("8+1 varyantı, elle büyük ürün, küçük resim 0", async () => {
    mockFetch(P);
    const { container, unmount } = await renderBlock("products_6_1", { _variant: "8_1", count: "8", thumbnails: 0, main_image_height: 300 });
    expect(container.querySelector(".pdb-61--8")).not.toBeNull();
    expect(container.querySelectorAll(".pdb-61__grid > li").length).toBe(8);
    expect(container.querySelector(".pdb-main__thumbs")).toBeNull();
    expect(container.querySelector(".pdb-main__fixed").style.height).toBe("300px");
    unmount();
  });

  test("sekme hap kendi kaynağına geçer", async () => {
    const f = mockFetch(P);
    const { container, unmount } = await renderBlock("products_6_1", { header: { pills: [
      { label: "İlk 7", as_tab: true, active: true, link: { kind: "none", url: "" } },
      { label: "Yeni", as_tab: true, link: { kind: "none", url: "" }, source: { kind: "newest", limit: 7 } }] } });
    const pill = container.querySelector('[data-pd-field="header.pills.1.label"]');
    await act(async () => { pill.click(); });
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
    const bodies = f.mock.calls.map((c) => c[1]?.body || "").join(" ");
    expect(bodies).toContain("newest");
    unmount();
  });

  test("boş kaynak: panel yazısı", async () => {
    mockFetch([]);
    const { container, unmount } = await renderBlock("products_6_1", {});
    expect(container.querySelector('[data-pd-field="empty_text"]').textContent).toBe("Henüz çok satan ürün yok.");
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  });
});
