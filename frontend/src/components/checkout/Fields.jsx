// Shopify tarzı form ilkel bileşenleri: yüzen etiketli input/select, checkbox, radio listesi,
// hata bannerı. Tüm stiller pages/checkout.css içinde `.gt-checkout` kapsamındadır.
import { useId } from "react";

function FieldError({ id, error }) {
  if (!error) return null;
  return (
    <p className="gt-field-error" id={id} role="alert">
      <svg viewBox="0 0 20 20" aria-hidden="true" width="14" height="14"><path fill="currentColor" d="M10 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm-.75-11.5v4.5h1.5V6.5h-1.5Zm0 6v1.5h1.5V12.5h-1.5Z" /></svg>
      <span>{error}</span>
    </p>
  );
}

/** Yüzen etiketli metin alanı — etiket input içinde durur, odak/doluyken küçülüp yukarı kayar. */
export function Field({ label, value, onChange, error, name, type = "text", className = "", testId, suffix, ...rest }) {
  const id = useId();
  const errId = `${id}-err`;
  const filled = value !== undefined && value !== null && String(value) !== "";
  return (
    <div className={`gt-field ${filled ? "is-filled" : ""} ${error ? "has-error" : ""} ${className}`} data-field={name}>
      <div className="gt-field-control">
        <input
          id={id}
          name={name}
          type={type}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder=" "
          aria-invalid={error ? "true" : undefined}
          aria-describedby={error ? errId : undefined}
          data-testid={testId}
          className="gt-input"
          {...rest}
        />
        <label htmlFor={id} className="gt-float-label">{label}</label>
        {suffix && <span className="gt-field-suffix">{suffix}</span>}
      </div>
      <FieldError id={errId} error={error} />
    </div>
  );
}

/** Yüzen etiketli select (Shopify: etiket her zaman üstte küçük). */
export function SelectField({ label, value, onChange, children, error, name, className = "", testId, disabled }) {
  const id = useId();
  return (
    <div className={`gt-field is-filled is-select ${error ? "has-error" : ""} ${className}`} data-field={name}>
      <div className="gt-field-control">
        <select id={id} name={name} value={value} disabled={disabled}
          onChange={(e) => onChange(e.target.value)} className="gt-input gt-select" data-testid={testId}
          aria-invalid={error ? "true" : undefined}>
          {children}
        </select>
        <label htmlFor={id} className="gt-float-label">{label}</label>
        <svg className="gt-select-caret" viewBox="0 0 10 6" aria-hidden="true"><path d="M1 1l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.5" /></svg>
      </div>
      <FieldError id={`${id}-err`} error={error} />
    </div>
  );
}

export function Checkbox({ checked, onChange, children, testId, error, name, className = "" }) {
  const id = useId();
  return (
    <div className={`gt-check-wrap ${className}`} data-field={name}>
      <label className="gt-check" htmlFor={id}>
        <input id={id} type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)}
          data-testid={testId} aria-invalid={error ? "true" : undefined} />
        <span className="gt-check-box" aria-hidden="true">
          <svg viewBox="0 0 12 10"><path d="M1 5l3.5 3.5L11 1.5" fill="none" stroke="currentColor" strokeWidth="2" /></svg>
        </span>
        <span className="gt-check-label">{children}</span>
      </label>
      <FieldError id={`${id}-err`} error={error} />
    </div>
  );
}

/**
 * Shopify tarzı gruplanmış radyo listesi. Seçili satır vurgulanır; seçili satırın `content`'i
 * satırın hemen altında gri alanda açılır.
 * options: [{ value, label, description?, aside?, content?, testId? }]
 */
export function RadioList({ name, value, onChange, options, testId }) {
  return (
    <div className="gt-radio-list" role="radiogroup" data-testid={testId}>
      {options.map((o) => {
        const selected = o.value === value;
        return (
          <div key={o.value} className={`gt-radio-item ${selected ? "is-selected" : ""}`} data-testid={o.testId}>
            <label className="gt-radio-row">
              <input type="radio" name={name} value={o.value} checked={selected}
                onChange={() => onChange(o.value)} />
              <span className="gt-radio-dot" aria-hidden="true" />
              <span className="gt-radio-text">
                <span className="gt-radio-label">{o.label}</span>
                {o.description && <span className="gt-radio-desc">{o.description}</span>}
              </span>
              {o.aside && <span className="gt-radio-aside">{o.aside}</span>}
            </label>
            {selected && o.content && (
              <div className="gt-radio-content" data-testid={o.testId ? `${o.testId}-content` : undefined}>{o.content}</div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function Banner({ tone = "critical", title, children, testId }) {
  return (
    <div className={`gt-banner gt-banner-${tone}`} role={tone === "critical" ? "alert" : "status"} data-testid={testId}>
      <svg viewBox="0 0 20 20" aria-hidden="true" width="18" height="18"><path fill="currentColor" d="M10 18a8 8 0 1 1 0-16 8 8 0 0 1 0 16Zm-.75-11.5v4.5h1.5V6.5h-1.5Zm0 6v1.5h1.5V12.5h-1.5Z" /></svg>
      <div>
        {title && <p className="gt-banner-title">{title}</p>}
        {children && <div className="gt-banner-body">{children}</div>}
      </div>
    </div>
  );
}

export function Section({ title, subtitle, aside, children, testId }) {
  return (
    <section className="gt-section" data-testid={testId}>
      {(title || aside) && (
        <div className="gt-section-head">
          {title && <h2 className="gt-h2">{title}</h2>}
          {aside && <div className="gt-section-aside">{aside}</div>}
        </div>
      )}
      {subtitle && <p className="gt-section-sub">{subtitle}</p>}
      {children}
    </section>
  );
}
