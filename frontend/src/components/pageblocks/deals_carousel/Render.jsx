// B4 deals_carousel — "Haftanın Fırsatları".
//   gallery (vars.): şablon v1.0 deals-of-the-week-carousel.php — slayt başına tek fırsat: solda 600×600 görsel +
//                    dikey küçük resimler + koyu kazanç kutusu, sağda ad, fiyat, stok çubuğu, geri sayım;
//                    üstte "‹ Önceki Fırsat | Sonraki Fırsat ›" metin bağlantıları.
//   cards          : v2.0 home-v7/v8/v11 "Deals of The Day" — başlıkta geri sayım hapı + bağlantı, kart karuseli.
// Fırsat öğesinde ürün seçilmediyse ürün kaynağının sıradaki ürünü kullanılır (vars.: indirimdekiler).
import { useEffect, useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard from "../_shared/ProductCard";
import BlockCarousel from "../_shared/BlockCarousel";
import { useCountdown } from "../_shared/Countdown";
import { plainText } from "../_shared/schema";
import { optimizeImg, galleryImages } from "../../../lib/img";
import { CountdownV1, DealImage, OnsaleBody, SavingsBox, StockV1, savingsAmount, stockValues } from "../deals_tabs/DealParts";
import { HeaderArrows, HeaderLink, HeaderPills, HeaderTitle } from "./HeaderParts";
import "./style.css";

const BASE = { category_ids: [], include_children: true, tag: "", brand_ids: [], sort: "default", exclude_out_of_stock: false, exclude_ids: [], fill_with: "none" };
const pad2 = (n) => String(n).padStart(2, "0");

function GallerySlide({ deal, idx, product }) {
  const imgs = galleryImages(product);
  const main = deal.main_image?.url ? [deal.main_image.url] : imgs.slice(0, 1);
  const own = (deal.thumbnails || []).map((t, i) => ({ t, i })).filter((x) => x.t?.image?.url);
  const thumbs = own.length ? own.map(({ t, i }) => ({ url: t.image.url, field: `deals.${idx}.thumbnails.${i}.image` })) : imgs.slice(1, 4).map((u) => ({ url: u }));
  const all = [...main.map((u) => ({ url: u, field: deal.main_image?.url ? `deals.${idx}.main_image` : undefined })), ...thumbs];
  const [cur, setCur] = useState(0);
  const shown = all[cur] || all[0];
  const cd = useCountdown(deal.countdown);
  if (deal.countdown?.enabled && cd.expired && deal.countdown.on_expire === "hide_block") return null;
  const { sold, available } = stockValues(deal.stock, product);
  const titleHtml = plainText(deal.title_override) ? deal.title_override : "";
  return (
    <div className="pdb-dow__slide" data-testid={`dow-slide-${idx}`}>
      <div className="pdb-dow__media">
        <SavingsBox savings={deal.savings} amount={savingsAmount(deal.savings, product)} field={`deals.${idx}.savings`} />
        <div className="pdb-dow__images">
          <span className="pdb-dow__main">
            <DealImage image={shown ? { url: shown.url, alt: product.name } : null} product={product} size={[600, 600]} width={800} field={shown?.field} />
          </span>
          {all.length > 1 && (
            <span className="pdb-dow__thumbs">
              {all.slice(0, 4).map((t, i) => (
                <button type="button" key={`${t.url}${i}`} className={i === cur ? "current" : ""} onClick={() => setCur(i)} aria-label={`${product.name} ${i + 1}`}>
                  <span className="pdb-img" style={{ aspectRatio: "1 / 1" }}><img src={optimizeImg(t.url, 180)} alt="" loading="lazy" /></span>
                </button>
              ))}
            </span>
          )}
        </div>
      </div>
      <div className="pdb-dow__content">
        <OnsaleBody product={product} titleOverride={titleHtml} titleField={`deals.${idx}.title_override`} image={null} listName="deals_of_week" hideImage />
        <StockV1 stock={deal.stock} sold={sold} available={available} field={`deals.${idx}.stock`} />
        <CountdownV1 value={deal.countdown} field={`deals.${idx}.countdown`} />
      </div>
    </div>
  );
}

/** BlockCarousel kontrollerini (prev/next/canPrev/canNext) karusel dışındaki başlık satırına taşır. */
function CtlBridge({ ctl, onCtl }) {
  useEffect(() => { onCtl(ctl); }, [ctl.canPrev, ctl.canNext, ctl.prev, ctl.next]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/** Başlık satırının sağ tarafı: bağlantı | haplar | oklar (+ karusel okları "Başlıkta" ise). */
function HeaderRight({ h, ctl, arrows, active, onPill, linkClass = "" }) {
  return (
    <>
      {h.right === "pills" && <HeaderPills h={h} active={active} onPill={onPill} className="ml-md-auto" />}
      {h.right === "link" && <HeaderLink h={h} className={`ml-md-auto ${linkClass}`} />}
      {(h.right === "arrows" || arrows) && <HeaderArrows ctl={ctl} className={h.right === "link" || h.right === "pills" ? "ml-3" : "ml-auto"} />}
    </>
  );
}

function Gallery({ st }) {
  const [ctl, setCtl] = useState(null);
  const deals = (st.deals || []).map((d, i) => ({ ...d, _idx: i }));
  const autoCount = deals.filter((d) => !d.product).length;
  const pool = useProductSource(autoCount ? { ...BASE, ...(st.source || {}), limit: Math.max(autoCount, Number(st.source?.limit) || 0) } : null);
  const picked = useMemo(() => deals.filter((d) => d.product).map((d) => d.product), [deals]);
  const manual = useProductSource(picked.length ? { ...BASE, kind: "manual", product_ids: picked, limit: picked.length } : null);
  if (!deals.length) return null;
  if ((autoCount && !pool) || (picked.length && !manual)) return <div className="pdb-dow__box"><div className="pdb-skel" style={{ height: 420 }} /></div>;
  const byId = new Map((manual || []).map((p) => [String(p.id), p]));
  const used = new Set(picked.map(String));
  const free = (pool || []).filter((p) => !used.has(String(p.id)));
  let k = 0;
  const slides = deals.map((d) => ({ d, p: d.product ? byId.get(String(d.product)) : free[k++] })).filter((x) => x.p);
  if (!slides.length) return null;
  const h = st.header || {};
  const c = st.gallery_carousel || {};
  // şablon: "‹ Önceki Fırsat | Sonraki Fırsat ›" metin bağlantıları; "İki yanda/Dışta" seçilirse yan oklar onların yerine geçer
  const side = c.arrows === "side" || c.arrows === "outer";
  const headArrows = slides.length > 1 && (h.right === "arrows" || c.arrows === "header");
  const right = <HeaderRight h={h} ctl={ctl} arrows={headArrows} />;
  const hasRight = (h.right === "pills" && (h.pills || []).some((x) => x && x.label)) || (h.right === "link" && h.link?.label) || headArrows;
  return (
    <section className="pdb-dow" data-testid="deals-carousel">
      {h.title && h.tag === "sr-only" && <HeaderTitle h={h} />}
      {((h.title && h.tag !== "sr-only") || hasRight) && (
        <header className={`pdb-dow__header d-flex flex-wrap align-items-center${h.align === "center" ? " justify-content-center text-center" : ""}`}>
          {h.tag !== "sr-only" && <HeaderTitle h={h} className={`pdb-dow__title${h.underline ? " pdb-line" : ""}`} />}
          {right}
        </header>
      )}
      <div className="pdb-dow__box" style={st.border_color ? { borderColor: st.border_color } : undefined}>
        <BlockCarousel value={{ ...c, per_view: { 0: 1 }, rows: 1, slides_to_scroll: 1, gutter: 0 }} ariaLabel={plainText(h.title)}
          header={(ctl2) => (
            <>
              <CtlBridge ctl={ctl2} onCtl={setCtl} />
              {slides.length > 1 && !side ? <NavLinks st={st} ctl={ctl2} /> : null}
            </>
          )}>
          {slides.map(({ d, p }) => <GallerySlide key={d._id || d._idx} deal={d} idx={d._idx} product={p} />)}
        </BlockCarousel>
      </div>
    </section>
  );
}

function NavLinks({ st, ctl }) {
  if (!st.prev_label && !st.next_label) return null;
  return (
    <div className="pdb-dow__nav">
      <button type="button" className="pdb-prev" onClick={ctl.prev} disabled={!ctl.canPrev}><i className="fa fa-angle-left" /><span data-pd-field="prev_label">{st.prev_label}</span></button>
      <button type="button" className="pdb-next" onClick={ctl.next} disabled={!ctl.canNext}><span data-pd-field="next_label">{st.next_label}</span><i className="fa fa-angle-right" /></button>
    </div>
  );
}

function HeaderCountdown({ cd }) {
  const s = useCountdown(cd);
  if (!cd?.enabled) return null;
  if (s.expired && cd.on_expire === "hide_timer") return null;
  if (s.expired && cd.on_expire === "show_text") return <div className="ml-md-5 align-self-center font-size-15" data-pd-field="header_countdown.expired_text">{cd.expired_text}</div>;
  const units = (cd.units && cd.units.length ? cd.units : ["hours", "minutes", "seconds"]).filter((u) => !(u === "days" && cd.hide_zero_days && s.days === 0));
  const val = (u) => (u === "hours" && !units.includes("days") ? s.hours + s.days * 24 : s[u]);
  return (
    <div className="js-countdown pdb-dow-cards__cd ml-md-5 mt-md-n1 border-top border-color-1 border-md-top-0 w-100 w-md-auto pt-2 pt-md-0 mb-2 mb-md-0" data-testid="deal-countdown">
      <div className="flex-horizontal-center d-inline-flex bg-primary py-2 align-self-start height-33 px-5 rounded-pill text-gray-2 font-size-15 font-weight-bold text-lh-1">
        {cd.heading && <h5 className="font-size-15 mb-0 font-weight-bold text-lh-1 mr-1" data-pd-field="header_countdown.heading">{cd.heading}</h5>}
        {units.map((u, i) => (
          <span key={u} className="d-inline-flex">
            {i > 0 && <span>:</span>}
            <span className="px-1">{cd.pad === false ? val(u) : pad2(val(u))}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Cards({ st }) {
  const h = st.header || {};
  const [ctl, setCtl] = useState(null);
  const [pill, setPill] = useState(null);
  const pills = h.right === "pills" ? (h.pills || []) : [];
  const active = pill ?? Math.max(0, pills.findIndex((x) => x && x.active));
  const cur = pills[active];
  const src = cur && cur.as_tab && cur.source && cur.source.kind ? cur.source : st.source;
  const list = useProductSource(src);
  const cd = useCountdown(st.header_countdown);
  if (st.header_countdown?.enabled && cd.expired && st.header_countdown.on_expire === "hide_block") return null;
  if (list && !list.length && !pills.length) return null;
  const c = st.carousel || {};
  const headArrows = c.arrows === "header";
  return (
    <div className="pdb-dow-cards" data-testid="deals-carousel">
      {h.title && h.tag === "sr-only" && <HeaderTitle h={h} />}
      <div className={`d-flex border-bottom border-color-1 flex-lg-nowrap flex-wrap border-md-down-top-0 border-sm-bottom-0 mb-2 mb-md-0 align-items-center${h.align === "center" ? " justify-content-center" : ""}`}>
        {h.tag !== "sr-only" && <HeaderTitle h={h} defTag="h3" className={`section-title${h.underline === false ? "" : " section-title__full"} mb-0 pb-2 font-size-22`} />}
        <HeaderCountdown cd={st.header_countdown} />
        <HeaderRight h={h} ctl={ctl} arrows={headArrows} active={active} onPill={(i) => setPill(i)} />
      </div>
      {!list ? <div className="pdb-skel mt-3" style={{ height: 330 }} /> : !list.length ? null : (
        <BlockCarousel value={c} className="overflow-hidden u-slick-overflow-visble pt-3 pb-6 px-1" header={(ctl2) => <CtlBridge ctl={ctl2} onCtl={setCtl} />}
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-4" ariaLabel={plainText(h.title)}>
          {list.map((p, i) => (
            <div className="js-slide products-group" key={p.id}>
              <ProductCard product={p} card={st.card || "grid_small"} listName="deals_of_day" index={i} />
            </div>
          ))}
        </BlockCarousel>
      )}
    </div>
  );
}

export default function Render({ settings }) {
  return settings._variant === "cards" ? <Cards st={settings} /> : <Gallery st={settings} />;
}
