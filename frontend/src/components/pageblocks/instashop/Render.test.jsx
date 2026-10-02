import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("başlık + görseller; masaüstü sütun ayarı karusele iner", async () => {
  const { container, unmount } = await renderBlock("instashop", {
    columns: "4", items: [{ image: { url: "/api/uploads/a.jpg" }, alt: "Atölye", link: { kind: "url", url: "/x" } }, { image: null }],
  });
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Atölyemizden");
  expect(container.querySelectorAll('[data-pd-field^="items."]').length).toBe(1);
  expect(container.querySelector(".pd-carousel").style.getPropertyValue("--el-n-xl")).toBe("4");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("görsel yoksa vitrinde gizli, önizlemede kare yer tutucu", async () => {
  let r = await renderBlock("instashop", { items: [{ image: null }] });
  expect(r.container.innerHTML).toBe("");
  r.unmount();
  r = await renderBlock("instashop", { items: [{ image: null }] }, { preview: true });
  expect(r.container.querySelector("[data-pd-placeholder]")).not.toBeNull();
  r.unmount();
});
