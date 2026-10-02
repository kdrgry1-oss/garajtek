import "./testMocks";
import {
  BLOCKS, GLOBALS, allFields, applyVariant, defaultHome, defaultSettings, duplicateBlock, instantiate, isModified, listBlocks,
  resetBlock, withDefaults, withGlobalDefaults,
} from "./registry";
import { filterItems, scheduleActive, showIf } from "./_shared/schema";

test("her blok klasörü şema + varsayılan + Render içerir; anahtar klasör adıyla aynı", () => {
  const keys = Object.keys(BLOCKS);
  expect(keys.length).toBeGreaterThanOrEqual(44);
  keys.forEach((k) => {
    expect(BLOCKS[k].schema.key).toBe(k);
    expect(typeof BLOCKS[k].Render).toBe("function");
    expect(BLOCKS[k].defaults).toBeTruthy();
  });
  expect(Object.keys(GLOBALS)).toEqual(expect.arrayContaining(["site_theme", "site_header", "site_topbar", "site_footer_bottom"]));
});

test("varsayılan ana sayfa şablon v1.0 sırasında ve dolu", () => {
  const home = defaultHome();
  expect(home.map((b) => b.type)).toEqual(["hero_slider", "ads_block", "deals_tabs", "product_grid_212", "best_sellers",
    "full_banner", "product_slider", "brands_carousel", "product_columns"]);
  expect(home[0].settings.slides).toHaveLength(3);
  expect(home[0].settings.slides.every((s) => s._id)).toBe(true);
  expect(home[0].settings._section.width).toBe("full_bleed");
  expect(home[3].settings._variant).toBe("2_1_2");
});

test("varyant yaması + ortak gruplar + varsayılandan değişti rozeti + sıfırlama", () => {
  expect(defaultSettings("ads_block", "v2").columns).toBe("2");
  const b = instantiate("ads_block");
  expect(isModified(b)).toBe(false);
  const changed = { ...b, settings: { ...b.settings, card_background: "#000000" } };
  expect(isModified(changed)).toBe(true);
  expect(isModified(resetBlock(changed))).toBe(false);
  const v = applyVariant(changed, "v3");
  expect(v.settings._variant).toBe("v3");
  expect(v.settings.ratio).toBe("62_38");
  expect(v.settings.card_background).toBe("#000000");
});

test("çoğaltma yeni blok ve öğe kimlikleri verir", () => {
  const b = instantiate("hero_slider");
  const c = duplicateBlock(b);
  expect(c.id).not.toBe(b.id);
  expect(c.settings.slides[0]._id).not.toBe(b.settings.slides[0]._id);
  expect(c.settings.slides[0].title).toBe(b.settings.slides[0].title);
});

test("eski öğeler yeni alanları varsayılandan alır; zamanlama öğe düzeyinde süzülür", () => {
  const st = withDefaults("hero_slider", { slides: [{ title: "A", _schedule: { start: "2099-01-01T00:00", end: "" } }, { title: "B" }] });
  expect(st.slides[0].button.style).toBe("primary");
  const f = filterItems(allFields(BLOCKS.hero_slider.schema), st, new Date("2026-01-01T00:00:00Z"));
  expect(f.slides.map((s) => s.title)).toEqual(["B"]);
  expect(scheduleActive({ start: "", end: "2020-01-01T00:00" })).toBe(false);
});

test("show_if: alan, _variant ve $parent", () => {
  expect(showIf({ show_if: { layout: ["price"] } }, { layout: "price" })).toBe(true);
  expect(showIf({ show_if: { layout: ["price"] } }, { layout: "promo" })).toBe(false);
  expect(showIf({ show_if: { _variant: ["text_overlay"] } }, {}, { root: { _variant: "image" } })).toBe(false);
  expect(showIf({ show_if: { "$parent.nav_mode": ["links"] } }, {}, { parent: { nav_mode: "links" } })).toBe(true);
});

test("galeri: hazırlanan (stub) bloklar varsayılan olarak gizli", () => {
  const ready = listBlocks().map((b) => b.key);
  expect(ready).toContain("hero_slider");
  expect(ready).not.toContain("banner_mosaic");
  expect(listBlocks({ includeStubs: true }).map((b) => b.key)).toContain("banner_mosaic");
});

test("global alanlar varsayılanla dolar", () => {
  const g = withGlobalDefaults({ site_theme: { primary_color: "#0787ea" } });
  expect(g.site_theme.primary_color).toBe("#0787ea");
  expect(g.site_theme.card.add_to_cart_text).toBe("Sepete Ekle");
  expect(g.site_header.search.placeholder).toMatch(/ara/i);
});
