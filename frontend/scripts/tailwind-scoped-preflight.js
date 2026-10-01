/**
 * Tailwind preflight'ı (CSS reset) VİTRİN TEMASI (.electro) dışına kapsamlar.
 *
 * Neden: Electro teması Bootstrap 4 reboot'u + tarayıcı varsayılanlarına dayanır. Tailwind preflight
 * ise img'yi block yapar, tüm kenarlıkları 0/solid yapar, liste/başlık/düğme stillerini sıfırlar →
 * `.electro` içinde (header, sayfa, footer) tema "bozuk" görünüyordu. Burada preflight'ın her
 * seçicisi `:where(<seçici>):where(:not(.electro, .electro *))` biçimine çevrilir:
 *   - .electro alt ağacına HİÇ uygulanmaz (tema, orijinal HTML şablondaki gibi görünür)
 *   - özgüllük 0 kalır → admin/ödeme (Tailwind) ekranlarında davranış aynıdır.
 * tailwind.config.js: corePlugins.preflight=false + plugins: [scopedPreflight]
 */
const fs = require("fs");
const path = require("path");
const postcss = require("postcss");

const NOT_ELECTRO = ":where(:not(.electro, .electro *))";

function scope(sel) {
  const s = sel.trim();
  // Sondaki pseudo-element (::before, ::placeholder, ::-webkit-…) :where() içine giremez → dışarıda bırak
  const m = s.match(/^(.*?)(::[\w-]+(?:\([^)]*\))?)$/);
  const base = m ? m[1] : s;
  const pseudo = m ? m[2] : "";
  return (base ? `:where(${base})` : "") + NOT_ELECTRO + pseudo;
}

module.exports = function scopedPreflight({ addBase }) {
  const file = path.join(path.dirname(require.resolve("tailwindcss/package.json")), "lib", "css", "preflight.css");
  const root = postcss.parse(fs.readFileSync(file, "utf8"));
  root.walkRules((rule) => {
    rule.selectors = rule.selectors.map(scope);
  });
  addBase(root.nodes);
};
module.exports.scope = scope;
