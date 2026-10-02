// Kategori / ürün listeleme — Electro "shop" sayfası (sol kenar çubuğu: kategori ağacı + filtreler +
// son ürünler; sağda önerilen ürünler karuseli, araç çubuğu (görünüm, sıralama, adet, sayfa),
// ızgara/liste görünümü ve sayfalama). Mevcut davranışlar korunur: URL tabanlı filtre/sıralama/sayfa,
// üyelere özel kategori yönlendirmesi, view_item_list analitiği, kategori SEO'su, facet önbelleği.
import { useState, useEffect, useRef, useMemo } from "react";
import { Link, useParams, useSearchParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { useAuth } from "../context/AuthContext";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ProductCard from "../components/ProductCard";
import Breadcrumb from "../components/electro/Breadcrumb";
import Carousel from "../components/electro/Carousel";
import RangeSlider from "../components/electro/RangeSlider";
import useCategoryTree, { findBySlug, categoryPath } from "../components/electro/useCategoryTree";
import { trackViewItemList } from "../lib/dataLayer";
import { applyRuntimeSeo, setCategorySeo } from "../lib/seo";
import { dedupeColorGroups } from "../lib/colorGroups";
import { sortLikeSize } from "../utils/sizeSort";
import { resolveColor, MULTI_GRADIENT } from "../lib/colorMap";
import { optimizeImg, firstImage } from "../lib/img";
import { fmtPrice, priceOf, productHref } from "../components/electro/format";
import SpecFacets, { specQueryString, specFilterCount } from "../components/catalog/SpecFacets";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const VIRTUAL = { "en-yeniler": "Yeni Ürünler", sale: "İndirimdeki Ürünler", "tum-urunler": "Tüm Ürünler", tumu: "Tüm Ürünler", all: "Tüm Ürünler" };

function pColor(p) {
  const v = (p.variants || []).find((x) => (x.color || "").trim());
  if (v) return v.color.trim();
  const a = (p.attributes || []).find((x) => ["web color", "renk", "color"].includes((x.name || "").trim().toLowerCase()));
  if (a && (a.value || "").trim()) return a.value.trim();
  return (p.color || "").trim();
}

const SORTS = [
  { label: "Varsayılan sıralama (en yeni)", value: "created_at:desc" },
  { label: "Popülerliğe göre", value: "popular:desc" },
  { label: "Fiyat: düşükten yükseğe", value: "price:asc" },
  { label: "Fiyat: yüksekten düşüğe", value: "price:desc" },
  { label: "İsim: A-Z", value: "name:asc" },
];
const PER_PAGE = [20, 40, 80];

function CheckRow({ id, label, count, checked, onChange, swatch }) {
  return (
    <div className="form-group d-flex align-items-center justify-content-between mb-2 pb-1">
      <div className="custom-control custom-checkbox">
        <input type="checkbox" className="custom-control-input" id={id} checked={checked} onChange={onChange} />
        <label className="custom-control-label" htmlFor={id}>
          {swatch && <span className="d-inline-block rounded-circle border mr-1 align-middle" style={{ width: 12, height: 12, ...swatch }} />}
          {label}{count != null && <span className="text-gray-25 font-size-12 font-weight-normal"> ({count})</span>}
        </label>
      </div>
    </div>
  );
}

function FacetGroup({ title, items, selected, onToggle, idPrefix, swatchOf }) {
  const [more, setMore] = useState(false);
  if (!items.length) return null;
  const shown = more ? items : items.slice(0, 5);
  return (
    <div className="border-bottom pb-4 mb-4">
      <h4 className="font-size-14 mb-3 font-weight-bold">{title}</h4>
      {shown.map(([val, count]) => (
        <CheckRow key={val} id={`${idPrefix}-${val}`} label={val} count={count} checked={selected.includes(val)} onChange={() => onToggle(val)} swatch={swatchOf ? swatchOf(val) : null} />
      ))}
      {items.length > 5 && (
        <button type="button" className="link link-collapse small font-size-13 text-gray-27 d-inline-flex mt-2 btn btn-link p-0" onClick={() => setMore((v) => !v)} aria-expanded={more}>
          <span className="link__icon text-gray-27 bg-white"><span className="link__icon-inner">{more ? "−" : "+"}</span></span>
          <span className="ml-1">{more ? "Daha az göster" : "Daha fazla göster"}</span>
        </button>
      )}
    </div>
  );
}

export default function Category() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const tree = useCategoryTree();

  // ÜYELERE ÖZEL kategori: misafir doğrudan URL ile gelirse giriş sayfasına yönlendir.
  useEffect(() => {
    if (!slug || slug === "all" || token) return undefined;
    let cancel = false;
    (async () => {
      try {
        const r = await axios.get(`${API}/categories/${encodeURIComponent(slug)}`);
        if (!cancel && (r.data?.members_only || r.data?.members_only_effective)) navigate(`/giris?redirect=${encodeURIComponent("/" + slug)}`, { replace: true });
      } catch { /* kategori yoksa normal akış */ }
    })();
    return () => { cancel = true; };
  }, [slug, token, navigate]);

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [pages, setPages] = useState(1);
  const [filterOpen, setFilterOpen] = useState(false);
  const [recommended, setRecommended] = useState([]);
  const [latest, setLatest] = useState([]);

  const page = parseInt(searchParams.get("page") || "1", 10) || 1;
  const setParam = (mut) => { const next = new URLSearchParams(searchParams); mut(next); setSearchParams(next); };
  const setPage = (n) => setParam((nx) => { if (!n || n <= 1) nx.delete("page"); else nx.set("page", String(n)); });

  const [view, setViewState] = useState(() => {
    try { const v = localStorage.getItem("el_plp_view"); if (["grid", "grid-ext", "list", "list-small"].includes(v)) return v; } catch { /* yoksay */ }
    return "grid";
  });
  const setView = (v) => { setViewState(v); try { localStorage.setItem("el_plp_view", v); } catch { /* yoksay */ } };

  const sort = searchParams.get("sort") || "created_at";
  const order = searchParams.get("order") || "desc";
  const minPrice = searchParams.get("min_price") || "";
  const maxPrice = searchParams.get("max_price") || "";
  const sizesParam = searchParams.get("sizes") || "";
  const colorsParam = searchParams.get("colors") || "";
  const brandParam = searchParams.get("brand") || "";
  const specQ = specQueryString(searchParams);   // teknik özellik süzgeçleri (?spec_*)
  const limit = PER_PAGE.includes(Number(searchParams.get("limit"))) ? Number(searchParams.get("limit")) : 20;

  // facet'ler (kategori başına önbellek)
  const [facets, setFacets] = useState({ sizes: [], colors: [], brands: [], min: 0, max: 0 });
  const facetCache = useRef(new Map());

  const prevSlug = useRef(slug);
  useEffect(() => {
    if (prevSlug.current !== slug) { prevSlug.current = slug; setPage(1); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      setLoading(true);
      try {
        let url = `${API}/products?page=${page}&limit=${limit}&sort=${sort}&order=${order}`;
        if (slug && slug !== "all") url += `&category=${slug}`;
        if (minPrice) url += `&min_price=${minPrice}`;
        if (maxPrice) url += `&max_price=${maxPrice}`;
        if (sizesParam) url += `&sizes=${encodeURIComponent(sizesParam)}`;
        if (colorsParam) url += `&colors=${encodeURIComponent(colorsParam)}`;
        if (brandParam) url += `&brand=${encodeURIComponent(brandParam)}`;
        url += specQ;
        const res = await axios.get(url, { signal: controller.signal });
        const fetched = res.data?.products || [];
        setProducts(fetched);
        setTotal(res.data?.total || 0);
        setPages(res.data?.pages || 1);
        if (fetched.length) { try { trackViewItemList({ products: fetched.slice(0, 24), listName: slug || "all" }); } catch (_) { /* silent */ } }
      } catch (err) {
        if (axios.isCancel?.(err) || err.name === "CanceledError") return;
        console.error(err);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    })();
    return () => controller.abort();
  }, [slug, sort, order, minPrice, maxPrice, sizesParam, colorsParam, brandParam, specQ, page, limit]);

  useEffect(() => { window.scrollTo({ top: 0, behavior: "auto" }); }, [page]);

  // facet + önerilen + son ürünler
  useEffect(() => {
    const key = slug || "all";
    let alive = true;
    const catQ = slug && slug !== "all" ? `&category=${slug}` : "";
    const apply = (f) => { if (alive) setFacets(f); };
    if (facetCache.current.has(key)) apply(facetCache.current.get(key));
    else {
      axios.get(`${API}/products?page=1&limit=120&sort=created_at&order=desc${catQ}`).then((res) => {
        const items = res.data?.products || [];
        const count = (arr) => { const m = new Map(); arr.forEach((v) => { if (v) m.set(v, (m.get(v) || 0) + 1); }); return [...m.entries()]; };
        let sizes = count(items.flatMap((p) => [...new Set((p.variants || []).map((v) => String(v.size || "").trim()).filter(Boolean))]));
        try { sizes = sortLikeSize(sizes, (x) => x[0]); } catch (_) { /* yoksay */ }
        const colors = count(items.map(pColor));
        const brands = count(items.map((p) => String(p.brand || "").trim())).sort((a, b) => a[0].localeCompare(b[0], "tr"));
        const prices = items.map((p) => priceOf(p).display).filter((n) => n > 0);
        const f = { sizes, colors, brands, min: prices.length ? Math.floor(Math.min(...prices)) : 0, max: prices.length ? Math.ceil(Math.max(...prices)) : 0 };
        facetCache.current.set(key, f);
        apply(f);
      }).catch(() => apply({ sizes: [], colors: [], brands: [], min: 0, max: 0 }));
    }
    axios.get(`${API}/products?limit=10&sort=popular${catQ}`).then((r) => { if (alive) setRecommended(r.data?.products || []); }).catch(() => {});
    axios.get(`${API}/products?limit=5&sort=created_at&order=desc`).then((r) => { if (alive) setLatest(r.data?.products || []); }).catch(() => {});
    return () => { alive = false; };
  }, [slug]);

  // taslak fiyat aralığı (kaydırıcı)
  const [range, setRange] = useState([0, 0]);
  useEffect(() => {
    setRange([minPrice ? Number(minPrice) : facets.min, maxPrice ? Number(maxPrice) : facets.max]);
  }, [facets.min, facets.max, minPrice, maxPrice]);

  const toggleList = (param, val) => setParam((nx) => {
    const cur = (nx.get(param) || "").split(",").filter(Boolean);
    const next = cur.includes(val) ? cur.filter((x) => x !== val) : [...cur, val];
    if (next.length) nx.set(param, next.join(",")); else nx.delete(param);
    nx.delete("page");
  });
  const applyPrice = () => setParam((nx) => {
    if (range[0] > facets.min) nx.set("min_price", String(range[0])); else nx.delete("min_price");
    if (range[1] < facets.max) nx.set("max_price", String(range[1])); else nx.delete("max_price");
    nx.delete("page");
  });
  const applySort = (value) => setParam((nx) => { const [sk, so] = value.split(":"); nx.set("sort", sk); nx.set("order", so); nx.delete("page"); });
  const clearAll = () => setSearchParams({});

  const current = findBySlug(tree, slug);
  const path = current ? categoryPath(tree, current) : [];
  const categoryName = current?.name || VIRTUAL[slug] || slug?.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Tüm Ürünler";
  const sidebarRoot = path[0] || null;

  useEffect(() => {
    if (slug && slug !== "all") {
      const controller = new AbortController();
      applyRuntimeSeo(`/kategori/${slug}`, () => { try { setCategorySeo(categoryName, slug, "", current?.description); } catch (_) { /* yoksay */ } }, { signal: controller.signal });
      return () => { controller.abort(); document.querySelectorAll('script[data-seo="runtime"]').forEach((el) => el.remove()); };
    }
    return undefined;
  }, [slug, categoryName, current?.description]);

  const activeCount = useMemo(() => {
    let n = 0;
    if (minPrice || maxPrice) n += 1;
    [sizesParam, colorsParam, brandParam].forEach((s) => { if (s) n += s.split(",").filter(Boolean).length; });
    n += specFilterCount(searchParams);
    return n;
  }, [minPrice, maxPrice, sizesParam, colorsParam, brandParam, searchParams]);

  const list = dedupeColorGroups(products);
  const from = total ? (page - 1) * limit + 1 : 0;
  const to = Math.min(total, page * limit);
  const showing = `${total} sonuçtan ${from}–${to} arası gösteriliyor`;
  const swatchOf = (c) => { const col = resolveColor(c); return col?.type === "solid" ? { backgroundColor: col.value } : col?.type === "multi" ? { background: MULTI_GRADIENT } : { background: "#e5e5e5" }; };

  const sidebar = (
    <>
      <div className="mb-6 border border-width-2 border-color-3 borders-radius-6" data-testid="category-sidebar">
        <ul id="sidebarNav" className="list-unstyled mb-0 sidebar-navbar view-all">
          <li><div className="dropdown-title">Kategorilere Göz At</div></li>
          {tree.roots.map((c) => {
            const open = sidebarRoot && sidebarRoot.id === c.id;
            const kids = c.children || [];
            return (
              <li key={c.id}>
                {kids.length ? (
                  <>
                    <Link className={`dropdown-toggle dropdown-toggle-collapse${open ? "" : " collapsed"}${current && current.id === c.id ? " font-weight-bold" : ""}`} to={`/${c.slug}`} aria-expanded={!!open}>
                      {c.name}{c.product_count != null && <span className="text-gray-25 font-size-12 font-weight-normal"> ({c.product_count})</span>}
                    </Link>
                    <div className={`collapse${open ? " show" : ""}`}>
                      <ul className="list-unstyled dropdown-list">
                        {kids.map((k) => (
                          <li key={k.id}>
                            <Link className={`dropdown-item${current && (current.id === k.id || path.some((x) => x.id === k.id)) ? " font-weight-bold" : ""}`} to={`/${k.slug}`}>
                              {k.name}{k.product_count != null && <span className="text-gray-25 font-size-12 font-weight-normal"> ({k.product_count})</span>}
                            </Link>
                            {(k.children || []).length > 0 && path.some((x) => x.id === k.id) && (
                              <ul className="list-unstyled dropdown-list pl-3">
                                {k.children.map((g) => (
                                  <li key={g.id}><Link className={`dropdown-item${current && current.id === g.id ? " font-weight-bold" : ""}`} to={`/${g.slug}`}>{g.name}</Link></li>
                                ))}
                              </ul>
                            )}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </>
                ) : (
                  <Link className={`dropdown-current${current && current.id === c.id ? " active font-weight-bold" : ""}`} to={`/${c.slug}`}>{c.name}</Link>
                )}
              </li>
            );
          })}
        </ul>
      </div>
      <div className="mb-6" data-testid="filter-panel">
        <div className="border-bottom border-color-1 mb-5 d-flex justify-content-between align-items-end">
          <h3 className="section-title section-title__sm mb-0 pb-2 font-size-18">Filtreler</h3>
          {activeCount > 0 && <button type="button" className="btn btn-link p-0 pb-2 font-size-13 text-gray-90" onClick={clearAll}>Temizle ({activeCount})</button>}
        </div>
        <FacetGroup title="Markalar" items={facets.brands} selected={brandParam.split(",").filter(Boolean)} onToggle={(v) => toggleList("brand", v)} idPrefix="brand" />
        <SpecFacets slug={slug} searchParams={searchParams} onToggle={toggleList} />
        <FacetGroup title="Seçenek / Ölçü" items={facets.sizes} selected={sizesParam.split(",").filter(Boolean)} onToggle={(v) => toggleList("sizes", v)} idPrefix="size" />
        <FacetGroup title="Renk" items={facets.colors} selected={colorsParam.split(",").filter(Boolean)} onToggle={(v) => toggleList("colors", v)} idPrefix="color" swatchOf={swatchOf} />
        {facets.max > facets.min && (
          <div className="range-slider">
            <h4 className="font-size-14 mb-3 font-weight-bold">Fiyat</h4>
            <RangeSlider min={facets.min} max={facets.max} step={1} value={range} onChange={setRange} />
            <div className="mt-1 text-gray-111 d-flex mb-4">
              <span className="mr-0dot5">Fiyat:&nbsp;</span>
              <span data-testid="price-min">{fmtPrice(range[0])}</span>
              <span className="mx-0dot5">&nbsp;—&nbsp;</span>
              <span data-testid="price-max">{fmtPrice(range[1])}</span>
            </div>
            <button type="button" className="btn px-4 btn-primary-dark-w py-2 rounded-lg" onClick={() => { applyPrice(); setFilterOpen(false); }} data-testid="apply-filters-btn">Filtrele</button>
          </div>
        )}
      </div>
      {latest.length > 0 && (
        <div className="mb-8">
          <div className="border-bottom border-color-1 mb-5">
            <h3 className="section-title section-title__sm mb-0 pb-2 font-size-18">Son Eklenenler</h3>
          </div>
          <ul className="list-unstyled">
            {latest.map((p) => {
              const pv = priceOf(p);
              return (
                <li className="mb-4" key={p.id}>
                  <div className="row">
                    <div className="col-auto">
                      <Link to={productHref(p)} className="d-block width-75"><img className="img-fluid" src={optimizeImg(firstImage(p), 150)} alt={p.name} loading="lazy" width="75" height="75" /></Link>
                    </div>
                    <div className="col">
                      <h3 className="text-lh-1dot2 font-size-14 mb-0"><Link to={productHref(p)}>{p.name}</Link></h3>
                      <div className="font-weight-bold">
                        {pv.hasDiscount && <del className="font-size-11 text-gray-9 d-block">{fmtPrice(pv.list)}</del>}
                        <ins className="font-size-15 text-red text-decoration-none d-block">{fmtPrice(pv.display)}</ins>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </>
  );

  const pageNums = (() => {
    const out = [];
    const s = Math.max(1, page - 2); const e = Math.min(pages, s + 4);
    for (let i = Math.max(1, e - 4); i <= e; i++) out.push(i);
    return out;
  })();

  return (
    <div className="sf-page" data-testid="category-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb testId="category-breadcrumb" items={path.length ? path.map((c) => ({ label: c.name, to: `/${c.slug}` })) : [{ label: categoryName }]} />
        <div className="container">
          <div className="row mb-8">
            <div className="d-none d-xl-block col-xl-3 col-wd-2gdot5">{sidebar}</div>
            <div className="col-xl-9 col-wd-9gdot5">
              {page === 1 && recommended.length > 0 && (
                <div className="mb-6 d-none d-xl-block" data-testid="recommended-products">
                  <div className="position-relative">
                    <div className="border-bottom border-color-1 mb-2">
                      <h3 className="d-inline-block section-title section-title__full mb-0 pb-2 font-size-22">Önerilen Ürünler</h3>
                    </div>
                    <Carousel perView={{ base: 2, md: 3, lg: 4, xl: 4, wd: 5 }} className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
                      arrows arrowsClassName="position-absolute top-0 font-size-17 u-slick__arrow-normal top-10" arrowLeftClassName="fa fa-angle-left right-1" arrowRightClassName="fa fa-angle-right right-0"
                      dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0">
                      {recommended.map((p, i) => (
                        <div className="js-slide products-group" key={p.id}>
                          <ProductCard product={p} listName="recommended" index={i} innerClassName="product-item__inner px-wd-4 p-2 p-md-3" wishlistLabel="Favori" />
                        </div>
                      ))}
                    </Carousel>
                  </div>
                </div>
              )}

              <div className="flex-center-between mb-3">
                <h1 className="font-size-25 mb-0">{categoryName}</h1>
                <p className="font-size-14 text-gray-90 mb-0" data-testid="result-count">{showing}</p>
              </div>
              <div className="bg-gray-1 flex-center-between borders-radius-9 py-1">
                <div className="d-xl-none">
                  <button type="button" className="btn btn-sm py-1 font-weight-normal" onClick={() => setFilterOpen(true)} data-testid="filter-btn">
                    <i className="fas fa-sliders-h" /> <span className="ml-1">Filtreler{activeCount ? ` (${activeCount})` : ""}</span>
                  </button>
                </div>
                <div className="px-3 d-none d-xl-block">
                  <ul className="nav nav-tab-shop" role="tablist">
                    {[["grid", "fa fa-th", "Izgara"], ["grid-ext", "fa fa-align-justify", "Geniş ızgara"], ["list", "fa fa-list", "Liste"], ["list-small", "fa fa-th-list", "Küçük liste"]].map(([v, icon, label]) => (
                      <li className="nav-item" key={v}>
                        <a href={`#${v}`} className={`nav-link${view === v ? " active" : ""}`} onClick={(e) => { e.preventDefault(); setView(v); }} aria-label={label} title={label} data-testid={`grid-${v}`}>
                          <div className="d-md-flex justify-content-md-center align-items-md-center"><i className={icon} /></div>
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="d-flex">
                  <div className="dropdown bootstrap-select js-select dropdown-select max-width-200 max-width-160-sm right-dropdown-0 px-2 px-xl-0 el-native-select">
                    <button type="button" tabIndex={-1} aria-hidden="true" className="btn dropdown-toggle btn-sm bg-white font-weight-normal py-2 border text-gray-20 bg-lg-down-transparent border-lg-down-0">
                      <div className="filter-option"><div className="filter-option-inner"><div className="filter-option-inner-inner">{(SORTS.find((s) => s.value === `${sort}:${order}`) || SORTS[0]).label}</div></div></div>
                    </button>
                    <select value={`${sort}:${order}`} onChange={(e) => applySort(e.target.value)} aria-label="Sıralama" data-testid="sort-btn">
                      {SORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                    </select>
                  </div>
                  <div className="ml-2 d-none d-xl-block dropdown bootstrap-select js-select dropdown-select max-width-120 el-native-select">
                    <button type="button" tabIndex={-1} aria-hidden="true" className="btn dropdown-toggle btn-sm bg-white font-weight-normal py-2 border text-gray-20 bg-lg-down-transparent border-lg-down-0">
                      <div className="filter-option"><div className="filter-option-inner"><div className="filter-option-inner-inner">{limit} Göster</div></div></div>
                    </button>
                    <select value={limit} onChange={(e) => setParam((nx) => { nx.set("limit", e.target.value); nx.delete("page"); })} aria-label="Sayfa başına ürün">
                      {PER_PAGE.map((n) => <option key={n} value={n}>{n} Göster</option>)}
                    </select>
                  </div>
                </div>
                <nav className="px-3 flex-horizontal-center text-gray-20 d-none d-xl-flex" aria-label="Sayfa">
                  <form className="min-width-50 mr-1" onSubmit={(e) => { e.preventDefault(); const v = parseInt(e.currentTarget.elements.p.value, 10); if (v >= 1 && v <= pages) setPage(v); }}>
                    <input name="p" key={page} size="2" min="1" max={pages} step="1" type="number" className="form-control text-center px-2 height-35" defaultValue={page} aria-label="Sayfa numarası" />
                  </form> / {pages}
                  <button type="button" className="btn btn-link text-gray-30 font-size-20 ml-2 p-0" onClick={() => page < pages && setPage(page + 1)} disabled={page >= pages} aria-label="Sonraki sayfa">→</button>
                </nav>
              </div>

              <div className="tab-content">
                <div className="tab-pane fade pt-2 show active" role="tabpanel">
                  {loading ? (
                    <ul className="row list-unstyled products-group no-gutters">
                      {[...Array(8)].map((_, i) => <li key={i} className="col-6 col-md-3 p-3"><div className="el-skel" style={{ height: 300 }} /></li>)}
                    </ul>
                  ) : list.length === 0 ? (
                    <div className="text-center py-10" data-testid="category-empty">
                      <p className="font-size-16 text-gray-90">Bu kategoride ürün bulunamadı.</p>
                      {activeCount > 0 && <button type="button" onClick={clearAll} className="btn btn-primary-dark-w px-5 rounded-pill">Filtreleri Temizle</button>}
                    </div>
                  ) : view === "list" || view === "list-small" ? (
                    <ul className={`d-block list-unstyled products-group ${view === "list" ? "prodcut-list-view" : "prodcut-list-view-small"}`}>
                      {list.map((p, i) => <ProductCard key={p.id} product={p} as="li" variant="listview" listName={slug || "all"} index={i} />)}
                    </ul>
                  ) : (
                    <ul className="row list-unstyled products-group no-gutters" data-testid="product-grid">
                      {list.map((p, i) => (
                        <ProductCard key={p.id} product={p} as="li" listName={slug || "all"} index={i} wishlistLabel="Favori"
                          className={view === "grid-ext" ? "col-6 col-md-4 col-wd-3 product-item__card" : "col-6 col-md-3 col-wd-2gdot4"} />
                      ))}
                    </ul>
                  )}
                </div>
              </div>

              {pages > 1 && (
                <nav className="d-md-flex justify-content-between align-items-center border-top pt-3" aria-label="Sayfalama">
                  <div className="text-center text-md-left mb-3 mb-md-0">{showing}</div>
                  <ul className="pagination mb-0 pagination-shop justify-content-center justify-content-md-start">
                    {page > 1 && <li className="page-item"><button type="button" className="page-link" onClick={() => setPage(page - 1)} aria-label="Önceki">‹</button></li>}
                    {pageNums.map((n) => (
                      <li className="page-item" key={n}><button type="button" className={`page-link${n === page ? " current" : ""}`} onClick={() => setPage(n)} aria-current={n === page ? "page" : undefined}>{n}</button></li>
                    ))}
                    {page < pages && <li className="page-item"><button type="button" className="page-link" onClick={() => setPage(page + 1)} aria-label="Sonraki">›</button></li>}
                  </ul>
                </nav>
              )}
            </div>
          </div>
        </div>

        {/* Mobil filtre paneli (off-canvas) */}
        {filterOpen && (
          <>
            <div className="el-backdrop" onClick={() => setFilterOpen(false)} aria-hidden="true" />
            <aside className="u-sidebar u-sidebar--left el-anim-left el-filter-sidebar" role="dialog" aria-modal="true" aria-label="Filtreler" data-testid="filter-drawer">
              <div className="u-sidebar__scroller">
                <div className="u-sidebar__container">
                  <div className="position-absolute top-0 right-0 z-index-2 pt-4 pr-4 bg-white">
                    <button type="button" className="close ml-auto" onClick={() => setFilterOpen(false)} aria-label="Kapat"><i className="ec ec-close-remove text-gray-90 font-size-20" /></button>
                  </div>
                  <div className="u-sidebar__body"><div className="u-sidebar__content pt-6">{sidebar}</div></div>
                </div>
              </div>
            </aside>
          </>
        )}
      </main>
      <Footer />
    </div>
  );
}
