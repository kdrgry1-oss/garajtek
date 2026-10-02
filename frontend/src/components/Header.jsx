// Electro header (HTML template v2.0 — home-v1 ve shop sayfaları başlığı), React ile.
//   • Topbar: hoş geldin metni + Sipariş Takibi / İletişim / Giriş-Hesabım
//   • Logo + hamburger (mobil off-canvas) + arama (kategori seçimli, canlı öneri) + ikonlar
//     (Karşılaştır, Favoriler, Sepet mini-dropdown + tutar)
//   • Ana sayfa: "Tüm Kategoriler" dikey mega menü AÇIK + yatay menü (admin Menü Yönetimi sekmeleri)
//   • Diğer sayfalar: logo satırında yatay menü + destek bloğu; altında sarı şerit
//     ("Kategoriler" açılır dikey menü + arama + ikonlar)
//   • Masaüstünde aşağı kaydırınca yapışkan (sticky) sarı şerit
// Veri kaynakları korunur: kategori ağacı (/categories), admin header menüsü (page-blocks/header-menu),
// SALE menüsü (/sale-menu), duyuru + sayaç barları (ana sayfa blokları), canlı arama (/products?search).
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { useFavorites } from "../context/FavoritesContext";
import CartDrawer, { MiniCartList } from "./CartDrawer";
import CountdownBar from "./CountdownBar";
import RotatingText from "./RotatingText";
import { optimizeImg, firstImage } from "../lib/img";
import { fetchHeaderMenu, fetchTopBars, fetchSaleMenu, getCachedMenu, getCachedBars, DEFAULT_MENU_TABS } from "../lib/headerMenu";
import { cartSummary } from "../lib/price";
import { useStoreInfo } from "../lib/storeInfo";
import { SITE_NAME } from "../lib/brand";
import useCategoryTree from "./electro/useCategoryTree";
import { fitTabs } from "../lib/navFit";
import CategoryIcon from "./electro/CategoryIcon";
import Logo from "./electro/Logo";
import { fmtPrice, priceOf } from "./electro/format";
import { useCompare } from "./electro/compare";
import { fetchSiteMenus, getCachedSiteMenus } from "../lib/siteMenus";
import { useSiteDesign, mergeContact } from "../lib/siteDesign";
import { usePreviewState } from "../lib/pagePreview";
import SmartLink, { linkHref } from "./pageblocks/_shared/SmartLink";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const MAX_VERTICAL = 14; // dikey menüde gösterilecek en fazla kök kategori (fazlası "Tüm Kategoriler" bağlantısında)

/* ------------------------------------------------------------------ */
/* Dikey "Tüm Kategoriler" menüsü (hs-mega-menu, 3 seviye)              */
/* ------------------------------------------------------------------ */
/** Elle tanımlı menü öğesini (label/link/children) kategori düğümü biçimine çevirir. */
function itemToNode(it) {
  return { id: it.id, name: it.label, slug: null, link: it.link || "/", style: it.style, icon: it.icon, image: it.image || "", children: (it.children || []).map(itemToNode) };
}
const nodeHref = (n) => n.link || `/${n.slug}`;

