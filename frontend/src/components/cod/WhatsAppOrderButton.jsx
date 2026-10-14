// Ürün sayfası "WhatsApp'tan Sipariş Ver": mağazanın WhatsApp hattına ürün adı, seçenek, adet ve
// bağlantıyla hazır mesaj açar. Numara: İş Kuralları › storefront.whatsapp_number (yoksa Sayfa
// Tasarımı › İletişim › WhatsApp / telefon). Numara hiç yoksa buton görünmez.
import { useEffect, useState } from "react";
import axios from "axios";
import { useSiteDesign, mergeContact } from "../../lib/siteDesign";
import { useStoreInfo } from "../../lib/storeInfo";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
let _rulesCache = null;

/** "0543 276 89 73" / "+90 543…" / "905432768973" → "905432768973" */
export function waNumber(raw) {
  let d = String(raw || "").replace(/[^\d]/g, "");
  if (!d) return "";
  if (d.startsWith("00")) d = d.slice(2);
  if (d.startsWith("0")) d = "90" + d.slice(1);
  if (d.length === 10 && d.startsWith("5")) d = "90" + d;
  return d.length >= 11 ? d : "";
}

export function orderMessage(product, variant, quantity, url) {
  const parts = [`Merhaba, bu ürünü sipariş vermek istiyorum:`, product?.name || ""];
  if (variant?.size) parts.push(`Seçenek: ${variant.size}`);
  parts.push(`Adet: ${Math.max(1, Number(quantity) || 1)}`);
  if (product?.stock_code || product?.sku) parts.push(`Stok kodu: ${product.stock_code || product.sku}`);
  if (url) parts.push(url);
  return parts.filter(Boolean).join("\n");
}

/** Mağazanın WhatsApp numarası (İş Kuralları → yoksa site iletişim bilgisi). */
export function useStoreWhatsApp() {
  const [rules, setRules] = useState(_rulesCache);
  const contact = mergeContact(useSiteDesign().site_contact, useStoreInfo());
  useEffect(() => {
    if (_rulesCache) return undefined;
    let alive = true;
    axios.get(`${API}/business-rules`).then((r) => { _rulesCache = r.data || {}; if (alive) setRules(_rulesCache); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  return waNumber((rules && rules["storefront.whatsapp_number"]) || contact.whatsapp || contact.phone);
}

const fmtTL = (n) => `${(Number(n) || 0).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} TL`;

/** Sepet mesajı. `grand` sepet sayfasındaki "Toplam" ile AYNI tanımdır: ürünler − indirimler + kargo
 *  (CartDrawer, Cart.jsx ile aynı shippingQuote hesabını geçirir). Mesajda da kargo dahil olduğu yazılır ki
 *  müşteri / satıcı iki farklı "Toplam" görmesin. */
export function cartMessage(items, grand) {
  const lines = ["Merhaba, sepetimdeki ürünleri sipariş vermek istiyorum:"];
  (items || []).forEach((it) => {
    const opt = it.size || it.variant || "";
    lines.push(`• ${it.name || "Ürün"}${opt ? ` (${opt})` : ""} × ${Math.max(1, Number(it.quantity) || 1)}`);
  });
  if (grand != null) lines.push(`Toplam (kargo dahil): ${fmtTL(grand)}`);
  return lines.join("\n");
}

/** Sepet çekmecesi: tüm sepeti WhatsApp'a hazır mesaj olarak gönderir. Numara yoksa null. */
export function WhatsAppCartButton({ items, grand, className = "", onClick }) {
  const num = useStoreWhatsApp();
  if (!num || !(items || []).length) return null;
  const href = `https://wa.me/${num}?text=${encodeURIComponent(cartMessage(items, grand))}`;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" onClick={onClick}
      className={`btn gt-buy-btn--wa ${className}`} style={{ background: "#116b43", color: "#fff" }} data-testid="drawer-whatsapp-order">
      <i className="fab fa-whatsapp mr-1" /> WhatsApp'tan Sipariş
    </a>
  );
}

export default function WhatsAppOrderButton({ product, variant = null, quantity = 1 }) {
  const num = useStoreWhatsApp();
  if (!num || !product) return null;
  const url = typeof window !== "undefined" ? window.location.href.split("#")[0] : "";
  const href = `https://wa.me/${num}?text=${encodeURIComponent(orderMessage(product, variant, quantity, url))}`;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="btn gt-buy-btn gt-buy-btn--wa" data-testid="pdp-whatsapp-order">
      <i className="fab fa-whatsapp mr-2" /> WhatsApp'tan Sipariş Ver
    </a>
  );
}
