// C4 products_carousel_with_image — Arka Plan Görselli Ürün Karuseli.
// Şablon: v1.0 homepage-3/products-carousel-with-image.php + _products-carousel-with-image.scss (tam genişlik #f9f9f9
// bant, cover arka plan 1919×1026, 58px üst boşluk, 85px alt boşluk; solda 665×616 şeffaf PNG, sağda başlık + ‹ › +
// 2'li karusel, 30px boşluk, beyaz kart içi, ayırıcı ve noktalar yok) ve v2.0 home-v3 "Television Entertainment".
import SectionHeader from "../_shared/SectionHeader";
import BlockCarousel from "../_shared/BlockCarousel";
import ProductCard from "../_shared/ProductCard";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import useProductSource from "../_shared/useProductSource";
import { optimizeImg } from "../../../lib/img";
import { EmptyNote, Skeleton, useLastActive } from "../product_slider/viewport";
import "./style.css";

const pos = (f) => (f && typeof f.x === "number" ? `${Math.round(f.x * 100)}% ${Math.round(f.y * 100)}%` : "center center");

export default function Render({ settings, ctx }) {
  const st = settings;
  const list = useProductSource(st.source);
  const c = st.carousel || {};
  const { onSelect, perView } = useLastActive(c, list ? list.length : 0);
  if (list && !list.length) return <EmptyNote preview={ctx?.preview} text="Görselli ürün karuseli: seçilen kaynakta ürün yok (vitrinde bu bölüm gizlenir)." />;
  const header = st.header || {};
  const right = st.image_position === "right";
  const bg = st.background_image?.url;
  const head = (ctl) => <SectionHeader value={{ ...header, right: header.right === "arrows" && c.arrows !== "header" ? "none" : header.right }} arrows={ctl} className="pcwi__header border-color-1" />;
  return (
    <div className={`pcwi pcwi--${right ? "right" : "left"}`} data-testid="products-carousel-with-image">
      {bg ? (
        <div className="pcwi__bg" data-pd-field="background_image" role="presentation"
          style={{ backgroundImage: `url("${optimizeImg(bg, 1920)}")`, backgroundPosition: pos(st.background_image.focal) }} />
      ) : null}
      <div className={st.content_width === "full" ? "container-fluid" : "container"}>
        <div className={`row${right ? " flex-md-row-reverse" : ""}`}>
          <div className={`pcwi__image col-12 col-md-6 ${st.side_image_mobile === false ? "d-none d-md-block" : "mb-5 mb-md-0"}`}>
            <SmartLink link={st.side_image_link} fallback="div" className="d-block">
              <SmartImage image={st.side_image} size={[665, 616]} width={900} field="side_image" />
            </SmartLink>
          </div>
          <div className="pcwi__products col-12 col-md-6">
            {!list ? (
              <>{head(null)}<Skeleton height={340} count={Math.min(perView, 2)} /></>
            ) : (
              <BlockCarousel value={c} onSelect={onSelect} header={head} ariaLabel={header.title || undefined}
                className="pcwi__carousel overflow-hidden"
                dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 mt-4">
                {list.map((p, i) => (
                  <div className="products-group" key={p.id}>
                    <ProductCard product={p} card={st.card} listName="products_carousel_with_image" index={i} />
                  </div>
                ))}
              </BlockCarousel>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
