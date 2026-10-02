// Sayfa Tasarımı — Grup A (slider, banner, içerik) görsel eşdeğerlik + panel→vitrin testleri (SPEC §7, §9).
//
//   BASE=http://localhost:8632 API=http://localhost:8631/api TOKEN=<admin jwt> \
//   TEMPLATE=/yol/electro-zip-açılmış  node e2e/pageblocks/group_a.e2e.js [blok_anahtarı …]
//   (Playwright: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers; paket yolu PW_MODULE; ekran görüntüleri OUT klasörüne)
//
// Not: vitrin lang="tr" olduğundan büyük harfe çevirme i→İ yapar; şablon metinleri bu yüzden baştan büyük harfle verilir.
// Her durum için:
//   1) Blok, şablon bölümünün METİNLERİYLE (İngilizce) ayarlanır → taslağa yazılır → yayınlanır (yönetici API'si).
//   2) Vitrin (production build) 1440 ve 390 px genişlikte açılır, blok bölümünün ekran görüntüsü alınır.
//   3) Şablonun aynı bölümü (TEMPLATE altındaki HTML, yerel varlıklarla) aynı genişlikte görüntülenir.
//   4) İki görüntü tarayıcı içinde piksel piksel karşılaştırılır; görsel alanları (şablonda <img>/arka plan,
//      vitrinde yer tutucu/görsel) maskelenir. Fark oranı ≤ THRESHOLD (vars. %2) beklenir.
//   Ayrıca: panelden (API) değiştirilen alanın vitrine yansıdığı ve görünür metinlerin hepsinin data-pd-field
//   taşıdığı doğrulanır.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { chromium } = require(process.env.PW_MODULE || "/opt/node22/lib/node_modules/playwright");

const BASE = process.env.BASE;
const API = process.env.API || `${BASE}/api`;
const TOKEN = process.env.TOKEN;
const TPL = process.env.TEMPLATE;
const OUT = process.env.OUT || path.join(require("os").tmpdir(), "pd-group-a");
const THRESHOLD = Number(process.env.THRESHOLD || 2);
const FONTS = path.join(__dirname, "..", "..", "frontend", "public", "electro", "fonts");
if (!BASE || !TOKEN || !TPL) { console.error("BASE, TOKEN ve TEMPLATE gerekli"); process.exit(2); }
fs.mkdirSync(OUT, { recursive: true });

