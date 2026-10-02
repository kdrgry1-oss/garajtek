// Hızlı Sipariş satır ayrıştırıcı (pages/QuickOrder.jsx).

/** "KOD, ADET" / "KOD ADET" / "KOD;ADET" / "KOD<TAB>ADET" satırlarını ayrıştırır (adet yoksa 1). */
export function parseQuickLines(text) {
  return String(text || "").split(/\r?\n/).map((l) => l.trim()).filter(Boolean).map((l) => {
    const m = l.match(/^(.+?)[\s,;\t]+(\d{1,4})$/);
    return m ? { code: m[1].trim(), qty: Number(m[2]) } : { code: l, qty: 1 };
  }).slice(0, 300);
}