function VerticalMenu({ roots, open, variant, onNavigate, config, moreLabel, texts = {} }) {
  const [hover, setHover] = useState(null);
  const timer = useRef(null);
  const enter = (id) => { clearTimeout(timer.current); setHover(id); };
  const leave = () => { clearTimeout(timer.current); timer.current = setTimeout(() => setHover(null), 120); };
  const cfg = config || {};
  const manual = cfg.mode === "manual" && (cfg.items || []).length > 0;
  const maxRoots = Number(cfg.max_roots) || MAX_VERTICAL;
  const source = manual ? cfg.items.map(itemToNode) : roots;
  const list = source.slice(0, maxRoots);
  const quick = Array.isArray(cfg.quick) ? cfg.quick : [
    { id: "q1", label: "Günün Fırsatları", link: "/sale", style: "bold" },
    { id: "q2", label: "Yeni Ürünler", link: "/en-yeniler", style: "bold" },
  ];
  return (
    <div className={`collapse vertical-menu${variant === "shop" ? " v1" : ""}${open ? " show" : ""}`} data-testid="vertical-menu">
      <div className="card-body p-0">
        <nav className="js-mega-menu navbar navbar-expand-xl u-header__navbar u-header__navbar--no-space hs-menu-initialized hs-menu-vertical">
          <div className="collapse navbar-collapse u-header__navbar-collapse show">
            <ul className="navbar-nav u-header__navbar-nav">
              {quick.map((q) => (
                <li className="nav-item u-header__nav-item" data-event="hover" key={q.id || q.label}>
                  <Link to={q.link || "/"} className={`nav-link u-header__nav-link${q.style === "sale" ? " text-sale font-weight-bold" : q.style === "normal" ? "" : " font-weight-bold"}`} onClick={onNavigate}>{q.label}</Link>
                </li>
              ))}
              {list.map((cat) => {
                const kids = cat.children || [];
                if (!kids.length) {
                  return (
                    <li key={cat.id} className="nav-item u-header__nav-item" data-event="hover">
                      <Link to={nodeHref(cat)} className="nav-link u-header__nav-link" onClick={onNavigate}>
                        <span title={cat.name}><CategoryIcon cat={cat} className="el-cat-icon mr-2" /><span className="el-vm-label">{cat.name}</span></span>
                      </Link>
                    </li>
                  );
                }
                // Alt kategorileri 2 kolona böl: torunu olanlar başlık + liste, olmayanlar ilk kolonda liste
                const withKids = kids.filter((k) => (k.children || []).length);
                const leafs = kids.filter((k) => !(k.children || []).length);
                const cols = [];
                if (leafs.length) cols.push({ title: cat.name, to: nodeHref(cat), items: leafs, all: true });
                withKids.forEach((k) => cols.push({ title: k.name, to: nodeHref(k), items: k.children }));
                const half = Math.ceil(cols.length / 2);
                const colGroups = cols.length > 1 ? [cols.slice(0, half), cols.slice(half)] : [cols];
                const opened = hover === cat.id;
                return (
                  <li key={cat.id} className={`nav-item hs-has-mega-menu u-header__nav-item${opened ? " hs-mega-menu-opened" : ""}`}
                    data-event="hover" onMouseEnter={() => enter(cat.id)} onMouseLeave={leave}>
                    <Link to={nodeHref(cat)} className="nav-link u-header__nav-link u-header__nav-link-toggle" onClick={onNavigate} aria-haspopup="true" aria-expanded={opened}>
                      <span title={cat.name}><CategoryIcon cat={cat} className="el-cat-icon mr-2" /><span className="el-vm-label">{cat.name}</span></span>
                    </Link>
                    <div className="hs-mega-menu vmm-tfw u-header__sub-menu el-anim-up" data-testid={`vmenu-panel-${cat.slug}`}>
                      {(cat.image_url || cat.image) && (
                        <div className="vmm-bg">
                          <img className="img-fluid" src={optimizeImg(cat.image_url || cat.image, 500)} alt="" loading="lazy" />
                        </div>
                      )}
                      <div className="row u-header__mega-menu-wrapper">
                        {colGroups.map((group, gi) => (
                          <div className="col mb-3 mb-sm-0" key={gi}>
                            {group.map((col, ci) => (
                              <div key={col.title + ci}>
                                <Link to={col.to} className="u-header__sub-menu-title d-block" onClick={onNavigate}>{col.title}</Link>
                                <ul className="u-header__sub-menu-nav-group mb-3">
                                  {col.items.map((it) => (
                                    <li key={it.id}><Link className="nav-link u-header__sub-menu-nav-link" to={nodeHref(it)} onClick={onNavigate}>{it.name}</Link></li>
                                  ))}
                                  {col.all && (
                                    <li>
                                      <Link className="nav-link u-header__sub-menu-nav-link u-nav-divider border-top pt-2 flex-column align-items-start" to={col.to} onClick={onNavigate}>
                                        <div>{texts.all_prefix ?? "Tüm"} {cat.name}</div>
                                        {(texts.all_subtext ?? "Tüm ürünleri keşfedin") && <div className="u-nav-subtext font-size-11 text-gray-30" data-pd-field="site_departments_menu.all_subtext">{texts.all_subtext ?? "Tüm ürünleri keşfedin"}</div>}
                                      </Link>
                                    </li>
                                  )}
                                </ul>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </div>
                  </li>
                );
              })}
              {source.length > maxRoots && (
                <li className="nav-item u-header__nav-item" data-event="hover">
                  <Link to="/tum-urunler" className="nav-link u-header__nav-link font-weight-bold" onClick={onNavigate} data-pd-field="site_departments_menu.title">{cfg.more_label || moreLabel || "Tüm Kategoriler"}</Link>
                </li>
              )}
            </ul>
          </div>
        </nav>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Yatay menü — admin "Menü Yönetimi" sekmeleri (link / mega / SALE)    */
/* ------------------------------------------------------------------ */
function megaColumnsOf(tab) {
  return (tab?.columns || []).filter((c) => c && c.title).map((c) => ({
    title: c.title,
    link: c.link || "/",
    items: (c.items || []).filter((it) => it && it.name).map((it) => ({ name: it.name, link: it.link || "/" })),
  }));
}

// Yatay menüde aynı anda gösterilecek en fazla sekme (Electro home-v1 ≈ 5–7 kısa sekme).
// Fazlası — ve genişliğe sığmayanlar — "Daha Fazla" açılır menüsüne taşınır; etiketler asla
// alt satıra kırılmaz (nowrap). Panelde uzun menü kaydedilse bile başlık bozulmaz.
export const NAV_MAX_HOME = 7;
export const NAV_MAX_SHOP = 6;

function HorizontalNav({ tabs, saleMenu, freeShippingText, freeShippingLink = "/sayfa/kargo-ve-teslimat", showLast, maxVisible = NAV_MAX_HOME, moreLabel = "Daha Fazla" }) {
  const [open, setOpen] = useState(null);
  const timer = useRef(null);
  const enter = (id) => { clearTimeout(timer.current); setOpen(id); };
  const leave = () => { clearTimeout(timer.current); timer.current = setTimeout(() => setOpen(null), 150); };
  const close = () => setOpen(null);

  const promoText = showLast && freeShippingText ? freeShippingText : "";
  const sig = tabs.map((t) => `${t.id}|${t.label}|${t.style || ""}|${t.type || ""}`).join("§");
  const initial = () => ({ sig, visible: fitTabs(tabs, [], 0, 0, maxVisible), promo: !!promoText });
  const [layout, setLayout] = useState(initial);
  const tabsRef = useRef(tabs);
  tabsRef.current = tabs;
  const boxRef = useRef(null);
  const measureRef = useRef(null);

  useLayoutEffect(() => {
    const box = boxRef.current;
    const meas = measureRef.current;
    if (!box || !meas) return undefined;
    const compute = () => {
      const list = tabsRef.current;
      const avail = box.clientWidth;
      const items = Array.from(meas.children);
      if (!avail || !items.length) {
        setLayout((prev) => (prev.sig === sig ? prev : initial()));
        return;
      }
      const widths = items.slice(0, list.length).map((el) => el.getBoundingClientRect().width);
      const moreW = items[list.length] ? items[list.length].getBoundingClientRect().width : 0;
      const promoW = promoText && items[list.length + 1] ? items[list.length + 1].getBoundingClientRect().width : 0;
      let visible = fitTabs(list, widths, avail - promoW - 12, moreW, maxVisible);
      let promo = !!promoText;
      // Yer darsa önce kampanya metni (sağdaki "Ücretsiz Kargo…") gizlenir, sekmeler kalır.
      if (promo && visible.size < Math.min(list.length, maxVisible)) {
        const without = fitTabs(list, widths, avail - 12, moreW, maxVisible);
        if (without.size > visible.size) { visible = without; promo = false; }
      }
      setLayout((prev) => {
        const same = prev.sig === sig && prev.promo === promo && prev.visible.size === visible.size
          && [...visible].every((i) => prev.visible.has(i));
        return same ? prev : { sig, visible, promo };
      });
    };
    compute();
    let ro = null;
    if (typeof ResizeObserver !== "undefined") { ro = new ResizeObserver(() => compute()); ro.observe(box); }
    else window.addEventListener("resize", compute);
    let alive = true;
    try { document.fonts && document.fonts.ready.then(() => { if (alive) compute(); }); } catch { /* yoksay */ }
    return () => { alive = false; if (ro) ro.disconnect(); else window.removeEventListener("resize", compute); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, maxVisible, promoText]);

  const visible = layout.sig === sig ? layout.visible : initial().visible;
  const showPromo = !!promoText && (layout.sig === sig ? layout.promo : true);
  const overflow = tabs.filter((t, i) => !visible.has(i));

  const renderTab = (tab) => {
    const cls = `nav-link u-header__nav-link${tab.style === "sale" ? " text-sale" : ""}`;
    const cols = tab.type === "mega" ? megaColumnsOf(tab) : [];
    const hasSale = tab.style === "sale" && tab.type !== "mega" && saleMenu.length > 0;
    if (cols.length) {
      return (
        <li key={tab.id} className={`nav-item hs-has-mega-menu u-header__nav-item${open === tab.id ? " hs-mega-menu-opened" : ""}`}
          onMouseEnter={() => enter(tab.id)} onMouseLeave={leave}>
          <Link to={tab.link || "#"} className={`${cls} u-header__nav-link-toggle`} data-testid={`nav-tab-${tab.id}`} onClick={close}>{tab.label}</Link>
          <div className="hs-mega-menu w-100 u-header__sub-menu el-anim-up">
            <div className="row u-header__mega-menu-wrapper">
              {cols.map((col) => (
                <div className="col-md-3" key={col.title}>
                  <Link to={col.link} className="u-header__sub-menu-title d-block" onClick={close}>{col.title}</Link>
                  <ul className="u-header__sub-menu-nav-group mb-3">
                    {col.items.map((it) => (
                      <li key={it.name}><Link to={it.link} className="nav-link u-header__sub-menu-nav-link" onClick={close}>{it.name}</Link></li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </li>
      );
    }
    if (hasSale) {
      return (
        <li key={tab.id} className={`nav-item hs-has-sub-menu u-header__nav-item${open === tab.id ? " hs-sub-menu-opened" : ""}`}
          onMouseEnter={() => enter(tab.id)} onMouseLeave={leave} data-testid="sale-menu">
          <Link to={tab.link || "/sale"} className={`${cls} u-header__nav-link-toggle`} data-testid={`nav-tab-${tab.id}`} onClick={close}>{tab.label}</Link>
          <ul className="hs-sub-menu u-header__sub-menu el-anim-up" style={{ minWidth: 230 }}>
            {saleMenu.map((it) => (
              <li key={`${it.url}-${it.label}`}><Link className="nav-link u-header__sub-menu-nav-link" to={it.url} onClick={close}>{it.label}</Link></li>
            ))}
            <li><Link className="nav-link u-header__sub-menu-nav-link font-weight-bold" to={tab.link || "/sale"} onClick={close}>Tümünü Gör</Link></li>
          </ul>
        </li>
      );
    }
    return (
      <li key={tab.id} className="nav-item u-header__nav-item">
        <Link to={tab.link || "#"} className={cls} data-testid={`nav-tab-${tab.id}`}>{tab.label}</Link>
      </li>
    );
  };

  return (
    <nav className="js-mega-menu navbar navbar-expand-md u-header__navbar u-header__navbar--no-space hs-menu-initialized hs-menu-horizontal el-hnav" data-testid="horizontal-nav">
      <div className="collapse navbar-collapse u-header__navbar-collapse show" ref={boxRef}>
        <ul className="navbar-nav u-header__navbar-nav el-hnav__list">
          {tabs.map((tab, i) => (visible.has(i) ? renderTab(tab) : null))}
          {overflow.length > 0 && (
            <li className={`nav-item hs-has-mega-menu u-header__nav-item${open === "__more" ? " hs-mega-menu-opened" : ""}`}
              onMouseEnter={() => enter("__more")} onMouseLeave={leave} data-testid="nav-more">
              <button type="button" className="nav-link u-header__nav-link u-header__nav-link-toggle btn-link border-0 bg-transparent"
                aria-haspopup="true" aria-expanded={open === "__more"} onClick={() => setOpen((o) => (o === "__more" ? null : "__more"))}>
                {moreLabel}
              </button>
              <div className="hs-mega-menu w-100 u-header__sub-menu el-anim-up" data-testid="nav-more-panel">
                <div className="row u-header__mega-menu-wrapper">
                  {overflow.map((tab) => {
                    const cols = tab.type === "mega" ? megaColumnsOf(tab) : [];
                    return (
                      <div className="col-md-3" key={tab.id}>
                        <Link to={tab.link || "/"} className={`u-header__sub-menu-title d-block${tab.style === "sale" ? " text-sale" : ""}`} onClick={close}>{tab.label}</Link>
                        {cols.length > 0 && (
                          <ul className="u-header__sub-menu-nav-group mb-3">
                            {cols.slice(0, 8).map((c) => (
                              <li key={c.title}><Link to={c.link} className="nav-link u-header__sub-menu-nav-link" onClick={close}>{c.title}</Link></li>
                            ))}
                          </ul>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </li>
          )}
          {showPromo && (
            <li className="nav-item u-header__nav-last-item">
              <Link className="text-gray-90" to={freeShippingLink || "/"}>{promoText}</Link>
            </li>
          )}
        </ul>
        {/* Ölçüm kopyası (görünmez): her sekmenin, "Daha Fazla"nın ve kampanya metninin gerçek genişliği */}
        <ul className="navbar-nav u-header__navbar-nav el-hnav__measure" ref={measureRef} aria-hidden="true">
          {tabs.map((tab) => (
            <li key={tab.id} className="nav-item u-header__nav-item">
              <span className={`nav-link u-header__nav-link${tab.type === "mega" || (tab.style === "sale" && saleMenu.length) ? " u-header__nav-link-toggle" : ""}`}>{tab.label}</span>
            </li>
          ))}
          <li className="nav-item u-header__nav-item"><span className="nav-link u-header__nav-link u-header__nav-link-toggle">{moreLabel}</span></li>
          {promoText && <li className="nav-item u-header__nav-last-item"><span className="text-gray-90">{promoText}</span></li>}
        </ul>
      </div>
    </nav>
  );
}

/* ------------------------------------------------------------------ */
/* Arama (kategori seçimli + canlı öneri)                               */
/* ------------------------------------------------------------------ */
function SearchBar({ roots, variant = "home", inputId = "searchproduct-item", cfg = {} }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [results, setResults] = useState([]);
  const [total, setTotal] = useState(0);
  const [focus, setFocus] = useState(false);
  const boxRef = useRef(null);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2 || cfg.live_suggestions === false) { setResults([]); setTotal(0); return undefined; }
    let alive = true;
    const t = setTimeout(() => {
      axios.get(`${API}/products?search=${encodeURIComponent(term)}&limit=6${cat ? `&category=${encodeURIComponent(cat)}` : ""}`)
        .then((r) => { if (alive) { setResults(r.data?.products || []); setTotal(Number(r.data?.total || 0)); } })
        .catch(() => {});
    }, 280);
    return () => { alive = false; clearTimeout(t); };
  }, [q, cat, cfg.live_suggestions]);

  useEffect(() => {
    const onDoc = (e) => { if (boxRef.current && !boxRef.current.contains(e.target)) setFocus(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const submit = (e) => {
    e.preventDefault();
    const term = q.trim();
    if (!term) return;
    setFocus(false);
    navigate(`/arama?q=${encodeURIComponent(term)}${cat ? `&kategori=${encodeURIComponent(cat)}` : ""}`);
  };
  const allLabel = cfg.all_label || "Tüm Kategoriler";
  const catLabel = (roots.find((r) => r.slug === cat) || {}).name || allLabel;
  const showCats = cfg.show_category_select !== false;
  const btnCls = cfg.button_color === "dark" ? "btn-dark" : cfg.button_color === "primary" ? "btn-primary" : null;
  const shop = variant === "shop";
  return (
    <form className="js-focus-state position-relative" onSubmit={submit} ref={boxRef} role="search" data-testid="header-search">
      <label className="sr-only" htmlFor={inputId}>{cfg.button_label || "Ara"}</label>
      <div className="input-group">
        <input type="search" id={inputId} value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => setFocus(true)}
          className={shop
            ? "form-control py-2 pl-5 font-size-15 border-0 height-40 rounded-left-pill"
            : "form-control py-2 pl-5 font-size-15 border-right-0 height-40 border-width-2 rounded-left-pill border-primary"}
          placeholder={cfg.placeholder ?? "Ürün, marka veya kategori ara"} aria-label={cfg.placeholder || "Ürün ara"} autoComplete="off" data-testid="search-input" />
        <div className="input-group-append">
          {showCats && <div className="dropdown bootstrap-select js-select dropdown-select custom-search-categories-select el-native-select">
            <button type="button" tabIndex={-1} aria-hidden="true"
              className={shop
                ? "btn dropdown-toggle height-40 text-gray-60 font-weight-normal border-0 rounded-0 bg-white px-5 py-2"
                : "btn dropdown-toggle height-40 text-gray-60 font-weight-normal border-top border-bottom border-left-0 rounded-0 border-primary border-width-2 pl-0 pr-5 py-2"}>
              <div className="filter-option"><div className="filter-option-inner"><div className="filter-option-inner-inner">{catLabel}</div></div></div>
            </button>
            <select value={cat} onChange={(e) => setCat(e.target.value)} aria-label="Kategori seçin" data-testid="search-category">
              <option value="">{allLabel}</option>
              {roots.map((r) => <option key={r.id} value={r.slug}>{r.name}</option>)}
            </select>
          </div>}
          <button className={`btn ${btnCls && !shop ? btnCls : shop ? "btn-dark" : "btn-primary"} height-40 py-2 px-3 rounded-right-pill`} type="submit" aria-label={cfg.button_label || "Ara"} data-testid="search-btn">
            <span className="ec ec-search font-size-24" />
          </button>
        </div>
      </div>
      {focus && q.trim().length >= 2 && (
        <div className="el-search-results" data-testid="search-results">
          {results.length === 0 ? (
            <div className="px-4 py-3 font-size-14 text-gray-90">"{q}" için sonuç bulunamadı.</div>
          ) : (
            <>
              <ul className="list-unstyled mb-0">
                {results.map((p) => {
                  const pv = priceOf(p);
                  return (
                    <li key={p.id}>
                      <Link to={`/${p.slug || p.id}`} className="d-flex align-items-center px-3 py-2" onClick={() => { setFocus(false); setQ(""); }}>
                        <span className="el-search-thumb mr-3"><img src={optimizeImg(firstImage(p), 120) || "/placeholder.jpg"} alt="" loading="lazy" /></span>
                        <span className="flex-grow-1 font-size-14 text-blue font-weight-bold el-line-2">{p.name}</span>
                        <span className="ml-3 font-size-14 text-nowrap">
                          {pv.hasDiscount && <del className="font-size-12 text-gray-9 mr-1">{fmtPrice(pv.list)}</del>}
                          <span className={pv.hasDiscount ? "text-red" : "text-gray-90"}>{fmtPrice(pv.display)}</span>
                        </span>
                      </Link>
                    </li>
                  );
                })}
              </ul>
              <button type="submit" className="btn btn-block btn-soft-secondary rounded-0 font-size-13">
                {total > results.length ? `Tüm sonuçları gör (${total})` : "Tüm sonuçları gör"}
              </button>
            </>
          )}
        </div>
      )}
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Header ikonları + mini sepet                                         */
/* ------------------------------------------------------------------ */
function HeaderIcons({ variant, onMobileSearch, mobileSearchOpen, cfg = {} }) {
  const { items, itemCount, total, setIsOpen, removeItem, updateQuantity } = useCart();
  const { user } = useAuth();
  const { count: favCount } = useFavorites();
  const compare = useCompare();
  const [miniOpen, setMiniOpen] = useState(false);
  const ref = useRef(null);
  const location = useLocation();
  useEffect(() => { setMiniOpen(false); }, [location.pathname]);
  useEffect(() => {
    if (!miniOpen) return undefined;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setMiniOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [miniOpen]);
  const shop = variant === "shop";
  const sum = cartSummary(items, 0).effSum || total;
  const badge = cfg.badge_style === "dark" ? "bg-dark text-white" : cfg.badge_style === "white" ? "bg-white text-gray-90" : null;
  const badgeCls = shop
    ? `width-22 height-22 ${badge || "bg-dark text-white"} position-absolute d-flex align-items-center justify-content-center rounded-circle left-12 top-8 font-weight-bold font-size-12`
    : `bg-lg-down-black width-22 height-22 ${badge || "bg-primary"} position-absolute d-flex align-items-center justify-content-center rounded-circle left-12 top-8 font-weight-bold font-size-12`;
  const tx = cfg.texts || {};

  return (
    <ul className="d-flex list-unstyled mb-0 align-items-center">
      <li className="col d-xl-none px-2 px-sm-3 position-static">
        <button type="button" className="btn btn-link p-0 font-size-22 text-gray-90 text-lh-1 btn-text-secondary" aria-label="Ara" aria-expanded={mobileSearchOpen} onClick={onMobileSearch} data-testid="mobile-search-btn">
          <span className="ec ec-search" />
        </button>
      </li>
      {cfg.compare !== false && <li className="col d-none d-xl-block">
        <Link to="/karsilastir" className="text-gray-90 position-relative d-inline-block" title="Karşılaştır" aria-label="Karşılaştır">
          <i className="font-size-22 ec ec-compare" />
          {compare.length > 0 && <span className="el-icon-count">{compare.length}</span>}
        </Link>
      </li>}
      {cfg.wishlist !== false && <li className="col d-none d-xl-block">
        <Link to="/favoriler" className="text-gray-90 position-relative d-inline-block" title="Favoriler" aria-label="Favoriler" data-testid="favorites-btn">
          <i className="font-size-22 ec ec-favorites" />
          {favCount > 0 && <span className="el-icon-count">{favCount}</span>}
        </Link>
      </li>}
      {cfg.account_mobile !== false && <li className="col d-xl-none px-2 px-sm-3">
        <Link to={user ? "/hesabim" : "/giris"} className="text-gray-90" title={user ? "Hesabım" : "Giriş Yap"} aria-label="Hesap">
          <i className="font-size-22 ec ec-user" />
        </Link>
      </li>}
      {cfg.cart !== false && <>
      {/* Mobil/tablet: sepet paneli */}
      <li className="col pr-xl-0 px-2 px-sm-3 d-xl-none">
        <button type="button" onClick={() => setIsOpen(true)} className="btn btn-link p-0 text-gray-90 position-relative d-flex" aria-label="Sepet" data-testid="cart-btn-mobile">
          <i className="font-size-22 ec ec-shopping-bag" />
          <span className={badgeCls}>{itemCount}</span>
        </button>
      </li>
      {/* Masaüstü: mini sepet açılır menüsü */}
      <li className="col pr-xl-0 px-2 px-sm-3 d-none d-xl-block position-relative" ref={ref}>
        <button type="button" onClick={() => setMiniOpen((v) => !v)} className="btn btn-link p-0 text-gray-90 position-relative d-flex align-items-center" title="Sepet" aria-haspopup="true" aria-expanded={miniOpen} data-testid="cart-btn">
          <i className="font-size-22 ec ec-shopping-bag" />
          <span className={badgeCls}>{itemCount}</span>
          {cfg.cart_show_total !== false && <span className="d-none d-xl-block font-weight-bold font-size-16 text-gray-90 ml-3 text-nowrap" data-testid="header-cart-total">{fmtPrice(sum)}</span>}
        </button>
        {miniOpen && (
          <div className="cart-dropdown dropdown-menu dropdown-unfold show border-top border-top-primary mt-3 border-width-2 border-left-0 border-right-0 border-bottom-0 left-auto right-0 el-anim-up" data-testid="mini-cart">
            {items.length === 0 ? (
              <div className="px-3 py-4 text-center font-size-14">{tx.empty || "Sepetinizde ürün bulunmuyor."}</div>
            ) : (
              <>
                <MiniCartList items={items.slice(0, 5)} onNavigate={() => setMiniOpen(false)} removeItem={removeItem} updateQuantity={updateQuantity} compact />
                {items.length > 5 && <div className="px-3 pb-2 font-size-13 text-gray-90">+{items.length - 5} ürün daha</div>}
                <div className="flex-center-between px-4 pt-2">
                  <Link to="/sepet" className="btn btn-soft-secondary mb-3 font-weight-normal px-4 text-nowrap flex-grow-1" onClick={() => setMiniOpen(false)}>{tx.view_cart || "Sepeti Gör"}</Link>
                  <Link to="/odeme" className="btn btn-primary-dark-w mb-3 ml-2 px-4 text-nowrap flex-grow-1" onClick={() => setMiniOpen(false)}>{tx.checkout || "Ödemeye Geç"}</Link>
                </div>
              </>
            )}
          </div>
        )}
      </li>
      </>}
    </ul>
  );
}

/* ------------------------------------------------------------------ */
/* Mobil off-canvas menü (u-sidebar--left)                              */
/* ------------------------------------------------------------------ */
/** Elle tanımlı menü ağacı (hamburger / mobil menü "elle" modunda) — 3 seviyeye kadar. */
function ManualSidebarList({ items, onClose }) {
  const [expanded, setExpanded] = useState(null);
  return items.map((it) => {
    const kids = it.children || [];
    const cls = `u-header-collapse__nav-link${it.style === "bold" ? " font-weight-bold" : ""}${it.style === "sale" ? " text-sale font-weight-bold" : ""}`;
    const icon = it.icon ? <i className={`${it.icon} el-cat-icon mr-2`} aria-hidden="true" /> : null;
    if (!kids.length) return <li key={it.id}><Link className={cls} to={it.link || "/"} onClick={onClose}>{icon}{it.label}</Link></li>;
    const isOpen = expanded === it.id;
    return (
      <li key={it.id} className="u-has-submenu u-header-collapse__submenu">
        <button type="button" className={`${cls} u-header-collapse__nav-pointer btn btn-link p-0 text-left w-100${isOpen ? "" : " collapsed"}`}
          aria-expanded={isOpen} onClick={() => setExpanded(isOpen ? null : it.id)}>{icon}{it.label}</button>
        <div className={`collapse${isOpen ? " show" : ""}`}>
          <ul className="u-header-collapse__nav-list">
            <li><Link className="u-header-collapse__submenu-nav-link font-weight-bold" to={it.link || "/"} onClick={onClose}>Tümü: {it.label}</Link></li>
            {kids.map((k) => (
              <li key={k.id}>
                {(k.children || []).length ? (
                  <>
                    <Link className="u-header-sidebar__sub-menu-title d-block" to={k.link || "/"} onClick={onClose}>{k.label}</Link>
                    {k.children.map((g) => <Link key={g.id} className="u-header-collapse__submenu-nav-link d-block" to={g.link || "/"} onClick={onClose}>{g.label}</Link>)}
                  </>
                ) : <Link className="u-header-collapse__submenu-nav-link" to={k.link || "/"} onClick={onClose}>{k.label}</Link>}
              </li>
            ))}
          </ul>
        </div>
      </li>
    );
  });
}

function MobileSidebar({ open, onClose, roots, tabs, menus, highlight }) {
  const [expanded, setExpanded] = useState(null);
  const { user } = useAuth();
  const isSmall = typeof window !== "undefined" && window.innerWidth < 1200;
  const hb = menus?.hamburger || {};
  const mob = menus?.mobile || {};
  const useMobile = isSmall && mob.mode === "manual" && (mob.items || []).length > 0;
  const manualItems = useMobile ? mob.items : (hb.mode === "manual" && (hb.items || []).length ? hb.items : null);
  const quick = Array.isArray(hb.quick) ? hb.quick : [
    { id: "q1", label: "Günün Fırsatları", link: "/sale", style: "bold" },
    { id: "q2", label: "Yeni Ürünler", link: "/en-yeniler", style: "bold" },
  ];
  const quickLinks = new Set(quick.map((q) => (q.link || "").split("?")[0]));
  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => { document.body.style.overflow = prev; window.removeEventListener("keydown", onKey); };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <>
      <div className="el-backdrop" onClick={onClose} aria-hidden="true" />
      <aside id="sidebarHeader1" className={`u-sidebar u-sidebar--left el-anim-left${highlight ? " el-menu-hl" : ""}`} role="dialog" aria-modal="true" aria-label="Menü" data-testid="mobile-menu" data-menu-group={useMobile ? "mobile" : "hamburger"}>
        <div className="u-sidebar__scroller">
          <div className="u-sidebar__container">
            <div className="u-header-sidebar__footer-offset">
              <div className="position-absolute top-0 right-0 z-index-2 pt-4 pr-4 bg-white">
                <button type="button" className="close ml-auto" onClick={onClose} aria-label="Kapat">
                  <span aria-hidden="true"><i className="ec ec-close-remove text-gray-90 font-size-20" /></span>
                </button>
              </div>
              <div className="u-sidebar__body">
                <div id="headerSidebarContent" className="u-sidebar__content u-header-sidebar__content">
                  <Logo className="navbar-brand u-header__navbar-brand u-header__navbar-brand-center mb-3" onClick={onClose} />
                  <ul id="headerSidebarList" className="u-header-collapse__nav">
                    {manualItems ? <ManualSidebarList items={manualItems} onClose={onClose} /> : <>
                    {quick.map((q) => (
                      <li key={q.id || q.label}><Link className={`u-header-collapse__nav-link${q.style === "normal" ? "" : " font-weight-bold"}${q.style === "sale" ? " text-sale" : ""}`} to={q.link || "/"} onClick={onClose}>{q.label}</Link></li>
                    ))}
                    {tabs.filter((t) => {
                      const l = (t.link || "").split("?")[0];
                      // kategori ağacında zaten olan sekmeleri tekrar listeleme
                      return !quickLinks.has(l) && !roots.some((r) => `/${r.slug}` === l || r.name.toLocaleLowerCase("tr") === String(t.label || "").toLocaleLowerCase("tr"));
                    }).map((t) => (
                      <li key={`tab-${t.id}`}><Link className={`u-header-collapse__nav-link font-weight-bold${t.style === "sale" ? " text-sale" : ""}`} to={t.link || "/"} onClick={onClose}>{t.label}</Link></li>
                    ))}
                    {roots.map((cat) => {
                      const kids = cat.children || [];
                      if (!kids.length) {
                        return <li key={cat.id}><Link className="u-header-collapse__nav-link" to={`/${cat.slug}`} onClick={onClose}><CategoryIcon cat={cat} className="el-cat-icon mr-2" />{cat.name}</Link></li>;
                      }
                      const isOpen = expanded === cat.id;
                      return (
                        <li key={cat.id} className="u-has-submenu u-header-collapse__submenu">
                          <button type="button" className={`u-header-collapse__nav-link u-header-collapse__nav-pointer btn btn-link p-0 text-left w-100${isOpen ? "" : " collapsed"}`}
                            aria-expanded={isOpen} onClick={() => setExpanded(isOpen ? null : cat.id)}>
                            <CategoryIcon cat={cat} className="el-cat-icon mr-2" />{cat.name}
                          </button>
                          <div className={`collapse${isOpen ? " show" : ""}`}>
                            <ul className="u-header-collapse__nav-list">
                              <li><Link className="u-header-collapse__submenu-nav-link font-weight-bold" to={`/${cat.slug}`} onClick={onClose}>Tüm {cat.name}</Link></li>
                              {kids.map((k) => (
                                <li key={k.id}>
                                  {(k.children || []).length ? (
                                    <>
                                      <Link className="u-header-sidebar__sub-menu-title d-block" to={`/${k.slug}`} onClick={onClose}>{k.name}</Link>
                                      {k.children.map((g) => (
                                        <Link key={g.id} className="u-header-collapse__submenu-nav-link d-block" to={`/${g.slug}`} onClick={onClose}>{g.name}</Link>
                                      ))}
                                    </>
                                  ) : (
                                    <Link className="u-header-collapse__submenu-nav-link" to={`/${k.slug}`} onClick={onClose}>{k.name}</Link>
                                  )}
                                </li>
                              ))}
                            </ul>
                          </div>
                        </li>
                      );
                    })}
                    </>}
                  </ul>
                  {hb.show_account_links !== false && (
                  <ul className="list-unstyled border-top pt-3 mt-3 mb-0 font-size-14">
                    <li className="mb-2"><Link to={user ? "/hesabim" : "/giris"} className="text-gray-90" onClick={onClose}><i className="ec ec-user mr-2" />{user ? "Hesabım" : "Giriş Yap / Üye Ol"}</Link></li>
                    <li className="mb-2"><Link to="/favoriler" className="text-gray-90" onClick={onClose}><i className="ec ec-favorites mr-2" />Favorilerim</Link></li>
                    <li className="mb-2"><Link to="/siparis-takip" className="text-gray-90" onClick={onClose}><i className="ec ec-transport mr-2" />Sipariş Takibi</Link></li>
                    <li className="mb-2"><Link to="/iade-islemleri" className="text-gray-90" onClick={onClose}><i className="ec ec-returning mr-2" />İade Talebi</Link></li>
                    <li className="mb-2"><Link to="/sayfa/iletisim" className="text-gray-90" onClick={onClose}><i className="ec ec-map-pointer mr-2" />İletişim</Link></li>
                  </ul>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Header                                                              */
/* ------------------------------------------------------------------ */
export default function Header({ announcement, announcementFirst = false, announcementPosition, heroFirst = true, variant: forcedVariant }) {
  const location = useLocation();
  const { user } = useAuth();
  const info = useStoreInfo();
  const sd = useSiteDesign();
  const pv = usePreviewState();
  const tb = sd.site_topbar || {};
  const hd = sd.site_header || {};
  const dm = sd.site_departments_menu || {};
  const sm = sd.site_secondary_menu || {};
  const contact = mergeContact(sd.site_contact, info);
  const tree = useCategoryTree();
  const roots = tree.menuRoots || tree.roots;
  const isCheckout = location.pathname.includes("/odeme") || location.pathname.includes("/checkout");
  const isHomePath = location.pathname === "/" || (pv.active && pv.page === "home");
  // Sayfa Tasarımı › Header görünümü: v1 = logo+arama+ikonlar / dikey menü + ikincil menü (ana sayfa);
  // v2 = logo + ana menü + destek / ana renk şerit; v3 = geniş ana renk menü şeridi; v3_full_color = tamamı ana renk.
  const hv = hd.variant || "v1";
  const variant = forcedVariant || (isHomePath && hv !== "v2" ? "home" : "shop");
  const home = variant === "home";
  const v3 = home && (hv === "v3" || hv === "v3_full_color");

  // Duyuru + sayaç barları (Home kendi bloklarından geçirir; diğer sayfalar aynı bloğu kendisi çeker)
  const selfBars = announcement === undefined;
  const [bars, setBars] = useState(() => (selfBars ? getCachedBars() : null));
  useEffect(() => {
    if (!selfBars) return undefined;
    let alive = true;
    fetchTopBars(API).then((b) => { if (alive) setBars(b); }).catch(() => {});
    return () => { alive = false; };
  }, [selfBars]);
  const topAnnouncement = selfBars ? (bars?.rotating ? <RotatingText block={bars.rotating} /> : null) : announcement;
  const topFirst = selfBars ? !!bars?.announcementFirst : announcementFirst;
  // Dönen duyuru konumu (Sayfa Tasarımı › Dönen Duyuru › Konum): üst barın üstünde (vars.) / altında
  const annBelow = (selfBars ? bars?.rotating?.settings?.position : announcementPosition) === "below_topbar";

  // Admin menü sekmeleri (Tasarım › Menü Yönetimi) + SALE menüsü
  const [menuTabs, setMenuTabs] = useState(() => getCachedMenu() || DEFAULT_MENU_TABS);
  useEffect(() => {
    let alive = true;
    fetchHeaderMenu(API).then((tabs) => { if (alive && Array.isArray(tabs) && tabs.length) setMenuTabs(tabs); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  const tabs = menuTabs.filter((t) => t && t.active !== false && t.label);
  const [saleMenu, setSaleMenu] = useState([]);
  useEffect(() => {
    let alive = true;
    fetchSaleMenu(API).then((items) => { if (alive) setSaleMenu(items || []); }).catch(() => {});
    return () => { alive = false; };
  }, []);

  // Menü grupları (Menü Yönetimi): üst bar, sol menü, hamburger, orta menü sağ yazısı, mobil
  const [menus, setMenus] = useState(getCachedSiteMenus);
  useEffect(() => {
    let alive = true;
    fetchSiteMenus(API).then((m) => { if (alive && m) setMenus(m); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  // Panel "Sitede göster": ?menu-highlight=<grup> → ilgili alan vurgulanır (hamburger/mobil açılır)
  const hl = (() => { try { return new URLSearchParams(location.search).get("menu-highlight") || ""; } catch { return ""; } })();
  const hlCls = (g) => (hl === g ? " el-menu-hl" : "");

  const [mobileOpen, setMobileOpen] = useState(() => hl === "hamburger" || hl === "mobile");
  const [mobileSearch, setMobileSearch] = useState(false);
  const [deptOpen, setDeptOpen] = useState(false);
  const [stuck, setStuck] = useState(false);
  const headerRef = useRef(null);
  useEffect(() => { setMobileOpen(hl === "hamburger" || hl === "mobile"); setMobileSearch(false); setDeptOpen(false); }, [location.pathname, location.search, hl]);

  // Masaüstü yapışkan şerit: header görünümden çıkınca üstte sabit sarı şerit belirir.
  useEffect(() => {
    const onScroll = () => {
      const h = headerRef.current ? headerRef.current.offsetHeight : 0;
      setStuck(hd.sticky !== false && window.scrollY > h + 40);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [hd.sticky]);

  const welcome = tb.welcome_text || menus.topbar?.welcome || `${info.name && info.name !== "Mağaza" ? info.name : SITE_NAME}'e Hoş Geldiniz — Oto Servis & Garaj Ekipmanları`;
  const freeShip = sm.right_text ?? menus.center?.right_text ?? "";
  const freeShipLink = linkHref(sm.right_link) || menus.center?.right_link || "/sayfa/kargo-ve-teslimat";
  const topItems = (Array.isArray(tb.right_items) ? tb.right_items : []).filter((it) => it && !it._hidden && it.label)
    .map((it) => ({ id: it._id, label: it.label, link: linkHref(it.link) || "/", icon: it.icon?.icon || "", special: it.special, guest: it.guest_text }));
  const topCls = { gray: " bg-gray-13", primary: " bg-primary", transparent: " bg-transparent" }[tb.style] || "";
  const searchCfg = hd.search || {};
  const iconsCfg = hd.icons || {};
  const sup = hd.support || {};
  const deptTitle = home ? (dm.title || "Tüm Kategoriler") : (dm.title_shop || "Kategoriler");
  const deptIcon = dm.title_icon?.icon || "fa fa-list-ul";
  // Ana sayfada açık dikey menü şablondaki gibi slider'ın ÜSTÜNE biner; sayfa slider ile başlamıyorsa
  // ilk içerik bloğunu örtmesin diye kapalı başlar (tıklayınca açılır).
  const deptOpenByDefault = home ? dm.open_on_home !== false && heroFirst : !!dm.open_elsewhere;
  const navMax = home ? Number(sm.max_visible_home) || NAV_MAX_HOME : Number(sm.max_visible_shop) || NAV_MAX_SHOP;
  const closeMobile = () => setMobileOpen(false);

  // Ödeme sayfasında sade header (yalnız logo) — dikkat dağıtmaz.
  if (isCheckout) {
    return (
      <div className="electro el-header-wrap">
        <header id="header" className="u-header u-header-left-aligned-nav border-bottom">
          <div className="u-header__section">
            <div className="py-3">
              <div className="container d-flex align-items-center justify-content-between">
                <Logo className="navbar-brand u-header__navbar-brand" />
                <span className="font-size-14 text-gray-90"><i className="fas fa-lock mr-1" /> Güvenli Ödeme</span>
              </div>
            </div>
          </div>
        </header>
        <CartDrawer />
      </div>
    );
  }

  const bar = (
    <>
      {annBelow ? <CountdownBar /> : topFirst ? <>{topAnnouncement}<CountdownBar /></> : <><CountdownBar />{topAnnouncement}</>}
    </>
  );

  return (
    <>
      <div>{bar}</div>
      <div className="electro el-header-wrap" data-header-variant={variant}>
        <header id="header" className="u-header u-header-left-aligned-nav" ref={headerRef} data-testid="site-header">
          <div className="u-header__section">
            {/* Topbar */}
            {tb.enabled !== false && <div className={`u-header-topbar py-2 d-none d-${tb.hide_below === "lg" ? "lg" : "xl"}-block${topCls}${hlCls("topbar")}`} data-menu-group="topbar" data-testid="topbar">
              <div className="container">
                <div className="d-flex align-items-center">
                  <div className="topbar-left">
                    {tb.left_mode === "phone_email" ? (
                      <span className="text-gray-110 font-size-13">
                        {contact.phone && <a href={`tel:${contact.phone.replace(/\s/g, "")}`} className="text-gray-110 mr-3"><i className="ec ec-phone mr-1" />{contact.phone}</a>}
                        {contact.email && <a href={`mailto:${contact.email}`} className="text-gray-110"><i className="ec ec-mail mr-1" />{contact.email}</a>}
                      </span>
                    ) : (
                      <SmartLink link={tb.welcome_link} className="text-gray-110 font-size-13 hover-on-dark" field="site_topbar.welcome_text">{welcome}</SmartLink>
                    )}
                  </div>
                  <div className="topbar-right ml-auto">
                    <ul className="list-inline mb-0">
                      {topItems.map((it) => (
                        <li className="list-inline-item mr-0 u-header-topbar__nav-item u-header-topbar__nav-item-border" key={it.id || it.label} data-pd-field="site_topbar.right_items">
                          {it.special === "account" ? (user ? (
                            <Link to="/hesabim" className="u-header-topbar__nav-link" data-testid="topbar-account">{it.icon && <i className={`${it.icon} mr-1`} />} {it.label || "Hesabım"}{user.first_name ? ` (${user.first_name})` : ""}</Link>
                          ) : (
                            <Link to="/giris" className="u-header-topbar__nav-link" data-testid="topbar-login">{it.icon && <i className={`${it.icon} mr-1`} />} {it.guest || "Üye Ol veya Giriş Yap"}</Link>
                          )) : /^https?:/i.test(it.link || "") ? (
                            <a href={it.link} className="u-header-topbar__nav-link" target="_blank" rel="noopener noreferrer">{it.icon && <i className={`${it.icon} mr-1`} />} {it.label}</a>
                          ) : (
                            <Link to={it.link || "/"} className="u-header-topbar__nav-link">{it.icon && <i className={`${it.icon} mr-1`} />} {it.label}</Link>
                          )}
                        </li>
                      ))}
                      {tb.currency_text && (
                        <li className="list-inline-item mr-0 u-header-topbar__nav-item u-header-topbar__nav-item-border">
                          <span className="u-header-topbar__nav-link" data-pd-field="site_topbar.currency_text"><i className="ec ec-dollar mr-1" /> {tb.currency_text}</span>
                        </li>
                      )}
                    </ul>
                  </div>
                </div>
              </div>
            </div>}
            {annBelow && topAnnouncement}

            {/* Logo + arama/menü + ikonlar */}
            <div className={`py-2 ${home ? "py-xl-5" : "py-xl-4"}${hd.mobile_band_primary === false ? "" : " bg-primary-down-lg"}${hv === "v3_full_color" && home ? " bg-primary" : ""}`}>
              <div className="container my-0dot5 my-xl-0">
                <div className="row align-items-center">
                  <div className="col-auto">
                    <nav className="navbar navbar-expand u-header__navbar py-0 justify-content-xl-between max-width-270 min-width-270">
                      <Logo className="order-1 order-xl-0 navbar-brand u-header__navbar-brand u-header__navbar-brand-center" />
                      <button type="button" className="navbar-toggler d-block btn u-hamburger mr-3 mr-xl-0" aria-label="Menüyü aç" aria-expanded={mobileOpen} onClick={() => setMobileOpen(true)} data-testid="mobile-menu-btn">
                        <span className="u-hamburger__box"><span className="u-hamburger__inner" /></span>
                      </button>
                    </nav>
                  </div>
                  {home ? (
                    <div className="col d-none d-xl-block">
                      {searchCfg.enabled !== false && <SearchBar roots={roots} variant="home" cfg={searchCfg} />}
                    </div>
                  ) : (
                    <>
                      <div className={`col d-none d-xl-block el-hnav-col${hlCls("center")}`} data-menu-group="center">
                        {sm.enabled !== false && <HorizontalNav tabs={tabs} saleMenu={saleMenu} maxVisible={navMax} moreLabel={sm.more_label || "Daha Fazla"} />}
                      </div>
                      {sup.enabled !== false && (
                        <div className="d-none d-xl-block col-md-auto" data-testid="header-support">
                          <div className="d-flex">
                            <i className={`${sup.icon?.icon || "ec ec-support"} font-size-50 text-primary`} />
                            <div className="ml-2">
                              <div className="phone"><strong>{sup.label}</strong> {contact.phone ? <a href={`tel:${contact.phone.replace(/\s/g, "")}`} className="text-gray-90">{contact.phone}</a> : <Link to="/sayfa/iletisim" className="text-gray-90">{sup.fallback_text}</Link>}</div>
                              {contact.email && <div className="email">{sup.email_label} <a href={`mailto:${contact.email}`} className="text-gray-90">{contact.email}</a></div>}
                            </div>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                  <div className={`${home ? "" : "d-xl-none "}col col-xl-auto text-right text-xl-left pl-0 pl-xl-3 position-static`}>
                    <div className="d-inline-flex">
                      <HeaderIcons variant={variant} onMobileSearch={() => setMobileSearch((v) => !v)} mobileSearchOpen={mobileSearch} cfg={iconsCfg} />
                    </div>
                  </div>
                </div>
                {mobileSearch && (
                  <div className="d-xl-none pt-2 pb-1">
                    <SearchBar roots={roots} variant="shop" inputId="searchproduct-mobile" cfg={searchCfg} />
                  </div>
                )}
              </div>
            </div>

            {/* Ana sayfa: dikey menü (açık) + yatay menü */}
            {v3 ? (
              <div className={`d-none d-xl-block ${hv === "v3_full_color" ? "bg-primary border-top border-color-1" : "bg-primary"}`} data-testid="header-v3-band">
                <div className="container">
                  <div className={`el-hnav-col${hlCls("center")}`} data-menu-group="center">
                    {sm.enabled !== false && <HorizontalNav tabs={tabs} saleMenu={saleMenu} freeShippingText={freeShip} freeShippingLink={freeShipLink} showLast maxVisible={navMax} moreLabel={sm.more_label || "Daha Fazla"} />}
                  </div>
                </div>
              </div>
            ) : home ? (
              <div className="d-none d-xl-block container">
                <div className="row">
                  {dm.enabled !== false && <div className={`col-md-auto d-none d-xl-block${hlCls("departments")}`} data-menu-group="departments">
                    <div className="max-width-270 min-width-270" style={dm.width && Number(dm.width) !== 270 ? { maxWidth: Number(dm.width), minWidth: Number(dm.width) } : undefined}>
                      <div id="basicsAccordion">
                        <div className="card border-0">
                          <div className="card-header card-collapse border-0" id="basicsHeadingOne">
                            <button type="button" className="btn-link btn-remove-focus btn-block d-flex card-btn py-3 text-lh-1 px-4 shadow-none btn-primary rounded-top-lg border-0 font-weight-bold text-gray-90"
                              aria-expanded="true" onClick={() => setDeptOpen((v) => !v)} data-testid="all-departments-btn">
                              <span className="ml-0 text-gray-90 mr-2"><span className={deptIcon} /></span>
                              <span className="pl-1 text-gray-90" data-pd-field="site_departments_menu.title">{deptTitle}</span>
                            </button>
                          </div>
                          <VerticalMenu roots={roots} open={deptOpenByDefault ? !deptOpen : deptOpen} variant="home" config={menus.departments} moreLabel={dm.title} texts={dm} />
                        </div>
                      </div>
                    </div>
                  </div>}
                  <div className={`col el-hnav-col${hlCls("center")}`} data-menu-group="center">
                    {sm.enabled !== false && <HorizontalNav tabs={tabs} saleMenu={saleMenu} freeShippingText={freeShip} freeShippingLink={freeShipLink} showLast maxVisible={navMax} moreLabel={sm.more_label || "Daha Fazla"} />}
                  </div>
                </div>
              </div>
            ) : (
              <ShopBar dm={dm} roots={roots} deptOpen={deptOpen || hl === "departments" || (!!dm.open_elsewhere && !deptOpen)} setDeptOpen={setDeptOpen} config={menus.departments}
                highlight={hl === "departments"} title={deptTitle} enabled={dm.enabled !== false} searchCfg={searchCfg} iconsCfg={iconsCfg} />
            )}
          </div>
        </header>

        {/* Yapışkan şerit (masaüstü) */}
        {stuck && (
          <div className="el-sticky-bar d-none d-xl-block bg-primary el-anim-down" data-testid="sticky-header">
            <div className="container">
              <div className="row align-items-center min-height-50 py-1">
                <div className="col-auto"><Logo className="navbar-brand u-header__navbar-brand py-0" width={130} height={32} /></div>
                <div className="col">{searchCfg.enabled !== false && <SearchBar roots={roots} variant="shop" inputId="searchproduct-sticky" cfg={searchCfg} />}</div>
                <div className="col-md-auto">
                  <div className="d-flex"><HeaderIcons variant="shop" cfg={iconsCfg} /></div>
                </div>
              </div>
            </div>
          </div>
        )}

        <MobileSidebar open={mobileOpen} onClose={closeMobile} roots={roots} tabs={tabs} menus={menus} highlight={hl === "hamburger" || hl === "mobile"} />
        <CartDrawer />
      </div>
    </>
  );
}

/** İç sayfalar: sarı şerit — "Kategoriler" (açılır dikey menü) + arama + ikonlar. */
function ShopBar({ roots, deptOpen, setDeptOpen, config, highlight, title = "Kategoriler", enabled = true, searchCfg = {}, iconsCfg = {}, dm = {} }) {
  const ref = useRef(null);
  useEffect(() => {
    if (!deptOpen) return undefined;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setDeptOpen(false); };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [deptOpen, setDeptOpen]);
  return (
    <div className="d-none d-xl-block bg-primary">
      <div className="container">
        <div className="row align-items-stretch min-height-50">
          {enabled && <div className={`col-md-auto d-none d-xl-flex align-items-end${highlight ? " el-menu-hl" : ""}`} data-menu-group="departments">
            <div className="max-width-270 min-width-270" ref={ref}>
              <div id="basicsAccordion">
                <div className="card border-0 rounded-0">
                  <div className="card-header bg-primary rounded-0 card-collapse border-0" id="basicsHeadingOne">
                    <button type="button" className="btn-link btn-remove-focus btn-block d-flex card-btn py-3 text-lh-1 px-4 shadow-none btn-primary rounded-top-lg border-0 font-weight-bold text-gray-90"
                      aria-expanded={deptOpen} onClick={() => setDeptOpen((v) => !v)} data-testid="all-departments-btn">
                      <span className="pl-1 text-gray-90">{title}</span>
                      <span className="text-gray-90 ml-3"><span className="ec ec-arrow-down-search" /></span>
                    </button>
                  </div>
                  <VerticalMenu roots={roots} open={deptOpen} variant="shop" onNavigate={() => setDeptOpen(false)} config={config} moreLabel={dm.title} texts={dm} />
                </div>
              </div>
            </div>
          </div>}
          <div className="col align-self-center">
            {searchCfg.enabled !== false && <SearchBar roots={roots} variant="shop" inputId="searchProduct" cfg={searchCfg} />}
          </div>
          <div className="col-md-auto align-self-center">
            <div className="d-flex"><HeaderIcons variant="shop" cfg={iconsCfg} /></div>
          </div>
        </div>
      </div>
    </div>
  );
}
