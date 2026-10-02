// Hızlı Sipariş — stok kodu / barkod + adet listesi yapıştır, tek istekte çöz, tek tıkla sepete ekle.
// (Sözleşme 7.2: belirlenen satış senaryolarında 100 ürünün tek işlemle sepete eklenmesi — set dışı
// senaryolar için; setler "Seti Sepete Ekle" ile aynı şekilde tek işlemle eklenir.)
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";
import { useCart } from "../context/CartContext";
import { optimizeImg } from "../lib/img";
import { fmtPrice, priceOf } from "../components/electro/format";
import { parseQuickLines } from "../lib/quickOrder";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const EXAMPLE = "GT-DEMO-007, 2\nGT-DEMO-016 1\nGT-DEMO-019;3";

export default function QuickOrder() {
  const { addMany } = useCart();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);

  const resolve = async () => {
    const lines = parseQuickLines(text);
    if (!lines.length) { toast.error("En az bir stok kodu / barkod girin"); return; }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/storefront/quick-order`, { lines });
      setRes(r.data);
    } catch {
      toast.error("Liste çözümlenemedi");
    } finally { setBusy(false); }
  };

  const addAll = () => {
    const rows = (res?.found || []).filter((f) => f.stock > 0)
      .map((f) => ({ product: f.product, variant: f.variant, quantity: Math.min(f.quantity, f.stock) }));
    const n = addMany(rows);
    if (n) {
      toast.success(`${n} kalem sepete eklendi`);
      navigate("/sepet");
    }
  };

  const okCount = (res?.found || []).filter((f) => f.stock > 0).length;
  return (
    <div className="sf-page" data-testid="quick-order-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb items={[{ label: "Hızlı Sipariş" }]} />
        <div className="container mb-10">
          <h1 className="font-size-26 mb-2">Hızlı Sipariş</h1>
          <p className="text-gray-90 mb-4">Stok kodu veya barkod ile birden çok ürünü tek seferde sepete ekleyin. Her satıra bir ürün yazın: <code>STOKKODU, ADET</code></p>
          <div className="row">
            <div className="col-lg-5 mb-4">
              <textarea className="form-control" rows={12} value={text} onChange={(e) => setText(e.target.value)}
                placeholder={EXAMPLE} data-testid="quick-order-input" />
              <div className="d-flex mt-3">
                <button type="button" className="btn btn-primary-dark-w px-5" onClick={resolve} disabled={busy} data-testid="quick-order-resolve">
                  {busy ? "Kontrol ediliyor…" : "Listeyi Kontrol Et"}
                </button>
                <button type="button" className="btn btn-link text-gray-90 ml-2" onClick={() => setText(EXAMPLE)}>Örnek doldur</button>
              </div>
            </div>
            <div className="col-lg-7">
              {res && (
                <div data-testid="quick-order-result">
                  {res.missing?.length > 0 && (
                    <div className="gt-set-notice mb-3">Bulunamayan kod(lar): <strong>{res.missing.join(", ")}</strong></div>
                  )}
                  <table className="table">
                    <thead><tr><th>Ürün</th><th className="text-center">Adet</th><th className="text-right">Tutar</th></tr></thead>
                    <tbody>
                      {(res.found || []).map((f) => {
                        const pv = priceOf(f.product);
                        const unit = pv.display + (Number(f.variant?.price_diff) || 0);
                        return (
                          <tr key={`${f.code}-${f.product.id}`} data-testid={`quick-row-${f.code}`}>
                            <td>
                              <div className="d-flex align-items-center">
                                <img src={optimizeImg(f.product.images?.[0], 100) || "/placeholder.jpg"} alt="" width="48" height="48" className="mr-2" style={{ objectFit: "contain" }} />
                                <div>
                                  <Link to={`/${f.product.slug || f.product.id}`} className="text-gray-90">{f.product.name}</Link>
                                  <div className="font-size-12 text-gray-5">{f.code}{f.variant?.size ? ` · ${f.variant.size}` : ""} · {f.stock > 0
                                    ? <span className="text-green">Stokta ({f.stock})</span>
                                    : <span className="text-red">Bu ürün stokta bulunmamaktadır</span>}</div>
                                </div>
                              </div>
                            </td>
                            <td className="text-center">{f.stock > 0 ? Math.min(f.quantity, f.stock) : 0}{f.stock > 0 && f.quantity > f.stock ? <div className="font-size-11 text-red">en fazla {f.stock}</div> : null}</td>
                            <td className="text-right">{fmtPrice(unit * (f.stock > 0 ? Math.min(f.quantity, f.stock) : 0))}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  <button type="button" className="btn btn-primary-dark-w px-5" disabled={!okCount} onClick={addAll} data-testid="quick-order-add-all">
                    <i className="ec ec-add-to-cart mr-2" />{okCount} ürünü sepete ekle
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
