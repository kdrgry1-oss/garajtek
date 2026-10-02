// Ürün sayfası — "Kapıda Ödeme ile Hemen Al" (hızlı kapıda ödeme siparişi; sayfadaki birincil eylem).
// Görünürlük: kapıda ödeme ayarlardan AÇIK + ürün/seçenek kapıda ödemeye uygun + stokta.
// Tutar /api/storefront/cod-quote ile sipariş kurallarıyla aynı hesaplanır; sipariş NORMAL
// POST /api/orders yolundan (payment_method=cash_on_delivery, misafir) açılır → stok, kapıda
// ödeme kuralları, hizmet bedeli, tutar doğrulaması, idempotency, e-posta/SMS, atıf aynen işler.
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import ProvinceDistrictSelect from "../ProvinceDistrictSelect";
import LegalModal from "../checkout/LegalModal";
import { useCodInfo, useCodCheck } from "../../lib/cod";
import { collectClickIds } from "../../lib/dataLayer";
import { trackPurchase } from "../../utils/pixelEvents";
import { fmtPrice } from "../electro/format";
import "../sets/sets.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LEGAL = { "on-bilgilendirme": "Ön Bilgilendirme Formu", "mesafeli-satis": "Mesafeli Satış Sözleşmesi" };

/** "0 (5xx) xxx xx xx" → 10 hane (5 ile başlar) */
export function normalizeTrPhone(v) {
  let d = String(v || "").replace(/\D/g, "");
  if (d.startsWith("90") && d.length >= 12) d = d.slice(2);
  if (d.startsWith("0")) d = d.slice(1);
  return d.slice(0, 10);
}
export function formatTrPhone(v) {
  const d = normalizeTrPhone(v);
  const p = [d.slice(0, 3), d.slice(3, 6), d.slice(6, 8), d.slice(8, 10)].filter(Boolean);
  return p.length ? `0 (${p[0]}${p[0].length === 3 ? ")" : ""}${p[1] ? ` ${p[1]}` : ""}${p[2] ? ` ${p[2]}` : ""}${p[3] ? ` ${p[3]}` : ""}` : "";
}
export const isValidTrMobile = (v) => /^5\d{9}$/.test(normalizeTrPhone(v));

export function validateCodForm(f) {
  const e = {};
  const parts = String(f.name || "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) e.name = "Ad ve soyadınızı girin";
  if (!isValidTrMobile(f.phone)) e.phone = "Geçerli bir cep telefonu girin (5XX XXX XX XX)";
  if (!f.city) e.city = "İl seçin";
  if (!f.district) e.district = "İlçe seçin";
  if (String(f.address || "").trim().length < 10) e.address = "Açık adresinizi girin (mahalle, cadde, no)";
  if (f.email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.trim())) e.email = "Geçerli bir e-posta girin";
  if (!f.acceptPre) e.acceptPre = "Ön Bilgilendirme Formu'nu onaylayın";
  if (!f.acceptContract) e.acceptContract = "Mesafeli Satış Sözleşmesi'ni onaylayın";
  return e;
}

/** POST /api/orders gövdesi — kasa ile aynı şema (misafir, kapıda ödeme). */
export function buildCodOrderPayload(form, quote, idemKey) {
  const parts = String(form.name || "").trim().split(/\s+/);
  const last = parts.length > 1 ? parts.pop() : "";
  const addr = {
    first_name: parts.join(" "), last_name: last, phone: normalizeTrPhone(form.phone),
    email: (form.email || "").trim(), city: form.city, district: form.district,
    address: String(form.address || "").trim(), country: "Türkiye",
  };
  return {
    user_id: null,
    items: (quote.lines || []).map((l) => ({
      product_id: l.product_id, variant_id: l.variant_id || null, quantity: l.quantity, price: l.price,
      name: l.name, image: l.image, size: l.size || null, category_id: l.category_id || null,
      ...(l.set_id ? { set_id: l.set_id, set_slot: l.set_slot } : {}),
    })),
    shipping_address: addr, billing_address: { ...addr }, billing_same_as_shipping: true,
    billing_info: { is_corporate: false },
    subtotal: quote.subtotal, shipping_cost: quote.shipping, discount: quote.discount,
    coupon_code: "", applied_promotions: [], excluded_ids: [],
    notes: String(form.note || "").trim().slice(0, 500),
    total: quote.total, payment_method: "cash_on_delivery",
    marketing_consent: { email: !!(form.mktEmail && form.email), sms: false, otp_verified: false },
    idempotency_key: idemKey, source_detail: "pdp_cod_quick_order",
  };
}

