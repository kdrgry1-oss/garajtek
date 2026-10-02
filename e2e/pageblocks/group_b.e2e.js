// Sayfa Tasarımı — Grup B blokları uçtan uca (SPEC §7 / §9): deals_tabs, product_grid_212, products_6_1,
// deals_carousel, deals_week_limited, product_grid, banner_with_products_grid.
//
//   BASE=http://localhost:8744 API=http://localhost:8743/api TOKEN=<admin jwt> \
//   [TPL1=http://localhost:3022] [OUT=/tmp/grpb-shots] node e2e/pageblocks/group_b.e2e.js
//
// Doğrulananlar (gerçek backend + production build):
//   a) Panel API'siyle (taslak → yayın) girilen her metin vitrinde ilgili data-pd-field düğümünde çıkar
//   b) Her blok varyantı vitrinde kendi şablon işaretleyicisiyle çizilir
//   c) Panel editörü: alan yazılınca iframe önizleme anında güncellenir, vitrin yayından önce değişmez;
//      görünüm (varyant) değişimi önizlemeye yansır; Yayınla → vitrinde görünür
//   d) Önizleme == vitrin (blok ekran görüntüleri bayt-eşit; geri sayımlar maskeli)
//   e) Sabit kodlu görünür metin yok (yalnız data-pd-field / katalog verisi)
//   f) Şablon ölçüleri (TPL1 verilirse, 1440 ve 390): kazanç kutusu 110×65 #343f49, geri sayım 56×41,
//      stok çubuğu 20 px, 2-1-2 bant 58 px #f9f9f9 + sütun genişlikleri, 6-1 sütunları ve 367 px büyük görsel
// Sonunda başlangıç revizyonu geri yüklenip yayınlanır.
const assert = require("assert");
const fs = require("fs");
const { chromium } = require(process.env.PW_MODULE || "/opt/node22/lib/node_modules/playwright");

const BASE = process.env.BASE;
const API = process.env.API || `${BASE}/api`;
const TOKEN = process.env.TOKEN;
const TPL1 = process.env.TPL1 || "";
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
const blk = (type, variant, settings = {}) => ({ id: `e2e-b-${type}-${variant}-${(n += 1)}`, type, title: `${type} ${variant}`, is_active: true,
  settings: { _variant: variant, _reveal: { enabled: false }, ...settings } });

async function publishLayout(blocks) {
  const cur = await api("GET", "/page-design/home");
  const rev = cur.data.draft ? cur.data.draft.rev : undefined;
  const put = await api("PUT", "/page-design/home/draft", { blocks }, rev !== undefined ? { "If-Match": String(rev) } : {});
  assert.strictEqual(put.status, 200, `taslak: ${JSON.stringify(put.data).slice(0, 300)}`);
  assert.deepStrictEqual(put.data.errors, [], "doğrulama hatası olmamalı");
  const pub = await api("POST", "/page-design/home/publish");
  assert.strictEqual(pub.status, 200, `yayın: ${JSON.stringify(pub.data).slice(0, 300)}`);
}

