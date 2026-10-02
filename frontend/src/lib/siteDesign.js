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

/** Tek iletişim kaynağı (SPEC §4.7): Genel Alanlar › İletişim Bilgileri; boş alanlar Firma Bilgileri'nden. */
export function mergeContact(sc, info) {
  const c = sc || {};
  const i = info || {};
  return {
    phone: c.phone || i.phone || "",
    phone2: c.phone_2 || "",
    email: c.email || i.email || "",
    whatsapp: c.whatsapp || i.whatsapp || "",
    address: c.address || i.address || "",
    hours: c.working_hours || "",
  };
}
