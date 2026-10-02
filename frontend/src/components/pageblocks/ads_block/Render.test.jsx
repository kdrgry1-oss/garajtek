import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan v1: 3 kutu, %60/%40, bağlantı / %'ye varan / bağlantı", async () => {
  const { container, unmount } = await renderBlock("ads_block", {});
  expect(container.querySelectorAll(".pd-ads__col").length).toBe(3);
  expect(container.querySelector(".pd-ads__col").className).toContain("col-md-4");
  expect(container.querySelector(".pd-ads__left").style.width).toBe("60%");
  expect(container.querySelector(".pd-ads__body").style.width).toBe("40%");
  expect(container.querySelector('[data-pd-field="items.0.text"]').innerHTML).toContain("<strong>BÜYÜK</strong>");
  expect(container.querySelector('[data-pd-field="items.0.action_text"]').textContent).toBe("Hemen İncele");
  expect(container.querySelector('[data-pd-field="items.1.action_prefix"]').textContent).toBe("%'ye varan");
  expect(container.querySelector('[data-pd-field="items.1.action_value"]').textContent).toBe("20");
  expect(container.querySelector('[data-testid="ad-2"]').getAttribute("href")).toBe("/liftler");
  expect(container.querySelectorAll("[data-pd-placeholder]").length).toBe(3);
  expect(container.querySelector(".pd-ads").style.getPropertyValue("--pd-ads-fs")).toBe("1.286em");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("başlayan fiyat + para birimi + kuruş; ayarlar CSS değişkenine iner", async () => {
  const { container, unmount } = await renderBlock("ads_block", {
    columns: "2", ratio: "62_38", text_size: 1.571, card_background: "#eeeeee", arrow_color: "#ff0000",
    items: [{ text: "A", action_type: "from_price", action_prefix: "başlayan", action_value: "749", action_suffix: ",99", currency: "₺", link: { kind: "url", url: "/a" } }],
  });
  expect(container.querySelector(".pd-ads__col").className).toContain("col-md-6");
  expect(container.querySelector(".pd-ads__left").style.width).toBe("62%");
  expect(container.querySelector('[data-pd-field="items.0.currency"]').textContent).toBe("₺");
  expect(container.querySelector('[data-pd-field="items.0.action_suffix"]').textContent).toBe(",99");
  const st = container.querySelector(".pd-ads").style;
  expect(st.getPropertyValue("--pd-ads-bg")).toBe("#eeeeee");
  expect(st.getPropertyValue("--pd-ads-arrow")).toBe("#ff0000");
  unmount();
});

test("v2.0 kart varyantları", async () => {
  let r = await renderBlock("ads_block", { _variant: "v2_cards" });
  expect(r.container.querySelectorAll(".pd-ads__card").length).toBe(4);
  expect(r.container.querySelector(".link__icon")).not.toBeNull();
  expect(hardcodedTexts(r.container)).toEqual([]);
  r.unmount();
  r = await renderBlock("ads_block", { _variant: "wide_plus_two" });
  expect(r.container.querySelector(".pd-ads__col").className).toContain("col-xl-6");
  expect(r.container.querySelector('[data-pd-field="items.0.image"]')).not.toBeNull();
  r.unmount();
});

test("boş liste → çizilmez", async () => {
  const { container, unmount } = await renderBlock("ads_block", { items: [] });
  expect(container.querySelector(".pd-ads")).toBeNull();
  unmount();
});
