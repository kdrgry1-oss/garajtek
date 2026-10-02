// D8 sidebar_features — şablon v2.0 home-v2 kenar çubuğu “Feature List”:
//   aside.mb-8 > .d-flex.justify-content-center.rounded.border.mb-4 > .px-4.py-6.w-100
//   > .media.px-3.mb-4.pb-4.border-bottom × N (son öğe çizgisiz) > .u-avatar.mr-2 i.text-primary.ec.font-size-46 (müşteri ikonu 56)
//   + .media-body.text-center span.d-block.font-weight-bold.text-dark + div.text-secondary
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import "../sidebar_product_list/style.css";

function Icon({ icon, f, size }) {
  if (icon && icon.image && icon.image.url) return <SmartImage image={icon.image} width={120} className="img-fluid" style={{ width: size, height: "auto" }} field={`${f}.icon`} placeholder={false} />;
  const cls = (icon && icon.icon) || "ec ec-tag";
  const big = /ec-customers/.test(cls);
  return <i className={`${cls} pd-sfe__i`} style={{ fontSize: big ? Math.round(size * 56 / 46) : size }} data-pd-field={`${f}.icon`} aria-hidden="true" />;
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const items = (st.items || []).filter((x) => x && (x.strong_text || x.text));
  if (!items.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Avantaj ekleyin.</div> : null;
  const size = Number(st.icon_size) || 46;
  // “Yazı rengi” boşsa şablon renkleri (kalın: text-dark, açıklama: text-secondary); doluysa ikisine de uygulanır
  const tc = st.text_color || "";
  return (
    <aside className="pd-sfe" data-testid="sidebar-features">
      <div className={`d-flex justify-content-center mb-4${st.border ? " rounded border" : ""}`} style={{ backgroundColor: st.background || undefined }}>
        <div className="px-4 py-6 w-100">
          {items.map((it, i) => {
            const f = `items.${i}`;
            return (
              <SmartLink key={it._id || i} link={it.link} fallback="div" className={`media px-3 text-reset${i < items.length - 1 ? " mb-4 pb-4 border-bottom" : ""}`}>
                <div className="u-avatar mr-2" style={{ color: st.icon_color || "var(--electro-primary, #fed700)" }}><Icon icon={it.icon} f={f} size={size} /></div>
                <div className="media-body text-center">
                  {it.strong_text && <span className={`d-block font-weight-bold${tc ? "" : " text-dark"}`} style={tc ? { color: tc } : undefined} data-pd-field={`${f}.strong_text`}>{it.strong_text}</span>}
                  {it.text && <div className={tc ? undefined : "text-secondary"} style={tc ? { color: tc } : undefined} data-pd-field={`${f}.text`}>{it.text}</div>}
                </div>
              </SmartLink>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
