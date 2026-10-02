// B1 deals_tabs — şablon deals-and-tabs: solda geri sayımlı "Özel Teklif" kartı, sağda sekmeli ürün ızgarası.
// Grup B geliştirir (v2 / discount_tabs varyantları).
import { useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard, { DealProduct } from "../_shared/ProductCard";
import Countdown, { useCountdown } from "../_shared/Countdown";
import StockBar from "../_shared/StockBar";
import SavingsBadge from "../_shared/SavingsBadge";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import { plainText } from "../_shared/schema";
import { fmtPrice, priceOf } from "../../electro/format";

const COLS = { 2: "col-6", 3: "col-6 col-wd-3 col-md-4", 4: "col-6 col-md-3" };

function stockOf(p) {
  return (p.variants || []).length ? p.variants.reduce((s, v) => s + (Number(v.stock) || 0), 0) : Number(p.stock) || 0;
}

function DealCard({ deal, product }) {
  const cd = useCountdown(deal.countdown);
  const pv = priceOf(product);
  if (deal.countdown?.enabled && cd.expired && deal.countdown.on_expire === "hide_block") return null;
  const save = deal.savings?.mode === "manual" ? deal.savings.amount : (pv.list - pv.display > 0 ? fmtPrice(pv.list - pv.display) : "");
  const sold = deal.stock?.mode === "manual" ? Number(deal.stock.sold) || 0 : Number(product.sold_count || product.sales_count || 0);
  const avail = deal.stock?.mode === "manual" ? Number(deal.stock.available) || 0 : stockOf(product);
  const body = <DealProduct product={product} titleHtml={plainText(deal.title_override) ? deal.title_override : ""} image={deal.image_override} listName="special_offer" />;
  return (
    <div className="p-3 border border-width-2 borders-radius-20 bg-white el-special" style={{ borderColor: deal.border_color || "var(--electro-primary)" }} data-testid="special-offer">
      <div className="d-flex justify-content-between align-items-center m-1 ml-2">
        {deal.title && <h3 className="font-size-22 mb-0 font-weight-normal text-lh-28 max-width-120" data-pd-field="deal.title">{deal.title}</h3>}
        {deal.savings?.show && <SavingsBadge label={deal.savings.label} amount={save} field="deal.savings" />}
      </div>
      {linkHref(deal.link) ? <SmartLink link={deal.link} className="d-block text-reset">{body}</SmartLink> : body}
      {deal.stock?.show && <StockBar sold={sold} available={avail} soldLabel={deal.stock.sold_label} availableLabel={deal.stock.available_label} field="deal.stock" />}
      <div className="mb-2"><Countdown value={deal.countdown} field="deal.countdown" /></div>
    </div>
  );
}

function TabbedGrid({ st }) {
  const tabs = (st.tabs || []).filter((t) => t && t.label);
  const [active, setActive] = useState(Math.min(Number(st.default_tab) || 0, Math.max(0, tabs.length - 1)));
  const cur = tabs[Math.min(active, tabs.length - 1)];
  const items = useProductSource(cur ? cur.source : null);
  if (!tabs.length) return null;
  const n = Number(st.columns) || 3;
  const max = cur?.source?.limit || 6;
  return (
    <div data-testid="home-tabs">
      <div className={`position-relative bg-white z-index-2 ${st.tab_align === "left" ? "text-left" : "text-center"}`}>
        <ul className={`nav nav-classic nav-tab ${st.tab_align === "left" ? "justify-content-start" : "justify-content-start justify-content-md-center"} flex-nowrap overflow-auto`} role="tablist">
          {tabs.map((t, i) => (
            <li className="nav-item flex-shrink-0" key={t._id || i}>
              <a href={`#tab-${i}`} role="tab" aria-selected={i === active} className={`nav-link${i === active ? " active" : ""}`}
                onClick={(e) => { e.preventDefault(); setActive(i); }}>
                <div className="d-md-flex justify-content-md-center align-items-md-center" data-pd-field={`tabs.${i}.label`}>{t.label}</div>
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className="tab-content">
        <div key={active} className={`tab-pane pt-2 show active${st.tab_animation === "fade" ? " fade el-anim-fade" : ""}${st.tab_animation === "slideInUp" ? " el-anim-up" : ""}`} role="tabpanel">
          {!items ? (
            <div className="row no-gutters">{[0, 1, 2].map((i) => <div key={i} className="col-4 p-2"><div className="el-skel" style={{ height: 300 }} /></div>)}</div>
          ) : !items.length ? (
            <div className="text-center py-6 text-gray-90" data-pd-field="empty_text">{st.empty_text}</div>
          ) : (
            <ul className="row list-unstyled products-group no-gutters">
              {items.slice(0, max).map((p, i) => (
                <ProductCard key={p.id} product={p} card={st.card} as="li" listName={`tab${active}`} index={i}
                  className={`${COLS[n] || COLS[3]}${n === 3 && i === 2 ? " remove-divider-xl" : ""}${n === 3 && i === 3 ? " remove-divider-wd" : ""}${n === 3 && i >= 4 ? " d-wd-none" : ""}`} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const deal = st.deal || {};
  const src = useMemo(() => (!deal.enabled ? null : deal.mode === "manual"
    ? (deal.product ? { kind: "manual", product_ids: [deal.product], limit: 1 } : null)
    : { kind: "discounted", sort: "discount_desc", limit: 1, exclude_out_of_stock: true }), [deal.enabled, deal.mode, deal.product]);
  const dealList = useProductSource(src);
  const product = (dealList || [])[0] || null;
  if (!(st.tabs || []).length && !product) return null;
  return (
    <div data-testid="deals-tabs">
      <div className="row">
        {product && <div className="col-lg-auto mb-6 mb-lg-0 d-flex justify-content-center"><DealCard deal={deal} product={product} /></div>}
        <div className="col min-width-0"><TabbedGrid st={st} /></div>
      </div>
    </div>
  );
}
