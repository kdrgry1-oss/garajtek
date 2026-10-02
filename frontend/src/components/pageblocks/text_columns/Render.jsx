// D9 text_columns — şablon v2.0 about.html: .row.mb-8 > .col-lg-7 > .row > .col-lg-6.mb-5.mb-lg-8
//   > h3.font-size-18.font-weight-semi-bold.text-gray-39.mb-4 + p.text-gray-90
import RichText from "../_shared/RichText";

const COL = { 1: "col-12", 2: "col-lg-6", 3: "col-md-6 col-lg-4", 4: "col-md-6 col-lg-3" };

export default function Render({ settings, ctx }) {
  const st = settings;
  const items = (st.items || []).filter((x) => x && (x.title || x.text));
  if (!items.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Sütun ekleyin.</div> : null;
  const col = COL[Number(st.columns) || 2] || COL[2];
  const grid = (
    <div className="row">
      {items.map((it, i) => {
        const f = `items.${i}`;
        return (
          <div key={it._id || i} className={`${col} mb-5 mb-lg-8`}>
            {it.title && <h3 className="font-size-18 font-weight-semi-bold mb-4" style={{ color: st.title_color || "#434343" }} data-pd-field={`${f}.title`}>{it.title}</h3>}
            <RichText html={it.text} as="p" style={{ color: st.text_color || "#333e48" }} field={`${f}.text`} />
          </div>
        );
      })}
    </div>
  );
  return (
    <div className="pd-tc" data-testid="text-columns">
      {st.width === "wide" ? <div className="row"><div className="col-lg-7">{grid}</div></div> : grid}
    </div>
  );
}
