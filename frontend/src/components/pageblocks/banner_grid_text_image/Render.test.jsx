import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: 2 satır; 1. satır geniş solda, 2. satır geniş sağda ve özellik listeli", async () => {
  const { container, unmount } = await renderBlock("banner_grid_text_image", {});
  const cols = [...container.querySelector(".pd-bgti > .row").children].map((c) => c.className);
  expect(cols).toEqual(["col-lg-8 mb-5", "col-md-6 col-lg-4 mb-5", "col-md-6 col-lg-4 mb-5", "col-lg-8 mb-5"]);
  expect(container.querySelector('[data-pd-field="rows.0.wide.title"]').textContent).toBe("Profesyonel Lastik Sökme Makineleri");
  expect(container.querySelector('[data-pd-field="rows.0.wide.price"]').textContent).toBe("₺24.900");
  expect(container.querySelectorAll('[data-pd-field="rows.1.wide.specs"] li').length).toBe(3);
  expect(container.querySelector('[data-pd-field="rows.1.wide.title"] strong').textContent).toBe("Hidrolik Kriko");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("renk ve boyut ayarları", async () => {
  const { container, unmount } = await renderBlock("banner_grid_text_image", {
    title_size: 20, price_size: 30, rows: [{ wide_side: "left", wide: { background: "#000000", text_color: "#ffffff", title: "A", price: "₺1" }, small: {} }],
  });
  expect(container.querySelector(".pd-bgti").style.getPropertyValue("--pd-bgti-ts")).toBe("20px");
  expect(container.querySelector(".pd-bgti").style.getPropertyValue("--pd-bgti-ps")).toBe("30px");
  expect(container.querySelector(".pd-bgti__wide").parentElement.style.backgroundColor).toBe("rgb(0, 0, 0)");
  unmount();
});
