import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Package, Truck, CheckCircle, Clock, MapPin, ExternalLink } from "lucide-react";
import axios from "axios";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function TrackOrder() {
  const { trackingCode: paramCode } = useParams();
  const [searchParams] = useSearchParams();
  const initialCode = paramCode || searchParams.get('code') || '';
  
  const [trackingCode, setTrackingCode] = useState(initialCode);
  const [order, setOrder] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e) => {
    e?.preventDefault();
    if (!trackingCode.trim()) return;
    
    setLoading(true);
    setError(null);
    setSearched(true);
    
    try {
      const res = await axios.get(`${API}/track/${trackingCode.trim()}`);
      setOrder(res.data);
    } catch (err) {
      setError("Sipariş bulunamadı. Lütfen sipariş numaranızı veya kargo takip numaranızı kontrol edin.");
      setOrder(null);
    } finally {
      setLoading(false);
    }
  };

  // O15: Otomatik arama useState ile YANLIŞ yapılmıştı (render sırasında setState, StrictMode'da
  // çift tetik, initialCode değişince tekrar ÇALIŞMIYOR). Doğrusu useEffect.
  useEffect(() => {
    if (initialCode) {
      handleSearch();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialCode]);

  const getStatusIcon = (status, completed) => {
    const iconClass = completed ? "text-green-600" : "text-gray-300";
    switch (status) {
      case 'placed':
        return <Package className={iconClass} size={24} />;
      case 'confirmed':
        return <CheckCircle className={iconClass} size={24} />;
      case 'processing':
        return <Clock className={iconClass} size={24} />;
      case 'shipped':
        return <Truck className={iconClass} size={24} />;
      case 'delivered':
        return <MapPin className={iconClass} size={24} />;
      default:
        return <Package className={iconClass} size={24} />;
    }
  };

  return (
    <div className="sf-page" data-testid="track-order-page">
      <Header />
      <div className="electro">
        <Breadcrumb items={[{ label: "Sipariş Takibi" }]} />
        <div className="container">
          <div className="mx-xl-10">
            <div className="mb-6 text-center">
              <h1 className="mb-6">Sipariş Takibi</h1>
              <p className="text-gray-90 px-xl-10">Siparişinizi takip etmek için sipariş onay e-postanızda yer alan sipariş numaranızı veya kargo takip numaranızı aşağıdaki kutuya yazıp "Takip Et" düğmesine basın.</p>
            </div>
            <div className="my-4 my-xl-8">
              <form onSubmit={handleSearch}>
                <div className="row">
                  <div className="col-md-8 mb-3">
                    <div className="form-group">
                      <label className="form-label" htmlFor="orderid">Sipariş / Kargo Takip Numarası</label>
                      <input type="text" className="form-control" id="orderid" value={trackingCode} onChange={(e) => setTrackingCode(e.target.value)}
                        placeholder="Sipariş onay e-postanızda yer alır." data-testid="tracking-input" />
                    </div>
                  </div>
                  <div className="col-md-4 mb-3 d-flex align-items-end">
                    <div className="form-group w-100">
                      <button type="submit" disabled={loading} className="btn btn-soft-secondary mb-3 mb-md-0 font-weight-normal px-5 px-md-4 px-lg-5 w-100" data-testid="tracking-search-btn">
                        <i className="ec ec-search mr-1" /> {loading ? "Aranıyor..." : "Takip Et"}
                      </button>
                    </div>
                  </div>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 pb-12">
        {/* Error */}
        {error && searched && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-6">
            {error}
          </div>
        )}

        {/* Order Details */}
        {order && (
          <div className="bg-white rounded-lg shadow-sm border p-6" data-testid="order-tracking-result">
            {/* Order Header */}
            <div className="flex justify-between items-start mb-6 pb-4 border-b">
              <div>
                <p className="text-sm text-gray-500">Sipariş Numarası</p>
                <p className="font-medium">{order.order_number}</p>
              </div>
              <div className="text-right">
                <span className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                  order.status === 'delivered' ? 'bg-green-100 text-green-700' :
                  order.status === 'shipped' ? 'bg-blue-100 text-blue-700' :
                  order.status === 'cancelled' ? 'bg-red-100 text-red-700' :
                  'bg-yellow-100 text-yellow-700'
                }`}>
                  {order.status_text}
                </span>
              </div>
            </div>

            {/* Timeline */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-500 mb-4">Sipariş Durumu</h3>
              <div className="space-y-4">
                {order.timeline.map((step, index) => (
                  <div key={step.status} className="flex items-start gap-4">
                    <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                      step.completed ? 'bg-green-100' : 'bg-gray-100'
                    }`}>
                      {getStatusIcon(step.status, step.completed)}
                    </div>
                    <div className="flex-1 pt-1">
                      <p className={`font-medium ${step.completed ? 'text-gray-900' : 'text-gray-400'}`}>
                        {step.title}
                      </p>
                      {step.date && (
                        <p className="text-sm text-gray-500">
                          {new Date(step.date).toLocaleString('tr-TR')}
                        </p>
                      )}
                      {step.tracking_number && (
                        <div className="mt-2 bg-blue-50 rounded-lg p-3">
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">{step.carrier}</span> - {step.tracking_number}
                          </p>
                          {step.tracking_url && (
                            <a
                              href={step.tracking_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-blue-600 text-sm hover:underline flex items-center gap-1 mt-1"
                            >
                              Kargo Takip <ExternalLink size={14} />
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                    {index < order.timeline.length - 1 && (
                      <div className={`absolute left-5 mt-10 w-0.5 h-8 ${
                        step.completed ? 'bg-green-300' : 'bg-gray-200'
                      }`} style={{ display: 'none' }} />
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Delivery Address */}
            {order.shipping_address && (
              <div className="border-t pt-4">
                <h3 className="text-sm font-medium text-gray-500 mb-2">Teslimat Adresi</h3>
                <p className="text-gray-700">
                  {order.shipping_address.first_name} {order.shipping_address.last_name}
                  {order.shipping_address.district && `, ${order.shipping_address.district}`}
                  {order.shipping_address.city && ` / ${order.shipping_address.city}`}
                </p>
              </div>
            )}

            {/* A3: Kimliksiz takip sayfasında finansal özet (tutar/kalem/indirim) gösterilmez —
                sipariş no ardışık olduğundan enumeration ile sızmasın. Tutar detayı için
                müşteri giriş yapıp "Siparişlerim"den görür. */}
          </div>
        )}

        {/* Help Text */}
        {!order && !loading && !searched && (
          <div className="text-center text-gray-500 text-sm">
            <p className="mb-2">Sipariş numaranız veya kargo takip numaranız ile siparişinizi takip edebilirsiniz.</p>
            <p>Sipariş numaranızı e-posta veya SMS ile aldınız.</p>
          </div>
        )}
      </div>

      <Footer />
    </div>
  );
}
