// A9 features_list — şablon v1 homepage-3/features-list.php + _features-list.scss: .features-list.columns-5
// (1px #ddd, r8) > .feature (2.143em dikey boşluk; ardışık kutular arası sol çizgi) > .media (150px, ortalı) >
// .media-left i.ec (2.571em, ana renk; ec-customers 3.386em) + .media-body <strong>…</strong> metin.
// v2: şablon v2.0 home-v3 "Feature List" (ortalı metin, ana renk ikon, mobilde yatay kaydırma).
// Dikey yerleşim = kenar çubuğu widget'ı (electro-features: columns-1, alt çizgili).
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import "./features.css";

function Icon({ icon, f, v2 }) {
  if (icon && icon.image && icon.image.url) return <SmartImage image={icon.image} width={120} className="pd-feat__img" field={`${f}.icon`} placeholder={false} />;
  const cls = (icon && icon.icon) || "ec ec-tag";
  return <i className={`${cls} pd-feat__i${/ec-customers/.test(cls) ? " pd-feat__i--lg" : ""}${v2 ? " text-primary" : ""}`} data-pd-field={`${f}.icon`} aria-hidden="true" />;
}

export default function Render({ settings }) {
  const st = settings;
  const v2 = st._variant === "v2";
  const items = (st.items || []).filter(Boolean).slice(0, 6);
  if (!items.length) return null;
  const vertical = st.layout === "vertical";
  const cols = vertical ? 1 : Number(st.columns) || 5;
  const style = {
    "--pd-feat-icon": st.icon_color || "var(--electro-primary, #fed700)",
    "--pd-feat-color": st.text_color || "#333e48",
    "--pd-feat-bg": st.background || "transparent",
    "--pd-feat-isz": `${Number(st.icon_size) || 2.571}em`,
    "--pd-feat-py": `${Number(st.padding_y ?? 2.143)}em`,
    "--pd-feat-w": `${100 / cols}%`,
  };
  if (v2 && !vertical) {
    return (
      <div data-testid="features-list" className="pd-feat pd-feat--v2" style={style}>
        <div className={`row mx-0 flex-nowrap flex-xl-wrap overflow-auto overflow-xl-visble${st.border ? " border rounded-lg" : ""}`}>
          {items.map((it, i) => {
            const f = `items.${i}`;
            return (
              <SmartLink key={it._id || i} link={it.link} fallback="div"
                className={`media col px-6 px-xl-4 px-wd-8 flex-shrink-0 flex-xl-shrink-1 min-width-270-all py-3 text-reset${i && st.border ? " border-left" : ""}`}>
                <div className="u-avatar mr-2 pd-feat__icon"><Icon icon={it.icon} f={f} v2 /></div>
                <div className="media-body text-center">
                  {it.strong_text && <span className="d-block font-weight-bold" data-pd-field={`${f}.strong_text`}>{it.strong_text}</span>}
                  {it.text && <div className="text-secondary" data-pd-field={`${f}.text`}>{it.text}</div>}
                </div>
              </SmartLink>
            );
          })}
        </div>
      </div>
    );
  }
  return (
    <div data-testid="features-list" className={`pd-feat pd-feat--v1${vertical ? " pd-feat--vertical" : ""}${st.border ? " pd-feat--border" : ""}`} style={style}>
      <div className="pd-feat__list">
        {items.map((it, i) => {
          const f = `items.${i}`;
          return (
            <SmartLink key={it._id || i} link={it.link} fallback="div" className="pd-feat__item">
              <div className="pd-feat__media">
                <div className="pd-feat__left"><Icon icon={it.icon} f={f} /></div>
                <div className="pd-feat__body">
                  {it.strong_text && <strong data-pd-field={`${f}.strong_text`}>{it.strong_text}</strong>}
                  {it.strong_text && it.text ? " " : null}
                  {it.text && <span data-pd-field={`${f}.text`}>{it.text}</span>}
                </div>
              </div>
            </SmartLink>
          );
        })}
      </div>
    </div>
  );
}
