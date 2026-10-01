// Checkout sol sütun bölümleri (İletişim, Kargo yöntemi, Fatura, Ek seçenekler, Sözleşmeler).
import { useState } from "react";
import { Link } from "react-router-dom";
import AddressFields from "./AddressFields";
import { Checkbox, Field, RadioList, Section } from "./Fields";
import { formatTRY } from "./utils";

/* ───────── İletişim ───────── */
export function ContactSection({ user, email, onEmailChange, error, mktEmail, setMktEmail }) {
  return (
    <Section title="İletişim" testId="contact-block"
      aside={!user ? <Link to="/giris?redirect=/odeme" className="gt-link" data-testid="checkout-login-link">Giriş yap</Link> : null}>
      {user ? (
        <div className="gt-account-box" data-testid="contact-account">
          <span className="gt-avatar" aria-hidden="true">{(user.email || "?").slice(0, 1).toUpperCase()}</span>
          <div>
            <p className="gt-account-email">{user.email}</p>
            <p className="gt-muted gt-small">Sipariş onayı ve faturanız bu adrese gönderilir.</p>
          </div>
        </div>
      ) : (
        <Field label="E-posta" type="email" value={email} onChange={onEmailChange} error={error}
          name="email" autoComplete="email" testId="contact-email" />
      )}
      <Checkbox checked={mktEmail} onChange={setMktEmail} testId="consent-email" className="gt-mt-sm">
        E-posta ile kampanya ve fırsatlardan haberdar et
      </Checkbox>
    </Section>
  );
}

/* ───────── SMS izni + OTP (İYS) — telefon alanının altında ───────── */
export function SmsConsent({ mktSms, onSmsChange, otpSent, otpCode, setOtpCode, otpVerified, otpBusy, sendOtp, verifyOtp }) {
  return (
    <div className="gt-sms-consent">
      <Checkbox checked={mktSms} onChange={onSmsChange} testId="consent-sms">
        SMS ile kampanya ve fırsatlardan haberdar et
        {mktSms && !otpVerified && <span className="gt-warn"> (telefon doğrulaması gerekir)</span>}
        {otpVerified && <span className="gt-ok"> ✓ doğrulandı</span>}
      </Checkbox>
      {mktSms && !otpVerified && (
        <div className="gt-otp" data-testid="otp-box">
          {!otpSent ? (
            <button type="button" className="gt-btn gt-btn-secondary gt-btn-sm" onClick={sendOtp} disabled={otpBusy}>
              {otpBusy ? "Gönderiliyor…" : "Doğrulama kodu gönder"}
            </button>
          ) : (
            <>
              <Field label="6 haneli kod" value={otpCode} onChange={setOtpCode} inputMode="numeric" maxLength={6} className="gt-otp-field" />
              <button type="button" className="gt-btn gt-btn-primary gt-btn-sm" onClick={verifyOtp} disabled={otpBusy}>{otpBusy ? "…" : "Doğrula"}</button>
              <button type="button" className="gt-link gt-small" onClick={sendOtp} disabled={otpBusy}>Tekrar gönder</button>
            </>
          )}
        </div>
      )}
      <p className="gt-fineprint">
        İzniniz İYS'ye (İleti Yönetim Sistemi) kaydedilir. İstediğiniz zaman{" "}
        <a href="https://iys.org.tr" target="_blank" rel="noreferrer">iys.org.tr</a> üzerinden, her e-postadaki
        "abonelikten çık" bağlantısından ya da SMS'e "RET" yazarak izni iptal edebilirsiniz.
      </p>
    </div>
  );
}

/* ───────── Kargo yöntemi ───────── */
export function ShippingMethodSection({ hasAddress, shippingCost, baseShipFee, deliveryEstimate, freeShippingThreshold, basis }) {
  const remaining = freeShippingThreshold ? Math.max(0, freeShippingThreshold - basis) : 0;
  return (
    <Section title="Kargo yöntemi" testId="shipping-method-block">
      {!hasAddress && (
        <p className="gt-placeholder-box" data-testid="shipping-method-placeholder">
          Kargo seçeneklerini görmek için teslimat adresinizi girin.
        </p>
      )}
      {hasAddress && (
        <RadioList name="shipping_method" value="standard" onChange={() => {}} testId="shipping-methods"
          options={[{
            value: "standard",
            label: "Standart Kargo",
            description: `Tahmini teslimat: ${deliveryEstimate} · 2-4 iş günü`,
            aside: shippingCost === 0
              ? <strong data-testid="shipping-method-price">Ücretsiz</strong>
              : <strong data-testid="shipping-method-price">{formatTRY(shippingCost)}</strong>,
          }]} />
      )}
      {freeShippingThreshold > 0 && shippingCost > 0 && remaining > 0 && (
        <p className="gt-hint gt-free-hint" data-testid="free-shipping-hint">
          {formatTRY(freeShippingThreshold)} ve üzeri siparişlerde kargo ücretsiz — <strong>{formatTRY(remaining)}</strong> daha ekleyin.
        </p>
      )}
      {baseShipFee > 0 && shippingCost === 0 && hasAddress && (
        <p className="gt-hint gt-ok">Siparişiniz ücretsiz kargo kapsamında.</p>
      )}
    </Section>
  );
}

