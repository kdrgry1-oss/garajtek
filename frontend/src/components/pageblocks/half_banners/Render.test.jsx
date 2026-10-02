import "../testMocks";
import { mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });
const items = [{ image: { url: "/api/uploads/a.jpg" }, alt: "A", link: { kind: "url", url: "/a" } }, { image: null, alt: "B", link: { kind: "url", url: "/b" } }];

test("vitrin: görseli olmayan öğe atlanır; önizleme: 570×300 yer tutucu", async () => {
  let r = await renderBlock("half_banners", { items });
  expect(r.container.querySelectorAll("[data-pd-field^='items.']").length).toBe(1);
  expect(r.container.querySelector("a").getAttribute("href")).toBe("/a");
  r.unmount();
  r = await renderBlock("half_banners", { items, gap: 10, radius: 6 }, { preview: true });
  expect(r.container.querySelector('[data-pd-field="items.1.image"][data-pd-placeholder]').textContent).toContain("570 × 300");
  expect(r.container.querySelector(".col-md-6").style.paddingLeft).toBe("5px");
  r.unmount();
});

test("boş → çizilmez", async () => {
  const { container, unmount } = await renderBlock("half_banners", {});
  expect(container.innerHTML).toBe("");
  unmount();
});
