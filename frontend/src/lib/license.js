// Copyright (c) 2026 kdrgry1-oss. Tüm hakları saklıdır. Bkz. LICENSE.
// Lisans kilidi (tarayıcı tarafı): arayüz YALNIZ lisanslı alan adında (garajtek.com ve alt alan
// adları) ya da yerel geliştirmede açılır. Sunucu tarafında da aynı kilit vardır (backend/licensing.py).
export const LICENSED_DOMAIN = "garajtek.com";
const LOCAL = new Set(["localhost", "127.0.0.1", "::1", "[::1]"]);

export function isLicensedHostname(hostname) {
  const h = String(hostname || "").toLowerCase().replace(/\.$/, "");
  return h === LICENSED_DOMAIN || h.endsWith(`.${LICENSED_DOMAIN}`) || LOCAL.has(h);
}

export function licenseOk() {
  try { return isLicensedHostname(window.location.hostname); } catch { return false; }
}
