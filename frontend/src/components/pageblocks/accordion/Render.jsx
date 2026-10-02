// D9 accordion — şablon v2.0 about.html “What can we do for you ?”:
//   h3.font-size-18.font-weight-semi-bold.text-gray-39.mb-4 + #basicsAccordion1.about-accordion
//   > .card.mb-4.border-color-4.rounded-0 > .card-header.card-collapse.border-color-4 > h5.mb-0
//     > button.btn.btn-link.btn-block.flex-horizontal-center.card-btn.p-0.font-size-18[aria-expanded]
//       > span.border.border-color-5.rounded.font-size-12.mr-5 (i.fa-plus / i.fa-minus) + soru
//   > .collapse(.show) > .card-body > p.mb-0 (cevap). Açık kartın düğmesi kalın, artı kutusu ana renkte.
import { useEffect, useState } from "react";
import RichText from "../_shared/RichText";

const WIDTH = { narrow: "col-lg-5", wide: "col-lg-8", full: "col-12" };

export default function Render({ block, settings, ctx }) {
  const st = settings;
  const items = (st.items || []).filter((x) => x && x.question);
  const first = Number(st.open_index) || 0;
  const [open, setOpen] = useState(() => (first > 0 ? [first - 1] : []));
  useEffect(() => { setOpen(first > 0 ? [first - 1] : []); }, [first]);
  if (!items.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Soru ekleyin.</div> : null;
  const toggle = (i) => setOpen((cur) => (cur.includes(i) ? cur.filter((x) => x !== i) : (st.multiple ? [...cur, i] : [i])));
  const uid = `pdacc-${(block && block.id) || "b"}`;
  return (
    <div className="row pd-acc" data-testid="accordion">
      <div className={WIDTH[st.width] || WIDTH.full}>
        {st.title && <h3 className="font-size-18 font-weight-semi-bold text-gray-39 mb-4" data-pd-field="title">{st.title}</h3>}
        <div id={uid} className="about-accordion">
          {items.map((it, i) => {
            const on = open.includes(i);
            const f = `items.${i}`;
            return (
              <div key={it._id || i} className="card mb-4 border-color-4 rounded-0">
                <div className="card-header card-collapse border-color-4" id={`${uid}-h${i}`}>
                  <h5 className="mb-0">
                    <button type="button" className="btn btn-link btn-block flex-horizontal-center card-btn p-0 font-size-18"
                      aria-expanded={on ? "true" : "false"} aria-controls={`${uid}-c${i}`} onClick={() => toggle(i)}>
                      <span className="border border-color-5 rounded font-size-12 mr-5">
                        <i className="fas fa-plus" />
                        <i className="fas fa-minus" />
                      </span>
                      <div className="pd-acc__q" data-pd-field={`${f}.question`}>{it.question}</div>
                    </button>
                  </h5>
                </div>
                <div id={`${uid}-c${i}`} className={`collapse${on ? " show" : ""}`} aria-labelledby={`${uid}-h${i}`}>
                  <div className="card-body">
                    <RichText html={it.answer} as="p" className="mb-0" field={`${f}.answer`} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
