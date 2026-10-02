// Checkout'a özel sade üst bar + alt politika bağlantıları (site menüsü/footer YOK — Shopify).
import { useState } from "react";
import { Link } from "react-router-dom";
import { SITE_NAME } from "../../lib/brand";

export const POLICY_LINKS = [
  { to: "/sayfa/iade-kosullari", label: "İade politikası" },
  { to: "/sayfa/gizlilik", label: "Gizlilik politikası" },
  { to: "/sayfa/mesafeli-satis", label: "Mesafeli Satış Sözleşmesi" },
  { to: "/sayfa/on-bilgilendirme", label: "Ön Bilgilendirme Formu" },
  { to: "/sayfa/kvkk", label: "KVKK Aydınlatma Metni" },
  { to: "/sayfa/kullanim-kosullari", label: "Kullanım Koşulları" },
];

const LockIcon = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
    <path fill="currentColor" d="M8 1a3.5 3.5 0 0 0-3.5 3.5V6H4a1.5 1.5 0 0 0-1.5 1.5v6A1.5 1.5 0 0 0 4 15h8a1.5 1.5 0 0 0 1.5-1.5v-6A1.5 1.5 0 0 0 12 6h-.5V4.5A3.5 3.5 0 0 0 8 1Zm2 5H6V4.5a2 2 0 1 1 4 0V6Z" />
  </svg>
);

export function CheckoutHeader() {
  const [logoOk, setLogoOk] = useState(true);
  return (
    <header className="gt-co-header" data-testid="checkout-header">
      <div className="gt-co-header-inner">
        <Link to="/" className="gt-co-logo" aria-label={SITE_NAME}>
          {logoOk
            ? <img src="/logo.webp" alt={SITE_NAME} onError={() => setLogoOk(false)} />
            : <span className="gt-co-logo-text">{SITE_NAME}</span>}
        </Link>
        <div className="gt-co-header-right">
          <span className="gt-co-secure"><LockIcon /> Güvenli Ödeme</span>
          <Link to="/sepet" className="gt-co-cart-link" data-testid="checkout-back-btn" aria-label="Sepete dön">
            <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path fill="none" stroke="currentColor" strokeWidth="1.6" d="M3 4h2l2.4 11.2a1 1 0 0 0 1 .8h9.2a1 1 0 0 0 1-.8L20 8H6.2M9 20.5a.5.5 0 1 1-1 0 .5.5 0 0 1 1 0Zm9 0a.5.5 0 1 1-1 0 .5.5 0 0 1 1 0Z" /></svg>
          </Link>
        </div>
      </div>
    </header>
  );
}

export function CheckoutFooter() {
  return (
    <footer className="gt-co-footer" data-testid="checkout-footer">
      <nav aria-label="Politikalar">
        {POLICY_LINKS.map((l) => (
          <Link key={l.to} to={l.to} target="_blank" rel="noreferrer">{l.label}</Link>
        ))}
      </nav>
    </footer>
  );
}
