// Sayfa Tasarımı — Grup C blokları uçtan uca (SPEC §7 / §9): best_sellers, product_slider, products_carousel_tabs,
// products_carousel_with_image, product_columns.
//
//   BASE=http://localhost:<statik> API=http://localhost:<backend>/api TOKEN=<admin jwt> \
//   [TPL=http://localhost:<şablon kökü; 1.0/HTML ve 2.0/html altında>] [OUT=/tmp/grpc-shots] node e2e/pageblocks/group_c.e2e.js
//
// Doğrulananlar (gerçek backend + production build, demo içerik yüklü veritabanı):
//   a) Panel API'siyle (taslak → yayın) girilen her metin/görsel vitrinde ilgili data-pd-field düğümünde çıkar
//   b) Her blok varyantı vitrinde kendi şablon işaretleyicisiyle çizilir
//   c) Davranışlar: Çok Satanlar hapı sekme gibi ürünleri değiştirir; sekmeli karuselde gizli sekme görünür olunca
//      karusel doğru genişlikte ölçülür; başlık okları kaydırır ve “last-active” ayırıcısı güncellenir; ayarlar
//      (kırılım başına adet, satır × sütun, boşluk) vitrinde uygulanır; Alt Ürün Sütunları varken footer bandı gizlidir
//   d) Panel editörü: alan yazılınca iframe önizleme anında güncellenir, vitrin yayından önce değişmez; Yayınla → vitrin
//   e) Önizleme == vitrin (blok ekran görüntüleri bayt-eşit)
//   f) Sabit kodlu görünür metin yok, yatay taşma yok (1440 + 390)
//   g) Şablon ölçüleri (TPL verilirse, 1440 ve 390)
// Sonunda başlangıç revizyonu geri yüklenip yayınlanır.
const assert = require("assert");
const fs = require("fs");
const { chromium } = require(process.env.PW_MODULE || "/opt/node22/lib/node_modules/playwright");

