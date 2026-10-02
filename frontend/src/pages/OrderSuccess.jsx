import { useState, useEffect } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import BankTransferInfo from "../components/BankTransferInfo";
import { useAuth } from "../context/AuthContext";
import { useStoreInfo } from "../lib/storeInfo";
import { fmtPrice } from "../components/electro/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Havale/EFT ödeme yöntemi mi? (sunucu farklı anahtarlar kullanabiliyor)
const _isBankTransfer = (pm) =>
  ["bank_transfer", "havale", "eft", "havale_eft", "banka_havale", "havale/eft"].includes(
    String(pm || "").toLowerCase()
  );

export default function OrderSuccess() {
  const { orderNumber } = useParams();
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth() || {};
  const store = useStoreInfo();
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(true);
  const [signupPwd, setSignupPwd] = useState("");
  const [signupBusy, setSignupBusy] = useState(false);
  const [signupDone, setSignupDone] = useState(false);
  const [codeSent, setCodeSent] = useState(false);   // A2.4: e-posta doğrulama kodu gönderildi mi
  const [signupCode, setSignupCode] = useState("");   // A2.4: kullanıcının girdiği 6 haneli kod
  const [codeEmail, setCodeEmail] = useState("");      // maskeli e-posta (kod nereye gitti)

  useEffect(() => {
    if (!orderNumber) {
      navigate("/");
      return;
    }
    let cancel = false;
    (async () => {
      try {
        const token = localStorage.getItem("token");
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const r = await axios.get(`${API}/orders/by-number/${orderNumber}`, { headers });
        if (!cancel) setOrder(r.data);
      } catch (_) {
        if (!cancel) setOrder(null);
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => { cancel = true; };
  }, [orderNumber, navigate]);
  if (loading) {
    return (
      <div className="sf-page">
        <Header />
        <main className="electro el-page"><div className="container py-10 text-center"><div className="el-skel mx-auto" style={{ height: 240, maxWidth: 720 }} /></div></main>
      </div>
    );
  }

  const ship = order?.shipping_address || {};
  const items = order?.items || [];
  const isCorporate = order?.billing_info?.is_corporate;
  const bank = _isBankTransfer(order?.payment_method);
  const steps = (bank ? [["fas fa-clock", "Ödeme Bekliyor"]] : []).concat([["fas fa-check", "Onaylandı"], ["fas fa-box", "Hazırlanıyor"], ["fas fa-truck", "Kargoda"], ["fas fa-home", "Teslim"]]);

  return (
    <div className="sf-page" data-testid="order-success-page">
      <Header />
      <main className="electro el-page">
        <div className="bg-gray-13 bg-md-transparent">
          <div className="container">
            <div className="my-md-3">
              <nav aria-label="breadcrumb">
                <ol className="breadcrumb mb-3 flex-nowrap flex-xl-wrap overflow-auto overflow-xl-visble">
                  <li className="breadcrumb-item flex-shrink-0 flex-xl-shrink-1"><Link to="/">Anasayfa</Link></li>
                  <li className="breadcrumb-item flex-shrink-0 flex-xl-shrink-1 active" aria-current="page">Sipariş Tamamlandı</li>
                </ol>
              </nav>
            </div>
          </div>
        </div>
        <div className="container">
          <div className="max-width-890 mx-auto mb-8">
            <button type="button" onClick={() => navigate(-1)} data-testid="ordersuccess-back-btn" aria-label="Geri Dön" className="btn btn-sm btn-soft-secondary rounded-pill mb-4">
              <i className="fas fa-chevron-left mr-1" /> Geri
            </button>
            <div className="text-center mb-6">
              <span className="d-inline-flex align-items-center justify-content-center bg-primary rounded-circle mb-4" style={{ width: 72, height: 72 }}>
                <i className="fas fa-check font-size-30 text-gray-90" />
              </span>
              <h1 className="font-size-26 font-weight-light mb-2" data-testid="order-success-title">Teşekkür Ederiz!</h1>
              <p className="text-gray-90 mb-0">Siparişiniz başarıyla alındı. Sipariş detayları ve takip bilgileri e-posta adresinize gönderildi.</p>
            </div>
            <div className="border border-color-1 rounded-lg text-center py-5 px-4 mb-6">
              <div className="font-size-13 text-gray-5 text-uppercase mb-1">Sipariş Numarası</div>
              <div className="font-size-26 font-weight-bold" data-testid="order-success-number">{orderNumber}</div>
              {order?.created_at && (
                <div className="font-size-13 text-gray-90 mt-1">
                  {new Date(order.created_at).toLocaleString("tr-TR", { day: "2-digit", month: "long", year: "numeric", hour: "2-digit", minute: "2-digit" })}
                </div>
              )}
            </div>
            <ol className="el-steps list-unstyled d-flex justify-content-between mb-8" aria-label="Sipariş durumu">
              {steps.map(([icon, label], i) => (
                <li key={label} className={`el-steps__item${i === 0 ? " active" : ""}`}>
                  <span className="el-steps__dot"><i className={icon} /></span>
                  <span className="el-steps__label">{label}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </main>
      {bank && <div className="max-w-3xl mx-auto px-4 mb-8"><BankTransferInfo orderNumber={orderNumber} /></div>}
      <main className="electro el-page" style={{ minHeight: 0 }}>
        <div className="container">
          <div className="max-width-890 mx-auto mb-8">
            {items.length > 0 && (
              <div className="mb-6">
                <div className="border-bottom border-color-1 mb-3"><h3 className="section-title mb-0 pb-2 font-size-18">Ürünler ({items.length})</h3></div>
                <table className="table mb-0">
                  <tbody>
                    {items.map((it, idx) => (
                      <tr key={idx}>
                        <td style={{ width: 80 }}><span className="el-mini-thumb"><img className="img-fluid" src={it.image} alt={it.name} /></span></td>
                        <td className="align-middle">
                          <div className="text-gray-90 font-weight-bold font-size-14">{it.name}</div>
                          <div className="font-size-12 text-gray-5">{[it.size && `Seçenek: ${it.size}`, it.color && `Renk: ${it.color}`, `Adet: ${it.quantity}`].filter(Boolean).join(" · ")}</div>
                        </td>
                        <td className="align-middle text-right text-nowrap">{fmtPrice(it.price * it.quantity)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="row">
              <div className="col-md-6 mb-6">
                <div className="border-bottom border-color-1 mb-3"><h3 className="section-title mb-0 pb-2 font-size-18">Teslimat Adresi</h3></div>
                <address className="font-size-14 text-gray-90 mb-0">
                  <strong>{ship.first_name} {ship.last_name}</strong><br />
                  {ship.address}<br />{ship.district} / {ship.city}<br />
                  <i className="fas fa-phone mr-1" /> {ship.phone}
                  {ship.email && <><br /><i className="fas fa-envelope mr-1" /> {ship.email}</>}
                </address>
                {isCorporate && (
                  <div className="mt-3 font-size-14">
                    <strong>Kurumsal Fatura</strong><br />{order.billing_info.company_name}<br />VKN: {order.billing_info.tax_number} · {order.billing_info.tax_office}
                    {order.billing_info.e_invoice_user && <div className="font-size-12 text-gray-5">e-Fatura mükellefi</div>}
                  </div>
                )}
              </div>
              <div className="col-md-6 mb-6">
                <div className="border-bottom border-color-1 mb-3"><h3 className="section-title mb-0 pb-2 font-size-18">Sipariş Özeti</h3></div>
                <table className="table mb-0 font-size-14">
                  <tbody>
                    <tr><th className="border-top-0">Ara Toplam</th><td className="border-top-0 text-right">{fmtPrice(order?.subtotal || 0)}</td></tr>
                    {Array.isArray(order?.discount_breakdown) && order.discount_breakdown.length > 0
                      ? order.discount_breakdown.map((d, i) => <tr key={i} className="text-green"><th>{d.label}{d.code ? ` · ${d.code}` : ""}</th><td className="text-right">-{fmtPrice(d.amount || 0)}</td></tr>)
                      : (order?.discount || 0) > 0 && <tr className="text-green"><th>İndirim{order.coupon_code ? ` · ${order.coupon_code}` : ""}</th><td className="text-right">-{fmtPrice(order.discount)}</td></tr>}
                    <tr><th>Kargo</th><td className="text-right">{(order?.shipping_cost || 0) === 0 ? "Ücretsiz" : fmtPrice(order.shipping_cost)}</td></tr>
                    <tr><th className="font-size-16">Toplam</th><td className="text-right font-size-16 font-weight-bold">{fmtPrice(order?.total || 0)}</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
            <div className="d-flex flex-wrap justify-content-center">
              <Link to="/hesabim" data-testid="view-orders-btn" className="btn btn-primary-dark-w px-5 rounded-pill mr-md-3 mb-3">Siparişlerimi Gör</Link>
              <Link to="/" data-testid="continue-shopping-btn" className="btn btn-soft-secondary px-5 rounded-pill mb-3">Alışverişe Devam Et</Link>
            </div>
        {/* Guest Signup CTA — Hesap oluştur ve siparişi takip et */}
        {!user && !signupDone && order && (
          <div className="mt-6 border-top pt-6" data-testid="guest-signup-cta">
            <div className="max-width-530 mx-auto bg-gray-1 rounded-lg px-4 px-md-6 py-6 text-center">
              <i className="ec ec-user font-size-30 mb-2 d-block" />
              <h3 className="font-size-20 font-weight-light mb-2">Hesap oluştur, takipte kal</h3>
              <p className="font-size-13 text-gray-90 mb-4">
                Bu siparişin <strong>otomatik hesabına bağlanır</strong>; iade & değişim, kargo durumu ve gelecek siparişlerin tek bir yerden yönetilir.
              </p>
              {!codeSent ? (
                <>
                  <div className="d-flex">
                    <input type="password" value={signupPwd} onChange={(e) => setSignupPwd(e.target.value)}
                      placeholder="En az 6 karakter şifre"
                      data-testid="guest-signup-password"
                      className="form-control rounded-left-pill" />
                    <button onClick={async () => {
                      if (signupPwd.length < 6) { toast.error("Şifre en az 6 karakter olmalı"); return; }
                      setSignupBusy(true);
                      try {
                        const r = await axios.post(`${API}/auth/guest-convert/send-code`, { order_id: orderNumber });
                        if (r.data.existing_account) {
                          toast(r.data.message || "Bu e-posta ile zaten hesabınız var. Lütfen giriş yapın.", { icon: "ℹ️" });
                          navigate("/giris");
                          return;
                        }
                        setCodeEmail(r.data.email_masked || "");
                        setCodeSent(true);
                        toast.success("Doğrulama kodu e-postanıza gönderildi.");
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "Kod gönderilemedi");
                      } finally { setSignupBusy(false); }
                    }} disabled={signupBusy}
                      data-testid="guest-signup-create-btn"
                      className="btn btn-dark rounded-right-pill px-4">
                      {signupBusy ? "..." : "Devam"}
                    </button>
                  </div>
                  <p className="font-size-12 text-gray-5 mt-3 mb-0">
                    E-posta: {order?.shipping_address?.email || "—"}
                  </p>
                </>
              ) : (
                <>
                  <p className="font-size-13 text-gray-90 mb-3">
                    <strong>{codeEmail}</strong> adresine gönderilen 6 haneli doğrulama kodunu girin.
                  </p>
                  <div className="d-flex">
                    <input type="text" inputMode="numeric" maxLength={6} value={signupCode}
                      onChange={(e) => setSignupCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                      placeholder="000000"
                      data-testid="guest-signup-code"
                      className="form-control rounded-left-pill text-center" />
                    <button onClick={async () => {
                      if (signupCode.length !== 6) { toast.error("6 haneli kodu girin"); return; }
                      setSignupBusy(true);
                      try {
                        const r = await axios.post(`${API}/auth/convert-guest-order`, { order_id: orderNumber, password: signupPwd, code: signupCode });
                        if (r.data.token) localStorage.setItem("token", r.data.token);
                        toast.success(r.data.existing_account ? "Hesabınıza bağlandı" : "Hesap oluşturuldu!");
                        setSignupDone(true);
                        if (refreshUser) await refreshUser();
                      } catch (e) {
                        toast.error(e?.response?.data?.detail || "İşlem başarısız");
                      } finally { setSignupBusy(false); }
                    }} disabled={signupBusy}
                      data-testid="guest-signup-verify-btn"
                      className="btn btn-dark rounded-right-pill px-4">
                      {signupBusy ? "..." : "Onayla"}
                    </button>
                  </div>
                  <button onClick={() => { setCodeSent(false); setSignupCode(""); }}
                    className="btn btn-link font-size-12 text-gray-90 mt-2">
                    Kodu almadınız mı? Tekrar deneyin
                  </button>
                </>
              )}
            </div>
          </div>
        )}

        {signupDone && (
          <div className="mt-6 border-top pt-6 text-center" data-testid="guest-signup-done">
            <i className="fas fa-check-circle font-size-30 text-green d-block mb-2" />
            <p className="mb-2">Hesabın hazır!</p>
            <Link to="/hesabim" className="btn btn-primary-dark-w rounded-pill px-5">Hesabıma Git</Link>
          </div>
        )}

        {/* Help */}
        {store.email && (
          <div className="text-center mt-6 pt-4 border-top">
            <p className="font-size-13 text-gray-90">
              Sorularınız için: <a href={`mailto:${store.email}`} className="text-blue">{store.email}</a>
            </p>
          </div>
        )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
