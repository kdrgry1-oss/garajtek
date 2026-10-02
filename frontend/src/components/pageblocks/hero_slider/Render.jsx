// A1 hero_slider — şablon home-v1-slider (T1 inc/blocks/homepage/home-v1-slider.php + _sliders.scss + electro.js
// L98-319): tam genişlik 1920×466 arka plan, `col-md-offset-3 col-md-5` açıklama (dikey menüye yer bırakır),
// .hero-1/.hero-2 başlık, .hero-subtitle(-v2), .hero-v2-price, .hero-action-btn; katmanlar fadeInDown-N
// (500/700/1000/1000 ms gecikme, 800 ms, easeOutCubic). Owl: autoplay 5000, fade, loop, noktalar.
// v2.0 varyantları: v2_product (index), boxed_side_banners (v4/v10), rounded_with_deals (v9), fullscreen (v11),
// menu_strip (v7). Her metin/görsel/bağlantı data-pd-field taşır; tüm davranış ayarlardan gelir.
import { useLayoutEffect, useState } from "react";
import BlockCarousel from "../_shared/BlockCarousel";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import Placeholder from "../_shared/Placeholder";
import useProductSource from "../_shared/useProductSource";
import { useCountdown } from "../_shared/Countdown";
import { plainText, resolveResponsive } from "../_shared/schema";
import { useProductActions } from "../../ProductCard";
import { optimizeImg, firstImage } from "../../../lib/img";
import { fmtPrice, priceOf } from "../../electro/format";
import { trackSelectPromotion } from "../../../lib/dataLayer";
import "./hero.css";

const CAPTION_COL = {
  offset3_5: "offset-lg-3 col-lg-5 col-12",
  wide8: "col-lg-8 col-12",
  center: "offset-lg-2 col-lg-8 col-12",
  left4: "col-lg-5 col-xl-4 col-12",
  offset1_6: "offset-xl-1 col-md-6 col-12",
};
const EASING = { easeOutCubic: "cubic-bezier(0.215, 0.61, 0.355, 1)", linear: "linear" };
const BOXED = ["boxed_side_banners", "rounded_with_deals", "menu_strip"];
const promo = (id, name) => { try { trackSelectPromotion({ promotionId: id, promotionName: name }); } catch { /* yoksay */ } };
const pad2 = (n) => String(n).padStart(2, "0");

/** Açık dikey menü hero'dan uzunsa hero menünün altına kadar uzar (--el-hero-h). Yalnız tam genişlik varyantlar. */
function useHeroClearance(base, on) {
  useLayoutEffect(() => {
    if (!on || typeof window === "undefined") return undefined;
    const root = document.documentElement;
    let last = 0;
    const calc = () => {
      const vm = document.querySelector('.el-header-wrap [data-testid="vertical-menu"].show');
      const hero = document.querySelector(".pd-hero--bleed");
      const vr = vm ? vm.getBoundingClientRect() : null;
      if (!vr || !vr.height || !hero || window.innerWidth < 1200) { if (last) { root.style.removeProperty("--el-hero-h"); last = 0; } return; }
      const need = Math.ceil(vr.bottom - hero.getBoundingClientRect().top) + 24;
      const h = need > base ? need : 0;
      if (h !== last) { if (h) root.style.setProperty("--el-hero-h", `${h}px`); else root.style.removeProperty("--el-hero-h"); last = h; }
    };
    calc();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(calc) : null;
    const wrap = document.querySelector(".el-header-wrap");
    if (ro) { ro.observe(document.body); if (wrap) ro.observe(wrap); }
    window.addEventListener("resize", calc);
    return () => { if (ro) ro.disconnect(); window.removeEventListener("resize", calc); root.style.removeProperty("--el-hero-h"); };
  }, [base, on]);
}

/** Katman: etkin slaytta animasyon sınıfı + gecikme/süre (slayt değişince yeniden oynar). */
function Layer({ cfg, active, easing, as: Tag = "div", className = "", children, ...rest }) {
  const eff = cfg && cfg.effect && cfg.effect !== "none" ? cfg.effect : null;
  const on = eff && active;
  const style = on ? {
    animationDelay: `${Number(cfg.delay) || 0}ms`, animationDuration: `${Number(cfg.duration) || 800}ms`, animationTimingFunction: easing,
  } : undefined;
  return <Tag className={`${className}${on ? ` pd-hero-layer pd-hero-anim-${eff}` : ""}`} style={style} {...rest}>{children}</Tag>;
}

