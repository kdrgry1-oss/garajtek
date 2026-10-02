import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: 1 büyük (552×325) + 6 küçük (268×155), radius 10", async () => {
  const { container, unmount } = await renderBlock("banner_mosaic", {});
  expect(container.querySelector('[data-pd-field="big.image"]').textContent).toContain("552 × 325");
  expect(container.querySelectorAll('[data-pd-field^="small."]').length).toBe(6);
  expect(container.querySelector(".col-xl-4gdot9")).not.toBeNull();
  expect(container.querySelector("a").style.borderRadius).toBe("10px");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("küçük banner yoksa büyük tam genişlik; 2 sütun ayarı", async () => {
  let r = await renderBlock("banner_mosaic", { small: [] });
  expect(r.container.querySelector(".col-12")).not.toBeNull();
  r.unmount();
  r = await renderBlock("banner_mosaic", { small_columns: "2" });
  expect(r.container.querySelector(".col-xl-7gdot1 .col-6")).not.toBeNull();
  r.unmount();
});
