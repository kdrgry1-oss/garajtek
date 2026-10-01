// Sağ sütun (masaüstü) / üst açılır bar (mobil) — Shopify sipariş özeti.
import { cartLineView } from "../../lib/price";
import { formatTRY } from "./utils";

const TagIcon = () => (
  <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M1 2.5A1.5 1.5 0 0 1 2.5 1h4.38a1.5 1.5 0 0 1 1.06.44l6.62 6.62a1.5 1.5 0 0 1 0 2.12l-4.38 4.38a1.5 1.5 0 0 1-2.12 0L1.44 7.94A1.5 1.5 0 0 1 1 6.88V2.5ZM4.5 6a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" /></svg>
);

function LineItem({ item }) {
  const lv = cartLineView(item);
  const variant = [item.size, item.color].filter(Boolean).join(" / ");
  return (
    <li className="gt-line" data-testid="summary-line">
      <div className="gt-line-thumb">
        {item.image ? <img src={item.image} alt={item.name} loading="lazy" /> : <span className="gt-line-noimg" />}
        <span className="gt-line-qty" aria-label={`Adet: ${item.quantity}`}>{item.quantity}</span>
      </div>
      <div className="gt-line-info">
        <p className="gt-line-name">{item.name}</p>
        {variant && <p className="gt-line-variant">{variant}</p>}
      </div>
      <div className="gt-line-price">
        {lv.hasDiscount && <s>{formatTRY(lv.listUnit * item.quantity)}</s>}
        <span>{formatTRY(lv.unit * item.quantity)}</span>
      </div>
    </li>
  );
}

