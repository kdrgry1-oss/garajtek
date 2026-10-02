// Ürün / kategori / marka seçicileri (çoklu: çipler + sürükle-sırala yok; ürünler ↑↓ ile sıralanır).
import { useEffect, useState } from "react";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import { CategoryTreeSelect } from "../../admin/CategoryTreeSelect";
import { productsByIds, searchProducts, useBrands, useCategories } from "./adminData";
import { inputCls } from "./widgets";

export function ProductPicker({ field, value, onChange }) {
  const multiple = !!field.multiple;
  const ids = multiple ? (Array.isArray(value) ? value : []) : (value ? [value] : []);
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [hits, setHits] = useState([]);
  useEffect(() => { let a = true; if (ids.length) productsByIds(ids).then((r) => { if (a) setRows(r); }).catch(() => {}); else setRows([]); return () => { a = false; }; }, [ids.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (list) => onChange(multiple ? list : (list[0] || ""));
  const search = async (t) => { setQ(t); if (t.trim().length < 2) { setHits([]); return; } try { setHits(await searchProducts(t, 10)); } catch { setHits([]); } };
  const name = (id) => (rows.find((r) => String(r.id) === String(id) || String(r.slug) === String(id)) || {}).name || id;
  const max = field.max || (multiple ? 48 : 1);
  return (
    <div className="space-y-1">
      {ids.map((id, i) => (
        <div key={id} className="flex items-center gap-1 text-xs border rounded px-2 py-1 bg-white">
          <span className="flex-1 truncate">{name(id)}</span>
          {multiple && <button type="button" aria-label="Yukarı" disabled={!i} onClick={() => { const n = [...ids]; [n[i - 1], n[i]] = [n[i], n[i - 1]]; set(n); }}><ArrowUp size={12} /></button>}
          {multiple && <button type="button" aria-label="Aşağı" disabled={i === ids.length - 1} onClick={() => { const n = [...ids]; [n[i + 1], n[i]] = [n[i], n[i + 1]]; set(n); }}><ArrowDown size={12} /></button>}
          <button type="button" aria-label="Kaldır" className="text-red-500" onClick={() => set(ids.filter((x) => x !== id))}><X size={12} /></button>
        </div>
      ))}
      {ids.length < max && (
        <div className="relative">
          <input className={inputCls} value={q} placeholder={multiple ? "Ürün ara ve ekle…" : "Ürün ara…"} onChange={(e) => search(e.target.value)} aria-label="Ürün ara" />
          {hits.length > 0 && (
            <div className="absolute z-20 left-0 right-0 bg-white border rounded shadow max-h-56 overflow-auto">
              {hits.map((p) => (
                <button key={p.id} type="button" className="block w-full text-left px-2 py-1 text-xs hover:bg-yellow-50"
                  onClick={() => { set(multiple ? [...ids.filter((x) => x !== String(p.id)), String(p.id)] : [String(p.id)]); setHits([]); setQ(""); }}>{p.name}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function CategoryPicker({ field, value, onChange }) {
  const cats = useCategories();
  const multiple = field.multiple !== false;
  const ids = multiple ? (Array.isArray(value) ? value.map(String) : []) : (value ? [String(value)] : []);
  const name = (id) => (cats.find((c) => String(c.id) === String(id)) || {}).name || id;
  const set = (list) => onChange(multiple ? list : (list[0] || ""));
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap gap-1">
        {ids.map((id) => (
          <span key={id} className="inline-flex items-center gap-1 text-xs bg-gray-100 border rounded-full px-2 py-0.5">{name(id)}
            <button type="button" aria-label="Kaldır" onClick={() => set(ids.filter((x) => x !== id))}><X size={11} /></button></span>
        ))}
      </div>
      {(!field.max || ids.length < field.max) && (
        <CategoryTreeSelect categories={cats} value="" onChange={(id) => { if (id && !ids.includes(String(id))) set(multiple ? [...ids, String(id)] : [String(id)]); }} />
      )}
    </div>
  );
}

export function BrandPicker({ field, value, onChange }) {
  const brands = useBrands();
  const multiple = field.multiple !== false;
  const ids = multiple ? (Array.isArray(value) ? value : []) : (value ? [value] : []);
  const set = (list) => onChange(multiple ? list : (list[0] || ""));
  return (
    <div className="flex flex-wrap gap-1 max-h-40 overflow-auto border rounded p-1 bg-white">
      {!brands.length && <span className="text-xs text-gray-500">Marka bulunamadı (Katalog › Markalar).</span>}
      {brands.map((b) => {
        const on = ids.includes(b.id);
        return (
          <button key={b.id} type="button" aria-pressed={on} onClick={() => set(on ? ids.filter((x) => x !== b.id) : (multiple ? [...ids, b.id] : [b.id]))}
            className={`text-xs px-2 py-0.5 rounded-full border ${on ? "bg-yellow-300 border-yellow-400" : "bg-white border-gray-300"}`}>{b.name}</button>
        );
      })}
    </div>
  );
}
