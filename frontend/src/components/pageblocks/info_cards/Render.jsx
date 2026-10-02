// D9 info_cards — şablon v2.0 about.html: .row > .col-md-4.mb-4.mb-md-0 > .card.mb-3.border-0.text-center.rounded-0
//   > img.img-fluid.mb-3 (500×300) + .card-body > h5.font-size-18.font-weight-semi-bold.mb-3 + p.text-gray-90.max-width-334.mx-auto
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";

const COL = { 2: "col-md-6", 3: "col-md-4", 4: "col-md-6 col-lg-3" };

export default function Render({ settings, ctx }) {
  const st = settings;
  const items = (st.items || []).filter((x) => x && (x.title || x.text || (x.image && x.image.url)));
  if (!items.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Kart ekleyin.</div> : null;
  const col = COL[Number(st.columns) || 3] || COL[3];
  const left = st.align === "left";
  const tw = Number(st.text_max_width) || 334;
  return (
    <div className="row pd-ic" data-testid="info-cards">
      {items.map((it, i) => {
        const f = `items.${i}`;
        return (
          <div key={it._id || i} className={`${col}${i < items.length - 1 ? " mb-4 mb-md-0" : ""}`}>
            <div className={`card mb-3 border-0 rounded-0${left ? " text-left" : " text-center"}`}>
              <SmartLink link={it.link} fallback="div" className="d-block">
                <SmartImage image={it.image} size={[500, 300]} width={1000} className="img-fluid mb-3" phClassName="mb-3" field={`${f}.image`} alt={it.title} />
              </SmartLink>
              <div className="card-body">
                {it.title && <h5 className="font-size-18 font-weight-semi-bold mb-3" data-pd-field={`${f}.title`}>{it.title}</h5>}
                {it.text && <p className={`text-gray-90${left ? "" : " mx-auto"}`} style={{ maxWidth: tw, whiteSpace: "pre-line" }} data-pd-field={`${f}.text`}>{it.text}</p>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
