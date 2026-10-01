// Electro tarzı yazı logosu ("garajtek" + sarı nokta). Admin › Ayarlar'da logo yüklüyse o kullanılır.
import { Link } from "react-router-dom";
import { useStoreInfo } from "../../lib/storeInfo";
import { SITE_NAME } from "../../lib/brand";

export function LogoMark({ name, size = 40 }) {
  const text = String(name || SITE_NAME || "garajtek").toLocaleLowerCase("tr").replace(/\s+/g, "");
  return (
    <span className="el-logo" style={{ fontSize: size }} aria-hidden="true">
      {text}<span className="el-logo__dot" />
    </span>
  );
}

export default function Logo({ className = "", onClick, width, height }) {
  const info = useStoreInfo();
  const name = info.name && info.name !== "Mağaza" ? info.name : (SITE_NAME !== "Mağaza" ? SITE_NAME : "GarajTek");
  return (
    <Link to="/" className={className} aria-label={name} onClick={onClick} data-testid="header-logo">
      {info.logo
        ? <img src={info.logo} alt={name} style={{ maxHeight: height || 42, maxWidth: width || 175, width: "auto" }} />
        : <LogoMark name={name} size={height ? Math.round(height * 0.95) : 40} />}
    </Link>
  );
}