const H = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };
const api = async (method, p, body, extra = {}) => {
  const r = await fetch(`${API}${p}`, { method, headers: { ...H, ...extra }, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text();
  return { status: r.status, data: t ? JSON.parse(t) : null };
};
const lnk = (url) => ({ kind: "url", url, new_tab: false });
const T1 = (f) => path.join(TPL, "1.0", "HTML", f);
const IMG = (rel, extra = {}) => ({ $img: rel, ...extra }); // şablon görseli → yükleme API'siyle aynı görsel vitrine

const uploaded = {};
async function upload(rel) {
  if (uploaded[rel]) return uploaded[rel];
  const file = path.join(TPL, rel);
  const ext = path.extname(file).slice(1).toLowerCase();
  const fd = new FormData();
  fd.append("file", new Blob([fs.readFileSync(file)], { type: ext === "png" ? "image/png" : "image/jpeg" }), path.basename(file));
  const r = await fetch(`${API}/upload/image`, { method: "POST", headers: { Authorization: `Bearer ${TOKEN}` }, body: fd });
  const d = await r.json();
  assert(r.ok, `yükleme: ${JSON.stringify(d)}`);
  uploaded[rel] = d.url || `/api/upload/files/${d.path}`;
  return uploaded[rel];
}
async function resolveImages(v) {
  if (Array.isArray(v)) return Promise.all(v.map(resolveImages));
  if (v && typeof v === "object") {
    if (v.$img) { const { $img, ...rest } = v; return { url: await upload($img), alt: "", ...rest }; }
    const o = {};
    for (const k of Object.keys(v)) o[k] = await resolveImages(v[k]);
    return o;
  }
  return v;
}
const T2 = (f) => path.join(TPL, "2.0", "html", "home", f); // eslint-disable-line no-unused-vars

// ---------------------------------------------------------------- durumlar (şablon metinleriyle)
const CASES = [
  {
    key: "hero_slider", name: "hero v1", tpl: T1("home.html"), sel: ".home-v1-slider",
    settings: {
      _variant: "v1",
      carousel: { autoplay: false },
      slides: [
        { background: IMG("1.0/HTML/assets/images/slider/banner-2.jpg"), layout: "price", title: "THE NEW <br> STANDARD", subtitle: "UNDER FAVORABLE SMARTWATCHES", price_prefix: "FROM", price: "$749",
          button: { text: "Start Buying", style: "primary", link: lnk("/sale") } },
        { background: IMG("1.0/HTML/assets/images/slider/banner-1.jpg"), layout: "promo", pretitle: "SHOP TO GET WHAT YOU LOVES", title: "TIMEPIECES THAT MAKE A STATEMENT UP TO <strong>40% OFF</strong>",
          button: { text: "Start Buying", style: "primary", link: lnk("/sale") } },
        { background: IMG("1.0/HTML/assets/images/slider/banner-3.jpg"), layout: "promo", pretitle: "SHOP TO GET WHAT YOU LOVES", title: "TIMEPIECES THAT MAKE A STATEMENT UP TO <strong>40% OFF</strong>",
          button: { text: "Start Buying", style: "primary", link: lnk("/sale") } },
      ],
    },
    edit: { path: ["slides", 0, "subtitle"], value: "PANELDEN DEĞİŞTİ" },
  },
  {
    key: "ads_block", name: "ads v1", tpl: T1("home.html"), sel: ".home-v1-ads-block .ads-block", sfInner: ".pd-ads > .row",
    settings: {
      _variant: "v1",
      items: [
        { image: IMG("1.0/HTML/assets/images/banner/cameras.jpg"), text: "CATCH BIG <br><strong>DEALS</strong> ON THE <br>CAMERAS", action_type: "link", action_text: "Shop now", link: lnk("/sale") },
        { image: IMG("1.0/HTML/assets/images/banner/MobileDevicesv2-2.jpg"), text: "TABLETS,<br> SMARTPHONES<br> <strong>AND MORE</strong>", action_type: "upto", action_prefix: "UP TO", action_value: "70", action_suffix: "", link: lnk("/sale") },
        { image: IMG("1.0/HTML/assets/images/banner/DesktopPC.jpg"), text: "SHOP THE <br><strong>HOTTEST</strong><br> PRODUCTS", action_type: "link", action_text: "Shop now", link: lnk("/sale") },
      ],
    },
    edit: { path: ["items", 0, "action_text"], value: "Panelden İncele" },
  },
  {
    key: "full_banner", name: "full banner v1", tpl: T1("home.html"), sel: ".home-v1-fullbanner-ad", sfInner: ".pd-fullbanner",
    settings: { _variant: "image", image: IMG("1.0/HTML/assets/images/banner/home-v1-banner.png"), link: lnk("/sale") },
  },
  {
    key: "banner_two_columns", name: "2 kolon banner (v2.0 v3)", tpl: T2("home-v3.html"), sel: '.mb-8:has(img[src*="690X150"])', sfInner: ".pd-b2c",
    settings: { items: [{ image: IMG("2.0/assets/img/690X150/img1.jpg"), link: lnk("/sale"), alt: "" }, { image: IMG("2.0/assets/img/690X150/img2.jpg"), link: lnk("/sale"), alt: "" }] },
  },
  {
    key: "banner_mosaic", name: "banner mozaiği (v2.0 v9)", tpl: T2("home-v9.html"), sel: '.container.mb-3:has(img[src*="552X325"]) > .row', sfInner: ".pd-mosaic > .row",
    settings: { big: { image: IMG("2.0/assets/img/552X325/img1.jpg"), link: lnk("/sale"), alt: "" },
      small: Array.from({ length: 6 }, () => ({ image: IMG("2.0/assets/img/268X155/img1.jpg"), link: lnk("/sale"), alt: "" })) },
  },
  {
    key: "banner_grid_text_image", name: "metinli banner ızgarası (v2.0 v5)", tpl: T2("home-v5.html"), sel: '.mb-6:has(img[src*="446X262"]) > .row', sfInner: ".pd-bgti > .row",
    settings: { rows: [
      { wide_side: "left", wide: { background: "#ecedf2", title: "G9 Laptops with Ultra 4K HD Display", text: "and the fastest Intel Core i7 processor ever", specs: "", price_prefix: "from", price: "$399", image: IMG("2.0/assets/img/446X262/img1.jpg"), link: lnk("/sale") },
        small: { image: IMG("2.0/assets/img/446X262/img3.jpg"), link: lnk("/sale"), alt: "" } },
      { wide_side: "right", wide: { background: "#f5f5f5", title: "<strong>Fresh Honor 9</strong><br> 32GB Unlocked quadcore", text: "", specs: "4GB RAM | 64GB ROM | 20MP + 12MP Dual Camera", price_prefix: "from", price: "$279", image: IMG("2.0/assets/img/446X262/img2.jpg"), link: lnk("/sale") },
        small: { image: IMG("2.0/assets/img/446X262/img4.jpg"), link: lnk("/sale"), alt: "" } },
    ] },
  },
  {
    key: "features_list", name: "özellik şeridi (v1 home-v3)", tpl: T1("home-v3.html"), sel: ".features-list", sfInner: ".pd-feat__list",
    settings: { _variant: "v1", items: [["ec-transport", "Free Delivery", "from $50"], ["ec-customers", "99% Positive", "Feedbacks"], ["ec-returning", "365 days", "for free return"], ["ec-payment", "Payment", "Secure System"], ["ec-tag", "Only Best", "Brands"]]
      .map(([i, a, b]) => ({ icon: { icon: `ec ${i}` }, strong_text: a, text: b, link: { kind: "none", url: "", new_tab: false } })) },
    edit: { path: ["items", 0, "strong_text"], value: "Panelden Kargo" },
  },
  {
    key: "hero_tabs", name: "sekmeli hero (v2.0 v6)", tpl: T2("home-v6.html"), sel: "#content > .mb-5:first-child .bg-img-hero > .container > .mb-6", sfInner: ".pd-htabs .container > .mb-6",
    tplCss: ".bg-img-hero{background-image:none!important}",
    settings: { background: null, background_color: "", text_color: "#333e48", title_size: 58, products: { enabled: false },
      tabs: ["Gaming Monitors 65", "Smartphones Sale", "End Season Sale", "Laptops Arrivals", "Earphones - 25%", "Tablets 10 inch Sale"].map((label) => ({
        label, title: "END SEASON <br>SMARTPHONES", offer_label: "LAST CALL FOR UP TO", amount: "$250", amount_suffix: "OFF!",
        button: { text: "Start Buying", link: lnk("/sale") }, image: IMG("2.0/assets/img/724X360/img2.png") })) },
    edit: { path: ["tabs", 0, "offer_label"], value: "PANELDEN TEKLİF" },
  },
  {
    key: "deal_slider", name: "haftanın fırsatı (v2.0 v5)", tplBroken: [390],
    tplBrokenWhy: "şablon 390 px'te slick slaytı görünmez bırakıyor (yalnız arka plan çiziliyor)", tpl: T2("home-v5.html"), sel: ".bg-img-hero.min-height-420", sfInner: ".pd-deal__bg",
    tplMask: ".js-countdown, .prodcut-price, .rounded-pill, strong", sfMask: ".js-countdown, .prodcut-price, .rounded-pill, strong",
    settings: { _variant: "thumbs", background: IMG("2.0/assets/img/1400X420/img1.jpg"), carousel: { autoplay: false },
      slides: [{ kicker: "LIMITED", title: "WEEK DEAL", subtitle: "HURRY UP BEFORE OFFER WILL END", title_override: "Widescreen 4K SUHD TV",
        image_override: IMG("2.0/assets/img/400X400/img2.png"), stock: { show: true, available_label: "Availavle:", sold_label: "Already Sold:" },
        countdown: { units: ["hours", "minutes", "seconds"], labels: { days: "DAYS", hours: "HOURS", minutes: "MINS", seconds: "SECS" } }, thumb_label: "SO MUCH TO WATCH IN 4K TVS" }] },
    edit: { path: ["slides", 0, "subtitle"], value: "PANELDEN ALT YAZI" },
  },
];

// ---------------------------------------------------------------- yardımcılar
const fontCss = [300, 400, 600, 700, 800].map((w) => `@font-face{font-family:"Open Sans";font-style:normal;font-weight:${w};src:url("https://fonts.gstatic.com/local/${w}.woff2") format("woff2")}`).join("\n");

async function routeTemplate(p) {
  await p.route(/^https?:\/\//, (r) => r.abort());
  await p.route(/fonts\.googleapis\.com/, (r) => r.fulfill({ status: 200, contentType: "text/css", headers: { "Access-Control-Allow-Origin": "*" }, body: fontCss }));
  await p.route(/fonts\.gstatic\.com\/local\/(\d+)/, (r) => {
    const w = r.request().url().match(/local\/(\d+)/)[1];
    r.fulfill({ status: 200, contentType: "font/woff2", headers: { "Access-Control-Allow-Origin": "*" }, body: fs.readFileSync(path.join(FONTS, `open-sans-latin-${w}-normal.woff2`)) });
  });
}

/** Element ekran görüntüsü + görsel alanlarının (maske) element-göreli kutuları. */
async function shoot(p, loc, file, imgSel) {
  await loc.scrollIntoViewIfNeeded();
  await p.waitForTimeout(600);
  const box = await loc.boundingBox();
  const masks = await loc.evaluate((el, sel) => {
    const r0 = el.getBoundingClientRect();
    const out = [];
    el.querySelectorAll(sel).forEach((e) => {
      const r = e.getBoundingClientRect();
      if (r.width > 2 && r.height > 2) out.push([r.left - r0.left, r.top - r0.top, r.width, r.height]);
    });
    return out;
  }, imgSel);
  const buf = await loc.screenshot({ path: file, animations: "disabled" });
  return { buf, box, masks };
}

/** Tarayıcı içinde piksel karşılaştırma: farklı piksel oranı (%). Boyut farkı fark sayılır. */
async function diffPct(page, a, b) {
  return page.evaluate(async ([a64, b64, masks]) => {
    const load = (s) => new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.src = `data:image/png;base64,${s}`; });
    const [ia, ib] = await Promise.all([load(a64), load(b64)]);
    const W = Math.max(ia.width, ib.width); const Hh = Math.max(ia.height, ib.height);
    const ctx = (img) => { const c = document.createElement("canvas"); c.width = W; c.height = Hh; const x = c.getContext("2d"); x.fillStyle = "#ff00ff"; x.fillRect(0, 0, W, Hh); x.drawImage(img, 0, 0); return x.getImageData(0, 0, W, Hh).data; };
    const da = ctx(ia); const db = ctx(ib);
    const masked = new Uint8Array(W * Hh);
    masks.forEach(([x, y, w, h]) => { for (let yy = Math.max(0, Math.floor(y)); yy < Math.min(Hh, Math.ceil(y + h)); yy += 1) for (let xx = Math.max(0, Math.floor(x)); xx < Math.min(W, Math.ceil(x + w)); xx += 1) masked[yy * W + xx] = 1; });
    // Kenar yumuşatma (anti-aliasing) / kesirli konum toleransı: bir piksel, diğer görüntüde 3×3 komşuluğunda eşi
    // (kanal farkı toplamı ≤ 60) varsa aynı sayılır (pixelmatch'in AA algısına benzer, ≤1 px kayma).
    const near = (o, q) => Math.abs(da[o] - db[q]) + Math.abs(da[o + 1] - db[q + 1]) + Math.abs(da[o + 2] - db[q + 2]) <= 60;
    let diff = 0; let total = 0;
    for (let y = 1; y < Hh - 1; y += 1) for (let x = 1; x < W - 1; x += 1) {
      const i = y * W + x; if (masked[i]) continue;
      total += 1;
      const o = i * 4;
      let ok = false;
      for (let dy = -1; dy <= 1 && !ok; dy += 1) for (let dx = -1; dx <= 1 && !ok; dx += 1) ok = near(o, ((y + dy) * W + (x + dx)) * 4);
      if (!ok) diff += 1;
    }
    return { pct: total ? (diff / total) * 100 : 0, size: [ia.width, ia.height, ib.width, ib.height] };
  }, [a.buf.toString("base64"), b.buf.toString("base64"), [...a.masks, ...b.masks]]);
}

let failures = 0;
const results = [];
async function step(name, fn) {
  try { await fn(); console.log(`✓ ${name}`); } catch (e) { failures += 1; console.log(`✕ ${name}\n   ${e && e.message ? e.message.split("\n").slice(0, 4).join("\n   ") : e}`); }
}

async function publishOnly(block) {
  const cur = await api("GET", "/page-design/home");
  const rev = cur.data.draft ? cur.data.draft.rev : null;
  const put = await api("PUT", "/page-design/home/draft", { blocks: [block] }, rev !== null ? { "If-Match": String(rev) } : {});
  assert.strictEqual(put.status, 200, `taslak kaydı: ${JSON.stringify(put.data).slice(0, 300)}`);
  assert.deepStrictEqual(put.data.errors || [], [], `doğrulama hataları: ${JSON.stringify(put.data.errors)}`);
  const pub = await api("POST", "/page-design/home/publish");
  assert.strictEqual(pub.status, 200, `yayın: ${JSON.stringify(pub.data).slice(0, 300)}`);
}

(async () => {
  const only = process.argv.slice(2);
  const browser = await chromium.launch();
  const original = (await api("GET", "/page-design/home")).data.published.blocks;
  const cmpPage = await (await browser.newContext()).newPage();
  for (const c of CASES.filter((x) => !only.length || only.includes(x.key))) {
    const block = { id: `grpa-${c.key}`, type: c.key, title: c.name, is_active: true, settings: await resolveImages({ ...c.settings, _reveal: { enabled: false } }) };
    await step(`${c.name}: yayınla`, () => publishOnly(block));
    for (const w of [1440, 390]) {
      await step(`${c.name} @${w}: şablon bölümüyle görsel eşdeğerlik (≤%${THRESHOLD})`, async () => {
        const tctx = await browser.newContext({ viewport: { width: w, height: 900 } });
        const tp = await tctx.newPage();
        await routeTemplate(tp);
        await tp.goto(`file://${c.tpl}`, { waitUntil: "load" });
        // dikey menü (vitrinde kategori sayısı farklı) iki tarafta da gizlenir
        await tp.addStyleTag({ content: `.animate-in-view{opacity:1!important;animation:none!important}.vertical-menu.make-absolute{visibility:hidden!important}.js-go-to,.u-go-to{display:none!important}${c.tplCss || ""}` });
        await tp.evaluate(() => { document.querySelectorAll("img[data-echo]").forEach((i) => { i.src = i.getAttribute("data-echo"); }); });
        await tp.waitForTimeout(2600);
        const ta = await shoot(tp, tp.locator(`${c.sel} >> visible=true`).first(), path.join(OUT, `${c.key}-tpl-${w}.png`), c.tplMask || ".js-countdown");
        await tctx.close();

        const sctx = await browser.newContext({ viewport: { width: w, height: 900 } });
        await sctx.addInitScript(() => { try { localStorage.setItem("store_cookie_consent", JSON.stringify({ necessary: true, analytics: false, marketing: false, ts: new Date().toISOString(), v: 1 })); } catch (e) { /* yoksay */ } });
        const sp = await sctx.newPage();
        await sp.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
        await sp.addStyleTag({ content: `.el-sticky-bar{display:none!important}[data-testid="vertical-menu"]{display:none!important}${c.sfCss || ""}` });
        await sp.evaluate(() => window.dispatchEvent(new Event("resize")));
        await sp.waitForTimeout(800);
        const blockLoc = sp.locator(`[data-block-type="${c.key}"]`).first();
        const sa = await shoot(sp, c.sfInner ? blockLoc.locator(c.sfInner).first() : blockLoc, path.join(OUT, `${c.key}-sf-${w}.png`), c.sfMask || "[data-testid=deal-countdown], .js-countdown");
        // §9: görünür metinlerin hepsi panelden (data-pd-field) ya da katalogdan (data-pd-data)
        const hard = await blockLoc.evaluate((root) => {
          const out = []; const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n = tw.nextNode();
          while (n) { const t = n.textContent.replace(/\s+/g, " ").trim(); const el = n.parentElement;
            if (t && !/^[\s:·|/–—%₺$,.\-+×x\d]*$/.test(t) && el.offsetParent !== null && !el.closest("[data-pd-field],[data-pd-data],[data-pd-placeholder],.product-item,.sr-only")) out.push(t);
            n = tw.nextNode(); }
          return out;
        });
        await sctx.close();
        assert.deepStrictEqual(hard, [], "sabit kodlu görünür metin");
        const d = await diffPct(cmpPage, ta, sa);
        results.push({ block: c.name, width: w, diff: Number(d.pct.toFixed(2)), tpl: [Math.round(ta.box.width), Math.round(ta.box.height)], sf: [Math.round(sa.box.width), Math.round(sa.box.height)] });
        console.log(`   fark %${d.pct.toFixed(2)} — şablon ${d.size[0]}×${d.size[1]}, vitrin ${d.size[2]}×${d.size[3]}`);
        if ((c.tplBroken || []).includes(w)) { console.log(`   (bilgi) şablonun ${w} px görünümü JS durumundan dolayı karşılaştırılamaz: ${c.tplBrokenWhy}`); return; }
        assert(d.pct <= THRESHOLD, `piksel farkı %${d.pct.toFixed(2)} > %${THRESHOLD}`);
      });
    }
    if (c.edit) {
      await step(`${c.name}: panelde (API) değişen alan vitrine yansır`, async () => {
        const st = JSON.parse(JSON.stringify(block.settings));
        let o = st; c.edit.path.slice(0, -1).forEach((k) => { o = o[k]; });
        o[c.edit.path[c.edit.path.length - 1]] = c.edit.value;
        await publishOnly({ ...block, settings: st });
        const sp = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
        await sp.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
        const f = c.edit.path.join(".");
        const txt = await sp.locator(`[data-block-type="${c.key}"] [data-pd-field="${f}"]`).first().textContent();
        assert.strictEqual(txt.trim(), c.edit.value);
        await sp.context().close();
      });
    }
  }
  // özgün yayını geri yükle
  if (original.length && !process.env.KEEP) {
    const cur = await api("GET", "/page-design/home");
    await api("PUT", "/page-design/home/draft", { blocks: original }, cur.data.draft ? { "If-Match": String(cur.data.draft.rev) } : {});
    await api("POST", "/page-design/home/publish");
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, "results.json"), JSON.stringify(results, null, 2));
  console.table(results);
  console.log(failures ? `\n${failures} adım başarısız` : "\nTüm adımlar geçti");
  process.exit(failures ? 1 : 0);
})();
