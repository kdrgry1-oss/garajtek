// D1 brands_carousel — şablon brands-carousel: marka logoları (200×60), gri tonlu, hover'da renkli. Grup D geliştirir.
import { useEffect, useState } from "react";
import BlockCarousel from "../_shared/BlockCarousel";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
let _catalog = null;

function useCatalogBrands(on) {
  const [rows, setRows] = useState(_catalog);
  useEffect(() => {
    if (!on || _catalog) return undefined;
    let alive = true;
    fetch(`${API}/page-blocks/brands`).then((r) => (r.ok ? r.json() : { items: [] })).then((d) => {
      _catalog = Array.isArray(d.items) ? d.items : [];
      if (alive) setRows(_catalog);
    }).catch(() => {});
    return () => { alive = false; };
  }, [on]);
  return rows || [];
}

export default function Render({ settings }) {
  const st = settings;
  const manual = st.source === "manual";
  const catalog = useCatalogBrands(!manual);
  const items = manual
    ? (st.brands || []).filter((b) => b && (b.logo?.url || b.name)).map((b, i) => ({ key: b._id || i, link: b.link, logo: b.logo, name: b.name, field: `brands.${i}` }))
    : catalog.map((b) => ({ key: b.name, link: { kind: "search", url: b.url || `/arama?q=${encodeURIComponent(b.name)}` }, logo: b.logo ? { url: b.logo, alt: b.name } : null, name: b.name, data: true }));
  if (!items.length) return null;
  const mh = Number(st.logo_max_height) || 50;
  return (
    <div data-testid="brands-carousel" className={`pd-brands${st.grayscale ? " pd-brands--gray" : ""}`}>
      <style>{`.electro .pd-brands--gray .el-brand img{filter:grayscale(1);opacity:.5;transition:.2s}.electro .pd-brands--gray .el-brand:hover img{filter:none;opacity:1}`}</style>
      <div className="py-2 border-top border-bottom">
        <BlockCarousel value={st.carousel} className="my-1 el-brands">
          {items.map((it) => (
            <SmartLink key={it.key} link={it.link} fallback="div" className="link-hover__brand d-flex align-items-center justify-content-center el-brand" title={st.show_name_overlay ? it.name : undefined}>
              {it.logo?.url
                ? <SmartImage image={it.logo} alt={it.name} width={400} className="img-fluid m-auto" style={{ maxHeight: mh }} field={it.field ? `${it.field}.logo` : undefined} />
                : <span className="el-brand-word" {...(it.data ? { "data-pd-data": "" } : { "data-pd-field": `${it.field}.name` })}>{it.name}</span>}
            </SmartLink>
          ))}
        </BlockCarousel>
      </div>
    </div>
  );
}
