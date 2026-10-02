import "../testMocks";
import { mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("görsel + bağlantı; görsel yokken vitrinde gizli, önizlemede 270×428 yer tutucu", async () => {
  let r = await renderBlock("sidebar_image_ad", { image: { url: "/api/uploads/ad.jpg" }, link: { kind: "url", url: "/kampanya" } });
  expect(r.container.querySelector('a[href="/kampanya"] [data-pd-field="image"] img')).not.toBeNull();
  r.unmount();
  r = await renderBlock("sidebar_image_ad", {});
  expect(r.container.textContent).toBe("");
  r.unmount();
  r = await renderBlock("sidebar_image_ad", {}, { preview: true });
  expect(r.container.querySelector("[data-pd-placeholder]").textContent).toBe("270 × 428");
  r.unmount();
  expect(require("./schema.json").layout).toBe("sidebar");
});
