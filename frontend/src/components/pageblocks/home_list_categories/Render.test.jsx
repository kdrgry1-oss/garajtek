import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: v1 başlık + ana kategoriden otomatik kart (katalog verisi data-pd-data)", async () => {
  const { container, unmount } = await renderBlock("home_list_categories", {});
  expect(container.querySelector('[data-pd-field="header.title"]').textContent).toBe("Bu Ayın Popüler Kategorileri");
  expect(container.querySelectorAll(".pd-hlc__cat").length).toBe(1);
  expect(container.querySelector(".pd-hlc__heading a").getAttribute("href")).toBe("/liftler");
  expect(container.querySelector(".pd-hlc__heading [data-pd-data]").textContent).toBe("Liftler");
  expect(container.querySelector('[data-pd-field="see_all_text"]').textContent).toBe("Tümünü gör");
  expect(container.querySelector(".pd-hlc").className).toContain("pd-hlc--c3");
  expect(container.querySelector("[data-pd-placeholder]")).not.toBeNull();
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("elle kartlar: ad/görsel/alt bağlantı/tümünü gör özel, 4 sütun, v2", async () => {
  const st = { source: "manual", columns: "4", categories: [
    { category: "c1", name_override: "Liftler & Kaldırma", image_override: { url: "/api/uploads/l.png" }, sub_mode: "manual",
      sub_links: [{ label: "Makaslı", link: { kind: "url", url: "/makasli" } }], see_all_text: "Hepsi" },
  ] };
  let r = await renderBlock("home_list_categories", st);
  expect(r.container.querySelector('[data-pd-field="categories.0.name_override"]').textContent).toBe("Liftler & Kaldırma");
  expect(r.container.querySelector('[data-pd-field="categories.0.image_override"] img')).not.toBeNull();
  expect(r.container.querySelector('[data-pd-field="categories.0.sub_links.0.label"]').getAttribute("href")).toBe("/makasli");
  expect(r.container.querySelector('[data-pd-field="categories.0.see_all_text"]').textContent).toBe("Hepsi");
  expect(r.container.querySelector(".pd-hlc").className).toContain("pd-hlc--c4");
  expect(hardcodedTexts(r.container)).toEqual([]);
  r.unmount();
  r = await renderBlock("home_list_categories", { ...st, _variant: "v2", show_see_all: false });
  expect(r.container.querySelector(".pd-hlc--v2 .col-6.col-md-4.col-xl-3")).not.toBeNull();
  expect(r.container.querySelector('[data-pd-field="categories.0.see_all_text"]')).toBeNull();
  r.unmount();
});

test("boş durum: kategori yoksa vitrinde çizilmez, önizlemede uyarı", async () => {
  let r = await renderBlock("home_list_categories", { source: "manual", categories: [] });
  expect(r.container.textContent).toBe("");
  r.unmount();
  r = await renderBlock("home_list_categories", { source: "manual", categories: [] }, { preview: true });
  expect(r.container.querySelector("[data-empty]")).not.toBeNull();
  r.unmount();
});
