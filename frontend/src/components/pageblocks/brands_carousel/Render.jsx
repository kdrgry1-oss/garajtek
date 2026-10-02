// D1 brands_carousel — şablon v1 inc/footer/brands-carousel.php + _brands-carousel.scss:
//   section.brands-carousel > h2.sr-only + .owl-brands (üst/alt 1px #dadada, 1.286em dikey boşluk) > .item (50 px yükseklik)
//   > a > figure (dikey ortalı) > figcaption.text-overlay h4 (ad) + img (en fazla 50 px, %50 saydam → hover %100).
//   Owl: 1200 px üstü 5, 992 üstü 3, 768 üstü 2, altı 1; navRewind; nokta yok; oklar (fa-chevron) şeridin iki ucunda.
// v2: şablon v2.0 Brand Carousel (.py-2.border-top.border-bottom > .u-slick.my-1 > a.link-hover__brand > img.max-height-50,
//   yanlarda u-slick__arrow-classic oklar, 992 üstü 5 / 768 üstü 2 / altı 1).
// Kaynak: katalogdaki logolu markalar (GET /api/page-blocks/brands) ya da elle girilen 200×60 logolar.
import { useEffect, useState } from "react";
import BlockCarousel from "../_shared/BlockCarousel";
import Placeholder from "../_shared/Placeholder";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import { optimizeImg } from "../../../lib/img";
import "./style.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
let _catalog = null;
let _pending = null;

export function loadCatalogBrands() {
  if (_catalog) return Promise.resolve(_catalog);
  if (!_pending) {
    _pending = fetch(`${API}/page-blocks/brands`).then((r) => (r.ok ? r.json() : { items: [] }))
      .then((d) => { _catalog = Array.isArray(d && d.items) ? d.items : []; return _catalog; })
      .catch(() => { _pending = null; return []; });
  }
  return _pending;
}
export function clearCatalogBrands() { _catalog = null; _pending = null; }

export function useCatalogBrands(on) {
  const [rows, setRows] = useState(_catalog);
  useEffect(() => {
    if (!on) return undefined;
    let alive = true;
    loadCatalogBrands().then((r) => { if (alive) setRows(r); });
    return () => { alive = false; };
  }, [on]);
  return on ? rows : [];
}

/** Ayarlar → çizilecek öğe listesi ({key, link, logo, name, field?, data?}). */
export function brandItems(st, catalog, limit) {
  if (st.source === "manual" || st.brands_source === "manual") {
    return (st.brands || []).filter((b) => b && ((b.logo && b.logo.url) || b.name))
      .map((b, i) => ({ key: b._id || `m${i}`, link: b.link, logo: b.logo && b.logo.url ? b.logo : null, name: b.name || "", field: `brands.${i}` }));
  }
  return (catalog || []).slice(0, limit || 30).map((b) => ({
    key: `c-${b.name}`, link: { kind: "search", url: b.url || `/arama?q=${encodeURIComponent(b.name)}`, label: b.name },
    logo: b.logo ? { url: b.logo, alt: b.name } : null, name: b.name || "", data: true,
  }));
}

function Logo({ it, className, mh }) {
  if (!it.logo) {
    return <span className="pd-brands__word" {...(it.data ? { "data-pd-data": "" } : { "data-pd-field": `${it.field}.name` })}>{it.name}</span>;
  }
  if (it.data) {
    return <img className={className} src={optimizeImg(it.logo.url, 400)} alt={it.name} loading="lazy" decoding="async" style={{ maxHeight: mh }} data-pd-data="" />;
  }
  return <SmartImage image={it.logo} alt={it.logo.alt || it.name} width={400} className={className} style={{ maxHeight: mh }} field={`${it.field}.logo`} placeholder={false} />;
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const v2 = st._variant === "v2";
  const catalog = useCatalogBrands(st.source !== "manual");
  const items = brandItems(st, catalog, Number(st.catalog_limit) || 20);
  const preview = !!(ctx && ctx.preview);
  const mh = Number(st.logo_max_height) || 50;
  const vars = {
    "--pd-brands-h": `${Number(st.item_height) || 50}px`,
    "--pd-brands-mh": `${mh}px`,
    "--pd-brands-op": String(Math.max(0.1, Math.min(1, (Number(st.logo_opacity) || 50) / 100))),
    "--pd-brands-line": st.border_color || "#dadada",
    "--pd-brands-arrow": st.arrow_color || "#d6d6d6",
  };
  const cls = `pd-brands pd-brands--${v2 ? "v2" : "v1"}${st.grayscale ? " pd-brands--gray" : ""}${st.show_name_overlay ? " pd-brands--names" : ""}`;
  const title = st.title ? <h2 className="sr-only" data-pd-field="title">{st.title}</h2> : null;

  if (!items.length) {
    if (!preview || (st.source !== "manual" && catalog === null)) return null;
    // Önizleme: logo yokken şablon ölçüsünde yer tutucular (vitrinde bölüm hiç çizilmez)
    return (
      <section className={cls} style={vars} data-testid="brands-carousel" data-empty="">
        {title}
        <div className="pd-brands__owl pd-brands__owl--empty">
          {Array.from({ length: 5 }).map((_, i) => <div className="pd-brands__item" key={i}><Placeholder size={[200, 60]} label="200 × 60" className="pd-brands__ph" field={st.source === "manual" ? "brands" : undefined} /></div>)}
        </div>
      </section>
    );
  }

  if (v2) {
    return (
      <section className={cls} style={vars} data-testid="brands-carousel">
        {title}
        <div className="py-2 border-top border-bottom pd-brands__band">
          <BlockCarousel value={st.carousel} className="my-1" ariaLabel={st.title || undefined}
            sideArrowsClassName="d-none d-lg-inline-block u-slick__arrow-normal u-slick__arrow-centered--y">
            {items.map((it) => (
              <div key={it.key} className="pd-brands__item2">
                <SmartLink link={it.link} fallback="div" className="link-hover__brand pd-brands__link" title={it.name || undefined}>
                  <Logo it={it} mh={mh} className="img-fluid m-auto max-height-50" />
                  {st.show_name_overlay && it.logo && it.name ? (
                    <span className="pd-brands__name" {...(it.data ? { "data-pd-data": "" } : { "data-pd-field": `${it.field}.name` })}>{it.name}</span>
                  ) : null}
                </SmartLink>
              </div>
            ))}
          </BlockCarousel>
        </div>
      </section>
    );
  }

  return (
    <section className={cls} style={vars} data-testid="brands-carousel">
      {title}
      <BlockCarousel value={st.carousel} className="pd-brands__owl" ariaLabel={st.title || undefined}
        sideArrowsClassName="pd-brands__nav" arrowLeftClassName="fa fa-chevron-left pd-brands__prev" arrowRightClassName="fa fa-chevron-right pd-brands__next">
        {items.map((it) => (
          <div key={it.key} className="pd-brands__item">
            <SmartLink link={it.link} fallback="div" className="pd-brands__link" title={it.name || undefined}>
              <figure className="pd-brands__fig">
                {st.show_name_overlay && it.logo && it.name ? (
                  <figcaption className="pd-brands__name">
                    <h4 {...(it.data ? { "data-pd-data": "" } : { "data-pd-field": `${it.field}.name` })}>{it.name}</h4>
                  </figcaption>
                ) : null}
                <Logo it={it} mh={mh} className="pd-brands__img" />
              </figure>
            </SmartLink>
          </div>
        ))}
      </BlockCarousel>
    </section>
  );
}
