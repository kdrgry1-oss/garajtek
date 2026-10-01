/**
 * Electro tema CSS'ini (scripts/electro/electro.full.css — `.electro` kapsamlı TAM sürüm)
 * vitrin kaynak kodunda kullanılan sınıflara göre budar → public/electro/electro.css (+ minify).
 *
 * Bir kural, seçicisindeki TÜM sınıflar src/ altındaki .js/.jsx dosyalarında (veya güvenli liste
 * öneklerinde) geçiyorsa korunur. Admin'in CMS HTML'inde (sayfa içerikleri, özel footer HTML)
 * kullanabileceği yaygın Bootstrap/Electro yardımcı sınıfları öneklerle güvenli listededir.
 *
 * Yeni bir Electro sınıfı kullanınca:  node scripts/purge-electro-css.js
 * Tema CSS'ini baştan üretmek için önce: node scripts/build-electro-css.js <electro/2.0>
 * (o betik tam sürümü public/electro/electro.css'e yazar; ardından bu betiği çalıştırın.)
 */
const fs = require("fs");
const path = require("path");
const postcss = require("postcss");
const cssnano = require("cssnano");

const ROOT = path.join(__dirname, "..");
const FULL = path.join(__dirname, "electro", "electro.full.css");
const OUT = path.join(ROOT, "public", "electro", "electro.css");

const tokens = new Set();
(function walk(dir) {
  for (const f of fs.readdirSync(dir)) {
    const p = path.join(dir, f);
    if (fs.statSync(p).isDirectory()) { if (f !== "node_modules") walk(p); continue; }
    if (!/\.(jsx?|html)$/.test(f)) continue;
    const txt = fs.readFileSync(p, "utf8");
    (txt.match(/[A-Za-z0-9_-]+/g) || []).forEach((t) => tokens.add(t));
  }
})(path.join(ROOT, "src"));
fs.readFileSync(path.join(ROOT, "public", "index.html"), "utf8").match(/[A-Za-z0-9_-]+/g).forEach((t) => tokens.add(t));

const SAFE = [
  /^electro$/, /^(show|active|collapsed|disabled|current|selected|open|focus|fade|in)$/,
  /^(hs-|slick-|u-slick|animated)/,
  /^(row|container|table|img-fluid|lead|small|blockquote|alert|badge|text-(center|left|right|justify|muted)$|font-weight-(bold|normal|light)$|list-(unstyled|inline))/,
];
const ok = (cls) => tokens.has(cls) || SAFE.some((re) => re.test(cls));

const css = fs.readFileSync(FULL, "utf8");
const root = postcss.parse(css);
let kept = 0, dropped = 0;
root.walkRules((rule) => {
  const p = rule.parent;
  if (p && p.type === "atrule" && /keyframes$/i.test(p.name)) return;
  const sels = rule.selectors.filter((sel) => {
    const classes = (sel.replace(/:not\([^)]*\)/g, "").match(/\.[A-Za-z0-9_-]+/g) || []).map((c) => c.slice(1));
    return classes.every(ok);
  });
  if (!sels.length) { rule.remove(); dropped++; } else { rule.selectors = sels; kept++; }
});
root.walkAtRules((at) => { if (/media|supports/.test(at.name) && !at.nodes.length) at.remove(); });

postcss([cssnano({ preset: ["default", { discardComments: { removeAll: true } }] })])
  .process(root.toString(), { from: undefined })
  .then((res) => {
    fs.writeFileSync(OUT, res.css);
    console.log(`kural: ${kept} korundu, ${dropped} atıldı → ${(res.css.length / 1024).toFixed(0)} KB`);
  });
