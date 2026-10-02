// Stok çubuğu (section-onsale-product): "Satılan: 2  Kalan: 26" + ana renkli doluluk çubuğu.
export default function StockBar({ sold = 0, available = 0, soldLabel, availableLabel, field = "stock", className = "mb-3 mx-2" }) {
  const total = Number(sold) + Number(available);
  const pct = total > 0 ? Math.round((Number(sold) / total) * 100) : 0;
  return (
    <div className={className} data-testid="stock-bar">
      <div className="d-flex justify-content-between align-items-center mb-2">
        <span><span data-pd-field={`${field}.available_label`}>{availableLabel}</span> <strong>{available}</strong></span>
        <span><span data-pd-field={`${field}.sold_label`}>{soldLabel}</span> <strong>{sold}</strong></span>
      </div>
      <div className="rounded-pill bg-gray-3 height-20 position-relative">
        <span className="position-absolute left-0 top-0 bottom-0 rounded-pill bg-primary" style={{ width: `${Math.min(100, Math.max(8, pct))}%` }} />
      </div>
    </div>
  );
}
