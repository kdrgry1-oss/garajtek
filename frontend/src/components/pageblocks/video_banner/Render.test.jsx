import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("video ayarları: otomatik/sessiz/döngü + oran + metinler", async () => {
  const { container, unmount } = await renderBlock("video_banner", {
    video: { url: "/api/uploads/v.mp4" }, aspect: "21_9", loop: false, title: "Atölye turu", text: "Kısa video",
    button: { text: "İzle", link: { kind: "url", url: "/v" } },
  });
  const v = container.querySelector("video");
  expect(v.muted).toBe(true);
  expect(v.loop).toBe(false);
  expect(v.parentElement.style.aspectRatio).toBe("21 / 9");
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Atölye turu");
  expect(container.querySelector('[data-pd-field="button.text"]').getAttribute("href")).toBe("/v");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("otomatik oynatma kapalıysa kapak + oynat düğmesi", async () => {
  const { container, unmount } = await renderBlock("video_banner", { video: { url: "/api/uploads/v.mp4" }, poster: { url: "/api/uploads/p.jpg" }, autoplay: false });
  expect(container.querySelector("video")).toBeNull();
  expect(container.querySelector('button[aria-label="Videoyu oynat"]')).not.toBeNull();
  unmount();
});

test("boş: vitrinde yok, önizlemede yer tutucu", async () => {
  let r = await renderBlock("video_banner", {});
  expect(r.container.innerHTML).toBe("");
  r.unmount();
  r = await renderBlock("video_banner", {}, { preview: true });
  expect(r.container.querySelector('[data-pd-field="poster"][data-pd-placeholder]')).not.toBeNull();
  r.unmount();
});
