// Ana sayfa — şablonun v1.0 ana sayfa yapısı (PHP pages/home.php) blok blok; görünüm tema CSS'i
// (public/electro/electro.css) bileşenleriyle. Bölümler Admin › Tasarım › Sayfa Tasarımı'ndaki
// bloklardan gelir (/page-blocks?page=home); hiç blok yoksa lib/homeLayout.js varsayılan düzeni.
//   hero_slider       → home-v1-slider (tam genişlik 1920×466; solda "Tüm Kategoriler" menüsü üstte)
//   ads_block         → home-v1-ads-block (410×281, 410×281, 714×486 + metin)
//   deals_tabs        → deals-and-tabs (Günün Fırsatı + Öne Çıkanlar/İndirimdekiler/Çok Satanlar)
//   product_grid_212  → 2-1-2-product-grid (kategori sekmeli)
//   best_sellers      → best-sellers-products-cards-carousel
//   full_banner       → home-banner (1170×207)
//   product_slider    → recently-added-products-carousel (kaynak seçilebilir)
//   brands_carousel   → footer/brands-carousel (200×60 logolar; boşsa ürün markaları)
//   product_columns   → footer ürün sütunları (Öne Çıkan / İndirimdeki / Çok Satan)
//   text_block / video_banner / instashop / half_banners → ek bloklar
// Görseli girilmemiş alan, şablon ölçüsünde nötr yer tutucu gösterir (sayfa düzeni bozulmaz).
import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import RotatingText from "../components/RotatingText";
import Footer from "../components/Footer";
import ProductCard, { CardPrice, useProductActions } from "../components/ProductCard";
import Carousel from "../components/electro/Carousel";
import Countdown from "../components/electro/Countdown";
import useCategoryTree from "../components/electro/useCategoryTree";
import { optimizeImg, firstImage, galleryImages } from "../lib/img";
import { trackSelectPromotion } from "../lib/dataLayer";
import { dedupeColorGroups } from "../lib/colorGroups";
import { fmtPrice, priceOf } from "../components/electro/format";
import { useStoreInfo } from "../lib/storeInfo";
import { socialUrl, SITE_NAME } from "../lib/brand";
import { DEFAULT_HOME_BLOCKS, SIZES, sizeText } from "../lib/homeLayout";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const isVideoUrl = (u) => typeof u === "string" && /\.(mp4|webm|mov|m4v|ogg)(\?|$)/i.test(u);
const promo = (id, name) => { try { trackSelectPromotion({ promotionId: id, promotionName: name }); } catch (_) { /* silent */ } };
const isExternal = (to) => /^https?:\/\//i.test(String(to || ""));

/** Dış bağlantı ise <a>, değilse router <Link>. */
function SmartLink({ to, children, ...rest }) {
  if (isExternal(to)) return <a href={to} target="_blank" rel="noopener noreferrer" {...rest}>{children}</a>;
  return <Link to={to || "/"} {...rest}>{children}</Link>;
}

/** Görsel girilmemiş alan — şablon ölçüsünde nötr yer tutucu (ölçü yazısı soluk). */
export function Placeholder({ size, className = "", style, label }) {
  return (
    <div className={`el-ph ${className}`} style={{ aspectRatio: `${size[0]} / ${size[1]}`, ...style }} aria-hidden="true">
      <span className="el-ph__size">{label || sizeText(size)}</span>
    </div>
  );
}

function splitPrice(n) {
  const v = Number(n) || 0;
  const int = Math.floor(v);
  const dec = Math.round((v - int) * 100);
  return { int: int.toLocaleString("tr-TR"), dec: String(dec).padStart(2, "0") };
}

/* ------------------------------------------------------- ürün kaynakları */
const _srcCache = new Map();
function sourceUrl({ source = "newest", category_ids = [], limit = 12, slug }) {
  const cids = (category_ids || []).filter(Boolean).join(",");
  switch (source) {
    case "featured": return `${API}/products?limit=${limit}&is_featured=true`;
    case "discounted": return `${API}/products/slider-feed?source=discounted&limit=${limit}`;
    case "popular": return `${API}/products?limit=${limit}&sort=popular`;
    case "category":
      if (slug) return `${API}/products?limit=${limit}&sort=popular&category=${encodeURIComponent(slug)}`;
      return cids ? `${API}/products/slider-feed?source=category&limit=${limit}&category_ids=${encodeURIComponent(cids)}` : null;
    case "newest":
    default: return `${API}/products?limit=${limit}&sort=created_at&order=desc`;
  }
}

