// C3 products_carousel_tabs — Sekmeli Ürün Karuseli.
// Şablon: v1.0 product-carousel-tab.php (home-v2: ortalı nav-inline sekmeler, columns-3) ve
// homepage-3/products-carousel-tabs.php (home-v3: sola yaslı, columns-4); v2.0 home-v3 "Tab Prodcut Section"
// (nav-classic nav-tab: kalın etkin sekme + 10×4 ana renk dil) ve home-v5/v6 (başlık + nav-pills nav-tab-pill
// hap sekmeler + opsiyonel 390×370 yan banner, tab-content u-slick__tab).
// Sekmelerin ürünleri tek istekte birlikte çözülür; yalnız etkin sekmenin karuseli monte edilir → gizli sekme
// görünür olduğunda karusel sıfırdan (doğru genişlikle) ölçülür.
import { useEffect, useMemo, useState } from "react";
import BlockCarousel, { perViewVars } from "../_shared/BlockCarousel";
import ProductCard from "../_shared/ProductCard";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import { useProductSources } from "../_shared/useProductSource";
import { EmptyNote, Skeleton, useLastActive } from "../product_slider/viewport";
import "../product_slider/style.css";
import "./style.css";

function Tabs({ tabs, active, onPick, variant }) {
  if (variant === "pill_header") {
    return (
      <ul className="w-100 w-xl-auto nav nav-pills nav-tab-pill mb-2 pt-3 pt-xl-0 mb-0 border-top border-color-1 border-xl-top-0 align-items-center font-size-15 font-size-15-lg flex-nowrap flex-xl-wrap overflow-auto overflow-xl-visble pr-0" role="tablist">
        {tabs.map(({ t, i }) => (
          <li className="nav-item flex-shrink-0 flex-xl-shrink-1" key={t._id || i}>
            <a className={`nav-link rounded-pill${active === i ? " active" : ""}`} href={`#pct-${i}`} role="tab" aria-selected={active === i}
              onClick={(e) => { e.preventDefault(); onPick(i); }} data-pd-field={`tabs.${i}.label`}>{t.label}</a>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <div className="position-relative bg-white text-center z-index-2">
      <ul className={`nav nav-classic nav-tab ${variant === "left" ? "justify-content-start" : "justify-content-start justify-content-md-center"} flex-nowrap flex-md-wrap overflow-auto overflow-md-visble`} role="tablist">
        {tabs.map(({ t, i }) => (
          <li className="nav-item flex-shrink-0" key={t._id || i}>
            <a className={`nav-link${active === i ? " active" : ""}`} href={`#pct-${i}`} role="tab" aria-selected={active === i}
              onClick={(e) => { e.preventDefault(); onPick(i); }}>
              <div className="d-md-flex justify-content-md-center align-items-md-center" data-pd-field={`tabs.${i}.label`}>{t.label}</div>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Pane({ list, st, idx, card }) {
  const c = st.carousel || {};
  const { onSelect, last, perView } = useLastActive(c, list ? list.length : 0);
  if (!list) return <Skeleton height={card === "horizontal" ? 200 : 330} count={Math.min(perView, 5)} />;
  if (!list.length) return <div className="py-6 text-center text-gray-90" data-pd-field="empty_text">{st.empty_text}</div>;
  if (st.display === "grid") {
    return (
      <ul className="row list-unstyled products-group no-gutters el-carousel pct-grid" style={perViewVars(c.per_view)}>
        {list.map((p, i) => (
          <ProductCard key={p.id} product={p} card={card} as="li" listName={`products_carousel_tabs_${idx}`} index={i} className="pct-grid__item" />
        ))}
      </ul>
    );
  }
  return (
    <BlockCarousel value={c} onSelect={onSelect} className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
      dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0">
      {list.map((p, i) => (
        <div className={`products-group${i === last ? " pc-last-active" : ""}`} key={p.id}>
          <ProductCard product={p} card={card} listName={`products_carousel_tabs_${idx}`} index={i} />
        </div>
      ))}
    </BlockCarousel>
  );
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const variant = st._variant || "centered";
  const tabs = useMemo(() => (st.tabs || []).map((t, i) => ({ t, i })).filter(({ t }) => t && t.label), [st.tabs]);
  const sources = useMemo(() => tabs.map(({ t }) => t.source), [tabs]);
  const lists = useProductSources(sources);
  const wantI = (tabs[Math.max(0, Math.min(tabs.length - 1, Number(st.default_tab) || 0))] || {}).i;
  const [activeI, setActiveI] = useState(wantI);
  useEffect(() => { setActiveI(wantI); }, [wantI]);
  const pos = Math.max(0, tabs.findIndex((x) => x.i === activeI));
  const cur = tabs[pos];
  const header = st.header || {};
  const sb = st.side_banner || {};
  if (!tabs.length) return <EmptyNote preview={ctx?.preview} text="Sekmeli karusel: en az bir sekme ekleyin." />;
  if (lists.every((l) => Array.isArray(l) && !l.length)) return <EmptyNote preview={ctx?.preview} text="Sekmeli karusel: sekmelerin hiçbirinde ürün yok (vitrinde bu bölüm gizlenir)." />;
  const pick = (i) => setActiveI(i);
  const effect = st.tab_effect && st.tab_effect !== "none" ? ` pct-anim pct-anim--${st.tab_effect}` : "";
  const pane = (
    <div className="tab-content" data-testid="pct-content">
      <div className={`tab-pane active show pt-2${effect}`} key={cur.i} role="tabpanel" data-testid={`pct-pane-${cur.i}`}>
        <Pane list={lists[pos]} st={st} idx={cur.i} card={st.card} />
      </div>
    </div>
  );
  const banner = sb.enabled ? (
    <div className={`col-md-6 col-lg${sb.position === "right" ? " order-md-2" : ""}`} data-testid="pct-banner">
      <SmartLink link={sb.link} fallback="div" className="d-block"><SmartImage image={sb.image} size={[390, 370]} width={800} field="side_banner.image" /></SmartLink>
    </div>
  ) : null;
  const body = banner ? (
    <div className="row">
      {banner}
      <div className={`col-md-6 col-lg-8gdot46 ${sb.position === "right" ? "pr-md-0 order-md-1" : "pl-md-0"}`}>{pane}</div>
    </div>
  ) : pane;

  if (variant === "pill_header") {
    const title = header.title && header.tag !== "sr-only";
    const TitleTag = header.tag === "h2" ? "h2" : "h3"; // şablon v2.0: h3
    return (
      <div className="pct pct--pill" data-testid="products-carousel-tabs">
        <div className="position-relative text-center z-index-2">
          <div className={`d-flex justify-content-between border-bottom border-color-1 flex-xl-nowrap flex-wrap border-md-down-top-0 border-lg-down-bottom-0 mb-3${header.align === "center" ? " justify-content-xl-center" : ""}`}>
            {title ? <TitleTag className={`section-title${header.underline === false ? " pct-no-underline" : ""} mb-0 pb-2 font-size-22`} data-pd-field="header.title">{header.title}</TitleTag>
              : header.title ? <h2 className="sr-only" data-pd-field="header.title">{header.title}</h2> : null}
            <Tabs tabs={tabs} active={cur.i} onPick={pick} variant={variant} />
            {header.right === "link" && header.link?.label && (
              <SmartLink link={header.link.link} className="d-none d-xl-block font-size-14 text-gray-90 pb-2 align-self-end ml-3 flex-shrink-0" field="header.link.label">
                {header.link.label} <i className="ec ec-arrow-right-categproes font-size-12" />
              </SmartLink>
            )}
          </div>
        </div>
        {banner ? <div className="row">{banner}<div className={`col-md-6 col-lg-8gdot46 ${sb.position === "right" ? "pr-md-0 order-md-1" : "pl-md-0"}`}><div className="u-slick__tab overflow-hidden pr-0dot5">{pane}</div></div></div> : pane}
      </div>
    );
  }
  const HTag = header.tag === "h3" ? "h3" : "h2";
  return (
    <div className={`pct pct--${variant}`} data-testid="products-carousel-tabs">
      {header.title ? (header.tag === "sr-only"
        ? <h2 className="sr-only" data-pd-field="header.title">{header.title}</h2>
        : <HTag className={`section-title${header.underline === false ? " pct-no-underline" : ""} mb-3 pb-2 font-size-22 ${variant === "left" ? "" : "text-center"}`} data-pd-field="header.title">{header.title}</HTag>) : null}
      <Tabs tabs={tabs} active={cur.i} onPick={pick} variant={variant} />
      {body}
    </div>
  );
}
