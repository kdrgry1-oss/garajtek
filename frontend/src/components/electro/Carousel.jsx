// Electro "js-slick-carousel u-slick" karşılığı — jQuery/slick yerine embla-carousel-react.
// Electro'nun pagination (u-slick__pagination--long) ve ok (u-slick__arrow-*) işaretlemesini üretir.
//   perView: { base, sm, md, lg, xl, wd } — kırılım başına görünen slayt sayısı.
import { Children, useCallback, useEffect, useState } from "react";
import useEmblaCarousel from "embla-carousel-react";

export default function Carousel({
  children,
  perView = { base: 1 },
  loop = false,
  autoplay = 0,
  className = "",
  trackClassName = "",
  slideClassName = "",
  dots = true,
  dotsClassName = "text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 mt-4",
  arrows = false,
  arrowsClassName = "",
  arrowLeftClassName = "fa fa-angle-left",
  arrowRightClassName = "fa fa-angle-right",
  gutter = 0,
  ariaLabel,
  testId,
  onSelect,
}) {
  const [emblaRef, api] = useEmblaCarousel({ align: "start", loop, containScroll: "trimSnaps", slidesToScroll: 1, dragFree: false });
  const [snaps, setSnaps] = useState([]);
  const [sel, setSel] = useState(0);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);

  const sync = useCallback(() => {
    if (!api) return;
    setSnaps(api.scrollSnapList());
    setSel(api.selectedScrollSnap());
    setCanPrev(api.canScrollPrev());
    setCanNext(api.canScrollNext());
    if (onSelect) onSelect(api.selectedScrollSnap());
  }, [api, onSelect]);

  useEffect(() => {
    if (!api) return undefined;
    sync();
    api.on("select", sync);
    api.on("reInit", sync);
    return () => { api.off("select", sync); api.off("reInit", sync); };
  }, [api, sync]);

  useEffect(() => {
    if (!api || !autoplay) return undefined;
    const t = setInterval(() => {
      if (document.hidden) return;
      if (api.canScrollNext()) api.scrollNext(); else api.scrollTo(0);
    }, autoplay);
    return () => clearInterval(t);
  }, [api, autoplay]);

  const pv = { base: 1, ...perView };
  const style = {
    "--el-n-base": pv.base,
    "--el-n-sm": pv.sm || pv.base,
    "--el-n-md": pv.md || pv.sm || pv.base,
    "--el-n-lg": pv.lg || pv.md || pv.sm || pv.base,
    "--el-n-xl": pv.xl || pv.lg || pv.md || pv.sm || pv.base,
    "--el-n-wd": pv.wd || pv.xl || pv.lg || pv.md || pv.sm || pv.base,
    "--el-gutter": `${gutter}px`,
  };
  const items = Children.toArray(children).filter(Boolean);

  return (
    <div className={`js-slick-carousel u-slick slick-initialized el-carousel position-relative ${className}`} style={style} aria-roledescription="carousel" aria-label={ariaLabel} data-testid={testId}>
      <div className="el-carousel__viewport" ref={emblaRef}>
        <div className={`el-carousel__track ${trackClassName}`}>
          {items.map((child, i) => (
            <div className={`js-slide el-carousel__slide ${slideClassName}`} key={child.key ?? i} role="group" aria-roledescription="slide" aria-label={`${i + 1} / ${items.length}`}>
              {child}
            </div>
          ))}
        </div>
      </div>
      {arrows && items.length > 1 && (
        <>
          <button type="button" aria-label="Önceki" className={`slick-arrow ${arrowsClassName} ${arrowLeftClassName} ${canPrev || loop ? "" : "slick-disabled"}`} onClick={() => api && api.scrollPrev()} />
          <button type="button" aria-label="Sonraki" className={`slick-arrow ${arrowsClassName} ${arrowRightClassName} ${canNext || loop ? "" : "slick-disabled"}`} onClick={() => api && api.scrollNext()} />
        </>
      )}
      {dots && snaps.length > 1 && (
        <ul className={`js-pagination ${dotsClassName}`} role="tablist">
          {snaps.map((_, i) => (
            <li key={i} className={i === sel ? "slick-active slick-current" : ""} onClick={() => api && api.scrollTo(i)} role="presentation">
              <span role="tab" aria-selected={i === sel} aria-label={`Slayt ${i + 1}`} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
