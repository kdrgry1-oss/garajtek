/**
 * Mağaza kimliği — çalışma anı (GET /api/settings → tenant_config). Bkz. lib/brand.js.
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { SITE_NAME, SITE_URL } from "./brand";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const EMPTY = {
  name: SITE_NAME,
  legalName: "",
  url: SITE_URL,
  email: "",
  phone: "",
  whatsapp: "",
  address: "",
  instagram: "",
  tiktok: "",
  logo: "",
};

let _cache = null;
let _promise = null;

function fromSettings(s) {
  const t = (s && s.tenant_config) || {};
  const brand = t.brand || {};
  const contact = t.contact || {};
  const company = t.company || {};
  const domains = t.domains || {};
  const ci = (s && s.company_info) || {};
  return {
    name: brand.store_name || (s && s.site_name) || SITE_NAME,
    legalName: company.legal_name || ci.company_name || "",
    url: (domains.storefront_url || ci.website || SITE_URL || "").replace(/\/+$/, ""),
    email: contact.email || (s && s.contact_email) || ci.email || "",
    phone: contact.phone || (s && s.contact_phone) || ci.phone || "",
    whatsapp: contact.whatsapp || "",
    address: company.address || (s && s.address) || ci.address || "",
    instagram: contact.instagram || "",
    tiktok: contact.tiktok || "",
    logo: brand.logo_url || (s && s.logo_url) || "",
  };
}

/** Mağaza kimliğini tek sefer çeker (modül önbelleği); hata → nötr varsayılanlar. */
export function loadStoreInfo() {
  if (_cache) return Promise.resolve(_cache);
  if (!_promise) {
    _promise = axios
      .get(`${API}/settings`, { timeout: 8000 })
      .then((r) => { _cache = fromSettings(r.data); return _cache; })
      .catch(() => { _promise = null; return EMPTY; });
  }
  return _promise;
}

/**
 * index.html'deki build-time adı (%REACT_APP_SITE_NAME% → SITE_NAME) panelde kaydedilen mağaza adıyla değiştirir:
 * <title>, og:site_name, og/twitter başlık-açıklama ve JSON-LD "name". Kendi başlığını kurmayan sayfalar
 * (ana sayfa, tüm ürünler, CMS sayfaları) ve setPageSeo'nun dokunmadığı og:site_name böylece güncel adı taşır.
 * Yalnız build-time adın TAM / önek / " | ad" sonek halleri değiştirilir (ürün adının içindeki kelimeye dokunulmaz).
 */
export function applyRuntimeSiteName(name, doc = typeof document !== "undefined" ? document : null) {
  const n = String(name || "").trim();
  const old = SITE_NAME;
  if (!doc || !n || n === old) return;
  const swap = (s) => {
    const v = String(s || "");
    if (v === old) return n;
    if (v.endsWith(` | ${old}`)) return `${v.slice(0, -old.length)}${n}`;
    if (v.startsWith(`${old} —`)) return `${n}${v.slice(old.length)}`;
    return v;
  };
  try {
    if (doc.title) doc.title = swap(doc.title);
    doc.querySelectorAll(
      'meta[property="og:site_name"],meta[property="og:title"],meta[name="twitter:title"],'
      + 'meta[name="description"],meta[property="og:description"],meta[name="twitter:description"]',
    ).forEach((m) => {
      const c = m.getAttribute("content");
      const v = swap(c);
      if (v !== c) m.setAttribute("content", v);
    });
    doc.querySelectorAll('script[type="application/ld+json"]').forEach((s) => {
      try {
        const j = JSON.parse(s.textContent || "null");
        if (j && typeof j === "object" && !Array.isArray(j) && j.name === old) {
          s.textContent = JSON.stringify({ ...j, name: n });
        }
      } catch { /* bozuk JSON-LD — dokunma */ }
    });
  } catch { /* SSR / test ortamı */ }
}

/** React hook: mağaza kimliği (ilk render'da env/nötr değer, sonra backend ayarları). */
export function useStoreInfo() {
  const [info, setInfo] = useState(_cache || EMPTY);
  useEffect(() => {
    let alive = true;
    loadStoreInfo().then((v) => { if (alive) setInfo(v); });
    return () => { alive = false; };
  }, []);
  return info;
}
