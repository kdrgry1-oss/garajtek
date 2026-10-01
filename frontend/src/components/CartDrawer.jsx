// Sepet paneli — Electro "u-sidebar" (sağdan açılan panel) görünümünde. Sepete ürün eklenince
// (CartContext.addItem → setIsOpen(true)) ve mobil header'daki sepet ikonundan açılır.
// İş mantığı aynen korunur: kampanya/kupon değerlendirme (/coupons/evaluate), ücretsiz kargo
// eşiği (shippingQuote), kalem indirim görünümü (cartLineView), sepet paylaş, analitik.
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import axios from "axios";
import { shippingQuote } from "../lib/shippingRules";
import { useShipping } from "../lib/shipping";
import { useCart } from "../context/CartContext";
import { cartLineView, cartSummary } from "../lib/price";
import { trackRemoveFromCart } from "../lib/dataLayer";
import { shareCart } from "../lib/shareCart";
import { optimizeImg } from "../lib/img";
import { fmtPrice } from "./electro/format";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export function trackRemove(item) {
  try {
    trackRemoveFromCart({
      product: { id: item.productId || item.product_id || item.id, name: item.name, sale_price: item.price, price: item.price },
      variant: { size: item.size, color: item.color, price: item.price },
      quantity: item.quantity || 1,
    });
  } catch (_) { /* silent */ }
}

/** Sepet kalemleri listesi — mini sepet (dropdown) ve panel ortak kullanır. */
export function MiniCartList({ items, onNavigate, removeItem, updateQuantity, compact = false }) {
  return (
    <ul className="list-unstyled px-3 pt-3 mb-0">
      {items.map((item) => {
        const lv = cartLineView(item);
        return (
          <li key={item.id} className="border-bottom pb-3 mb-3" data-testid={`cart-line-${item.id}`}>
            <ul className="list-unstyled row mx-n2 mb-0">
              <li className="px-2 col-auto">
                <Link to={`/${item.slug || item.productId}`} onClick={onNavigate} className="d-block el-mini-thumb">
                  <img className="img-fluid" src={optimizeImg(item.image, 150) || "/placeholder.jpg"} alt={item.name} width="75" height="75" loading="lazy" />
                </Link>
              </li>
              <li className="px-2 col">
                <h5 className="text-blue font-size-14 font-weight-bold mb-1">
                  <Link to={`/${item.slug || item.productId}`} onClick={onNavigate} className="text-blue">{item.name}</Link>
                </h5>
                {(item.color || item.size) && (
                  <div className="font-size-12 text-gray-5 mb-1">{[item.color, item.size].filter(Boolean).join(" / ")}</div>
                )}
                <span className="font-size-14">
                  {item.quantity} × {lv.hasDiscount && <del className="text-gray-9 font-size-12 mr-1">{fmtPrice(lv.listUnit)}</del>}
                  <span className={lv.hasDiscount ? "text-red" : ""}>{fmtPrice(lv.unit)}</span>
                </span>
                {!compact && (
                  <div className="d-flex align-items-center mt-2">
                    <div className="border rounded-pill d-inline-flex align-items-center px-2 py-0 font-size-13">
                      <button type="button" className="btn btn-xs btn-icon border-0 p-0 px-1" onClick={() => updateQuantity(item.id, item.quantity - 1)} disabled={item.quantity <= 1} data-testid={`decrease-${item.id}`} aria-label="Azalt"><small className="fas fa-minus" /></button>
                      <span className="px-2">{item.quantity}</span>
                      <button type="button" className="btn btn-xs btn-icon border-0 p-0 px-1" onClick={() => updateQuantity(item.id, item.quantity + 1)} data-testid={`increase-${item.id}`} aria-label="Artır"><small className="fas fa-plus" /></button>
                    </div>
                  </div>
                )}
              </li>
              <li className="px-2 col-auto">
                <button type="button" className="btn btn-link p-0 text-gray-90" onClick={() => { trackRemove(item); removeItem(item.id); }} data-testid={`remove-${item.id}`} aria-label="Kaldır">
                  <i className="ec ec-close-remove" />
                </button>
              </li>
            </ul>
          </li>
        );
      })}
    </ul>
  );
}

