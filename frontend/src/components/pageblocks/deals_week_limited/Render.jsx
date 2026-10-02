// B5 deals_week_limited — "Sınırlı Haftalık Fırsatlar" (v2.0 home-v4 / home-v11 "Week Deals limited").
// Tam genişlik gri bant: solda başlık + büyük "%" simgesi + geri sayım (v4) ya da büyük başlık + "%70 İNDİRİM" teklifi
// + düğme (v11); sağda yan oklu ürün kartı karuseli.
import useProductSource from "../_shared/useProductSource";
import ProductCard from "../_shared/ProductCard";
import BlockCarousel from "../_shared/BlockCarousel";
import RichText from "../_shared/RichText";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import { useCountdown } from "../_shared/Countdown";
import { plainText } from "../_shared/schema";

const UNITS = ["days", "hours", "minutes", "seconds"];
const pad2 = (n) => String(n).padStart(2, "0");

function BoxCountdown({ cd, align }) {
  const s = useCountdown(cd);
  if (!cd?.enabled) return null;
  if (s.expired && (cd.on_expire === "hide_timer" || cd.on_expire === "hide_block")) return null;
  const heading = cd.heading ? <h6 className="text-gray-2 mb-2" data-pd-field="left.countdown.heading">{cd.heading}</h6> : null;
  if (s.expired && cd.on_expire === "show_text") return <>{heading}<div className="font-size-15" data-pd-field="left.countdown.expired_text">{cd.expired_text}</div></>;
  let units = (cd.units && cd.units.length ? cd.units : UNITS).filter((u) => UNITS.includes(u));
  if (cd.hide_zero_days && s.days === 0) units = units.filter((u) => u !== "days");
  const val = (u) => (u === "hours" && !units.includes("days") ? s.hours + s.days * 24 : s[u]);
  return (
    <>
      {heading}
      <div className={`js-countdown d-flex mx-n2 justify-content-center ${align === "left" ? "justify-content-md-start" : ""}`} data-testid="deal-countdown">
        {units.map((u) => (
          <div className="text-lh-1 px-2 text-center" key={u}>
            <div className="bg-white rounded-sm border border-width-2 border-primary py-2 px-2 min-width-46">
              <div className="text-gray-2 font-size-20 mb-2"><span>{cd.pad === false ? val(u) : pad2(val(u))}</span></div>
              <div className="text-gray-2 font-size-8 text-center text-uppercase" data-pd-field={`left.countdown.labels.${u}`}>{(cd.labels || {})[u]}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function Left({ st, v11 }) {
  const l = st.left || {};
  const offer = l.offer || {};
  const btn = l.button || {};
  if (v11) {
    return (
      <div className="col-md-4 col-lg-3 mb-6 mb-md-0">
        {plainText(l.title) && <RichText as="h2" html={l.title} field="left.title" className="pdb-wdl__title font-size-42 text-lh-38 mb-3 font-weight-light" />}
        {offer.show && (
          <div className="mb-6">
            {offer.prefix && <span className="font-size-15 font-weight-bold mr-1" data-pd-field="left.offer.prefix">{offer.prefix}</span>}
            <span className="font-size-sl-48 font-weight-bold text-lh-45 pdb-wdl__value">
              <span data-pd-field="left.offer.value">{offer.value}</span>
              {offer.suffix && <sup className="font-size-36" data-pd-field="left.offer.suffix">{offer.suffix}</sup>}
              {offer.sub && <sub className="font-size-16" data-pd-field="left.offer.sub">{offer.sub}</sub>}
            </span>
          </div>
        )}
        {l.big_symbol && l.show_symbol && <div className="font-size-130 font-weight-light mb-2 text-lh-1" data-pd-field="left.big_symbol">{l.big_symbol}</div>}
        <div className="mb-4"><BoxCountdown cd={l.countdown} align="left" /></div>
        {btn.show && btn.text && (
          <SmartLink link={btn.link} className="btn btn-primary transition-3d-hover rounded-lg font-weight-normal py-2 px-md-7 px-3 font-size-16" field="left.button.text">{btn.text}</SmartLink>
        )}
      </div>
    );
  }
  return (
    <div className="col-md-4 col-lg-3 col-wd-2 mb-6 mb-md-0">
      <div className="max-width-244">
        {plainText(l.title) && (
          <div className="d-flex border-bottom border-color-1 mb-3">
            <RichText as="h3" html={l.title} field="left.title" className="section-title mb-0 pb-2 font-size-22" />
          </div>
        )}
        <div className="mb-3 mb-md-2 text-center text-md-left">
          {l.show_symbol && l.big_symbol && <div className="font-size-130 font-weight-light mb-2 text-lh-1" data-pd-field="left.big_symbol">{l.big_symbol}</div>}
          {offer.show && (
            <div className="mb-3">
              {offer.prefix && <span className="font-size-15 font-weight-bold mr-1" data-pd-field="left.offer.prefix">{offer.prefix}</span>}
              <span className="font-size-36 font-weight-bold"><span data-pd-field="left.offer.value">{offer.value}</span>{offer.suffix && <sup className="font-size-20" data-pd-field="left.offer.suffix">{offer.suffix}</sup>}</span>
              {offer.sub && <span className="font-size-16 font-weight-bold ml-1" data-pd-field="left.offer.sub">{offer.sub}</span>}
            </div>
          )}
          <BoxCountdown cd={l.countdown} align="left" />
          {btn.show && btn.text && linkHref(btn.link) && (
            <SmartLink link={btn.link} className="btn btn-primary transition-3d-hover rounded-lg font-weight-normal py-2 px-4 font-size-15 mt-4" field="left.button.text">{btn.text}</SmartLink>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const v11 = st._variant === "v11";
  const cd = useCountdown(st.left?.countdown);
  const list = useProductSource(st.source);
  if (st.left?.countdown?.enabled && cd.expired && st.left.countdown.on_expire === "hide_block") return null;
  if (list && !list.length && !st.show_when_empty) return null;
  return (
    <div className={`pdb-wdl py-7${v11 ? " pt-xl-15 pb-xl-7" : ""}`} style={{ backgroundColor: st.background || undefined }} data-testid="deals-week-limited">
      <div className="container">
        <div className={`row${v11 ? " align-items-center" : ""}`}>
          <Left st={st} v11={v11} />
          <div className={v11 ? "col-md-8 col-lg-9" : "col-md-8 col-lg-9 col-wd-10"}>
            {!list ? <div className="pdb-skel" style={{ height: 340 }} /> : (
              <BlockCarousel value={st.carousel} className="position-static overflow-hidden u-slick-overflow-visble pb-5 pt-2 px-1"
                dotsClassName={`text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 pt-1${st.carousel?.arrows === "side" ? " d-xl-none" : ""}`}
                sideArrowsClassName="d-none d-xl-inline-block u-slick__arrow-normal u-slick__arrow-centered--y font-size-25"
                arrowLeftClassName="fas fa-chevron-left left-n16 u-slick__arrow-classic-inner--left z-index-9"
                arrowRightClassName="fas fa-chevron-right right-n16 u-slick__arrow-classic-inner--right"
                ariaLabel={plainText(st.left?.title)}>
                {list.map((p, i) => (
                  <div className="js-slide products-group" key={p.id}>
                    <ProductCard product={p} card={st.card || "grid_small"} className="mx-1 remove-divider" innerClassName="product-item__inner bg-white px-wd-4 p-2 p-md-3" listName="week_deals_limited" index={i} />
                  </div>
                ))}
              </BlockCarousel>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