// a) panelden girilen değerler → vitrin
const CUSTOM = [
  ["deals_tabs", "v1", {
    deal: { title: "Haftanın Ürünü", savings: { label: "Tasarruf", mode: "manual", amount: "₺2.500" }, stock: { sold_label: "Satıldı:", available_label: "Stokta:" },
      countdown: { heading: "Son fırsat:", labels: { days: "G", hours: "S", minutes: "D", seconds: "SN" } } },
    tabs: [{ label: "Öne Çıkan Ekipman", source: { kind: "featured", limit: 6 } }, { label: "İndirimli Ekipman", source: { kind: "discounted", limit: 6 } }],
  }, { "deal.title": "Haftanın Ürünü", "deal.savings.label": "Tasarruf", "deal.stock.sold_label": "Satıldı:", "deal.countdown.heading": "Son fırsat:",
    "deal.countdown.labels.hours": "S", "tabs.0.label": "Öne Çıkan Ekipman", "tabs.1.label": "İndirimli Ekipman" }],
  ["product_grid_212", "2_1_2", { title: "Kategori vitrini", nav_items: [{ label: "Kampanyalı Liftler", source: { kind: "discounted", limit: 5 } }], nav_auto_categories: { enabled: true, max: 2 } },
    { "nav_items.0.label": "Kampanyalı Liftler", title: "Kategori vitrini" }],
  ["products_6_1", "6_1", { header: { title: "En Çok Satan Ekipmanlar", right: "pills", pills: [{ label: "İlk 7", as_tab: true, active: true, link: { kind: "none", url: "" } }, { label: "Kompresör", link: { kind: "url", url: "/kompresorler" } }] } },
    { "header.title": "En Çok Satan Ekipmanlar", "header.pills.0.label": "İlk 7", "header.pills.1.label": "Kompresör" }],
  ["deals_carousel", "gallery", { header: { title: "Bu Haftanın Fırsatları" }, prev_label: "Geri", next_label: "İleri" },
    { "header.title": "Bu Haftanın Fırsatları", prev_label: "Geri", next_label: "İleri", "deals.0.savings.label": "Kazancınız" }],
  ["deals_week_limited", "v4", { left: { title: "Sınırlı <strong>Stok</strong>", big_symbol: "%", countdown: { heading: "Bitmesine:" } } },
    { "left.big_symbol": "%", "left.countdown.heading": "Bitmesine:" }],
  ["product_grid", "recommendations", { header: { title: "Atölyeniz İçin Seçtiklerimiz", right: "link", link: { label: "Hepsini gör", link: { kind: "url", url: "/tum-urunler" } } } },
    { "header.title": "Atölyeniz İçin Seçtiklerimiz", "header.link.label": "Hepsini gör" }],
  ["banner_with_products_grid", "banner_list", { header: { title: "Lift Dünyası" }, tabs: [{ label: "Popüler", active: true, source: { kind: "best_sellers", limit: 8 } }, { label: "Yeni", source: { kind: "newest", limit: 8 } }],
    category_links: [{ label: "Makaslı Liftler", link: { kind: "url", url: "/makasli-liftler" } }] },
    { "header.title": "Lift Dünyası", "tabs.0.label": "Popüler", "tabs.1.label": "Yeni", "category_links.0.label": "Makaslı Liftler" }],
];

// b) varyant işaretleyicileri
const VARIANTS = [
  ["deals_tabs", "v1", ".pdb-onsale .pdb-savings"], ["deals_tabs", "v2", ".min-width-370 .height-75"], ["deals_tabs", "discount_tabs", ".nav-tab-pill-fill"],
  ["product_grid_212", "2_1_2", ".pdb-212__cols .pdb-212__mid .pdb-main"], ["product_grid_212", "4_1_4", ".products-group-4-1-4 .pdb-main__thumbs"],
  ["products_6_1", "6_1", ".pdb-61 .pdb-main__fixed"], ["products_6_1", "8_1", ".pdb-61--8"],
  ["deals_carousel", "gallery", ".pdb-dow__box .pdb-dow__slide"], ["deals_carousel", "cards", ".pdb-dow-cards .js-slide .product-item"],
  ["deals_week_limited", "v4", ".pdb-wdl .font-size-130"], ["deals_week_limited", "v11", ".pdb-wdl .font-size-sl-48"],
  ["product_grid", "recommendations", ".pdb-grid .pdb-cols .product-item"], ["product_grid", "hot", ".pdb-grid .product-item__card"],
  ["banner_with_products_grid", "banner_list", ".pdb-bpg .list-group-item"], ["banner_with_products_grid", "menu", ".pdb-bpg .box-shadow-3"],
  ["banner_with_products_grid", "featured", ".pdb-bpg .pdb-main"],
];

