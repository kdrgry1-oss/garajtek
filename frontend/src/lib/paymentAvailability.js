/**
 * Kartla (taksitli) ödeme gerçekten sunuluyor mu? — kasa (Checkout) ile AYNI iki sinyal:
 *   • GET /api/settings → payment_methods.credit_card (admin açık/kapalı)
 *   • GET /api/integrations/payment/status → configured (iyzico anahtarları girilmiş mi)
 * Ürün sayfası "Taksitli Ödeme" rozetini yalnız ikisi de uygunsa gösterir; aksi halde
 * kasada olmayan bir taksit seçeneği vaat edilmiş olurdu.
 */
import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Saf karar: true/false; sinyallerden biri henüz bilinmiyorsa null. */
export function cardPaymentAvailable(settings, status) {
  if (settings === undefined || status === undefined) return null;
  const enabled = settings?.payment_methods?.credit_card !== false;
  const configured = status?.configured !== false;
  return enabled && configured;
}

let _promise = null;

function loadCardAvailability() {
  if (!_promise) {
    _promise = Promise.all([
      axios.get(`${API}/settings`).then((r) => r.data || {}),
      axios.get(`${API}/integrations/payment/status`).then((r) => r.data || {}),
    ])
      .then(([s, st]) => cardPaymentAvailable(s, st))
      // Okunamazsa taksit VAAT ETME (rozet nötr metne düşer); sonraki sayfada tekrar dene.
      .catch(() => { _promise = null; return false; });
  }
  return _promise;
}

/** React hook: null (yükleniyor) | true | false */
export function useCardPaymentAvailable() {
  const [ok, setOk] = useState(null);
  useEffect(() => {
    let alive = true;
    loadCardAvailability().then((v) => { if (alive) setOk(v); });
    return () => { alive = false; };
  }, []);
  return ok;
}
