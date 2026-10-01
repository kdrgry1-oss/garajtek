import { useState, useEffect, useRef, useCallback } from "react";
import { shippingQuote } from "../lib/shippingRules";
import { useNavigate, useSearchParams } from "react-router-dom";
import axios from "axios";
import { useShipping } from "../lib/shipping";
import { toast } from "sonner";
import { useCart } from "../context/CartContext";
import { cartLineView } from "../lib/price";
import { useAuth } from "../context/AuthContext";
import { trackInitiateCheckout, trackPurchase, trackAddPaymentInfo, trackAddShippingInfo } from "../utils/pixelEvents";
import { collectClickIds } from "../lib/dataLayer";
import { getSessionId } from "../lib/attribution";
import { SITE_NAME } from "../lib/brand";
import { CheckoutHeader, CheckoutFooter } from "../components/checkout/CheckoutChrome";
import OrderSummary from "../components/checkout/OrderSummary";
import AddressFields from "../components/checkout/AddressFields";
import PaymentSection from "../components/checkout/PaymentSection";
import LegalModal from "../components/checkout/LegalModal";
import { Banner, Checkbox, Section } from "../components/checkout/Fields";
import { BillingSection, ContactSection, ExtrasSection, ShippingMethodSection, SmsConsent } from "../components/checkout/Sections";
import {
  analyticsItems, estimateDelivery, foldCode, formatTRY, isValidTCKN, mergeAddressLine, validateAddress,
} from "../components/checkout/utils";
import "./checkout.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Sunucunun OTOMATİK eklediği indirimler (üye grubu / .edu.tr öğrenci): kampanya değil,
// müşteriye hakkı olan indirim → listede görünür ama "×" ile kaldırılamaz.
const AUTO_PROMO_IDS = ["member_discount", "edu_discount"];

const emptyAddress = {
  id: "",
  title: "",
  first_name: "",
  last_name: "",
  phone: "",
  address: "",
  address2: "",
  city: "",
  district: "",
  postal_code: "",
};

const LEGAL_DOCS = {
  "mesafeli-satis": "Mesafeli Satış Sözleşmesi",
  "on-bilgilendirme": "Ön Bilgilendirme Formu",
};

// Checkout'a özel kabuk: site menüsü/footer yok (Shopify tek-sayfa ödeme).
function CheckoutShell({ children, testId = "checkout-page" }) {
  return (
    <div className="gt-checkout" data-testid={testId}>
      <CheckoutHeader />
      {children}
    </div>
  );
}

