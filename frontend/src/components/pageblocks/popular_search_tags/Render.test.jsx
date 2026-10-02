import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: başlık + 10 arama etiketi (btn-soft-secondary)", async () => {
  const { container, unmount } = await renderBlock("popular_search_tags", {});
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Popüler Aramalar");
  const tags = container.querySelectorAll("a.btn");
  expect(tags.length).toBe(10);
  expect(tags[0].className).toContain("btn-soft-secondary");
  expect(tags[0].getAttribute("href")).toBe("/arama?q=Lift");
  expect([...tags].map((t) => t.textContent)).toContain("Far ayar");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("bağlantısız etiket metinle arar; görünüm ayarları; boş başlık", async () => {
  const r = await renderBlock("popular_search_tags", { title: "", style: "primary", rounded_pill: true, tags: [{ label: "Kriko", link: { kind: "none", url: "" } }] });
  const a = r.container.querySelector("a.btn");
  expect(a.getAttribute("href")).toBe("/arama?q=Kriko");
  expect(a.className).toContain("btn-primary");
  expect(a.className).toContain("rounded-pill");
  expect(r.container.querySelector('[data-pd-field="title"]')).toBeNull();
  r.unmount();
});
