// Electro tarzı yazı logosu ("garajtek" + sarı nokta). Admin › Ayarlar'da logo yüklüyse o kullanılır.
import { Link } from "react-router-dom";
import { useStoreInfo } from "../../lib/storeInfo";
import { SITE_NAME } from "../../lib/brand";

export function LogoMark({ name, width = 175, height = 42 }) {
  const text = String(name || SITE_NAME || "garajtek").toLocaleLowerCase("tr").replace(/\s+/g, "");
  // Uzun adlarda viewBox genişler, görünür boyut sabit kalır.
  const vbW = Math.max(120, text.length * 21 + 14);
  return (
    <svg width={width} height={height} viewBox={`0 0 ${vbW} 42`} role="img" aria-label={name || SITE_NAME} style={{ marginBottom: 0 }}>
      <text x="0" y="33" fontFamily="'Open Sans', Arial, Helvetica, sans-serif" fontSize="38" fontWeight="800" letterSpacing="-1.5" fill="#333E48">{text}</text>
      <circle className="ellipse-bg" cx={vbW - 8} cy="30" r="5.3" fill="var(--electro-primary, #FDD700)" />
    </svg>
  );
}

export default function Logo({ className = "", onClick, width, height }) {
  const info = useStoreInfo();
  return (
    <Link to="/" className={className} aria-label={info.name || SITE_NAME} onClick={onClick} data-testid="header-logo">
      {info.logo
        ? <img src={info.logo} alt={info.name || SITE_NAME} style={{ maxHeight: height || 42, maxWidth: width || 175, width: "auto" }} />
        : <LogoMark name={info.name && info.name !== "Mağaza" ? info.name : "garajtek"} width={width} height={height} />}
    </Link>
  );
}