function Caption({ s, i, active, easing }) {
  const f = `slides.${i}`;
  const a = s.animation || {};
  const layout = s.layout || "promo";
  const href = linkHref(s.button?.link);
  const hasBtn = !!(s.button?.text && href);
  const btnCls = `pd-hero__btn pd-hero__btn--${s.button?.style || "primary"}`;
  return (
    <div className={`pd-hero__caption text-${s.text_align || "left"}`}>
      {layout === "promo" && s.pretitle && (
        <Layer cfg={a.pretitle} active={active} easing={easing} className="pd-hero__pretitle" data-pd-field={`${f}.pretitle`}
          style={{ color: s.accent_color || undefined }}>{s.pretitle}</Layer>
      )}
      {plainText(s.title) && (
        <Layer cfg={a.title} active={active} easing={easing}>
          <RichText as="h2" html={s.title} field={`${f}.title`} className={layout === "price" ? "pd-hero__title pd-hero__title--1" : "pd-hero__title pd-hero__title--2"} />
        </Layer>
      )}
      {layout === "price" && s.subtitle && (
        <Layer cfg={a.subtitle} active={active} easing={easing} className="pd-hero__subtitle" data-pd-field={`${f}.subtitle`}>{s.subtitle}</Layer>
      )}
      {layout === "price" && (s.price || s.price_prefix) && (
        <Layer cfg={a.price} active={active} easing={easing} className="pd-hero__price">
          {s.price_prefix && <span className="pd-hero__price-prefix" data-pd-field={`${f}.price_prefix`}>{s.price_prefix}</span>}
          {s.price_prefix && s.price && <br />}
          {s.price && <span className="pd-hero__price-value" data-pd-field={`${f}.price`}>{s.price}</span>}
        </Layer>
      )}
      {hasBtn && (
        <Layer cfg={a.button} active={active} easing={easing} className="pd-hero__action">
          <SmartLink link={s.button.link} className={btnCls} field={`${f}.button.text`}
            onClick={() => promo(`hero_${i + 1}`, plainText(s.title) || href)}>{s.button.text}</SmartLink>
        </Layer>
      )}
    </div>
  );
}

function Slide({ s, i, st, active, easing, boxed }) {
  const f = `slides.${i}`;
  const layout = s.layout || "promo";
  const href = linkHref(s.button?.link);
  const hasBtn = !!(s.button?.text && href);
  const col = CAPTION_COL[st.caption_column] || CAPTION_COL.offset3_5;
  const prod = s.product_image?.url ? s.product_image : null;
  const inner = (
    <div className={`row pd-hero__row${boxed ? " mx-0" : ""}`}>
      <div className={`${col} pd-hero__col`}><Caption s={s} i={i} active={active} easing={easing} /></div>
      {prod && (
        <Layer cfg={s.animation?.product_image} active={active} easing={easing} className="col d-none d-md-flex align-items-center justify-content-center pd-hero__media">
          <SmartImage image={prod} width={840} eager={i === 0} field={`${f}.product_image`} className="img-fluid" />
        </Layer>
      )}
    </div>
  );
  return (
    <div className={`pd-hero__slide${s.background?.mobile_url ? " pd-hero__slide--mimg" : ""}`} data-testid={`hero-slide-${i}`} style={{ color: s.text_color || undefined }}>
      {s.background?.url || s.background?.mobile_url ? (
        <SmartImage image={s.background} className="pd-hero__bg" fit="cover" width={1920} eager={i === 0} field={`${f}.background`}
          alt={s.background?.alt || plainText(s.title)} />
      ) : (
        <div className="pd-hero__bg el-ph el-ph--fill" aria-hidden="true" data-pd-field={`${f}.background`} data-pd-placeholder="">
          <span className="el-ph__size el-ph__size--hero">1920 × 466</span>
        </div>
      )}
      {layout !== "image_only" && (boxed ? <div className="pd-hero__inner">{inner}</div> : <div className="container pd-hero__container">{inner}</div>)}
      {(layout === "image_only" || !hasBtn) && href && (
        <SmartLink link={s.button.link} className="pd-hero__hit" aria-label={plainText(s.title) || s.background?.alt || href}
          onClick={() => promo(`hero_${i + 1}`, plainText(s.title) || href)} />
      )}
    </div>
  );
}

function Slider({ st, slides, boxed }) {
  const [active, setActive] = useState(0);
  const easing = EASING[st.easing] || EASING.easeOutCubic;
  const dots = `pd-hero__dots pd-hero__dots--${st.dots_style || "v1"}`;
  if (slides.length < 2) return <Slide s={slides[0]} i={0} st={st} active easing={easing} boxed={boxed} />;
  return (
    <BlockCarousel value={st.carousel} ariaLabel="Kampanyalar" onSelect={setActive} dotsClassName={dots}
      sideArrowsClassName="pd-hero__arrow" arrowLeftClassName="fa fa-angle-left pd-hero__arrow--l" arrowRightClassName="fa fa-angle-right pd-hero__arrow--r">
      {slides.map((s, i) => <Slide key={s._id || i} s={s} i={i} st={st} active={i === active} easing={easing} boxed={boxed} />)}
    </BlockCarousel>
  );
}

