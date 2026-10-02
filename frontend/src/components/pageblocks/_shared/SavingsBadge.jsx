// Kazanç rozeti: ana renkli daire içinde "Kazancınız / 1.250 ₺".
export default function SavingsBadge({ label, amount, field = "savings", size = 75 }) {
  if (!amount) return null;
  return (
    <div className="d-flex align-items-center flex-column justify-content-center bg-primary rounded-pill text-lh-1 flex-shrink-0"
      style={{ width: size, height: size }} data-testid="savings-badge">
      <span className="font-size-12" data-pd-field={`${field}.label`}>{label}</span>
      <div className="font-size-15 font-weight-bold text-nowrap" data-pd-data="">{amount}</div>
    </div>
  );
}
