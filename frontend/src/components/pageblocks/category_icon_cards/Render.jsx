// D3 category_icon_cards — şablon v2.0:
//   v4 “Top Categories this Week”: .bg-gray-7.py-6 bant > başlık + .row.flex-nowrap.flex-md-wrap (mobilde yana kaydırma)
//      > .col-md-4.col-lg-3.col-xl-2gdot4 > .bg-white.overflow-hidden.shadow-on-hover > a.d-block.pr-2.pr-wd-6
//      > .media.align-items-center > .pt-2 img.transform-rotate-15 (100 px) + .ml-3.media-body h6.text-gray-90
//   v5 “Categories Card”: .bg-gray-1 kartlar (col-md-6 col-xl-4), .max-width-148 görsel, h4
//   v8 “Banner”: solda .col-xl-5 543×272 arka planlı banner (yazı sağda), sağda .col-xl-7 içinde 3'lü gri kartlar (min-height-120)
import SectionHeader from "../_shared/SectionHeader";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import "./style.css";

const n = (v, d) => { const x = Number(v); return Number.isFinite(x) && x > 0 ? x : d; };

export default function Render({ settings, ctx }) {
  const st = settings;
  const variant = st._variant || "v4";
  const preview = !!(ctx && ctx.preview);
  const tiles = (st.tiles || []).filter((t) => t && (t.label || (t.image && t.image.url)));
  const lead = st.lead_banner || {};
  const showLead = !!lead.enabled;
  if (!tiles.length && !showLead) return preview ? <div className="pd-stub" data-testid="category-icon-cards" data-empty="">Kart ekleyin.</div> : null;
  const cols = st.columns && typeof st.columns === "object" ? st.columns : { desktop: n(st.columns, 5), tablet: 3, mobile: 1 };
  const vars = {
    "--pd-cic-d": n(cols.desktop, 5), "--pd-cic-t": n(cols.tablet, 3), "--pd-cic-m": n(cols.mobile, 1),
    "--pd-cic-rot": `${Number(st.rotation) || 0}deg`, "--pd-cic-img": `${n(st.image_size, 100)}px`,
    "--pd-cic-bg": st.tile_background || "#fff", "--pd-cic-color": st.label_color || "#333e48",
    "--pd-cic-minh": `${Number(st.min_height) || 0}px`,
  };
  const Tag = variant === "v5" ? "h4" : "h6";
  const grid = (
    <div className={`row pd-cic__row${st.mobile_scroll ? " flex-nowrap flex-md-wrap overflow-auto overflow-md-visble pd-cic__row--scroll" : ""}`}>
      {tiles.map((t, i) => {
        const f = `tiles.${i}`;
        return (
          <div key={t._id || i} className={`pd-cic__col ${variant === "v4" ? "mb-3" : "mb-5"} flex-shrink-0 flex-md-shrink-1`}>
            <div className={`pd-cic__tile overflow-hidden${st.shadow_on_hover ? " shadow-on-hover" : ""} h-100 d-flex align-items-center`}>
              <SmartLink link={t.link} fallback="div" className="d-block pr-2 pr-wd-6 pd-cic__link">
                <div className="media align-items-center pd-cic__media">
                  <div className={variant === "v5" ? "pd-cic__imgwrap" : "pt-2 pd-cic__imgwrap"}>
                    <SmartImage image={t.image} size={[300, 300]} width={300} className="img-fluid pd-cic__img" field={`${f}.image`} phClassName="pd-cic__ph" alt={t.label} />
                  </div>
                  {t.label && (
                    <div className={`${variant === "v5" ? "ml-4" : "ml-3"} media-body`}>
                      <Tag className="mb-0 pd-cic__label" style={Number(st.label_size) > 0 ? { fontSize: `${Number(st.label_size)}px` } : undefined} data-pd-field={`${f}.label`}>{t.label}</Tag>
                    </div>
                  )}
                </div>
              </SmartLink>
            </div>
          </div>
        );
      })}
    </div>
  );
  const header = st.header && st.header.title
    ? <SectionHeader value={st.header} field="header" className="mb-5 pd-cic__header" titleClassName="section-title mb-0 pb-2 font-size-22" />
    : null;
  if (showLead) {
    return (
      <div className={`pd-cic pd-cic--${variant}`} style={vars} data-testid="category-icon-cards">
        {header}
        <div className="row">
          <div className="col-xl-5 mb-4 mb-xl-0">
            <div className="bg-gray-1 position-relative overflow-hidden pd-cic__lead">
              {lead.image && lead.image.url
                ? <SmartImage image={lead.image} width={1100} className="pd-cic__lead-bg" fit="cover" field="lead_banner.image" />
                : <SmartImage image={null} size={[543, 272]} phFill phClassName="pd-cic__lead-bg" field="lead_banner.image" />}
              <SmartLink link={lead.link} fallback="div" className="row align-items-center mx-0 min-height-272 position-relative">
                <div className="col-md-8 mb-4 mb-md-0 pl-0" />
                <div className="col-md-4 mb-4 mb-md-0">
                  {lead.label && <div className="font-size-18 font-weight-semi-bold text-dark" data-pd-field="lead_banner.label">{lead.label}</div>}
                </div>
              </SmartLink>
            </div>
          </div>
          <div className="col-xl-7">{grid}</div>
        </div>
      </div>
    );
  }
  return (
    <div className={`pd-cic pd-cic--${variant}`} style={vars} data-testid="category-icon-cards">
      {header}
      {grid}
    </div>
  );
}
