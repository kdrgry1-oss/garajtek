import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: iki 690×150 yer tutucu, bağlantılar, sabit metin yok", async () => {
  const { container, unmount } = await renderBlock("banner_two_columns", {});
  expect(container.querySelectorAll('[data-pd-field^="items."][data-pd-placeholder]').length).toBe(2);
  expect(container.textContent).toContain("690 × 150");
  expect([...container.querySelectorAll("a")].map((a) => a.getAttribute("href"))).toEqual(["/liftler", "/kompresorler"]);
  expect(container.querySelector(".col-md-6")).not.toBeNull();
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("ayarlar: boşluk, kırılım, köşe, görsel alt metni", async () => {
  const { container, unmount } = await renderBlock("banner_two_columns", {
    gap: 10, stack_below: "lg", radius: 8,
    items: [{ image: { url: "/api/uploads/x.jpg" }, alt: "Lift", link: { kind: "url", url: "/a" } }, { image: { url: "/api/uploads/y.jpg" }, alt: "K", link: { kind: "url", url: "/b" } }],
  });
  const col = container.querySelector(".col-lg-6");
  expect(col.style.paddingLeft).toBe("5px");
  expect(container.querySelector("a").style.borderRadius).toBe("8px");
  expect(container.querySelector('[data-pd-field="items.0.image"] img').getAttribute("alt")).toBe("Lift");
  unmount();
});

test("boş → çizilmez", async () => {
  const { container, unmount } = await renderBlock("banner_two_columns", { items: [] });
  expect(container.innerHTML).toBe("");
  unmount();
});