const BASE = process.env.BASE;
const API = process.env.API || `${BASE}/api`;
const TOKEN = process.env.TOKEN;
const TPL = process.env.TPL || "";
const OUT = process.env.OUT || "";
if (!BASE || !TOKEN) { console.error("BASE ve TOKEN gerekli"); process.exit(2); }
if (OUT) fs.mkdirSync(OUT, { recursive: true });
const H = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };
const api = async (method, path, body, extra = {}) => {
  const r = await fetch(`${API}${path}`, { method, headers: { ...H, ...extra }, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text();
  return { status: r.status, data: t ? JSON.parse(t) : null };
};
let failures = 0;
async function step(name, fn) {
  try { await fn(); console.log(`✓ ${name}`); } catch (e) { failures += 1; console.log(`✕ ${name}\n   ${e && e.stack ? e.stack.split("\n").slice(0, 4).join("\n   ") : e}`); }
}
let n = 0;
const blk = (type, variant, settings = {}) => ({ id: `e2e-c-${type}-${variant || "def"}-${(n += 1)}`, type, title: `${type} ${variant}`, is_active: true,
  settings: { ...(variant ? { _variant: variant } : {}), _reveal: { enabled: false }, ...settings } });

async function publishLayout(blocks) {
  const cur = await api("GET", "/page-design/home");
  const rev = cur.data.draft ? cur.data.draft.rev : undefined;
  const put = await api("PUT", "/page-design/home/draft", { blocks }, rev !== undefined ? { "If-Match": String(rev) } : {});
  assert.strictEqual(put.status, 200, `taslak: ${JSON.stringify(put.data).slice(0, 300)}`);
  assert.deepStrictEqual(put.data.errors, [], "doğrulama hatası olmamalı");
  const pub = await api("POST", "/page-design/home/publish");
  assert.strictEqual(pub.status, 200, `yayın: ${JSON.stringify(pub.data).slice(0, 300)}`);
}
const textAt = (p, sel, path) => p.$eval(`${sel} [data-pd-field="${path}"]`, (e) => e.textContent.replace(/\s+/g, " ").trim()).catch(() => null);
const sfPage = async (ctx, w = 1440) => {
  const p = await ctx.newPage();
  await p.setViewportSize({ width: w, height: 900 });
  await p.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
  await p.waitForTimeout(1500);
  return p;
};

const VARIANTS = [
  ["best_sellers", "v1", "ul.products-group > li.product-item__card"], ["best_sellers", "v2_grid", "ul.products-group > li.product-item:not(.product-item__card)"],
  ["product_slider", "v1", ".pcs .js-slide .product-item"], ["product_slider", "v2_wide", ".pcs"], ["product_slider", "category", ".pcs .js-slide .product-item"],
  ["products_carousel_tabs", "centered", ".pct--centered .nav-tab.justify-content-md-center"], ["products_carousel_tabs", "left", ".pct--left .nav-tab.justify-content-start"],
  ["products_carousel_tabs", "pill_header", ".pct--pill .nav-tab-pill [data-pd-field='tabs.0.label']"],
  ["products_carousel_with_image", "v1", ".pcwi .pcwi__image [data-pd-field='side_image']"], ["products_carousel_with_image", "v2_cards", ".pcwi .product-item__card"],
  ["product_columns", "", ".product-item__list"],
];

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem("store_cookie_consent", JSON.stringify({ necessary: true, analytics: false, marketing: false, ts: new Date().toISOString(), v: 1 }));
      if (location.pathname.startsWith("/admin") || location.pathname.startsWith("/onizleme")) localStorage.setItem("token", t);
      else localStorage.removeItem("token");
    } catch (e) { /* yoksay */ }
  }, TOKEN);
  await api("DELETE", "/page-design/home/draft");
  const start = await api("GET", "/page-design/home");
  const startRev = start.data.published.rev;
  const hero = start.data.published.blocks.find((b) => b.type === "hero_slider");
  const top = hero ? [{ ...hero, id: "e2e-c-hero" }] : [];
  const banners = (await (await fetch(`${API}/banners`)).json().catch(() => [])) || [];
  const IMG = (banners.find((b) => b.image) || {}).image || "";
  const cats = (await (await fetch(`${API}/categories`)).json().catch(() => [])) || [];
  const cat = (Array.isArray(cats) ? cats : cats.items || []).find((c) => !c.parent_id) || {};

  await step("a) panelden girilen metin/görseller vitrinde (data-pd-field)", async () => {
    const custom = [
      blk("best_sellers", "", { header: { title: "Atölyenin Çok Satanları", pills: [{ label: "İlk 12", as_tab: true, active: true, link: { kind: "none", url: "" } }] },
        pills_auto_categories: { enabled: true, max: 2 } }),
      blk("product_slider", "", { header: { title: "Yeni Gelen Ekipmanlar" } }),
      blk("products_carousel_tabs", "pill_header", { header: { title: "Servis Ekipmanları", right: "link", link: { label: "Hepsini gör", link: { kind: "url", url: "/tum-urunler" } } },
        tabs: [{ label: "Vitrindekiler", source: { kind: "featured", limit: 7 } }, { label: "Kampanyalı", source: { kind: "discounted", limit: 7 } }],
        side_banner: { enabled: true, image: IMG ? { url: IMG, alt: "Yan banner" } : null } }),
      blk("products_carousel_with_image", "", { header: { title: "Balans Makineleri" }, background_image: IMG ? { url: IMG } : null, side_image: IMG ? { url: IMG } : null,
        source: { kind: cat.id ? "category" : "newest", category_ids: cat.id ? [String(cat.id)] : [], limit: 7, fill_with: "newest" } }),
      blk("product_columns", "", { columns: [{ title: "Vitrin Ürünleri", source: { kind: "featured", limit: 3 } }, { title: "Kampanyadakiler", source: { kind: "discounted", limit: 3 } },
        { title: "Yeni Gelenler", source: { kind: "newest", limit: 2 } }] }),
    ];
    await publishLayout([...top, ...custom]);
    const p = await sfPage(ctx);
    const S = (t) => `[data-block-type="${t}"]`;
    const expect = [
      ["best_sellers", "header.title", "Atölyenin Çok Satanları"], ["best_sellers", "header.pills.0.label", "İlk 12"],
      ["product_slider", "header.title", "Yeni Gelen Ekipmanlar"],
      ["products_carousel_tabs", "header.title", "Servis Ekipmanları"], ["products_carousel_tabs", "header.link.label", "Hepsini gör"],
      ["products_carousel_tabs", "tabs.0.label", "Vitrindekiler"], ["products_carousel_tabs", "tabs.1.label", "Kampanyalı"],
      ["products_carousel_with_image", "header.title", "Balans Makineleri"],
      ["product_columns", "columns.0.title", "Vitrin Ürünleri"], ["product_columns", "columns.2.title", "Yeni Gelenler"],
    ];
    const bad = [];
    for (const [t, path, val] of expect) { const got = await textAt(p, S(t), path); if (got !== val) bad.push(`${t} ${path}: "${got}"`); }
    // otomatik kategori hapları: 1 elle + 2 kategori
    const pills = await p.$$eval(`${S("best_sellers")} .nav-pills .nav-item`, (e) => e.length);
    if (pills !== 3) bad.push(`best_sellers hap sayısı ${pills}`);
    const cnt = await p.$$eval(`${S("product_columns")} [data-testid="pcol-2"] li.product-item__list`, (e) => e.length);
    if (cnt !== 2) bad.push(`product_columns limit 2 → ${cnt}`);
    if (IMG) {
      const bg = await p.$eval(`${S("products_carousel_with_image")} [data-pd-field="background_image"]`, (e) => e.style.backgroundImage).catch(() => "");
      if (!bg.includes(IMG.split("/").pop().split(".")[0])) bad.push(`arka plan görseli: ${bg}`);
      if (!(await p.$(`${S("products_carousel_with_image")} [data-pd-field="side_image"] img`))) bad.push("yan görsel");
      if (!(await p.$(`${S("products_carousel_tabs")} [data-testid="pct-banner"] [data-pd-field="side_banner.image"] img`))) bad.push("sekmeli yan banner");
    }
    const fw = await p.$('[data-testid="footer-widgets"]');
    if (fw) bad.push("product_columns varken footer ürün bandı gizlenmeli");
    await p.close();
    assert.deepStrictEqual(bad, [], bad.join(" | "));
  });

  await step("b) tüm varyantlar vitrinde çizilir (+ ekran görüntüleri)", async () => {
    await publishLayout([...top, ...VARIANTS.map(([t, v]) => blk(t, v))]);
    const p = await sfPage(ctx);
    const ids = await p.$$eval("[data-pd-block]", (els) => els.map((e) => e.getAttribute("data-pd-block")));
    const missing = [];
    for (const [t, v, sel] of VARIANTS) {
      const id = ids.find((x) => x.startsWith(`e2e-c-${t}-${v || "def"}-`));
      if (!id || !(await p.$(`[data-pd-block="${id}"] ${sel}`))) missing.push(`${t}/${v}`);
    }
    if (OUT) {
      await p.addStyleTag({ content: "html body .el-sticky-bar,html body .pd-gotop{visibility:hidden!important}" });
      for (const w of [1440, 390]) {
        await p.setViewportSize({ width: w, height: 900 });
        await p.waitForTimeout(600);
        for (const id of ids.filter((x) => x.startsWith("e2e-c-") && x !== "e2e-c-hero")) {
          const el = await p.$(`[data-pd-block="${id}"]`);
          await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(250);
          if ((await el.boundingBox())?.height) await el.screenshot({ path: `${OUT}/${id.replace(/-\d+$/, "")}-${w}.png` });
        }
      }
    }
    await p.close();
    assert.deepStrictEqual(missing, [], `eksik: ${missing.join(", ")}`);
  });

  await step("c) davranışlar: hap sekmesi, gizli sekme ölçümü, başlık okları + last-active, ayarlar, footer bandı", async () => {
    await publishLayout([...top,
      blk("best_sellers", "", { columns: "3", rows_per_slide: 2 }),
      blk("product_slider", "", {}),
      blk("products_carousel_tabs", "centered", {}),
      blk("products_carousel_with_image", "", { source: { kind: "newest", limit: 7 } }),
    ]);
    const p = await sfPage(ctx);
    const bad = [];
    // Çok Satanlar: 1440 → sayfa başına 6 kart (3 × 2); 2. hap tıklanınca kategori ürünleri istenir
    const first = await p.$$eval('[data-block-type="best_sellers"] .js-slide:first-child li.product-item', (e) => e.length);
    if (first !== 6) bad.push(`best_sellers sayfa başına ${first} (beklenen 6)`);
    const before = await p.$$eval('[data-block-type="best_sellers"] li.product-item h5', (e) => e.map((x) => x.textContent).join("|"));
    const req = p.waitForRequest((r) => r.url().includes("resolve-products") && (r.postData() || "").includes('"category"'), { timeout: 8000 });
    await p.click('[data-block-type="best_sellers"] [data-pd-field="header.pills.1.label"]');
    await req;
    await p.waitForTimeout(800);
    const active = await p.$eval('[data-block-type="best_sellers"] [data-pd-field="header.pills.1.label"]', (e) => e.className);
    if (!active.includes("btn-outline-primary")) bad.push("hap etkinleşmedi");
    const after = await p.$$eval('[data-block-type="best_sellers"] li.product-item h5', (e) => e.map((x) => x.textContent).join("|"));
    if (after === before) bad.push("hap tıklanınca ürünler değişmedi");
    // Yeni Eklenenler: 1440 → 6 görünür, 6. kart last-active; sonraki ok → 7. kart last-active
    const slide = '[data-block-type="product_slider"] .js-slide';
    const w0 = await p.$eval(slide, (e) => e.getBoundingClientRect().width);
    const vw = await p.$eval('[data-block-type="product_slider"] .el-carousel__viewport', (e) => e.getBoundingClientRect().width);
    if (Math.abs(vw / w0 - 6) > 0.1) bad.push(`product_slider görünen adet ${(vw / w0).toFixed(2)}`);
    const la = () => p.$$eval(`${slide} > .products-group`, (e) => e.findIndex((x) => x.classList.contains("pc-last-active")));
    if ((await la()) !== 5) bad.push(`last-active başta ${await la()}`);
    await p.click('[data-block-type="product_slider"] [data-testid="header-arrows"] button[aria-label="Sonraki"]');
    await p.waitForTimeout(700);
    if ((await la()) !== 6) bad.push(`last-active ok sonrası ${await la()}`);
    // Sekmeli karusel: 3. sekme görünür olunca slayt genişliği = görünüm / 3
    await p.click('[data-block-type="products_carousel_tabs"] .nav-tab .nav-item:nth-child(3) a');
    await p.waitForTimeout(800);
    const tw = await p.$eval('[data-block-type="products_carousel_tabs"] [data-testid="pct-pane-2"] .js-slide', (e) => e.getBoundingClientRect().width).catch(() => 0);
    const tv = await p.$eval('[data-block-type="products_carousel_tabs"] [data-testid="pct-pane-2"] .el-carousel__viewport', (e) => e.getBoundingClientRect().width).catch(() => 0);
    if (!tw || Math.abs(tv / tw - 3) > 0.1) bad.push(`gizli sekme ölçümü: ${tw}/${tv}`);
    // Görselli karusel: 2'li, 30 px boşluk, nokta yok
    const g = await p.$$eval('[data-block-type="products_carousel_with_image"] .js-slide', (e) => e.slice(0, 2).map((x) => x.getBoundingClientRect().left));
    const gw = await p.$eval('[data-block-type="products_carousel_with_image"] .js-slide', (e) => getComputedStyle(e).paddingLeft);
    if (gw !== "30px") bad.push(`boşluk ${gw}`);
    if (g.length < 2) bad.push("görselli karusel kartları");
    if (await p.$('[data-block-type="products_carousel_with_image"] .js-pagination')) bad.push("görselli karuselde nokta olmamalı");
    // product_columns yokken footer ürün bandı görünür (≥992)
    if (!(await p.$('[data-testid="footer-widgets"]'))) bad.push("product_columns yokken footer bandı görünmeli");
    await p.close();
    assert.deepStrictEqual(bad, [], bad.join(" | "));
  });

  // varsayılan grup C düzeni (editör / önizleme / denetim adımları için)
  await publishLayout([...top, blk("best_sellers"), blk("product_slider"), blk("products_carousel_tabs", "centered"), blk("products_carousel_with_image"), blk("product_columns")]);

  await step("d) editör: alan → anında önizleme, vitrin yayından önce değişmez, yayınla → vitrin", async () => {
    const page = await ctx.newPage();
    page.on("pageerror", (e) => console.log("  PAGEERR", e.message));
    await page.goto(`${BASE}/admin/sayfa-tasarimi`, { waitUntil: "networkidle" });
    const frame = () => page.frame({ url: /\/onizleme\/sayfa\/home/ });
    await page.waitForFunction(() => document.querySelector('[data-testid="preview-frame"]')?.contentDocument?.querySelector('[data-block-type="best_sellers"] .product-item'), null, { timeout: 20000 });
    const MARK = `Çok Satan Ekipman ${Date.now() % 100000}`;
    await page.click('[data-testid^="block-row-"][data-block-type="best_sellers"] button.flex-1');
    const input = page.locator('[data-testid="block-editor"] [data-field-path="header.title"] input').first();
    await input.fill(MARK);
    await frame().waitForFunction((m) => document.querySelector('[data-block-type="best_sellers"] [data-pd-field="header.title"]')?.textContent === m, MARK, { timeout: 8000 });
    const TAB = `Kampanyalı ${Date.now() % 1000}`;
    await page.click('[data-testid^="block-row-"][data-block-type="products_carousel_tabs"] button.flex-1');
    await page.click('[data-testid="block-editor"] [role="tab"]:has-text("Ürünler")');
    await page.locator('[data-testid="block-editor"] [data-testid="repeater-tabs"] button.flex-1').nth(1).click();
    await page.locator('[data-testid="block-editor"] [data-field-path="tabs.1.label"] input').first().fill(TAB);
    await frame().waitForFunction((m) => document.querySelector('[data-block-type="products_carousel_tabs"] [data-pd-field="tabs.1.label"]')?.textContent === m, TAB, { timeout: 8000 });
    const pub = await (await fetch(`${API}/page-blocks?page=home`)).text();
    assert(!pub.includes(MARK) && !pub.includes(TAB), "taslak vitrine sızmamalı");
    await page.waitForFunction(() => /otomatik kaydedildi/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 10000 });
    await page.click('[data-testid="publish"]');
    await page.waitForFunction(() => /Yayındaki sürüm/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 15000 });
    const sf = await ctx.newPage();
    await sf.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
    await sf.waitForFunction((m) => document.querySelector('[data-block-type="best_sellers"] [data-pd-field="header.title"]')?.textContent === m, MARK, { timeout: 10000 });
    await sf.waitForFunction((m) => document.querySelector('[data-block-type="products_carousel_tabs"] [data-pd-field="tabs.1.label"]')?.textContent === m, TAB, { timeout: 10000 });
    await sf.close();
    await page.close();
  });

  await step("e) önizleme == vitrin (grup C blokları bayt-eşit)", async () => {
    const shots = async (url) => {
      const p = await ctx.newPage();
      await p.goto(url, { waitUntil: "networkidle" });
      await p.waitForSelector("[data-pd-block]");
      await p.addStyleTag({ content: "html body .el-sticky-bar,html body .pd-insert,html body .pd-gotop{display:none!important}" });
      await p.waitForTimeout(1500);
      const ids = await p.$$eval("[data-pd-block]", (els) => els.map((e) => e.getAttribute("data-pd-block")));
      const out = {};
      for (const id of ids) {
        const el = await p.$(`[data-pd-block="${id}"]`);
        if ((await el.getAttribute("data-block-type")) === "hero_slider") continue;
        await el.scrollIntoViewIfNeeded();
        await p.mouse.move(0, 0);
        await p.waitForTimeout(250);
        out[id] = await el.screenshot();
      }
      await p.close();
      return out;
    };
    const a = await shots(`${BASE}/?pd-noanim=1`);
    const b = await shots(`${BASE}/onizleme/sayfa/home?pd-noanim=1`);
    assert.deepStrictEqual(Object.keys(b), Object.keys(a), "aynı bloklar");
    const diff = Object.keys(a).filter((k) => Buffer.compare(a[k], b[k]) !== 0);
    assert.deepStrictEqual(diff, [], `farklı bloklar: ${diff.join(", ")}`);
  });

  await step("f) grup C bloklarında sabit kodlu görünür metin yok, yatay taşma yok (1440 + 390)", async () => {
    const bad = [];
    for (const w of [1440, 390]) {
      const p = await sfPage(ctx, w);
      bad.push(...await p.$$eval("[data-pd-block]", (blocks) => {
        const out = [];
        blocks.forEach((b) => {
          if (b.getAttribute("data-block-type") === "hero_slider") return;
          const wk = document.createTreeWalker(b, NodeFilter.SHOW_TEXT);
          for (let nd = wk.nextNode(); nd; nd = wk.nextNode()) {
            const t = nd.textContent.replace(/\s+/g, " ").trim();
            if (!t || /^[\s:·|/–—%₺,.\-+×x\d]*$/.test(t)) continue;
            const el = nd.parentElement;
            if (!el || el.closest("[data-pd-field],[data-pd-data],[data-pd-placeholder],.product-item,.sr-only,script,style,.pd-stub")) continue;
            if (!el.getClientRects().length) continue;
            out.push(`${b.getAttribute("data-block-type")}: ${t.slice(0, 60)}`);
          }
        });
        return out;
      }));
      const sw = await p.evaluate(() => document.documentElement.scrollWidth);
      if (sw > w) bad.push(`${w}px: yatay taşma ${sw}`);
      await p.close();
    }
    assert.deepStrictEqual(bad, [], bad.join(" | "));
  });

  if (TPL) {
    await step("g) şablon ölçüleri (v1.0 home / home-v2 / home-v3, v2.0 index) — 1440 ve 390", async () => {
      const measure = (p, sel) => p.evaluate((s) => {
        const e = document.querySelector(s); if (!e) return null;
        const r = e.getBoundingClientRect(); const c = getComputedStyle(e);
        return { w: Math.round(r.width), h: Math.round(r.height), bg: c.backgroundColor, pt: c.paddingTop, mb: c.marginBottom, fs: c.fontSize, fw: c.fontWeight, bb: c.borderBottomWidth };
      }, sel);
      const near = (a, b, tol) => Math.abs(a - b) <= tol;
      const bad = [];
      for (const w of [1440, 390]) {
        const op = await sfPage(ctx, w);
        const tp = await ctx.newPage(); await tp.setViewportSize({ width: w, height: 900 });
        const cmp = async (label, url, ts, os, keys, tol = 2) => {
          if (tp.url() !== url) { await tp.goto(url, { waitUntil: "load" }); await tp.waitForTimeout(1500); }
          const a = await measure(tp, ts); const b = await measure(op, os);
          if (!a || !b) { bad.push(`${w} ${label}: bulunamadı`); return; }
          keys.forEach((k) => { if (typeof a[k] === "number" ? !near(a[k], b[k], tol) : a[k] !== b[k]) bad.push(`${w} ${label}.${k}: şablon ${a[k]} vitrin ${b[k]}`); });
        };
        const V2 = `${TPL}/2.0/html/home/index.html`;
        const V1 = `${TPL}/1.0/HTML`;
        // Çok Satanlar (v2.0 index aynı CSS): yatay kart görsel kutusu, etkin hap, başlık alt çizgisi
        await cmp("çok satanlar hap", V2, ".space-top-2 .nav-pills .btn-outline-primary", '[data-block-type="best_sellers"] .nav-pills .btn-outline-primary', ["h", "fs", "fw"]);
        if (w === 1440) {
          await cmp("çok satanlar kart", V2, ".space-top-2 li.product-item__card", '[data-block-type="best_sellers"] li.product-item__card', ["w"]);
          await cmp("çok satanlar görsel", V2, ".space-top-2 .product-media-left a", '[data-block-type="best_sellers"] .product-media-left a', ["w"]);
          await cmp("çok satanlar blok", V2, ".space-top-2", '[data-block-type="best_sellers"] [data-testid="bestsellers"]', ["pt"]);
        }
        // Görselli karusel (v1.0 home-v3): bant rengi, üst iç boşluk, alt boşluk
        await cmp("görselli bant", `${V1}/home-v3.html`, ".products-carousel-with-image", '[data-block-type="products_carousel_with_image"]', ["bg", "pt", "mb"]);
        // Sekmeli karusel (v1.0 home-v2): sekme yazı boyutu, etkin kalın
        if (w === 1440) {
          await cmp("sekme yazısı", `${V1}/home-v2.html`, ".products-carousel-tabs .nav-link.active", '[data-block-type="products_carousel_tabs"] .nav-tab .nav-link.active', ["fs", "fw"]);
          // Alt ürün sütunları (v2.0 index footer-top-widget): 75 px görsel, başlık yazısı
          await cmp("alt sütun görseli", V2, ".product-item__list .width-75", '[data-block-type="product_columns"] .product-item__list .width-75', ["w"]);
          await cmp("alt sütun başlığı", V2, ".section-title__sm", '[data-block-type="product_columns"] .section-title__sm', ["fs"]);
        }
        if (OUT) {
          for (const [nm, url, ts, os] of [["best_sellers", V2, ".space-top-2", '[data-block-type="best_sellers"]'],
            ["products_carousel_with_image", `${V1}/home-v3.html`, ".products-carousel-with-image", '[data-block-type="products_carousel_with_image"]']]) {
            if (tp.url() !== url) { await tp.goto(url, { waitUntil: "load" }); await tp.waitForTimeout(1500); }
            const te = await tp.$(ts); if (te) { await te.scrollIntoViewIfNeeded(); await tp.waitForTimeout(500); await te.screenshot({ path: `${OUT}/tpl-${nm}-${w}.png` }); }
            const oe = await op.$(os); if (oe) { await oe.scrollIntoViewIfNeeded(); await op.waitForTimeout(300); await oe.screenshot({ path: `${OUT}/sf-${nm}-${w}.png` }); }
          }
        }
        await tp.close(); await op.close();
      }
      assert.deepStrictEqual(bad, [], bad.join(" | "));
    });
  }

  // temizlik: başlangıç sürümüne dön
  await api("DELETE", "/page-design/home/draft");
  const rs = await api("POST", `/page-design/home/revisions/${startRev}/restore`);
  if (rs.status === 200) await api("POST", "/page-design/home/publish");
  await browser.close();
  console.log(failures ? `\n${failures} adım başarısız` : "\nTüm adımlar geçti");
  process.exit(failures ? 1 : 0);
})();
