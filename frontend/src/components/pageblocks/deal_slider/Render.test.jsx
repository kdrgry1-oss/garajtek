import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

const P = [{ id: "p1", name: "4 Ton Lift", price: 1000, sale_price: 800, stock: 6, sold_count: 28, images: [] },
  { id: "p2", name: "Kompresör", price: 500, sale_price: 400, stock: 2, images: [] }];
beforeEach(() => { mockFetch(P); });

test("thumbs: 5 slayt, yedek kaynaktan ürünler, geri sayım (saat/dk/sn), stok, alt sekmeler", async () => {
  const { container, unmount } = await renderBlock("deal_slider", {});
  expect(container.querySelectorAll('[data-testid^="deal-slide-"]').length).toBe(5);
  const s0 = container.querySelector('[data-testid="deal-slide-0"]');
  expect(s0.querySelector('[data-pd-field="slides.0.kicker"]').textContent).toBe("SINIRLI");
  expect(s0.querySelector('[data-pd-field="slides.0.title"]').textContent).toBe("HAFTANIN FIRSATI");
  expect(s0.textContent).toContain("4 Ton Lift");
  expect(container.querySelector('[data-testid="deal-slide-1"]').textContent).toContain("Kompresör");
  expect([...s0.querySelectorAll('[data-pd-field^="slides.0.countdown.labels."]')].map((x) => x.textContent)).toEqual(["SAAT", "DK", "SN"]);
  expect(s0.querySelector('[data-pd-field="slides.0.stock.available_label"]').textContent).toBe("Kalan:");
  const thumbs = container.querySelectorAll(".pd-deal__thumbs button");
  expect(thumbs.length).toBe(5);
  await act(async () => { thumbs[3].click(); });
  expect(container.querySelector('[data-testid="deal-slide-3"]').parentElement.className).toContain("is-active");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("primary_band: ana renk bant + düğme ürün sayfasına gider", async () => {
  const { container, unmount } = await renderBlock("deal_slider", { _variant: "primary_band", slides: [{ button: { text: "Hemen Al", link: { kind: "none" } } }] });
  expect(container.querySelector(".pd-deal--band")).not.toBeNull();
  expect(container.querySelector('[data-pd-field="slides.0.button.text"]').textContent).toBe("Hemen Al");
  expect(container.querySelector(".pd-deal__thumbs")).toBeNull();
  unmount();
});

test("ürün yoksa görsel yer tutucu, ürün bilgisi gizli", async () => {
  mockFetch([]);
  const { container, unmount } = await renderBlock("deal_slider", { slides: [{ title: "X" }] });
  expect(container.querySelector('[data-pd-field="slides.0.image_override"][data-pd-placeholder]')).not.toBeNull();
  expect(container.querySelector(".prodcut-price")).toBeNull();
  unmount();
});
