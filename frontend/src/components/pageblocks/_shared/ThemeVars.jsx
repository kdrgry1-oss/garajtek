// site_theme → .electro kapsamında CSS değişkenleri ve küçük kural kümesi (ana renk, koyu ton, üzerindeki
// yazı, gövde/indirim/bağlantı renkleri, yazı tipi, temel boyut, sayfa genişliği, ürün kartı anahtarları).
import { useSiteDesign } from "../../../lib/siteDesign";

const FONTS = { "Open Sans": null, Roboto: "Roboto", Inter: "Inter", Montserrat: "Montserrat", Rubik: "Rubik", "Nunito Sans": "Nunito+Sans" };
const SAFE = /^(#[0-9a-f]{3,8}|var\(--[a-z0-9-]+\)|transparent|rgba?\([\d.,\s]+\))$/i;
const col = (c, d) => (c && SAFE.test(String(c)) ? c : d);

function darken(hex, amt = 0.08) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  const f = (x) => Math.max(0, Math.min(255, Math.round(x * (1 - amt))));
  return `#${[(n >> 16) & 255, (n >> 8) & 255, n & 255].map(f).map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

export function themeCss(t) {
  if (!t) return "";
  const primary = col(t.primary_color, "#fed700");
  const dark = col(t.primary_dark, "") || darken(primary);
  const on = t.text_on_primary === "white" ? "#ffffff" : "#333e48";
  const font = FONTS[t.font_family] !== undefined ? t.font_family : "Open Sans";
  const base = Math.max(12, Math.min(18, Number(t.base_font_size) || 14));
  const cw = String(t.container_width) === "1430" ? 1430 : 0;
  const card = t.card || {};
  const r = [];
  r.push(`.electro{--electro-primary:${primary};--primary:${primary};--primary-dark:${dark};--pd-on-primary:${on};--body-text:${col(t.body_text, "#333e48")};--sale-color:${col(t.sale_color, "#df3737")};--link-color:${col(t.link_color, "#0077d0")}}`);
  if (primary.toLowerCase() !== "#fed700" || t.text_on_primary === "white") {
    r.push(`.electro .btn-primary,.electro .bg-primary,.electro .btn-primary:not(:disabled):not(.disabled):active{background-color:${primary}!important;border-color:${primary}!important;color:${on}}`);
    r.push(`.electro .btn-primary:hover,.electro .btn-primary:focus,.electro .btn-primary-dark-w:hover{background-color:${dark}!important;border-color:${dark}!important;color:${on}}`);
    r.push(`.electro .text-primary{color:${primary}!important}.electro .border-primary{border-color:${primary}!important}`);
    if (on === "#ffffff") r.push(".electro .bg-primary .text-gray-90,.electro .btn-primary .text-gray-90,.electro .bg-primary-down-lg .u-hamburger__inner{color:#fff}");
  }
  if (col(t.body_text, "#333e48") !== "#333e48") r.push(`.electro,.electro body{color:${t.body_text}}`);
  if (col(t.sale_color, "#df3737") !== "#df3737") r.push(`.electro .text-red,.electro .text-sale{color:${t.sale_color}!important}`);
  if (col(t.link_color, "#0077d0") !== "#0077d0") r.push(`.electro .text-blue{color:${t.link_color}!important}`);
  if (font !== "Open Sans") r.push(`.electro{font-family:"${font}",system-ui,sans-serif}`);
  if (base !== 14) r.push(`.electro{font-size:${base}px}`);
  if (cw) r.push(`@media (min-width:1480px){.electro .container{max-width:${cw}px}}`);
  if (card.show_compare === false) r.push(".electro .product-item a[data-testid^=\"compare-\"]{display:none!important}");
  if (card.show_wishlist === false) r.push(".electro .product-item a[data-testid^=\"favorite-\"]{display:none!important}");
  if (card.show_category === false) r.push(".electro .product-item .product-item__body>div.mb-2:first-child{display:none!important}");
  if (card.show_old_price === false) r.push(".electro .product-item .prodcut-price del{display:none!important}");
  if (card.show_discount_badge === false) r.push(".electro .product-item .el-badge--sale{display:none!important}");
  return r.join("\n");
}

export default function ThemeVars() {
  const sd = useSiteDesign();
  const t = sd.site_theme;
  const font = FONTS[t?.font_family];
  return (
    <>
      {font && <link rel="stylesheet" href={`https://fonts.googleapis.com/css2?family=${font}:wght@300;400;600;700&display=swap`} />}
      <style data-pd-theme="">{themeCss(t)}</style>
    </>
  );
}
