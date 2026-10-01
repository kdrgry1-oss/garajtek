/**
 * Vitrin teması CSS'ini (ThemeForest "Electro" v2.0 HTML şablonunun CSS'i) vitrine uyarlar →
 * public/electro/electro.css (TAM sürüm, küçültülmüş).
 *
 * - Tüm kurallar `.electro` kapsamına alınır (html/body/:root → .electro). Böylece Bootstrap 4
 *   tabanlı tema CSS'i yalnız `.electro` sarmalayıcısı içindeki vitrin bileşenlerini etkiler;
 *   Tailwind kullanan admin paneli ve ödeme ekranına SIZMAZ. (Tailwind preflight da `.electro`
 *   dışına kapsamlıdır: scripts/tailwind-scoped-preflight.js.)
 * - BUDAMA (purge) YAPILMAZ: önceki sürüm yalnız kaynak kodda geçen sınıfları tutuyordu; dinamik
 *   üretilen sınıflar, panelden girilen CMS HTML'i, Bootstrap ızgara/yardımcı sınıfları ve JS ile
 *   eklenen durum sınıfları (show/active/open…) kaybolup sayfalar "bozuk" görünüyordu.
 *   Tam sürüm ≈ 100 KB gzip (şablonun kendi theme.css'i ile aynı kapsam).
 * - Tema sarısı (#fed700) `var(--electro-primary)` yapılır → `.electro{--electro-primary:#xxxxxx}`.
 * - Yazı tipi Open Sans KENDİ SUNUCUMUZDAN (public/electro/fonts, latin + latin-ext → Türkçe
 *   karakterler) yüklenir; Google Fonts bağımlılığı yok.
 * - Font yolları göreli (fonts/…, webfonts/…) → /electro/electro.css konumunda nginx ile çalışır.
 *
 * Kullanım:  node scripts/build-electro-css.js /path/to/electro/2.0
 * (Tema kaynağı repoda tutulmaz; çıktı + fontlar public/electro altında versiyonlanır.
 *  Önbellek kırma: craco.config.js dosya içeriğinin özetini REACT_APP_ELECTRO_CSS_VER yapar.)
 */
const fs = require("fs");
const path = require("path");
const postcss = require("postcss");
const cssnano = require("cssnano");

const SRC = process.argv[2] || process.env.ELECTRO_SRC;
if (!SRC) { console.error("Kullanım: node scripts/build-electro-css.js <electro/2.0 klasörü>"); process.exit(1); }
const A = (p) => path.join(SRC, "assets", p);
const OUT_DIR = path.join(__dirname, "..", "public", "electro");
const SCOPE = ".electro";

const parts = [
  ["vendor/hs-megamenu/src/hs.megamenu.css", ""],
  ["vendor/bootstrap-select/dist/css/bootstrap-select.min.css", ""],
  ["css/font-electro.css", "electro"],
  ["vendor/font-awesome/css/fontawesome-all.min.css", "fa"],
  ["css/theme.css", ""],
];

// Open Sans (OFL) — public/electro/fonts/open-sans-<subset>-<ağırlık>-<stil>.woff2
const OPEN_SANS = [[300, "normal"], [400, "normal"], [600, "normal"], [700, "normal"], [800, "normal"], [400, "italic"], [700, "italic"]];
const RANGES = {
  latin: "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD",
  "latin-ext": "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF",
};
const openSansCss = OPEN_SANS.flatMap(([w, st]) => Object.entries(RANGES).map(([sub, range]) =>
  `@font-face{font-family:"Open Sans";font-style:${st};font-weight:${w};font-display:swap;` +
  `src:url("fonts/open-sans-${sub}-${w}-${st}.woff2") format("woff2");unicode-range:${range}}`)).join("\n");

function fixFontFace(rule, kind) {
  rule.walkDecls("src", (d) => {
    if (kind === "electro") {
      d.value = 'url("fonts/font-electro.woff") format("woff"), url("fonts/font-electro.ttf") format("truetype")';
    } else if (kind === "fa") {
      const m = d.value.match(/fa-(brands|regular|solid)-(\d+)/);
      if (m) d.value = `url("webfonts/fa-${m[1]}-${m[2]}.woff2") format("woff2")`;
    }
  });
  // İkon fontları: yüklenene kadar kutu/harf göstermemek için "block"
  rule.walkDecls("font-display", (d) => d.remove());
  rule.append({ prop: "font-display", value: "block" });
}

function scopeSelector(sel) {
  const s = sel.trim();
  if (!s) return s;
  // html / body / :root başlangıçlarını kapsam köküne eşle
  const m = s.match(/^(?:html\s+body|html|body|:root)(?=$|[\s.:#[>+~])(.*)$/);
  if (m) {
    const rest = m[1];
    if (!rest) return SCOPE;
    return SCOPE + rest; // body.foo → .electro.foo ; " x" / " > x"
  }
  return `${SCOPE} ${s}`;
}

const root = postcss.root();
for (const [rel, kind] of parts) {
  const text = fs.readFileSync(A(rel), "utf8");
  const r = postcss.parse(text, { from: A(rel) });
  r.walkAtRules("font-face", (at) => fixFontFace(at, kind));
  r.walkAtRules("import", (at) => at.remove()); // theme.css'teki Google Fonts @import'u
  r.walkRules((rule) => {
    const p = rule.parent;
    if (p && p.type === "atrule" && /keyframes$/i.test(p.name)) return;
    rule.selectors = rule.selectors.map(scopeSelector);
  });
  r.walkDecls((d) => {
    if (/#fed700/i.test(d.value)) d.value = d.value.replace(/#fed700/gi, "var(--electro-primary)");
  });
  root.append(r.nodes);
}
root.prepend(postcss.parse(`${openSansCss}\n${SCOPE}{--electro-primary:#fed700;}`));

postcss([cssnano({ preset: ["default", { discardComments: { removeAll: true } }] })])
  .process(root.toString(), { from: undefined })
  .then((res) => {
    fs.mkdirSync(OUT_DIR, { recursive: true });
    fs.writeFileSync(path.join(OUT_DIR, "electro.css"), res.css);
    const copy = (from, to) => { fs.mkdirSync(path.dirname(to), { recursive: true }); fs.copyFileSync(from, to); };
    for (const f of ["font-electro.woff", "font-electro.ttf"]) copy(A(`fonts/${f}`), path.join(OUT_DIR, "fonts", f));
    for (const f of ["fa-brands-400.woff2", "fa-regular-400.woff2", "fa-solid-900.woff2"]) copy(A(`vendor/font-awesome/webfonts/${f}`), path.join(OUT_DIR, "webfonts", f));
    const missing = OPEN_SANS.flatMap(([w, st]) => Object.keys(RANGES).map((sub) => `fonts/open-sans-${sub}-${w}-${st}.woff2`))
      .filter((f) => !fs.existsSync(path.join(OUT_DIR, f)));
    if (missing.length) console.warn("UYARI: eksik Open Sans dosyaları (npm @fontsource/open-sans/files):", missing.join(", "));
    console.log(`public/electro/electro.css: ${(res.css.length / 1024).toFixed(0)} KB`);
  });
