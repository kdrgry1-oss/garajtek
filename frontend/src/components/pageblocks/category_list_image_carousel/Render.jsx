// D6 category_list_image_carousel — şablon v2.0 home-v9 “List-Image Section”:
//   .container.position-relative.mb-5.pb-1 > başlık (.border-bottom.border-color-1 h3.section-title.font-size-22, sağda oklar)
//   > .js-slick-carousel > .js-slide.border.border-color-7.borders-radius-10.overflow-hidden > .row.no-gutters:
//     .col-md-6.col-xl-2gdot4.bg-gray-7.p-4 (gruplar: h6.font-size-13.font-weight-bold + ul.ml-3 a.font-size-13.hover-on-bold)
//     .col-md-6.col-xl-2gdot4.px-4.py-2 (ul.list-group-flush li.border-color-1 a.hover-on-bold.py-2.text-gray-90)
//     .col-xl.d-none.d-xl-block (a > img 840×370)
import BlockCarousel from "../_shared/BlockCarousel";
import SectionHeader from "../_shared/SectionHeader";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import "./style.css";

export default function Render({ settings, ctx }) {
  const st = settings;
  const slides = (st.slides || []).filter((s) => s && ((s.groups || []).length || (s.links || []).length || (s.image && s.image.url)));
  if (!slides.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Slayt ekleyin.</div> : null;
  const style = { "--pd-clic-box": st.box_background || "#f9f9f9", "--pd-clic-line": st.border_color || "#eaeaea", "--pd-clic-r": `${Number(st.radius ?? 10)}px` };
  const header = st.header && (st.header.title || st.header.right === "arrows")
    ? (ctl) => <SectionHeader value={st.header} field="header" arrows={ctl} className="mb-4 pd-clic__header" titleClassName="section-title mb-0 pb-2 font-size-22" />
    : undefined;
  const carousel = { ...(st.carousel || {}), per_view: { 0: 1 }, rows: 1, arrows: (st.carousel && st.carousel.arrows) || "header" };
  return (
    <div className="position-relative pb-1 pd-clic" style={style} data-testid="category-list-image-carousel">
      <BlockCarousel value={carousel} header={header} className="u-slick pd-clic__car"
        sideArrowsClassName="u-slick__arrow-normal u-slick__arrow-centered--y d-none d-md-block">
        {slides.map((s, i) => {
          const f = `slides.${i}`;
          return (
            <div key={s._id || i} className="border borders-radius-10 overflow-hidden pd-clic__slide">
              <div className="row no-gutters">
                <div className="col-md-6 col-xl-2gdot4 p-4 pd-clic__box">
                  {(s.groups || []).map((g, gi) => {
                    const gf = `${f}.groups.${gi}`;
                    return (
                      <div className="mb-1" key={g._id || gi}>
                        {g.title && (
                          <h6 className="font-size-13 font-weight-bold mb-1">
                            <SmartLink link={g.link} className="text-dark" field={`${gf}.title`}>{g.title}</SmartLink>
                          </h6>
                        )}
                        <ul className="list-unstyled m-0 ml-3">
                          {(g.links || []).filter((l) => l && l.label).map((l, li, arr) => (
                            <li key={l._id || li}>
                              <SmartLink link={l.link} className={`d-inline-block font-size-13 text-dark hover-on-bold${li < arr.length - 1 ? " mb-1" : ""}`} field={`${gf}.links.${li}.label`}>{l.label}</SmartLink>
                            </li>
                          ))}
                        </ul>
                      </div>
                    );
                  })}
                </div>
                <div className="col-md-6 col-xl-2gdot4 px-4 py-2">
                  <ul className="list-group list-group-flush mb-3 mb-xl-0">
                    {(s.links || []).filter((l) => l && l.label).map((l, li) => (
                      <li key={l._id || li} className={`border-color-1 list-group-item${li === 0 ? " border-lg-down-0" : ""}`}>
                        <SmartLink link={l.link} className="hover-on-bold py-2 text-gray-90 d-block" field={`${f}.links.${li}.label`}>{l.label}</SmartLink>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="col-xl d-none d-xl-block">
                  <SmartLink link={s.link} fallback="div" className="d-block">
                    <SmartImage image={s.image} size={[840, 370]} width={1000} className="img-fluid" field={`${f}.image`} alt={s.alt} />
                  </SmartLink>
                </div>
              </div>
            </div>
          );
        })}
      </BlockCarousel>
    </div>
  );
}
