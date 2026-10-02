// C2 product_slider — Ürün Karuseli (Yeni Eklenenler / kategori / trend).
// Şablon: v1.0 recently-added-products-carousel.php (başlık h2.h1 + sağda ‹ › + 6'lı Owl, .last-active) ve
// v2.0 index "Recently Viewed" (border-bottom başlık, u-slick pb-7 pt-2 px-1, uzun noktalar). Tüm karusel
// davranışı (kırılım başına adet, oklar, noktalar, otomatik oynatma, döngü, belirme, son kart ayırıcısı) şemadan.
import SectionHeader from "../_shared/SectionHeader";
import BlockCarousel from "../_shared/BlockCarousel";
import ProductCard from "../_shared/ProductCard";
import useProductSource from "../_shared/useProductSource";
import { EmptyNote, Skeleton, useLastActive } from "./viewport";
import "./style.css";

export default function Render({ settings, ctx }) {
  const st = settings;
  const list = useProductSource(st.source);
  const c = st.carousel || {};
  const { onSelect, last, perView } = useLastActive(c, list ? list.length : 0);
  const header = st.header || {};
  if (list && !list.length) return <EmptyNote preview={ctx?.preview} text="Ürün karuseli: seçilen kaynakta ürün yok (vitrinde bu bölüm gizlenir)." />;
  const right = header.right === "arrows" && c.arrows !== "header" ? "none" : header.right;
  const badge = st.show_discount_badge ? "pcs-badge-on" : "pcs-badge-off";
  const head = (ctl) => <SectionHeader value={{ ...header, right }} arrows={ctl} className="mb-2 border-color-1" />;
  if (!list) {
    return (
      <div data-testid="product-slider">
        {head(null)}
        <Skeleton height={300} count={Math.min(perView, 6)} />
      </div>
    );
  }
  return (
    <div data-testid="product-slider" className={`pcs ${badge}`}>
      <div className="position-relative">
        <BlockCarousel value={c} onSelect={onSelect} ariaLabel={header.title || undefined}
          className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0"
          header={head}>
          {list.map((p, i) => (
            <div className={`products-group${i === last ? " pc-last-active" : ""}`} key={p.id}>
              <ProductCard product={p} card={st.card} listName="product_slider" index={i} />
            </div>
          ))}
        </BlockCarousel>
      </div>
    </div>
  );
}
