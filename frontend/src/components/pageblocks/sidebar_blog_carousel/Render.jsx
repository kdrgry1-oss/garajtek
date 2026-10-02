// D8 sidebar_blog_carousel — şablon v2.0 home-v2 kenar çubuğu “From the Blog”:
//   aside > .position-relative > .border-bottom.border-color-1.mb-4 h3.section-title.pb-3.font-size-18 (+ oklar)
//   > .js-slick-carousel (1'li) > .js-slide.post-group > .post-item > .product-item__body > a img (270×180)
//   + .mb-1 a.font-size-12.text-gray-5 (kategori) + h6.post-item__title.font-size-14 a.font-weight-bold.text-dark + a.text-gray-5 i.ec-comment
// Mağazada blog modülü yok: yazılar elle girilir (galeride gizli blok).
import BlockCarousel from "../_shared/BlockCarousel";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import { SideHeader } from "../sidebar_product_list/Render";
import "../sidebar_product_list/style.css";

export default function Render({ settings, ctx }) {
  const st = settings;
  const posts = (st.posts || []).filter((p) => p && p.title).slice(0, Number(st.limit) || 4);
  if (!posts.length) return ctx && ctx.preview ? <div className="pd-stub" data-empty="">Yazı ekleyin.</div> : null;
  const car = { ...(st.carousel || {}), per_view: { 0: 1 }, rows: 1 };
  const header = car.arrows === "header" ? (ctl) => <SideHeader title={st.title} ctl={ctl} sm={false} className="mb-4" /> : undefined;
  return (
    <aside className="position-relative pd-sbc" data-testid="sidebar-blog-carousel">
      {!header && <SideHeader title={st.title} sm={false} className="mb-4" />}
      <BlockCarousel value={car} header={header} className="u-slick u-slick-overflow-visble">
        {posts.map((p, i) => {
          const f = `posts.${i}`;
          return (
            <div key={p._id || i} className="post-group">
              <div className="post-item">
                <div className="product-item__body pb-xl-2">
                  <div className="mb-3">
                    <SmartLink link={p.link} fallback="div" className="d-block text-center">
                      <SmartImage image={p.image} size={[270, 180]} width={560} className="img-fluid" field={`${f}.image`} alt={p.title} />
                    </SmartLink>
                  </div>
                  {p.category && <div className="mb-1"><span className="font-size-12 text-gray-5" data-pd-field={`${f}.category`}>{p.category}</span></div>}
                  <h6 className="mb-2 post-item__title font-size-14">
                    <SmartLink link={p.link} className="font-weight-bold text-dark" field={`${f}.title`}>{p.title}</SmartLink>
                  </h6>
                  {p.meta && <div className="mb-1"><span className="d-block text-gray-5"><i className="ec ec-comment mr-1" /><span data-pd-field={`${f}.meta`}>{p.meta}</span></span></div>}
                </div>
              </div>
            </div>
          );
        })}
      </BlockCarousel>
    </aside>
  );
}
