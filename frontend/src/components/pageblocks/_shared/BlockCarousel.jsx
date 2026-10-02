// Şema `carousel` değeri → Embla tabanlı karusel (Owl v1 davranışını taklit eder, SPEC §2.3):
//   per_view (min-width kırılımları), slides_to_scroll, rows, gutter, autoplay/interval/pause_on_hover,
//   loop/rewind, transition (slide | fade), speed, dots (true | false | "mobile"), arrows
//   (none | header | side | outer), drag, last_active_divider.
// `header` verilirse ({prev,next,canPrev,canNext}) => düğüm; başlık satırındaki oklar buradan beslenir.
import { Children, useCallback, useEffect, useMemo, useRef, useState } from "react";
import useEmblaCarousel from "embla-carousel-react";

const BPS = [["base", 0], ["sm", 576], ["md", 768], ["lg", 992], ["xl", 1200], ["wd", 1480]];

/** {"0":1,"768":3,...} (min-width) → Bootstrap kırılımı başına adet. */
export function perViewVars(pv = {}) {
  const keys = Object.keys(pv || {}).map(Number).filter((n) => !Number.isNaN(n)).sort((a, b) => a - b);
  const at = (w) => { let v = 1; keys.forEach((k) => { if (k <= w) v = Number(pv[String(k)]) || v; }); return v; };
  const out = {};
  BPS.forEach(([n, w]) => { out[`--el-n-${n}`] = at(w === 576 ? 576 : w); });
  return out;
}

/** Kırılım tablosuna göre verilen genişlikte görünen adet (min-width, Owl tarzı). */
export function perViewAt(pv = {}, w = 0) {
  const keys = Object.keys(pv || {}).map(Number).filter((n) => !Number.isNaN(n)).sort((a, b) => a - b);
  let v = 1;
  keys.forEach((k) => { if (k <= w) v = Number(pv[String(k)]) || v; });
  return v;
}

const STD_BPS = new Set(BPS.map((b) => b[1]));
function useWinWidth() {
  const [w, setW] = useState(() => (typeof window !== "undefined" ? window.innerWidth : 1440));
  useEffect(() => {
    const on = () => setW(window.innerWidth);
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);
  return w;
}

function chunk(arr, n) { const out = []; for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n)); return out; }

function useAutoplay(api, { autoplay, interval, pause, rewind, loop, rootRef, count, onTick }) {
  useEffect(() => {
    if (!autoplay || count < 2) return undefined;
    let hover = false;
    const el = rootRef.current;
    const on = () => { hover = true; };
    const off = () => { hover = false; };
    if (pause && el) { el.addEventListener("mouseenter", on); el.addEventListener("mouseleave", off); }
    const t = setInterval(() => {
      if (document.hidden || (pause && hover)) return;
      onTick();
    }, Math.max(1000, Number(interval) || 5000));
    return () => { clearInterval(t); if (el) { el.removeEventListener("mouseenter", on); el.removeEventListener("mouseleave", off); } };
  }, [api, autoplay, interval, pause, rewind, loop, rootRef, count, onTick]);
}

function Dots({ count, sel, onGo, mode, className }) {
  if (!mode || count < 2) return null;
  return (
    <ul className={`js-pagination ${className}${mode === "mobile" ? " pd-dots-mobile" : ""}`} role="tablist">
      {Array.from({ length: count }).map((_, i) => (
        <li key={i} className={i === sel ? "slick-active slick-current" : ""} onClick={() => onGo(i)} role="presentation">
          <span role="tab" aria-selected={i === sel} aria-label={`Slayt ${i + 1}`} />
        </li>
      ))}
    </ul>
  );
}

function FadeCarousel({ items, c, header, className, dotsClassName, ariaLabel, testId, onSelect, sideArrows }) {
  const [sel, setSel] = useState(0);
  const rootRef = useRef(null);
  const n = items.length;
  const go = useCallback((i) => { const k = ((i % n) + n) % n; setSel(k); if (onSelect) onSelect(k); }, [n, onSelect]);
  const next = useCallback(() => { if (sel < n - 1 || c.loop || c.rewind || c.autoplay) go(sel + 1); }, [sel, n, c.loop, c.rewind, c.autoplay, go]);
  const prev = useCallback(() => { if (sel > 0 || c.loop) go(sel - 1); }, [sel, c.loop, go]);
  useAutoplay(null, { autoplay: c.autoplay, interval: c.interval, pause: c.pause_on_hover, rewind: c.rewind, loop: c.loop, rootRef, count: n, onTick: next });
  const ctl = { prev, next, canPrev: c.loop || sel > 0, canNext: c.loop || sel < n - 1 };
  return (
    <>
      {header ? header(ctl) : null}
      <div ref={rootRef} className={`js-slick-carousel u-slick slick-initialized el-carousel pd-carousel pd-carousel--fade position-relative ${className}`}
        style={{ "--pd-speed": `${Number(c.speed) || 300}ms` }} aria-roledescription="carousel" aria-label={ariaLabel} data-testid={testId}>
        <div className="pd-fade-track">
          {items.map((child, i) => (
            <div key={child.key ?? i} className={`pd-fade-slide js-slide${i === sel ? " is-active slick-current slick-active" : ""}`}
              role="group" aria-roledescription="slide" aria-label={`${i + 1} / ${n}`} aria-hidden={i !== sel}>{child}</div>
          ))}
        </div>
        {sideArrows(ctl)}
        <Dots count={n} sel={sel} onGo={go} mode={c.dots} className={dotsClassName} />
      </div>
    </>
  );
}

