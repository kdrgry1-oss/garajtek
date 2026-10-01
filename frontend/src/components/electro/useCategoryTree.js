// Kategori ağacı — /api/categories?visible_only=true (düz liste, parent_id ile) → 3 seviyeli ağaç.
// Tüm Header/Footer/Sidebar bileşenleri aynı isteği paylaşır (modül önbelleği + localStorage ile
// ilk karede son bilinen ağaç → menü titremez). Üyelere özel kategoriler oturuma göre değiştiği
// için önbellek oturum (token) anahtarına göre ayrılır.
import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LS = "el_cat_tree_v1";

let _promise = null;
let _key = null;
let _resolved = null;

const tokenKey = () => {
  try { return localStorage.getItem("token") ? "m" : "g"; } catch { return "g"; }
};

export function buildTree(list) {
  const cats = (Array.isArray(list) ? list : []).filter((c) => c && c.name && c.is_active !== false);
  const byId = new Map();
  cats.forEach((c) => byId.set(String(c.id), { ...c, children: [] }));
  const roots = [];
  byId.forEach((node) => {
    const pid = node.parent_id != null && node.parent_id !== "" ? String(node.parent_id) : null;
    if (pid && byId.has(pid) && pid !== String(node.id)) byId.get(pid).children.push(node);
    else roots.push(node);
  });
  const sortRec = (arr) => {
    arr.sort((a, b) => (Number(a.sort_order) || 999) - (Number(b.sort_order) || 999) || String(a.name).localeCompare(String(b.name), "tr"));
    arr.forEach((n) => sortRec(n.children));
    return arr;
  };
  return { roots: sortRec(roots), byId, flat: cats };
}

function cached() {
  const k = tokenKey();
  if (_resolved && _resolved.k === k) return _resolved.tree;
  try {
    const raw = JSON.parse(localStorage.getItem(`${LS}:${k}`) || "null");
    if (Array.isArray(raw) && raw.length) return buildTree(raw);
  } catch { /* yoksay */ }
  return null;
}

export function loadCategories() {
  const k = tokenKey();
  if (_promise && _key === k) return _promise;
  _key = k;
  let tok = null;
  try { tok = localStorage.getItem("token"); } catch { tok = null; }
  _promise = axios
    .get(`${API}/categories?visible_only=true`, tok ? { headers: { Authorization: `Bearer ${tok}` } } : undefined)
    .then((r) => {
      const raw = Array.isArray(r.data) ? r.data : (r.data?.categories || r.data?.items || []);
      try { localStorage.setItem(`${LS}:${k}`, JSON.stringify(raw.map(({ id, name, slug, parent_id, sort_order, icon, image, image_url, is_active, product_count, description }) => ({ id, name, slug, parent_id, sort_order, icon, image, image_url, is_active, product_count, description })))); } catch { /* kota */ }
      const tree = buildTree(raw);
      _resolved = { k, tree };
      return tree;
    })
    .catch(() => { _promise = null; return cached() || buildTree([]); });
  return _promise;
}

/** { roots, byId, flat, ready } */
export default function useCategoryTree() {
  const [tree, setTree] = useState(() => cached());
  useEffect(() => {
    let alive = true;
    loadCategories().then((t) => { if (alive) setTree(t); });
    return () => { alive = false; };
  }, []);
  return tree ? { ...tree, ready: true } : { roots: [], byId: new Map(), flat: [], ready: false };
}

/** Bir kategorinin kökten kendisine kadar yolu (breadcrumb için). */
export function categoryPath(tree, cat) {
  const out = [];
  let cur = cat;
  const seen = new Set();
  while (cur && !seen.has(String(cur.id))) {
    seen.add(String(cur.id));
    out.unshift(cur);
    const pid = cur.parent_id != null ? String(cur.parent_id) : null;
    cur = pid ? tree.byId.get(pid) : null;
  }
  return out;
}

export function findBySlug(tree, slug) {
  if (!slug) return null;
  const s = String(slug).toLowerCase();
  for (const n of tree.byId.values()) {
    if (String(n.slug || "").toLowerCase() === s) return n;
  }
  return null;
}
