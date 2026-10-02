// A8 deal_slider — şablon v2.0 home-v5 "Slider Section" (L791, #thumbProgress + #thumbProgressNav) ve home-v8 (L1151,
// bg-primary bant). Slayt: .row.height-410-xl > .col-md-4 (h3 "LIMITED" 48 / h1 "WEEK DEAL" 72 / h6 alt yazı) +
// .col-md-4 ürün görseli (400×400) + .col-md-4 ürün adı, ins/del fiyat, geri sayım kutuları (beyaz, 2px ana renk
// çerçeve), stok çubuğu. Altında 5'li metin sekmeleri (u-slick-thumb-progress__custom). v8: .col-md-5 görsel,
// .col-md-3 ad + fiyat + "Buy Now" (btn-outline-dark). Geçişler ayarlardaki karusel değerinden (fade/slide, otomatik).
import { useEffect, useMemo, useRef, useState } from "react";
import { useProductSources } from "../_shared/useProductSource";
import { useCountdown } from "../_shared/Countdown";
import StockBar from "../_shared/StockBar";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import { useProductActions } from "../../ProductCard";
import { optimizeImg, firstImage } from "../../../lib/img";
import { fmtPrice, priceOf } from "../../electro/format";
import "./deal.css";

const pad2 = (n) => String(n).padStart(2, "0");
const UNITS = ["days", "hours", "minutes", "seconds"];

