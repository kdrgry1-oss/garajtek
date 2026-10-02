// Sayfa Tasarımı — Grup D (kategori, marka, kenar çubuğu, içerik blokları) görsel eşdeğerlik + panel→vitrin testleri.
//
//   BASE=http://localhost:8468 API=http://localhost:8467/api TOKEN=<admin jwt> \
//   TEMPLATE=/yol/electro-zip-açılmış  node e2e/pageblocks/group_d.e2e.js [blok_anahtarı | durum adı …]
//   (Playwright: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers; paket yolu PW_MODULE; ekran görüntüleri OUT klasörüne)
//
// Her durum için:
//   1) Şablon sayfası açılır, ilgili bölümün İÇERİĞİ (metinler, ikonlar, görsel yolları) DOM'dan okunur → blok ayarlarına
//      çevrilir (görseller yükleme API'siyle vitrine aynen verilir) → taslağa yazılır → yayınlanır (yönetici API'si).
//   2) Vitrin (production build) ve şablon bölümü aynı genişlikte (1440 / 390) görüntülenir, tarayıcı içinde piksel
//      karşılaştırılır (≤ THRESHOLD %, varsayılan 2). Şablonun yükleniyor-iskeleti (bg-animation) olan öğeler iki yanda maskelenir.
//   3) §9: blok içindeki görünür metinlerin hepsi data-pd-field (panel) ya da data-pd-data (katalog) taşır.
//   4) Panelden (API) değiştirilen bir alan vitrine yansır.
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { chromium } = require(process.env.PW_MODULE || "/opt/node22/lib/node_modules/playwright");

const BASE = process.env.BASE;
const API = process.env.API || `${BASE}/api`;
const TOKEN = process.env.TOKEN;
const TPL = process.env.TEMPLATE;
const OUT = process.env.OUT || path.join(require("os").tmpdir(), "pd-group-d");
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
const T2 = (f) => path.join(TPL, "2.0", "html", "home", f);

const uploaded = {};
async function upload(file) {
  if (uploaded[file]) return uploaded[file];
  const ext = path.extname(file).slice(1).toLowerCase();
  const fd = new FormData();
  fd.append("file", new Blob([fs.readFileSync(file)], { type: ext === "png" ? "image/png" : "image/jpeg" }), path.basename(file));
  const r = await fetch(`${API}/upload/image`, { method: "POST", headers: { Authorization: `Bearer ${TOKEN}` }, body: fd });
  const d = await r.json();
  assert(r.ok, `yükleme: ${JSON.stringify(d)}`);
  uploaded[file] = d.url || `/api/upload/files/${d.path}`;
  return uploaded[file];
}
/** {$img: "<şablon sayfasına göre göreli yol>"} → yüklenmiş görsel değeri. */
async function resolveImages(v, base) {
  if (Array.isArray(v)) return Promise.all(v.map((x) => resolveImages(x, base)));
  if (v && typeof v === "object") {
    if (v.$img) { const { $img, ...rest } = v; return { url: await upload(path.resolve(base, $img)), alt: "", ...rest }; }
    const o = {};
    for (const k of Object.keys(v)) o[k] = await resolveImages(v[k], base);
    return o;
  }
  return v;
}

