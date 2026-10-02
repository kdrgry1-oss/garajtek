// Grup B ortak fırsat parçaları (deals_tabs + deals_carousel). Şablon v1.0 `section-onsale-product`
// görünümü: koyu kazanç kutusu (110×65 #343f49), "Satılan / Kalan" stok çubuğu, gri kutulu geri sayım.
// Her panel metni data-pd-field taşır; ürün verisi .product-item / data-pd-data altında.
import { Link } from "react-router-dom";
import { useProductActions } from "../../ProductCard";
import { useCountdown } from "../_shared/Countdown";
import { fmtPrice, priceOf } from "../../electro/format";
import { optimizeImg, firstImage } from "../../../lib/img";
import { sanitizeHtml } from "../../../lib/sanitizeHtml";
import Placeholder from "../_shared/Placeholder";
import "./style.css";

export function stockOf(p) {
  if (!p) return 0;
  return (p.variants || []).length ? p.variants.reduce((s, v) => s + (Number(v.stock) || 0), 0) : Number(p.stock) || 0;
}

/** Kazanç tutarı: elle girilmişse o, değilse liste − satış fiyatı. */
export function savingsAmount(savings, product) {
  if (!savings) return "";
  if (savings.mode === "manual") return savings.amount || "";
  if (!product) return "";
  const pv = priceOf(product);
  return pv.list - pv.display > 0 ? fmtPrice(pv.list - pv.display) : "";
}

export function stockValues(stock, product) {
  if (stock?.mode === "manual") return { sold: Number(stock.sold) || 0, available: Number(stock.available) || 0 };
  return { sold: Number(product?.sold_count || product?.sales_count || 0), available: stockOf(product) };
}

/** v1 koyu kazanç kutusu (veya v2 ana renkli daire: shape="circle"). */
export function SavingsBox({ savings, amount, field, shape = "box" }) {
  if (!savings?.show || !amount) return null;
  const style = savings.color ? { backgroundColor: savings.color } : undefined;
  if (shape === "circle") {
    return (
      <div className="d-flex align-items-center flex-column justify-content-center bg-primary rounded-pill height-75 width-75 text-lh-1 flex-shrink-0"
        style={style} data-testid="savings-badge">
        <span className="font-size-12" data-pd-field={`${field}.label`}>{savings.label}</span>
        <div className="font-size-20 font-weight-bold text-nowrap" data-pd-data="">{amount}</div>
      </div>
    );
  }
  return (
    <div className="pdb-savings" style={style} data-testid="savings-badge">
      <span className="pdb-savings__text">
        <span data-pd-field={`${field}.label`}>{savings.label}</span>
        <span className="pdb-savings__amount" data-pd-data="">{amount}</span>
      </span>
    </div>
  );
}

/** v1 stok: solda "Satılan: 2", sağda "Kalan: 26" + yuvarlak çubuk. */
export function StockV1({ stock, sold, available, field }) {
  if (!stock?.show) return null;
  const total = sold + available;
  const pct = total > 0 ? Math.round((sold / total) * 100) : 0;
  return (
    <div className="pdb-progress" data-testid="stock-bar">
      <div className="pdb-progress__stock">
        <span className="pdb-progress__sold"><span data-pd-field={`${field}.sold_label`}>{stock.sold_label}</span> <strong data-pd-data="">{sold}</strong></span>
        <span className="pdb-progress__available"><span data-pd-field={`${field}.available_label`}>{stock.available_label}</span> <strong data-pd-data="">{available}</strong></span>
      </div>
      <div className="pdb-progress__track"><span className="pdb-progress__bar" style={{ width: `${Math.min(100, Math.max(8, pct))}%` }} /></div>
    </div>
  );
}

const UNITS = ["days", "hours", "minutes", "seconds"];
const pad2 = (n) => String(n).padStart(2, "0");

