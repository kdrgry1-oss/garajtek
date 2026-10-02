// Electro tarzı yazı logosu ("garajtek" + sarı nokta). Admin › Ayarlar'da logo yüklüyse o kullanılır.
import { Link } from "react-router-dom";
import { useStoreInfo } from "../../lib/storeInfo";
import { SITE_NAME } from "../../lib/brand";
import { useSiteDesign } from "../../lib/siteDesign";

export function LogoMark({ name, size = 40 }) {
  const text = String(name || SITE_NAME || "garajtek").toLocaleLowerCase("tr").replace(/\s+/g, "");
  return (
    <span className="el-logo" style={{ fontSize: size }} aria-hidden="true">
      {text}<span className="el-logo__dot" />
    </span>
  );
}

// Sayfa Tasarımı › Genel Alanlar › Header › Logo: görsel / genişlik / yükseklik / mobil / footer logosu / alt
// metin. Boşsa Ayarlar'daki mağaza logosu, o da yoksa yazı logosu.
export default function Logo({ className = "", onClick, width, height, place = "header" }) {
  const info = useStoreInfo();
  const lg = useSiteDesign().site_header?.logo || {};
  const name = info.name && info.name !== "Mağaza" ? info.name : (SITE_NAME !== "Mağaza" ? SITE_NAME : "GarajTek");
  const alt = lg.alt || name;
  const src = (place === "footer" && lg.footer_image?.url) || lg.image?.url || info.logo;
  const mw = width || Number(lg.width) || 175;
  const mh = height || Number(lg.max_height) || 42;
  const to = (lg.link && lg.link.url) || "/";
  return (
    <Link to={to} className={className} aria-label={alt} onClick={onClick} data-testid="header-logo">
      {src ? (
        <picture>
          {place === "header" && lg.mobile_image?.url && <source media="(max-width: 1199px)" srcSet={lg.mobile_image.url} />}
          <img src={src} alt={alt} style={{ maxHeight: mh, maxWidth: mw, width: "auto" }} />
        </picture>
      ) : <LogoMark name={name} size={height ? Math.round(height * 0.95) : 40} />}
    </Link>
  );
}
