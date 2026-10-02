import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: 4 başlık + metin, 2'li ızgara", async () => {
  const { container, unmount } = await renderBlock("text_columns", {});
  expect(container.querySelectorAll(".col-lg-6").length).toBe(4);
  expect(container.querySelector('[data-pd-field="items.0.title"]').textContent).toBe("Ne yapıyoruz?");
  expect(container.querySelector('[data-pd-field="items.3.title"]').textContent).toBe("Bizimle çalışın");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("3 sütun, 7/12 genişlik, renk", async () => {
  const r = await renderBlock("text_columns", { columns: "3", width: "wide", title_color: "#ff0000" });
  expect(r.container.querySelector(".col-lg-7 .col-lg-4")).not.toBeNull();
  expect(r.container.querySelector('[data-pd-field="items.0.title"]').style.color).toBe("rgb(255, 0, 0)");
  r.unmount();
});
