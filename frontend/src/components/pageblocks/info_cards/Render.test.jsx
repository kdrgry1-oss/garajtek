import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: 3 kart (500×300 yer tutucu + başlık + metin)", async () => {
  const { container, unmount } = await renderBlock("info_cards", {});
  expect(container.querySelectorAll(".col-md-4 .card").length).toBe(3);
  expect(container.querySelector('[data-pd-field="items.0.title"]').textContent).toBe("Ne yapıyoruz?");
  expect(container.querySelector('[data-pd-field="items.0.image"]').textContent).toBe("500 × 300");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("2 sütun, sola hizalı, boş durum", async () => {
  let r = await renderBlock("info_cards", { columns: "2", align: "left" });
  expect(r.container.querySelectorAll(".col-md-6 .card.text-left").length).toBe(3);
  r.unmount();
  r = await renderBlock("info_cards", { items: [] });
  expect(r.container.textContent).toBe("");
  r.unmount();
});
