// Panel veri kaynakları (kategori / marka / içerik sayfası / ürün arama) — modül düzeyinde önbellekli.
import { useEffect, useState } from "react";
import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const BACKEND_ORIGIN = String(process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "").replace(/\/api$/, "");
export const authHeaders = () => {
  let t = null;
  try { t = localStorage.getItem("token"); } catch { t = null; }
  return t ? { Authorization: `Bearer ${t}` } : {};
};

const cache = {};
function useCached(key, loader) {
  const [data, setData] = useState(cache[key] || null);
  useEffect(() => {
    if (cache[key]) { setData(cache[key]); return undefined; }
    let alive = true;
    loader().then((d) => { cache[key] = d; if (alive) setData(d); }).catch(() => { if (alive) setData([]); });
    return () => { alive = false; };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return data || [];
}

export function useCategories() {
  return useCached("categories", () => axios.get(`${API}/categories`).then((r) => {
    const rows = Array.isArray(r.data) ? r.data : (r.data?.categories || []);
    return rows.map((c) => ({ ...c, id: String(c.id), parent_id: c.parent_id ? String(c.parent_id) : null }));
  }));
}

export function useBrands() {
  return useCached("brands", () => axios.get(`${API}/brands`, { headers: authHeaders() }).then((r) => {
    const rows = Array.isArray(r.data) ? r.data : (r.data?.items || r.data?.brands || []);
    return rows.map((b) => ({ id: String(b.id || b.name), name: b.name || "", slug: b.slug || "" }));
  }));
}

export function usePages() {
  return useCached("pages", () => axios.get(`${API}/pages`, { headers: authHeaders() }).then((r) => (Array.isArray(r.data) ? r.data : [])
    .map((p) => ({ slug: p.slug, title: p.title || p.slug }))));
}

export async function searchProducts(q, limit = 10) {
  const r = await axios.get(`${API}/products?search=${encodeURIComponent(q)}&limit=${limit}`, { headers: authHeaders() });
  return r.data?.products || [];
}

const prodCache = new Map();
export async function productsByIds(ids) {
  const missing = ids.filter((id) => !prodCache.has(id));
  if (missing.length) {
    const r = await axios.post(`${API}/page-blocks/resolve-products`, { sources: [{ kind: "manual", product_ids: missing, limit: 48 }], preview: true }, { headers: authHeaders() });
    (r.data?.results?.[0] || []).forEach((p) => { prodCache.set(String(p.id), p); if (p.slug) prodCache.set(String(p.slug), p); });
  }
  return ids.map((id) => prodCache.get(String(id)) || { id, name: id, missing: true });
}

export function clientCompress(file, maxSide = 2400, quality = 0.86) {
  return new Promise((resolve) => {
    if (!file || !/^image\/(jpeg|png|webp)$/.test(file.type) || typeof document === "undefined") { resolve({ file, w: 0, h: 0 }); return; }
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const w0 = img.naturalWidth; const h0 = img.naturalHeight;
      const k = Math.min(1, maxSide / Math.max(w0, h0));
      if (k >= 1 && file.size < 1.5 * 1024 * 1024) { URL.revokeObjectURL(url); resolve({ file, w: w0, h: h0 }); return; }
      const c = document.createElement("canvas");
      c.width = Math.round(w0 * k); c.height = Math.round(h0 * k);
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      URL.revokeObjectURL(url);
      c.toBlob((b) => resolve({ file: b ? new File([b], file.name.replace(/\.\w+$/, ".webp"), { type: "image/webp" }) : file, w: c.width, h: c.height }), "image/webp", quality);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve({ file, w: 0, h: 0 }); };
    img.src = url;
  });
}

/** Önerilen orana kırp (odak noktasına göre) → yeni dosya. */
export function cropToRatio(file, ratio, focal = { x: 0.5, y: 0.5 }) {
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const W = img.naturalWidth; const H = img.naturalHeight;
      let w = W; let h = Math.round(W / ratio);
      if (h > H) { h = H; w = Math.round(H * ratio); }
      const x = Math.max(0, Math.min(W - w, Math.round(focal.x * W - w / 2)));
      const y = Math.max(0, Math.min(H - h, Math.round(focal.y * H - h / 2)));
      const c = document.createElement("canvas");
      c.width = w; c.height = h;
      c.getContext("2d").drawImage(img, x, y, w, h, 0, 0, w, h);
      URL.revokeObjectURL(url);
      c.toBlob((b) => resolve(b ? new File([b], file.name.replace(/\.\w+$/, ".webp"), { type: "image/webp" }) : file), "image/webp", 0.9);
    };
    img.onerror = () => { URL.revokeObjectURL(url); resolve(file); };
    img.src = url;
  });
}

export async function uploadMedia(file, { video = false } = {}) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await axios.post(`${API}/upload/${video ? "video" : "image"}`, fd, { headers: authHeaders(), timeout: 120000 });
  const raw = res.data?.url || `/api/upload/files/${res.data?.path}`;
  return raw.startsWith("http") || raw.startsWith("/") ? raw : `/${raw}`;
}

export function imageSize(url) {
  return new Promise((resolve) => {
    if (!url) { resolve(null); return; }
    const img = new Image();
    img.onload = () => resolve([img.naturalWidth, img.naturalHeight]);
    img.onerror = () => resolve(null);
    img.src = url.startsWith("/") ? `${BACKEND_ORIGIN}${url}` : url;
  });
}
