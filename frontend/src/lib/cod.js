// Kapıda ödeme (COD) vitrin yardımcıları. Kurallar sunucuda: backend/cod_rules.py
//  • /api/storefront/cod-info  → açık mı, hizmet bedeli, alt/üst tutar, kart rozeti, kapalı kategoriler
//  • /api/storefront/cod-check → belirli ürünler + tutar için uygun mu (ürün/kategori/limit)
// Kapıda ödeme kapalıysa hiçbir rozet/satır gösterilmez.
import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
let _infoPromise = null;
let _info = null;

export function fetchCodInfo() {
  if (_info) return Promise.resolve(_info);
  if (typeof fetch !== "function") return Promise.resolve({ enabled: false });
  if (!_infoPromise) {
    _infoPromise = fetch(`${API}/storefront/cod-info`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { _info = d || { enabled: false }; return _info; })
      .catch(() => { _infoPromise = null; return { enabled: false }; });
  }
  return _infoPromise;
}

/** Test/oturum değişimi için önbelleği sıfırla. */
export function resetCodInfoCache() {
  _info = null;
  _infoPromise = null;
}

export function useCodInfo() {
  const [info, setInfo] = useState(_info);
  useEffect(() => {
    let alive = true;
    fetchCodInfo().then((d) => { if (alive) setInfo(d); });
    return () => { alive = false; };
  }, []);
  return info;
}

/** Ürün (kart verisiyle) kapıda ödemeye uygun mu? Yalnız ürün/kategori kapatmasına bakar. */
export function productCodAllowed(product, info) {
  if (!info || !info.enabled || !product) return false;
  if (product.cod_disabled) return false;
  const ex = new Set((info.excluded_category_ids || []).map(String));
  if (!ex.size) return true;
  const ids = [...(product.category_ids || []), product.category_id].filter(Boolean).map(String);
  return !ids.some((id) => ex.has(id));
}

/** Sepet/kasa için sunucu kontrolü: {available, reason, fee, ...}. productIds değişince yenilenir. */
export function useCodCheck(productIds, subtotal) {
  const key = (productIds || []).filter(Boolean).slice().sort().join(",");
  const amount = Math.round((Number(subtotal) || 0) * 100) / 100;
  const [state, setState] = useState({ available: null, reason: "" });
  useEffect(() => {
    if (!key) { setState({ available: null, reason: "" }); return undefined; }
    let alive = true;
    Promise.resolve(axios.post(`${API}/storefront/cod-check`, { product_ids: key.split(","), subtotal: amount }))
      .then((r) => { if (alive && r && r.data && typeof r.data.available === "boolean") setState(r.data); })
      .catch(() => {});
    return () => { alive = false; };
  }, [key, amount]);
  return state;
}
