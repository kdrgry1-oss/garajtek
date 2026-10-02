// D5 categories_brands_card — şablon v2.0 home-v11 “Categories list and Brand”:
//   .my-5.my-xl-n10.borders-radius-20.bg-white.box-shadow-3 (masaüstünde slider'ın üzerine biner)
//   > .px-5.py-4.d-flex: h6 “Brands:” + a.link-hover__brand (img.height-35.width-80.o-f-c) × 6 + a.ml-auto.text-gray-30 “+ More Brands”
//   > .row.no-gutters > .col-md-6.col-lg-4.col-xl-3 × 8: img 350×92 + .px-6.py-4.border-right.border-bottom
//     (yuvarlak ok düğmesi top -20px, h6.font-size-15, ul.font-size-14.text-lh-28 a.text-blue, son öğe “...”).
import useCategoryTree from "../../electro/useCategoryTree";
import { brandItems, useCatalogBrands } from "../brands_carousel/Render";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import { optimizeImg } from "../../../lib/img";
import "./style.css";

const catHref = (c) => (c ? `/${c.slug || c.id}` : "");

export default function Render({ settings, ctx }) {
  const st = settings;
  const tree = useCategoryTree();
  const byId = (tree && tree.byId) || new Map();
  const showBrands = st.brands_source !== "none";
  const catalog = useCatalogBrands(showBrands && st.brands_source !== "manual");
  const brands = showBrands ? brandItems(st, catalog, Number(st.brands_limit) || 6) : [];
  const boxes = (st.boxes || []).filter((b) => b && (b.title || b.category));
  const preview = !!(ctx && ctx.preview);
  if (!boxes.length && !brands.length) return preview ? <div className="pd-stub" data-empty="">Kutu ya da marka ekleyin.</div> : null;
  const more = st.more_brands || {};
  const style = { "--pd-cbc-r": `${Number(st.radius ?? 20)}px`, "--pd-cbc-link": st.link_color || "#0077d0" };
  return (
    <div className={`bg-white box-shadow-3 pd-cbc${st.overlap_hero ? " mt-5 mt-xl-n10 pd-cbc--overlap" : ""}`} style={style} data-testid="categories-brands-card">
      {showBrands && (brands.length > 0 || st.brands_label || more.text) && (
        <div className="px-5 py-4 d-flex align-items-center flex-wrap">
          {st.brands_label && <h6 className="mr-2 mb-0 font-size-14 font-weight-bold w-100 w-xl-auto my-2" data-pd-field="brands_label">{st.brands_label}</h6>}
          {brands.map((b) => (
            <SmartLink key={b.key} link={b.link} fallback="span" className="link-hover__brand mr-4 mx-xl-4 my-2 my-xl-0" title={b.name || undefined}>
              {b.logo
                ? (b.data
                  ? <img className="img-fluid m-auto height-35 width-80 o-f-c" src={optimizeImg(b.logo.url, 200)} alt={b.name} loading="lazy" data-pd-data="" />
                  : <SmartImage image={b.logo} width={200} className="img-fluid m-auto height-35 width-80 o-f-c" field={`${b.field}.logo`} alt={b.name} />)
                : <span className="font-weight-bold text-gray-90 pd-cbc__word" {...(b.data ? { "data-pd-data": "" } : { "data-pd-field": `${b.field}.name` })}>{b.name}</span>}
            </SmartLink>
          ))}
          {more.text && <SmartLink link={more.link} className="ml-auto text-gray-30" field="more_brands.text">{more.text}</SmartLink>}
        </div>
      )}
      {boxes.length > 0 && (
        <div className="row no-gutters">
          {boxes.map((b, i) => {
            const f = `boxes.${i}`;
            const c = b.category ? byId.get(String(b.category)) : null;
            const ownLinks = (b.links || []).filter((l) => l && l.label);
            const links = ownLinks.length
              ? ownLinks.map((l, j) => ({ key: l._id || j, label: l.label, link: l.link, field: `${f}.links.${j}.label` }))
              : (c && c.children ? c.children.slice(0, 5) : []).map((s) => ({ key: s.id, label: s.name, link: { kind: "category", url: catHref(s) }, data: true }));
            const arrowLink = b.link && b.link.url ? b.link : (c ? { kind: "category", url: catHref(c) } : null);
            return (
              <div key={b._id || i} className="col-md-6 col-lg-4 col-xl-3 pd-cbc__box">
                <SmartImage image={b.header_image} size={[350, 92]} width={700} className="img-fluid" field={`${f}.header_image`} alt={b.title} />
                <div className="px-6 py-4 position-relative border-right border-bottom">
                  {arrowLink && (
                    <SmartLink link={arrowLink} className="position-absolute font-size-11 mr-3 top-n20 right-0 rounded-circle bg-white box-shadow-4 flex-content-center height-40 width-40 pd-cbc__arrow" aria-label={b.title || "Kategori"}>
                      <i className="fas fa-chevron-right" />
                    </SmartLink>
                  )}
                  {b.title && <h6 className="font-weight-bold font-size-15 mb-4" data-pd-field={`${f}.title`}>{b.title}</h6>}
                  {(links.length > 0 || st.show_more_link) && (
                    <ul className="mb-0 font-size-14 list-unstyled text-lh-28">
                      {links.map((l) => (
                        <li key={l.key}><SmartLink link={l.link} className="pd-cbc__link" {...(l.data ? { "data-pd-data": "" } : { "data-pd-field": l.field })}>{l.label}</SmartLink></li>
                      ))}
                      {st.show_more_link && arrowLink && <li><SmartLink link={arrowLink} className="pd-cbc__link" aria-label="Tümü">...</SmartLink></li>}
                    </ul>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