export default function OrderSummary({
  items, open, onToggle,
  // indirim kodu
  couponCode, onCouponChange, onApplyCode, appliedCoupon, onRemoveCoupon, giftCardBusy, couponMsg,
  // hediye çeki
  giftCardEnabled, giftCardApplied, onRemoveGiftCard, giftCardDeduction,
  // kampanyalar
  appliedPromotions, eligiblePromotions, visiblePromotions, autoPromoIds, onRemovePromotion,
  excludedIds, onResetExcluded, shippingFree,
  // tutarlar
  listSum, productDisc, shippingCost, baseShipFee, deliveryEstimate,
  bankTransferDiscount, bankPct, paymentMethodDiscount, paymentRuleLabel, pointsDeduction,
  giftWrap, giftWrapPrice, codFee, chargeTotal, isInstallmentSelected, selectedInstallment,
  perInstallmentAmount, installmentDiff,
}) {
  const itemCount = items.reduce((s, it) => s + (Number(it.quantity) || 0), 0);
  const showPromos = appliedPromotions.length > 0 || eligiblePromotions.length > 0;

  return (
    <aside className={`gt-summary ${open ? "is-open" : ""}`} data-testid="order-summary">
      {/* Mobil: Shopify tarzı açılır üst bar */}
      <button type="button" className="gt-summary-toggle" onClick={onToggle} aria-expanded={open}
        aria-controls="gt-summary-body" data-testid="summary-toggle">
        <span className="gt-summary-toggle-label">
          {open ? "Sipariş özetini gizle" : "Sipariş özetini göster"}
          <svg viewBox="0 0 10 6" width="11" height="7" aria-hidden="true" className="gt-chev"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" /></svg>
        </span>
        <span className="gt-summary-toggle-total" data-testid="summary-toggle-total">{formatTRY(chargeTotal)}</span>
      </button>

      <div className="gt-summary-body" id="gt-summary-body" data-testid="summary-body">
        <ul className="gt-lines">
          {items.map((it) => <LineItem key={it.id} item={it} />)}
        </ul>

        {/* TEK KUTU: indirim VEYA hediye çeki kodu — ne girilirse otomatik algılanır */}
        <div className="gt-discount">
          <div className="gt-discount-row">
            <div className={`gt-field ${couponCode ? "is-filled" : ""} ${couponMsg?.type === "error" ? "has-error" : ""}`}>
              <div className="gt-field-control">
                <input id="gt-discount-code" className="gt-input" placeholder=" " value={couponCode}
                  onChange={(e) => onCouponChange(e.target.value.toUpperCase())}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      if (!appliedCoupon && !giftCardBusy && couponCode.trim()) onApplyCode(couponCode);
                    }
                  }}
                  aria-invalid={couponMsg?.type === "error" ? "true" : undefined}
                  data-testid="manual-coupon-input" />
                <label htmlFor="gt-discount-code" className="gt-float-label">İndirim kodu veya hediye kartı</label>
              </div>
            </div>
            {appliedCoupon
              ? <button type="button" className="gt-btn gt-btn-secondary" onClick={onRemoveCoupon} data-testid="remove-coupon-btn">Kaldır</button>
              : <button type="button" className="gt-btn gt-btn-secondary" onClick={() => onApplyCode(couponCode)}
                  disabled={giftCardBusy || !couponCode.trim()} data-testid="apply-coupon-btn">
                  {giftCardBusy ? "…" : "Uygula"}
                </button>}
          </div>
          {couponMsg && (
            <p className={couponMsg.type === "error" ? "gt-field-error" : "gt-field-ok"} role={couponMsg.type === "error" ? "alert" : "status"} data-testid="coupon-message">
              {couponMsg.text}
            </p>
          )}

          {giftCardEnabled && giftCardApplied && (
            <div className="gt-chips">
              <span className="gt-chip" data-testid="gift-card-applied">
                <TagIcon />
                {giftCardApplied.kind === "credit" ? "Mağaza kredisi" : "Hediye çeki"} {giftCardApplied.code}
                {" · "}
                {giftCardApplied.value_type === "percent"
                  ? `%${giftCardApplied.percent}${giftCardApplied.max_amount > 0 ? ` (en fazla ${formatTRY(giftCardApplied.max_amount)})` : ""}`
                  : `bakiye ${formatTRY(giftCardApplied.balance)}`}
                <button type="button" onClick={onRemoveGiftCard} aria-label="Hediye çekini kaldır" data-testid="remove-gift-card-btn">×</button>
              </span>
            </div>
          )}

          {showPromos && (
            <div className="gt-chips" data-testid="applied-promotions">
              {visiblePromotions.map((p, i) => (
                <span key={p.coupon_id || p.code || i} className="gt-chip">
                  <TagIcon />
                  <span className="gt-chip-text">{p.title || p.code}{p.free_shipping && shippingFree ? " · Ücretsiz Kargo" : ""}</span>
                  {Number(p.discount) > 0 && <span className="gt-chip-amt">-{formatTRY(p.discount)}</span>}
                  {!autoPromoIds.includes(p.coupon_id) && (
                    <button type="button" onClick={() => onRemovePromotion(p)} title="Kampanyayı kaldır" aria-label="Kaldır">×</button>
                  )}
                </span>
              ))}
              {excludedIds.length > 0 && (
                <button type="button" className="gt-link gt-small" onClick={onResetExcluded}>Kaldırılan kampanyaları geri al</button>
              )}
            </div>
          )}
        </div>

        <div className="gt-totals">
          <div className="gt-row"><span>Ara toplam · {itemCount} ürün</span><span>{formatTRY(listSum)}</span></div>
          {productDisc > 0.001 && (
            <div className="gt-row gt-row-discount"><span>Ürün fiyat indirimi</span><span>-{formatTRY(productDisc)}</span></div>
          )}
          <div data-testid="promotion-totals" className="gt-rows">
            {visiblePromotions.filter((p) => Number(p.discount) > 0).map((p, i) => (
              <div key={p.coupon_id || i} className="gt-row gt-row-discount">
                <span><TagIcon /> {p.title || p.code}</span><span>-{formatTRY(p.discount)}</span>
              </div>
            ))}
          </div>
          <div className="gt-row" data-testid="shipping-cost">
            <span>Kargo</span>
            {shippingCost === 0
              ? <span>{baseShipFee > 0 && <s className="gt-muted">{formatTRY(baseShipFee)}</s>} <strong>Ücretsiz</strong></span>
              : <span>{formatTRY(shippingCost)}</span>}
          </div>
          <div className="gt-row gt-row-sub" data-testid="delivery-estimate">
            <span>Tahmini teslimat</span><span>{deliveryEstimate}</span>
          </div>
          {bankTransferDiscount > 0 && (
            <div className="gt-row gt-row-discount" data-testid="bank-discount-row"><span>Havale/EFT indirimi (%{bankPct})</span><span>-{formatTRY(bankTransferDiscount)}</span></div>
          )}
          {paymentMethodDiscount > 0 && (
            <div className="gt-row gt-row-discount"><span>{paymentRuleLabel || "Ödeme indirimi"}</span><span>-{formatTRY(paymentMethodDiscount)}</span></div>
          )}
          {pointsDeduction > 0 && <div className="gt-row gt-row-discount"><span>Puan kullanımı</span><span>-{formatTRY(pointsDeduction)}</span></div>}
          {giftCardDeduction > 0 && (
            <div className="gt-row gt-row-discount" data-testid="gift-card-row"><span>Hediye çeki ({giftCardApplied?.code})</span><span>-{formatTRY(giftCardDeduction)}</span></div>
          )}
          {giftWrap && <div className="gt-row"><span>Hediye paketi</span><span>{formatTRY(giftWrapPrice)}</span></div>}
          {codFee > 0 && <div className="gt-row" data-testid="cod-fee-row"><span>Kapıda ödeme hizmet bedeli</span><span>{formatTRY(codFee)}</span></div>}

          <div className="gt-row gt-row-total" data-testid="grand-total">
            <span>{isInstallmentSelected ? `Toplam (${selectedInstallment} taksit)` : "Toplam"}</span>
            <span><small>TRY</small> <strong>{formatTRY(chargeTotal)}</strong></span>
          </div>
          {isInstallmentSelected && (
            <div className="gt-row gt-row-sub"><span>Aylık ödeme</span><span>{selectedInstallment} × {formatTRY(perInstallmentAmount)}</span></div>
          )}
          {isInstallmentSelected && installmentDiff > 0 && (
            <div className="gt-row gt-row-sub"><span>Vade farkı</span><span>+{formatTRY(installmentDiff)}</span></div>
          )}
          <p className="gt-tax-note">Tüm fiyatlara KDV dahildir.</p>
        </div>
      </div>
    </aside>
  );
}
