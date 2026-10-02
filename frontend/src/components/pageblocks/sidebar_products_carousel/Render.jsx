// D8 sidebar_products_carousel — şablon v2.0 home-v2 kenar çubuğu “Featured Products”:
//   aside > .position-relative > .border-bottom.border-color-1.mb-2 h3.section-title.pb-3.font-size-18 (+ sağ üstte oklar)
//   > .js-slick-carousel (1'li) > .js-slide.products-group > .product-item.remove-divider.text-center
//     > .product-item__inner.remove-prodcut-hover.px-wd-4.p-2.p-md-3 > img (212×200) + kategori (font-size-12 text-gray-5)
//     + h5.product-item__title a.text-blue.font-weight-bold + .prodcut-price .text-gray-100
import { Link } from "react-router-dom";
import { useProductActions } from "../../ProductCard";
import { fmtPrice, priceOf } from "../../electro/format";
import { firstImage, optimizeImg } from "../../../lib/img";
import BlockCarousel from "../_shared/BlockCarousel";
import useProductSource from "../_shared/useProductSource";
import { SideHeader } from "../sidebar_product_list/Render";
import "../sidebar_product_list/style.css";

function Slide({ product, showCat, showOld }) {
  const a = useProductActions(product, { listName: "sidebar_carousel" });
  const pv = priceOf(product);
  return (
    <div className="product-item remove-divider text-center" data-testid={`product-card-${product.id}`}>
      <div className="product-item__outer h-100">
        <div className="product-item__inner remove-prodcut-hover px-wd-4 p-2 p-md-3">
          <div className="product-item__body pb-xl-2">
            <div className="mb-2">
              <Link to={a.href} onClick={a.select} className="d-block text-center">
                <span className="el-img-box" style={{ aspectRatio: "212 / 200" }}>
                  <img className="img-fluid" src={optimizeImg(firstImage(product) || "/placeholder.jpg", 440)} alt={product.name} loading="lazy" />
                </span>
              </Link>
            </div>
            {showCat && product.category_name && <div className="mb-2"><span className="font-size-12 text-gray-5">{product.category_name}</span></div>}
            <h5 className="mb-4 product-item__title"><Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link></h5>
            <div className="mb-1">
              <div className="prodcut-price">
                {pv.hasDiscount ? (
                  <div className="d-flex align-items-center justify-content-center flex-wrap">
                    <ins className="text-red text-decoration-none mr-2">{fmtPrice(pv.display)}</ins>
                    {showOld && <del className="font-size-12 text-gray-9">{fmtPrice(pv.list)}</del>}
                  </div>
                ) : <div className="text-gray-100">{fmtPrice(pv.display)}</div>}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const rows = useProductSource(st.source);
  const preview = !!(ctx && ctx.preview);
  if (rows === null) {
    return (
      <aside className="position-relative pd-spc" data-testid="sidebar-products-carousel" aria-busy="true">
        <SideHeader title={st.title} sm={false} />
        <div className="pd-spl__skel" style={{ height: 300 }} />
      </aside>
    );
  }
  if (!rows.length) {
    if (st.empty_text) return <aside className="pd-spc"><SideHeader title={st.title} sm={false} /><p className="text-gray-5" data-pd-field="empty_text">{st.empty_text}</p></aside>;
    return preview ? <div className="pd-stub" data-empty="">Bu kaynakta ürün yok.</div> : null;
  }
  const car = { ...(st.carousel || {}), per_view: { 0: 1 }, rows: 1 };
  const header = car.arrows === "header" ? (ctl) => <SideHeader title={st.title} ctl={ctl} sm={false} /> : undefined;
  return (
    <aside className="position-relative pd-spc" data-testid="sidebar-products-carousel">
      {!header && <SideHeader title={st.title} sm={false} />}
      <BlockCarousel value={car} header={header} className="u-slick u-slick-overflow-visble">
        {rows.map((p) => <div key={p.id} className="products-group"><Slide product={p} showCat={st.show_category} showOld={st.show_old_price} /></div>)}
      </BlockCarousel>
    </aside>
  );
}
