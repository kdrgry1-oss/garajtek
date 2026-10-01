// Ana sayfa — Electro "Home v1" düzeni.
// Veri kaynakları korunur: Admin › Tasarım › Sayfa Blokları (/page-blocks?page=home) + Admin ›
// Bannerlar (/banners) + ürün/kategori API'leri. Admin verisi olmayan bölümler ürün/kategori
// verisinden otomatik doldurulur (öne çıkanlar, indirimdekiler, çok satanlar, yeni ürünler).
//   hero_slider   → Electro hero slider (sol tarafta "Tüm Kategoriler" menüsüne yer bırakır)
//   half_banners  → 4'lü "fırsat" banner şeridi
//   product_slider→ Electro ürün karuseli (başlık + sekme çizgisi)
//   full_banner   → tam genişlik banner
//   text_block / video_banner / instashop → Electro bölüm başlığıyla
//   rotating_text / countdown_bar → header üst barları
import { useEffect, useLayoutEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import RotatingText from "../components/RotatingText";
import Footer from "../components/Footer";
import ProductCard, { CardPrice, useProductActions } from "../components/ProductCard";
import Carousel from "../components/electro/Carousel";
import Countdown from "../components/electro/Countdown";
import useCategoryTree, { descendantIds } from "../components/electro/useCategoryTree";
import { optimizeImg, firstImage, galleryImages } from "../lib/img";
import { trackSelectPromotion } from "../lib/dataLayer";
import { dedupeColorGroups } from "../lib/colorGroups";
import { fmtPrice, priceOf, productHref } from "../components/electro/format";
import { useStoreInfo } from "../lib/storeInfo";
import { socialUrl, SITE_NAME } from "../lib/brand";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const isVideoUrl = (u) => typeof u === "string" && /\.(mp4|webm|mov|m4v|ogg)(\?|$)/i.test(u);
const promo = (id, name) => { try { trackSelectPromotion({ promotionId: id, promotionName: name }); } catch (_) { /* silent */ } };

function splitPrice(n) {
  const v = Number(n) || 0;
  const int = Math.floor(v);
  const dec = Math.round((v - int) * 100);
  return { int: int.toLocaleString("tr-TR"), dec: String(dec).padStart(2, "0") };
}

/* ---------------------------------------------------------------- Hero */
const HERO_MIN = 420; // Electro home-v1 hero yüksekliği (min-height-420)

/** Masaüstünde ana sayfada AÇIK duran "Tüm Kategoriler" dikey menüsü hero'nun üstüne biner.
 * Menü hero'dan uzunsa (çok kategori / büyük yazı tipi) alttaki 4'lü banner şeridini örtmesin
 * diye hero yüksekliği (--el-hero-h) menünün altına kadar uzatılır. Mobil/tablette menü gizli
 * olduğundan değişken kaldırılır ve hero 420px kalır. */
function useHeroClearance() {
  useLayoutEffect(() => {
    if (typeof window === "undefined" || typeof document === "undefined") return undefined;
    const root = document.documentElement;
    let last = 0;
    const calc = () => {
      const vm = document.querySelector('.el-header-wrap [data-testid="vertical-menu"]');
      const hero = document.querySelector(".el-hero-bg");
      if (!vm || !hero || window.innerWidth < 1200) {
        if (last) { root.style.removeProperty("--el-hero-h"); last = 0; }
        return;
      }
      const vr = vm.getBoundingClientRect();
      if (!vr.height) return; // menü kapalı → son değeri koru (tıklamada zıplamasın)
      const need = Math.ceil(vr.bottom - hero.getBoundingClientRect().top) + 24;
      const h = need > HERO_MIN ? need : 0;
      if (h !== last) {
        if (h) root.style.setProperty("--el-hero-h", `${h}px`); else root.style.removeProperty("--el-hero-h");
        last = h;
      }
    };
    calc();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(calc) : null;
    const mo = typeof MutationObserver !== "undefined" ? new MutationObserver(calc) : null;
    const wrap = document.querySelector(".el-header-wrap");
    if (ro) { ro.observe(document.body); if (wrap) ro.observe(wrap); }
    if (mo && wrap) mo.observe(wrap, { childList: true, subtree: true, attributes: true, attributeFilter: ["class"] });
    window.addEventListener("resize", calc);
    return () => {
      if (ro) ro.disconnect();
      if (mo) mo.disconnect();
      window.removeEventListener("resize", calc);
      root.style.removeProperty("--el-hero-h");
    };
  }, []);
}

/** Varsayılan GarajTek hero'su — panelde slayt/banner ve öne çıkan ürün yokken (yeni kurulum)
 * hero alanı Electro yüksekliğini (420px) korusun, açık "Tüm Kategoriler" menüsü alttaki
 * banner'ların üstüne taşmasın. Harici görsel yok: yalnız CSS + satır içi SVG. */
function DefaultHero() {
  return (
    <div className="mb-5" data-testid="hero-slider">
      <div className="bg-img-hero bg-gray-1 el-hero-bg el-hero-default" data-testid="hero-default">
        <div className="container min-height-420 overflow-hidden position-relative">
          <div className="row min-height-420 align-items-center py-6 py-md-0">
            <div className="offset-xl-3 col-xl-5 col-md-7 col-12 el-hero-default__text">
              <span className="el-hero-default__eyebrow">OTO SERVİS &amp; GARAJ EKİPMANLARI</span>
              <h2 className="font-size-46 text-lh-57 font-weight-light mb-3">
                Atölyeniz için <strong className="font-weight-bold d-block">profesyonel ekipman</strong>
              </h2>
              <p className="font-size-15 text-gray-90 mb-4">
                Liftler, kompresörler, lastik ekipmanları ve el aletleri — servisinizi kurmak ya da
                büyütmek için ihtiyacınız olan her şey tek adreste.
              </p>
              <div className="d-flex flex-wrap align-items-center">
                <Link to="/tum-urunler" className="btn btn-primary transition-3d-hover rounded-lg font-weight-normal py-2 px-md-7 px-4 font-size-16 mr-3 mb-2"
                  onClick={() => promo("hero_default", "Kategorileri Keşfet")} data-testid="hero-default-cta">
                  Kategorileri Keşfet
                </Link>
                <Link to="/sale" className="font-weight-bold text-gray-90 font-size-15 mb-2">Kampanyalar <i className="ec ec-arrow-right-categproes ml-1" /></Link>
              </div>
            </div>
            <div className="col-xl-4 col-md-5 d-none d-md-flex el-hero-media">
              <svg className="el-hero-default__art" viewBox="0 0 420 340" role="img" aria-label="Araç lifti üzerinde otomobil">
                <circle cx="230" cy="170" r="150" fill="#fed700" opacity=".18" />
                <circle cx="230" cy="170" r="110" fill="#fed700" opacity=".22" />
                {/* Lift sütunları */}
                <rect x="70" y="40" width="26" height="270" rx="4" fill="#333e48" />
                <rect x="324" y="40" width="26" height="270" rx="4" fill="#333e48" />
                <rect x="62" y="300" width="42" height="12" rx="3" fill="#333e48" />
                <rect x="316" y="300" width="42" height="12" rx="3" fill="#333e48" />
                <rect x="76" y="50" width="14" height="250" fill="#fed700" opacity=".9" />
                <rect x="330" y="50" width="14" height="250" fill="#fed700" opacity=".9" />
                {/* Kollar */}
                <rect x="92" y="186" width="96" height="10" rx="3" fill="#5b6670" />
                <rect x="232" y="186" width="96" height="10" rx="3" fill="#5b6670" />
                {/* Otomobil */}
                <path d="M118 176 L136 136 Q146 116 172 114 L250 112 Q276 112 292 132 L314 160 Q332 164 334 176 L334 186 L106 186 L106 180 Q108 176 118 176 Z" fill="#333e48" />
                <path d="M150 140 Q156 126 174 124 L208 123 L208 156 L142 158 Z" fill="#cfd8dc" />
                <path d="M218 123 L250 122 Q268 122 280 136 L292 154 L218 156 Z" fill="#cfd8dc" />
                <circle cx="160" cy="188" r="22" fill="#1f262c" /><circle cx="160" cy="188" r="9" fill="#9aa5ad" />
                <circle cx="288" cy="188" r="22" fill="#1f262c" /><circle cx="288" cy="188" r="9" fill="#9aa5ad" />
                <rect x="316" y="166" width="14" height="6" rx="2" fill="#fed700" />
                {/* Zemin + anahtar */}
                <rect x="40" y="312" width="340" height="4" rx="2" fill="#333e48" opacity=".25" />
                <g transform="translate(176 236) rotate(-28)">
                  <rect x="0" y="-6" width="86" height="12" rx="6" fill="#fed700" />
                  <circle cx="0" cy="0" r="15" fill="#fed700" /><rect x="-6" y="-16" width="12" height="13" fill="#f5f5f5" />
                </g>
              </svg>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function HeroSlider({ slides }) {
  if (!slides.length) return <DefaultHero />;
  return (
    <div className="mb-5" data-testid="hero-slider">
      <div className="bg-img-hero bg-gray-1 el-hero-bg">
        <div className="container min-height-420 overflow-hidden">
          <Carousel perView={{ base: 1 }} loop autoplay={6000} ariaLabel="Kampanyalar"
            dotsClassName="text-center position-absolute right-0 bottom-0 left-0 u-slick__pagination u-slick__pagination--long justify-content-start mb-3 mb-md-4 offset-xl-3 pl-2 pb-1">
            {slides.map((s, i) => (s.image && !s.product ? (
              <Link key={i} to={s.link || "/"} className="d-block position-relative min-height-420 el-hero-slide"
                onClick={() => promo(`hero_${i + 1}`, s.title || s.link || `Hero ${i + 1}`)}>
                {isVideoUrl(s.image) ? (
                  <video className="el-hero-img" src={s.image} muted loop playsInline autoPlay={i === 0} preload={i === 0 ? "auto" : "none"} />
                ) : (
                  <picture>
                    {s.mobileImage && <source media="(max-width: 767px)" srcSet={optimizeImg(s.mobileImage, 800)} />}
                    <img className="el-hero-img" src={optimizeImg(s.image, 1920, 78)} alt={s.title || ""} fetchPriority={i === 0 ? "high" : "auto"} loading={i === 0 ? "eager" : "lazy"} decoding="async" />
                  </picture>
                )}
                {(s.title || s.eyebrow || s.cta) && (
                  <div className="row min-height-420 py-7 py-md-0 position-relative">
                    <div className="offset-xl-3 col-xl-4 col-8 mt-md-8">
                      {s.title && <h2 className="font-size-46 text-lh-57 font-weight-light">{s.title}</h2>}
                      {s.eyebrow && <h6 className="font-size-15 font-weight-bold mb-3">{s.eyebrow}</h6>}
                      {s.cta && <span className="btn btn-primary transition-3d-hover rounded-lg font-weight-normal py-2 px-md-7 px-3 font-size-16">{s.cta}</span>}
                    </div>
                  </div>
                )}
              </Link>
            ) : (
              <div key={i} className="js-slide bg-img-hero-center">
                <div className="row min-height-420 py-7 py-md-0">
                  <div className="offset-xl-3 col-xl-4 col-6 mt-md-8">
                    <h2 className="font-size-64 text-lh-57 font-weight-light">
                      {s.line1}<span className="d-block font-size-55">{s.line2}</span>
                    </h2>
                    <h6 className="font-size-15 font-weight-bold mb-3 el-line-2">{s.subtitle}</h6>
                    {s.price != null && (
                      <div className="mb-4">
                        <span className="font-size-13">BAŞLAYAN FİYATLARLA</span>
                        <div className="font-size-50 font-weight-bold text-lh-45">
                          {splitPrice(s.price).int}<sup>,{splitPrice(s.price).dec}</sup><sup className="font-size-25 ml-1">₺</sup>
                        </div>
                      </div>
                    )}
                    <Link to={s.link} onClick={() => promo(`hero_${i + 1}`, s.subtitle)} className="btn btn-primary transition-3d-hover rounded-lg font-weight-normal py-2 px-md-7 px-3 font-size-16">
                      Hemen İncele
                    </Link>
                  </div>
                  <div className="col-xl-5 col-6 d-flex align-items-center el-hero-media">
                    {s.productImage && <img className="img-fluid" src={optimizeImg(s.productImage, 840)} alt={s.subtitle} width="416" height="420" fetchPriority={i === 0 ? "high" : "auto"} loading={i === 0 ? "eager" : "lazy"} />}
                  </div>
                </div>
              </div>
            )))}
          </Carousel>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------- 4'lü fırsat banner'ı */
function SmallBanners({ items }) {
  if (!items.length) return null;
  return (
    <div className="mb-5" data-testid="half-banners">
      <div className="row">
        {items.slice(0, 4).map((b, i) => (
          <div className="col-md-6 mb-4 mb-xl-0 col-xl-3" key={i}>
            <Link to={b.link || "/"} className="d-black text-gray-90" onClick={() => promo(`banner_${i + 1}`, b.title || b.link)}>
              {b.full ? (
                <img className="img-fluid w-100" src={optimizeImg(b.image, 600)} alt={b.title || ""} loading="lazy" />
              ) : (
                <div className="min-height-132 py-1 d-flex bg-gray-1 align-items-center">
                  <div className="col-6 col-xl-5 col-wd-6 pr-0">
                    {b.image ? <img className="img-fluid el-banner-img" src={optimizeImg(b.image, 380)} alt="" loading="lazy" width="190" height="150" /> : null}
                  </div>
                  <div className="col-6 col-xl-7 col-wd-6">
                    <div className="mb-2 pb-1 font-size-18 font-weight-light text-ls-n1 text-lh-23">
                      {b.pre} <strong>{b.strong}</strong> {b.post}
                    </div>
                    <div className="link text-gray-90 font-weight-bold font-size-15">
                      Hemen İncele
                      <span className="link__icon ml-1"><span className="link__icon-inner"><i className="ec ec-arrow-right-categproes" /></span></span>
                    </div>
                  </div>
                </div>
              )}
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

/* --------------------------------------------- Günün fırsatı + sekmeler */
function SpecialOffer({ product }) {
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
    <div className="p-3 border border-width-2 border-primary borders-radius-20 bg-white min-width-370" data-testid="special-offer">
      <div className="d-flex justify-content-between align-items-center m-1 ml-2">
        <h3 className="font-size-22 mb-0 font-weight-normal text-lh-28 max-width-120">Günün Fırsatı</h3>
        {save > 0 && (
          <div className="d-flex align-items-center flex-column justify-content-center bg-primary rounded-pill height-75 width-75 text-lh-1">
            <span className="font-size-12">Kazanç</span>
            <div className="font-size-16 font-weight-bold">{Math.round(save).toLocaleString("tr-TR")} ₺</div>
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
  const avail = tabs.filter((t) => t.items.length);
  const [active, setActive] = useState(0);
  if (!avail.length) return null;
  const cur = avail[Math.min(active, avail.length - 1)];
  return (
    <div data-testid={testId}>
      <div className="position-relative bg-white text-center z-index-2">
        <ul className="nav nav-classic nav-tab justify-content-center" role="tablist">
          {avail.map((t, i) => (
            <li className="nav-item" key={t.key}>
              <a href={`#${t.key}`} role="tab" aria-selected={cur.key === t.key} className={`nav-link${cur.key === t.key ? " active" : ""}`}
                onClick={(e) => { e.preventDefault(); setActive(i); }}>
                <div className="d-md-flex justify-content-md-center align-items-md-center">{t.label}</div>
              </a>
            </li>
          ))}
        </ul>
      </div>
      <div className="tab-content">
        <div className="tab-pane fade pt-2 show active" role="tabpanel">
          <ul className="row list-unstyled products-group no-gutters">
            {cur.items.slice(0, 6).map((p, i) => (
              <ProductCard key={p.id} product={p} as="li" listName={cur.key} index={i}
                className={`col-6 col-wd-3 col-md-4${i === 2 ? " remove-divider-xl" : ""}${i === 3 ? " remove-divider-wd" : ""}${i >= 4 ? " d-wd-none" : ""}`} />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------- 4-1-4 kategori sekmeli ürün grubu */
function Products414({ roots }) {
  const cats = roots.slice(0, 8);
  const [active, setActive] = useState(0);
  const [items, setItems] = useState({});
  const key = active === 0 ? "__best" : cats[active - 1]?.slug;
  useEffect(() => {
    if (!key || items[key]) return undefined;
    let alive = true;
    const url = key === "__best" ? `${API}/products?limit=9&sort=popular` : `${API}/products?limit=9&sort=popular&category=${encodeURIComponent(key)}`;
    axios.get(url).then((r) => { if (alive) setItems((m) => ({ ...m, [key]: r.data?.products || [] })); })
      .catch(() => { if (alive) setItems((m) => ({ ...m, [key]: [] })); });
    return () => { alive = false; };
  }, [key, items]);
  const list = items[key] || [];
  const all = items.__best || [];
  if (!all.length && key === "__best" && items.__best) return null;
  const big = list[0];
  const left = list.slice(1, 5);
  const right = list.slice(5, 9);
  const tabsList = [{ label: "En İyi Fırsatlar" }, ...cats.map((c) => ({ label: c.name }))];
  const cell = (p, i) => (
    <ProductCard key={p.id} product={p} as="li" className={`col-xl-6 max-width-xl-100 remove-divider${i >= 2 ? " d-md-none d-wd-block" : ""}`}
      innerClassName="product-item__inner bg-white p-3" />
  );
  return (
    <div className="products-group-4-1-4 space-1 bg-gray-7 mb-6" data-testid="products-414">
      <h2 className="sr-only">Kategori ürünleri</h2>
      <div className="container">
        <div className="position-relative text-center z-index-2 mb-3">
          <ul className="nav nav-classic nav-tab nav-tab-sm px-md-3 justify-content-start justify-content-lg-center flex-nowrap flex-lg-wrap overflow-auto overflow-lg-visble border-md-down-bottom-0 pb-1 pb-lg-0 mb-n1 mb-lg-0" role="tablist">
            {tabsList.map((t, i) => (
              <li className="nav-item flex-shrink-0 flex-lg-shrink-1" key={t.label}>
                <a href="#urunler" role="tab" aria-selected={i === active} className={`nav-link${i === active ? " active" : ""}`} onClick={(e) => { e.preventDefault(); setActive(i); }}>
                  <div className="d-md-flex justify-content-md-center align-items-md-center">{t.label}</div>
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div className="tab-content">
          <div className="tab-pane fade pt-2 show active" role="tabpanel">
            {!items[key] ? (
              <div className="row no-gutters">{[0, 1, 2].map((i) => <div key={i} className="col-md-4 p-2"><div className="el-skel" style={{ height: 420 }} /></div>)}</div>
            ) : !list.length ? (
              <div className="text-center py-6 text-gray-90">Bu kategoride henüz ürün bulunmuyor.</div>
            ) : (
              <div className="row no-gutters">
                <div className="col-md-3 col-wd-4 d-md-flex d-wd-block">
                  <ul className="row list-unstyled products-group no-gutters mb-0 flex-xl-column flex-wd-row">{left.map(cell)}</ul>
                </div>
                <div className="col-md-6 col-wd-4 products-group-1">
                  <ul className="row list-unstyled products-group no-gutters bg-white h-100 mb-0">
                    {big && <BigProduct product={big} />}
                  </ul>
                </div>
                <div className="col-md-3 col-wd-4 d-md-flex d-wd-block">
                  <ul className="row list-unstyled products-group no-gutters mb-0 flex-xl-column flex-wd-row">{right.map(cell)}</ul>
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
  const a = useProductActions(product, { listName: "products_414" });
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
            <div className="mb-1 min-height-4-1-4">
              <Link to={a.href} onClick={a.select} className="d-block text-center my-4 mt-lg-6 mb-lg-5 mt-xl-0 mb-xl-0 mt-wd-6 mb-wd-5">
                <span className="el-img-box" style={{ aspectRatio: "564 / 520" }}>
                  <img className="img-fluid" src={optimizeImg(imgs[cur] || "/placeholder.jpg", 800)} alt={product.name} loading="lazy" />
                </span>
              </Link>
              {imgs.length > 1 && (
                <div className="row mx-gutters-2 mb-3">
                  {imgs.slice(0, 3).map((im, i) => (
                    <div className="col-auto" key={im}>
                      <button type="button" className={`max-width-60 u-media-viewer btn p-0 border-0${cur === i ? " opacity-1" : ""}`} onClick={() => setCur(i)} aria-label={`Görsel ${i + 1}`}>
                        <img className="img-fluid border" src={optimizeImg(im, 120)} alt="" loading="lazy" width="60" height="60" />
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

function Bestsellers({ products, roots, title = "Çok Satanlar" }) {
  const [tab, setTab] = useState(null);
  const [byCat, setByCat] = useState({});
  useEffect(() => {
    if (!tab || byCat[tab]) return undefined;
    let alive = true;
    axios.get(`${API}/products?limit=12&sort=popular&category=${encodeURIComponent(tab)}`)
      .then((r) => { if (alive) setByCat((m) => ({ ...m, [tab]: r.data?.products || [] })); })
      .catch(() => { if (alive) setByCat((m) => ({ ...m, [tab]: [] })); });
    return () => { alive = false; };
  }, [tab, byCat]);
  const list = tab ? (byCat[tab] || []) : products;
  if (!products.length) return null;
  return (
    <div className="space-top-2 mb-6" data-testid="bestsellers">
      <div className="d-flex justify-content-between border-bottom border-color-1 flex-md-nowrap flex-wrap border-sm-bottom-0">
        <h3 className="section-title mb-0 pb-2 font-size-22">{title}</h3>
        <ul className="nav nav-pills mb-2 pt-3 pt-md-0 mb-0 border-top border-color-1 border-md-top-0 align-items-center font-size-15 font-size-15-md flex-nowrap flex-md-wrap overflow-auto overflow-md-visble">
          <li className="nav-item flex-shrink-0 flex-md-shrink-1">
            <a href="#top" onClick={(e) => { e.preventDefault(); setTab(null); }} className={tab ? "nav-link text-gray-8" : "text-gray-90 btn btn-outline-primary border-width-2 rounded-pill py-1 px-4 font-size-15 text-lh-19 font-size-15-md"}>İlk 20</a>
          </li>
          {roots.slice(0, 3).map((c) => (
            <li className="nav-item flex-shrink-0 flex-md-shrink-1" key={c.id}>
              <a href={`#${c.slug}`} onClick={(e) => { e.preventDefault(); setTab(c.slug); }} className={tab === c.slug ? "text-gray-90 btn btn-outline-primary border-width-2 rounded-pill py-1 px-4 font-size-15 text-lh-19 font-size-15-md" : "nav-link text-gray-8"}>{c.name}</a>
            </li>
          ))}
        </ul>
      </div>
      {list.length === 0 ? (
        <div className="py-6 text-center text-gray-90">{tab && !byCat[tab] ? "Yükleniyor…" : "Bu kategoride ürün bulunamadı."}</div>
      ) : (
        <Carousel key={tab || "top"} perView={{ base: 1 }} className="u-slick--gutters-2 overflow-hidden u-slick-overflow-visble pt-3 pb-6"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-4">
          {chunk(list.slice(0, 18), 6).map((group, gi) => (
            <ul className="row list-unstyled products-group no-gutters mb-0 overflow-visible" key={gi}>
              {group.map((p, i) => (
                <ProductCard key={p.id} product={p} as="li" variant="card" listName="bestsellers" index={gi * 6 + i}
                  className={`col-wd-3 col-md-4 border-bottom border-md-bottom-0${i % 3 === 2 ? " remove-divider-xl" : ""}${i >= 6 ? "" : ""}`} />
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
  if (!products.length) return null;
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

/* ------------------------------------------------------- Tam banner */
function FullBanner({ banner, cheapest }) {
  if (banner && banner.image) {
    return (
      <div className="mb-6" data-testid="full-banner">
        <Link to={banner.link || "/"} className="d-block" onClick={() => promo("full_banner", banner.title || banner.link)}>
          <img className="img-fluid w-100" src={optimizeImg(banner.image, 1400)} alt={banner.title || ""} loading="lazy" style={{ aspectRatio: banner.dims ? `${banner.dims[0]} / ${banner.dims[1]}` : undefined }} />
        </Link>
      </div>
    );
  }
  if (!cheapest) return null;
  const sp = splitPrice(priceOf(cheapest).display);
  return (
    <div className="mb-6" data-testid="full-banner">
      <Link to="/sale" className="d-block text-gray-90">
        <div className="bg-gray-1">
          <div className="space-top-2-md p-4 pt-6 pt-md-8 pt-lg-6 pt-xl-8 pb-lg-4 px-xl-8 px-lg-6">
            <div className="flex-horizontal-center mt-lg-3 mt-xl-0 overflow-auto overflow-md-visble">
              <h2 className="text-lh-38 font-size-32 font-weight-light mb-0 flex-shrink-0 flex-md-shrink-1">
                ATÖLYENİZİ <strong>KAZANÇLA</strong> DONATIN — SERVİS EKİPMANLARINDA FIRSATLAR
              </h2>
              <div className="ml-5 flex-content-center flex-shrink-0">
                <div className="bg-primary rounded-lg px-6 py-2">
                  <em className="font-size-14 font-weight-light">BAŞLAYAN FİYATLARLA</em>
                  <div className="font-size-30 font-weight-bold text-lh-1">{sp.int}<sup>,{sp.dec}</sup><sup className="ml-1">₺</sup></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </Link>
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
            {block.links?.[0] ? <Link to={block.links[0]}><img className="img-fluid" src={optimizeImg(img, 1200)} alt={block.title || ""} loading="lazy" /></Link>
              : <img className="img-fluid" src={optimizeImg(img, 1200)} alt={block.title || ""} loading="lazy" />}
          </div>
        )}
        <div className={img ? "col-md-6" : "col-12"}>
          {block.settings?.text && <p className="font-size-16 text-gray-90">{block.settings.text}</p>}
          {block.links?.[0] && <Link to={block.links[0]} className="btn btn-primary-dark-w px-5 rounded-pill">Keşfet</Link>}
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
        <Link to={block.links?.[0] || "/"} className="d-block"><img src={optimizeImg(block.images[0], 1400)} alt={block.title || ""} className="img-fluid w-100" loading="lazy" /></Link>
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
          return /^https?:/.test(href)
            ? <a key={p.id || i} href={href} target="_blank" rel="noopener noreferrer" className="d-block rounded overflow-hidden">{img}</a>
            : <Link key={p.id || i} to={href} className="d-block rounded overflow-hidden">{img}</Link>;
        })}
      </Carousel>
    </div>
  );
}

function HomeSkeleton() {
  return (
    <div data-testid="home-skeleton">
      <div className="bg-gray-1 mb-5 el-hero-bg"><div className="container min-height-420" /></div>
      <div className="container">
        <div className="row mb-5">{[0, 1, 2, 3].map((i) => <div key={i} className="col-md-6 col-xl-3 mb-4"><div className="el-skel" style={{ height: 132 }} /></div>)}</div>
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

/* ================================================================ Home */
export default function Home() {
  const [products, setProducts] = useState([]);
  const [blocks, setBlocks] = useState([]);
  const [banners, setBanners] = useState([]);
  const [popular, setPopular] = useState([]);
  const [discounted, setDiscounted] = useState([]);
  const [featured, setFeatured] = useState([]);
  const [loading, setLoading] = useState(true);
  const tree = useCategoryTree();
  useHeroClearance();
  const roots = tree.menuRoots || tree.roots;

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [productsRes, blocksRes, bannersRes] = await Promise.all([
          axios.get(`${API}/products?limit=100&sort=created_at&order=desc`),
          axios.get(`${API}/page-blocks?page=home`).catch(() => ({ data: [] })),
          axios.get(`${API}/banners?is_active=true`).catch(() => ({ data: [] })),
        ]);
        if (!active) return;
        setProducts(productsRes.data?.products || []);
        const isPreview = new URLSearchParams(window.location.search).get("preview") === "true";
        setBlocks((blocksRes.data || []).filter((b) => isPreview || b.is_active).toSorted((a, b) => (a.sort_order || 0) - (b.sort_order || 0)));
        setBanners(Array.isArray(bannersRes.data) ? bannersRes.data : []);
      } catch (err) {
        console.error(err);
      } finally {
        if (active) setLoading(false);
      }
    })();
    Promise.all([
      axios.get(`${API}/products?limit=18&sort=popular`).catch(() => null),
      axios.get(`${API}/products/slider-feed?source=discounted&limit=12`).catch(() => null),
      axios.get(`${API}/products?limit=12&is_featured=true`).catch(() => null),
    ]).then(([p, d, f]) => {
      if (!active) return;
      setPopular(p?.data?.products || []);
      setDiscounted(d?.data?.products || []);
      setFeatured(f?.data?.products || []);
    });
    return () => { active = false; };
  }, []);

  // ZAMANLI BANNER: sekme öne gelince blokları tazele (yayın aralığı sunucuda süzülür).
  useEffect(() => {
    let lastAt = Date.now();
    const onVisible = async () => {
      if (document.visibilityState !== "visible" || Date.now() - lastAt < 60000) return;
      lastAt = Date.now();
      const res = await axios.get(`${API}/page-blocks?page=home`).catch(() => null);
      if (!res) return;
      const isPreview = new URLSearchParams(window.location.search).get("preview") === "true";
      setBlocks((res.data || []).filter((b) => isPreview || b.is_active).toSorted((a, b) => (a.sort_order || 0) - (b.sort_order || 0)));
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  const newest = useMemo(() => dedupeColorGroups(products), [products]);
  const onSale = discounted.length ? discounted : newest.filter((p) => priceOf(p).hasDiscount);
  const feat = featured.length ? featured : newest.slice(0, 6);
  const best = popular.length ? popular : newest.slice(0, 18);

  const rotatingBlock = blocks.find((b) => b.type === "rotating_text");
  const countdownBlock = blocks.find((b) => b.type === "countdown_bar");
  const announcementFirst = !!(rotatingBlock && countdownBlock) && (Number(rotatingBlock.sort_order ?? 0) < Number(countdownBlock.sort_order ?? 0));

  // --- Hero slaytları: page-block hero_slider → Admin Bannerlar (home/hero) → ürünlerden
  const heroBlock = blocks.find((b) => b.type === "hero_slider");
  const deviceOk = (b) => !b.device || b.device === "all" || b.device === (typeof window !== "undefined" && window.innerWidth < 768 ? "mobile" : "desktop");
  const homeBanners = banners.filter((b) => deviceOk(b) && ["home", "hero", "home_slider", "slider"].includes(String(b.position || "home")));
  let heroSlides = [];
  if (heroBlock && heroBlock.images?.length) {
    const caps = heroBlock.settings?.captions || [];
    heroSlides = heroBlock.images.map((img, i) => ({ image: img, link: heroBlock.links?.[i] || "/", title: caps[i]?.title, eyebrow: caps[i]?.eyebrow, cta: caps[i]?.cta }));
  } else if (homeBanners.length) {
    heroSlides = homeBanners.map((b) => ({ image: b.image_url || b.image || b.video_url, mobileImage: b.mobile_image, link: b.link_url || b.link || "/", title: b.title, eyebrow: b.subtitle }));
  } else {
    heroSlides = (feat.length ? feat : newest).slice(0, 3).map((p) => {
      return {
        product: true,
        line1: "ATÖLYENİZ",
        line2: "İÇİN EN İYİSİ",
        subtitle: p.name,
        price: priceOf(p).display,
        productImage: firstImage(p),
        link: productHref(p),
      };
    });
  }

  // --- 4'lü banner: half_banners bloğu → Admin Bannerlar (home_small/category) → kategoriler
  const halfBlock = blocks.find((b) => b.type === "half_banners");
  const smallBanners = banners.filter((b) => deviceOk(b) && ["home_small", "home_banner", "category", "small"].includes(String(b.position || "")));
  let banner4 = [];
  if (halfBlock && halfBlock.images?.length) {
    banner4 = halfBlock.images.map((img, i) => ({ image: img, link: halfBlock.links?.[i] || "/", full: true, title: halfBlock.title }));
  } else if (smallBanners.length) {
    banner4 = smallBanners.map((b) => ({ image: b.image_url || b.image, link: b.link_url || b.link || "/", full: true, title: b.title }));
  } else if (roots.length) {
    banner4 = roots.slice(0, 4).map((c) => {
      const ids = descendantIds(c);
      const sample = newest.find((p) => ids.has(String(p.category_id))) || null;
      return { image: c.image_url || c.image || (sample ? firstImage(sample) : ""), link: `/${c.slug}`, pre: "", strong: c.name.toLocaleUpperCase("tr"), post: "FIRSATLARI" };
    });
  }

  const special = useMemo(() => {
    const pool = [...onSale, ...newest];
    let bestP = null; let bestPct = -1;
    for (const p of pool) { const pv = priceOf(p); if (pv.discountPct > bestPct) { bestPct = pv.discountPct; bestP = p; } }
    return bestP;
  }, [onSale, newest]);

  const fullBannerBlock = blocks.find((b) => b.type === "full_banner" && b.images?.[0]);
  const wideBanner = banners.find((b) => deviceOk(b) && ["home_wide", "wide", "full"].includes(String(b.position || "")));
  const fullBanner = fullBannerBlock
    ? { image: fullBannerBlock.images[0], link: fullBannerBlock.links?.[0], title: fullBannerBlock.title, dims: fullBannerBlock.settings?.img_dims?.[0] }
    : wideBanner ? { image: wideBanner.image_url || wideBanner.image, link: wideBanner.link_url || wideBanner.link, title: wideBanner.title } : null;
  const cheapest = useMemo(() => [...onSale].sort((a, b) => priceOf(a).display - priceOf(b).display)[0] || null, [onSale]);

  // Son gezilenler (ürün detay sayfası localStorage'a yazar)
  const [recent, setRecent] = useState([]);
  useEffect(() => {
    try { const r = JSON.parse(localStorage.getItem("store_recently_viewed") || "[]"); if (Array.isArray(r)) setRecent(r.filter((x) => x && x.id)); } catch { /* yoksay */ }
  }, []);

  // Admin akış blokları (hero/half/full dışındakiler) — sıralı
  const flowBlocks = blocks.filter((b) => ["product_slider", "text_block", "video_banner", "instashop"].includes(b.type) || (b.type === "full_banner" && b !== fullBannerBlock));
  const hasProductSlider = flowBlocks.some((b) => b.type === "product_slider");

  return (
    <div className="sf-page" data-testid="home-page">
      <Header announcement={rotatingBlock ? <RotatingText block={rotatingBlock} /> : null} announcementFirst={announcementFirst} />
      <main id="content" role="main" className="electro el-page">
        <h1 className="sr-only">{SITE_NAME} — Oto Servis ve Garaj Ekipmanları</h1>
        {loading ? <HomeSkeleton /> : (
          <>
            <HeroSlider slides={heroSlides} />
            <div className="container">
              <SmallBanners items={banner4} />
              {(special || feat.length) && (
                <div className="mb-5">
                  <div className="row">
                    {special && priceOf(special).hasDiscount && (
                      <div className="col-md-auto mb-6 mb-md-0"><SpecialOffer product={special} /></div>
                    )}
                    <div className="col">
                      <TabbedGrid tabs={[
                        { key: "featured", label: "Öne Çıkanlar", items: feat },
                        { key: "onsale", label: "İndirimdekiler", items: onSale },
                        { key: "toprated", label: "Çok Satanlar", items: best },
                      ]} />
                    </div>
                  </div>
                </div>
              )}
            </div>
            {roots.length > 0 && <Products414 roots={roots} />}
            <div className="container">
              {!hasProductSlider && <Bestsellers products={best} roots={roots} />}
              {flowBlocks.map((block) => {
                const vis = visibleOn(block);
                if (vis === null) return null;
                let el = null;
                if (block.type === "product_slider") el = <AdminProductSlider block={block} products={newest} />;
                else if (block.type === "text_block") el = <TextBlock block={block} />;
                else if (block.type === "video_banner") el = <VideoBanner block={block} />;
                else if (block.type === "instashop") el = <InstaShop block={block} />;
                else if (block.type === "full_banner") el = <FullBanner banner={{ image: block.images?.[0], link: block.links?.[0], title: block.title }} />;
                return el ? <div key={block.id} className={vis}>{el}</div> : null;
              })}
              <FullBanner banner={fullBanner} cheapest={cheapest} />
              {recent.length > 0 ? (
                <ProductCarouselSection title="Son Gezdikleriniz" products={recent} testId="recently-viewed" />
              ) : (
                <ProductCarouselSection title="Yeni Ürünler" products={newest.slice(0, 14)} ctaLink="/en-yeniler" testId="new-arrivals" />
              )}
            </div>
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}

/** Admin "Ürün Slider" bloğu — kaynak: manual / newest / discounted / favorites / category (slider-feed). */
function AdminProductSlider({ block, products }) {
  const selectedIds = block?.settings?.product_ids;
  const source = block?.settings?.source || (selectedIds?.length > 0 ? "manual" : "newest");
  const limit = block?.settings?.limit || 12;
  const [feed, setFeed] = useState(null);
  const catKey = JSON.stringify(block?.settings?.category_ids || []);
  useEffect(() => {
    if (source === "manual" || source === "newest") { setFeed(null); return undefined; }
    let alive = true;
    const cids = JSON.parse(catKey).join(",");
    axios.get(`${API}/products/slider-feed?source=${source}&limit=${limit}${cids ? `&category_ids=${encodeURIComponent(cids)}` : ""}`)
      .then((r) => { if (alive) setFeed(r.data?.products || []); })
      .catch(() => { if (alive) setFeed([]); });
    return () => { alive = false; };
  }, [source, limit, catKey]);
  let list;
  if (source !== "manual" && source !== "newest") list = feed || [];
  else if (selectedIds && selectedIds.length) list = selectedIds.map((id) => products.find((p) => p._id === id || p.id === id)).filter(Boolean);
  else list = products.slice(0, limit);
  const defaultCta = source === "discounted" ? "/sale" : "/en-yeniler";
  return (
    <ProductCarouselSection title={block?.title || (source === "discounted" ? "İndirimdeki Ürünler" : "Yeni Ürünler")}
      products={list} ctaLink={block?.settings?.cta_link || defaultCta} ctaLabel={block?.settings?.cta_label}
      testId="product-slider" bg={block?.settings?.bg_color} />
  );
}
