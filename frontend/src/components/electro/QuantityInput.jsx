// Electro "js-quantity" adet kutusu (border rounded-pill + / -).
export default function QuantityInput({ value, onChange, min = 1, max = 9999, testId, small = false }) {
  const set = (n) => onChange(Math.max(min, Math.min(max, Number.isFinite(n) ? n : min)));
  return (
    <div className={`border rounded-pill py-1 ${small ? "width-100" : "width-122"} w-xl-80 px-3 border-color-1`} data-testid={testId}>
      <div className="js-quantity row align-items-center">
        <div className="col">
          <input className="js-result form-control h-auto border-0 rounded p-0 shadow-none" type="text" inputMode="numeric"
            aria-label="Adet" value={value}
            onChange={(e) => set(parseInt(e.target.value.replace(/\D/g, ""), 10))} />
        </div>
        <div className="col-auto pr-1">
          <button type="button" className="js-minus btn btn-icon btn-xs btn-outline-secondary rounded-circle border-0" onClick={() => set(value - 1)} disabled={value <= min} aria-label="Azalt" data-testid={testId ? `${testId}-minus` : undefined}>
            <small className="fas fa-minus btn-icon__inner" />
          </button>
          <button type="button" className="js-plus btn btn-icon btn-xs btn-outline-secondary rounded-circle border-0" onClick={() => set(value + 1)} disabled={value >= max} aria-label="Artır" data-testid={testId ? `${testId}-plus` : undefined}>
            <small className="fas fa-plus btn-icon__inner" />
          </button>
        </div>
      </div>
    </div>
  );
}
