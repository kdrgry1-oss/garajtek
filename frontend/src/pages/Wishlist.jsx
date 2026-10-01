// Favorilerim — Electro "wishlist" tablosu. Üye: /favorites (sunucu); misafir: yerel favori id'leri.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";
import { useAuth } from "../context/AuthContext";
import { useFavorites } from "../context/FavoritesContext";
import { useCart } from "../context/CartContext";
import { optimizeImg, firstImage } from "../lib/img";
import { fmtPrice, priceOf, isSoldOut, needsVariantChoice, productHref } from "../components/electro/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Wishlist() {
  const { token } = useAuth();
  const { isFavorite, toggleFavorite, count } = useFavorites();
  const { addItem } = useCart();
  const [products, setProducts] = useState(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (token) {
          const r = await axios.get(`${API}/favorites`, { headers: { Authorization: `Bearer ${token}` } });
          if (alive) setProducts(r.data?.favorites || []);
          return;
        }
        let ids = [];
        try { ids = JSON.parse(localStorage.getItem("store_favorites") || "[]"); } catch { ids = []; }
        const list = await Promise.all((Array.isArray(ids) ? ids : []).slice(0, 40).map((id) => axios.get(`${API}/products/${id}`).then((r) => r.data).catch(() => null)));
        if (alive) setProducts(list.filter(Boolean));
      } catch {
        if (alive) setProducts([]);
      }
    })();
    return () => { alive = false; };
  }, [token, count]);

  const visible = (products || []).filter((p) => isFavorite(p.id));
  return (
    <div className="sf-page" data-testid="wishlist-page">
      <Header />
      <main id="content" role="main" className="electro el-page cart-page">
        <Breadcrumb items={[{ label: "Favorilerim" }]} />
        <div className="container">
          <div className="my-6"><h1 className="text-center">Favori Ürünlerim</h1></div>
          {products === null ? (
            <div className="el-skel mb-16" style={{ height: 240 }} />
          ) : visible.length === 0 ? (
            <div className="text-center mb-16" data-testid="favorites-empty">
              <i className="ec ec-favorites font-size-50 text-gray-5 d-block mb-3" />
              <p className="font-size-16 text-gray-90">Favori listeniz boş.</p>
              <Link to="/" className="btn btn-primary-dark-w px-5">Alışverişe Başla</Link>
            </div>
          ) : (
            <div className="mb-16 wishlist-table">
              <div className="table-responsive">
                <table className="table" cellSpacing="0">
                  <thead>
                    <tr>
                      <th className="product-remove">&nbsp;</th>
                      <th className="product-thumbnail">&nbsp;</th>
                      <th className="product-name">Ürün</th>
                      <th className="product-price">Birim Fiyat</th>
                      <th className="product-Stock w-lg-15">Stok Durumu</th>
                      <th className="product-subtotal min-width-200-md-lg">&nbsp;</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((p) => {
                      const pv = priceOf(p);
                      const sold = isSoldOut(p);
                      return (
                        <tr key={p.id}>
                          <td className="text-center">
                            <button type="button" className="btn btn-link text-gray-32 font-size-26 p-0" onClick={() => toggleFavorite(p)} aria-label="Favorilerden çıkar">×</button>
                          </td>
                          <td className="d-none d-md-table-cell">
                            <Link to={productHref(p)}><img className="img-fluid max-width-100 p-1 border border-color-1" src={optimizeImg(firstImage(p), 200)} alt={p.name} loading="lazy" width="100" height="100" /></Link>
                          </td>
                          <td data-title="Ürün"><Link to={productHref(p)} className="text-gray-90">{p.name}</Link></td>
                          <td data-title="Birim Fiyat">
                            {pv.hasDiscount && <del className="text-gray-9 font-size-13 mr-2">{fmtPrice(pv.list)}</del>}
                            <span className={pv.hasDiscount ? "text-red" : ""}>{fmtPrice(pv.display)}</span>
                          </td>
                          <td data-title="Stok Durumu"><span>{sold ? "Tükendi" : "Stokta"}</span></td>
                          <td>
                            {needsVariantChoice(p) ? (
                              <Link to={productHref(p)} className="btn btn-soft-secondary mb-3 mb-md-0 font-weight-normal px-5 px-md-4 px-lg-5 w-100 w-md-auto">Seçenekleri Gör</Link>
                            ) : (
                              <button type="button" disabled={sold} className="btn btn-soft-secondary mb-3 mb-md-0 font-weight-normal px-5 px-md-4 px-lg-5 w-100 w-md-auto"
                                onClick={() => { const vs = (p.variants || []).filter((v) => v && v.id); addItem(p, vs.length === 1 ? vs[0] : null); toast.success("Ürün sepete eklendi"); }}>
                                Sepete Ekle
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
