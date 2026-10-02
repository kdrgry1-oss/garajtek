// C5 product_columns — footer üstü 3 sütun küçük ürün listesi (Öne Çıkan / İndirimdeki / En Çok Beğenilen).
// Bu blok sayfadaysa Footer kendi ürün bandını gizler. Grup C geliştirir.
import ProductCard from "../_shared/ProductCard";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import useProductSource from "../_shared/useProductSource";

function Column({ col, i, n }) {
  const list = useProductSource(col.source);
  if (!list || !list.length) return null;
  return (
    <div className={`${n >= 4 ? "col-md-3" : "col-md-4"} mb-6 mb-md-0${col.show_old_price === false ? " pd-no-old-price" : ""}`}>
      <div className="widget-column">
        <div className="border-bottom border-color-1 mb-5">
          <h3 className="section-title section-title__sm mb-0 pb-2 font-size-18" data-pd-field={`columns.${i}.title`}>{col.title}</h3>
        </div>
        <ul className="list-unstyled products-group">
          {list.slice(0, col.source?.limit || 3).map((p) => <ProductCard key={p.id} product={p} card="list_small" as="li" listName="product_columns" />)}
        </ul>
      </div>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const cols = (st.columns || []).filter((c) => c && c.title).slice(0, 4);
  if (!cols.length) return null;
  const promo = st.promo?.enabled && st.promo.image?.url;
  return (
    <div data-testid="product-columns">
      <style>{".electro .pd-no-old-price .prodcut-price del{display:none}"}</style>
      <div className="row">
        {cols.map((c, i) => <Column key={c._id || i} col={c} i={i} n={cols.length + (promo ? 1 : 0)} />)}
        {promo && (
          <div className="col-wd-3 d-none d-wd-block">
            <SmartLink link={st.promo.link} fallback="div" className="d-block"><SmartImage image={st.promo.image} width={660} field="promo.image" /></SmartLink>
          </div>
        )}
      </div>
    </div>
  );
}
