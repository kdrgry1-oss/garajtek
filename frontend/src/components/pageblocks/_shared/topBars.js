import "./pageblocks.css";
// Üst bar blokları (rotating_text, countdown_bar) sayfa akışında değil Header'da çizilir; BlockFrame yoktur.
// Bu yüzden ortak "Görünürlük" grubu (_visibility: masaüstü/tablet/mobil, zamanlama, kitle) burada uygulanır.
import { scheduleActive } from "./schema";

export function isMemberNow() {
  try { return !!localStorage.getItem("token"); } catch { return false; }
}

/** Blok bu ziyaretçiye (kitle + zamanlama) gösterilmeli mi? */
export function barAllowed(block, isMember = isMemberNow(), now = new Date()) {
  if (!block || block.is_active === false) return false;
  const v = block.settings?._visibility || {};
  if (!scheduleActive(v.schedule, now)) return false;
  if ((v.audience === "members" && !isMember) || (v.audience === "guests" && isMember)) return false;
  return true;
}

/** Cihaz görünürlüğü sınıfları (≥1200 masaüstü / 768–1199 tablet / <768 mobil). */
export function barVisClass(block) {
  const v = block?.settings?._visibility || {};
  return [v.desktop === false ? "pd-bar-hide-desktop" : "", v.tablet === false ? "pd-bar-hide-tablet" : "", v.mobile === false ? "pd-bar-hide-mobile" : ""]
    .filter(Boolean).join(" ");
}
