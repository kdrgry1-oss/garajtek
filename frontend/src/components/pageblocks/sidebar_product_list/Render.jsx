// D8 sidebar_product_list — şablon v2.0 home-v2 kenar çubuğu “Latest Products”:
//   aside > .mb-2.position-relative > başlık (.border-bottom.border-color-1 h3.section-title.section-title__sm.pb-3.font-size-18)
//   > ul.products-group > li.product-item__list > .product-item__inner.py-md-3.mx-3.border-bottom.row.no-gutters
//     > .col-auto.product-media-left (a.max-width-70 img) + .col.product-item__body (h5.product-item__title a.text-gray-90
//     + .prodcut-price .text-gray-100.font-size-15.font-weight-bold)
//   per_page > 0 → ürünler sayfalara bölünür, başlıkta oklarla gezilir (şablon: 1'li slick).
import { Link } from "react-router-dom";
import { useProductActions } from "../../ProductCard";
import { fmtPrice, priceOf } from "../../electro/format";
import { firstImage, optimizeImg } from "../../../lib/img";
import BlockCarousel from "../_shared/BlockCarousel";
import useProductSource from "../_shared/useProductSource";
import "./style.css";

export function SideItem({ product, showOld = true, listName = "sidebar" }) {
  const a = useProductActions(product, { listName });
  const pv = priceOf(product);
  return (
    <li className="product-item product-item__list pb-2 mb-2 pb-md-0 mb-md-0" data-testid={`product-card-${product.id}`}>
      <div className="product-item__outer h-100">
        <div className="product-item__inner py-md-3 mx-3 border-bottom row no-gutters">
          <div className="col-auto product-media-left">
            <Link to={a.href} onClick={a.select} className="max-width-70 d-block">
              <img className="img-fluid" src={optimizeImg(firstImage(product) || "/placeholder.jpg", 160)} alt={product.name} loading="lazy" width="70" height="65" />
            </Link>
          </div>
          <div className="col product-item__body pl-2 pl-lg-3">
            <div className="mb-4">
              <h5 className="product-item__title"><Link to={a.href} onClick={a.select} className="text-gray-90">{product.name}</Link></h5>
            </div>
            <div className="flex-center-between">
              <div className="prodcut-price">
                {pv.hasDiscount ? (
                  <div className="d-flex align-items-center flex-wrap">
                    <ins className="text-red font-size-15 font-weight-bold text-decoration-none mr-2">{fmtPrice(pv.display)}</ins>
                    {showOld && <del className="font-size-12 text-gray-9">{fmtPrice(pv.list)}</del>}
                  </div>
                ) : <div className="text-gray-100 font-size-15 font-weight-bold">{fmtPrice(pv.display)}</div>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}

/** Kenar çubuğu widget başlığı: h3.section-title (alt çizgi) + sağ üstte ‹ › oklar (şablon: top-10, font-size-17). */
export function SideHeader({ title, ctl, field = "title", sm = true, className = "mb-2" }) {
  if (!title && !ctl) return null;
  return (
    <div className={`d-flex justify-content-between align-items-end border-bottom border-color-1 pd-sbh ${className}`}>
      {title ? <h3 className={`section-title${sm ? " section-title__sm" : ""} mb-0 pb-3 font-size-18`} data-pd-field={field}>{title}</h3> : <span />}
      {ctl && (
        <div className="pd-sbh__arrows" data-testid="header-arrows">
          <button type="button" aria-label="Önceki" disabled={!ctl.canPrev} onClick={ctl.prev}><i className="fa fa-angle-left" /></button>
          <button type="button" aria-label="Sonraki" disabled={!ctl.canNext} onClick={ctl.next}><i className="fa fa-angle-right" /></button>
        </div>
      )}
    </div>
  );
}

function chunk(arr, n) { const out = []; for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n)); return out; }

export default function Render({ settings, ctx }) {
  const st = settings;
  const rows = useProductSource(st.source);
  const preview = !!(ctx && ctx.preview);
  const head = (ctl) => <SideHeader title={st.title} ctl={ctl} className="mb-0" />;
  if (rows === null) {
    return (
      <aside className="mb-2 position-relative pd-spl" data-testid="sidebar-product-list" aria-busy="true">
        {head(null)}
        <ul className="list-unstyled products-group mb-0">{[0, 1, 2].map((i) => <li key={i} className="pd-spl__skel" />)}</ul>
      </aside>
    );
  }
  if (!rows.length) {
    if (st.empty_text) return <aside className="mb-2 pd-spl">{head(null)}<p className="text-gray-5 mt-3" data-pd-field="empty_text">{st.empty_text}</p></aside>;
    return preview ? <div className="pd-stub" data-empty="">Bu kaynakta ürün yok.</div> : null;
  }
  const per = Number(st.per_page) || 0;
  const list = (items) => (
    <ul className="list-unstyled products-group mb-0 overflow-visible">
      {items.map((p) => <SideItem key={p.id} product={p} showOld={st.show_old_price} />)}
    </ul>
  );
  if (per > 0 && rows.length > per) {
    return (
      <aside className="mb-2 position-relative pd-spl" data-testid="sidebar-product-list">
        <BlockCarousel value={{ per_view: { 0: 1 }, arrows: "header", dots: false, drag: true, speed: 300 }} className="pt-3"
          header={(ctl) => head(ctl)}>
          {chunk(rows, per).map((g, i) => <div key={i}>{list(g)}</div>)}
        </BlockCarousel>
      </aside>
    );
  }
  return (
    <aside className="mb-2 position-relative pd-spl" data-testid="sidebar-product-list">
      {head(null)}
      <div className="pt-3">{list(rows)}</div>
    </aside>
  );
}
