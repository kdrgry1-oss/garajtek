// Grup B ızgara başlığı — v2.0 home-v4/v7 başlık satırı: `h3.section-title(__full)` + sağda hap sekmeler
// (nav-pills nav-tab-pill) veya "Tümünü gör ›" bağlantısı. Değer şeması SPEC §2.5 section_header.
import SmartLink, { linkHref } from "../_shared/SmartLink";

export default function GridHeader({ value, field = "header", active = 0, onPill, className = "mb-4", pillField }) {
  const h = value || {};
  const pills = (h.pills || []).map((p, i) => ({ p, i })).filter(({ p }) => p && p.label);
  const right = h.right || "none";
  const Tag = h.tag === "h2" ? "h2" : "h3";
  const title = h.title ? (h.tag === "sr-only"
    ? <h2 className="sr-only" data-pd-field={`${field}.title`}>{h.title}</h2>
    : <Tag className={`section-title${h.underline === false ? "" : " section-title__full"} mb-0 pb-2 font-size-22`} data-pd-field={`${field}.title`}>{h.title}</Tag>) : null;
  const showPills = right === "pills" && pills.length > 0;
  const showLink = right === "link" && h.link?.label && linkHref(h.link.link);
  if (!title && !showPills && !showLink) return null;
  if (h.tag === "sr-only" && !showPills && !showLink) return title;
  return (
    <div className={`d-flex ${h.align === "center" ? "justify-content-center" : "justify-content-between"} align-items-center border-bottom border-color-1 flex-lg-nowrap flex-wrap border-md-down-top-0 border-md-down-bottom-0 ${className}`} data-testid="section-header">
      {title}
      {showPills && (
        <ul className="w-100 w-lg-auto nav nav-pills nav-tab-pill mb-2 pt-3 pt-lg-0 mb-0 border-top border-color-1 border-lg-top-0 align-items-center font-size-15 font-size-15-lg flex-nowrap flex-lg-wrap overflow-auto overflow-lg-visble pr-0" role="tablist">
          {pills.map(({ p, i }) => {
            const cls = `nav-link rounded-pill${i === active ? " active" : ""}`;
            const tab = onPill && (p.as_tab || !linkHref(p.link));
            return (
              <li className="nav-item flex-shrink-0 flex-lg-shrink-1" key={p._id || i}>
                {tab ? (
                  <a href={`#${field}-${i}`} role="tab" aria-selected={i === active} className={cls} onClick={(e) => { e.preventDefault(); onPill(i); }} data-pd-field={pillField ? pillField(i) : `${field}.pills.${i}.label`}>{p.label}</a>
                ) : <SmartLink link={p.link} className={cls} field={pillField ? pillField(i) : `${field}.pills.${i}.label`}>{p.label}</SmartLink>}
              </li>
            );
          })}
        </ul>
      )}
      {showLink && (
        <SmartLink link={h.link.link} className="d-block text-gray-16 border-top border-color-1 border-md-top-0 w-100 w-md-auto pt-2 pt-md-0" field={`${field}.link.label`}>
          {h.link.label} <i className="ec ec-arrow-right-categproes" />
        </SmartLink>
      )}
    </div>
  );
}

/** Başlangıçta seçili hap: `active` işaretli ilk sekme hap, yoksa 0. */
export const initialPill = (h) => Math.max(0, (h?.pills || []).findIndex((p) => p && p.active));

/** Seçili hap sekmeyse ve kendi kaynağı varsa o kaynak, değilse varsayılan kaynak. */
export function pillSource(h, idx, fallback) {
  const p = (h?.pills || [])[idx];
  return p && p.as_tab && p.source && p.source.kind ? p.source : fallback;
}
