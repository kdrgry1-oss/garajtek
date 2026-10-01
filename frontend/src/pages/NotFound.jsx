// 404 — Electro "Error 404" sayfası.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ProductCard from "../components/ProductCard";
import Breadcrumb from "../components/electro/Breadcrumb";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function NotFound({ message }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [products, setProducts] = useState([]);
  useEffect(() => {
    document.title = "Sayfa bulunamadı (404)";
    let m = document.querySelector('meta[name="robots"]');
    const created = !m;
    if (!m) { m = document.createElement("meta"); m.name = "robots"; document.head.appendChild(m); }
    const prev = m.content;
    m.content = "noindex";
    axios.get(`${API}/products?limit=5&sort=popular`).then((r) => setProducts(r.data?.products || [])).catch(() => {});
    return () => { if (created) m.remove(); else m.content = prev; };
  }, []);
  return (
    <div className="sf-page" data-testid="not-found-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb items={[{ label: "Hata 404" }]} />
        <div className="container">
          <div className="mb-5 text-center pb-3 border-bottom border-color-1">
            <h1 className="font-size-sl-72 font-weight-light mb-3">404!</h1>
            <p className="text-gray-90 font-size-20 mb-0 font-weight-light">{message || "Aradığınız sayfa bulunamadı. Arama yapmayı deneyin ya da aşağıdaki ürünlere göz atın."}</p>
          </div>
          <div className="d-flex mb-6">
            <form className="d-block d-md-flex flex-horizontal-center w-100 w-lg-80 w-xl-50 mx-md-auto" onSubmit={(e) => { e.preventDefault(); if (q.trim()) navigate(`/arama?q=${encodeURIComponent(q.trim())}`); }}>
              <div className="mb-3 mb-md-0 col px-md-2 px-0">
                <input type="text" className="form-control" placeholder="Ürün ara…" aria-label="Ürün ara" value={q} onChange={(e) => setQ(e.target.value)} />
              </div>
              <div><button type="submit" className="btn btn-block btn-primary-dark-w px-5">Ara</button></div>
            </form>
          </div>
          {products.length > 0 && (
            <div className="mb-8">
              <div className="d-flex border-bottom border-color-1 mr-md-2 mb-4">
                <h3 className="section-title section-title__full mb-0 pb-2 font-size-22">Öne Çıkan Ürünler</h3>
              </div>
              <ul className="row list-unstyled products-group no-gutters">
                {products.map((p) => <ProductCard key={p.id} product={p} as="li" className="col-6 col-md-4 col-xl" />)}
              </ul>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