/** Blok ayarındaki kaynaktan ürün listesi (featured/discounted/popular/newest/category/manual). */
function useProducts(spec) {
  const key = JSON.stringify(spec || {});
  const [state, setState] = useState(() => _srcCache.get(key) || null);
  useEffect(() => {
    if (!spec) return undefined;
    if (_srcCache.has(key)) { setState(_srcCache.get(key)); return undefined; }
    let alive = true;
    const done = (list) => { _srcCache.set(key, list); if (alive) setState(list); };
    if (spec.source === "manual") {
      const ids = (spec.product_ids || []).slice(0, spec.limit || 24);
      Promise.all(ids.map((id) => axios.get(`${API}/products/${encodeURIComponent(id)}`).then((r) => r.data).catch(() => null)))
        .then((rows) => done(rows.filter((p) => p && p.id && p.is_active !== false)));
    } else {
      const url = sourceUrl(spec);
      if (!url) { done([]); return undefined; }
      axios.get(url).then((r) => done(dedupeColorGroups(r.data?.products || []))).catch(() => done([]));
    }
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return state;
}

/* ---------------------------------------------------------------- Hero */
const HERO_H = SIZES.hero[1];

/** Masaüstünde açık "Tüm Kategoriler" menüsü hero'dan uzunsa alttaki bloğu örtmesin diye hero,
 * menünün altına kadar uzatılır (--el-hero-h). Mobil/tablette menü gizli → değişken kaldırılır. */
function useHeroClearance() {
  useLayoutEffect(() => {
    if (typeof window === "undefined" || typeof document === "undefined") return undefined;
    const root = document.documentElement;
    let last = 0;
    const calc = () => {
      const vm = document.querySelector('.el-header-wrap [data-testid="vertical-menu"]');
      const hero = document.querySelector(".el-hero-v1");
      if (!vm || !hero || window.innerWidth < 1200) {
        if (last) { root.style.removeProperty("--el-hero-h"); last = 0; }
        return;
      }
      const vr = vm.getBoundingClientRect();
      if (!vr.height) return;
      const need = Math.ceil(vr.bottom - hero.getBoundingClientRect().top) + 24;
      const h = need > HERO_H ? need : 0;
      if (h !== last) {
        if (h) root.style.setProperty("--el-hero-h", `${h}px`); else root.style.removeProperty("--el-hero-h");
        last = h;
      }
    };
    calc();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(calc) : null;
    const wrap = document.querySelector(".el-header-wrap");
    if (ro) { ro.observe(document.body); if (wrap) ro.observe(wrap); }
    window.addEventListener("resize", calc);
    return () => { if (ro) ro.disconnect(); window.removeEventListener("resize", calc); root.style.removeProperty("--el-hero-h"); };
  }, []);
}

function HeroSlide({ s, i }) {
  const hasText = s.title || s.subtitle || s.price || s.cta;
  return (
    <div className="el-hero-v1__slide position-relative" data-testid={`hero-slide-${i}`}>
      {s.image ? (
        isVideoUrl(s.image) ? (
          <video className="el-hero-v1__img" src={s.image} muted loop playsInline autoPlay={i === 0} preload={i === 0 ? "auto" : "none"} />
        ) : (
          <picture>
            {s.mobileImage && <source media="(max-width: 767px)" srcSet={optimizeImg(s.mobileImage, 800)} />}
            <img className="el-hero-v1__img" src={optimizeImg(s.image, 1920, 78)} alt={s.title || ""}
              fetchPriority={i === 0 ? "high" : "auto"} loading={i === 0 ? "eager" : "lazy"} decoding="async" />
          </picture>
        )
      ) : s.productImage ? null : (
        <div className="el-hero-v1__img el-ph el-ph--fill" aria-hidden="true"><span className="el-ph__size el-ph__size--hero">{sizeText(SIZES.hero)}</span></div>
      )}
      <div className="container position-relative h-100">
        <div className="row el-hero-v1__row align-items-center">
          <div className="offset-xl-3 col-xl-5 col-md-7 col-10 py-6 py-md-0">
            {hasText && (
              <div className="el-hero-v1__caption el-anim-up">
                {s.title && <h2 className="font-size-46 text-lh-57 font-weight-light text-gray-90 mb-2">{s.title}</h2>}
                {s.subtitle && <h6 className="font-size-15 font-weight-bold text-gray-90 text-uppercase mb-3">{s.subtitle}</h6>}
                {s.price != null && s.price !== "" && (
                  <div className="mb-4 text-gray-90">
                    <span className="font-size-13 text-uppercase">{s.priceLabel || "Başlayan fiyatlarla"}</span>
                    <div className="font-size-50 font-weight-bold text-lh-45">
                      {splitPrice(s.price).int}<sup>,{splitPrice(s.price).dec}</sup><sup className="font-size-25 ml-1">₺</sup>
                    </div>
                  </div>
                )}
                {s.cta && (
                  <SmartLink to={s.link} onClick={() => promo(`hero_${i + 1}`, s.title || s.link)}
                    className="btn btn-primary transition-3d-hover rounded-lg font-weight-normal py-2 px-md-7 px-4 font-size-16 stretched-link">
                    {s.cta}
                  </SmartLink>
                )}
              </div>
            )}
          </div>
          {s.productImage && (
            <div className="col-xl-4 col-md-5 d-none d-md-flex align-items-center el-hero-media">
              <img className="img-fluid" src={optimizeImg(s.productImage, 840)} alt={s.title || ""} width="416" height="420" fetchPriority={i === 0 ? "high" : "auto"} loading={i === 0 ? "eager" : "lazy"} />
            </div>
          )}
        </div>
      </div>
      {!s.cta && s.link && <SmartLink to={s.link} className="el-hero-v1__hit" aria-label={s.title || "Kampanya"} onClick={() => promo(`hero_${i + 1}`, s.title || s.link)} />}
    </div>
  );
}

function HeroV1({ block, fallbackSlides }) {
  const caps = block?.settings?.captions || [];
  const mob = block?.settings?.mobile_images || [];
  let slides = (block?.images || []).map((img, i) => ({
    image: img, mobileImage: mob[i] || "", link: block.links?.[i] || "",
    title: caps[i]?.title, subtitle: caps[i]?.subtitle || caps[i]?.eyebrow, priceLabel: caps[i]?.price_label,
    price: caps[i]?.price, cta: caps[i]?.cta,
  }));
  if (!slides.length) slides = fallbackSlides;
  return (
    <div className="mb-5 el-hero-v1 bg-gray-1" data-testid="hero-slider">
      {slides.length > 1 ? (
        <Carousel perView={{ base: 1 }} loop autoplay={6000} ariaLabel="Kampanyalar"
          dotsClassName="text-center position-absolute right-0 bottom-0 left-0 u-slick__pagination u-slick__pagination--long mb-3 mb-md-4 el-hero-v1__dots">
          {slides.map((s, i) => <HeroSlide key={i} s={s} i={i} />)}
        </Carousel>
      ) : <HeroSlide s={slides[0]} i={0} />}
    </div>
  );
}

/* ------------------------------------------------- Reklam bannerları */
function AdsBlock({ block }) {
  const items = (block?.settings?.items || []).slice(0, 3);
  if (!items.length) return null;
  return (
    <div className="mb-5" data-testid="ads-block">
      <div className="row">
        {items.map((it, i) => {
          const size = SIZES.ads[i] || SIZES.ads[0];
          return (
            <div className={`${i === 2 ? "col-md-12" : "col-md-6"} col-lg-4 mb-4 mb-lg-0`} key={i}>
              <SmartLink to={it.link || "/"} className="d-block text-gray-90 el-ad" onClick={() => promo(`ad_${i + 1}`, it.strong || it.link)} data-testid={`ad-${i + 1}`}>
                <div className="min-height-132 py-1 d-flex bg-gray-1 align-items-center">
                  <div className="col-6 col-xl-5 col-wd-6 pr-0">
                    {it.image ? <img className="img-fluid el-ad__img" src={optimizeImg(it.image, 420)} alt="" loading="lazy" style={{ aspectRatio: `${size[0]} / ${size[1]}` }} />
                      : <Placeholder size={size} />}
                  </div>
                  <div className="col-6 col-xl-7 col-wd-6">
                    <div className="mb-2 pb-1 font-size-18 font-weight-light text-ls-n1 text-lh-23 el-banner-text">
                      {it.pre} <strong>{it.strong}</strong> {it.post}
                    </div>
                    {it.upto ? (
                      <div className="text-gray-90 el-ad__upto"><span className="font-size-12 text-uppercase mr-1">varan</span><span className="font-size-30 font-weight-bold">%{it.upto}</span><span className="font-size-12 ml-1">indirim</span></div>
                    ) : (
                      <div className="link text-gray-90 font-weight-bold font-size-15">
                        {it.cta || "Hemen İncele"}
                        <span className="link__icon ml-1"><span className="link__icon-inner"><i className="ec ec-arrow-right-categproes" /></span></span>
                      </div>
                    )}
                  </div>
                </div>
              </SmartLink>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* --------------------------------------------- Günün fırsatı + sekmeler */
function SpecialOffer({ product, title = "Günün Fırsatı" }) {
  const a = useProductActions(product, { listName: "special_offer" });
  const pv = priceOf(product);
  const save = Math.max(0, pv.list - pv.display);
  const stock = (product.variants || []).length
    ? product.variants.reduce((s, v) => s + (Number(v.stock) || 0), 0)
    : Number(product.stock) || 0;
  const sold = Number(product.sold_count || product.sales_count || 0);
  const pct = stock + sold > 0 ? Math.round((sold / (stock + sold)) * 100) : 30;
  const end = useMemo(() => {
    const e = product.campaign_end || product.sale_end_date;
    if (e && new Date(e).getTime() > Date.now()) return e;
    const d = new Date(); d.setHours(23, 59, 59, 0); return d.toISOString();
  }, [product]);
  return (
    <div className="p-3 border border-width-2 border-primary borders-radius-20 bg-white el-special" data-testid="special-offer">
      <div className="d-flex justify-content-between align-items-center m-1 ml-2">
        <h3 className="font-size-22 mb-0 font-weight-normal text-lh-28 max-width-120">{title}</h3>
        {save > 0 && (
          <div className="d-flex align-items-center flex-column justify-content-center bg-primary rounded-pill height-75 width-75 text-lh-1">
            <span className="font-size-12">Kazanç</span>
            <div className="font-size-15 font-weight-bold text-nowrap">{Math.round(save).toLocaleString("tr-TR")} ₺</div>
          </div>
        )}
      </div>
      <div className="mb-4">
        <Link to={a.href} onClick={a.select} className="d-block text-center">
          <span className="el-img-box" style={{ aspectRatio: "320 / 300" }}>
            <img className="img-fluid" src={optimizeImg(firstImage(product), 640)} alt={product.name} loading="lazy" width="320" height="300" />
          </span>
        </Link>
      </div>
      <h5 className="mb-2 font-size-14 text-center mx-auto max-width-180 text-lh-18">
        <Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link>
      </h5>
      <div className="d-flex align-items-center justify-content-center mb-3">
        {pv.hasDiscount && <del className="font-size-18 mr-2 text-gray-2">{fmtPrice(pv.list)}</del>}
        <ins className="font-size-30 text-red text-decoration-none">{fmtPrice(pv.display)}</ins>
      </div>
      <div className="mb-3 mx-2">
        <div className="d-flex justify-content-between align-items-center mb-2">
          <span>Stokta: <strong>{stock}</strong></span>
          {sold > 0 && <span>Satılan: <strong>{sold}</strong></span>}
        </div>
        <div className="rounded-pill bg-gray-3 height-20 position-relative">
          <span className="position-absolute left-0 top-0 bottom-0 rounded-pill bg-primary" style={{ width: `${Math.min(100, Math.max(8, pct))}%` }} />
        </div>
      </div>
      <div className="mb-2">
        <h6 className="font-size-15 text-gray-2 text-center mb-3">Acele edin! Fırsatın bitmesine:</h6>
        <Countdown endDate={end} />
      </div>
    </div>
  );
}

function TabbedGrid({ tabs, testId = "home-tabs" }) {
  const [active, setActive] = useState(0);
  const cur = tabs[Math.min(active, tabs.length - 1)];
  const items = useProducts(cur ? { ...cur.spec, limit: 6 } : null);
  if (!tabs.length) return null;
  return (
    <div data-testid={testId}>
      <div className="position-relative bg-white text-center z-index-2">
        <ul className="nav nav-classic nav-tab justify-content-start justify-content-md-center flex-nowrap overflow-auto" role="tablist">
          {tabs.map((t, i) => (
            <li className="nav-item flex-shrink-0" key={t.key}>
              <a href={`#${t.key}`} role="tab" aria-selected={i === active} className={`nav-link${i === active ? " active" : ""}`}
                onClick={(e) => { e.preventDefault(); setActive(i); }}>
                <div className="d-md-flex justify-content-md-center align-items-md-center">{t.label}</div>
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className="tab-content">
        <div className="tab-pane fade pt-2 show active" role="tabpanel">
          {!items ? (
            <div className="row no-gutters">{[0, 1, 2].map((i) => <div key={i} className="col-4 p-2"><div className="el-skel" style={{ height: 300 }} /></div>)}</div>
          ) : !items.length ? (
            <div className="text-center py-6 text-gray-90">Bu sekmede henüz ürün yok.</div>
          ) : (
            <ul className="row list-unstyled products-group no-gutters">
              {items.slice(0, 6).map((p, i) => (
                <ProductCard key={p.id} product={p} as="li" listName={cur.key} index={i}
                  className={`col-6 col-wd-3 col-md-4${i === 2 ? " remove-divider-xl" : ""}${i === 3 ? " remove-divider-wd" : ""}${i >= 4 ? " d-wd-none" : ""}`} />
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function DealsTabs({ block, pool }) {
  const st = block?.settings || {};
  const tabs = (st.tabs || []).filter((t) => t && t.label).map((t, i) => ({
    key: `tab${i}`, label: t.label,
    spec: { source: t.source || "newest", category_ids: t.category_ids, product_ids: t.product_ids },
  }));
  const manualId = st.special?.mode === "manual" ? st.special?.product_id : null;
  const manual = useProducts(manualId ? { source: "manual", product_ids: [manualId] } : null);
  const special = useMemo(() => {
    if (manualId) return (manual || [])[0] || null;
    let bestP = null; let bestPct = 0;
    for (const p of pool) { const pv = priceOf(p); if (pv.hasDiscount && pv.discountPct > bestPct) { bestPct = pv.discountPct; bestP = p; } }
    return bestP;
  }, [pool, manual, manualId]);
  if (!tabs.length && !special) return null;
  return (
    <div className="mb-5" data-testid="deals-tabs">
      <div className="row">
        {special && <div className="col-lg-auto mb-6 mb-lg-0 d-flex justify-content-center"><SpecialOffer product={special} title={st.special?.title || "Günün Fırsatı"} /></div>}
        <div className="col min-width-0"><TabbedGrid tabs={tabs} /></div>
      </div>
    </div>
  );
}

/* ------------------------------------- 2-1-2 kategori sekmeli ürün ızgarası */
function ProductGrid212({ block, roots }) {
  const st = block?.settings || {};
  const tree = useCategoryTree();
  const picked = (st.category_ids || []).map((id) => tree.byId.get(String(id))).filter(Boolean);
  const cats = (picked.length ? picked : roots).slice(0, Math.max(1, (st.max_tabs || 6) - 1));
  const tabsList = [{ key: "__first", label: st.first_label || "En İyi Fırsatlar", spec: { source: st.first_source || "discounted", limit: 5 } },
    ...cats.map((c) => ({ key: c.slug, label: c.name, spec: { source: "category", slug: c.slug, limit: 5 } }))];
  const [active, setActive] = useState(0);
  const cur = tabsList[Math.min(active, tabsList.length - 1)];
  const list = useProducts(cur.spec);
  const cell = (p) => (
    <ProductCard key={p.id} product={p} as="li" className="col-12 remove-divider" innerClassName="product-item__inner bg-white p-3" />
  );
  return (
    <div className="products-group-4-1-4 space-1 bg-gray-7 mb-6 el-212" data-testid="products-212">
      <h2 className="sr-only">{block?.title || "Kategori fırsatları"}</h2>
      <div className="container">
        <div className="position-relative text-center z-index-2 mb-3">
          <ul className="nav nav-classic nav-tab nav-tab-sm px-md-3 justify-content-start justify-content-lg-center flex-nowrap flex-lg-wrap overflow-auto overflow-lg-visble border-md-down-bottom-0 pb-1 pb-lg-0 mb-n1 mb-lg-0" role="tablist">
            {tabsList.map((t, i) => (
              <li className="nav-item flex-shrink-0 flex-lg-shrink-1" key={t.key}>
                <a href="#urunler" role="tab" aria-selected={i === active} className={`nav-link${i === active ? " active" : ""}`} onClick={(e) => { e.preventDefault(); setActive(i); }}>
                  <div className="d-md-flex justify-content-md-center align-items-md-center">{t.label}</div>
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div className="tab-content">
          <div className="tab-pane fade pt-2 show active" role="tabpanel">
            {!list ? (
              <div className="row no-gutters">{[0, 1, 2].map((i) => <div key={i} className="col-md-4 p-2"><div className="el-skel" style={{ height: 420 }} /></div>)}</div>
            ) : !list.length ? (
              <div className="text-center py-6 text-gray-90">Bu kategoride henüz ürün bulunmuyor.</div>
            ) : (
              <div className="row no-gutters">
                <div className="col-md-3">
                  <ul className="row list-unstyled products-group no-gutters mb-0 h-100 el-212__side">{list.slice(1, 3).map(cell)}</ul>
                </div>
                <div className="col-md-6 products-group-1">
                  <ul className="row list-unstyled products-group no-gutters bg-white h-100 mb-0">
                    <BigProduct product={list[0]} />
                  </ul>
                </div>
                <div className="col-md-3">
                  <ul className="row list-unstyled products-group no-gutters mb-0 h-100 el-212__side">{list.slice(3, 5).map(cell)}</ul>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function BigProduct({ product }) {
  const a = useProductActions(product, { listName: "products_212" });
  const imgs = galleryImages(product);
  const [cur, setCur] = useState(0);
  const cat = product.category_name;
  return (
    <li className="col product-item remove-divider" data-testid={`product-card-${product.id}`}>
      <div className="product-item__outer h-100 w-100 prodcut-box-shadow">
        <div className="product-item__inner bg-white p-3">
          <div className="product-item__body d-flex flex-column">
            <div className="mb-1">
              {cat && <div className="mb-2"><span className="font-size-12 text-gray-5">{cat}</span></div>}
              <h5 className="mb-0 product-item__title"><Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link></h5>
            </div>
            <div className="mb-1">
              <Link to={a.href} onClick={a.select} className="d-block text-center my-4">
                <span className="el-img-box" style={{ aspectRatio: "564 / 420" }}>
                  <img className="img-fluid" src={optimizeImg(imgs[cur] || "/placeholder.jpg", 800)} alt={product.name} loading="lazy" />
                </span>
              </Link>
              {imgs.length > 1 && (
                <div className="row mx-gutters-2 mb-3">
                  {imgs.slice(0, 4).map((im, i) => (
                    <div className="col-auto" key={im}>
                      <button type="button" className={`el-thumb-btn${cur === i ? " active" : ""}`} onClick={() => setCur(i)} aria-label={`Görsel ${i + 1}`}>
                        <img src={optimizeImg(im, 120)} alt="" loading="lazy" width="60" height="60" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex-center-between mb-3">
              <CardPrice product={product} />
              <div className="prodcut-add-cart">
                <a href={a.href} onClick={a.add} className="btn-add-cart btn-primary transition-3d-hover" data-testid={`quick-add-${product.id}`} aria-label="Sepete ekle"><i className="ec ec-add-to-cart" /></a>
              </div>
            </div>
          </div>
          <div className="product-item__footer">
            <div className="border-top pt-2 flex-center-between flex-wrap">
              <a href="#karsilastir" onClick={a.cmp} className="text-gray-6 font-size-13"><i className="ec ec-compare mr-1 font-size-15" /> Karşılaştır</a>
              <a href="#favori" onClick={a.fav} className={`text-gray-6 font-size-13${a.isFav ? " text-red" : ""}`} data-testid={`favorite-${product.id}`}><i className="ec ec-favorites mr-1 font-size-15" /> Favorilere Ekle</a>
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}

/* ------------------------------------------------ Çok satanlar karuseli */
function chunk(arr, n) { const out = []; for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n)); return out; }

function BestSellers({ block, roots }) {
  const st = block?.settings || {};
  const tree = useCategoryTree();
  const picked = (st.category_ids || []).map((id) => tree.byId.get(String(id))).filter(Boolean);
  const cats = (picked.length ? picked : roots).slice(0, st.max_tabs || 3);
  const [tab, setTab] = useState(null);
  const list = useProducts(tab ? { source: "category", slug: tab, limit: 12 } : { source: "popular", limit: 18 });
  if (!tab && list && !list.length) return null;
  const activeCls = "text-gray-90 btn btn-outline-primary border-width-2 rounded-pill py-1 px-4 font-size-15 text-lh-19 font-size-15-md";
  return (
    <div className="space-top-2 mb-6" data-testid="bestsellers">
      <div className="d-flex justify-content-between border-bottom border-color-1 flex-md-nowrap flex-wrap border-sm-bottom-0">
        <h3 className="section-title mb-0 pb-2 font-size-22">{block?.title || "Çok Satanlar"}</h3>
        <ul className="nav nav-pills mb-2 pt-3 pt-md-0 mb-0 border-top border-color-1 border-md-top-0 align-items-center font-size-15 font-size-15-md flex-nowrap flex-md-wrap overflow-auto overflow-md-visble">
          <li className="nav-item flex-shrink-0 flex-md-shrink-1">
            <a href="#top" onClick={(e) => { e.preventDefault(); setTab(null); }} className={tab ? "nav-link text-gray-8" : activeCls}>{st.first_label || "İlk 20"}</a>
          </li>
          {cats.map((c) => (
            <li className="nav-item flex-shrink-0 flex-md-shrink-1" key={c.id}>
              <a href={`#${c.slug}`} onClick={(e) => { e.preventDefault(); setTab(c.slug); }} className={tab === c.slug ? activeCls : "nav-link text-gray-8"}>{c.name}</a>
            </li>
          ))}
        </ul>
      </div>
      {!list ? (
        <div className="py-6 text-center text-gray-90">Yükleniyor…</div>
      ) : list.length === 0 ? (
        <div className="py-6 text-center text-gray-90">Bu kategoride ürün bulunamadı.</div>
      ) : (
        <Carousel key={tab || "top"} perView={{ base: 1 }} className="u-slick--gutters-2 overflow-hidden u-slick-overflow-visble pt-3 pb-6"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-4">
          {chunk(list.slice(0, 18), 6).map((group, gi) => (
            <ul className="row list-unstyled products-group no-gutters mb-0 overflow-visible" key={gi}>
              {group.map((p, i) => (
                <ProductCard key={p.id} product={p} as="li" variant="card" listName="bestsellers" index={gi * 6 + i}
                  className={`col-wd-3 col-md-4 border-bottom border-md-bottom-0${i % 3 === 2 ? " remove-divider-xl" : ""}`} />
              ))}
            </ul>
          ))}
        </Carousel>
      )}
    </div>
  );
}

/* ----------------------------------------------- Ürün karuseli (bölüm) */
function ProductCarouselSection({ title, products, ctaLink, ctaLabel, testId = "product-slider", bg }) {
  if (!products || !products.length) return null;
  return (
    <div className="mb-6" data-testid={testId} style={bg ? { backgroundColor: bg } : undefined}>
      <div className="position-relative">
        <div className="border-bottom border-color-1 mb-2 d-flex justify-content-between align-items-end">
          <h3 className="section-title mb-0 pb-2 font-size-22">{title}</h3>
          {ctaLink && <Link to={ctaLink} className="font-size-14 text-gray-90 pb-2 mr-8">{ctaLabel || "Tümünü Gör"} <i className="ec ec-arrow-right-categproes font-size-12" /></Link>}
        </div>
        <Carousel perView={{ base: 2, md: 3, lg: 4, xl: 5, wd: 7 }} className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
          arrows arrowsClassName="position-absolute top-0 font-size-17 u-slick__arrow-normal top-10"
          arrowLeftClassName="fa fa-angle-left right-1" arrowRightClassName="fa fa-angle-right right-0"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0">
          {products.map((p, i) => (
            <div className="js-slide products-group" key={p.id}>
              <ProductCard product={p} listName={testId} index={i} innerClassName="product-item__inner px-wd-4 p-2 p-md-3" wishlistLabel="Favori" />
            </div>
          ))}
        </Carousel>
      </div>
    </div>
  );
}

/** Ürün karuseli bloğu — kaynak: newest / discounted / featured / popular / category / manual. */
function SliderBlock({ block }) {
  const st = block?.settings || {};
  const ids = st.product_ids || [];
  const source = st.source || (ids.length ? "manual" : "newest");
  const list = useProducts({ source: source === "favorites" ? "popular" : source, category_ids: st.category_ids, product_ids: ids, limit: st.limit || 14 });
  const defaultCta = source === "discounted" ? "/sale" : "/en-yeniler";
  return (
    <ProductCarouselSection title={block?.title || "Son Eklenenler"} products={list} ctaLink={st.cta_link || defaultCta}
      ctaLabel={st.cta_label} testId="product-slider" bg={st.bg_color} />
  );
}

/* ------------------------------------------------------- Tam banner */
function FullBanner({ block }) {
  const img = block?.images?.[0];
  const dims = block?.settings?.img_dims?.[0];
  return (
    <div className="mb-6" data-testid="full-banner">
      {img ? (
        <SmartLink to={block.links?.[0] || "/"} className="d-block" onClick={() => promo("full_banner", block.title || block.links?.[0])}>
          <img className="img-fluid w-100" src={optimizeImg(img, 1400)} alt={block.title || ""} loading="lazy" style={{ aspectRatio: dims ? `${dims[0]} / ${dims[1]}` : `${SIZES.fullBanner[0]} / ${SIZES.fullBanner[1]}` }} />
        </SmartLink>
      ) : <Placeholder size={SIZES.fullBanner} />}
    </div>
  );
}

/* --------------------------------------------------------- Markalar */
function BrandsCarousel({ block, pool }) {
  const imgs = block?.images || [];
  const brands = useMemo(() => {
    if (imgs.length) return [];
    const seen = new Map();
    pool.forEach((p) => { const b = String(p.brand || "").trim(); if (b && !seen.has(b.toLocaleLowerCase("tr"))) seen.set(b.toLocaleLowerCase("tr"), b); });
    return [...seen.values()];
  }, [imgs.length, pool]);
  const items = imgs.length
    ? imgs.map((src, i) => ({ key: src + i, link: block.links?.[i] || "/", node: <img className="img-fluid m-auto max-height-50" src={optimizeImg(src, 400)} alt="" loading="lazy" /> }))
    : brands.map((b) => ({ key: b, link: `/arama?q=${encodeURIComponent(b)}`, node: <span className="el-brand-word">{b}</span> }));
  if (!items.length) return null;
  return (
    <div className="mb-8" data-testid="brands-carousel">
      <div className="py-2 border-top border-bottom">
        <Carousel perView={{ base: 2, sm: 3, md: 4, lg: 5, xl: 6 }} dots={false} arrows className="my-1 el-brands"
          arrowsClassName="u-slick__arrow-normal u-slick__arrow-centered--y" arrowLeftClassName="fa fa-angle-left u-slick__arrow-classic-inner--left z-index-9" arrowRightClassName="fa fa-angle-right u-slick__arrow-classic-inner--right">
          {items.map((it) => (
            <div className="js-slide" key={it.key}>
              <SmartLink to={it.link} className="link-hover__brand d-flex align-items-center justify-content-center el-brand">{it.node}</SmartLink>
            </div>
          ))}
        </Carousel>
      </div>
    </div>
  );
}

/* ---------------------------------------------------- Alt ürün sütunları */
function ProductColumn({ col }) {
  const list = useProducts({ source: col.source || "featured", category_ids: col.category_ids, product_ids: col.product_ids, limit: 3 });
  if (!list || !list.length) return null;
  return (
    <div className="col-md-4 mb-6 mb-md-0">
      <div className="widget-column">
        <div className="border-bottom border-color-1 mb-5">
          <h3 className="section-title section-title__sm mb-0 pb-2 font-size-18">{col.title}</h3>
        </div>
        <ul className="list-unstyled products-group">
          {list.slice(0, 3).map((p) => <ProductCard key={p.id} product={p} variant="list" as="li" />)}
        </ul>
      </div>
    </div>
  );
}

function ProductColumns({ block }) {
  const cols = (block?.settings?.columns || []).filter((c) => c && c.title).slice(0, 3);
  if (!cols.length) return null;
  return (
    <div className="mb-6" data-testid="product-columns">
      <div className="row">{cols.map((c, i) => <ProductColumn key={i} col={c} />)}</div>
    </div>
  );
}

/* --------------------------------------------- Ek bloklar (eski türler) */
function HalfBanners({ block }) {
  const imgs = block?.images || [];
  if (!imgs.length) return null;
  return (
    <div className="mb-6" data-testid="half-banners">
      <div className="row">
        {imgs.slice(0, 4).map((img, i) => (
          <div className={`${imgs.length === 1 ? "col-12" : "col-md-6"} mb-4`} key={i}>
            <SmartLink to={block.links?.[i] || "/"} className="d-block"><img className="img-fluid w-100" src={optimizeImg(img, 900)} alt={block.title || ""} loading="lazy" /></SmartLink>
          </div>
        ))}
      </div>
    </div>
  );
}

function TextBlock({ block }) {
  const img = block?.images?.[0];
  if (!block?.title && !block?.settings?.text && !img) return null;
  return (
    <div className="mb-6" data-testid="text-block">
      {block.title && (
        <div className="border-bottom border-color-1 mb-4"><h3 className="section-title mb-0 pb-2 font-size-22">{block.title}</h3></div>
      )}
      <div className="row align-items-center">
        {img && (
          <div className="col-md-6 mb-4 mb-md-0">
            {block.links?.[0] ? <SmartLink to={block.links[0]}><img className="img-fluid" src={optimizeImg(img, 1200)} alt={block.title || ""} loading="lazy" /></SmartLink>
              : <img className="img-fluid" src={optimizeImg(img, 1200)} alt={block.title || ""} loading="lazy" />}
          </div>
        )}
        <div className={img ? "col-md-6" : "col-12"}>
          {block.settings?.text && <p className="font-size-16 text-gray-90">{block.settings.text}</p>}
          {block.links?.[0] && <SmartLink to={block.links[0]} className="btn btn-primary-dark-w px-5 rounded-pill">Keşfet</SmartLink>}
        </div>
      </div>
    </div>
  );
}

function VideoBanner({ block }) {
  const [playing, setPlaying] = useState(false);
  if (!block?.settings?.video_url && !block?.images?.[0]) return null;
  return (
    <div className="mb-6" data-testid="video-banner">
      {block.settings?.video_url ? (
        <div className="position-relative bg-dark rounded" style={{ aspectRatio: "16 / 9", overflow: "hidden" }}>
          {playing ? (
            <video src={block.settings.video_url} autoPlay loop muted playsInline className="w-100 h-100" style={{ objectFit: "cover" }} />
          ) : (
            <>
              {block.images?.[0] && <img src={optimizeImg(block.images[0], 1400)} alt={block.title || ""} className="w-100 h-100" style={{ objectFit: "cover" }} loading="lazy" />}
              <button type="button" onClick={() => setPlaying(true)} className="btn btn-primary rounded-circle position-absolute" style={{ left: "50%", top: "50%", transform: "translate(-50%,-50%)", width: 72, height: 72 }} aria-label="Oynat">
                <i className="fas fa-play" />
              </button>
            </>
          )}
        </div>
      ) : (
        <SmartLink to={block.links?.[0] || "/"} className="d-block"><img src={optimizeImg(block.images[0], 1400)} alt={block.title || ""} className="img-fluid w-100" loading="lazy" /></SmartLink>
      )}
    </div>
  );
}

function InstaShop({ block }) {
  const store = useStoreInfo();
  const igUrl = socialUrl("instagram", store.instagram);
  const [feed, setFeed] = useState(null);
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/instagram/feed?limit=12`).then((r) => { if (alive) setFeed(r.data?.posts || []); }).catch(() => { if (alive) setFeed([]); });
    return () => { alive = false; };
  }, []);
  const posts = (Array.isArray(feed) && feed.length ? feed : (block?.images || []).map((img, i) => ({ image: img, product_link: block.links?.[i] || "/" }))).slice(0, 12);
  if (!posts.length) return null;
  return (
    <div className="mb-6" data-testid="instashop">
      <div className="border-bottom border-color-1 mb-3 d-flex justify-content-between align-items-end">
        <h3 className="section-title mb-0 pb-2 font-size-22">{block?.title || "Instagram'da Biz"}</h3>
        {igUrl && <a href={igUrl} target="_blank" rel="noopener noreferrer" className="font-size-14 text-gray-90 pb-2"><i className="fab fa-instagram mr-1" />Takip Edin</a>}
      </div>
      <Carousel perView={{ base: 2, md: 4, xl: 6 }} gutter={10} dotsClassName="text-center u-slick__pagination u-slick__pagination--long mb-0 mt-3">
        {posts.map((p, i) => {
          const href = p.product_link || p.permalink || "/";
          const img = <img src={optimizeImg(p.image, 500)} alt="" className="img-fluid w-100" style={{ aspectRatio: "1 / 1", objectFit: "cover" }} loading="lazy" />;
          return <SmartLink key={p.id || i} to={href} className="d-block rounded overflow-hidden">{img}</SmartLink>;
        })}
      </Carousel>
    </div>
  );
}

function HomeSkeleton() {
  return (
    <div data-testid="home-skeleton">
      <div className="bg-gray-1 mb-5 el-hero-v1"><div className="el-hero-v1__row" /></div>
      <div className="container">
        <div className="row mb-5">{[0, 1, 2].map((i) => <div key={i} className="col-md-4 mb-4"><div className="el-skel" style={{ height: 132 }} /></div>)}</div>
        <div className="row mb-5">{[0, 1, 2, 3].map((i) => <div key={i} className="col-6 col-md-3 mb-4"><div className="el-skel" style={{ height: 320 }} /></div>)}</div>
      </div>
    </div>
  );
}

const visibleOn = (b) => {
  const d = b.show_desktop !== false; const m = b.show_mobile !== false;
  if (!d && !m) return null;
  if (!d) return "d-md-none";
  if (!m) return "d-none d-md-block";
  return "";
};

/** Panel "Taslağı sitede önizle": kaydedilmemiş taslak localStorage'dan okunur (yalnız personel). */
function readDraft() {
  try {
    if (new URLSearchParams(window.location.search).get("onizleme") !== "taslak") return null;
    if (!localStorage.getItem("token")) return null;
    const d = JSON.parse(localStorage.getItem("page_design_draft") || "null");
    return Array.isArray(d) ? d : null;
  } catch { return null; }
}

// Tam genişlik (container dışı) bloklar
const FULL_WIDTH = new Set(["hero_slider", "product_grid_212"]);

/* ================================================================ Home */
export default function Home() {
  const [products, setProducts] = useState([]);
  const [blocks, setBlocks] = useState(null);
  const [loading, setLoading] = useState(true);
  const [draft] = useState(readDraft);
  const tree = useCategoryTree();
  useHeroClearance();
  const roots = tree.menuRoots || tree.roots;

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [productsRes, blocksRes] = await Promise.all([
          axios.get(`${API}/products?limit=60&sort=created_at&order=desc`).catch(() => ({ data: {} })),
          draft ? Promise.resolve({ data: draft }) : axios.get(`${API}/page-blocks?page=home`).catch(() => ({ data: null })),
        ]);
        if (!active) return;
        setProducts(productsRes.data?.products || []);
        const isPreview = !!draft || new URLSearchParams(window.location.search).get("preview") === "true";
        const raw = Array.isArray(blocksRes.data) ? blocksRes.data : null;
        setBlocks(raw ? raw.filter((b) => isPreview || b.is_active).toSorted((a, b) => (a.sort_order || 0) - (b.sort_order || 0)) : null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [draft]);

  const pool = useMemo(() => dedupeColorGroups(products), [products]);
  const all = blocks || [];
  const rotatingBlock = all.find((b) => b.type === "rotating_text");
  const countdownBlock = all.find((b) => b.type === "countdown_bar");
  const announcementFirst = !!(rotatingBlock && countdownBlock) && (Number(rotatingBlock.sort_order ?? 0) < Number(countdownBlock.sort_order ?? 0));
  // Panelde hiç düzen bloğu yoksa (yeni kurulum / API hatası) şablon varsayılan düzeni
  const layout = all.filter((b) => !["rotating_text", "countdown_bar"].includes(b.type));
  const flow = layout.length ? layout : DEFAULT_HOME_BLOCKS;
  const hasColumns = flow.some((b) => b.type === "product_columns" && visibleOn(b) !== null);

  // Hero'da görsel yoksa: öne çıkan/indirimli ürünlerden şablondaki "ürün slaytı" düzeni
  const fallbackSlides = useMemo(() => {
    const src = pool.filter((p) => p.is_featured).concat(pool).slice(0, 3);
    if (!src.length) return [{ title: "Atölyeniz için profesyonel ekipman", subtitle: "Liftler · Kompresörler · Lastik ekipmanları", cta: "Kategorileri Keşfet", link: "/tum-urunler" }];
    return src.map((p) => ({ title: p.name, subtitle: p.brand ? `${p.brand} · ${p.category_name || ""}` : p.category_name, price: priceOf(p).display, cta: "Hemen İncele", link: `/${p.slug || p.id}`, productImage: firstImage(p) }));
  }, [pool]);

  const renderBlock = (block) => {
    switch (block.type) {
      case "hero_slider": return <HeroV1 block={block} fallbackSlides={fallbackSlides} />;
      case "ads_block": return <AdsBlock block={block} />;
      case "deals_tabs": return <DealsTabs block={block} pool={pool} />;
      case "product_grid_212": return roots.length ? <ProductGrid212 block={block} roots={roots} /> : null;
      case "best_sellers": return <BestSellers block={block} roots={roots} />;
      case "full_banner": return <FullBanner block={block} />;
      case "product_slider": return <SliderBlock block={block} />;
      case "brands_carousel": return <BrandsCarousel block={block} pool={pool} />;
      case "product_columns": return <ProductColumns block={block} />;
      case "half_banners": return <HalfBanners block={block} />;
      case "text_block": return <TextBlock block={block} />;
      case "video_banner": return <VideoBanner block={block} />;
      case "instashop": return <InstaShop block={block} />;
      default: return null;
    }
  };

  // Ardışık container-içi blokları tek .container altında topla; tam genişlikleri ayrı bas.
  const sections = [];
  flow.forEach((block) => {
    const vis = visibleOn(block);
    if (vis === null) return;
    const el = renderBlock(block);
    if (!el) return;
    const node = <div key={block.id} className={vis || undefined} data-block-type={block.type}>{el}</div>;
    const last = sections[sections.length - 1];
    if (FULL_WIDTH.has(block.type)) sections.push({ full: true, nodes: [node] });
    else if (last && !last.full) last.nodes.push(node);
    else sections.push({ full: false, nodes: [node] });
  });

  return (
    <div className="sf-page" data-testid="home-page">
      <Header announcement={rotatingBlock ? <RotatingText block={rotatingBlock} /> : null} announcementFirst={announcementFirst} />
      <main id="content" role="main" className="electro el-page">
        <h1 className="sr-only">{SITE_NAME} — Oto Servis ve Garaj Ekipmanları</h1>
        {draft && <div className="bg-primary text-center font-size-13 font-weight-bold py-1" data-testid="draft-preview-bar">Taslak önizleme — değişiklikler henüz yayında değil</div>}
        {loading ? <HomeSkeleton /> : sections.map((s, i) => (s.full ? <div key={i}>{s.nodes}</div> : <div key={i} className="container">{s.nodes}</div>))}
      </main>
      <Footer hideWidgets={hasColumns} />
    </div>
  );
}