export default function BlockCarousel({
  value, children, header, className = "", slideClassName = "", trackClassName = "", ariaLabel, testId, onSelect,
  dotsClassName = "text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 mt-4",
  sideArrowsClassName = "u-slick__arrow-normal u-slick__arrow-centered--y",
  arrowLeftClassName = "fa fa-angle-left u-slick__arrow-classic-inner--left z-index-9",
  arrowRightClassName = "fa fa-angle-right u-slick__arrow-classic-inner--right",
  perView,
}) {
  const c = value || {};
  const raw = Children.toArray(children).filter(Boolean);
  const rows = Math.max(1, Number(c.rows) || 1);
  const items = rows > 1 ? chunk(raw, rows).map((g, i) => <div key={`r${i}`} className="pd-carousel__rows">{g}</div>) : raw;
  const pvTable = perView || c.per_view || { 0: 1 };
  const winW = useWinWidth();
  const nowPer = perViewAt(pvTable, winW);
  // Standart dışı kırılım (ör. şablondaki 1400 px) varsa CSS kırılımları yetmez → o anki genişliğe göre tek değer.
  const custom = Object.keys(pvTable).some((k) => !STD_BPS.has(Number(k)));
  const pvVars = useMemo(() => {
    if (!custom) return perViewVars(pvTable);
    const out = {};
    BPS.forEach(([n]) => { out[`--el-n-${n}`] = nowPer; });
    return out;
  }, [custom, nowPer, JSON.stringify(pvTable)]); // eslint-disable-line react-hooks/exhaustive-deps
  const fade = c.transition === "fade";
  const duration = Math.max(10, Math.min(60, Math.round((Number(c.speed) || 300) / 12)));
  const [emblaRef, api] = useEmblaCarousel(fade ? { active: false } : {
    align: "start", loop: !!c.loop, containScroll: "trimSnaps", slidesToScroll: Math.max(1, Number(c.slides_to_scroll) || 1),
    duration, watchDrag: c.drag !== false,
  });
  const [snaps, setSnaps] = useState([]);
  const [sel, setSel] = useState(0);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(false);
  const rootRef = useRef(null);

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
    api.on("select", sync); api.on("reInit", sync);
    return () => { api.off("select", sync); api.off("reInit", sync); };
  }, [api, sync]);
  useEffect(() => { if (api) api.reInit(); }, [api, items.length, pvVars]);

  const next = useCallback(() => { if (!api) return; if (api.canScrollNext()) api.scrollNext(); else if (c.rewind || c.autoplay) api.scrollTo(0); }, [api, c.rewind, c.autoplay]);
  const prev = useCallback(() => { if (!api) return; if (api.canScrollPrev()) api.scrollPrev(); else if (c.rewind) api.scrollTo(api.scrollSnapList().length - 1); }, [api, c.rewind]);
  useAutoplay(api, { autoplay: !fade && c.autoplay, interval: c.interval, pause: c.pause_on_hover, rewind: c.rewind, loop: c.loop, rootRef, count: items.length, onTick: next });

  const sideArrows = (ctl) => ((c.arrows === "side" || c.arrows === "outer") && items.length > 1 ? (
    <>
      <button type="button" aria-label="Önceki" className={`slick-arrow ${sideArrowsClassName} ${arrowLeftClassName} ${ctl.canPrev || c.rewind ? "" : "slick-disabled"}`} onClick={ctl.prev} />
      <button type="button" aria-label="Sonraki" className={`slick-arrow ${sideArrowsClassName} ${arrowRightClassName} ${ctl.canNext || c.rewind ? "" : "slick-disabled"}`} onClick={ctl.next} />
    </>
  ) : null);

  if (fade) {
    return <FadeCarousel items={items} c={c} header={header} className={className} dotsClassName={dotsClassName} ariaLabel={ariaLabel} testId={testId} onSelect={onSelect} sideArrows={sideArrows} />;
  }
  const ctl = { prev, next, canPrev: canPrev || !!c.rewind, canNext: canNext || !!c.rewind || !!c.loop };
  // Noktalar şablondaki gibi SAYFA başına (görünen adet kadar kart = 1 nokta), kaydırma konumu başına değil.
  const per = Math.max(1, nowPer);
  const lastSnap = Math.max(0, snaps.length - 1);
  const dotPages = c.loop ? snaps.length : Math.min(snaps.length, Math.ceil(items.length / per));
  const dotSel = c.loop ? sel : (sel >= lastSnap && dotPages > 0 ? dotPages - 1 : Math.min(dotPages - 1, Math.floor(sel / per)));
  const goPage = (i) => { if (!api) return; api.scrollTo(c.loop ? i : Math.min(i * per, lastSnap)); };
  const style = { ...pvVars, "--el-gutter": `${Number(c.gutter) || 0}px` };
  return (
    <>
      {header ? header(ctl) : null}
      <div ref={rootRef} className={`js-slick-carousel u-slick slick-initialized el-carousel pd-carousel position-relative${c.last_active_divider ? " pd-last-active" : ""} ${className}`}
        style={style} aria-roledescription="carousel" aria-label={ariaLabel} data-testid={testId}>
        <div className="el-carousel__viewport" ref={emblaRef}>
          <div className={`el-carousel__track ${trackClassName}`}>
            {items.map((child, i) => (
              <div className={`js-slide el-carousel__slide ${slideClassName}`} key={child.key ?? i} role="group" aria-roledescription="slide" aria-label={`${i + 1} / ${items.length}`}>
                {child}
              </div>
            ))}
          </div>
        </div>
        {sideArrows(ctl)}
        <Dots count={dotPages} sel={dotSel} onGo={goPage} mode={c.dots} className={dotsClassName} />
      </div>
    </>
  );
}
