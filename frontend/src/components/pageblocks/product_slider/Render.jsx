// C2 product_slider — şablon recently-added-products-carousel: başlık (sağda ‹ ›) + ürün karuseli. Grup C geliştirir.
import SectionHeader from "../_shared/SectionHeader";
import BlockCarousel from "../_shared/BlockCarousel";
import ProductCard from "../_shared/ProductCard";
import useProductSource from "../_shared/useProductSource";

export default function Render({ settings }) {
  const st = settings;
  const list = useProductSource(st.source);
  if (!list || !list.length) return null;
  const arrowsInHeader = st.carousel?.arrows === "header";
  return (
    <div data-testid="product-slider" className={st.show_discount_badge ? "pd-show-badge" : "pd-hide-badge"}>
      <div className="position-relative">
        <BlockCarousel value={st.carousel} className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0"
          header={(ctl) => <SectionHeader value={{ ...st.header, right: st.header?.right === "arrows" && !arrowsInHeader ? "none" : st.header?.right }} arrows={ctl} className="mb-2 border-color-1" />}>
          {list.map((p, i) => (
            <div className="js-slide products-group" key={p.id}>
              <ProductCard product={p} card={st.card} listName="product_slider" index={i} />
            </div>
          ))}
        </BlockCarousel>
      </div>
    </div>
  );
}
