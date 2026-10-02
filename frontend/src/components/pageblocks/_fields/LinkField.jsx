// Bağlantı seçici: Kategori / Ürün / Sayfa / Marka / Arama / Özel URL / Bağlantı yok.
// Değer: {kind, url (her zaman çözümlenmiş), id?, slug?, label?, new_tab}.
import { useMemo, useState } from "react";
import { CategoryTreeSelect } from "../../admin/CategoryTreeSelect";
import { searchProducts, useBrands, useCategories, usePages } from "./adminData";
import { inputCls } from "./widgets";

const KINDS = [
  ["category", "Kategori"], ["product", "Ürün"], ["page", "Sayfa"], ["brand", "Marka"], ["search", "Arama"], ["url", "Özel URL"], ["none", "Bağlantı yok"],
];

function ProductSearch({ onPick }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const run = async (t) => { setQ(t); if (t.trim().length < 2) { setRows([]); return; } try { setRows(await searchProducts(t, 8)); } catch { setRows([]); } };
  return (
    <div className="relative">
      <input className={inputCls} value={q} placeholder="Ürün ara…" onChange={(e) => run(e.target.value)} aria-label="Ürün ara" />
      {rows.length > 0 && (
        <div className="absolute z-20 left-0 right-0 bg-white border rounded shadow max-h-56 overflow-auto">
          {rows.map((p) => (
            <button key={p.id} type="button" className="block w-full text-left px-2 py-1 text-xs hover:bg-yellow-50" onClick={() => { onPick(p); setRows([]); setQ(""); }}>{p.name}</button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LinkField({ field, value, onChange }) {
  const v = value && typeof value === "object" ? value : { kind: value ? "url" : "none", url: value || "" };
  const kinds = useMemo(() => {
    const allow = field.kinds || KINDS.map((k) => k[0]);
    return KINDS.filter(([k]) => allow.includes(k) || k === "url" || k === "none");
  }, [field.kinds]);
  const cats = useCategories();
  const brands = useBrands();
  const pages = usePages();
  const set = (patch) => onChange({ ...v, ...patch });
  const kind = v.kind || "url";
  return (
    <div className="space-y-1.5">
      <div className="flex flex-wrap gap-1" role="radiogroup" aria-label={`${field.label} türü`}>
        {kinds.map(([k, l]) => (
          <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => onChange({ kind: k, url: k === "none" ? "" : (k === kind ? v.url : ""), new_tab: v.new_tab || false })}
            className={`px-2 py-0.5 rounded-full border text-[11px] ${kind === k ? "bg-gray-800 text-white border-gray-800" : "bg-white border-gray-300"}`}>{l}</button>
        ))}
      </div>
      {kind === "category" && (
        <CategoryTreeSelect categories={cats} value={v.id || ""} onChange={(id) => {
          const c = cats.find((x) => String(x.id) === String(id));
          set(c ? { id: String(c.id), slug: c.slug, url: `/${c.slug}`, label: c.name } : { id: "", slug: "", url: "" });
        }} />
      )}
      {kind === "product" && (
        <div>
          {v.url && <div className="text-xs mb-1">Seçili: <b>{v.label || v.url}</b></div>}
          <ProductSearch onPick={(p) => set({ id: String(p.id), slug: p.slug, url: `/${p.slug || p.id}`, label: p.name })} />
        </div>
      )}
      {kind === "page" && (
        <select className={inputCls} value={v.slug || ""} onChange={(e) => { const p = pages.find((x) => x.slug === e.target.value); set({ slug: e.target.value, url: e.target.value ? `/sayfa/${e.target.value}` : "", label: p?.title }); }}>
          <option value="">— Sayfa seçin —</option>
          {pages.map((p) => <option key={p.slug} value={p.slug}>{p.title}</option>)}
        </select>
      )}
      {kind === "brand" && (
        <select className={inputCls} value={v.id || ""} onChange={(e) => { const b = brands.find((x) => x.id === e.target.value); set(b ? { id: b.id, label: b.name, url: `/arama?q=${encodeURIComponent(b.name)}` } : { id: "", url: "" }); }}>
          <option value="">— Marka seçin —</option>
          {brands.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
        </select>
      )}
      {kind === "search" && (
        <input className={inputCls} placeholder="Aranacak kelime" value={v.label || ""} onChange={(e) => set({ label: e.target.value, url: e.target.value ? `/arama?q=${encodeURIComponent(e.target.value)}` : "" })} />
      )}
      {kind === "url" && (
        <input className={inputCls} placeholder="/sale veya https://…" value={v.url || ""} onChange={(e) => set({ url: e.target.value })} aria-label={`${field.label} adresi`} />
      )}
      {kind !== "none" && (
        <div className="flex items-center justify-between text-[11px] text-gray-500">
          <span className="truncate">{v.url ? `→ ${v.url}` : "Henüz hedef seçilmedi"}</span>
          <label className="flex items-center gap-1 shrink-0"><input type="checkbox" checked={!!v.new_tab} onChange={(e) => set({ new_tab: e.target.checked })} /> Yeni sekmede aç</label>
        </div>
      )}
    </div>
  );
}
