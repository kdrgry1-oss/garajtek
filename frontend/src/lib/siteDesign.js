// Global alanlar (Sayfa Tasarımı › Genel Alanlar): tema, üst bar, header, dikey menü, ikincil menü,
// e-bülten, footer… Yayındaki değerler /api/site-design'dan gelir, şema varsayılanlarıyla doldurulur.
// Önizlemede (iframe) panelin taslak global değerleri kullanılır. İlk karede titreme olmasın diye son
// değer localStorage'da tutulur.
import { useEffect, useSyncExternalStore } from "react";
import { withGlobalDefaults } from "../components/pageblocks/registry";
import { usePreviewState } from "./pagePreview";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LS = "site_design_v2";

let published = null;
let promise = null;
let fetchedAt = 0;
const subs = new Set();

function readCache() {
  try {
    const d = JSON.parse(localStorage.getItem(LS) || "null");
    return d && typeof d === "object" ? d : null;
  } catch { return null; }
}

// Tembel: registry ↔ blok bileşenleri döngüsel içe aktarımında modül değerlendirme sırası sorun olmasın.
let merged = null;

function emit() { subs.forEach((fn) => { try { fn(); } catch { /* yoksay */ } }); }

export function fetchSiteDesign(force = false) {
  if (!promise || force || Date.now() - fetchedAt > 5 * 60 * 1000) {
    fetchedAt = Date.now();
    promise = fetch(`${API}/site-design`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d && typeof d === "object") {
          published = d;
          merged = withGlobalDefaults(d);
          try { localStorage.setItem(LS, JSON.stringify(d)); } catch { /* yoksay */ }
          emit();
        }
        return getSnap();
      })
      .catch(() => { promise = null; return getSnap(); });
  }
  return promise;
}

const subscribe = (fn) => { subs.add(fn); return () => subs.delete(fn); };
const getSnap = () => merged || (merged = withGlobalDefaults(readCache() || {}));

/** Yayındaki (önizlemede taslak) global alanlar — her anahtar varsayılanlarla dolu. */
export function useSiteDesign() {
  const pub = useSyncExternalStore(subscribe, getSnap, getSnap);
  const pv = usePreviewState();
  useEffect(() => { if (!pv.active) fetchSiteDesign(); }, [pv.active]);
  if (pv.active && pv.global) return pv.globalMerged || withGlobalDefaults(pv.global);
  return pub;
}

export function getPublishedSiteDesign() {
  return published;
}

/** "{yıl}" / "{mağaza}" yer tutucuları. */
export function fillTokens(s, { storeName = "" } = {}) {
  return String(s || "").replace(/\{yıl\}|\{year\}/g, String(new Date().getFullYear())).replace(/\{mağaza\}|\{store_name\}/g, storeName);
}

/** Sayfa Tasarımı › Tema › "Görselleri gerektikçe yükle" (lazy_images). Bileşenler loading="lazy" yazar;
 *  ayar KAPALIYSA sayfadaki (ve sonradan eklenen) tüm lazy görseller eager'a çevrilir. Açılınca gözlem durur.
 *  Dönüş: temizleyici. */
let _lazyObs = null;
export function applyLazyImages(enabled, root = typeof document !== "undefined" ? document : null) {
  if (_lazyObs) { _lazyObs.disconnect(); _lazyObs = null; }
  if (enabled !== false || !root || !root.querySelectorAll) return () => {};
  const eager = (node) => {
    if (!node || !node.querySelectorAll) return;
    if (node.tagName === "IMG" && node.getAttribute("loading") === "lazy") node.setAttribute("loading", "eager");
    node.querySelectorAll('img[loading="lazy"]').forEach((img) => img.setAttribute("loading", "eager"));
  };
  eager(root.documentElement || root);
  if (typeof MutationObserver !== "undefined") {
    _lazyObs = new MutationObserver((muts) => muts.forEach((m) => {
      if (m.type === "attributes") eager(m.target);
      else m.addedNodes.forEach(eager);
    }));
    _lazyObs.observe(root.documentElement || root, { childList: true, subtree: true, attributes: true, attributeFilter: ["loading"] });
  }
  return () => { if (_lazyObs) { _lazyObs.disconnect(); _lazyObs = null; } };
}

/** Tek iletişim kaynağı:Ayarlar › Genel / Firma Bilgileri (tenant_config — yasal sayfalar ve /sayfa/iletisim
 *  gövdesi de buradan okur). Sayfa Tasarımı › İletişim Bilgileri yalnız orası boşsa kullanılır; ikinci telefon
 *  ve çalışma saatlerinin karşılığı olmadığından onlar doğrudan buradan gelir. (Önceden site_contact önceydi:
 *  Genel Ayarlar'da değiştirilen telefon/adres footer'a yansımıyor, aynı sayfada iki farklı iletişim görünüyordu.) */
export function mergeContact(sc, info) {
  const c = sc || {};
  const i = info || {};
  return {
    phone: i.phone || c.phone || "",
    phone2: c.phone_2 || "",
    email: i.email || c.email || "",
    whatsapp: i.whatsapp || c.whatsapp || "",
    address: i.address || c.address || "",
    hours: c.working_hours || "",
  };
}