// ---------------------------------------------------------------- durumlar
// fromTpl: şablon sayfasında (tarayıcıda) çalışır, bölümün içeriğini blok ayarlarına çevirir. src → {$img}.
const CASES = [
  {
    key: "brands_carousel", name: "markalar v1 (home.html)", id: "brands-v1", tpl: T1("home.html"), sel: "#owl-brands", sfInner: ".pd-brands__owl",
    fromTpl: () => ({
      _variant: "v1", source: "manual", grayscale: false,
      brands: [...document.querySelectorAll("#owl-brands .owl-item:not(.cloned) .item, #owl-brands > .item")].map((it) => ({
        logo: { $img: it.querySelector("img").getAttribute("src") }, name: it.querySelector("h4").textContent.trim(), link: { kind: "url", url: "/markalar", new_tab: false } })),
    }),
    edit: { path: ["brands", 0, "name"], value: "Panelden Marka" },
  },
  {
    key: "brands_carousel", name: "markalar v2.0 (index)", id: "brands-v2", tpl: T2("index.html"), sel: ".mb-8 > .py-2.border-top.border-bottom", sfInner: ".pd-brands__band",
    fromTpl: (sel) => ({
      _variant: "v2", source: "manual", grayscale: true, show_name_overlay: false,
      brands: [...document.querySelector(sel).querySelectorAll(".js-slide:not(.slick-cloned) img")].map((im, i) => ({ logo: { $img: im.getAttribute("src") }, name: `Marka ${i + 1}`, link: { kind: "url", url: "/markalar", new_tab: false } })),
    }),
  },
  {
    key: "home_list_categories", name: "popüler kategoriler v1 (home-v3)", id: "hlc-v1", tpl: T1("home-v3.html"), sel: "section.home-list-categories", sfInner: ".pd-hlc",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      return {
        _variant: "v1", source: "manual", see_all_text: "See all",
        header: { title: s.querySelector("header h2").textContent.trim(), tag: "h2", right: "none", underline: true },
        categories: [...s.querySelectorAll("li.category")].map((li) => ({
          name_override: li.querySelector(".media-heading").textContent.trim(),
          image_override: { $img: li.querySelector(".media-left img").getAttribute("data-echo") || li.querySelector(".media-left img").getAttribute("src") },
          link_override: { kind: "url", url: "/kategori", new_tab: false }, sub_mode: "manual",
          sub_links: [...li.querySelectorAll(".sub-categories a")].map((a) => ({ label: a.textContent.trim(), link: { kind: "url", url: "/alt", new_tab: false } })),
          see_all_text: li.querySelector(".see-all").textContent.trim(),
        })),
      };
    },
    edit: { path: ["categories", 0, "name_override"], value: "Panelden Kategori" },
  },
  {
    key: "home_list_categories", name: "popüler kategoriler v2.0 (home-v3)", id: "hlc-v2", tplBroken: [390],
    tplBrokenWhy: "şablonun ilk sütunu yükleniyor iskeleti; mobilde iskelet satırı gerçek karttan uzun olduğu için satır yükseklikleri kayar", tpl: T2("home-v3.html"), sel: ".mb-2:has(> .border-bottom > .section-title__full)", sfInner: ".pd-hlc",
    // şablonun ilk sütunu yükleniyor iskeleti → iki yanda da ilk sütun maskelenir
    tplMask: ".row > .col-4:first-child", sfMask: ".row > .pd-hlc__col2:first-child",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      const cols = [...s.querySelectorAll(".row.align-items-start > .col-4")].filter((c) => c.querySelector("h4"));
      const cat = (c) => ({
        name_override: c.querySelector("h4").textContent.trim(), image_override: { $img: c.querySelector("img").getAttribute("src") },
        link_override: { kind: "url", url: "/kategori", new_tab: false }, sub_mode: "manual",
        sub_links: [...c.querySelectorAll("ul a")].map((a) => ({ label: a.textContent.trim(), link: { kind: "url", url: "/alt", new_tab: false } })),
        see_all_text: (c.querySelector("a.text-right") || {}).textContent.trim(),
      });
      return { _variant: "v2", source: "manual", see_all_text: "See all", columns: "3",
        header: { title: s.querySelector("h3").textContent.trim(), tag: "h2", right: "none", underline: true },
        categories: [cat(cols[0]), ...cols.map(cat)] };
    },
  },
  {
    key: "category_icon_cards", name: "kategori kartları v4 (home-v4)", id: "cic-v4", tpl: T2("home-v4.html"), sel: "div.mb-6.bg-gray-7.py-6",
    tplMask: ".row > div:first-child", sfMask: ".pd-cic__col:first-child",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      const tiles = [...s.querySelectorAll(".row > div")].filter((c) => c.querySelector("img")).map((c) => ({
        image: { $img: c.querySelector("img").getAttribute("src") }, label: c.querySelector("h6").textContent.trim(), link: { kind: "url", url: "/kategori", new_tab: false } }));
      return { _variant: "v4", header: { title: s.querySelector("h3").textContent.trim(), tag: "h2", right: "none", underline: true }, tiles: [tiles[0], ...tiles] };
    },
    edit: { path: ["tiles", 1, "label"], value: "Panelden Kart" },
  },
  {
    key: "category_icon_cards", name: "kategori kartları v5 (home-v5)", id: "cic-v5", tpl: T2("home-v5.html"), sel: ".mb-6:has(.max-width-148)", sfInner: ".pd-cic",
    tplMask: ".row > div:first-child", sfMask: ".pd-cic__col:first-child",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      const tiles = [...s.querySelectorAll(".row > div")].filter((c) => c.querySelector("img")).map((c) => ({
        image: { $img: c.querySelector("img").getAttribute("src") }, label: c.querySelector("h4").textContent.trim(), link: { kind: "url", url: "/kategori", new_tab: false } }));
      return { _variant: "v5", header: { title: "" }, tiles: [tiles[0], ...tiles], _section: { background: "", padding: { desktop: { top: 0, bottom: 0 }, tablet: { top: 0, bottom: 0 }, mobile: { top: 0, bottom: 0 } } } };
    },
  },
  {
    key: "categories_icon_carousel", name: "ikonlu kategori karuseli v8 (home-v8)", tpl: T2("home-v8.html"), sel: "div.border-top.bg-primary.border-color-8", sfInner: ".pd-cicar--v8",
    fromTpl: (sel) => ({
      _variant: "v8",
      items: [...document.querySelector(sel).querySelectorAll(".js-slide:not(.slick-cloned) a")].map((a) => ({
        icon: { icon: a.querySelector("i").className.replace(/\s*font-size-\d+/, "").trim() }, label: a.querySelector("h6").textContent.trim(), link: { kind: "url", url: "/kategori", new_tab: false } })),
    }),
    edit: { path: ["items", 0, "label"], value: "Panelden İkon" },
  },
  {
    key: "categories_brands_card", name: "markalar + kategori kutuları (home-v11)", tpl: T2("home-v11.html"), sel: ".borders-radius-20.box-shadow-3", sfInner: ".pd-cbc",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      return {
        brands_label: s.querySelector("h6").textContent.trim(), brands_source: "manual", overlap_hero: false,
        brands: [...s.querySelectorAll("a.link-hover__brand img")].map((im, i) => ({ logo: { $img: im.getAttribute("src") }, name: `Marka ${i + 1}`, link: { kind: "url", url: "/markalar", new_tab: false } })),
        more_brands: { text: s.querySelector("a.ml-auto").textContent.trim(), link: { kind: "url", url: "/markalar", new_tab: false } },
        show_more_link: true,
        boxes: [...s.querySelectorAll(".row.no-gutters > div")].map((c) => ({
          header_image: { $img: c.querySelector("img").getAttribute("src") }, title: c.querySelector("h6").textContent.trim(), link: { kind: "url", url: "/kategori", new_tab: false },
          links: [...c.querySelectorAll("li a")].filter((a) => a.textContent.trim() !== "...").map((a) => ({ label: a.textContent.trim(), link: { kind: "url", url: "/alt", new_tab: false } })),
        })),
      };
    },
    edit: { path: ["boxes", 0, "title"], value: "Panelden Kutu" },
  },
  {
    key: "category_list_image_carousel", name: "kategori listesi + görsel (home-v9)", tpl: T2("home-v9.html"), sel: ".container.position-relative.mb-5.pb-1", sfInner: ".container",
    tplCss: ".slick-arrow{display:none!important}", sfCss: "[data-testid=header-arrows]{visibility:hidden!important}",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      const L = (a) => ({ label: a.textContent.trim(), link: { kind: "url", url: "/kategori", new_tab: false } });
      return {
        header: { title: s.querySelector("h3").textContent.trim(), tag: "h2", right: "arrows", underline: true },
        slides: [...s.querySelectorAll(".js-slide:not(.slick-cloned)")].map((sl) => ({
          groups: [...sl.querySelectorAll(".bg-gray-7 > .mb-1")].map((g) => ({ title: g.querySelector("h6").textContent.trim(), link: { kind: "url", url: "/kategori", new_tab: false }, links: [...g.querySelectorAll("ul a")].map(L) })),
          links: [...sl.querySelectorAll(".list-group a")].map(L), image: { $img: sl.querySelector("img").getAttribute("src") }, link: { kind: "url", url: "/kampanya", new_tab: false }, alt: "",
        })),
      };
    },
    edit: { path: ["slides", 0, "links", 0, "label"], value: "Panelden Bağlantı" },
  },
  {
    key: "popular_search_tags", name: "popüler aramalar (home-v8)", tpl: T2("home-v8.html"), sel: ".mb-6:has(.btn-soft-secondary)", sfInner: ".pd-pst",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      return { title: s.querySelector("h3").textContent.trim(), tags: [...s.querySelectorAll("a.btn")].map((a) => ({ label: a.textContent.trim(), link: { kind: "url", url: "/arama", new_tab: false } })) };
    },
    edit: { path: ["tags", 0, "label"], value: "Panelden Etiket" },
  },
  {
    key: "sidebar_image_ad", name: "kenar reklam görseli (home-v2)", tpl: T2("home-v2.html"), sel: 'aside:has(img[src*="270X428"])', sfInner: ".pd-sad", widths: [1440],
    sfCss: ".pd-block--sidebar_image_ad > *{width:270px!important;max-width:270px!important}",
    fromTpl: (sel) => ({ image: { $img: document.querySelector(`${sel} img`).getAttribute("src") }, link: { kind: "url", url: "/kampanya", new_tab: false }, alt: "" }),
  },
  {
    key: "sidebar_features", name: "kenar avantajlar (home-v2)", tpl: T2("home-v2.html"), sel: "aside.mb-8:has(.u-avatar) > div", sfInner: ".pd-sfe > div", widths: [1440],
    sfCss: ".pd-block--sidebar_features > *{width:270px!important;max-width:270px!important}",
    fromTpl: (sel) => ({
      items: [...document.querySelectorAll(`${sel} .media`)].map((m) => ({ icon: { icon: [...m.querySelector("i").classList].filter((c) => /^ec/.test(c)).join(" ") },
        strong_text: m.querySelector("span").textContent.trim(), text: m.querySelector(".text-secondary").textContent.trim(), link: { kind: "none", url: "", new_tab: false } })),
    }),
    edit: { path: ["items", 0, "strong_text"], value: "Panelden Avantaj" },
  },
  { key: "sidebar_product_list", name: "kenar ürün listesi", noCompare: true, sfInner: ".pd-spl", settings: { title: "Son Eklenenler" }, edit: { path: ["title"], value: "Panelden Liste" } },
  { key: "sidebar_products_carousel", name: "kenar ürün karuseli", noCompare: true, sfInner: ".pd-spc", settings: {}, edit: { path: ["title"], value: "Panelden Karusel" } },
  {
    key: "sidebar_blog_carousel", name: "kenar blog karuseli (galeride gizli)", noCompare: true, sfInner: ".pd-sbc",
    settings: { posts: [1, 2, 3].map((i) => ({ image: { $img: "2.0/assets/img/270X180/img1.jpg" }, category: "Atölye Rehberi", title: `Lift bakımı rehberi ${i}`, meta: `${i} yorum`, link: { kind: "url", url: "/blog", new_tab: false } })) },
    edit: { path: ["posts", 0, "title"], value: "Panelden Yazı" },
  },
  {
    key: "page_hero", name: "sayfa başlığı (about)", tpl: T2("about.html"), sel: ".bg-img-hero.mb-14", sfInner: ".pd-ph",
    fromTpl: (sel) => {
      const s = document.querySelector(sel);
      // şablon görseli "1920x600" (küçük x) diye çağırır, klasör "1920X600" → şablonda arka plan görseli yüklenmez; vitrinde de görsel yok
      return { background: null, background_color: "", title: s.querySelector("h1").textContent.trim(), text: s.querySelector("p").textContent.trim() };
    },
    edit: { path: ["title"], value: "Panelden Başlık" },
  },
  {
    key: "info_cards", name: "bilgi kartları (about)", tpl: T2("about.html"), sel: ".container > .row:has(> .col-md-4 > .card)", sfInner: ".pd-ic",
    fromTpl: (sel) => ({
      items: [...document.querySelectorAll(`${sel} .card`)].map((c) => ({ image: { $img: c.querySelector("img").getAttribute("src") }, title: c.querySelector("h5").textContent.trim(),
        text: c.querySelector("p").textContent.trim(), link: { kind: "none", url: "", new_tab: false } })),
    }),
    edit: { path: ["items", 0, "title"], value: "Panelden Kart" },
  },
  {
    key: "team_grid", name: "ekip ızgarası (about)", tpl: T2("about.html"), sel: ".bg-gray-1.py-12",
    fromTpl: (sel) => ({
      members: [...document.querySelectorAll(`${sel} .text-center`)].map((c) => ({ photo: { $img: c.querySelector("img").getAttribute("src") }, name: c.querySelector("h2").textContent.trim(),
        role: ((c.querySelector("span") || {}).textContent || "").trim(), link: { kind: "none", url: "", new_tab: false } })),
    }),
    edit: { path: ["members", 0, "role"], value: "Panelden Görev" },
  },
  {
    key: "accordion", name: "akordeon (about)", tpl: T2("about.html"), sel: "#basicsAccordion1", sfInner: ".about-accordion",
    sfCss: "@media (min-width:992px){.pd-acc > div > *{margin-left:3.5rem}}",
    fromTpl: (sel) => ({
      width: "narrow", open_index: 1, title: document.querySelector(".col-lg-5 > .ml-lg-8 h3").textContent.trim(),
      items: [...document.querySelectorAll(`${sel} .card`)].map((c) => ({ question: c.querySelector(".card-btn").textContent.trim(), answer: c.querySelector(".card-body p").textContent.trim() })),
    }),
    edit: { path: ["items", 0, "question"], value: "Panelden Soru" },
  },
  {
    key: "text_columns", name: "metin sütunları (about)", tpl: T2("about.html"), sel: ".col-lg-7 > .row", sfInner: ".pd-tc .col-lg-7 > .row",
    fromTpl: (sel) => ({
      width: "wide", columns: "2", title_color: "#434343", text_color: "#333e48",
      items: [...document.querySelector(sel).children].map((c) => ({ title: c.querySelector("h3").textContent.trim(), text: c.querySelector("p").textContent.trim() })),
    }),
    edit: { path: ["items", 0, "title"], value: "Panelden Sütun" },
  },
];

