// Satır içi (Shopify) adres formu — teslimat ve fatura adresi için ortak.
import ProvinceDistrictSelect from "../ProvinceDistrictSelect";
import { Field, SelectField } from "./Fields";
import { sanitizePhone } from "./utils";

const addressLabel = (a) => {
  const name = `${a.first_name || ""} ${a.last_name || ""}`.trim();
  const head = a.title ? `${a.title} — ` : "";
  return `${head}${name}, ${a.address || ""} ${a.district || ""}/${a.city || ""}`.trim();
};

export default function AddressFields({
  value, onChange, errors = {}, prefix, testIdPrefix,
  savedAddresses = [], onPickSaved, phoneFooter,
}) {
  const a = value || {};
  const set = (k) => (v) => onChange({ [k]: v });
  const err = (k) => errors[`${prefix}.${k}`];
  const selectedSaved = savedAddresses.find((s) => s.id && s.id === a.id) ? a.id : "";

  return (
    <div className="gt-grid" data-testid={`${testIdPrefix}-address-fields`}>
      {savedAddresses.length > 0 && (
        <SelectField label="Kayıtlı adresler" value={selectedSaved} name={`${prefix}.saved`}
          testId={`${testIdPrefix}-saved-address`} className="gt-col-2"
          onChange={(id) => onPickSaved(savedAddresses.find((s) => s.id === id) || null)}>
          <option value="">Yeni adres kullan</option>
          {savedAddresses.map((s) => <option key={s.id} value={s.id}>{addressLabel(s)}</option>)}
        </SelectField>
      )}
      <SelectField label="Ülke/Bölge" value="TR" onChange={() => {}} className="gt-col-2" name={`${prefix}.country`}>
        <option value="TR">Türkiye</option>
      </SelectField>
      <Field label="Ad" value={a.first_name} onChange={set("first_name")} error={err("first_name")}
        name={`${prefix}.first_name`} autoComplete={`${prefix === "ship" ? "shipping" : "billing"} given-name`}
        testId={`${testIdPrefix}-first-name`} />
      <Field label="Soyad" value={a.last_name} onChange={set("last_name")} error={err("last_name")}
        name={`${prefix}.last_name`} autoComplete={`${prefix === "ship" ? "shipping" : "billing"} family-name`}
        testId={`${testIdPrefix}-last-name`} />
      <Field label="Adres (mahalle, cadde, sokak, no)" value={a.address} onChange={set("address")} error={err("address")}
        name={`${prefix}.address`} className="gt-col-2" autoComplete={`${prefix === "ship" ? "shipping" : "billing"} address-line1`}
        testId={`${testIdPrefix}-address`} />
      <Field label="Apartman, daire vb. (isteğe bağlı)" value={a.address2} onChange={set("address2")}
        name={`${prefix}.address2`} className="gt-col-2" autoComplete={`${prefix === "ship" ? "shipping" : "billing"} address-line2`}
        testId={`${testIdPrefix}-address2`} />
      <div className={`gt-col-2 gt-pds-wrap ${err("city") || err("district") ? "has-error" : ""}`} data-field={`${prefix}.city`}>
        <ProvinceDistrictSelect
          city={a.city}
          district={a.district}
          onChange={({ city, district }) => onChange({ city, district })}
          className="gt-pds"
          selectClass="gt-input gt-pds-input"
          labelClass="gt-pds-label"
          testIdPrefix={testIdPrefix}
        />
        {(err("city") || err("district")) && (
          <div className="gt-pds-errors">
            <p className="gt-field-error" role="alert">{err("city") || ""}</p>
            <p className="gt-field-error" role="alert">{err("district") || ""}</p>
          </div>
        )}
      </div>
      <Field label="Posta kodu (isteğe bağlı)" value={a.postal_code} onChange={(v) => set("postal_code")(v.replace(/\D/g, "").slice(0, 5))}
        name={`${prefix}.postal_code`} inputMode="numeric" autoComplete={`${prefix === "ship" ? "shipping" : "billing"} postal-code`}
        testId={`${testIdPrefix}-postal-code`} />
      <Field label="Telefon" type="tel" value={a.phone} onChange={(v) => set("phone")(sanitizePhone(v))} error={err("phone")}
        name={`${prefix}.phone`} inputMode="tel" autoComplete={`${prefix === "ship" ? "shipping" : "billing"} tel`}
        testId={`${testIdPrefix}-phone`}
        suffix={<span className="gt-help-dot" title="Kargo firması teslimat için arayabilir">?</span>} />
      {phoneFooter && <div className="gt-col-2">{phoneFooter}</div>}
    </div>
  );
}
