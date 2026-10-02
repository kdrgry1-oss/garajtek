import { Link, useSearchParams } from "react-router-dom";
import { Fragment, useEffect, useState, useRef } from "react";
import { toast } from "sonner";
import axios from "axios";
import { shareCart } from "../lib/shareCart";
import { useShipping } from "../lib/shipping";
import { shippingQuote } from "../lib/shippingRules";
import Header from "../components/Header";
import Footer from "../components/Footer";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { optimizeImg } from "../lib/img";
import ProductCard from "../components/ProductCard";
import Breadcrumb from "../components/electro/Breadcrumb";
import Carousel from "../components/electro/Carousel";
import QuantityInput from "../components/electro/QuantityInput";
import { fmtPrice } from "../components/electro/format";
import { trackRemove } from "../components/CartDrawer";
import { cartLineView, cartSummary } from "../lib/price";
import { trackViewCart } from "../utils/pixelEvents";
import { SetGroupHeaderRow, SetPendingRows, SetPendingNotice } from "../components/sets/SetCartParts";
import { CartCodNote } from "../components/electro/CodInfo";
import { setPayload } from "../lib/productSets";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PLACEHOLDER = "/placeholder.jpg";

export default function Cart() {
  const { items, addItem, removeItem, updateQuantity, total, itemCount } = useCart();
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();

  // ── SEPETİ PAYLAŞ ────────────────────────────────────────────────────────
  // Paylaş: sepet kalemleri sunucuya yazılır → kısa link panoya kopyalanır.
  // Alma: /sepet?paylasim=<id> ile gelen ziyaretçinin sepetine kalemler eklenir
  // (fiyat otoritesi sunucu — link açıldığı andaki güncel fiyat geçerli).
  const [sharing, setSharing] = useState(false);
  const shareLoadedRef = useRef(false); // StrictMode çift-effect / tekrar ekleme koruması

  const handleShareCart = async () => {
    if (items.length === 0 || sharing) return;
    setSharing(true);
    try { await shareCart(items); } finally { setSharing(false); }
  };

  useEffect(() => {
    const shareId = searchParams.get("paylasim");
    if (!shareId || shareLoadedRef.current) return;
    // Aynı link ikinci kez açılırsa (yenileme dahil) mükerrer ekleme olmasın
    const seenKey = `shared_cart_loaded_${shareId}`;
    if (sessionStorage.getItem(seenKey)) {
      setSearchParams({}, { replace: true });
      return;
    }
    shareLoadedRef.current = true;
    axios.get(`${API}/shared-carts/${shareId}`)
      .then((res) => {
        // Paylaşılan sepet / hatırlatma linki: sepette ZATEN olan kalem tekrar eklenmez — aynı link
        // yeni sekmede tekrar açılınca adetler katlanıyordu (36 kalemlik sepette 176 adet görüldü).
        const fromReminder = searchParams.get("hatirlatma") === "1";
        const has = (pid, vid) => items.some((it) => it.productId === pid && (it.variantId || null) === (vid || null));
        const list = (res.data?.items || []).filter(({ product, variant }) =>
          product?.id && !has(product.id, variant?.id));
        list.forEach(({ product, variant, quantity }) => {
          addItem(product, variant || null, quantity || 1);
        });
        if (list.length) toast.success(fromReminder ? "Sepetin hazır" : `Paylaşılan sepetten ${list.length} ürün eklendi`);
        else if ((res.data?.items || []).length) toast.success("Paylaşılan sepetteki ürünler zaten sepetinde");
        sessionStorage.setItem(seenKey, "1");
      })
      .catch((e) => {
        toast.error(e.response?.data?.detail || "Paylaşılan sepet yüklenemedi");
      })
      .finally(() => setSearchParams({}, { replace: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);
  const { shippingFee, freeShippingThreshold } = useShipping();
  const freeShippingLimit = freeShippingThreshold || 0;

  // Madde 4 — Kampanya motoru: sepet sayfası da checkout ile AYNI motoru çağırır.
  // Önceden sadece Checkout.jsx çağırıyordu; bu yüzden "sepette otomatik %10" kampanyaları
  // sepet ekranında hiç görünmüyor/uygulanmıyordu (checkout'a geçilince aniden çıkıyordu).
  const [promoDiscount, setPromoDiscount] = useState(0);
  const [appliedPromotions, setAppliedPromotions] = useState([]);

  useEffect(() => {
    if (items.length === 0) { setPromoDiscount(0); setAppliedPromotions([]); return; }
    let cancel = false;
    axios.post(`${API}/coupons/evaluate`, {
      cart_total: total,
      items: items.map((it) => ({ product_id: it.productId, category_id: it.categoryId, price: it.price, qty: it.quantity, ...setPayload(it) })),
      user_id: user?.id || null,
      email: user?.email || "",
      code: "",
    }).then((res) => {
      if (cancel) return;
      const d = res.data || {};
      setPromoDiscount(Number(d.total_discount || 0));
      setAppliedPromotions(d.applied || []);
    }).catch(() => {
      if (!cancel) { setPromoDiscount(0); setAppliedPromotions([]); }
    });
    return () => { cancel = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, total, user?.id]);

  // ÜCRETSİZ KARGO EŞİĞİ — sunucunun kararıyla AYNI taban: İNDİRİM SONRASI sepet tutarı
  // (orders.create_order: (_subtotal - _server_discount) >= eşik). Eskiden indirimSİZ ara
  // toplam baz alınıyordu → hem "X TL daha" yazısı yanlış çıkıyor hem de sepet ekranı
  // "ücretsiz kargo" gösterip siparişte kargo ücreti ekleniyordu (tutarsızlık).
  // Payment/points choices are not known in the cart: this is an estimate only.
  const shipping = shippingQuote({ subtotal: total, discounts: [promoDiscount], threshold: freeShippingThreshold, fee: shippingFee });
  const netTotal = shipping.basis;
  const remaining = freeShippingThreshold != null ? Math.max(0, freeShippingThreshold - netTotal) : 0;
  const shippingCost = shipping.cost;

  // Ürün-seviyesi indirim (sale_price + otomatik kampanya) — satırlarla birebir tutarlı özet.
  const { listSum, productDisc, extraDisc, totalDisc, grand: _grandNoShip } = cartSummary(items, promoDiscount);
  const grandTotal = _grandNoShip + shippingCost;
  // Sepet-seviyesi kampanya adları (ör. "3 Al 2 Öde — Body"); kalemde zaten gösterilen
  // otomatik yüzde kampanyaları hariç.
  const extraTitles = (appliedPromotions || [])
    .filter((p) => p && Number(p.discount) > 0 && p.type !== "percent")
    .map((p) => p.title || p.code).filter(Boolean);

  // Benzer ürün / indirim önerileri
  const [suggestions, setSuggestions] = useState([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [deals, setDeals] = useState([]);

  useEffect(() => {
    if (items.length === 0) { setSuggestions([]); setDeals([]); return; }
    let cancel = false;
    setSuggestionsLoading(true);
    const productIds = items.map((it) => it.productId).filter(Boolean);
    Promise.all([
      axios.post(`${API}/products/cart-suggestions`, { product_ids: productIds, limit: 8 }),
      axios.post(`${API}/products/checkout-deals`, { product_ids: productIds, limit: 6 }),
    ])
      .then(([s, d]) => {
        if (cancel) return;
        setSuggestions(s.data?.items || []);
        setDeals(d.data?.items || []);
      })
      .catch(() => { if (!cancel) { setSuggestions([]); setDeals([]); } })
      .finally(() => { if (!cancel) setSuggestionsLoading(false); });
    return () => { cancel = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length]);

  // GA4: view_cart — sepet sayfası görüntüleme (mount'ta bir kez)
  useEffect(() => {
    if (items.length === 0) return;
    try {
      trackViewCart({ total, items });
    } catch (_) { /* silent */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const carousel = (title, list, testId, cta) => (list.length > 0 && (
    <div className="mb-6" data-testid={testId}>
      <div className="position-relative">
        <div className="border-bottom border-color-1 mb-2 d-flex justify-content-between align-items-end">
          <h3 className="section-title mb-0 pb-2 font-size-22">{title}</h3>
          {cta}
        </div>
        <Carousel perView={{ base: 2, md: 3, lg: 4, xl: 5, wd: 6 }} className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0">
          {list.map((p, i) => (
            <div className="js-slide products-group" key={p.id} data-testid={`${testId === "checkout-deals-block" ? "checkout-deal" : "cart-suggestion"}-${p.id}`}>
              <ProductCard product={p} listName={testId} index={i} innerClassName="product-item__inner px-wd-4 p-2 p-md-3" wishlistLabel="Favori" />
            </div>
          ))}
        </Carousel>
      </div>
    </div>
  ));

  if (items.length === 0) {
    return (
      <div className="sf-page" data-testid="cart-page">
        <Header />
        <main id="content" role="main" className="electro el-page cart-page">
          <Breadcrumb items={[{ label: "Sepetim" }]} />
          <div className="container">
            <div className="mb-4"><h1 className="text-center">Sepetim</h1></div>
            <div className="text-center mb-10">
              <i className="ec ec-shopping-bag font-size-50 text-gray-5 d-block mb-3" />
              <SetPendingNotice />
              <p className="font-size-16 text-gray-90 mb-4">Sepetinizde ürün bulunmuyor.</p>
              <Link to="/" className="btn btn-primary-dark-w px-5" data-testid="empty-cart-shop-btn">Alışverişe Başla</Link>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  return (
    <div className="sf-page" data-testid="cart-page">
      <Header />
      <main id="content" role="main" className="electro el-page cart-page">
        <Breadcrumb items={[{ label: "Sepetim" }]} />
        <div className="container">
          <div className="mb-4"><h1 className="text-center">Sepetim <span className="font-size-20 text-gray-90">({itemCount} ürün)</span></h1></div>

          {freeShippingThreshold != null && (
            <div className="mb-5 mx-auto" style={{ maxWidth: 640 }} data-testid="cart-free-shipping">
              {remaining > 0 ? (
                <>
                  <p className="text-center font-size-14 mb-2">Ücretsiz kargo için <strong>{fmtPrice(remaining)}</strong> daha ekleyin</p>
                  <div className="rounded-pill bg-gray-3 height-6 position-relative">
                    <span className="position-absolute left-0 top-0 bottom-0 rounded-pill bg-primary" style={{ width: `${Math.min(100, freeShippingLimit ? (netTotal / freeShippingLimit) * 100 : 0)}%` }} />
                  </div>
                </>
              ) : (
                <p className="text-center font-size-14 text-green mb-0"><i className="fas fa-truck mr-1" /> Tebrikler! Siparişiniz ücretsiz kargo kapsamında.</p>
              )}
            </div>
          )}

          <SetPendingNotice />
          <div className="mb-10 cart-table">
            <table className="table" cellSpacing="0">
              <thead>
                <tr>
                  <th className="product-remove">&nbsp;</th>
                  <th className="product-thumbnail">&nbsp;</th>
                  <th className="product-name">Ürün</th>
                  <th className="product-price">Fiyat</th>
                  <th className="product-quantity w-lg-15">Adet</th>
                  <th className="product-subtotal">Toplam</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item, idx) => {
                  const lv = cartLineView(item);
                  const href = `/${item.slug || item.productId || ""}`;
                  return (
                    <Fragment key={item.id}>
                    <SetGroupHeaderRow item={item} prev={items[idx - 1]} />
                    <tr data-testid={`cart-item-${item.id}`}>
                      <td className="text-center">
                        <button type="button" className="btn btn-link text-gray-32 font-size-26 p-0" onClick={() => { trackRemove(item); removeItem(item.id); }} data-testid={`remove-cart-${item.id}`} aria-label="Ürünü sepetten çıkar">×</button>
                      </td>
                      <td className="d-none d-md-table-cell">
                        <Link to={href}><img className="img-fluid max-width-100 p-1 border border-color-1" src={optimizeImg(item.image, 200) || PLACEHOLDER} alt={item.name} width="100" height="100" loading="lazy" /></Link>
                      </td>
                      <td data-title="Ürün">
                        <Link to={href} className="text-gray-90">{item.name}</Link>
                        {(item.color || item.size) && <div className="font-size-12 text-gray-5">{[item.color, item.size].filter(Boolean).join(" / ")}</div>}
                        {lv.campaignPct > 0 && <div className="font-size-12 text-green">%{lv.campaignPct} kampanya indirimi</div>}
                      </td>
                      <td data-title="Fiyat">
                        {lv.hasDiscount && <del className="text-gray-9 font-size-13 mr-1 d-block d-md-inline">{fmtPrice(lv.listUnit)}</del>}
                        <span className={lv.hasDiscount ? "text-red" : ""}>{fmtPrice(lv.unit)}</span>
                      </td>
                      <td data-title="Adet">
                        <span className="sr-only">Adet</span>
                        <QuantityInput value={item.quantity} onChange={(n) => updateQuantity(item.id, n)} max={item.stock || 9999} testId={`cart-qty-${item.id}`} />
                      </td>
                      <td data-title="Toplam"><span>{fmtPrice(lv.unit * item.quantity)}</span></td>
                    </tr>
                    <SetPendingRows item={item} next={items[idx + 1]} />
                    </Fragment>
                  );
                })}
                <SetPendingRows orphans />
                <tr>
                  <td colSpan="6" className="border-top space-top-2 justify-content-center">
                    <div className="pt-md-3">
                      <div className="d-block d-md-flex flex-center-between">
                        <div className="mb-3 mb-md-0 w-xl-40 font-size-14 text-gray-90">
                          <i className="fas fa-tags mr-1" /> İndirim kuponunuzu ödeme adımında uygulayabilirsiniz.
                        </div>
                        <div className="d-md-flex">
                          <button type="button" onClick={handleShareCart} disabled={sharing} className="btn btn-soft-secondary mb-3 mb-md-0 font-weight-normal px-5 px-md-4 px-lg-5 w-100 w-md-auto" data-testid="share-cart-btn">
                            <i className="fas fa-share-alt mr-1" /> {sharing ? "Hazırlanıyor..." : "Sepeti Paylaş"}
                          </button>
                          <Link to="/odeme" className="btn btn-primary-dark-w ml-md-2 px-5 px-md-4 px-lg-5 w-100 w-md-auto d-none d-md-inline-block" data-testid="checkout-btn-desktop">Ödemeye Geç</Link>
                        </div>
                      </div>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div className="mb-8 cart-total">
            <div className="row">
              <div className="col-xl-5 col-lg-6 offset-lg-6 offset-xl-7 col-md-8 offset-md-4">
                <div className="border-bottom border-color-1 mb-3">
                  <h3 className="d-inline-block section-title mb-0 pb-2 font-size-26">Sepet Toplamı</h3>
                </div>
                <table className="table mb-3 mb-md-0">
                  <tbody>
                    <tr className="cart-subtotal"><th>Ara Toplam</th><td data-title="Ara Toplam"><span className="amount">{fmtPrice(listSum)}</span></td></tr>
                    {productDisc > 0.001 && (
                      <tr data-testid="cart-product-discount"><th>Ürün İndirimleri</th><td data-title="Ürün İndirimleri"><span className="amount text-green">-{fmtPrice(productDisc)}</span></td></tr>
                    )}
                    {extraDisc > 0.001 && (
                      <tr data-testid="cart-promo-discount"><th>{extraTitles.length ? extraTitles.join(" + ") : "Kampanya İndirimi"}</th><td data-title="Kampanya"><span className="amount text-green">-{fmtPrice(extraDisc)}</span></td></tr>
                    )}
                    <tr className="shipping"><th>Kargo</th><td data-title="Kargo">{shippingCost === 0 ? <span className="text-green">Ücretsiz</span> : <span className="amount">{fmtPrice(shippingCost)}</span>}<div className="font-size-12 text-gray-90">Kargo, ödeme adımında kesinleşir.</div></td></tr>
                    <tr className="order-total"><th>Toplam</th><td data-title="Toplam"><strong><span className="amount" data-testid="cart-grand-total">{fmtPrice(grandTotal)}</span></strong></td></tr>
                  </tbody>
                </table>
                {totalDisc > 0.001 && <p className="font-size-13 text-green mb-2">Bu siparişte toplam {fmtPrice(totalDisc)} tasarruf ediyorsunuz.</p>}
                <CartCodNote items={items} total={total} />
                <Link to="/odeme" className="btn btn-primary-dark-w ml-md-2 px-5 px-md-4 px-lg-5 w-100 w-md-auto d-md-none" data-testid="checkout-btn">Ödemeye Geç</Link>
                <div className="text-center text-md-right mt-2"><Link to="/" className="font-size-13 text-gray-90">Alışverişe devam et</Link><span className="text-gray-5 mx-2">·</span><Link to="/hizli-siparis" className="font-size-13 text-gray-90" data-testid="cart-quick-order-link">Hızlı Sipariş</Link></div>
              </div>
            </div>
          </div>

          {!suggestionsLoading && carousel("Benzer Ürünler", suggestions, "cart-suggestions-block")}
          {carousel("Kasa Önü Fırsatları", deals, "checkout-deals-block", <Link to="/sale" className="font-size-14 text-gray-90 pb-2">Tümünü Gör</Link>)}
        </div>
      </main>
      <Footer />
    </div>
  );
}