/* ───────── Fatura adresi + fatura türü (bireysel/kurumsal) ───────── */
export function BillingSection({
  billingSameAsShipping, onSameChange, billingAddress, onBillingChange, errors, savedAddresses, onPickSavedBilling,
  corporateInvoice, setCorporateInvoice, corporateData, setCorporateData,
}) {
  const corpErr = (k) => errors[`corp.${k}`];
  return (
    <Section title="Fatura adresi" testId="billing-block">
      <RadioList name="billing_same" value={billingSameAsShipping ? "same" : "different"}
        onChange={(v) => onSameChange(v === "same")} testId="billing-same-list"
        options={[
          { value: "same", label: "Teslimat adresiyle aynı", testId: "same-billing-checkbox" },
          {
            value: "different", label: "Farklı bir fatura adresi kullan", testId: "different-billing-option",
            content: (
              <AddressFields value={billingAddress} onChange={onBillingChange} errors={errors} prefix="bill"
                testIdPrefix="billing" savedAddresses={savedAddresses} onPickSaved={onPickSavedBilling} />
            ),
          },
        ]} />

      <div className="gt-subsection" data-testid="corporate-invoice-block">
        <p className="gt-label-sm">Fatura türü</p>
        <RadioList name="invoice_type" value={corporateInvoice ? "corporate" : "individual"}
          onChange={(v) => setCorporateInvoice(v === "corporate")} testId="invoice-type"
          options={[
            { value: "individual", label: "Bireysel", testId: "invoice-individual" },
            {
              value: "corporate", label: "Kurumsal", testId: "corporate-invoice-checkbox",
              content: (
                <div className="gt-grid" data-testid="corporate-invoice-fields">
                  <Field label="Firma ünvanı" value={corporateData.company_name} name="corp.company_name" className="gt-col-2"
                    error={corpErr("company_name")} testId="corp-company-name-input"
                    onChange={(v) => setCorporateData({ ...corporateData, company_name: v })} />
                  <Field label="VKN / TCKN" value={corporateData.tax_number} name="corp.tax_number" inputMode="numeric"
                    error={corpErr("tax_number")} testId="corp-tax-number-input"
                    onChange={(v) => setCorporateData({ ...corporateData, tax_number: v.replace(/\D/g, "").slice(0, 11) })} />
                  <Field label="Vergi dairesi" value={corporateData.tax_office} name="corp.tax_office"
                    error={corpErr("tax_office")} testId="corp-tax-office-input"
                    onChange={(v) => setCorporateData({ ...corporateData, tax_office: v })} />
                  <div className="gt-col-2">
                    <Checkbox checked={corporateData.eInvoice_user} testId="corp-einvoice-user"
                      onChange={(c) => setCorporateData({ ...corporateData, eInvoice_user: c })}>
                      Şirketim e-Fatura mükellefidir (e-Fatura kesilsin)
                    </Checkbox>
                  </div>
                </div>
              ),
            },
          ]} />
      </div>
    </Section>
  );
}

/* ───────── Hediye paketi + sipariş notu ───────── */
export function ExtrasSection({ giftWrap, setGiftWrap, giftWrapPrice, giftNote, setGiftNote, orderNote, setOrderNote }) {
  const [noteOpen, setNoteOpen] = useState(!!orderNote);
  return (
    <Section title="Ek seçenekler" testId="gift-options-section">
      <div className="gt-extras">
        <Checkbox checked={giftWrap} onChange={setGiftWrap} testId="gift-wrap-toggle">
          Hediye paketi <span className="gt-muted">(+{formatTRY(giftWrapPrice)})</span>
        </Checkbox>
        {giftWrap && (
          <div className="gt-textarea-wrap">
            <label className="gt-label-sm" htmlFor="gt-gift-note">Hediye notu (isteğe bağlı)</label>
            <textarea id="gt-gift-note" className="gt-input gt-textarea" rows={2} value={giftNote}
              onChange={(e) => setGiftNote(e.target.value.slice(0, 300))} data-testid="gift-note-input" />
          </div>
        )}
        <div data-testid="order-note-section">
          <Checkbox checked={noteOpen || !!orderNote} onChange={(c) => { setNoteOpen(c); if (!c) setOrderNote(""); }} testId="order-note-toggle">
            Siparişe not ekle
          </Checkbox>
          {(noteOpen || !!orderNote) && (
            <div className="gt-textarea-wrap">
              <label className="gt-label-sm" htmlFor="gt-order-note">Sipariş notu</label>
              <textarea id="gt-order-note" className="gt-input gt-textarea" rows={3} value={orderNote}
                placeholder="Örn. teslimat saati tercihi, kapı/zil bilgisi"
                onChange={(e) => setOrderNote(e.target.value.slice(0, 500))} data-testid="order-note-input" />
              <p className="gt-hint gt-row-hint">
                <span>Bu not hediye notundan farklıdır — yalnız ekibimiz görür.</span>
                <span>{orderNote.length}/500</span>
              </p>
            </div>
          )}
        </div>
      </div>
    </Section>
  );
}
