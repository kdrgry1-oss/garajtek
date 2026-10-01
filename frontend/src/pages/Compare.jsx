// Ürün karşılaştırma — Electro "compare" tablosu (istemci tarafı liste, en fazla 4 ürün).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";
import { useCart } from "../context/CartContext";
import { useCompare, removeCompare } from "../components/electro/compare";
import { optimizeImg, firstImage } from "../lib/img";
import { fmtPrice, priceOf, isSoldOut, needsVariantChoice, productHref } from "../components/electro/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const strip = (s) => String(s || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();

export default function Compare() {
  const list = useCompare();
  const { addItem } = useCart();
  const [products, setProducts] = useState({});
  const key = list.map((p) => p.id).join(",");
  useEffect(() => {
    let alive = true;
    list.forEach((s) => {
      if (products[s.id]) return;
      axios.get(`${API}/products/${s.slug || s.id}`).then((r) => { if (alive) setProducts((m) => ({ ...m, [s.id]: r.data })); }).catch(() => {});
    });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  const rows = list.map((s) => products[s.id] || { ...s, _loading: true });
  const attrNames = [...new Set(rows.flatMap((p) => (p.attributes || []).map((a) => a.name)).filter(Boolean))].slice(0, 12);
  const attrOf = (p, n) => ((p.attributes || []).find((a) => a.name === n) || {}).value || "—";

  return (
    <div className="sf-page" data-testid="compare-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb items={[{ label: "Karşılaştır" }]} />
        <div className="container">
          {rows.length === 0 ? (
            <div className="text-center my-10" data-testid="compare-empty">
              <i className="ec ec-compare font-size-50 text-gray-5 d-block mb-3" />
              <p className="font-size-16 text-gray-90">Karşılaştırma listeniz boş. Ürün kartlarındaki "Karşılaştır" bağlantısıyla ürün ekleyebilirsiniz.</p>
              <Link to="/" className="btn btn-primary-dark-w px-5">Alışverişe Başla</Link>
            </div>
          ) : (
            <div className="table-responsive table-bordered table-compare-list mb-10 border-0">
              <table className="table">
                <tbody>
                  <tr>
                    <th className="min-width-200">Ürün</th>
                    {rows.map((p) => (
                      <td key={p.id}>
                        <Link to={productHref(p)} className="product d-block">
                          <div className="product-compare-image"><div className="d-flex mb-3 el-compare-img">{!p._loading && <img className="img-fluid mx-auto" src={optimizeImg(firstImage(p), 300)} alt={p.name} loading="lazy" />}</div></div>
                          <h3 className="product-item__title text-blue font-weight-bold mb-3">{p.name}</h3>
                        </Link>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th>Fiyat</th>
                    {rows.map((p) => { const pv = priceOf(p); return <td key={p.id}><div className="product-price">{pv.hasDiscount && <del className="mr-2 text-gray-9">{fmtPrice(pv.list)}</del>}<span className={pv.hasDiscount ? "text-red" : ""}>{p._loading ? "…" : fmtPrice(pv.display)}</span></div></td>; })}
                  </tr>
                  <tr>
                    <th>Stok Durumu</th>
                    {rows.map((p) => <td key={p.id}><span>{p._loading ? "…" : isSoldOut(p) ? "Tükendi" : "Stokta"}</span></td>)}
                  </tr>
                  <tr>
                    <th>Açıklama</th>
                    {rows.map((p) => <td key={p.id}><p className="font-size-13 mb-0">{strip(p.short_description || p.description).slice(0, 220)}</p></td>)}
                  </tr>
                  {attrNames.map((n) => (
                    <tr key={n}><th>{n}</th>{rows.map((p) => <td key={p.id}>{attrOf(p, n)}</td>)}</tr>
                  ))}
                  <tr>
                    <th>Sepete Ekle</th>
                    {rows.map((p) => (
                      <td key={p.id}>
                        <div>
                          {needsVariantChoice(p) ? (
                            <Link to={productHref(p)} className="btn btn-soft-secondary mb-3 mb-md-0 font-weight-normal px-5 px-md-4 px-lg-5">Seçenekleri Gör</Link>
                          ) : (
                            <button type="button" disabled={p._loading || isSoldOut(p)} className="btn btn-soft-secondary mb-3 mb-md-0 font-weight-normal px-5 px-md-4 px-lg-5"
                              onClick={() => { const vs = (p.variants || []).filter((v) => v && v.id); addItem(p, vs.length === 1 ? vs[0] : null); toast.success("Ürün sepete eklendi"); }}>Sepete Ekle</button>
                          )}
                        </div>
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <th>Kaldır</th>
                    {rows.map((p) => <td key={p.id} className="text-center"><button type="button" className="btn btn-link text-gray-90 p-0" onClick={() => removeCompare(p.id)} aria-label="Listeden kaldır"><i className="fa fa-times" /></button></td>)}
                  </tr>
                </tbody>
              </table>
            </div>
          )}
        </div>
      </main>
      <Footer />
    </div>
  );
}
