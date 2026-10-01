/**
 * Beyaz etiket — mağaza kimliği (ad, alan adı, iletişim, sosyal hesaplar).
 *
 * Kaynak sırası:
 *   1) Çalışma anı: GET /api/settings → tenant_config (admin "Ayarlar"dan düzenlenir).
 *   2) Build-time env: REACT_APP_SITE_NAME / REACT_APP_SITE_URL (ilk boya + SEO için).
 *   3) Nötr varsayılan ("Mağaza").
 * Koda firma-özel değer (ad, e-posta, telefon, IBAN, sosyal hesap) GÖMÜLMEZ.
 * Çalışma anı mağaza bilgisi için: lib/storeInfo.js → useStoreInfo().
 */
export const SITE_NAME = (process.env.REACT_APP_SITE_NAME || "").trim() || "Mağaza";
export const SITE_URL = (process.env.REACT_APP_SITE_URL || "").trim().replace(/\/+$/, "");
export const SITE_HOST = (() => {
  try { return SITE_URL ? new URL(SITE_URL).hostname.replace(/^www\./, "") : ""; } catch { return ""; }
})();

/** Sosyal hesap değeri tam URL değilse (ör. "@magaza" / "magaza") URL'ye çevirir. */
export function socialUrl(kind, value) {
  const v = String(value || "").trim();
  if (!v) return "";
  if (/^https?:\/\//i.test(v)) return v;
  const h = v.replace(/^@/, "");
  if (kind === "instagram") return `https://www.instagram.com/${h}`;
  if (kind === "tiktok") return `https://www.tiktok.com/@${h}`;
  return v;
}
