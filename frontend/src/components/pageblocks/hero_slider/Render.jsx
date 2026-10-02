// A1 hero_slider — şablon home-v1-slider (tam genişlik 1920×466; solda açık "Tüm Kategoriler" menüsü).
// Grup A geliştirir (varyantlar v2/v3/v2_product/boxed_side_banners/rounded_with_deals/fullscreen/menu_strip).
import { useLayoutEffect, useState } from "react";
import BlockCarousel from "../_shared/BlockCarousel";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import { plainText, resolveResponsive } from "../_shared/schema";
import { trackSelectPromotion } from "../../../lib/dataLayer";
import "./hero.css";

const CAPTION_COL = {
  offset3_5: "offset-xl-3 col-xl-5 col-md-7 col-10",
  wide8: "col-xl-8 col-md-9 col-11",
  center: "offset-xl-2 col-xl-8 col-12 text-center",
  left4: "col-xl-4 col-md-6 col-10",
};
const BTN = { primary: "btn-primary", dark: "btn-dark", outline: "btn-outline-primary" };
const promo = (id, name) => { try { trackSelectPromotion({ promotionId: id, promotionName: name }); } catch { /* yoksay */ } };

/** Açık dikey menü hero'dan uzunsa hero menünün altına kadar uzar (--el-hero-h). */
function useHeroClearance(base) {
  useLayoutEffect(() => {
    if (typeof window === "undefined") return undefined;
    const root = document.documentElement;
    let last = 0;
    const calc = () => {
      const vm = document.querySelector('.el-header-wrap [data-testid="vertical-menu"].show');
      const hero = document.querySelector(".pd-hero");
      if (!vm || !hero || window.innerWidth < 1200) { if (last) { root.style.removeProperty("--el-hero-h"); last = 0; } return; }
      const vr = vm.getBoundingClientRect();
      if (!vr.height) return;
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
  }, [base]);
}

function Layer({ anim, i, active, children, className = "", as: Tag = "div", ...rest }) {
  const eff = anim?.effect && anim.effect !== "none" ? anim.effect : null;
  const style = eff && active ? { animationDelay: `${(Number(anim.delay_step) || 0) * i}ms`, animationDuration: `${Number(anim.duration) || 1000}ms` } : undefined;
  return <Tag className={`${className}${eff && active ? ` pd-layer pd-anim-${eff}` : ""}`} style={style} {...rest}>{children}</Tag>;
}

function Slide({ s, i, st, active }) {
  const f = `slides.${i}`;
  const href = linkHref(s.button?.link);
  const hasBtn = !!(s.button?.text && href);
  const layout = s.layout || "promo";
  const align = s.text_align === "center" ? " text-center" : s.text_align === "right" ? " text-right" : "";
  const col = CAPTION_COL[st.caption_column] || CAPTION_COL.offset3_5;
  let li = 0;
  return (
    <div className="el-hero-v1__slide position-relative" data-testid={`hero-slide-${i}`} style={{ color: s.text_color || undefined }}>
      {s.background?.url || s.background?.mobile_url ? (
        <SmartImage image={s.background} className="el-hero-v1__img" fit="cover" width={1920} eager={i === 0} field={`${f}.background`} alt={s.background?.alt || plainText(s.title)} />
      ) : s.product_image?.url ? null : (
        <div className="el-hero-v1__img el-ph el-ph--fill" aria-hidden="true" data-pd-field={`${f}.background`} data-pd-placeholder="">
          <span className="el-ph__size el-ph__size--hero">1920 × 466</span>
        </div>
      )}
      {layout !== "image_only" && (
        <div className="container position-relative h-100">
          <div className="row el-hero-v1__row align-items-center">
            <div className={`${col} py-6 py-md-0 pd-hero__caption${align}`}>
              <div className="el-hero-v1__caption">
                {layout === "promo" && s.pretitle && (
                  <Layer anim={s.animation} i={li++} active={active} as="h6" className="pd-hero__pretitle mb-2" data-pd-field={`${f}.pretitle`}>{s.pretitle}</Layer>
                )}
                {plainText(s.title) && (
                  <Layer anim={s.animation} i={li++} active={active}>
                    <RichText as="h2" html={s.title} className={`pd-hero__title ${layout === "promo" ? "font-size-40" : "font-size-46"} text-lh-57 font-weight-light mb-2`} field={`${f}.title`} style={{ color: s.text_color || undefined }} />
                  </Layer>
                )}
                {layout === "price" && s.subtitle && (
                  <Layer anim={s.animation} i={li++} active={active} as="h6" className="font-size-15 font-weight-bold text-uppercase mb-3" data-pd-field={`${f}.subtitle`}>{s.subtitle}</Layer>
                )}
                {layout === "price" && s.price && (
                  <Layer anim={s.animation} i={li++} active={active} className="mb-4">
                    {s.price_prefix && <span className="font-size-13 text-uppercase" data-pd-field={`${f}.price_prefix`}>{s.price_prefix}</span>}
                    <div className="font-size-50 font-weight-bold text-lh-45" data-pd-field={`${f}.price`}>{s.price}</div>
                  </Layer>
                )}
                {hasBtn && (
                  <Layer anim={s.animation} i={li++} active={active}>
                    <SmartLink link={s.button.link} onClick={() => promo(`hero_${i + 1}`, plainText(s.title) || href)}
                      className={`btn ${BTN[s.button.style] || BTN.primary} transition-3d-hover rounded-lg font-weight-normal py-2 px-md-7 px-4 font-size-16 stretched-link`}
                      field={`${f}.button.text`}>{s.button.text}</SmartLink>
                  </Layer>
                )}
              </div>
            </div>
            {s.product_image?.url && (
              <div className="col-xl-4 col-md-5 d-none d-md-flex align-items-center el-hero-media">
                <SmartImage image={s.product_image} width={840} eager={i === 0} field={`${f}.product_image`} />
              </div>
            )}
          </div>
        </div>
      )}
      {!hasBtn && href && (
        <SmartLink link={s.button.link} className="el-hero-v1__hit" aria-label={plainText(s.title) || "Kampanya"} onClick={() => promo(`hero_${i + 1}`, plainText(s.title) || href)} />
      )}
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const slides = (st.slides || []).filter(Boolean);
  const [active, setActive] = useState(0);
  const h = st.height || {};
  const pt = st.caption_padding_top || {};
  useHeroClearance(Number(resolveResponsive(h, "desktop")) || 485);
  if (!slides.length) return null;
  const style = {
    backgroundColor: st.background_color || undefined,
    "--pd-hero-h-d": `${resolveResponsive(h, "desktop") || 485}px`, "--pd-hero-h-t": `${resolveResponsive(h, "tablet") || 400}px`, "--pd-hero-h-m": `${resolveResponsive(h, "mobile") || 300}px`,
    "--pd-hero-pt-d": `${resolveResponsive(pt, "desktop") || 0}px`, "--pd-hero-pt-t": `${resolveResponsive(pt, "tablet") || 0}px`, "--pd-hero-pt-m": `${resolveResponsive(pt, "mobile") || 0}px`,
  };
  return (
    <div className="el-hero-v1 pd-hero" data-testid="hero-slider" style={style}>
      {slides.length > 1 ? (
        <BlockCarousel value={st.carousel} ariaLabel="Kampanyalar" onSelect={setActive}
          dotsClassName="text-center position-absolute right-0 bottom-0 left-0 u-slick__pagination u-slick__pagination--long mb-3 mb-md-4 el-hero-v1__dots">
          {slides.map((s, i) => <Slide key={s._id || i} s={s} i={i} st={st} active={i === active} />)}
        </BlockCarousel>
      ) : <Slide s={slides[0]} i={0} st={st} active />}
    </div>
  );
}
