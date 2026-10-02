// Ürün kaynağı düzenleyici + canlı "eşleşen N ürün" göstergesi ve ilk 6 küçük resim (SPEC §5.1/11).
import { useEffect, useState } from "react";
import axios from "axios";
import { API, authHeaders, BACKEND_ORIGIN } from "./adminData";
import { CategoryPicker, ProductPicker, BrandPicker } from "./Pickers";
import { inputCls, NumberInput, BoolInput, SelectInput } from "./widgets";
import { firstImage } from "../../../lib/img";

const KINDS = [
  ["featured", "Öne çıkan ürünler"], ["discounted", "İndirimdeki ürünler"], ["best_sellers", "Çok satanlar"], ["newest", "En yeni ürünler"],
  ["top_rated", "En çok beğenilenler"], ["category", "Seçili kategoriler"], ["manual", "Elle seçilen ürünler"], ["brand", "Marka"],
  ["tag", "Etiket"], ["recently_viewed", "Son görüntülenenler (ziyaretçiye göre)"],
];
const SORTS = [["default", "Kaynağın sırası"], ["newest", "En yeni"], ["popular", "En çok satan"], ["price_asc", "Fiyat (artan)"],
  ["price_desc", "Fiyat (azalan)"], ["discount_desc", "İndirim oranı"], ["name_asc", "Ada göre"], ["random_daily", "Günlük karışık"]];
const abs = (u) => (u && u.startsWith("/") && BACKEND_ORIGIN ? `${BACKEND_ORIGIN}${u}` : u);

export const DEFAULT_SOURCE = { kind: "featured", product_ids: [], category_ids: [], include_children: true, tag: "", brand_ids: [], limit: 6,
  sort: "default", exclude_out_of_stock: false, exclude_ids: [], fill_with: "none" };

export default function ProductSourceField({ field, value, onChange }) {
  const v = { ...DEFAULT_SOURCE, limit: field.default_limit || 6, ...(value && typeof value === "object" ? value : {}) };
  const allowed = field.allowed_kinds || KINDS.map((k) => k[0]);
  const set = (patch) => onChange({ ...v, ...patch });
  const [match, setMatch] = useState(null);
  const key = JSON.stringify(v);
  useEffect(() => {
    let alive = true;
    if (v.kind === "recently_viewed") { setMatch({ n: null, rows: [] }); return undefined; }
    const t = setTimeout(() => {
      axios.post(`${API}/page-blocks/resolve-products`, { sources: [{ ...v, limit: Math.max(v.limit, 1) }], preview: true }, { headers: authHeaders() })
        .then((r) => { if (alive) { const rows = r.data?.results?.[0] || []; setMatch({ n: rows.length, rows }); } })
        .catch(() => { if (alive) setMatch({ n: 0, rows: [] }); });
    }, 350);
    return () => { alive = false; clearTimeout(t); };
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="space-y-2 border rounded p-2 bg-gray-50" data-testid={`source-${field.name}`}>
      <select className={inputCls} value={v.kind} onChange={(e) => set({ kind: e.target.value })} aria-label="Kaynak türü">
        {KINDS.filter(([k]) => allowed.includes(k)).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
      </select>
      {v.kind === "manual" && <ProductPicker field={{ multiple: true, max: field.max_limit || 48 }} value={v.product_ids} onChange={(x) => set({ product_ids: x })} />}
      {v.kind === "category" && (
        <>
          <CategoryPicker field={{ multiple: true }} value={v.category_ids} onChange={(x) => set({ category_ids: x })} />
          <label className="text-xs flex items-center gap-2"><BoolInput field={{ label: "Alt kategoriler dahil" }} value={v.include_children} onChange={(x) => set({ include_children: x })} /> Alt kategoriler dahil</label>
        </>
      )}
      {v.kind === "brand" && <BrandPicker field={{ multiple: true }} value={v.brand_ids} onChange={(x) => set({ brand_ids: x })} />}
      {v.kind === "tag" && <input className={inputCls} placeholder="Etiket" value={v.tag} onChange={(e) => set({ tag: e.target.value })} />}
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs">Adet<NumberInput field={{ min: 1, max: field.max_limit || 48, unit: "adet", label: "Adet" }} value={v.limit} onChange={(x) => set({ limit: Number(x) || 1 })} /></label>
        <label className="text-xs">Sıralama
          <select className={inputCls} value={v.sort} onChange={(e) => set({ sort: e.target.value })}>{SORTS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        </label>
      </div>
      <label className="text-xs flex items-center gap-2"><BoolInput field={{ label: "Stokta olmayanları gizle" }} value={v.exclude_out_of_stock} onChange={(x) => set({ exclude_out_of_stock: x })} /> Stokta olmayanları gizle</label>
      <div className="text-xs">Adet dolmazsa tamamla:
        <SelectInput field={{ label: "Tamamla", options: [{ value: "none", label: "Hayır" }, { value: "newest", label: "En yenilerle" }, { value: "featured", label: "Öne çıkanlarla" }] }} value={v.fill_with} onChange={(x) => set({ fill_with: x })} />
      </div>
      <div className="text-xs" data-testid="source-match">
        {match === null ? "Eşleşen ürünler hesaplanıyor…" : match.n === null ? "Ziyaretçiye göre değişir." : <><b>Eşleşen {match.n} ürün</b>{match.n === 0 && " — blok vitrinde boş kalabilir."}</>}
        {match?.rows?.length > 0 && (
          <div className="flex gap-1 mt-1">
            {match.rows.slice(0, 6).map((p) => <img key={p.id} src={abs(firstImage(p))} alt={p.name} title={p.name} className="w-9 h-9 object-cover rounded border bg-white" loading="lazy" />)}
          </div>
        )}
      </div>
    </div>
  );
}
