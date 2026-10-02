// C5 product_columns — Alt Ürün Sütunları (footer üstü).
// Şablon: v2.0 index "Footer-top-widget" (container d-none d-lg-block; col-wd-3 col-lg-4 sütunlar, h3.section-title
// .section-title__sm font-size-18 + border-bottom mb-5; li.product-item__list 75×75 görsel + ad + (yıldız) + fiyat;
// ≥1480'de 330×360 tanıtım görseli) — v1.0 footer widget'larının (Featured / Onsale / Top Rated) karşılığı.
// Bu blok sayfadaysa Footer kendi ürün bandını gizler (PageRenderer.hasProductColumns).
import { Link } from "react-router-dom";
import { useProductActions } from "../../ProductCard";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import useProductSource from "../_shared/useProductSource";
import { optimizeImg, firstImage } from "../../../lib/img";
import { fmtPrice, priceOf } from "../../electro/format";
import { EmptyNote } from "../product_slider/viewport";

const LG = { 1: "col-lg-12", 2: "col-lg-6", 3: "col-lg-4", 4: "col-lg-3" };
const WD = { 1: "col-wd-12", 2: "col-wd-6", 3: "col-wd-4", 4: "col-wd-3", 5: "col-wd-2gdot4" };

export function ratingOf(p) {
  const r = Number(p.rating ?? p.average_rating ?? p.rating_avg ?? 0);
  return Number.isFinite(r) ? Math.max(0, Math.min(5, r)) : 0;
}

function ListItem({ product, showRating, showOldPrice, listName, index }) {
  const a = useProductActions(product, { listName, index });
  const pv = priceOf(product);
  const r = ratingOf(product);
  return (
    <li className="product-item product-item__list row no-gutters mb-6 remove-divider" data-testid={`product-card-${product.id}`}>
      <div className="col-auto">
        <Link to={a.href} onClick={a.select} className="d-block width-75 text-center">
          <span className="el-img-box el-img-box--sq">
            <img className="img-fluid" src={optimizeImg(firstImage(product) || "/placeholder.jpg", 150)} alt={product.name} loading="lazy" decoding="async" width="75" height="75" />
          </span>
        </Link>
      </div>
      <div className="col pl-4 d-flex flex-column">
        <h5 className="product-item__title mb-0"><Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link></h5>
        {showRating && r > 0 && (
          <div className="text-warning mb-2" aria-label={`${r.toFixed(1)} / 5`} data-testid="pcol-rating">
            {[1, 2, 3, 4, 5].map((n) => <small key={n} className={n <= Math.round(r) ? "fas fa-star" : "far fa-star text-muted"} />)}
          </div>
        )}
        {pv.hasDiscount ? (
          <div className="prodcut-price mt-auto flex-horizontal-center">
            <ins className="font-size-15 text-decoration-none">{fmtPrice(pv.display)}</ins>
            {showOldPrice && <del className="font-size-12 text-gray-9 ml-2">{fmtPrice(pv.list)}</del>}
          </div>
        ) : (
          <div className="prodcut-price mt-auto"><div className="font-size-15">{fmtPrice(pv.display)}</div></div>
        )}
      </div>
    </li>
  );
}

function Column({ col, i, cls, preview }) {
  const list = useProductSource(col.source);
  if (list && !list.length && !preview) return null;
  return (
    <div className={cls} data-testid={`pcol-${i}`}>
      <div className="widget-column">
        <div className="border-bottom border-color-1 mb-5">
          <h3 className="section-title section-title__sm mb-0 pb-2 font-size-18" data-pd-field={`columns.${i}.title`}>
            {col.link?.url ? <SmartLink link={col.link} className="text-gray-90">{col.title}</SmartLink> : col.title}
          </h3>
        </div>
        {!list ? (
          <ul className="list-unstyled products-group" aria-hidden="true">
            {Array.from({ length: Math.min(3, col.source?.limit || 3) }).map((_, k) => <li key={k} className="el-skel mb-6" style={{ height: 75 }} />)}
          </ul>
        ) : !list.length ? (
          <EmptyNote preview text="Bu sütunun kaynağında ürün yok (vitrinde sütun gizlenir)." />
        ) : (
          <ul className="list-unstyled products-group">
            {list.slice(0, col.source?.limit || 3).map((p, k) => (
              <ListItem key={p.id} product={p} showRating={!!col.show_rating} showOldPrice={col.show_old_price !== false} listName="product_columns" index={k} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const cols = (st.columns || []).filter((c) => c && (c.title || c.source)).slice(0, 4);
  if (!cols.length) return <EmptyNote preview={ctx?.preview} text="Alt ürün sütunları: en az bir sütun ekleyin." />;
  const promo = !!(st.promo?.enabled);
  const n = cols.length;
  const colCls = ["col-12 col-md-6", LG[n] || "col-lg-4", WD[n + (promo ? 1 : 0)] || "col-wd-3"].join(" ");
  const hideBelow = st.min_screen === "lg" ? "d-none d-lg-block" : "";
  return (
    <div className={hideBelow} data-testid="product-columns">
      <div className="row">
        {cols.map((c, i) => <Column key={c._id || i} col={c} i={i} cls={colCls} preview={ctx?.preview} />)}
        {promo && (
          <div className={`${WD[n + 1] || "col-wd-3"} d-none d-wd-block`} data-testid="pcol-promo">
            <SmartLink link={st.promo.link} fallback="div" className="d-block">
              <SmartImage image={st.promo.image} size={[330, 360]} width={660} field="promo.image" />
            </SmartLink>
          </div>
        )}
      </div>
    </div>
  );
}
