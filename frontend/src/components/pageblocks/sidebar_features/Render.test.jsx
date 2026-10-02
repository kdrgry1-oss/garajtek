import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: çerçeveli dikey liste, 5 avantaj, son öğe çizgisiz", async () => {
  const { container, unmount } = await renderBlock("sidebar_features", {});
  const items = container.querySelectorAll(".media.px-3");
  expect(items.length).toBe(5);
  expect(items[0].className).toContain("border-bottom");
  expect(items[4].className).not.toContain("border-bottom");
  expect(container.querySelector(".rounded.border")).not.toBeNull();
  expect(container.querySelector('[data-pd-field="items.1.icon"]').style.fontSize).toBe("56px");
  expect(container.querySelector('[data-pd-field="items.0.strong_text"]').textContent).toBe("Ücretsiz Kargo");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("çerçevesiz, ikon rengi", async () => {
  const r = await renderBlock("sidebar_features", { border: false, icon_color: "#ff0000" });
  expect(r.container.querySelector(".rounded.border")).toBeNull();
  expect(r.container.querySelector(".u-avatar").style.color).toBe("rgb(255, 0, 0)");
  r.unmount();
});

test("left_sidebar sayfa düzeninde kenar çubuğu sütununa, diğer bloklar ana sütuna yerleşir", async () => {
  const { act } = require("react");
  const { createRoot } = require("react-dom/client");
  const PageRenderer = require("../_shared/PageRenderer").default;
  const { PageCtx } = require("../_shared/PageCtx");
  const container = document.createElement("div");
  container.className = "electro";
  document.body.appendChild(container);
  const root = createRoot(container);
  const blocks = [
    { id: "a", type: "sidebar_features", is_active: true, settings: {} },
    { id: "b", type: "popular_search_tags", is_active: true, settings: {} },
    { id: "c", type: "sidebar_image_ad", is_active: true, settings: { image: { url: "/api/uploads/a.jpg" } } },
  ];
  await act(async () => { root.render(<PageCtx.Provider value={{ preview: false }}><PageRenderer layout="left_sidebar" blocks={blocks} /></PageCtx.Provider>); });
  const side = container.querySelector("[data-testid=pd-sidebar]");
  expect(side.querySelector("[data-block-type=sidebar_features]")).not.toBeNull();
  expect(side.querySelector("[data-block-type=sidebar_image_ad]")).not.toBeNull();
  expect(side.querySelector("[data-block-type=popular_search_tags]")).toBeNull();
  expect(container.querySelector(".col-xl-9 [data-block-type=popular_search_tags]")).not.toBeNull();
  act(() => root.unmount());
});
