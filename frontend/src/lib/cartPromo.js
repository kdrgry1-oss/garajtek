// Sepetin sunucu-otoriter indirimi (set indirimi + otomatik kampanyalar) — POST /coupons/evaluate.
// Üst sepet simgesi ve mini sepet, açılan sepetle AYNI toplamı göstersin diye ortak kanca.
import { useEffect, useState } from "react";
import axios from "axios";
import { setPayload } from "./productSets";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function useCartPromo(items, total, enabled = true) {
  const [discount, setDiscount] = useState(0);
  const key = (items || []).map((it) => `${it.productId}:${it.variantId || ""}:${it.quantity}:${it.set_id || it.setId || ""}`).join("|");
  useEffect(() => {
    if (!enabled || !items || !items.length) { setDiscount(0); return undefined; }
    let cancel = false;
    const t = setTimeout(() => {
      axios.post(`${API}/coupons/evaluate`, {
        cart_total: total,
        items: items.map((it) => ({ product_id: it.productId, category_id: it.categoryId, price: it.price, qty: it.quantity, ...setPayload(it) })),
      })
        .then((r) => { if (!cancel) setDiscount(Number(r.data?.total_discount || 0)); })
        .catch(() => { if (!cancel) setDiscount(0); });
    }, 250);
    return () => { cancel = true; clearTimeout(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, total, enabled]);
  return discount;
}
