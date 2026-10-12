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

export default function WhatsAppOrderButton({ product, variant = null, quantity = 1 }) {
  const [rules, setRules] = useState(_rulesCache);
  const contact = mergeContact(useSiteDesign().site_contact, useStoreInfo());
  useEffect(() => {
    if (_rulesCache) return undefined;
    let alive = true;
    axios.get(`${API}/business-rules`).then((r) => { _rulesCache = r.data || {}; if (alive) setRules(_rulesCache); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  const num = waNumber((rules && rules["storefront.whatsapp_number"]) || contact.whatsapp || contact.phone);
  if (!num || !product) return null;
  const url = typeof window !== "undefined" ? window.location.href.split("#")[0] : "";
  const href = `https://wa.me/${num}?text=${encodeURIComponent(orderMessage(product, variant, quantity, url))}`;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="btn gt-buy-btn gt-buy-btn--wa" data-testid="pdp-whatsapp-order">
      <i className="fab fa-whatsapp mr-2" /> WhatsApp'tan Sipariş Ver
    </a>
  );
}
