// D7 popular_search_tags — şablon v2.0 home-v8 “Popular Search”:
//   .mb-6 > .d-flex.justify-content-between.border-bottom.border-color-1.mb-4 > h3.section-title.mb-0.pb-2.font-size-22
//   > .d-flex.flex-wrap > a.btn.btn-soft-secondary.rounded.font-weight-normal.px-4d.mr-2d.mb-2d × N
import { linkHref } from "../_shared/SmartLink";
import SmartLink from "../_shared/SmartLink";

const STYLE = { soft: "btn-soft-secondary", outline: "btn-outline-secondary", primary: "btn-primary" };

export default function Render({ settings, ctx }) {
  const st = settings;
  const tags = (st.tags || []).filter((t) => t && t.label);
  if (!tags.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Etiket ekleyin.</div> : null;
  const btn = `btn ${STYLE[st.style] || STYLE.soft} ${st.rounded_pill ? "rounded-pill" : "rounded"} font-weight-normal px-4d mr-2d mb-2d`;
  return (
    <div className="pd-pst" data-testid="popular-search-tags">
      {st.title && (
        <div className="d-flex justify-content-between border-bottom border-color-1 flex-lg-nowrap flex-wrap border-md-down-top-0 border-md-down-bottom-0 mb-4">
          <h3 className="section-title mb-0 pb-2 font-size-22" data-pd-field="title">{st.title}</h3>
        </div>
      )}
      <div className="d-flex flex-wrap">
        {tags.map((t, i) => {
          // bağlantı boşsa etiket metniyle arama
          const link = linkHref(t.link) ? t.link : { kind: "search", url: `/arama?q=${encodeURIComponent(t.label)}` };
          return <SmartLink key={t._id || i} link={link} className={btn} field={`tags.${i}.label`}>{t.label}</SmartLink>;
        })}
      </div>
    </div>
  );
}