function SideBanner({ b, i }) {
  const f = `side_banners.${i}`;
  return (
    <li className="px-2 px-xl-0 flex-shrink-0 flex-xl-shrink-1 mb-3">
      <SmartLink link={b.link} fallback="div" className={`pd-hero__side min-height-126 max-width-320 py-1 py-xl-2 d-flex align-items-center text-gray-90 pd-hero__side--${b.style || "gray"}`}>
        <div className="col col-lg-6 col-xl-5 col-wd-6 mb-3 mb-lg-0 pr-lg-0">
          <SmartImage image={b.image} size={[246, 176]} width={300} className="img-fluid" field={`${f}.image`} />
        </div>
        <div className="col col-lg-6 col-xl-7 col-wd-6 pr-xl-4">
          <RichText as="div" html={b.text} className="mb-2 pb-1 font-size-18 font-weight-light text-ls-n1 text-lh-23 text-uppercase" field={`${f}.text`} />
          {b.cta && (
            <div className="link text-gray-90 font-weight-bold font-size-15">
              <span data-pd-field={`${f}.cta`}>{b.cta}</span>
              <span className="link__icon ml-1"><span className="link__icon-inner"><i className="ec ec-arrow-right-categproes" /></span></span>
            </div>
          )}
        </div>
      </SmartLink>
    </li>
  );
}

function DealTimer({ cd }) {
  const t = useCountdown(cd);
  if (!cd?.enabled || (t.expired && cd.on_expire !== "zero")) {
    return t.expired && cd?.on_expire === "show_text" ? <div className="text-center mt-2 font-size-13" data-pd-field="side_deals.countdown.expired_text">{cd.expired_text}</div> : null;
  }
  const units = (cd.units || []).filter((u) => ["days", "hours", "minutes", "seconds"].includes(u));
  const val = (u) => (u === "hours" && !units.includes("days") ? t.hours + t.days * 24 : t[u]);
  return (
    <div className="text-center mt-n3">
      <div className="flex-horizontal-center d-inline-flex bg-primary py-2 height-33 px-5 rounded-pill text-gray-2 font-size-15 font-weight-bold text-lh-1">
        {cd.heading && <h5 className="font-size-14 mb-0 font-weight-bold text-lh-1 mr-1" data-pd-field="side_deals.countdown.heading">{cd.heading}</h5>}
        {units.map((u, k) => (
          <span key={u} className="d-flex">{k > 0 && <span>:</span>}<span className="px-1">{cd.pad === false ? val(u) : pad2(val(u))}</span></span>
        ))}
      </div>
    </div>
  );
}

function DealCard({ p, sd }) {
  const a = useProductActions(p, { listName: "hero_side_deals" });
  const pv = priceOf(p);
  const pct = pv.hasDiscount && pv.list > 0 ? Math.round((1 - pv.display / pv.list) * 100) : 0;
  const stock = Number(p.stock) || 0;
  return (
    <div data-pd-data="">
      <div className="border border-width-2 border-color-6 borders-radius-15 px-4 py-3 bg-white product-item">
        <h5 className="font-size-14 mb-3"><SmartLink to={a.href} onClick={a.select} className="text-blue font-weight-bold">{p.name}</SmartLink></h5>
        <div className="mb-5">
          <SmartLink to={a.href} onClick={a.select} className="d-block text-center">
            <img className="img-fluid m-auto" src={optimizeImg(firstImage(p) || "/placeholder.jpg", 400)} alt={p.name} loading="lazy" style={{ aspectRatio: "190 / 150", objectFit: "contain" }} />
          </SmartLink>
        </div>
        <div className="mb-2">
          <div className="flex-center-between mb-1 position-relative">
            {sd.show_discount && pct > 0 && <div className="position-absolute font-size-12 font-weight-bold left-0 top-0 bg-green rounded text-white text-lh-21 px-2 mt-n4">-%{pct}</div>}
            <div className="pr-3">
              <ins className="font-size-20 mr-2 text-red text-decoration-none">{fmtPrice(pv.display)}</ins>
              {pv.hasDiscount && <del className="font-size-12 text-gray-6">{fmtPrice(pv.list)}</del>}
            </div>
            <div className="prodcut-add-cart">
              <a href={a.href} onClick={a.add} className="btn-add-cart btn-primary transition-3d-hover" aria-label="Sepete ekle"><i className="ec ec-add-to-cart" /></a>
            </div>
          </div>
          {stock > 0 && sd.left_label && <span className="font-size-12 text-gray-5">{stock} <span data-pd-field="side_deals.left_label">{sd.left_label}</span></span>}
        </div>
      </div>
      <DealTimer cd={sd.countdown} />
    </div>
  );
}