function useQuote(open, product, variant, qty, email) {
  const [q, setQ] = useState(null);
  useEffect(() => {
    if (!open) return undefined;
    let alive = true;
    const t = setTimeout(() => {
      axios.post(`${API}/storefront/cod-quote`, { product_id: product.id, variant_id: variant?.id || null, quantity: qty, email })
        .then((r) => { if (alive) setQ(r.data); })
        .catch((e) => { if (alive) setQ({ available: false, reason: e?.response?.data?.detail || "Tutar hesaplanamadı" }); });
    }, 200);
    return () => { alive = false; clearTimeout(t); };
  }, [open, product.id, variant?.id, qty, email]);
  return q;
}

function CodOrderModal({ product, variant, initialQty, onClose }) {
  const navigate = useNavigate();
  const [qty, setQty] = useState(Math.max(1, Number(initialQty) || 1));
  const [f, setF] = useState({ name: "", phone: "", city: "", district: "", address: "", email: "", note: "",
    acceptPre: false, acceptContract: false, mktEmail: false });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [legal, setLegal] = useState(null);
  const idem = useRef(`codq-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`);
  const quote = useQuote(true, product, variant, qty, f.email);
  const set = (k, v) => { setF((p) => ({ ...p, [k]: v })); setErrors((e) => ({ ...e, [k]: undefined })); };
  const isSet = product.product_type === "set";
  const maxQty = isSet ? Math.max(1, Number(product.stock) || 1) : Math.max(1, Number(variant ? variant.stock : product.stock) || 1);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape" && !legal) onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, legal]);

  const legalCtx = useMemo(() => ({
    buyer: { name: f.name, address: [f.address, f.district, f.city].filter(Boolean).join(", "), phone: formatTrPhone(f.phone), email: f.email, invoice: f.name },
    order: {
      date: new Date().toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }),
      items: (quote?.lines || []).map((l) => ({ name: l.name, quantity: l.quantity, price: l.price, size: l.size })),
      subtotal: quote?.subtotal, discount: quote?.discount, shipping: (quote?.shipping || 0) + (quote?.cod_fee || 0),
      total: quote?.total, payment: "Kapıda ödeme",
    },
  }), [f, quote]);

  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    const v = validateCodForm(f);
    setErrors(v);
    if (Object.keys(v).length) return;
    if (!quote || !quote.available) { setErr(quote?.reason || "Kapıda ödeme bu sipariş için kullanılamıyor."); return; }
    setBusy(true);
    setErr("");
    try {
      const body = buildCodOrderPayload(f, quote, idem.current);
      body.attribution_session_id = (typeof window !== "undefined" && (window.__STORE_SID__ || localStorage.getItem("store_sid"))) || null;
      body.click_ids = collectClickIds();
      body.ad_tracking_consent = (() => { try { return !!JSON.parse(localStorage.getItem("store_cookie_consent") || "{}").marketing; } catch { return false; } })();
      const r = await axios.post(`${API}/orders`, body);
      const num = r.data.order_number || r.data.order_id;
      try {
        trackPurchase({ order_id: num, total: quote.total, items: body.items.map((i) => ({ ...i, productId: i.product_id })),
          discount: quote.discount, shipping: quote.shipping, tax: 0, payment_type: "cash_on_delivery",
          shipping_tier: quote.shipping > 0 ? "Standart Kargo" : "Ücretsiz" });
      } catch { /* analitik sessiz */ }
      navigate(`/order-success/${num}`);
    } catch (ex) {
      const d = ex?.response?.data?.detail;
      setErr(typeof d === "string" ? d : "Sipariş oluşturulamadı. Lütfen tekrar deneyin.");
      setBusy(false);
    }
  };

  const fe = (k) => (errors[k] ? <div className="gt-codq-err">{errors[k]}</div> : null);
  return createPortal(
    <div className="gt-codq-overlay electro" role="dialog" aria-modal="true" aria-label="Kapıda ödeme ile sipariş" data-testid="cod-quick-modal">
      <div className="gt-codq">
        <div className="gt-codq-head">
          <span className="el-cod-ico"><i className="fas fa-hand-holding-usd" /></span>
          <h3>Kapıda Ödeme ile Sipariş Ver</h3>
          <button type="button" className="gt-codq-x" onClick={onClose} aria-label="Kapat" data-testid="cod-quick-close">×</button>
        </div>
        <form onSubmit={submit} noValidate className="gt-codq-body">
          <div className="gt-codq-product">
            <img src={product.images?.[0] || "/placeholder.jpg"} alt="" width="56" height="56" />
            <div className="flex-grow-1">
              <div className="font-weight-bold font-size-14">{product.name}</div>
              {variant?.size && <div className="font-size-12 text-gray-90">{variant.size}</div>}
              {isSet && <div className="font-size-12 text-gray-90">Setin tamamı ({(quote?.lines || []).length} ürün)</div>}
            </div>
            <div className="gt-codq-qty">
              <button type="button" onClick={() => setQty((n) => Math.max(1, n - 1))} aria-label="Azalt">−</button>
              <input value={qty} inputMode="numeric" data-testid="cod-quick-qty"
                onChange={(e) => setQty(Math.max(1, Math.min(maxQty, parseInt(e.target.value, 10) || 1)))} />
              <button type="button" onClick={() => setQty((n) => Math.min(maxQty, n + 1))} aria-label="Artır">+</button>
            </div>
          </div>

          <div className="gt-codq-grid">
            <label className="gt-codq-f full">Ad Soyad
              <input value={f.name} onChange={(e) => set("name", e.target.value)} autoComplete="name" data-testid="cod-quick-name" />{fe("name")}
            </label>
            <label className="gt-codq-f full">Cep Telefonu
              <input value={formatTrPhone(f.phone)} onChange={(e) => set("phone", normalizeTrPhone(e.target.value))} inputMode="tel"
                autoComplete="tel" placeholder="0 (5XX) XXX XX XX" data-testid="cod-quick-phone" />{fe("phone")}
            </label>
            <div className="gt-codq-f full">
              <ProvinceDistrictSelect city={f.city} district={f.district} testIdPrefix="cod-quick"
                onChange={({ city, district }) => { setF((p) => ({ ...p, city, district })); setErrors((x) => ({ ...x, city: undefined, district: undefined })); }}
                className="gt-codq-pds" selectClass="gt-codq-input" labelClass="gt-codq-label" />
              {fe("city") || fe("district")}
            </div>
            <label className="gt-codq-f full">Açık Adres
              <textarea rows={2} value={f.address} onChange={(e) => set("address", e.target.value)} autoComplete="street-address"
                placeholder="Mahalle, cadde/sokak, bina ve daire no" data-testid="cod-quick-address" />{fe("address")}
            </label>
            <label className="gt-codq-f">E-posta <span className="text-gray-5">(isteğe bağlı)</span>
              <input type="email" value={f.email} onChange={(e) => set("email", e.target.value)} autoComplete="email" data-testid="cod-quick-email" />{fe("email")}
            </label>
            <label className="gt-codq-f">Sipariş notu <span className="text-gray-5">(isteğe bağlı)</span>
              <input value={f.note} onChange={(e) => set("note", e.target.value)} maxLength={500} />
            </label>
          </div>

          <div className="gt-codq-sum" data-testid="cod-quick-summary">
            {!quote ? <div className="text-gray-90 font-size-13">Tutar hesaplanıyor…</div> : quote.lines ? (
              <>
                <div className="gt-codq-row"><span>Ürün tutarı</span><span>{fmtPrice(quote.subtotal)}</span></div>
                {(quote.promotions || []).map((p) => (
                  <div className="gt-codq-row text-green" key={p.title}><span>{p.title}</span><span>-{fmtPrice(p.discount)}</span></div>
                ))}
                <div className="gt-codq-row"><span>Kargo</span><span>{quote.shipping > 0 ? fmtPrice(quote.shipping) : "Ücretsiz"}</span></div>
                <div className="gt-codq-row"><span>Kapıda ödeme hizmet bedeli</span><span>{quote.cod_fee > 0 ? fmtPrice(quote.cod_fee) : "Ücretsiz"}</span></div>
                <div className="gt-codq-row is-total"><span>Toplam (KDV dahil)</span><strong data-testid="cod-quick-total">{fmtPrice(quote.total)}</strong></div>
              </>
            ) : null}
            {quote && !quote.available && <div className="gt-codq-err mt-1" data-testid="cod-quick-unavailable">{quote.reason}</div>}
          </div>

          <label className="gt-codq-check">
            <input type="checkbox" checked={f.acceptPre} onChange={(e) => set("acceptPre", e.target.checked)} data-testid="cod-quick-accept-pre" />
            <span><a href="#on-bilgilendirme" onClick={(e) => { e.preventDefault(); setLegal("on-bilgilendirme"); }}>Ön Bilgilendirme Formu</a>'nu okudum, onaylıyorum.</span>
          </label>{fe("acceptPre")}
          <label className="gt-codq-check">
            <input type="checkbox" checked={f.acceptContract} onChange={(e) => set("acceptContract", e.target.checked)} data-testid="cod-quick-accept-contract" />
            <span><a href="#mesafeli-satis" onClick={(e) => { e.preventDefault(); setLegal("mesafeli-satis"); }}>Mesafeli Satış Sözleşmesi</a>'ni okudum, onaylıyorum.</span>
          </label>{fe("acceptContract")}
          <label className="gt-codq-check">
            <input type="checkbox" checked={f.mktEmail} onChange={(e) => set("mktEmail", e.target.checked)} disabled={!f.email} />
            <span>Kampanya ve fırsatlardan e-posta ile haberdar olmak istiyorum (İYS).</span>
          </label>
          <p className="font-size-12 text-gray-90 mb-2">Kişisel verileriniz <a href="/sayfa/kvkk" target="_blank" rel="noopener noreferrer">KVKK Aydınlatma Metni</a> kapsamında işlenir.</p>

          {err && <div className="gt-set-notice mb-2" role="alert" data-testid="cod-quick-error">{err}</div>}
          <button type="submit" className="btn btn-primary-dark-w btn-block gt-codq-submit" disabled={busy || !quote || !quote.available}
            data-testid="cod-quick-submit">
            {busy ? "Sipariş oluşturuluyor…" : <>Siparişi Tamamla{quote?.total ? ` — ${fmtPrice(quote.total)}` : ""}</>}
          </button>
          <p className="font-size-12 text-gray-90 text-center mt-2 mb-0">Ödemeyi teslimatta kargo görevlisine yaparsınız.</p>
        </form>
      </div>
      {legal && <LegalModal slug={legal} fallbackTitle={LEGAL[legal]} onClose={() => setLegal(null)} orderContext={legalCtx} />}
    </div>,
    document.body,
  );
}

