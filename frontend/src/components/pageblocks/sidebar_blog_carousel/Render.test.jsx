import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";
import { listBlocks } from "../registry";

beforeEach(() => { mockFetch([]); });

test("blog modülü yok: galeride gizli; elle girilen yazılar 1'li karuselde", async () => {
  expect(listBlocks().map((b) => b.key)).not.toContain("sidebar_blog_carousel");
  const { container, unmount } = await renderBlock("sidebar_blog_carousel", {});
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Blogdan");
  expect(container.querySelectorAll(".post-item").length).toBe(4);
  expect(container.querySelector('[data-pd-field="posts.0.image"][data-pd-placeholder]')).not.toBeNull();
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("limit ve boş durum", async () => {
  let r = await renderBlock("sidebar_blog_carousel", { limit: 2 });
  expect(r.container.querySelectorAll(".post-item").length).toBe(2);
  r.unmount();
  r = await renderBlock("sidebar_blog_carousel", { posts: [] });
  expect(r.container.textContent).toBe("");
  r.unmount();
});
