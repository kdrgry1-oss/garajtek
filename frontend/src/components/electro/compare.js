// Karşılaştırma listesi (Electro "Compare") — istemci tarafı, localStorage; en fazla 4 ürün.
import { useEffect, useState } from "react";

const KEY = "el_compare_v1";
const MAX = 4;
const subs = new Set();

export function readCompare() {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "[]");
    return Array.isArray(v) ? v : [];
  } catch { return []; }
}
function write(list) {
  try { localStorage.setItem(KEY, JSON.stringify(list)); } catch { /* kota */ }
  subs.forEach((f) => f(list));
}
export function toggleCompare(product) {
  const list = readCompare();
  const id = product && product.id;
  if (!id) return { added: false, list };
  if (list.some((p) => p.id === id)) {
    const next = list.filter((p) => p.id !== id);
    write(next);
    return { added: false, list: next };
  }
  const snap = { id, slug: product.slug, name: product.name };
  const next = [...list, snap].slice(-MAX);
  write(next);
  return { added: true, list: next };
}
export function removeCompare(id) { write(readCompare().filter((p) => p.id !== id)); }
export function useCompare() {
  const [list, setList] = useState(readCompare);
  useEffect(() => { subs.add(setList); return () => subs.delete(setList); }, []);
  return list;
}
