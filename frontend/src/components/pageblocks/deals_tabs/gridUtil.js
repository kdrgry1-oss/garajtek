// Grup B ızgara yardımcıları: cihaz başına sütun sayısı (CSS değişkeni) ve satır sonu ayırıcı sınıfları.
// Kırılımlar SPEC §2.4 ile aynı: mobil <768, tablet 768–1199, masaüstü ≥1200.
import "./style.css";

const num = (v, d) => { const n = Number(v); return n > 0 ? Math.min(12, Math.round(n)) : d; };

/** responsive sayı ({desktop,tablet,mobile} veya düz sayı) → {desktop,tablet,mobile} */
export function colCounts(v, fallback = { desktop: 4, tablet: 3, mobile: 2 }) {
  if (v && typeof v === "object") {
    const desktop = num(v.desktop, fallback.desktop);
    const tablet = num(v.tablet, Math.min(desktop, fallback.tablet));
    return { desktop, tablet, mobile: num(v.mobile, Math.min(tablet, fallback.mobile)) };
  }
  const d = num(v, fallback.desktop);
  return { desktop: d, tablet: Math.min(d, fallback.tablet), mobile: Math.min(d, fallback.mobile) };
}

export const colsStyle = (c) => ({ "--pdb-cd": c.desktop, "--pdb-ct": c.tablet, "--pdb-cm": c.mobile });

/** Satırın son kartının sağ ayırıcısını gizleyen Electro sınıfları. */
export function dividerClasses(i, c) {
  const n = i + 1;
  const out = [];
  if (n % c.mobile === 0) out.push("remove-divider-sm-down");
  if (n % c.tablet === 0) out.push("remove-divider-md-lg");
  if (n % c.desktop === 0) out.push("remove-divider-xl", "remove-divider-wd");
  return out.join(" ");
}
