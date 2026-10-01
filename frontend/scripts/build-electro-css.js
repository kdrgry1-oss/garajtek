/**
 * Electro (ThemeForest "Electro – Electronics eCommerce HTML Template" v2.0) CSS'ini
 * vitrine uyarlar → public/electro/electro.css
 *
 * - Tüm kurallar `.electro` kapsamına alınır (html/body/:root → .electro). Böylece Bootstrap 4
 *   tabanlı tema CSS'i yalnız `.electro` sarmalayıcısı içindeki vitrin bileşenlerini etkiler;
 *   Tailwind kullanan admin paneli ve diğer (ör. ödeme) ekranlarına SIZMAZ.
 * - Tema sarısı (#fed700) `var(--electro-primary)` yapılır → Admin › Özel Tema CSS ile
 *   `.electro{--electro-primary:#xxxxxx}` yazılarak değiştirilebilir.
 * - Font yolları public/electro/{fonts,webfonts} altına yeniden yazılır (yalnız woff/woff2/ttf).
 *
 * Kullanım:  node scripts/build-electro-css.js /path/to/electro/2.0
 * (Tema kaynağı repoda tutulmaz; çıktı + fontlar public/electro altında versiyonlanır.)
 */
const fs = require("fs");
const path = require("path");
const postcss = require("postcss");

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
  ["css/theme.min.css", ""],
];

function fixFontFace(rule, kind) {
  rule.walkDecls("src", (d) => {
    if (kind === "electro") {
      d.value = 'url("fonts/font-electro.woff") format("woff"), url("fonts/font-electro.ttf") format("truetype")';
    } else if (kind === "fa") {
      const m = d.value.match(/fa-(brands|regular|solid)-(\d+)/);
      if (m) d.value = `url("webfonts/fa-${m[1]}-${m[2]}.woff2") format("woff2")`;
    }
  });
  rule.walkDecls("src", () => {});
  // font-display: swap → metin font yüklenene kadar görünür (Lighthouse)
  if (!rule.some((n) => n.prop === "font-display")) rule.append({ prop: "font-display", value: "block" });
}

function scopeSelector(sel) {
  const s = sel.trim();
  if (!s) return s;
  // html / body / :root başlangıçlarını kapsam köküne eşle
  let m = s.match(/^(?:html\s+body|html|body|:root)(?=$|[\s.:#[>+~])(.*)$/);
  if (m) {
    const rest = m[1];
    if (!rest) return SCOPE;
    if (/^[.:#[]/.test(rest)) return SCOPE + rest; // body.foo → .electro.foo
    return SCOPE + rest; // " x" / " > x"
  }
  return `${SCOPE} ${s}`;
}

let css = "";
const root = postcss.root();
for (const [rel, kind] of parts) {
  const text = fs.readFileSync(A(rel), "utf8");
  const r = postcss.parse(text, { from: A(rel) });
  r.walkAtRules("font-face", (at) => fixFontFace(at, kind));
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
root.prepend(postcss.parse(`${SCOPE}{--electro-primary:#fed700;}`));
css = root.toString();
// yorumları at, gereksiz boşlukları sıkıştır
css = css.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\n\s*\n/g, "\n");
fs.mkdirSync(OUT_DIR, { recursive: true });
fs.writeFileSync(path.join(OUT_DIR, "electro.css"), css);

// fontlar
const copy = (from, to) => { fs.mkdirSync(path.dirname(to), { recursive: true }); fs.copyFileSync(from, to); };
for (const f of ["font-electro.woff", "font-electro.ttf"]) copy(A(`fonts/${f}`), path.join(OUT_DIR, "fonts", f));
for (const f of ["fa-brands-400.woff2", "fa-regular-400.woff2", "fa-solid-900.woff2"]) copy(A(`vendor/font-awesome/webfonts/${f}`), path.join(OUT_DIR, "webfonts", f));
console.log("electro.css:", (css.length / 1024).toFixed(0), "KB");
