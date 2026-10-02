// Grup B karusel başlık parçaları: başlık etiketi (h2/h3/gizli), hizalama, alt çizgi ve sağ taraf
// (bağlantı | hap bağlantıları/sekmeleri | karusel okları). Şema `section_header` değerinin tamamı burada karşılanır.
import SmartLink, { linkHref } from "../_shared/SmartLink";

/** Başlık satırındaki ‹ › okları (BlockCarousel `header(ctl)` kontrolleriyle). */
export function HeaderArrows({ ctl, className = "" }) {
  if (!ctl) return null;
  return (
    <div className={`pd-carousel__arrows-header ${className}`} data-testid="header-arrows">
      <button type="button" aria-label="Önceki" disabled={!ctl.canPrev} onClick={ctl.prev}><i className="fa fa-angle-left" /></button>
      <button type="button" aria-label="Sonraki" disabled={!ctl.canNext} onClick={ctl.next}><i className="fa fa-angle-right" /></button>
    </div>
  );
}

/** Başlık metni: tag h2 | h3 | sr-only. */
export function HeaderTitle({ h, field = "header", className, defTag = "h2" }) {
  if (!h?.title) return null;
  if (h.tag === "sr-only") return <h2 className="sr-only" data-pd-field={`${field}.title`}>{h.title}</h2>;
  const Tag = h.tag === "h3" || h.tag === "h2" ? h.tag : defTag;
  return <Tag className={className} data-pd-field={`${field}.title`}>{h.title}</Tag>;
}

/** Hap bağlantıları / sekmeleri (sekme ise onPill ile ürün kaynağını değiştirir). */
export function HeaderPills({ h, field = "header", active = 0, onPill, className = "" }) {
  const pills = (h?.pills || []).map((p, i) => ({ p, i })).filter(({ p }) => p && p.label);
  if (!pills.length) return null;
  return (
    <ul className={`nav nav-pills nav-tab-pill mb-0 align-items-center font-size-15 flex-nowrap overflow-auto ${className}`} role="tablist">
      {pills.map(({ p, i }) => {
        const cls = `nav-link rounded-pill${i === active ? " active" : ""}`;
        const tab = onPill && p.as_tab;
        return (
          <li className="nav-item flex-shrink-0" key={p._id || i}>
            {tab || !linkHref(p.link) ? (
              <a href={`#${field}-${i}`} role="tab" aria-selected={i === active} className={cls}
                onClick={(e) => { e.preventDefault(); if (onPill) onPill(i); }} data-pd-field={`${field}.pills.${i}.label`}>{p.label}</a>
            ) : <SmartLink link={p.link} className={cls} field={`${field}.pills.${i}.label`}>{p.label}</SmartLink>}
          </li>
        );
      })}
    </ul>
  );
}

/** "Tümünü gör ›" bağlantısı. */
export function HeaderLink({ h, field = "header", className = "" }) {
  if (!h?.link?.label || !linkHref(h.link.link)) return null;
  return (
    <SmartLink link={h.link.link} className={`d-block text-gray-16 align-self-center ${className}`} field={`${field}.link.label`}>
      {h.link.label} <i className="ec ec-arrow-right-categproes" />
    </SmartLink>
  );
}