export default function CartDrawer() {
  const { items, isOpen, setIsOpen, removeItem, updateQuantity, total, itemCount } = useCart();
  const { shippingFee, freeShippingThreshold } = useShipping();
  const freeShippingLimit = freeShippingThreshold || 0;
  const [promoDiscount, setPromoDiscount] = useState(0);

  // Ücretsiz kargo eşiği — sunucuyla aynı taban (indirim SONRASI tutar).
  const netTotal = shippingQuote({ subtotal: total, discounts: [promoDiscount], threshold: freeShippingThreshold, fee: shippingFee }).basis;
  const remaining = freeShippingThreshold != null ? Math.max(0, freeShippingThreshold - netTotal) : 0;

  useEffect(() => {
    if (!isOpen || items.length === 0) { setPromoDiscount(0); return undefined; }
    let cancel = false;
    axios.post(`${API}/coupons/evaluate`, {
      cart_total: total,
      items: items.map((it) => ({ product_id: it.productId, category_id: it.categoryId, price: it.price, qty: it.quantity })),
    })
      .then((r) => { if (!cancel) setPromoDiscount(Number(r.data?.total_discount || 0)); })
      .catch(() => { if (!cancel) setPromoDiscount(0); });
    return () => { cancel = true; };
  }, [isOpen, items, total]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => { if (e.key === "Escape") setIsOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isOpen, setIsOpen]);

  if (!isOpen) return null;
  const close = () => setIsOpen(false);
  const { listSum, grand, totalDisc } = cartSummary(items, promoDiscount);

  return (
    <div className="electro">
      <div className="el-backdrop" onClick={close} aria-hidden="true" />
      <aside className="u-sidebar u-sidebar__lg el-anim-right" data-testid="cart-drawer" role="dialog" aria-modal="true" aria-label="Sepetim">
        <div className="u-sidebar__scroller">
          <div className="u-sidebar__container d-flex flex-column">
            <div className="d-flex align-items-center justify-content-between pt-4 px-4 pb-3 border-bottom">
              <h3 className="font-size-18 mb-0">Sepetim ({itemCount})</h3>
              <button type="button" className="close" onClick={close} data-testid="close-cart" aria-label="Kapat">
                <i className="ec ec-close-remove" />
              </button>
            </div>

            {remaining > 0 && items.length > 0 && (
              <div className="px-4 py-3 border-bottom bg-gray-1">
                <p className="font-size-13 text-center mb-2">
                  Ücretsiz kargo için <strong className="text-green">{fmtPrice(remaining)}</strong> daha ekleyin
                </p>
                <div className="rounded-pill bg-gray-3 height-6 position-relative">
                  <span className="position-absolute left-0 top-0 bottom-0 rounded-pill bg-primary" style={{ width: `${Math.min(100, freeShippingLimit ? (netTotal / freeShippingLimit) * 100 : 0)}%` }} />
                </div>
              </div>
            )}

            <div className="flex-grow-1 overflow-auto">
              {items.length === 0 ? (
                <div className="text-center py-10 px-4">
                  <i className="ec ec-shopping-bag font-size-50 text-gray-5 d-block mb-3" />
                  <p className="text-gray-90 mb-4">Sepetiniz boş</p>
                  <button type="button" onClick={close} className="btn btn-primary-dark-w px-5 rounded-pill">Alışverişe Başla</button>
                </div>
              ) : (
                <MiniCartList items={items} onNavigate={close} removeItem={removeItem} updateQuantity={updateQuantity} />
              )}
            </div>

            {items.length > 0 && (
              <div className="border-top px-4 py-3">
                <div className="flex-center-between mb-1">
                  <span className="font-size-14">Ara Toplam</span>
                  <span className="font-size-14">{fmtPrice(listSum)}</span>
                </div>
                {totalDisc > 0.001 && (
                  <div className="flex-center-between mb-1 text-green" data-testid="drawer-promo-discount">
                    <span className="font-size-14">İndirim</span>
                    <span className="font-size-14">-{fmtPrice(totalDisc)}</span>
                  </div>
                )}
                <div className="flex-center-between border-top pt-2 mb-3">
                  <strong className="font-size-16">Toplam</strong>
                  <strong className="font-size-18">{fmtPrice(grand)}</strong>
                </div>
                {freeShippingThreshold != null && remaining <= 0 && (
                  <p className="font-size-12 text-green text-center mb-3">Sepetiniz ücretsiz kargo eşiğinde. Kargo, ödeme adımında kesinleşir.</p>
                )}
                <div className="d-flex mb-2">
                  <Link to="/sepet" onClick={close} className="btn btn-soft-secondary mb-3 mb-md-0 font-weight-normal px-4 px-md-5 flex-grow-1 mr-2" data-testid="continue-shopping">Sepeti Gör</Link>
                  <Link to="/odeme" onClick={close} className="btn btn-primary-dark-w ml-md-2 px-4 px-md-5 flex-grow-1" data-testid="go-to-checkout">Ödemeye Geç</Link>
                </div>
                <button type="button" onClick={() => shareCart(items)} className="btn btn-link btn-block font-size-13 text-gray-90 p-0" data-testid="drawer-share-cart">
                  <i className="fas fa-share-alt mr-1" /> Sepeti Paylaş
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
