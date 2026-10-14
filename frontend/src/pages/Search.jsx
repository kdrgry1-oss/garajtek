// Arama sonuçları — Electro shop ızgarası. ?q= arama terimi, ?kategori= (header'daki kategori seçimi).
import { useState, useEffect, useRef } from "react";
import { useSearchParams, Link, useNavigate } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ProductCard from "../components/ProductCard";
import Breadcrumb from "../components/electro/Breadcrumb";
import useCategoryTree, { findBySlug } from "../components/electro/useCategoryTree";
import { trackSearch } from "../lib/dataLayer";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PAGE_SIZE = 40;
const searchUrl = (query, cat, page) =>
  `${API}/products?search=${encodeURIComponent(query)}&limit=${PAGE_SIZE}&page=${page}${cat ? `&category=${encodeURIComponent(cat)}` : ""}`;

export default function Search() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const query = searchParams.get("q") || "";
  const cat = searchParams.get("kategori") || "";
  const tree = useCategoryTree();
  const catNode = findBySlug(tree, cat);
  const [products, setProducts] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  // Sayfalama: sunucu ilk 40 sonucu döndürür; kalanlar "Daha fazla göster" ile sonraki
  // sayfalardan eklenir (önceden yalnız ilk 40 gösteriliyordu, gerisine ulaşılamıyordu).
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loadingMore, setLoadingMore] = useState(false);
  const reqRef = useRef(0); // arama değişince eski "daha fazla" yanıtı listeye eklenmesin
  const [input, setInput] = useState(query);

  useEffect(() => { setInput(query); }, [query]);
  useEffect(() => {
    const reqId = ++reqRef.current;
    setPage(1); setPages(1); setLoadingMore(false);
    if (!query) { setProducts([]); setTotal(0); return undefined; }
    setLoading(true);
    try { trackSearch({ keyword: query }); } catch (_) { /* silent */ }
    axios.get(searchUrl(query, cat, 1))
      .then((res) => {
        if (reqRef.current !== reqId) return;
        setProducts(res.data?.products || []);
        setTotal(Number(res.data?.total || 0));
        setPages(Math.max(1, Number(res.data?.pages || 1)));
      })
      .catch((err) => console.error(err))
      .finally(() => { if (reqRef.current === reqId) setLoading(false); });
    return () => { reqRef.current += 1; };
  }, [query, cat]);

  const loadMore = () => {
    if (loadingMore || page >= pages) return;
    const reqId = reqRef.current;
    const next = page + 1;
    setLoadingMore(true);
    axios.get(searchUrl(query, cat, next))
      .then((res) => {
        if (reqRef.current !== reqId) return;
        const more = res.data?.products || [];
        // Aynı ürün iki sayfada gelirse (sıralama kayması) tekrar gösterme
        setProducts((prev) => {
          const seen = new Set(prev.map((p) => p.id));
          return prev.concat(more.filter((p) => !seen.has(p.id)));
        });
        setPage(next);
        if (res.data?.pages) setPages(Math.max(1, Number(res.data.pages)));
      })
      .catch((err) => console.error(err))
      .finally(() => { if (reqRef.current === reqId) setLoadingMore(false); });
  };

  return (
    <div className="sf-page" data-testid="search-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb items={[{ label: query ? `"${query}" için arama sonuçları` : "Arama" }]} />
        <div className="container">
          <div className="flex-center-between mb-3 flex-wrap">
            <h1 className="font-size-25 mb-0">{query ? <>"{query}" için sonuçlar{catNode ? <span className="font-size-16 text-gray-90"> — {catNode.name}</span> : null}</> : "Arama"}</h1>
            {query && !loading && <p className="font-size-14 text-gray-90 mb-0">{total || products.length} ürün bulundu</p>}
          </div>
          <form className="mb-4" onSubmit={(e) => { e.preventDefault(); if (input.trim()) navigate(`/arama?q=${encodeURIComponent(input.trim())}${cat ? `&kategori=${encodeURIComponent(cat)}` : ""}`); }}>
            <div className="input-group" style={{ maxWidth: 560 }}>
              <input type="search" className="form-control" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ürün ara…" aria-label="Ürün ara" />
              <div className="input-group-append"><button type="submit" className="btn btn-primary-dark-w px-4">Ara</button></div>
            </div>
          </form>
          {loading ? (
            <ul className="row list-unstyled products-group no-gutters">
              {[...Array(8)].map((_, i) => <li key={i} className="col-6 col-md-3 p-3"><div className="el-skel" style={{ height: 300 }} /></li>)}
            </ul>
          ) : products.length === 0 && query ? (
            <div className="text-center py-10">
              <p className="font-size-16 text-gray-90 mb-4">Aramanızla eşleşen ürün bulunamadı.</p>
              <Link to="/" className="btn btn-primary-dark-w px-5">Ana Sayfaya Dön</Link>
            </div>
          ) : (
            <>
              <ul className="row list-unstyled products-group no-gutters mb-8">
                {products.map((p, i) => (
                  <ProductCard key={p.id} product={p} as="li" listName="search" index={i} wishlistLabel="Favori" className="col-6 col-md-3 col-wd-2gdot4" />
                ))}
              </ul>
              {page < pages && products.length > 0 && (
                <div className="text-center mb-8">
                  <p className="font-size-13 text-gray-90 mb-2">{products.length} / {total} ürün gösteriliyor</p>
                  <button type="button" className="btn btn-soft-secondary px-5 rounded-pill" onClick={loadMore} disabled={loadingMore} data-testid="search-load-more">
                    {loadingMore ? "Yükleniyor..." : "Daha fazla göster"}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
