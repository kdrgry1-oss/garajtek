import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = [{ id: "p1", name: "4 Ton Lift", price: 100, stock: 3, images: [] }, { id: "p2", name: "Kompresör", price: 50, stock: 1, images: [] }];
beforeEach(() => { mockFetch(P); });

test("varsayılan: 6 sekme, ilki etkin; tıklayınca içerik değişir; ürün karuseli", async () => {
  const { container, unmount } = await renderBlock("hero_tabs", {});
  const tabs = container.querySelectorAll('[role="tab"]');
  expect(tabs.length).toBe(6);
  expect(container.querySelector('[data-pd-field="tabs.0.title"] .d-block').textContent).toBe("LİFTLER");
  expect(container.querySelector('[data-pd-field="tabs.0.offer_label"]').textContent).toBe("SON FIRSAT");
  expect(container.querySelector('[data-pd-field="tabs.0.amount_suffix"]').textContent).toBe("İNDİRİM!");
  await act(async () => { tabs[2].click(); });
  expect(container.querySelector('[data-testid="hero-tab-pane-2"]')).not.toBeNull();
  expect(container.querySelector('[data-pd-field="tabs.2.amount"]').textContent).toBe("₺3.000");
  expect(container.textContent).toContain("4 Ton Lift");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("ayarlar: varsayılan sekme, başlık boyutu, ürünler kapalı", async () => {
  const { container, unmount } = await renderBlock("hero_tabs", { default_tab: 1, title_size: 40, products: { enabled: false } });
  expect(container.querySelector('[data-testid="hero-tab-pane-1"]')).not.toBeNull();
  expect(container.querySelector('[data-pd-field="tabs.1.title"]').style.fontSize).toBe("40px");
  expect(container.textContent).not.toContain("4 Ton Lift");
  unmount();
});

test("boş ürün kaynağı → karusel gizli; tek sekmede sekme listesi yok", async () => {
  mockFetch([]);
  const { container, unmount } = await renderBlock("hero_tabs", { tabs: [{ label: "A", title: "B" }] });
  expect(container.querySelector('[role="tab"]')).toBeNull();
  expect(container.querySelector(".pd-htabs__products")).toBeNull();
  unmount();
});
