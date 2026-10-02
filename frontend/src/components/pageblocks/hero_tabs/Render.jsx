// A7 hero_tabs — şablon v2.0 home-v6 "Slider Section" (L720): .bg-img-hero (1920×714) > .container > .row.align-items-end:
// solda etkin sekme (.col-lg-5: h1.font-size-58 başlık + "LAST CALL FOR UP TO" + büyük tutar + düğme; .col-lg-7 724×360
// görsel) | sağda .max-width-216 > ul.nav.nav-box-custom sekmeler; altında .products-group ürün karuseli (yan oklar,
// 7/5/3/2 kart). Sekme içeriği data-scs-animation-in="fadeInUp" ile gelir.
import { useEffect, useState } from "react";
import BlockCarousel from "../_shared/BlockCarousel";
import ProductCard from "../_shared/ProductCard";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import useProductSource from "../_shared/useProductSource";
import { plainText } from "../_shared/schema";
import { optimizeImg } from "../../../lib/img";
import "./herotabs.css";

/** Şablon: "END SEASON <span class=d-block font-size-50>SMARTPHONES</span>" — ↵ sonrası satır 50/58 oranında küçük. */
function TabTitle({ html, field, size }) {
  const [first, ...rest] = String(html || "").split(/<br\s*\/?>/i);
  return (
    <h2 className="text-lh-57 mb-3 font-weight-light pd-htabs__title" style={{ fontSize: `${size}px` }} data-pd-field={field}>
      <RichText html={first} />
      {rest.length > 0 && <RichText html={rest.join("<br>")} className="d-block" style={{ fontSize: `${Math.round(size * 50 / 58)}px` }} />}
    </h2>
  );
}

/** Baştaki para birimi üst simge (şablon: <sup class="font-size-36">$</sup>250). */
function Amount({ v }) {
  const m = String(v).match(/^(\D+?)\s*(\d.*)$/);
  return m ? <><sup className="font-size-36">{m[1]}</sup>{m[2]}</> : <>{v}</>;
}

function Pane({ t, i, st }) {
  const f = `tabs.${i}`;
  const anim = st.animation && st.animation !== "none" ? ` pd-htabs-anim pd-htabs-anim--${st.animation}` : "";
  return (
    <div className="row align-items-end" data-testid={`hero-tab-pane-${i}`}>
      <div className="col-lg-5">
        {plainText(t.title) && (
          <div className={anim}>
            <TabTitle html={t.title} field={`${f}.title`} size={Number(st.title_size) || 58} />
          </div>
        )}
        {(t.offer_label || t.amount) && (
          <div className={`mb-6${anim}`} style={{ animationDelay: "200ms" }}>
            {t.offer_label && <span className="font-size-15 font-weight-bold mr-2" data-pd-field={`${f}.offer_label`}>{t.offer_label}</span>}
            {t.amount && (
              <span className="font-size-55 font-weight-bold text-lh-45">
                <span data-pd-field={`${f}.amount`}><Amount v={t.amount} /></span>
                {t.amount_suffix && <sub className="font-size-16 ml-1" data-pd-field={`${f}.amount_suffix`}>{t.amount_suffix}</sub>}
              </span>
            )}
          </div>
        )}
        {t.button?.text && linkHref(t.button?.link) && (
          <div className={anim} style={{ animationDelay: "300ms" }}>
            <SmartLink link={t.button.link} field={`${f}.button.text`}
              className="btn btn-primary transition-3d-hover rounded-lg font-weight-normal py-2 px-md-7 px-3 font-size-16">{t.button.text}</SmartLink>
          </div>
        )}
      </div>
      <div className={`col-lg-7${st.animation && st.animation !== "none" ? " pd-htabs-anim pd-htabs-anim--zoomIn" : ""}`} style={{ animationDelay: "500ms" }}>
        <SmartImage image={t.image} size={[724, 360]} width={900} className="img-fluid rounded-lg" field={`${f}.image`} phClassName="rounded-lg" />
      </div>
    </div>
  );
}

function Products({ p }) {
  const rows = useProductSource(p?.enabled === false ? null : p?.source);
  if (p?.enabled === false) return null;
  if (rows === null) return <div className="pd-htabs__skel mb-4" aria-hidden="true" />;
  if (!rows.length) return null;
  return (
    <div className="mb-4 position-relative pd-htabs__products">
      <BlockCarousel value={p.carousel} className="u-slick--gutters-0 position-static overflow-hidden pb-5 pt-2 px-1" ariaLabel="Ürünler"
        sideArrowsClassName="u-slick__arrow u-slick__arrow--flat u-slick__arrow-centered--y rounded-circle"
        arrowLeftClassName="fas fa-arrow-left u-slick__arrow-inner u-slick__arrow-inner--left ml-lg-2 ml-xl-n3"
        arrowRightClassName="fas fa-arrow-right u-slick__arrow-inner u-slick__arrow-inner--right mr-lg-2 mr-xl-n3"
        dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 pt-1">
        {rows.map((pr, k) => (
          <div className="products-group h-100" key={pr.id}>
            <ProductCard product={pr} card="grid" index={k} listName="hero_tabs" className="mx-1 remove-divider h-100"
              innerClassName="product-item__inner bg-white px-wd-3 p-2 p-md-3" />
          </div>
        ))}
      </BlockCarousel>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const tabs = (st.tabs || []).filter(Boolean).slice(0, 6);
  const start = Math.min(Math.max(0, Number(st.default_tab) || 0), Math.max(0, tabs.length - 1));
  const [cur, setCur] = useState(start);
  useEffect(() => { setCur(start); }, [start]);
  const auto = Number(st.autoplay) || 0;
  useEffect(() => {
    if (!auto || tabs.length < 2) return undefined;
    const t = setInterval(() => setCur((c) => (c + 1) % tabs.length), Math.max(2000, auto));
    return () => clearInterval(t);
  }, [auto, tabs.length]);
  if (!tabs.length) return null;
  const active = Math.min(cur, tabs.length - 1);
  const bg = st.background?.url ? `url("${optimizeImg(st.background.url, 1920)}")` : undefined;
  return (
    <div data-testid="hero-tabs" className="pd-htabs">
      <div className="bg-img-hero pd-htabs__bg" data-pd-field="background"
        style={{ backgroundImage: bg, backgroundColor: st.background_color || undefined, color: st.text_color || undefined,
          backgroundPosition: st.background?.focal ? `${Math.round(st.background.focal.x * 100)}% ${Math.round(st.background.focal.y * 100)}%` : undefined }}>
        <div className="container">
          <div className="mb-6 pt-3">
            <div className="row align-items-end">
              <div className="col">
                <div className="tab-content">
                  <div className="tab-pane fade show active" role="tabpanel" key={tabs[active]._id || active}>
                    <Pane t={tabs[active]} i={active} st={st} />
                  </div>
                </div>
              </div>
              {tabs.length > 1 && (
                <div className="col-auto">
                  <div className="bg-light max-width-216 pd-htabs__navwrap">
                    <ul className="nav nav-box-custom bg-white rounded-sm py-2" role="tablist">
                      {tabs.map((t, i) => (
                        <li className="nav-item mx-0" key={t._id || i}>
                          <button type="button" role="tab" aria-selected={i === active} onClick={() => setCur(i)}
                            className={`nav-link p-2 px-4 btn-link border-0 w-100 text-left${i === active ? " active" : ""}`}>
                            <span className="font-size-14" data-pd-field={`tabs.${i}.label`}>{t.label}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}
            </div>
          </div>
          <Products p={st.products} />
        </div>
      </div>
    </div>
  );
}
