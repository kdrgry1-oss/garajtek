// "Ödeme" bölümü — Shopify radyo listesi; seçili yöntemin içeriği satır içinde açılır.
import BankTransferInfo from "../BankTransferInfo";
import CardBrandIcons from "./CardBrandIcons";
import { Field, RadioList, Section, Checkbox } from "./Fields";
import { detectCardBrand, formatTRY } from "./utils";

const LockSmall = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M8 1a3.5 3.5 0 0 0-3.5 3.5V6H4a1.5 1.5 0 0 0-1.5 1.5v6A1.5 1.5 0 0 0 4 15h8a1.5 1.5 0 0 0 1.5-1.5v-6A1.5 1.5 0 0 0 12 6h-.5V4.5A3.5 3.5 0 0 0 8 1Zm2 5H6V4.5a2 2 0 1 1 4 0V6Z" /></svg>
);

function CardForm({
  card, setCard, errors, installments, selectedInstallment, setSelectedInstallment, grandTotal,
  userPoints, usePoints, setUsePoints, loyaltyTier, pointsMaxPct,
}) {
  const upd = (patch) => setCard({ ...card, ...patch });
  return (
    <div className="gt-card-form" data-testid="card-form">
      <div className="gt-grid">
        <Field label="Kart numarası" value={card.number} name="card.number" className="gt-col-2"
          inputMode="numeric" autoComplete="cc-number" error={errors["card.number"]} testId="card-number"
          onChange={(v) => { const d = v.replace(/\D/g, "").slice(0, 16); upd({ number: d.replace(/(.{4})/g, "$1 ").trim() }); }}
          suffix={<LockSmall />} />
        <Field label="Son kullanma (AA/YY)" value={card.expiry} name="card.expiry"
          inputMode="numeric" autoComplete="cc-exp" error={errors["card.expiry"]} testId="card-expiry"
          onChange={(v) => { let d = v.replace(/\D/g, "").slice(0, 4); if (d.length >= 3) d = d.slice(0, 2) + "/" + d.slice(2); upd({ expiry: d }); }} />
        <Field label="Güvenlik kodu" value={card.cvc} name="card.cvc"
          inputMode="numeric" autoComplete="cc-csc" error={errors["card.cvc"]} testId="card-cvc"
          onChange={(v) => upd({ cvc: v.replace(/\D/g, "").slice(0, 4) })} />
        <Field label="Kart üzerindeki isim" value={card.holder} name="card.holder" className="gt-col-2"
          autoComplete="cc-name" error={errors["card.holder"]} testId="card-holder"
          onChange={(v) => upd({ holder: v.toUpperCase() })} />
      </div>

      <div className="gt-installments" data-testid="installments">
        <p className="gt-label-sm">Taksit seçenekleri</p>
        <div className="gt-inst-grid">
          {installments.map((opt) => (
            <button type="button" key={opt.number} onClick={() => setSelectedInstallment(opt.number)}
              className={`gt-inst ${selectedInstallment === opt.number ? "is-selected" : ""}`}
              aria-pressed={selectedInstallment === opt.number}>
              <span className="gt-inst-title">{opt.number === 1 ? "Tek çekim" : `${opt.number} taksit`}</span>
              <span className="gt-inst-sub">
                {formatTRY(opt.totalPrice ?? grandTotal)}
                {opt.number > 1 && opt.installmentPrice ? ` · ${opt.number} × ${formatTRY(opt.installmentPrice)}` : ""}
              </span>
            </button>
          ))}
        </div>
        {installments.length <= 1 && (
          <p className="gt-hint">Taksit seçenekleri kart numaranızın ilk 6 hanesi girildiğinde görünür.</p>
        )}
      </div>

      {/* 3D Secure ZORUNLU (iyzico kuralı) — kapatılamaz; bilgi amaçlı statik rozet. */}
      <p className="gt-secure-note"><LockSmall /> Ödemeniz 3D Secure ile güvenle alınır. Kart bilgileriniz iyzico altyapısıyla şifreli işlenir, sitemizde saklanmaz.</p>

      {userPoints > 0 && (
        <div data-testid="use-points-toggle">
          <Checkbox checked={usePoints} onChange={setUsePoints}>
            <strong>{formatTRY(userPoints)}</strong> puan kullan
            {loyaltyTier && (
              <span className={`gt-tier gt-tier-${loyaltyTier}`}>
                {loyaltyTier === "platinum" ? "PLATINUM" : loyaltyTier === "gold" ? "GOLD" : "SILVER"}
              </span>
            )}
            <span className="gt-muted"> (sepetin en fazla %{pointsMaxPct}'i)</span>
          </Checkbox>
        </div>
      )}
    </div>
  );
}

export default function PaymentSection(props) {
  const { enabledPM, paymentMethod, onSelectMethod, bankPct, codFee, card, codNote } = props;
  const brand = detectCardBrand(card.number);

  const options = [];
  if (enabledPM.bank_transfer) {
    options.push({
      value: "bank_transfer",
      testId: "pm-bank_transfer",
      label: "Havale / EFT",
      description: bankPct > 0 ? <span className="gt-badge-discount">%{bankPct} indirim</span> : null,
      content: (
        <div className="gt-pm-content">
          <p>
            {bankPct > 0
              ? <>Havale/EFT ile ödemede sepetinize <strong>%{bankPct} indirim</strong> uygulanır. </>
              : null}
            Siparişinizi tamamladıktan sonra aşağıdaki hesaba ödeme yapın ve açıklamaya <strong>sipariş numaranızı</strong> yazın.
            Ödemeniz onaylanınca siparişiniz hazırlanır.
          </p>
          <div className="gt-bank-info"><BankTransferInfo /></div>
        </div>
      ),
    });
  }
  if (enabledPM.credit_card) {
    options.push({
      value: "credit_card",
      testId: "pm-credit_card",
      label: "Kredi / Banka Kartı",
      aside: <CardBrandIcons active={paymentMethod === "credit_card" ? brand : ""} />,
      content: <CardForm {...props} />,
    });
  }
  if (enabledPM.cash_on_delivery) {
    options.push({
      value: "cash_on_delivery",
      testId: "pm-cash_on_delivery",
      label: "Kapıda Ödeme",
      aside: codFee > 0 ? <span className="gt-muted">+{formatTRY(codFee)}</span> : null,
      content: (
        <div className="gt-pm-content">
          <p>Ödemeyi teslimat sırasında kargo görevlisine yaparsınız.
            {codFee > 0 && <> Kapıda ödeme hizmet bedeli: <strong>{formatTRY(codFee)}</strong>.</>}
          </p>
        </div>
      ),
    });
  }

  return (
    <Section title="Ödeme" subtitle="Tüm işlemler güvenli ve şifrelidir." testId="payment-block">
      {options.length === 0
        ? <p className="gt-muted">Şu anda aktif bir ödeme yöntemi bulunmuyor.</p>
        : <RadioList name="payment" value={paymentMethod} onChange={onSelectMethod} options={options} testId="payment-methods" />}
      {codNote ? <p className="gt-muted gt-cod-note" data-testid="checkout-cod-note">Kapıda ödeme: {codNote}</p> : null}
    </Section>
  );
}
