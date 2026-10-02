// Her bloğun ortak sarmalayıcısı (SPEC §2.4): _section (genişlik, bant rengi/görseli, iç/alt boşluk, yazı
// rengi, bağlantı hedefi, ek sınıf), _visibility (masaüstü ≥1200 / tablet 768–1199 / mobil <768),
// _reveal (IntersectionObserver ile waypoint benzeri giriş animasyonu). Önizlemede tıkla-seç çerçevesi.
import { useEffect, useRef, useState } from "react";
import { usePageCtx } from "./PageCtx";
import { DEVICES, isObj } from "./schema";
import { optimizeImg } from "../../../lib/img";

const SUF = { desktop: "d", tablet: "t", mobile: "m" };

function spacingVars(sec) {
  const v = {};
  const pad = sec.padding;
  const mb = sec.margin_bottom;
  DEVICES.forEach((d) => {
    const p = isObj(pad) && isObj(pad[d]) ? pad[d] : (isObj(pad) && "top" in pad ? pad : null);
    if (p) { v[`--pd-pt-${SUF[d]}`] = `${Number(p.top) || 0}px`; v[`--pd-pb-${SUF[d]}`] = `${Number(p.bottom) || 0}px`; }
    const m = isObj(mb) ? mb[d] : mb;
    if (m !== undefined && m !== null && m !== "") v[`--pd-mb-${SUF[d]}`] = `${Number(m) || 0}px`;
  });
  return v;
}

function useReveal(enabled, offset, once) {
  const ref = useRef(null);
  const [inView, setInView] = useState(!enabled);
  useEffect(() => {
    if (!enabled) { setInView(true); return undefined; }
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") { setInView(true); return undefined; }
    const pct = Math.max(0, Math.min(100, Number(offset) || 90));
    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { setInView(true); if (once !== false) io.disconnect(); }
        else if (once === false) setInView(false);
      });
    }, { rootMargin: `0px 0px -${100 - pct}% 0px` });
    io.observe(el);
    return () => io.disconnect();
  }, [enabled, offset, once]);
  return [ref, inView];
}

export default function BlockFrame({ block, schema, settings, index = 0, children, revealDefault = true }) {
  const ctx = usePageCtx();
  const sec = settings._section || {};
  const vis = settings._visibility || {};
  const rv = settings._reveal || {};
  const revealOn = !!(rv.enabled && revealDefault && index > 0);
  const [ref, inView] = useReveal(revealOn, rv.offset, rv.once);
  const width = schema?.layout === "sidebar" ? "sidebar" : (sec.width || schema?.layout || "container");
  const cls = [
    "pd-block", `pd-block--${block.type}`,
    vis.desktop === false ? "pd-hide-desktop" : "", vis.tablet === false ? "pd-hide-tablet" : "", vis.mobile === false ? "pd-hide-mobile" : "",
    sec.css_class || "", sec.background_image?.url ? "pd-block--bgimg" : "",
    revealOn ? `pd-reveal${inView ? ` pd-reveal--in pd-anim-${rv.effect || "fadeIn"}` : ""}` : "",
    ctx.preview && ctx.selectedId === block.id ? "pd-selected" : "",
  ].filter(Boolean).join(" ");
  const style = {
    ...spacingVars(sec),
    ...(sec.background ? { backgroundColor: sec.background } : {}),
    ...(sec.background_image?.url ? { backgroundImage: `url("${optimizeImg(sec.background_image.url, 1920)}")` } : {}),
    ...(sec.text_color ? { color: sec.text_color } : {}),
  };
  const inner = width === "full_bleed" || width === "sidebar" ? children
    : <div className={`container${width === "wide" ? " pd-wide" : ""}`}>{children}</div>;
  const onClick = ctx.preview && ctx.onSelect ? (e) => { if (!e.target.closest(".pd-insert")) ctx.onSelect(block.id, e); } : undefined;
  return (
    <section ref={ref} id={sec.anchor_id || undefined} className={cls} style={style} data-pd-block={block.id}
      data-block-type={block.type} onClick={onClick}>
      {ctx.preview && ctx.selectedId === block.id && <span className="pd-block__label">{block.title || schema?.title}</span>}
      {inner}
    </section>
  );
}
