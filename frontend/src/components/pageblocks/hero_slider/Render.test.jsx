import "../testMocks";
import { act } from "react";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([{ id: "p1", name: "4 Ton Lift", price: 1000, sale_price: 800, stock: 27, images: [] }]); });

test("varsayılanlar: 3 slayt, şablon katmanları ve data-pd-field", async () => {
  const { container, unmount } = await renderBlock("hero_slider", {});
  expect(container.querySelectorAll('[data-testid^="hero-slide-"]').length).toBe(3);
  const t = container.querySelector('[data-pd-field="slides.0.title"]');
  expect(t.className).toContain("pd-hero__title--1");
  expect(t.innerHTML).toContain("<br>");
  expect(container.querySelector('[data-pd-field="slides.0.subtitle"]').textContent).toBe("PROFESYONEL SERVİSLER İÇİN");
  expect(container.querySelector('[data-pd-field="slides.0.price"]').textContent).toBe("₺49.900");
  expect(container.querySelector('[data-pd-field="slides.0.price_prefix"]').textContent).toBe("başlayan fiyatlarla");
  expect(container.querySelector('[data-pd-field="slides.1.pretitle"]').textContent).toBe("ATÖLYENİZE DEĞER KATIN");
  expect(container.querySelector('[data-pd-field="slides.1.title"]').className).toContain("pd-hero__title--2");
  expect(container.querySelector('[data-pd-field="slides.0.button.text"]').getAttribute("href")).toBe("/liftler");
  // görsel yoksa şablon ölçüsünde yer tutucu (SPEC §3)
  expect(container.querySelector('[data-pd-field="slides.0.background"][data-pd-placeholder]')).not.toBeNull();
  // noktalar
  expect(container.querySelectorAll(".pd-hero__dots li").length).toBe(3);
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("katman animasyonları: etkin slaytta fadeInDown 500/700/1000/1000 ms, 800 ms, easeOutCubic", async () => {
  const { container, unmount } = await renderBlock("hero_slider", {});
  const s0 = container.querySelector('[data-testid="hero-slide-0"]');
  const layers = [...s0.querySelectorAll(".pd-hero-layer")];
  expect(layers.map((l) => l.style.animationDelay)).toEqual(["500ms", "700ms", "1000ms", "1000ms"]);
  layers.forEach((l) => {
    expect(l.className).toContain("pd-hero-anim-fadeInDown");
    expect(l.style.animationDuration).toBe("800ms");
    expect(l.style.animationTimingFunction).toContain("cubic-bezier(0.215, 0.61, 0.355, 1)");
  });
  // etkin olmayan slaytta animasyon sınıfı yok
  expect(container.querySelector('[data-testid="hero-slide-1"] .pd-hero-layer')).toBeNull();
  unmount();
});

test("ayarlar: yükseklik, açıklama sütunu, mobil ölçek, düzen ve renkler", async () => {
  const { container, unmount } = await renderBlock("hero_slider", {
    height: { desktop: 520, tablet: 410, mobile: 280 }, caption_column: "wide8", mobile_font_scale: 80,
    slides: [{ layout: "promo", pretitle: "ÜST", title: "Başlık", text_color: "#ff0000", accent_color: "#00ff00", text_align: "center",
      button: { text: "Al", style: "dark", link: { kind: "url", url: "/x" } } }],
  });
  const root = container.querySelector(".pd-hero");
  expect(root.style.getPropertyValue("--pd-hero-h-d")).toBe("520px");
  expect(root.style.getPropertyValue("--pd-hero-h-m")).toBe("280px");
  expect(root.style.getPropertyValue("--pd-hero-fs-m")).toBe("11.20px");
  expect(container.querySelector(".pd-hero__col").className).toContain("col-lg-8");
  expect(container.querySelector(".pd-hero__slide").style.color).toBe("rgb(255, 0, 0)");
  expect(container.querySelector('[data-pd-field="slides.0.pretitle"]').style.color).toBe("rgb(0, 255, 0)");
  expect(container.querySelector(".pd-hero__caption").className).toContain("text-center");
  expect(container.querySelector(".pd-hero__btn").className).toContain("pd-hero__btn--dark");
  expect(container.querySelector(".pd-hero__dots")).toBeNull(); // tek slayt → nokta yok
  unmount();
});

test("yalnız görsel slayt tamamen tıklanır; düğme yazısı boşsa da bağlantı korunur", async () => {
  const { container, unmount } = await renderBlock("hero_slider", {
    slides: [{ layout: "image_only", background: { url: "/api/uploads/a.jpg", alt: "Kampanya" }, button: { text: "", link: { kind: "url", url: "/sale" } } }],
  });
  expect(container.querySelector(".pd-hero__caption")).toBeNull();
  expect(container.querySelector(".pd-hero__hit").getAttribute("href")).toBe("/sale");
  expect(container.querySelector('[data-pd-field="slides.0.background"] img').getAttribute("alt")).toBe("Kampanya");
  unmount();
});

test("varyant boxed_side_banners: yan bannerlar; rounded_with_deals: fırsat kartı + geri sayım", async () => {
  let r = await renderBlock("hero_slider", { _variant: "boxed_side_banners" });
  expect(r.container.querySelector(".pd-hero--boxed .container")).not.toBeNull();
  expect(r.container.querySelectorAll('[data-pd-field$=".cta"]').length).toBe(3);
  expect(hardcodedTexts(r.container)).toEqual([]);
  r.unmount();
  r = await renderBlock("hero_slider", { _variant: "rounded_with_deals" });
  await act(async () => { await new Promise((x) => setTimeout(x, 10)); });
  expect(r.container.textContent).toContain("4 Ton Lift");
  expect(r.container.querySelector('[data-pd-field="side_deals.countdown.heading"]').textContent).toBe("Bitimine:");
  expect(r.container.querySelector('[data-pd-field="side_deals.left_label"]').textContent).toBe("kaldı");
  expect(r.container.querySelector(".pd-hero").style.getPropertyValue("--pd-hero-radius")).toBe("15px");
  expect(hardcodedTexts(r.container)).toEqual([]);
  r.unmount();
  r = await renderBlock("hero_slider", { _variant: "menu_strip" });
  expect(r.container.querySelectorAll('[data-pd-field^="category_strip."][data-pd-field$=".label"]').length).toBe(5);
  r.unmount();
});

test("boş slayt listesi → hiçbir şey çizilmez", async () => {
  const { container, unmount } = await renderBlock("hero_slider", { slides: [] });
  expect(container.querySelector(".pd-hero")).toBeNull();
  unmount();
});

test("v2_product: T2 index sınıfları (font-size-64 / d-block font-size-55, sup'lu fiyat, col-xl-5 ürün görseli)", async () => {
  const { container, unmount } = await renderBlock("hero_slider", {
    _variant: "v2_product", caption_column: "offset3_4",
    slides: [{ layout: "price", title: "THE NEW <br>STANDARD", subtitle: "UNDER", price_prefix: "FROM", price: "$749,99",
      product_image: { url: "/api/upload/files/p.png", alt: "" }, button: { text: "Start", link: { kind: "url", url: "/sale" } } }],
  });
  const t = container.querySelector('[data-pd-field="slides.0.title"]');
  expect(t.className).toContain("font-size-64");
  expect(t.querySelector(".d-block.font-size-55").textContent).toBe("STANDARD");
  const price = container.querySelector('[data-pd-field="slides.0.price"]');
  expect(price.innerHTML).toBe("<sup>$</sup>749<sup>99</sup>");
  expect(container.querySelector(".offset-xl-3.col-xl-4.col-6")).not.toBeNull();
  expect(container.querySelector(".col-xl-5.col-6 img")).not.toBeNull();
  expect(container.querySelector('[data-pd-field="slides.0.button.text"]').className).toContain("rounded-lg");
  unmount();
});