// ---------------------------------------------------------------- yardımcılar (grup A ile aynı ölçüt)
const fontCss = [300, 400, 600, 700, 800].map((w) => `@font-face{font-family:"Open Sans";font-style:normal;font-weight:${w};src:url("https://fonts.gstatic.com/local/${w}.woff2") format("woff2")}`).join("\n");

async function routeTemplate(p) {
  await p.route(/^https?:\/\//, (r) => r.abort());
  await p.route(/fonts\.googleapis\.com/, (r) => r.fulfill({ status: 200, contentType: "text/css", headers: { "Access-Control-Allow-Origin": "*" }, body: fontCss }));
  await p.route(/fonts\.gstatic\.com\/local\/(\d+)/, (r) => {
    const w = r.request().url().match(/local\/(\d+)/)[1];
    r.fulfill({ status: 200, contentType: "font/woff2", headers: { "Access-Control-Allow-Origin": "*" }, body: fs.readFileSync(path.join(FONTS, `open-sans-latin-${w}-normal.woff2`)) });
  });
}

async function openTemplate(browser, c, w) {
  const tctx = await browser.newContext({ viewport: { width: w, height: 900 } });
  const tp = await tctx.newPage();
  await routeTemplate(tp);
  await tp.goto(`file://${c.tpl}`, { waitUntil: "load" });
  await tp.addStyleTag({ content: `.animate-in-view{opacity:1!important;animation:none!important}.vertical-menu.make-absolute{visibility:hidden!important}.js-go-to,.u-go-to{display:none!important}${c.tplCss || ""}` });
  await tp.evaluate(() => { document.querySelectorAll("img[data-echo]").forEach((i) => { i.src = i.getAttribute("data-echo"); }); });
  await tp.waitForTimeout(2600);
  return { tctx, tp };
}

async function shoot(p, loc, file, maskSel) {
  await loc.scrollIntoViewIfNeeded();
  await p.waitForTimeout(600);
  const box = await loc.boundingBox();
  const masks = maskSel ? await loc.evaluate((el, sel) => {
    const r0 = el.getBoundingClientRect();
    const out = [];
    el.querySelectorAll(sel).forEach((e) => {
      const r = e.getBoundingClientRect();
      if (r.width > 2 && r.height > 2) out.push([r.left - r0.left, r.top - r0.top, r.width, r.height]);
    });
    return out;
  }, maskSel) : [];
  const buf = await loc.screenshot({ path: file, animations: "disabled" });
  return { buf, box, masks };
}

async function diffPct(page, a, b) {
  return page.evaluate(async ([a64, b64, masks]) => {
    const load = (s) => new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.src = `data:image/png;base64,${s}`; });
    const [ia, ib] = await Promise.all([load(a64), load(b64)]);
    const W = Math.max(ia.width, ib.width); const Hh = Math.max(ia.height, ib.height);
    const ctx = (img) => { const c = document.createElement("canvas"); c.width = W; c.height = Hh; const x = c.getContext("2d"); x.fillStyle = "#ff00ff"; x.fillRect(0, 0, W, Hh); x.drawImage(img, 0, 0); return x.getImageData(0, 0, W, Hh).data; };
    const da = ctx(ia); const db = ctx(ib);
    const masked = new Uint8Array(W * Hh);
    masks.forEach(([x, y, w, h]) => { for (let yy = Math.max(0, Math.floor(y)); yy < Math.min(Hh, Math.ceil(y + h)); yy += 1) for (let xx = Math.max(0, Math.floor(x)); xx < Math.min(W, Math.ceil(x + w)); xx += 1) masked[yy * W + xx] = 1; });
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

async function openStore(browser, w, css) {
  const sctx = await browser.newContext({ viewport: { width: w, height: 900 } });
  await sctx.addInitScript(() => { try { localStorage.setItem("store_cookie_consent", JSON.stringify({ necessary: true, analytics: false, marketing: false, ts: new Date().toISOString(), v: 1 })); } catch (e) { /* yoksay */ } });
  const sp = await sctx.newPage();
  await sp.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
  await sp.addStyleTag({ content: `.el-sticky-bar{display:none!important}[data-testid="vertical-menu"]{display:none!important}${css || ""}` });
  await sp.evaluate(() => window.dispatchEvent(new Event("resize")));
  await sp.waitForTimeout(900);
  return { sctx, sp };
}

const hardTexts = (root) => {
  const out = []; const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n = tw.nextNode();
  while (n) { const t = n.textContent.replace(/\s+/g, " ").trim(); const el = n.parentElement;
    if (t && !/^[\s:·|/–—%₺$,.\-+×x\d]*$/.test(t) && el.offsetParent !== null && !el.closest("[data-pd-field],[data-pd-data],[data-pd-placeholder],.product-item,.sr-only")) out.push(t);
    n = tw.nextNode(); }
  return out;
};

(async () => {
  const only = process.argv.slice(2);
  const browser = await chromium.launch();
  const original = (await api("GET", "/page-design/home")).data.published.blocks;
  const cmpPage = await (await browser.newContext()).newPage();
  for (const c of CASES.filter((x) => !only.length || only.includes(x.key) || only.includes(x.name) || only.includes(x.id))) {
    let settings = c.settings || {};
    if (c.fromTpl) {
      const { tctx, tp } = await openTemplate(browser, c, 1440);
      settings = await tp.evaluate(`(${c.fromTpl.toString()})(${JSON.stringify(c.sel)})`);
      await tctx.close();
      settings = await resolveImages(settings, path.dirname(c.tpl));
    }
    if (!c.fromTpl) settings = await resolveImages(settings, TPL);
    const block = { id: `grpd-${c.key}`, type: c.key, title: c.name, is_active: true, settings: { ...settings, _reveal: { enabled: false } } };
    await step(`${c.name}: yayınla`, () => publishOnly(block));
    for (const w of (c.noCompare ? [1440] : (c.widths || [1440, 390]))) {
      await step(`${c.name} @${w}: ${c.noCompare ? "vitrinde çizilir + sabit metin yok" : `şablon bölümüyle görsel eşdeğerlik (≤%${THRESHOLD})`}`, async () => {
        let ta = null;
        if (!c.noCompare) {
          const { tctx, tp } = await openTemplate(browser, c, w);
          ta = await shoot(tp, tp.locator(`${c.sel} >> visible=true`).first(), path.join(OUT, `${c.id || c.key}-${w}-tpl.png`), c.tplMask);
          await tctx.close();
        }
        const { sctx, sp } = await openStore(browser, w, c.sfCss);
        const blockLoc = sp.locator(`[data-block-type="${c.key}"]`).first();
        await blockLoc.waitFor({ state: "attached", timeout: 10000 });
        const target = c.sfInner ? blockLoc.locator(c.sfInner).first() : blockLoc;
        const sa = await shoot(sp, target, path.join(OUT, `${c.id || c.key}-${w}-sf.png`), c.sfMask);
        const hard = await blockLoc.evaluate(hardTexts);
        await sctx.close();
        assert.deepStrictEqual(hard, [], "sabit kodlu görünür metin");
        if (c.noCompare) { assert(sa.box && sa.box.height > 20, "blok boş çizildi"); return; }
        const d = await diffPct(cmpPage, ta, sa);
        results.push({ block: c.name, width: w, diff: Number(d.pct.toFixed(2)), tpl: [Math.round(ta.box.width), Math.round(ta.box.height)], sf: [Math.round(sa.box.width), Math.round(sa.box.height)] });
        console.log(`   fark %${d.pct.toFixed(2)} — şablon ${d.size[0]}×${d.size[1]}, vitrin ${d.size[2]}×${d.size[3]}`);
        if ((c.tplBroken || []).includes(w)) { console.log(`   (bilgi) şablonun ${w} px görünümü karşılaştırılamaz: ${c.tplBrokenWhy}`); return; }
        assert(d.pct <= THRESHOLD, `piksel farkı %${d.pct.toFixed(2)} > %${THRESHOLD}`);
      });
    }
    if (c.edit) {
      await step(`${c.name}: panelde (API) değişen alan vitrine yansır`, async () => {
        const st = JSON.parse(JSON.stringify(block.settings));
        let o = st; c.edit.path.slice(0, -1).forEach((k) => { o = o[k]; });
        o[c.edit.path[c.edit.path.length - 1]] = c.edit.value;
        await publishOnly({ ...block, settings: st });
        const { sctx, sp } = await openStore(browser, 1440);
        const f = c.edit.path.join(".");
        const txt = await sp.locator(`[data-block-type="${c.key}"] [data-pd-field="${f}"]`).first().textContent();
        assert.strictEqual(txt.trim(), c.edit.value);
        await sctx.close();
      });
    }
  }
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
