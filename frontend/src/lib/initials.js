/**
 * Avatar baş harfleri — Türkçe büyük harf kuralıyla ("ilker şahin" → "İŞ").
 * String#toUpperCase dile duyarsız olduğu için "i" → "I" (noktasız) olurdu.
 */
export const trUpper = (s) => String(s || "").toLocaleUpperCase("tr-TR");

export const initialsOf = (u) => {
  const a = (u?.first_name || "").trim();
  const b = (u?.last_name  || "").trim();
  if (a || b) return trUpper((a[0] || "") + (b[0] || ""));
  const e = u?.email || "";
  return e ? trUpper(e.slice(0, 2)) : "FA";
};