async function textAt(p, type, path) {
  return p.$eval(`[data-block-type="${type}"] [data-pd-field="${path}"]`, (e) => e.textContent.replace(/\s+/g, " ").trim()).catch(() => null);
}

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
  const top = hero ? [{ ...hero, id: "e2e-b-hero" }] : [];

  await step("a) panelden girilen metinler vitrinde (data-pd-field)", async () => {
    await publishLayout([...top, ...CUSTOM.map(([t, v, s]) => blk(t, v, s))]);
    const p = await ctx.newPage();
    await p.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
    await p.waitForTimeout(1500);
    const bad = [];
    for (const [type, , , expect] of CUSTOM) {
      for (const [path, val] of Object.entries(expect)) {
        const got = await textAt(p, type, path);
        if (got !== val) bad.push(`${type} ${path}: beklenen "${val}", gelen "${got}"`);
      }
    }
    const rich = await p.$eval('[data-block-type="deals_week_limited"] [data-pd-field="left.title"]', (e) => e.innerHTML).catch(() => "");
    if (!rich.includes("<strong>Stok</strong>")) bad.push("deals_week_limited left.title zengin metin");
    const savings = await p.$eval('[data-block-type="deals_tabs"] .pdb-savings__amount', (e) => e.textContent).catch(() => "");
    if (savings !== "₺2.500") bad.push(`deals_tabs elle kazanç: ${savings}`);
    await p.close();
    assert.deepStrictEqual(bad, [], bad.join(" | "));
  });

  await step("b) tüm varyantlar vitrinde çizilir", async () => {
    await publishLayout([...top, ...VARIANTS.map(([t, v]) => blk(t, v))]);
    const p = await ctx.newPage();
    await p.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
    await p.waitForTimeout(2000);
    const ids = await p.$$eval("[data-pd-block]", (els) => els.map((e) => e.getAttribute("data-pd-block")));
    const missing = [];
    for (const [t, v, sel] of VARIANTS) {
      const id = ids.find((x) => x.startsWith(`e2e-b-${t}-${v}-`));
      if (!id || !(await p.$(`[data-pd-block="${id}"] ${sel}`))) missing.push(`${t}/${v}`);
    }
    if (OUT) {
      for (const w of [1440, 390]) {
        await p.setViewportSize({ width: w, height: 900 });
        await p.waitForTimeout(600);
        for (const id of ids.filter((x) => x.startsWith("e2e-b-") && x !== "e2e-b-hero")) {
          const el = await p.$(`[data-pd-block="${id}"]`);
          await el.scrollIntoViewIfNeeded(); await p.waitForTimeout(250);
          if ((await el.boundingBox())?.height) await el.screenshot({ path: `${OUT}/${id.replace(/-\d+$/, "")}-${w}.png` });
        }
      }
    }
    await p.close();
    assert.deepStrictEqual(missing, [], `eksik: ${missing.join(", ")}`);
  });

  // varsayılan grup B düzeni (editör / önizleme / denetim adımları için)
  await publishLayout([...top, ...CUSTOM.map(([t, v]) => blk(t, v))]);

  await step("c) editör: alan → anında önizleme, varyant değişimi, yayınla → vitrin", async () => {
    const page = await ctx.newPage();
    page.on("pageerror", (e) => console.log("  PAGEERR", e.message));
    await page.goto(`${BASE}/admin/sayfa-tasarimi`, { waitUntil: "networkidle" });
    const frame = () => page.frame({ url: /\/onizleme\/sayfa\/home/ });
    await page.waitForFunction(() => document.querySelector('[data-testid="preview-frame"]')?.contentDocument?.querySelector('[data-block-type="deals_tabs"] .pdb-onsale'), null, { timeout: 20000 });
    const MARK = `Garaj Fırsatı ${Date.now() % 100000}`;
    await page.click('[data-testid^="block-row-"][data-block-type="deals_tabs"] button.flex-1');
    const input = page.locator('[data-testid="block-editor"] [data-field-path="deal.title"] input').first();
    await input.fill(MARK);
    await frame().waitForFunction((m) => document.querySelector('[data-block-type="deals_tabs"] [data-pd-field="deal.title"]')?.textContent === m, MARK, { timeout: 8000 });
    const pub = await (await fetch(`${API}/page-blocks?page=home`)).text();
    assert(!pub.includes(MARK), "taslak vitrine sızmamalı");
    // varyant: 2-1-2 → 4-1-4
    await page.click('[data-testid^="block-row-"][data-block-type="product_grid_212"] button.flex-1');
    await page.selectOption('[data-testid="variant-select"]', "4_1_4");
    await page.click('[data-testid="app-confirm-ok"]');
    await frame().waitForSelector('[data-block-type="product_grid_212"] .products-group-4-1-4', { timeout: 8000 });
    await page.waitForFunction(() => /otomatik kaydedildi/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 10000 });
    await page.click('[data-testid="publish"]');
    await page.waitForFunction(() => /Yayındaki sürüm/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 15000 });
    const sf = await ctx.newPage();
    await sf.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
    await sf.waitForFunction((m) => document.querySelector('[data-block-type="deals_tabs"] [data-pd-field="deal.title"]')?.textContent === m, MARK, { timeout: 10000 });
    await sf.waitForSelector('[data-block-type="product_grid_212"] .products-group-4-1-4', { timeout: 10000 });
    await sf.close();
    await page.close();
  });

  await step("d) önizleme == vitrin (grup B blokları bayt-eşit)", async () => {
    const shots = async (url) => {
      const p = await ctx.newPage();
      await p.goto(url, { waitUntil: "networkidle" });
      await p.waitForSelector("[data-pd-block]");
      // yapışkan şerit, "yukarı çık" düğmesi (kaydırmaya göre) ve önizlemenin "+ Blok ekle" çizgisi karşılaştırma dışı
      await p.addStyleTag({ content: "html body .el-sticky-bar,html body .pd-insert,html body .pd-gotop{display:none!important}" });
      await p.waitForTimeout(1500);
      const ids = await p.$$eval("[data-pd-block]", (els) => els.map((e) => e.getAttribute("data-pd-block")));
      const out = {};
      for (const id of ids) {
        const el = await p.$(`[data-pd-block="${id}"]`);
        if ((await el.getAttribute("data-block-type")) === "hero_slider") continue;
        await el.scrollIntoViewIfNeeded();
        await p.mouse.move(0, 0);
        await p.waitForTimeout(200);
        out[id] = await el.screenshot({ mask: [p.locator('[data-testid="deal-countdown"]')] });
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

  await step("e) grup B bloklarında sabit kodlu görünür metin yok (1440 + 390)", async () => {
    const bad = [];
    for (const w of [1440, 390]) {
      const p = await ctx.newPage();
      await p.setViewportSize({ width: w, height: 900 });
      await p.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
      await p.waitForTimeout(1500);
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

  if (TPL1) {
    await step("f) şablon ölçüleri (v1.0 home.html / home-v3.html) — 1440 ve 390", async () => {
      await publishLayout([...top, blk("deals_tabs", "v1"), blk("product_grid_212", "2_1_2"), blk("products_6_1", "6_1")]);
      const measure = (p, sel) => p.evaluate((s) => {
        const e = document.querySelector(s); if (!e) return null;
        const r = e.getBoundingClientRect(); const c = getComputedStyle(e);
        return { w: Math.round(r.width), h: Math.round(r.height), bg: c.backgroundColor, pt: c.paddingTop, fs: c.fontSize };
      }, sel);
      const bad = [];
      const near = (a, b, tol) => Math.abs(a - b) <= tol;
      for (const w of [1440, 390]) {
        const tp = await ctx.newPage(); await tp.setViewportSize({ width: w, height: 900 });
        const op = await ctx.newPage(); await op.setViewportSize({ width: w, height: 900 });
        await op.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "load" }); await op.waitForSelector('[data-block-type="products_6_1"] .pdb-main', { timeout: 20000 }); await op.waitForTimeout(1000);
        await tp.goto(`${TPL1}/home.html`, { waitUntil: "load" }); await tp.waitForTimeout(1000);
        const exact = [
          ["kazanç kutusu", ".section-onsale-product .savings", '[data-block-type="deals_tabs"] .pdb-savings', ["w", "h", "bg"]],
          ["geri sayım kutusu", ".section-onsale-product .countdown .hours .value", '[data-block-type="deals_tabs"] .pdb-cd__unit.hours .pdb-cd__value', ["w", "h", "bg", "fs"]],
          ["stok çubuğu", ".section-onsale-product .progress", '[data-block-type="deals_tabs"] .pdb-progress__track', ["h", "bg"]],
          ["2-1-2 bant", ".products-2-1-2", '[data-block-type="product_grid_212"]', ["bg", "pt"]],
          ["2-1-2 nav yazı", ".products-2-1-2 .nav-inline", '[data-block-type="product_grid_212"] .pdb-212__nav', ["fs"]],
        ];
        if (w === 1440) {
          exact.push(["özel teklif sütunu", ".section-onsale-product", '[data-block-type="deals_tabs"] .pdb-onsale', ["w"]]);
          exact.push(["2-1-2 orta sütun", ".columns-2-1-2 > ul:nth-child(2)", '[data-block-type="product_grid_212"] .pdb-212__mid', ["w"]]);
          exact.push(["2-1-2 yan sütun", ".columns-2-1-2 > ul:first-child", '[data-block-type="product_grid_212"] .pdb-212__side', ["w"]]);
        }
        for (const [label, ts, os, keys] of exact) {
          const a = await measure(tp, ts); const b = await measure(op, os);
          if (!a || !b) { bad.push(`${w} ${label}: bulunamadı`); continue; }
          keys.forEach((k) => { if (typeof a[k] === "number" ? !near(a[k], b[k], 2) : a[k] !== b[k]) bad.push(`${w} ${label}.${k}: şablon ${a[k]} vitrin ${b[k]}`); });
        }
        if (OUT) {
          for (const [nm, ts, os] of [["deals_tabs", ".deals-and-tabs", '[data-block-type="deals_tabs"]'], ["product_grid_212", ".products-2-1-2", '[data-block-type="product_grid_212"]']]) {
            const te = await tp.$(ts); if (te) { await te.scrollIntoViewIfNeeded(); await tp.waitForTimeout(500); await te.screenshot({ path: `${OUT}/tpl-${nm}-${w}.png` }); }
            const oe = await op.$(os); if (oe) { await oe.scrollIntoViewIfNeeded(); await op.waitForTimeout(300); await oe.screenshot({ path: `${OUT}/sf-${nm}-${w}.png` }); }
          }
        }
        await tp.goto(`${TPL1}/home-v3.html`, { waitUntil: "load" }); await tp.waitForTimeout(1000);
        const six = [["6-1 bant", ".products-6-1", '[data-block-type="products_6_1"]', ["bg", "pt"]]];
        if (w === 1440) {
          six.push(["6-1 ızgara", ".columns-6-1 > ul.products-6", '[data-block-type="products_6_1"] .pdb-61__grid', ["w"]]);
          six.push(["6-1 büyük ürün", ".columns-6-1 > ul.product-main-6-1", '[data-block-type="products_6_1"] .pdb-61__main', ["w"]]);
          six.push(["6-1 görsel yüksekliği", ".product-main-6-1 .product-thumbnail img", '[data-block-type="products_6_1"] .pdb-main__fixed', ["h"]]);
        }
        for (const [label, ts, os, keys] of six) {
          const a = await measure(tp, ts); const b = await measure(op, os);
          if (!a || !b) { bad.push(`${w} ${label}: bulunamadı`); continue; }
          keys.forEach((k) => { if (typeof a[k] === "number" ? !near(a[k], b[k], 2) : a[k] !== b[k]) bad.push(`${w} ${label}.${k}: şablon ${a[k]} vitrin ${b[k]}`); });
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
