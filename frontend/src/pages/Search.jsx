// Arama sonuçları — Electro shop ızgarası. ?q= arama terimi, ?kategori= (header'daki kategori seçimi).
import { useState, useEffect } from "react";
import { useSearchParams, Link, useNavigate } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ProductCard from "../components/ProductCard";
import Breadcrumb from "../components/electro/Breadcrumb";
import useCategoryTree, { findBySlug } from "../components/electro/useCategoryTree";
import { trackSearch } from "../lib/dataLayer";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
  const [input, setInput] = useState(query);

  useEffect(() => { setInput(query); }, [query]);
  useEffect(() => {
    if (!query) { setProducts([]); setTotal(0); return undefined; }
    let alive = true;
    setLoading(true);
    try { trackSearch({ keyword: query }); } catch (_) { /* silent */ }
    axios.get(`${API}/products?search=${encodeURIComponent(query)}&limit=40${cat ? `&category=${encodeURIComponent(cat)}` : ""}`)
      .then((res) => { if (alive) { setProducts(res.data?.products || []); setTotal(Number(res.data?.total || 0)); } })
      .catch((err) => console.error(err))
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [query, cat]);

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
            <ul className="row list-unstyled products-group no-gutters mb-8">
              {products.map((p, i) => (
                <ProductCard key={p.id} product={p} as="li" listName="search" index={i} wishlistLabel="Favori" className="col-6 col-md-3 col-wd-2gdot4" />
              ))}
            </ul>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