export default function Checkout() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { items, total, clearCart } = useCart();
  const { user } = useAuth();

  // UI durumu
  const [summaryOpen, setSummaryOpen] = useState(false); // mobil sipariş özeti
  const [errors, setErrors] = useState({});              // alan-içi hatalar { "ship.phone": "..." }
  const [submitError, setSubmitError] = useState("");    // Shopify tarzı kırmızı banner
  const [couponMsg, setCouponMsg] = useState(null);      // { type: "error"|"ok", text }
  const [legalDoc, setLegalDoc] = useState(null);        // açık sözleşme modalı slug'ı

  // Payment flow
  const [loading, setLoading] = useState(false);
  const [paymentStep, setPaymentStep] = useState("form"); // form | processing | iframe | success | error
  const [, setOrderId] = useState(null);

  // Addresses
  const [savedAddresses, setSavedAddresses] = useState([]);
  const [shippingAddress, setShippingAddress] = useState({ ...emptyAddress, email: user?.email || "" });
  const [billingAddress, setBillingAddress] = useState({ ...emptyAddress });
  const [billingSameAsShipping, setBillingSameAsShipping] = useState(true);

  const clearErr = useCallback((...keys) => {
    setErrors((prev) => {
      if (!keys.some((k) => prev[k])) return prev;
      const next = { ...prev };
      keys.forEach((k) => delete next[k]);
      return next;
    });
  }, []);

  // Üye girişliyse e-posta alanı GİZLENİR; siparişte gerekli olduğundan otomatik doldurulur.
  useEffect(() => {
    if (user?.email) setShippingAddress((p) => (p.email ? p : { ...p, email: user.email }));
  }, [user?.email]);

  // Coupons
  const [couponCode, setCouponCode] = useState("");
  // İlk-siparişe-özel bir kod kimlik (giriş/e-posta) yokken reddedildiyse burada tutulur;
  // müşteri giriş yapınca / e-postasını girince OTOMATİK yeniden uygulanır (destek talebi).
  const [pendingCode, setPendingCode] = useState("");
  const [discount, setDiscount] = useState(0);
  const [appliedCoupon, setAppliedCoupon] = useState(null);
  const [appliedPromotions, setAppliedPromotions] = useState([]); // Madde 4 motor sonucu
  const [eligiblePromotions, setEligiblePromotions] = useState([]); // tum uygulanabilirler (musteri secsin)
  const [excludedIds, setExcludedIds] = useState([]); // musterinin X ile kaldirdigi kampanyalar

  // ÇİFT SİPARİŞ KORUMASI: idempotency anahtarı. KÖK NEDEN #2 düzeltmesi — anahtar
  // sepet imzasına göre sessionStorage'da SAKLANIR. 3DS akışında sayfa document.write ile
  // ezilip banka dönüşünde TAM SAYFA yeniden yüklendiği için eski useRef her remount'ta YENİ
  // anahtar üretiyordu → her deneme YENİ sipariş + tekrar stok düşümü + müşteri 2-3 kez
  // deneyince mükerrer sipariş. Artık AYNI sepette (retry/reload) anahtar SABİT kalır →
  // sunucu mevcut siparişi döndürür (çift sipariş/stok/çekim yok); sepet değişince yenilenir.
  const _newIdemKey = () => (window.crypto?.randomUUID?.() || (String(Date.now()) + "-" + Math.random().toString(36).slice(2)));
  const _cartSig = () => {
    try {
      return (items || [])
        .map((it) => `${it.id || it.product_id || ""}:${it.variant_id || it.variantId || it.size || ""}:${it.quantity || 1}`)
        .sort()
        .join("|");
    } catch { return ""; }
  };
  const _idemStoreKey = () => {
    const sig = _cartSig();
    let h = "empty";
    try { if (sig) h = btoa(unescape(encodeURIComponent(sig))).replace(/[^A-Za-z0-9]/g, "").slice(0, 40); } catch { h = String(sig).length + "_" + (sig.length ? sig.charCodeAt(0) : 0); }
    return "store_idem_" + h;
  };
  const _getIdemKey = () => {
    const storeKey = _idemStoreKey();
    try {
      let k = window.sessionStorage.getItem(storeKey);
      if (!k) { k = _newIdemKey(); window.sessionStorage.setItem(storeKey, k); }
      return k;
    } catch { return _newIdemKey(); }
  };
  // Başarılı ödeme sonrası TÜM idem anahtarlarını temizle → aynı sepet daha sonra tekrar
  // alınırsa eski (ödenmiş) sipariş döndürülmesin, yeni sipariş açılsın.
  const _clearIdemKeys = () => {
    try {
      const rm = [];
      for (let i = 0; i < window.sessionStorage.length; i++) {
        const key = window.sessionStorage.key(i);
        if (key && key.indexOf("store_idem_") === 0) rm.push(key);
      }
      rm.forEach((k) => window.sessionStorage.removeItem(k));
    } catch { /* yoksay */ }
  };
  const idemKeyRef = useRef(null);
  if (idemKeyRef.current == null) idemKeyRef.current = _getIdemKey();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { idemKeyRef.current = _getIdemKey(); }, [items]);

  // Payment options
  const [paymentMethod, setPaymentMethod] = useState("bank_transfer");
  const [use3DSecure, setUse3DSecure] = useState(true);
  const [card, setCard] = useState({ holder: "", number: "", expiry: "", cvc: "" });
  const [installments, setInstallments] = useState([{ number: 1 }]);
  const [selectedInstallment, setSelectedInstallment] = useState(1);
  const [usePoints, setUsePoints] = useState(false);
  // C3: gerçek puan bakiyesi + kademe — üye girişliyse /loyalty/me'den gelir.
  const [userPoints, setUserPoints] = useState(0);
  const [loyaltyTier, setLoyaltyTier] = useState(null);
  useEffect(() => {
    const t = localStorage.getItem("token");
    if (!t || !user) { setUserPoints(0); setLoyaltyTier(null); return; }
    axios.get(`${API}/loyalty/me`, { headers: { Authorization: `Bearer ${t}` } })
      .then((r) => {
        if (r.data?.enabled === false) return;
        setUserPoints(Number(r.data?.points) || 0);
        setLoyaltyTier(r.data?.tier || null);
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);
  // C2 Hediye çeki / mağaza kredisi
  const [giftCardApplied, setGiftCardApplied] = useState(null); // {code, balance, kind}
  const [giftCardBusy, setGiftCardBusy] = useState(false);
  // Aktif ödeme yöntemleri — admin "Ödeme Yöntemleri" ayarından gelir (public /settings).
  // Varsayılan: kart & havale AÇIK, kapıda ödeme KAPALI.
  const [enabledPM, setEnabledPM] = useState({ credit_card: true, bank_transfer: true, cash_on_delivery: false });
  const [bankPct, setBankPct] = useState(5); // Havale/EFT teşvik indirimi (%) — ayardan gelir

  // İşletme Kuralları (admin panelinden yönetilir) — kodda sabit değil.
  const [bizRules, setBizRules] = useState({});
  useEffect(() => {
    axios.get(`${API}/business-rules`).then((r) => setBizRules(r.data || {})).catch(() => {});
  }, []);
  const GIFT_WRAP_PRICE = Number(bizRules["product.gift_wrap_price"] ?? 130);
  const COD_FEE = Number(bizRules["shipping.cod_fee"] ?? 10);
  const POINTS_MAX_PCT = Number(bizRules["payment.points_redeem_max_pct"] ?? 10);
  const [giftNote, setGiftNote] = useState("");
  // Siparişe dair GENEL not — hediye notundan AYRI. Hediye paketi seçilmese de girilebilir;
  // panelde 📌 not alanında görünür, hediye notuyla karışmaz.
  const [orderNote, setOrderNote] = useState("");
  const [giftWrap, setGiftWrap] = useState(false);
  const [acceptTerms, setAcceptTerms] = useState(false);
  // İYS ticari ileti izni + OTP
  const [mktEmail, setMktEmail] = useState(false);
  const [mktSms, setMktSms] = useState(false);
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpVerified, setOtpVerified] = useState(false);
  const [otpBusy, setOtpBusy] = useState(false);

  const sendOtp = async () => {
    const phone = (shippingAddress.phone || "").trim();
    if (!phone) { toast.error("Önce teslimat telefonunuzu girin"); return; }
    try {
      setOtpBusy(true);
      const res = await axios.post(`${API}/iys/otp/send`, { phone });
      if (res.data?.success) { setOtpSent(true); toast.success("Doğrulama kodu SMS ile gönderildi"); }
      else toast.error(res.data?.detail || "SMS gönderilemedi");
    } catch (e) {
      toast.error(e.response?.data?.detail || "SMS gönderilemedi");
    } finally { setOtpBusy(false); }
  };
  const verifyOtp = async () => {
    const phone = (shippingAddress.phone || "").trim();
    if (!otpCode.trim()) { toast.error("Kodu girin"); return; }
    try {
      setOtpBusy(true);
      const res = await axios.post(`${API}/iys/otp/verify`, { phone, code: otpCode.trim() });
      if (res.data?.verified) { setOtpVerified(true); toast.success("Telefonunuz doğrulandı"); }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kod doğrulanamadı");
    } finally { setOtpBusy(false); }
  };

  // KURUMSAL FATURA
  const [corporateInvoice, setCorporateInvoice] = useState(false);
  const [corporateData, setCorporateData] = useState({
    company_name: "",
    tax_office: "",
    tax_number: "",  // VKN (10) veya TCKN (11)
    eInvoice_user: false,  // E-Fatura mükellefi mi
  });

  // Sipariş tutarları (türetilmiş) — useEffect'lerden ÖNCE tanımlanmalı (TDZ hatası önlenir)
  const { shippingFee, freeShippingThreshold } = useShipping();

  // DENETİM FIX (#46): Kargo Kuralları (shipping_rules) sepet tutarına göre kargo bedelini
  // belirlesin. Eşleşen kural varsa onun bedeli kullanılır; yoksa genel settings.shipping_fee'ye
  // düşülür (fallback → regresyon yok). Ücretsiz kargo kuponu/eşiği yine önceliklidir.
  const [ruleShipCost, setRuleShipCost] = useState(null); // null = kural yok/yüklenmedi
  useEffect(() => {
    if (!total) { setRuleShipCost(null); return; }
    let cancel = false;
    axios
      .get(`${API}/admin/rules/shipping/resolve?cart_total=${total}`)
      .then((r) => { if (!cancel) setRuleShipCost(r.data?.matched ? Number(r.data.shipping_cost || 0) : null); })
      .catch(() => { if (!cancel) setRuleShipCost(null); });
    return () => { cancel = true; };
  }, [total]);

  // DENETİM FIX (#45): Ödeme Tipi İndirimleri (payment_discounts) — seçili ödeme yöntemine göre
  // aktif indirim uygulanır. Havale (bank_transfer) zaten bankPct ile ele alındığından çift
  // sayımı önlemek için burada hariç tutulur; asıl değer credit_card/diğer yöntemlerdedir.
  const [payDiscounts, setPayDiscounts] = useState({});
  useEffect(() => {
    let cancel = false;
    axios
      .get(`${API}/admin/rules/payment-discounts/resolve`)
      .then((r) => { if (!cancel) setPayDiscounts(r.data?.discounts || {}); })
      .catch(() => {});
    return () => { cancel = true; };
  }, []);

  // ÜYE GRUBU İNDİRİMİ — SUNUCUDA, kampanya motorunun içinde hesaplanıyor
  // (/coupons/evaluate + create_order aynı kaynak). Burada AYRICA düşülmemeli.

  // Y25: Ücretsiz kargo kuponu uygulandıysa kargo 0 gösterilir. Eşik ya da kupon → kargo bedava.
  const hasFreeShippingPromo = (appliedPromotions || []).some((p) => p && p.free_shipping);
  // A rule's preliminary zero fee cannot bypass the final merchandise minimum.
  const baseShipFee = ruleShipCost > 0 ? ruleShipCost : shippingFee;
  const giftWrapTotal = giftWrap ? GIFT_WRAP_PRICE : 0;
  const codFee = paymentMethod === "cash_on_delivery" ? COD_FEE : 0;
  // Puan tavanı SUNUCUYLA aynı tabandan hesaplanır: (ara toplam − kupon/kampanya indirimi).
  const pointsDeduction = usePoints
    ? Math.min(userPoints, Math.max(0, total - discount) * (POINTS_MAX_PCT / 100))
    : 0;
  // Havale/EFT indirimi — kupon indiriminden SONRAKİ tutar üzerinden (sunucu ile aynı mantık).
  const isBankTransfer = paymentMethod === "bank_transfer";
  const bankTransferDiscount = (isBankTransfer && bankPct > 0)
    ? Math.round((total - discount) * (bankPct / 100) * 100) / 100
    : 0;
  // Genelleştirilmiş ödeme tipi indirimi (havale hariç — o bankTransferDiscount ile geliyor)
  const _payRule = payDiscounts[paymentMethod];
  const paymentMethodDiscount = (_payRule && !isBankTransfer)
    ? (((_payRule.percent || 0) > 0)
        ? Math.round((total - discount) * ((_payRule.percent || 0) / 100) * 100) / 100
        : (Number(_payRule.amount) || 0))
    : 0;
  const shipping = shippingQuote({
    subtotal: total,
    discounts: [discount, bankTransferDiscount, paymentMethodDiscount, pointsDeduction],
    threshold: freeShippingThreshold, fee: baseShipFee, freeShippingPromotion: hasFreeShippingPromo,
  });
  const shippingCost = shipping.cost;
  const visiblePromotions = appliedPromotions.filter((p) => !p.free_shipping || shipping.free || Number(p.discount) > 0);
  const preGiftTotal = Math.max(0, total + shippingCost - discount - bankTransferDiscount - paymentMethodDiscount - pointsDeduction + giftWrapTotal + codFee);
  // C2 Hediye çeki: tüm indirimlerden SONRA, ödenecek tutardan düşer (sunucu-otoriter;
  // burada yalnız gösterim). TL bakiye → min(bakiye, tutar); YÜZDE çeki → tutar × % (tavanlı).
  const giftCardDeduction = giftCardApplied
    ? (giftCardApplied.value_type === "percent"
        ? Math.min(Math.round(preGiftTotal * (Number(giftCardApplied.percent) || 0)) / 100,
                   Number(giftCardApplied.max_amount) > 0 ? Number(giftCardApplied.max_amount) : Infinity, preGiftTotal)
        : Math.min(Number(giftCardApplied.balance) || 0, preGiftTotal))
    : 0;
  const grandTotal = Math.max(0, Math.round((preGiftTotal - giftCardDeduction) * 100) / 100);

  // Yalnız ürün kartındaki sale_price farkı motorun dışında kalır. Kampanyaları
  // cartLineView/campaignPct ile TEKRAR hesaplama: özet sunucu sonucunu kullanmalı.
  const listSum = items.reduce((s, it) => s + cartLineView(it).listUnit * it.quantity, 0);
  const productDisc = Math.max(0, listSum - total);

  // Seçili taksitin GERÇEK ödeme değerleri — özet "Toplam" ve buton seçilen taksiti yansıtır.
  const ccInstallmentOpt = paymentMethod === "credit_card"
    ? (installments.find((o) => o.number === selectedInstallment) || null)
    : null;
  const isInstallmentSelected = !!ccInstallmentOpt && ccInstallmentOpt.number > 1;
  const chargeTotal = (ccInstallmentOpt && ccInstallmentOpt.totalPrice) ? ccInstallmentOpt.totalPrice : grandTotal;
  const perInstallmentAmount = (ccInstallmentOpt && ccInstallmentOpt.installmentPrice) ? ccInstallmentOpt.installmentPrice : grandTotal;
  const installmentDiff = Math.max(0, chargeTotal - grandTotal);

  const shippingInfoTracked = useRef(false);

  // Storefront: hangi ödeme yöntemleri aktif? (admin panelinden yönetilir)
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/settings`)
      .then((r) => {
        if (!alive) return;
        const pm = r.data?.payment_methods || {};
        setEnabledPM({
          credit_card: pm.credit_card !== false,          // varsayılan AÇIK
          bank_transfer: pm.bank_transfer !== false,      // varsayılan AÇIK
          // Kapıda ödeme yalnız admin AÇIKÇA açtıysa (true) görünür — sunucu da aynı kuralla
          // (payment_methods.cash_on_delivery is True) doğrular ve hizmet bedelini ekler.
          cash_on_delivery: pm.cash_on_delivery === true,
        });
        // Havale/EFT teşvik indirimi yüzdesi (ayardan; varsayılan %5)
        const bp = r.data?.bank_transfer_discount_pct;
        setBankPct(bp === null || bp === undefined || bp === "" ? 5 : Number(bp) || 0);
      })
      .catch(() => { /* sessiz: varsayılan değerlerde kal */ });
    return () => { alive = false; };
  }, []);

  // Seçili ödeme yöntemi kapatılmışsa ilk aktif yönteme düş
  useEffect(() => {
    const order = ["credit_card", "bank_transfer", "cash_on_delivery"];
    if (!enabledPM[paymentMethod]) {
      const first = order.find((k) => enabledPM[k]);
      if (first) setPaymentMethod(first);
    }
  }, [enabledPM, paymentMethod]);

  // Load saved addresses for logged-in users
  useEffect(() => {
    let active = true;
    setSavedAddresses([]);
    setShippingAddress({ ...emptyAddress, email: user?.email || "" });
    setBillingAddress({ ...emptyAddress });
    if (!user) return;
    const token = localStorage.getItem("token");
    axios.get(`${API}/my-addresses`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        if (!active) return;
        const list = r.data?.addresses || [];
        setSavedAddresses(list);
        const def = list.find((a) => a.is_default) || list[0];
        if (def) {
          setShippingAddress({ ...emptyAddress, ...def, email: user.email || "" });
          setBillingAddress({ ...emptyAddress, ...def });
        }
      })
      .catch(() => {});
    return () => { active = false; };
    // Only an account change should clear an address being edited.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id]);

  // Legacy unscoped addresses can belong to another person on a shared device.
  // Saved addresses are loaded only through the authenticated address API above.
  useEffect(() => {
    try { localStorage.removeItem("store_last_address"); } catch {}
  }, []);

  // Madde 4 — Kampanya motoru: otomatik kampanyalar + (varsa) girilen kodu BIRLIKTE hesaplar.
  // YARIS KORUMASI: en son GÖNDERİLEN istek kazanır (sıra numarası).
  const recalcSeq = useRef(0);
  const recalcPromotions = async (code = "") => {
    const seq = ++recalcSeq.current;
    try {
      const res = await axios.post(`${API}/coupons/evaluate`, {
        cart_total: total,
        items: items.map((it) => ({ product_id: it.productId, category_id: it.categoryId, price: it.price, qty: it.quantity })),
        user_id: user?.id || null,
        // KRİTİK: Sunucu (create_order) uygunluğu shipping_address.email ile değerlendirir;
        // misafirin forma yazdığı e-posta gönderilerek iki taraf hizalanır.
        email: shippingAddress?.email || user?.email || "",
        code: code || "",
        payment_method: paymentMethod,
        excluded_ids: excludedIds,
      });
      if (seq !== recalcSeq.current) return null;   // daha yeni bir istek var → bu (stale) cevabı yut
      const d = res.data || {};
      setAppliedPromotions(d.applied || []);
      setEligiblePromotions(d.eligible || []);
      setDiscount(Number(d.total_discount || 0));
      return d;
    } catch {
      if (seq !== recalcSeq.current) return null;
      setAppliedPromotions([]);
      setEligiblePromotions([]);
      setDiscount(0);
      return null;
    }
  };

  // InitiateCheckout pixel (GA4 begin_checkout + Meta/TikTok)
  useEffect(() => {
    if (items.length === 0) return;
    trackInitiateCheckout({
      total: grandTotal,
      items: analyticsItems(items, SITE_NAME),
      discount, shipping_cost: shippingCost,
      coupon: appliedCoupon?.code || "",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, total, user?.id, discount, shippingCost, appliedCoupon?.code]);

  // GA4: add_shipping_info — geçerli teslimat adresi ilk kez hazır olduğunda BİR KEZ.
  useEffect(() => {
    if (shippingInfoTracked.current) return;
    if (items.length === 0) return;
    const a = shippingAddress;
    const hasAddress = a && a.first_name && (a.address || a.city);
    if (!hasAddress) return;
    shippingInfoTracked.current = true;
    trackAddShippingInfo({
      total: grandTotal,
      items: analyticsItems(items, SITE_NAME),
      coupon: appliedCoupon?.code || "",
      shipping_cost: shippingCost,
      shipping_tier: shippingCost > 0 ? "Standart Kargo" : "Ücretsiz",
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shippingAddress, items, grandTotal, shippingCost, appliedCoupon?.code]);

  // Madde 4 — sepet/kod/ÖDEME YÖNTEMİ/kaldırılanlar degisince motoru calistir (discount DEP DEGIL)
  useEffect(() => {
    if (items.length === 0) { setAppliedPromotions([]); setEligiblePromotions([]); setDiscount(0); return; }
    recalcPromotions(appliedCoupon?.code || "");
    // shippingAddress.email DEP: misafir e-postasını yazınca uygunluk yeniden değerlendirilsin.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items, total, user?.id, appliedCoupon?.code, paymentMethod, excludedIds, shippingAddress?.email]);

  // İLK-SİPARİŞ KODU OTOMATİK YENİDEN UYGULAMA (giriş / geçerli e-posta sonrası).
  useEffect(() => {
    if (!pendingCode || appliedCoupon) return;
    const em = (shippingAddress?.email || user?.email || "").trim();
    const emailValid = /.+@.+\..+/.test(em);
    if (user?.id || emailValid) {
      applyCode(pendingCode);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.id, shippingAddress?.email]);

  // Payment callback — iyzico → backend → storefront'a ?status=success|fail&order=.. ile döner
  useEffect(() => {
    const status = searchParams.get("status");
    const orderNum = searchParams.get("order");
    if (status === "success") {
      handlePaymentSuccess(orderNum);
    } else if (status === "fail") {
      setPaymentStep("error");
      toast.error("Ödeme tamamlanamadı. Lütfen tekrar deneyin.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Kart BIN'i (ilk 6 hane) + tutar değişince taksit seçeneklerini iyzico'dan getir
  useEffect(() => {
    if (paymentMethod !== "credit_card") return;
    const bin = card.number.replace(/\D/g, "").slice(0, 6);
    if (bin.length < 6 || grandTotal <= 0) {
      setInstallments([{ number: 1, totalPrice: grandTotal, installmentPrice: grandTotal }]);
      setSelectedInstallment(1);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await axios.post(`${API}/payment/installments`, {
          bin_number: bin, price: Number(grandTotal.toFixed(2)),
        });
        const opts = res.data?.options?.length
          ? res.data.options
          : [{ number: 1, totalPrice: grandTotal, installmentPrice: grandTotal }];
        setInstallments(opts);
        setSelectedInstallment((cur) => (opts.find((o) => o.number === cur) ? cur : 1));
        if (res.data?.force3ds) setUse3DSecure(true);
      } catch {
        setInstallments([{ number: 1, totalPrice: grandTotal, installmentPrice: grandTotal }]);
        setSelectedInstallment(1);
      }
    }, 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [card.number, grandTotal, paymentMethod]);

  const buildUserInfo = () => ({
    email: shippingAddress.email || user?.email || "",
    phone: shippingAddress.phone || user?.phone || "",
    first_name: shippingAddress.first_name || "",
    last_name: shippingAddress.last_name || "",
    city: shippingAddress.city || "",
    state: shippingAddress.district || shippingAddress.state || "",
    country: shippingAddress.country || "TR",
    zipcode: shippingAddress.zipcode || shippingAddress.postal_code || "",
    street: shippingAddress.address || "",
    // Üye → user id; misafir → stabil first-party visitor id (store_sid).
    // Aynı değer server-side Purchase'ta da external_id olur → browser↔server dedup.
    external_id: user?.id || getSessionId() || "",
  });

  const handlePaymentSuccess = async (orderNumber) => {
    if (!orderNumber) return;
    _clearIdemKeys();  // ödeme başarılı → idem anahtarlarını temizle (sonraki aynı-sepet alımı yeni sipariş açsın)
    setPaymentStep("processing");
    let amount = grandTotal;
    try {
      const r = await axios.get(`${API}/orders/by-number/${orderNumber}`);
      amount = r.data?.total || grandTotal;
    } catch (e) { /* sessiz */ }
    trackPurchase({
      order_id: orderNumber,
      total: amount,
      items: analyticsItems(items, SITE_NAME),
      coupon: appliedCoupon?.code || "",
      discount, shipping: shippingCost, tax: 0,
      payment_type: paymentMethod,
      shipping_tier: shippingCost > 0 ? "Standart Kargo" : "Ücretsiz",
      user: buildUserInfo(),
    });
    clearCart();
    setPaymentStep("success");
    toast.success("Ödemeniz başarıyla tamamlandı!");
    setTimeout(() => navigate(`/order-success/${orderNumber}`), 1200);
  };

  const applyCode = async (rawCode, _fromGift = false) => {
    const code = foldCode(rawCode);
    if (!code) return;
    setCouponMsg(null);
    const d = await recalcPromotions(code);
    if (!d) { setCouponMsg({ type: "error", text: "Kampanya hesaplanamadı" }); return; }
    // BULANIK ÇÖZÜMLEME: sunucu yazılan varyantı KANONİK koda çözer (entered_resolved).
    const resolved = foldCode(d.entered_resolved || code);
    const hit = (d.applied || []).find((a) => foldCode(a.code) === resolved || foldCode(a.code) === code);
    if (hit) {
      setAppliedCoupon({ code: hit.code || resolved });
      setCouponCode(rawCode);
      setPendingCode(""); // uygulandı → bekleyen kod kalmasın
      setCouponMsg({ type: "ok", text: `Kupon uygulandı (${hit.code || resolved}): ${formatTRY(hit.discount)} indirim` });
      return;
    }
    const rej = (d.rejected || []).find((r) =>
      foldCode(r.code) === resolved || foldCode(r.code) === code || foldCode(r.entered || "") === code);
    if (rej) {
      // İLK-SİPARİŞ + KİMLİK YOK: kodu HATIRLA; müşteri giriş yapınca/e-posta girince otomatik uygulanır.
      const _em = (shippingAddress?.email || user?.email || "").trim();
      const _noIdentity = !(user?.id) && !_em;
      if (_noIdentity && /giriş yap|ilk sipariş/i.test(rej.reason || "")) {
        setPendingCode(code);
        setCouponMsg({ type: "error", text: "Bu kod ilk siparişe özeldir — giriş yapın ya da üyelik e-postanızı girin; kod otomatik uygulanacak." });
      } else {
        setPendingCode(""); // kimlik var ama yine reddedildi → gerçekten uygulanamıyor
        setCouponMsg({ type: "error", text: rej.reason || "Bu kupon şu an bu sepete uygulanamıyor." });
      }
      return;
    }
    // Kod hiçbir kampanyayla eşleşmedi → belki HEDİYE ÇEKİdir; giftcard olarak dene (döngü yok).
    if (!_fromGift) {
      setGiftCardBusy(true);
      try {
        const { data } = await axios.post(`${API}/gift-cards/check`, {
          code, email: shippingAddress.email || user?.email || "",
        });
        if (data?.valid) {
          setGiftCardApplied({ code, balance: Number(data.balance) || 0, kind: data.kind || "gift",
                               value_type: data.value_type || "amount", percent: Number(data.percent) || 0, max_amount: Number(data.max_amount) || 0 });
          setCouponCode("");
          setCouponMsg({ type: "ok", text: data.value_type === "percent"
            ? `Hediye çeki uygulandı — %${Number(data.percent) || 0} indirim${Number(data.max_amount) > 0 ? ` (en fazla ${formatTRY(data.max_amount)})` : ""}`
            : `Hediye çeki uygulandı — bakiye: ${formatTRY(data.balance)}` });
          return;
        }
      } catch { /* sessiz */ }
      finally { setGiftCardBusy(false); }
    }
    setCouponMsg({ type: "error", text: "Bu kod geçersiz veya bu sepete uygulanamıyor." });
  };

  const handleRemoveCoupon = () => {
    setAppliedCoupon(null);
    setCouponCode("");
    setCouponMsg(null);
    recalcPromotions(""); // girilen kod kalkar, otomatik kampanyalar uygulanmaya devam eder
  };

  // Uygulanan bir kampanyayı X ile kaldır
  const removePromotion = (p) => {
    if (appliedCoupon && p.code && appliedCoupon.code === p.code) { handleRemoveCoupon(); return; }
    const id = p.coupon_id;
    if (!id) return;
    setExcludedIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
  };
  const resetExcluded = () => setExcludedIds([]);

  // ----- Adres güncelleme (satır içi form) -----
  const updateShipping = (patch) => {
    setShippingAddress((p) => {
      const next = { ...p, ...patch };
      // Kayıtlı adres seçiliyken alan değişirse artık "yeni adres"tir (seçim etiketi düşer).
      if (p.id && Object.keys(patch).some((k) => k !== "email" && patch[k] !== p[k])) next.id = "";
      return next;
    });
    clearErr(...Object.keys(patch).map((k) => `ship.${k}`));
  };
  const updateBilling = (patch) => {
    setBillingAddress((p) => {
      const next = { ...p, ...patch };
      if (p.id && Object.keys(patch).some((k) => patch[k] !== p[k])) next.id = "";
      return next;
    });
    clearErr(...Object.keys(patch).map((k) => `bill.${k}`));
  };
  const pickSavedShipping = (a) => {
    setShippingAddress((p) => (a ? { ...emptyAddress, ...a, email: user?.email || a.email || p.email || "" } : { ...emptyAddress, email: p.email || "" }));
    if (a && billingSameAsShipping) setBillingAddress({ ...emptyAddress, ...a });
    setErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => !k.startsWith("ship."))));
  };
  const pickSavedBilling = (a) => {
    setBillingAddress(a ? { ...emptyAddress, ...a } : { ...emptyAddress });
    setErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => !k.startsWith("bill."))));
  };

  const onSelectMethod = (key) => {
    setPaymentMethod(key);
    clearErr("card.holder", "card.number", "card.expiry", "card.cvc");
    // GA4 + CAPI: add_payment_info — zengin payload
    try {
      const mappedItems = (items || []).map((it) => ({
        item_id: String(it.product_id || it.productId || it.id || it.sku || ""),
        item_name: it.name || "",
        item_brand: it.brand || SITE_NAME,
        item_category: it.category || it.categoryName || "",
        item_variant: `${it.size || ""} ${it.color || ""}`.trim(),
        price: Number(it.price) || 0,
        list_price: Number(it.list_price || it.price) || 0,
        sale_price: Number(it.sale_price || it.price) || 0,
        discount: Math.max(0, Number(it.list_price || it.price) - Number(it.price)),
        sku: it.sku || it.stockCode || "",
        size: it.size || "", color: it.color || "",
        quantity: Number(it.quantity) || 1,
        coupon: appliedCoupon?.code || "",
      }));
      trackAddPaymentInfo({
        items: mappedItems,
        value: grandTotal,
        currency: "TRY",
        coupon: appliedCoupon?.code || "",
        discount, shipping: shippingCost, tax: 0,
        payment_type: key,
      });
    } catch (_) { /* silent */ }
  };

  // ----- Doğrulama (alan-içi hatalar) -----
  const validateAll = () => {
    const errs = {};
    const _email = (shippingAddress.email || user?.email || "").trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(_email)) errs.email = "Geçerli bir e-posta adresi girin";
    Object.assign(errs, validateAddress(shippingAddress, "ship"));
    if (!billingSameAsShipping) Object.assign(errs, validateAddress(billingAddress, "bill"));
    if (corporateInvoice) {
      if (!corporateData.company_name?.trim()) errs["corp.company_name"] = "Firma ünvanı gereklidir";
      if (!corporateData.tax_office?.trim()) errs["corp.tax_office"] = "Vergi dairesi gereklidir";
      const tn = (corporateData.tax_number || "").replace(/\D/g, "");
      if (tn.length !== 10 && tn.length !== 11) errs["corp.tax_number"] = "VKN (10 hane) veya TCKN (11 hane) girin";
      else if (tn.length === 11 && !isValidTCKN(tn)) errs["corp.tax_number"] = "Geçerli bir TC kimlik numarası girin";
    }
    if (paymentMethod === "credit_card") {
      const _n = card.number.replace(/\s/g, "");
      const _e = card.expiry.split("/");
      if (_n.length < 15) errs["card.number"] = "Geçerli bir kart numarası girin";
      if ((_e[0] || "").length !== 2 || (_e[1] || "").length !== 2 || Number(_e[0]) < 1 || Number(_e[0]) > 12) errs["card.expiry"] = "Son kullanma tarihini AA/YY biçiminde girin";
      if (card.cvc.length < 3) errs["card.cvc"] = "Güvenlik kodunu girin";
      if (!card.holder.trim()) errs["card.holder"] = "Kart üzerindeki ismi girin";
    }
    if (!acceptTerms) errs.terms = "Devam etmek için sözleşmeleri onaylamanız gerekir";
    return errs;
  };

  const focusFirstError = () => {
    setTimeout(() => {
      const el = document.querySelector('.gt-checkout [aria-invalid="true"]');
      if (el) {
        try { el.scrollIntoView({ behavior: "smooth", block: "center" }); } catch { /* jsdom */ }
        try { el.focus({ preventScroll: true }); } catch { /* yoksay */ }
      }
    }, 0);
  };

  // ----- Submit -----
  const handleSubmit = async (e) => {
    if (e?.preventDefault) e.preventDefault();
    setSubmitError("");
    if (items.length === 0) { setSubmitError("Sepetiniz boş"); return; }
    const errs = validateAll();
    setErrors(errs);
    if (Object.keys(errs).length > 0) {
      setSubmitError("Devam etmeden önce lütfen işaretli alanları düzeltin.");
      focusFirstError();
      return;
    }
    setLoading(true);
    try {
      const shipAddr = mergeAddressLine({ ...shippingAddress, email: shippingAddress.email || user?.email || "" });
      const billAddr = billingSameAsShipping
        ? { ...shipAddr }
        : mergeAddressLine({ ...billingAddress, email: shipAddr.email });
      const orderData = {
        user_id: user?.id || null,
        items: items.map((item) => ({
          product_id: item.productId, variant_id: item.variantId, quantity: item.quantity,
          category_id: item.categoryId,
          price: item.price, name: item.name, image: item.image, size: item.size, color: item.color,
        })),
        shipping_address: shipAddr,
        billing_address: billAddr,
        billing_same_as_shipping: billingSameAsShipping,
        billing_info: corporateInvoice ? {
          is_corporate: true,
          company_name: corporateData.company_name,
          tax_office: corporateData.tax_office,
          tax_number: corporateData.tax_number,
          e_invoice_user: corporateData.eInvoice_user,
        } : { is_corporate: false },
        subtotal: total,
        shipping_cost: shippingCost,
        discount, coupon_code: appliedCoupon?.code || "",
        gift_card_code: giftCardApplied?.code || "",
        applied_promotions: appliedPromotions,
        // Müşterinin "×" ile kaldırdığı kampanyalar SUNUCUYA da bildirilmeli.
        excluded_ids: excludedIds,
        gift_note: giftNote || "", gift_wrap: giftWrap, gift_wrap_price: giftWrapTotal,
        notes: orderNote.trim(),
        use_points: usePoints, points_used: pointsDeduction,
        use_3d_secure: use3DSecure,
        total: grandTotal,
        payment_method: paymentMethod,
        attribution_session_id:
          (typeof window !== "undefined" && (window.__STORE_SID__ || localStorage.getItem("store_sid"))) || null,
        // Reklam tıklama kimlikleri (ttclid/fbc/gclid …) — webhook CAPI purchase atfı için.
        click_ids: (typeof window !== "undefined" ? collectClickIds() : {}),
        // İYS — ticari ileti izni (kutu işaretliyse). SMS izni OTP doğrulaması ister.
        marketing_consent: { email: mktEmail, sms: mktSms, otp_verified: otpVerified },
        // KVKK: çerez bildirimindeki 'pazarlama' onayı — server Purchase CAPI buna göre.
        ad_tracking_consent: (() => {
          try { return !!JSON.parse(localStorage.getItem("store_cookie_consent") || "{}").marketing; }
          catch (_) { return false; }
        })(),
        // Çift sipariş koruması: aynı sepetin tekrar gönderimi yeni sipariş açmaz.
        idempotency_key: idemKeyRef.current,
      };

      // Üye girişliyse token'ı gönder ki sipariş user_id'ye bağlansın (misafirde token yok).
      const _authToken = localStorage.getItem("token");
      const orderRes = await axios.post(`${API}/orders`, orderData,
        _authToken ? { headers: { Authorization: `Bearer ${_authToken}` } } : undefined);
      const newOrderId = orderRes.data.order_id;
      setOrderId(newOrderId);
      const _successNum = orderRes.data.order_number || orderRes.data.order_id;

      // İdempotency: aynı sepet zaten ÖDENMİŞ bir siparişe bağlıysa tekrar ödeme başlatma.
      if (orderRes.data.idempotent && orderRes.data.payment_status === "paid") {
        setPaymentStep("success");
        clearCart();
        navigate(`/order-success/${_successNum}`, { replace: true });
        return;
      }

      // C2: Tutarın TAMAMI hediye çekiyle karşılandı → ödeme adımı atlanır.
      if (orderRes.data.payment_status === "paid" && Number(orderRes.data.total) === 0) {
        setPaymentStep("success");
        clearCart();
        navigate(`/order-success/${_successNum}`, { replace: true });
        return;
      }

      if (paymentMethod === "credit_card") {
        const _num = card.number.replace(/\s/g, "");
        const _exp = card.expiry.split("/");
        const cardPayload = {
          cardHolderName: card.holder.trim(),
          cardNumber: _num,
          expireMonth: (_exp[0] || "").trim(),
          expireYear: (_exp[1] || "").trim(),
          cvc: card.cvc.trim(),
        };
        // İYZİCO 3D SECURE ZORUNLU — TÜM kart ödemeleri 3DS ile başlatılır.
        const res = await axios.post(`${API}/payment/3ds/initialize`, {
          order_id: newOrderId,
          callback_url: `${API}/payment/3ds/callback`,
          return_url: `${window.location.origin}/odeme`,
          card: cardPayload,
          installment: selectedInstallment,
        });
        if (res.data.success && res.data.threeDSHtmlContent) {
          const html = window.atob(res.data.threeDSHtmlContent);
          document.open();
          document.write(html);
          document.close();
          return;
        }
        setLoading(false);
        setSubmitError(res.data.error || "Ödeme başlatılamadı");
        return;
      }

      trackPurchase({
        order_id: orderRes.data.order_number, total: grandTotal,
        items: analyticsItems(items, SITE_NAME),
        coupon: appliedCoupon?.code || "",
        discount, shipping: shippingCost, tax: 0,
        payment_type: paymentMethod,
        shipping_tier: shippingCost > 0 ? "Standart Kargo" : "Ücretsiz",
        user: buildUserInfo(),
      });
      // ÖNCE paymentStep'i "success"'e çevir (useEffect'in /sepet'e yönlendirmesini önler)
      setPaymentStep("success");
      _clearIdemKeys();  // sipariş alındı → idem anahtarlarını temizle
      clearCart();
      toast.success("Siparişiniz alındı!");
      // OrderSuccess havale ise banka bilgilerini kopyalanabilir gösterir.
      navigate(`/order-success/${_successNum}`, { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;
      setSubmitError(typeof detail === "string" ? detail : "Sipariş oluşturulamadı. Lütfen tekrar deneyin.");
      try { window.scrollTo({ top: 0, behavior: "smooth" }); } catch { /* jsdom */ }
    } finally {
      setLoading(false);
    }
  };

  // Boş sepet → /sepet'e yönlendir. Ödeme dönüşünde (?status=...) yönlendirme yapma.
  useEffect(() => {
    if (items.length === 0 && paymentStep === "form" && !searchParams.get("status")) {
      navigate("/sepet");
    }
  }, [items.length, paymentStep, navigate, searchParams]);

  if (items.length === 0 && paymentStep === "form" && !searchParams.get("status")) return null;

  if (paymentStep === "success" || paymentStep === "error" || paymentStep === "processing") {
    return (
      <CheckoutShell>
        <div className="gt-status" data-testid={`checkout-status-${paymentStep}`}>
          {paymentStep === "success" && (
            <>
              <div className="gt-status-icon is-ok" aria-hidden="true">✓</div>
              <h1 className="gt-h1">Ödemeniz başarılı!</h1>
              <p className="gt-muted">Siparişiniz alındı. Yönlendiriliyorsunuz…</p>
            </>
          )}
          {paymentStep === "error" && (
            <>
              <div className="gt-status-icon is-error" aria-hidden="true">!</div>
              <h1 className="gt-h1">Ödeme başarısız</h1>
              <p className="gt-muted">Kartınızdan çekim yapılmadı. Bilgilerinizi kontrol edip tekrar deneyebilirsiniz.</p>
              <button type="button" className="gt-btn gt-btn-primary" onClick={() => setPaymentStep("form")}>Tekrar dene</button>
            </>
          )}
          {paymentStep === "processing" && (
            <>
              <div className="gt-spinner gt-spinner-lg" aria-hidden="true" />
              <h1 className="gt-h1">Ödeme doğrulanıyor…</h1>
            </>
          )}
        </div>
        <CheckoutFooter />
      </CheckoutShell>
    );
  }

  const hasShippingAddress = !!(shippingAddress.city && shippingAddress.district && shippingAddress.address);
  const deliveryEstimate = estimateDelivery();
  const isCard = paymentMethod === "credit_card";

  return (
    <CheckoutShell>
      <form className="gt-co-layout" onSubmit={handleSubmit} noValidate>
        <OrderSummary
          items={items}
          open={summaryOpen}
          onToggle={() => setSummaryOpen((v) => !v)}
          couponCode={couponCode}
          onCouponChange={(v) => { setCouponCode(v); if (couponMsg?.type === "error") setCouponMsg(null); }}
          onApplyCode={applyCode}
          appliedCoupon={appliedCoupon}
          onRemoveCoupon={handleRemoveCoupon}
          giftCardBusy={giftCardBusy}
          couponMsg={couponMsg}
          giftCardEnabled={bizRules["giftcard.enabled"] !== false}
          giftCardApplied={giftCardApplied}
          onRemoveGiftCard={() => setGiftCardApplied(null)}
          giftCardDeduction={giftCardDeduction}
          appliedPromotions={appliedPromotions}
          eligiblePromotions={eligiblePromotions}
          visiblePromotions={visiblePromotions}
          autoPromoIds={AUTO_PROMO_IDS}
          onRemovePromotion={removePromotion}
          excludedIds={excludedIds}
          onResetExcluded={resetExcluded}
          shippingFree={shipping.free}
          listSum={listSum}
          productDisc={productDisc}
          shippingCost={shippingCost}
          baseShipFee={baseShipFee}
          deliveryEstimate={deliveryEstimate}
          bankTransferDiscount={bankTransferDiscount}
          bankPct={bankPct}
          paymentMethodDiscount={paymentMethodDiscount}
          paymentRuleLabel={_payRule?.label}
          pointsDeduction={pointsDeduction}
          giftWrap={giftWrap}
          giftWrapPrice={GIFT_WRAP_PRICE}
          codFee={codFee}
          chargeTotal={chargeTotal}
          isInstallmentSelected={isInstallmentSelected}
          selectedInstallment={selectedInstallment}
          perInstallmentAmount={perInstallmentAmount}
          installmentDiff={installmentDiff}
        />

        <main className="gt-co-main">
          <div className="gt-co-main-inner">
            {submitError && (
              <Banner title="Siparişiniz tamamlanamadı" testId="checkout-error-banner">{submitError}</Banner>
            )}

            {/* Express checkout: backend'de cüzdan (Apple/Google Pay) desteği yok → bölüm gösterilmez. */}

            <ContactSection
              user={user}
              email={shippingAddress.email || ""}
              onEmailChange={(v) => { setShippingAddress((p) => ({ ...p, email: v })); clearErr("email"); }}
              error={errors.email}
              mktEmail={mktEmail}
              setMktEmail={setMktEmail}
            />

            <Section title="Teslimat" testId="address-block">
              <AddressFields
                value={shippingAddress}
                onChange={updateShipping}
                errors={errors}
                prefix="ship"
                testIdPrefix="shipping"
                savedAddresses={user ? savedAddresses : []}
                onPickSaved={pickSavedShipping}
                phoneFooter={(
                  <SmsConsent
                    mktSms={mktSms}
                    onSmsChange={(c) => { setMktSms(c); if (!c) { setOtpSent(false); setOtpVerified(false); setOtpCode(""); } }}
                    otpSent={otpSent} otpCode={otpCode} setOtpCode={setOtpCode}
                    otpVerified={otpVerified} otpBusy={otpBusy} sendOtp={sendOtp} verifyOtp={verifyOtp}
                  />
                )}
              />
            </Section>

            <ShippingMethodSection
              hasAddress={hasShippingAddress}
              shippingCost={shippingCost}
              baseShipFee={baseShipFee}
              deliveryEstimate={deliveryEstimate}
              freeShippingThreshold={freeShippingThreshold}
              basis={shipping.basis}
            />

            <PaymentSection
              enabledPM={enabledPM}
              paymentMethod={paymentMethod}
              onSelectMethod={onSelectMethod}
              bankPct={bankPct}
              codFee={COD_FEE}
              card={card}
              setCard={(c) => {
                setCard(c);
                clearErr("card.holder", "card.number", "card.expiry", "card.cvc");
              }}
              errors={errors}
              installments={installments}
              selectedInstallment={selectedInstallment}
              setSelectedInstallment={setSelectedInstallment}
              grandTotal={grandTotal}
              userPoints={userPoints}
              usePoints={usePoints}
              setUsePoints={setUsePoints}
              loyaltyTier={loyaltyTier}
              pointsMaxPct={POINTS_MAX_PCT}
            />

            <BillingSection
              billingSameAsShipping={billingSameAsShipping}
              onSameChange={(same) => {
                setBillingSameAsShipping(same);
                if (same) setBillingAddress({ ...shippingAddress });
                else setBillingAddress({ ...emptyAddress });
              }}
              billingAddress={billingAddress}
              onBillingChange={updateBilling}
              errors={errors}
              savedAddresses={user ? savedAddresses : []}
              onPickSavedBilling={pickSavedBilling}
              corporateInvoice={corporateInvoice}
              setCorporateInvoice={(v) => { setCorporateInvoice(v); if (!v) clearErr("corp.company_name", "corp.tax_office", "corp.tax_number"); }}
              corporateData={corporateData}
              setCorporateData={(d) => { setCorporateData(d); clearErr("corp.company_name", "corp.tax_office", "corp.tax_number"); }}
            />

            <ExtrasSection
              giftWrap={giftWrap} setGiftWrap={setGiftWrap} giftWrapPrice={GIFT_WRAP_PRICE}
              giftNote={giftNote} setGiftNote={setGiftNote}
              orderNote={orderNote} setOrderNote={setOrderNote}
            />

            <div className="gt-agreements">
              <Checkbox checked={acceptTerms} onChange={(c) => { setAcceptTerms(c); if (c) clearErr("terms"); }}
                testId="accept-terms-checkbox" error={errors.terms} name="terms">
                <button type="button" className="gt-link" data-testid="open-distance-sales"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); setLegalDoc("mesafeli-satis"); }}>
                  Mesafeli Satış Sözleşmesi
                </button>
                {"'ni ve "}
                <button type="button" className="gt-link" data-testid="open-preinfo"
                  onClick={(e) => { e.preventDefault(); e.stopPropagation(); setLegalDoc("on-bilgilendirme"); }}>
                  Ön Bilgilendirme Formu
                </button>
                {"'nu okudum, onaylıyorum."}
              </Checkbox>
            </div>

            <button type="submit" className="gt-btn gt-btn-primary gt-btn-pay" disabled={loading} data-testid="place-order-btn" aria-busy={loading}>
              {loading
                ? <><span className="gt-spinner" aria-hidden="true" /> İşleniyor…</>
                : (isCard ? "Şimdi öde" : "Siparişi tamamla")}
            </button>
            <p className="gt-pay-hint">
              {isCard
                ? <>Ödeme tutarı: <strong>{formatTRY(chargeTotal)}</strong>{isInstallmentSelected ? ` (${selectedInstallment} taksit)` : ""}. Bankanızın 3D Secure ekranına yönlendirileceksiniz.</>
                : <>Ödenecek tutar: <strong>{formatTRY(chargeTotal)}</strong></>}
            </p>

            <CheckoutFooter />
          </div>
        </main>
      </form>

      {legalDoc && (
        <LegalModal slug={legalDoc} fallbackTitle={LEGAL_DOCS[legalDoc]} onClose={() => setLegalDoc(null)} />
      )}
    </CheckoutShell>
  );
}
