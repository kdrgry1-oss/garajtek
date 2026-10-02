// B1 deals_tabs — "Özel Teklif + Ürün Sekmeleri".
//   v1 (vars.)     : şablon v1.0 deals-and-tabs.php — col-lg-4 özel teklif (koyu 110×65 kazanç kutusu, stok, gri
//                    kutulu geri sayım) + col-lg-8 ortalı nav-inline sekmeler ve 3 sütunlu 6'lı ürün ızgarası.
//   v2             : v2.0 index Deals-and-tabs — 370 px kart, 75×75 ana renkli daire, nav-classic sekmeler.
//   discount_tabs  : v2.0 home-v6 "Catch Daily Deals" — başlık satırında hap sekmeler + sağda bağlantı.
// Tüm metinler panelden (data-pd-field); ürün verisi katalogdan (.product-item / data-pd-data).
import { useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard from "../_shared/ProductCard";
import Countdown, { useCountdown } from "../_shared/Countdown";
import StockBar from "../_shared/StockBar";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import { plainText } from "../_shared/schema";
import { CountdownV1, DealBodyV2, OnsaleBody, SavingsBox, StockV1, savingsAmount, stockValues } from "./DealParts";
import { colCounts, colsStyle, dividerClasses } from "./gridUtil";

function DealCard({ deal, product, variant }) {
  const cd = useCountdown(deal.countdown);
  if (deal.countdown?.enabled && cd.expired && deal.countdown.on_expire === "hide_block") return null;
  const amount = savingsAmount(deal.savings, product);
  const { sold, available } = stockValues(deal.stock, product);
  const link = linkHref(deal.link);
  const titleHtml = plainText(deal.title_override) ? deal.title_override : "";

  if (variant === "v1") {
    return (
      <section className="pdb-onsale" style={deal.border_color ? { borderColor: deal.border_color } : undefined} data-testid="special-offer">
        <header className="pdb-onsale__header">
          {deal.title ? <h2 className="pdb-onsale__title" data-pd-field="deal.title">{deal.title}</h2> : <span />}
          <SavingsBox savings={deal.savings} amount={amount} field="deal.savings" />
        </header>
        <OnsaleBody product={product} titleOverride={titleHtml} titleField="deal.title_override" image={deal.image_override}
          imageField="deal.image_override" listName="special_offer" link={link || undefined} />
        <StockV1 stock={deal.stock} sold={sold} available={available} field="deal.stock" />
        <CountdownV1 value={deal.countdown} field="deal.countdown" />
      </section>
    );
  }
  const body = <DealBodyV2 product={product} titleHtml={titleHtml} image={deal.image_override} link={link || undefined} />;
  return (
    <div className={`p-3 pdb-special2 borders-radius-20 bg-white${variant === "v2" ? " min-width-370" : ""} el-special`}
      style={deal.border_color ? { borderColor: deal.border_color } : undefined} data-testid="special-offer">
      <div className="d-flex justify-content-between align-items-center m-1 ml-2">
        {deal.title && <h3 className="font-size-22 mb-0 font-weight-normal text-lh-28 max-width-120" data-pd-field="deal.title">{deal.title}</h3>}
        <SavingsBox savings={deal.savings} amount={amount} field="deal.savings" shape="circle" />
      </div>
      {body}
      {deal.stock?.show && <StockBar sold={sold} available={available} soldLabel={deal.stock.sold_label} availableLabel={deal.stock.available_label} field="deal.stock" />}
      <div className="mb-2"><Countdown value={deal.countdown} field="deal.countdown" /></div>
    </div>
  );
}

function Grid({ st, items, active, cols }) {
  const max = Number(st._limit) || items.length;
  return (
    <ul className="pdb-cols list-unstyled products-group no-gutters mb-0" style={colsStyle(cols)}>
      {items.slice(0, max).map((p, i) => (
        <ProductCard key={p.id} product={p} card={st.card} as="li" listName={`deals_tab_${active}`} index={i}
          className={dividerClasses(i, cols)} />
      ))}
    </ul>
  );
}

function TabPane({ st, items, active, cols }) {
  const anim = st.tab_animation === "fade" ? " pdb-anim-fade" : st.tab_animation === "slideInUp" ? " pdb-anim-up" : "";
  return (
    <div className="tab-content">
      <div key={active} className={`tab-pane show active pt-2${anim}`} role="tabpanel">
        {!items ? (
          <div className="row no-gutters">{[0, 1, 2].map((i) => <div key={i} className="col-4 p-2"><div className="pdb-skel" style={{ height: 300 }} /></div>)}</div>
        ) : !items.length ? (
          st.empty_text ? <div className="text-center py-6 text-gray-90" data-pd-field="empty_text">{st.empty_text}</div> : null
        ) : <Grid st={st} items={items} active={active} cols={cols} />}
      </div>
    </div>
  );
}

function TabNav({ tabs, active, setActive, variant, align }) {
  const pick = (i) => (e) => { e.preventDefault(); setActive(i); };
  if (variant === "v1") {
    return (
      <div className="pdb-tabs-v1-wrap">
        <ul className={`pdb-tabs-v1${align === "left" ? " pdb-tabs--left" : ""}`} role="tablist">
          {tabs.map((t) => (
            <li key={t.key}>
              <a href={`#sekme-${t.i}`} role="tab" aria-selected={t.i === active} className={t.i === active ? "active" : ""} onClick={pick(t.i)}
                data-pd-field={`tabs.${t.i}.label`}>{t.label}</a>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <div className={`position-relative bg-white z-index-2 ${align === "left" ? "text-left" : "text-center"}`}>
      <ul className={`nav nav-classic nav-tab ${align === "left" ? "justify-content-start" : "justify-content-start justify-content-md-center"} flex-nowrap overflow-auto`} role="tablist">
        {tabs.map((t) => (
          <li className="nav-item flex-shrink-0" key={t.key}>
            <a href={`#sekme-${t.i}`} role="tab" aria-selected={t.i === active} className={`nav-link${t.i === active ? " active" : ""}`} onClick={pick(t.i)}>
              <div className="d-md-flex justify-content-md-center align-items-md-center" data-pd-field={`tabs.${t.i}.label`}>{t.label}</div>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PillHeader({ st, tabs, active, setActive }) {
  const activeCls = "nav-link rounded-pill active";
  return (
    <div className="d-flex justify-content-between border-bottom border-color-1 flex-lg-nowrap flex-wrap border-md-down-top-0 border-md-down-bottom-0 mb-4" data-testid="section-header">
      {st.header_title && <h3 className="section-title section-title__full mb-0 pb-2 font-size-22" data-pd-field="header_title">{st.header_title}</h3>}
      <ul className="w-100 w-lg-auto nav nav-pills nav-tab-pill nav-tab-pill-fill mb-3 mb-lg-2 pt-3 pt-lg-0 border-top border-color-1 border-lg-top-0 align-items-center font-size-15 font-size-15-lg flex-nowrap flex-lg-wrap overflow-auto overflow-lg-visble pr-0" role="tablist">
        {tabs.map((t) => (
          <li className="nav-item flex-shrink-0 flex-lg-shrink-1" key={t.key}>
            <a href={`#sekme-${t.i}`} role="tab" aria-selected={t.i === active} className={t.i === active ? activeCls : "nav-link rounded-pill"}
              onClick={(e) => { e.preventDefault(); setActive(t.i); }} data-pd-field={`tabs.${t.i}.label`}>{t.label}</a>
          </li>
        ))}
      </ul>
      {st.header_link?.label && linkHref(st.header_link.link) && (
        <SmartLink link={st.header_link.link} className="d-block text-gray-16 align-self-center" field="header_link.label">
          {st.header_link.label} <i className="ec ec-arrow-right-categproes" />
        </SmartLink>
      )}
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const variant = ["v2", "discount_tabs"].includes(st._variant) ? st._variant : "v1";
  const deal = st.deal || {};
  const tabs = useMemo(() => (st.tabs || []).map((t, i) => ({ ...t, i, key: t._id || `t${i}` })).filter((t) => t.label), [st.tabs]);
  const [picked, setActive] = useState(null);
  const def = Math.min(Math.max(0, Number(st.default_tab) || 0), Math.max(0, tabs.length - 1));
  const active = picked !== null && tabs.some((t) => t.i === picked) ? picked : (tabs[def] ? tabs[def].i : 0);
  const cur = tabs.find((t) => t.i === active) || null;
  const items = useProductSource(cur ? cur.source : null);
  const src = useMemo(() => (!deal.enabled ? null : deal.mode === "manual"
    ? (deal.product ? { kind: "manual", product_ids: [deal.product], limit: 1 } : null)
    : { kind: "discounted", sort: "discount_desc", limit: 1, exclude_out_of_stock: true }), [deal.enabled, deal.mode, deal.product]);
  const dealList = useProductSource(src);
  const product = (dealList || [])[0] || null;
  if (!tabs.length && !product) return null;
  const n = Number(st.columns) || 3;
  // şablon kırılımları: v1 col-lg-8 içinde n sütun; v2 col-md-4 / col-wd-3 (1200–1479'da 3 sütun, 7.–8. ürün gizli);
  // indirim sekmeleri col-md-4 / col-xl-3 / col-wd-2gdot4 (1480+'da 5 sütun).
  const cols = variant === "v1" ? { desktop: n, tablet: Math.min(n, 3), mobile: 1 }
    : variant === "v2" ? { wide: n, desktop: Math.min(n, 3), tablet: Math.min(n, 3), mobile: Math.min(n, 2), xlMax: n > 3 ? 6 : 0 }
      : { wide: n, desktop: Math.min(n, 4), tablet: Math.min(n, 3), mobile: Math.min(n, 2) };
  const gridSt = { ...st, _limit: cur?.source?.limit };
  const right = tabs.length ? (
    <>
      {variant !== "discount_tabs" && <TabNav tabs={tabs} active={active} setActive={setActive} variant={variant} align={st.tab_align} />}
      <TabPane st={gridSt} items={items} active={active} cols={cols} />
    </>
  ) : null;

  if (variant === "v1") {
    return (
      <div className="pdb-deals-tabs row" data-testid="deals-tabs">
        {product && <div className="col-lg-4 mb-6 mb-lg-0"><DealCard deal={deal} product={product} variant="v1" /></div>}
        <div className={`${product ? "col-lg-8" : "col-12"} min-width-0`}>{right}</div>
      </div>
    );
  }
  return (
    <div data-testid="deals-tabs">
      {variant === "discount_tabs" && tabs.length > 0 && <PillHeader st={st} tabs={tabs} active={active} setActive={setActive} />}
      <div className="row">
        {product && (
          <div className={variant === "discount_tabs" ? "col-md-auto col-md-5 col-xl-4 col-wd-3gdot3 mb-6 mb-md-0" : "col-md-auto mb-6 mb-md-0 d-flex justify-content-center"}>
            <DealCard deal={deal} product={product} variant={variant} />
          </div>
        )}
        <div className="col min-width-0">{right}</div>
      </div>
    </div>
  );
}