/** Buton (+ modal). Kapıda ödeme kapalıysa / ürün uygun değilse / stokta yoksa HİÇ görünmez. */
export default function CodQuickOrder({ product, variant = null, quantity = 1, compact = false }) {
  const info = useCodInfo();
  const [open, setOpen] = useState(false);
  const ids = product?.product_type === "set" ? (product.set_items || []).map((i) => i.product_id) : [product?.id];
  const check = useCodCheck(info?.enabled ? ids : [], Math.max(Number(product?.price) || 0, Number(info?.min_total) || 0));
  if (!product || !info || !info.enabled) return null;
  if (check.available === false && (check.blocked || []).length) return null;
  const hasVariants = (product.variants || []).length > 0 && product.product_type !== "set";
  const stock = hasVariants ? Number(variant?.stock || 0) : Number(product.stock || 0);
  if (stock <= 0) return null;
  const needChoice = hasVariants && !variant;
  return (
    <>
      {compact ? (
        <button type="button" className="btn btn-sm px-3 py-2 rounded-pill font-size-13 el-cod-btn" onClick={() => setOpen(true)}
          disabled={needChoice} data-testid="sticky-cod-order">
          <i className="fas fa-hand-holding-usd mr-1" />Kapıda Öde
        </button>
      ) : (
        <button type="button" className="btn btn-block el-cod-btn el-cod-btn--main mb-3" onClick={() => setOpen(true)}
          disabled={needChoice} title={needChoice ? "Önce seçenek seçin" : undefined} data-testid="pdp-cod-order-btn">
          <span className="el-cod-btn-title"><i className="fas fa-hand-holding-usd mr-2" />Kapıda Ödeme ile Hemen Al</span>
          <span className="el-cod-btn-sub">{needChoice ? "Önce seçenek seçin" : "Kargoda nakit veya kartla öde"}</span>
        </button>
      )}
      {open && <CodOrderModal product={product} variant={variant} initialQty={quantity} onClose={() => setOpen(false)} />}
    </>
  );
}
