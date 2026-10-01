// Ödeme satırındaki kart markası rozetleri (inline SVG — harici görsel yok).
const Frame = ({ children, label, active }) => (
  <span className={`gt-brand ${active ? "is-active" : ""}`} title={label} aria-label={label} role="img">
    <svg viewBox="0 0 38 24" width="38" height="24">
      <rect x="0.5" y="0.5" width="37" height="23" rx="3" fill="#fff" stroke="#d9d9d9" />
      {children}
    </svg>
  </span>
);

export const VisaIcon = ({ active }) => (
  <Frame label="Visa" active={active}>
    <text x="19" y="16" textAnchor="middle" fontFamily="Arial, sans-serif" fontWeight="900" fontStyle="italic" fontSize="10" fill="#1a1f71">VISA</text>
  </Frame>
);

export const MastercardIcon = ({ active }) => (
  <Frame label="Mastercard" active={active}>
    <circle cx="15" cy="12" r="6.5" fill="#eb001b" />
    <circle cx="23" cy="12" r="6.5" fill="#f79e1b" fillOpacity="0.9" />
  </Frame>
);

export const TroyIcon = ({ active }) => (
  <Frame label="Troy" active={active}>
    <text x="19" y="15.5" textAnchor="middle" fontFamily="Arial, sans-serif" fontWeight="700" fontSize="9" fill="#00a3a6">troy</text>
  </Frame>
);

export const AmexIcon = ({ active }) => (
  <Frame label="American Express" active={active}>
    <rect x="4" y="5" width="30" height="14" rx="2" fill="#2e77bc" />
    <text x="19" y="15" textAnchor="middle" fontFamily="Arial, sans-serif" fontWeight="800" fontSize="7" fill="#fff">AMEX</text>
  </Frame>
);

export default function CardBrandIcons({ active = "" }) {
  return (
    <span className="gt-brands">
      <VisaIcon active={active === "visa"} />
      <MastercardIcon active={active === "mastercard"} />
      <TroyIcon active={active === "troy"} />
      <AmexIcon active={active === "amex"} />
    </span>
  );
}
