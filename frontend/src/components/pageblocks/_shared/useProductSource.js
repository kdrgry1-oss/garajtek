// Şema `product_source` → ürün listesi. Tek uç: POST /api/page-blocks/resolve-products (aynı karede
// istenen kaynaklar tek istekte toplanır). 60 sn TTL önbellek; Sayfa Tasarımı önizlemesinde önbellek YOK
// (her değişiklik anında görünür). `recently_viewed` istemcide localStorage id listesinden çözülür.
import { useEffect, useMemo, useState } from "react";
import { dedupeColorGroups } from "../../../lib/colorGroups";
import { isPreviewActive } from "../../../lib/pagePreview";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const TTL = 60 * 1000;
const cache = new Map();
let queue = [];
let timer = null;

export function clearProductSourceCache() { cache.clear(); }

// Ürün sayfası (ProductDetail) "store_recently_viewed" anahtarına {id,…} anlık görüntüleri yazar;
// eski "recently_viewed" (düz id listesi) de okunur.
export function recentIds() {
  const read = (k) => { try { const a = JSON.parse(localStorage.getItem(k) || "[]"); return Array.isArray(a) ? a : []; } catch { return []; } };
  const ids = [...read("store_recently_viewed"), ...read("recently_viewed")]
    .map((x) => (x && typeof x === "object" ? x.id : x)).filter((x) => x !== undefined && x !== null && x !== "").map(String);
  return Array.from(new Set(ids));
}

function normalize(src) {
  if (!src || typeof src !== "object") return null;
  if (src.kind === "recently_viewed") return { ...src, kind: "manual", product_ids: recentIds().slice(0, src.limit || 12) };
  return src;
}

function flush() {
  const batch = queue;
  queue = [];
  timer = null;
  const preview = isPreviewActive();
  let token = null;
  try { token = localStorage.getItem("token"); } catch { token = null; }
  fetch(`${API}/page-blocks/resolve-products`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify({ sources: batch.map((b) => b.src), preview }),
  })
    .then((r) => (r.ok ? r.json() : { results: [] }))
    .then((d) => batch.forEach((b, i) => b.resolve(Array.isArray(d.results?.[i]) ? d.results[i] : [])))
    .catch(() => batch.forEach((b) => b.resolve([])));
}

export function resolveSource(src) {
  const s = normalize(src);
  if (!s) return Promise.resolve([]);
  if (s.kind === "manual" && !(s.product_ids || []).length) return Promise.resolve([]);
  const key = JSON.stringify(s);
  const preview = isPreviewActive();
  const hit = cache.get(key);
  if (!preview && hit && Date.now() - hit.t < TTL) return hit.p;
  const p = new Promise((resolve) => {
    queue.push({ src: s, resolve });
    if (!timer) timer = setTimeout(flush, 0);
  }).then((rows) => dedupeColorGroups(rows));
  cache.set(key, { t: Date.now(), p });
  return p;
}

/** null → yükleniyor; [] → boş. */
export default function useProductSource(src) {
  const key = useMemo(() => JSON.stringify(src || null), [src]);
  const [state, setState] = useState(null);
  useEffect(() => {
    if (!src) { setState([]); return undefined; }
    let alive = true;
    setState((prev) => prev); // önceki liste görünür kalsın (titreme yok)
    resolveSource(JSON.parse(key)).then((rows) => { if (alive) setState(rows); });
    return () => { alive = false; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return src ? state : [];
}

/** Birden çok kaynak (ör. sekmeler) — dizi döner; yüklenmeyenler null. */
export function useProductSources(sources) {
  const key = JSON.stringify(sources || []);
  const [state, setState] = useState(() => (sources || []).map(() => null));
  useEffect(() => {
    let alive = true;
    const list = JSON.parse(key);
    Promise.all(list.map((s) => resolveSource(s))).then((rows) => { if (alive) setState(rows); });
    return () => { alive = false; };
  }, [key]);
  return state;
}