/** v1 geri sayım: `.countdown > span.<birim> > span.value + b` (0 gün gizli, ":" ayırıcı). */
export function CountdownV1({ value, field }) {
  const cd = value || {};
  const st = useCountdown(cd);
  if (!cd.enabled) return null;
  if (st.expired && (cd.on_expire === "hide_timer" || cd.on_expire === "hide_block")) return null;
  const heading = cd.heading ? <div className="pdb-cd__heading" data-pd-field={`${field}.heading`}>{cd.heading}</div> : null;
  if (st.expired && cd.on_expire === "show_text") {
    return <div className="pdb-cd">{heading}<div className="pdb-cd__expired" data-pd-field={`${field}.expired_text`}>{cd.expired_text}</div></div>;
  }
  let units = (cd.units && cd.units.length ? cd.units : UNITS).filter((u) => UNITS.includes(u));
  if (cd.hide_zero_days && st.days === 0) units = units.filter((u) => u !== "days");
  const val = (u) => (u === "hours" && !units.includes("days") ? st.hours + st.days * 24 : st[u]);
  return (
    <div className="pdb-cd" data-testid="deal-countdown">
      {heading}
      <div className="pdb-cd__boxes" aria-live="off">
        {units.map((u) => (
          <span key={u} className={`pdb-cd__unit ${u}`}>
            <span className="pdb-cd__value">{cd.pad === false ? val(u) : pad2(val(u))}</span>
            <b data-pd-field={`${field}.labels.${u}`}>{(cd.labels || {})[u]}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

/** Ürün görseli (görsel geçersiz kılma → ürün görseli → yer tutucu). */
export function DealImage({ image, product, size = [250, 232], width = 600, field, className = "" }) {
  const src = image?.url || firstImage(product);
  if (!src) return <Placeholder size={size} field={field} className={className} />;
  return (
    <span className={`pdb-img ${className}`} style={{ aspectRatio: `${size[0]} / ${size[1]}` }} {...(image?.url ? { "data-pd-field": field } : {})}>
      <img src={optimizeImg(src, width)} alt={image?.alt || product?.name || ""} loading="lazy" width={size[0]} height={size[1]} />
    </span>
  );
}

/** v1 fırsat ürünü gövdesi: görsel + başlık (ürün adı veya geçersiz kılma) + fiyat. */
export function OnsaleBody({ product, titleOverride, titleField, image, imageField, listName = "deal", link, hideImage = false }) {
  const a = useProductActions(product, { listName });
  const pv = priceOf(product);
  const href = link || a.href;
  const clean = sanitizeHtml(titleOverride || "");
  return (
    <div className="pdb-onsale__product" data-pd-data="product" data-testid={`product-card-${product.id}`}>
      <Link to={href} onClick={a.select} className="d-block">
        {!hideImage && <div className="pdb-onsale__thumb"><DealImage image={image} product={product} field={imageField} /></div>}
        {clean ? <h3 className="pdb-onsale__name" data-pd-field={titleField} dangerouslySetInnerHTML={{ __html: clean }} />
          : <h3 className="pdb-onsale__name">{product.name}</h3>}
      </Link>
      <span className="pdb-price">
        <ins>{fmtPrice(pv.display)}</ins>
        {pv.hasDiscount && <del>{fmtPrice(pv.list)}</del>}
      </span>
    </div>
  );
}

/** v2.0 index "Special Offer" gövdesi (320×300 görsel, ortalı ad, del + 30 px kırmızı fiyat). */
export function DealBodyV2({ product, titleHtml, image, link, listName = "special_offer" }) {
  const a = useProductActions(product, { listName });
  const pv = priceOf(product);
  const href = link || a.href;
  const clean = sanitizeHtml(titleHtml || "");
  return (
    <div data-pd-data="product" data-testid={`product-card-${product.id}`}>
      <div className="mb-4">
        <Link to={href} onClick={a.select} className="d-block text-center">
          <DealImage image={image} product={product} size={[320, 300]} width={640} field="deal.image_override" />
        </Link>
      </div>
      <h5 className="mb-2 font-size-14 text-center mx-auto max-width-180 text-lh-18">
        {clean ? <Link to={href} onClick={a.select} className="text-blue font-weight-bold" data-pd-field="deal.title_override" dangerouslySetInnerHTML={{ __html: clean }} />
          : <Link to={href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link>}
      </h5>
      <div className="d-flex align-items-center justify-content-center mb-3">
        {pv.hasDiscount && <del className="font-size-18 mr-2 text-gray-2">{fmtPrice(pv.list)}</del>}
        <ins className="font-size-30 text-red text-decoration-none">{fmtPrice(pv.display)}</ins>
      </div>
    </div>
  );
}
