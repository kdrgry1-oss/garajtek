// Ödeme ekranındaki Mesafeli Satış Sözleşmesi / Ön Bilgilendirme Formu penceresinde
// {{alici.*}} / {{siparis.*}} yer tutucularını o anki sipariş verisiyle doldurur.
// Firma alanları ({{sirket.*}}) sunucuda doldurulur (GET /api/pages/{slug}?order_fields=1).
// Tüm değerler HTML-escape edilir; ürün tablosu yalnız escape edilmiş hücrelerden kurulur.

const esc = (v) => String(v ?? "")
  .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;").replace(/'/g, "&#39;");

const PENDING = "(sipariş sırasında doldurulur)";
const PENDING_ITEMS = "(Sipariş edilen ürünler; adet, birim fiyat ve KDV dahil tutarlarıyla sipariş onayı sırasında burada listelenir.)";

export const money = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "";
  return x.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + " TL";
};

function itemsTable(items) {
  const rows = (items || []).map((it) => {
    const qty = Number(it.quantity) || 1;
    const unit = Number(it.price) || 0;
    const variant = [it.size, it.color].filter(Boolean).join(" / ");
    const name = variant ? `${it.name || "Ürün"} (${variant})` : (it.name || "Ürün");
    return `<tr><td>${esc(name)}</td><td>${esc(qty)}</td><td>${esc(money(unit))}</td><td>${esc(money(unit * qty))}</td></tr>`;
  });
  if (!rows.length) return `<p>${esc(PENDING_ITEMS)}</p>`;
  return `<table><thead><tr><th>Ürün</th><th>Adet</th><th>Birim fiyat (KDV dahil)</th><th>Tutar</th></tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

/** ctx: { buyer:{name,address,phone,email,invoice}, order:{date,items,subtotal,discount,shipping,total,payment} } */
export function fillOrderFields(html, ctx) {
  if (!html || html.indexOf("{{") === -1) return html || "";
  const b = ctx?.buyer || {};
  const o = ctx?.order || {};
  const vals = {
    "alici.ad": b.name, "alici.adres": b.address, "alici.telefon": b.phone,
    "alici.eposta": b.email, "alici.fatura": b.invoice,
    "siparis.tarih": o.date, "siparis.ara_toplam": o.subtotal != null ? money(o.subtotal) : "",
    "siparis.indirim": o.discount ? `-${money(o.discount)}` : (o.subtotal != null ? money(0) : ""),
    "siparis.kargo": o.shipping != null ? (Number(o.shipping) > 0 ? money(o.shipping) : "Ücretsiz") : "",
    "siparis.toplam": o.total != null ? money(o.total) : "", "siparis.odeme": o.payment,
  };
  return html.replace(/\{\{\s*((?:alici|siparis)\.[a-z_]+)\s*\}\}/g, (_m, key) => {
    if (key === "siparis.urunler") return ctx ? itemsTable(o.items) : esc(PENDING_ITEMS);
    const v = vals[key];
    return v ? esc(v) : esc(PENDING);
  });
}