function SideDeals({ sd }) {
  const rows = useProductSource(sd?.source);
  if (rows === null) return <div className="pd-hero__deals-skel border border-width-2 border-color-6 borders-radius-15" aria-hidden="true" />;
  if (!rows.length) return null;
  return (
    <BlockCarousel value={{ per_view: { 0: 1 }, arrows: "side", dots: false, loop: true, drag: true, speed: 300 }} ariaLabel="Fırsatlar"
      sideArrowsClassName="d-none d-lg-inline-block u-slick__arrow-normal u-slick__arrow-centered--y font-size-18 mx-3">
      {rows.map((p) => <DealCard key={p.id} p={p} sd={sd} />)}
    </BlockCarousel>
  );
}

function CategoryStrip({ items }) {
  if (!items.length) return null;
  return (
    <ul className="list-unstyled row row-cols-2 row-cols-md-3 row-cols-xl-5 mx-n2 mt-4 mb-0 pd-hero__strip">
      {items.map((c, i) => (
        <li key={c._id || i} className="col px-2 mb-3">
          <SmartLink link={c.link} fallback="div" className="d-flex align-items-center bg-white rounded-sm p-2 text-gray-90 h-100">
            <span className="pd-hero__strip-img mr-3">
              {c.image?.url ? <SmartImage image={c.image} width={160} className="img-fluid" field={`category_strip.${i}.image`} />
                : <Placeholder size={[1, 1]} field={`category_strip.${i}.image`} label="300×300" />}
            </span>
            <span className="font-size-14 font-weight-bold" data-pd-field={`category_strip.${i}.label`}>{c.label}</span>
          </SmartLink>
        </li>
      ))}
    </ul>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const v = st._variant || "v1";
  const slides = (st.slides || []).filter(Boolean);
  const boxed = BOXED.includes(v) || v === "boxed_side_banners";
  const h = st.height || {};
  const pt = st.caption_padding_top || {};
  const hd = Number(resolveResponsive(h, "desktop")) || 485;
  useHeroClearance(hd, !boxed);
  if (!slides.length) return null;
  const scale = Math.max(0.4, Math.min(1.2, (Number(st.mobile_font_scale) || 71.43) / 100));
  const style = {
    "--pd-hero-bg": st.background_color || "transparent",
    "--pd-hero-h-d": `${hd}px`, "--pd-hero-h-t": `${Number(resolveResponsive(h, "tablet")) || hd}px`, "--pd-hero-h-m": `${Number(resolveResponsive(h, "mobile")) || 300}px`,
    "--pd-hero-pt-d": `${Number(resolveResponsive(pt, "desktop")) || 0}px`, "--pd-hero-pt-t": `${Number(resolveResponsive(pt, "tablet")) || 0}px`,
    "--pd-hero-pt-m": `${Number(resolveResponsive(pt, "mobile")) || 0}px`,
    "--pd-hero-fs-m": `${(14 * scale).toFixed(2)}px`,
    "--pd-hero-radius": `${Number(st.radius) || 0}px`,
  };
  const slider = <Slider st={st} slides={slides} boxed={boxed} />;
  if (!boxed) {
    return <div className={`pd-hero pd-hero--bleed pd-hero--${v}`} data-testid="hero-slider" style={style}>{slider}</div>;
  }
  const banners = (st.side_banners || []).filter(Boolean).slice(0, 3);
  const strip = v === "menu_strip" ? (st.category_strip || []).filter(Boolean) : [];
  return (
    <div className={`pd-hero pd-hero--boxed pd-hero--${v}${v === "menu_strip" ? " pd-hero--band" : ""}`} data-testid="hero-slider" style={style}>
      <div className="container">
        <div className="row">
          <div className={v === "rounded_with_deals" ? "col-lg-8 col-xl-9 mb-3 mb-lg-0" : "col-xl pr-xl-2 mb-4 mb-xl-0"}>
            <div className="pd-hero__box">{slider}</div>
          </div>
          {v === "rounded_with_deals" ? (
            <div className="col-lg-4 col-xl-3"><SideDeals sd={st.side_deals || {}} /></div>
          ) : banners.length > 0 && (
            <div className="col-xl-auto pl-xl-2">
              <ul className="list-unstyled row flex-nowrap flex-xl-wrap overflow-auto mx-n2 mx-xl-0 d-xl-block mb-0">
                {banners.map((b, i) => <SideBanner key={b._id || i} b={b} i={i} />)}
              </ul>
            </div>
          )}
        </div>
        {strip.length > 0 && <CategoryStrip items={strip} />}
      </div>
    </div>
  );
}
