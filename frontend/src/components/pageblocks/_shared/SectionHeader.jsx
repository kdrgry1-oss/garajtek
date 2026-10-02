// Ürün bölümlerinin ortak başlık satırı (SPEC §2.5): başlık + alt çizgi; sağda ok | hap | bağlantı | geri sayım.
import SmartLink from "./SmartLink";

export default function SectionHeader({ value, field = "header", activePill = 0, onPill, arrows, countdown, className = "mb-3", titleClassName }) {
  const h = value || {};
  const pills = (h.pills || []).filter((p) => p && p.label);
  const right = h.right || "none";
  const Tag = h.tag === "h3" ? "h3" : "h2";
  const title = h.title ? (
    h.tag === "sr-only"
      ? <h2 className="sr-only" data-pd-field={`${field}.title`}>{h.title}</h2>
      : <Tag className={titleClassName || "section-title pd-sh__title mb-0 pb-2 font-size-22"} data-pd-field={`${field}.title`}>{h.title}</Tag>
  ) : null;
  if (h.tag === "sr-only" && right === "none") return title;
  const activeCls = "text-gray-90 btn btn-outline-primary border-width-2 rounded-pill py-1 px-4 font-size-15 text-lh-19 font-size-15-md";
  return (
    <div className={`pd-sh${h.align === "center" ? " pd-sh--center" : ""}${h.underline === false ? "" : " pd-sh--underline"}${!title && right === "none" ? " pd-sh--no-line" : ""} ${className}`} data-testid="section-header">
      {title}
      {right === "pills" && pills.length > 0 && (
        <ul className="nav nav-pills mb-2 pt-3 pt-md-0 mb-0 align-items-center font-size-15 font-size-15-md flex-nowrap flex-md-wrap overflow-auto overflow-md-visble">
          {pills.map((p, i) => {
            const active = i === activePill;
            const asTab = !!onPill && (p.as_tab || !p.link?.url);
            return (
              <li className="nav-item flex-shrink-0 flex-md-shrink-1" key={p._id || i}>
                {asTab ? (
                  <a href={`#${field}-${i}`} className={active ? activeCls : "nav-link text-gray-8"} aria-current={active ? "true" : undefined}
                    onClick={(e) => { e.preventDefault(); onPill(i); }} data-pd-field={`${field}.pills.${i}.label`}>{p.label}</a>
                ) : (
                  <SmartLink link={p.link} className={active ? activeCls : "nav-link text-gray-8"} field={`${field}.pills.${i}.label`}>{p.label}</SmartLink>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {right === "link" && h.link?.label && (
        <SmartLink link={h.link.link} className="font-size-14 text-gray-90 pb-2" field={`${field}.link.label`}>
          {h.link.label} <i className="ec ec-arrow-right-categproes font-size-12" />
        </SmartLink>
      )}
      {right === "arrows" && arrows && (
        <div className="pd-carousel__arrows-header pb-2" data-testid="header-arrows">
          <button type="button" aria-label="Önceki" disabled={!arrows.canPrev} onClick={arrows.prev}><i className="fa fa-angle-left" /></button>
          <button type="button" aria-label="Sonraki" disabled={!arrows.canNext} onClick={arrows.next}><i className="fa fa-angle-right" /></button>
        </div>
      )}
      {right === "countdown" && countdown}
    </div>
  );
}
