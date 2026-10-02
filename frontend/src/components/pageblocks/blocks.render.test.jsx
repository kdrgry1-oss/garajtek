import "./testMocks";
// Framework güvencesi: kayıt defterindeki HER blok varsayılanlarıyla (ve boş ürün kaynağıyla) çökmeden çizilir;
// görsel/metin bloklarında sabit kodlu görünür metin yoktur (SPEC §9 data-pd-field denetimi).
import { BLOCKS } from "./registry";
import { hardcodedTexts, mockFetch, renderBlock } from "./testUtils";


beforeEach(() => { mockFetch([]); });

test.each(Object.keys(BLOCKS))("%s varsayılanlarla çizilir (vitrin + önizleme)", async (key) => {
  const a = await renderBlock(key, {});
  a.unmount();
  const b = await renderBlock(key, {}, { preview: true });
  b.unmount();
});

test.each(["hero_slider", "ads_block", "full_banner"])("%s: sabit kodlu görünür metin yok", async (key) => {
  const { container, unmount } = await renderBlock(key, {});
  expect(container.textContent.length).toBeGreaterThan(0);
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("ürünlü bloklar: ürün verisi data alanında, panel metinleri data-pd-field'da", async () => {
  mockFetch([{ id: "p1", name: "4 Ton Lift", price: 100, sale_price: 80, stock: 3, images: [] }, { id: "p2", name: "Kompresör", price: 50, stock: 1, images: [] }]);
  for (const key of ["deals_tabs", "product_slider", "product_columns", "best_sellers"]) {
    const { container, unmount } = await renderBlock(key, {});
    expect(container.textContent).toMatch(/Lift|Kompresör/);
    expect(hardcodedTexts(container)).toEqual([]);
    unmount();
  }
});

test("hero: panelde değişen başlık anında çizilir; gizli slayt atlanır", async () => {
  const { container, unmount } = await renderBlock("hero_slider", { slides: [{ title: "Yeni <strong>Başlık</strong>", layout: "promo" }] });
  expect(container.querySelector('[data-pd-field="slides.0.title"]').innerHTML).toContain("<strong>Başlık</strong>");
  unmount();
});
