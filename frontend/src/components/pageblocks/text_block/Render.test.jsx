import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("başlık + zengin metin + hizalama + genişlik + düğme", async () => {
  const { container, unmount } = await renderBlock("text_block", {
    title: "Hakkımızda", body: "<strong>Garajtek</strong> atölye ekipmanları", align: "center", max_width: 700,
    link: { kind: "url", url: "/hakkimizda" }, button_text: "Devamı",
  });
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Hakkımızda");
  const body = container.querySelector('[data-pd-field="body"]');
  expect(body.innerHTML).toContain("<strong>Garajtek</strong>");
  expect(body.parentElement.style.maxWidth).toBe("700px");
  expect(body.parentElement.className).toContain("text-center");
  expect(container.querySelector('[data-pd-field="button_text"]').getAttribute("href")).toBe("/hakkimizda");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("boş → çizilmez; zararlı HTML temizlenir", async () => {
  let r = await renderBlock("text_block", {});
  expect(r.container.innerHTML).toBe("");
  r.unmount();
  r = await renderBlock("text_block", { body: 'ok<script>alert(1)</script><img src=x onerror="alert(1)">' });
  expect(r.container.querySelector("script")).toBeNull();
  expect(r.container.innerHTML).not.toContain("onerror");
  r.unmount();
});
