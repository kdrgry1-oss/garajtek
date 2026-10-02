import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: Hakkımızda başlığı, açıklama, 564 px en az yükseklik, ortalı", async () => {
  const { container, unmount } = await renderBlock("page_hero", {});
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Hakkımızda");
  expect(container.querySelector('[data-pd-field="text"]').textContent).toMatch(/atölyenizin/);
  const root = container.querySelector("[data-testid=page-hero]");
  expect(root.style.getPropertyValue("--pd-ph-h-d")).toBe("564px");
  expect(container.querySelector(".pd-ph__inner--center")).not.toBeNull();
  expect(hardcodedTexts(container)).toEqual([]);
  expect(require("./schema.json").allowed_pages).toEqual(["*"]);
  unmount();
});

test("görsel, hizalama, renkler", async () => {
  const r = await renderBlock("page_hero", { background: { url: "/api/uploads/h.jpg" }, align: "left", title_color: "#ffffff", min_height: { desktop: 400, tablet: 300, mobile: 200 } });
  expect(r.container.querySelector('[data-pd-field="background"] img')).not.toBeNull();
  expect(r.container.querySelector(".pd-ph__inner--left")).not.toBeNull();
  expect(r.container.querySelector(".pd-ph__title").style.color).toBe("rgb(255, 255, 255)");
  expect(r.container.querySelector("[data-testid=page-hero]").style.getPropertyValue("--pd-ph-h-m")).toBe("200px");
  r.unmount();
});