function Timer({ cd, f }) {
  const t = useCountdown(cd);
  if (!cd?.enabled) return null;
  if (t.expired && cd.on_expire === "show_text") return <div className="mb-5 font-size-15" data-pd-field={`${f}.expired_text`}>{cd.expired_text}</div>;
  if (t.expired && cd.on_expire !== "zero") return null;
  let units = (cd.units || []).filter((u) => UNITS.includes(u));
  if (cd.hide_zero_days && t.days === 0) units = units.filter((u) => u !== "days");
  const val = (u) => (u === "hours" && !units.includes("days") ? t.hours + t.days * 24 : t[u]);
  return (
    <div className="mb-5">
      {cd.heading && <h6 className="font-size-15 mb-2" data-pd-field={`${f}.heading`}>{cd.heading}</h6>}
      <div className="js-countdown d-flex mx-n2 justify-content-center justify-content-md-start" aria-live="off" data-testid="deal-countdown">
        {units.map((u) => (
          <div className="text-lh-1 px-2 text-center" key={u}>
            <div className="bg-white rounded-sm border border-width-2 border-primary py-2 px-2 min-width-46">
              <div className="text-gray-2 font-size-34 mb-2"><span>{cd.pad === false ? val(u) : pad2(val(u))}</span></div>
              <div className="text-gray-2 font-size-12 text-center" data-pd-field={`${f}.labels.${u}`}>{cd.labels?.[u]}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Slide({ s, i, p, band, active }) {
  const f = `slides.${i}`;
  const a = useProductActions(p || { id: "", name: "" }, { listName: "deal_slider" });
  const pv = p ? priceOf(p) : null;
  const img = s.image_override?.url ? s.image_override : null;
  const src = !img && p ? firstImage(p) : "";
  const stock = p ? Number(p.stock) || 0 : 0;
  const sold = p ? Number(p.sold_count || p.sales_count || 0) : 0;
  const btnLink = linkHref(s.button?.link) ? s.button.link : (p ? a.href : "");
  const anim = active ? " pd-deal-in" : "";
  return (
    <div className="row height-410-xl mx-0 align-items-center pd-deal__slide" data-testid={`deal-slide-${i}`}>
      <div className="col-md-4 mt-6 mt-md-0 mb-4 mb-md-0">
        <div className={band ? "ml-wd-5" : "ml-xl-8"}>
          {s.kicker && <h3 className={`font-size-sl-48 font-weight-light mb-1 text-lh-1${anim}`} style={{ animationDelay: "50ms" }} data-pd-field={`${f}.kicker`}>{s.kicker}</h3>}
          {s.title && <h2 className={`${band ? "display-3" : "font-size-sl-72"} text-lh-1 font-weight-light mb-2 mb-lg-3 mb-wd-4${anim}`} style={{ animationDelay: "100ms" }} data-pd-field={`${f}.title`}>{s.title}</h2>}
          {s.subtitle && <h6 className={`font-size-15 font-weight-bold mb-0${anim}`} style={{ animationDelay: "200ms" }} data-pd-field={`${f}.subtitle`}>{s.subtitle}</h6>}
        </div>
      </div>
      <div className={`${band ? "col-md-5" : "col-md-4"} d-flex align-items-center justify-content-center ml-auto ml-md-0 mb-4 mb-md-0${active ? (band ? " pd-deal-in" : " pd-deal-zoom") : ""}`} style={{ animationDelay: "400ms" }}>
        {img ? <SmartImage image={img} width={600} className="img-fluid" field={`${f}.image_override`} />
          : p ? <SmartLink to={a.href} onClick={a.select} className="d-block" data-pd-data=""><img className="img-fluid" src={optimizeImg(src || "/placeholder.jpg", 600)} alt={p.name} loading="lazy" style={{ aspectRatio: band ? "576 / 310" : "1 / 1", objectFit: "contain" }} /></SmartLink>
            : <SmartImage image={null} size={band ? [576, 310] : [400, 400]} field={`${f}.image_override`} />}
      </div>
      <div className={band ? "col-md-3" : "col-md-4"} >
        <div className={`${band ? "mr-wd-8" : "mr-xl-14"}${active ? " pd-deal-in-r" : ""}`} style={{ animationDelay: "600ms" }}>
          {p ? (
            <div data-pd-data="">
              <h5 className={`${band ? "mb-5" : "mb-3"} font-size-17 product-item__title text-lh-default`}>
                <SmartLink to={a.href} onClick={a.select} className="text-blue font-weight-bold">
                  {s.title_override ? <span data-pd-field={`${f}.title_override`}>{s.title_override}</span> : p.name}
                </SmartLink>
              </h5>
              <div className={`prodcut-price d-flex align-items-end position-relative text-lh-1 ${band ? "mb-6" : "mb-5"}`}>
                {band && pv.hasDiscount && <del className="font-size-18 tex-gray-6 mb-1 mr-2">{fmtPrice(pv.list)}</del>}
                <ins className="font-size-34 text-red text-decoration-none">{fmtPrice(pv.display)}</ins>
                {!band && pv.hasDiscount && <del className="font-size-18 tex-gray-6 mb-1 ml-2">{fmtPrice(pv.list)}</del>}
              </div>
            </div>
          ) : null}
          <Timer cd={s.countdown} f={`${f}.countdown`} />
          {!band && s.stock?.show && p && (stock > 0 || sold > 0) && (
            <StockBar sold={sold} available={stock} soldLabel={s.stock.sold_label} availableLabel={s.stock.available_label} field={`${f}.stock`} className="mb-3" />
          )}
          {band && s.button?.text && linkHref(btnLink) && (
            <SmartLink link={typeof btnLink === "string" ? { kind: "url", url: btnLink } : btnLink} field={`${f}.button.text`}
              className="btn btn-outline-dark borders-radius-9 border-width-2 px-8 text-lh-23 py-2">{s.button.text}</SmartLink>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const band = st._variant === "primary_band";
  const slides = (st.slides || []).filter(Boolean).slice(0, 6);
  const sources = useMemo(() => [
    st.fallback_source || null,
    ...slides.map((s) => (s.product ? { kind: "manual", product_ids: [Array.isArray(s.product) ? s.product[0] : s.product], limit: 1 } : null)),
  ], [JSON.stringify(st.fallback_source), JSON.stringify(slides.map((s) => s.product))]); // eslint-disable-line react-hooks/exhaustive-deps
  const res = useProductSources(sources.map((x) => x || { kind: "manual", product_ids: [] }));
  const fb = res[0] || [];
  const used = new Set();
  const products = slides.map((s, i) => {
    const own = s.product && res[i + 1] && res[i + 1][0];
    if (own) { used.add(own.id); return own; }
    return null;
  });
  let k = 0;
  products.forEach((p, i) => {
    if (p) return;
    while (k < fb.length && used.has(fb[k].id)) k += 1;
    if (k < fb.length) { products[i] = fb[k]; used.add(fb[k].id); k += 1; }
  });
  const c = st.carousel || {};
  const n = slides.length;
  const [cur, setCur] = useState(0);
  const hover = useRef(false);
  useEffect(() => {
    if (!c.autoplay || n < 2) return undefined;
    const t = setInterval(() => { if (!(c.pause_on_hover && hover.current) && !document.hidden) setCur((x) => (x + 1 < n ? x + 1 : (c.loop || c.rewind ? 0 : x))); }, Math.max(1500, Number(c.interval) || 6000));
    return () => clearInterval(t);
  }, [c.autoplay, c.interval, c.pause_on_hover, c.loop, c.rewind, n]);
  if (!n) return null;
  const active = Math.min(cur, n - 1);
  const fade = c.transition !== "slide";
  const bg = !band && st.background?.url ? `url("${optimizeImg(st.background.url, 1400)}")` : undefined;
  const track = (
    <div className={`pd-deal__track${fade ? " pd-deal__track--fade" : ""}`} style={{ "--pd-deal-speed": `${Number(c.speed) || 400}ms`, ...(fade ? {} : { transform: `translateX(-${active * 100}%)` }) }}>
      {slides.map((s, i) => (
        <div key={s._id || i} className={`pd-deal__item${i === active ? " is-active" : ""}`} aria-hidden={i !== active}>
          <Slide s={s} i={i} p={products[i]} band={band} active={i === active} />
        </div>
      ))}
    </div>
  );
  const dots = c.dots && n > 1 ? (
    <ul className={`js-pagination text-center u-slick__pagination u-slick__pagination--long mb-0 mt-4 pd-deal__dots${c.dots === "mobile" ? " d-md-none" : ""}${band ? " u-slick__pagination--dark" : ""}`} role="tablist">
      {slides.map((s, i) => <li key={s._id || i} className={i === active ? "slick-active slick-current" : ""} onClick={() => setCur(i)} role="presentation"><span role="tab" aria-label={`Fırsat ${i + 1}`} aria-selected={i === active} /></li>)}
    </ul>
  ) : null;
  const wrapStyle = { color: st.text_color || undefined };
  if (band) {
    return (
      <div data-testid="deal-slider" className="pd-deal pd-deal--band" style={{ ...wrapStyle, backgroundColor: st.band_color || "var(--electro-primary, #fed700)" }}
        onMouseEnter={() => { hover.current = true; }} onMouseLeave={() => { hover.current = false; }}>
        <div className="container min-height-420 overflow-hidden position-relative">{track}{dots}</div>
      </div>
    );
  }
  return (
    <div data-testid="deal-slider" className="pd-deal pd-deal--thumbs" style={wrapStyle}
      onMouseEnter={() => { hover.current = true; }} onMouseLeave={() => { hover.current = false; }}>
      <div className="container">
        <div className="overflow-hidden">
          <div className="bg-img-hero min-height-420 pd-deal__bg" data-pd-field="background"
            style={{ backgroundImage: bg, backgroundColor: st.background_color || undefined }}>
            {track}
          </div>
        </div>
        {n > 1 && (
          <div className="u-slick u-slick--transform-off u-slick-thumb-progress__custom mx-xl-3 text-center font-size-13 d-none d-md-flex pd-deal__thumbs" role="tablist">
            {slides.map((s, i) => (
              <div key={s._id || i} className={`js-slide flex-fill${i === active ? " slick-current slick-active" : ""}`}>
                <button type="button" role="tab" aria-selected={i === active} className="js-slick-thumb-progress btn-link border-0 bg-transparent w-100" onClick={() => setCur(i)}>
                  <span data-pd-field={`slides.${i}.thumb_label`}>{s.thumb_label}</span>
                </button>
              </div>
            ))}
          </div>
        )}
        {dots}
      </div>
    </div>
  );
}
