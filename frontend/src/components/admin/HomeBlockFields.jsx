// Sayfa Tasarımı — şablon v1.0 ana sayfa blokları için ayar alanları
// (ads_block, deals_tabs, product_grid_212, best_sellers, product_columns, brands/hero yardımcıları).
// Görsel alanlarının yanında önerilen ölçü gösterilir; yükleme mevcut medya yükleme uç noktasını kullanır.
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Upload, X, Search } from "lucide-react";
import { PRODUCT_SOURCES, SIZES, sizeText } from "../../lib/homeLayout";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BACKEND_ORIGIN = String(process.env.REACT_APP_BACKEND_URL || "").replace(/\/+$/, "").replace(/\/api$/, "");

export async function uploadImageFile(file) {
  const fd = new FormData();
  fd.append("file", file);
  const res = await axios.post(`${API}/upload/image`, fd, {
    headers: { Authorization: `Bearer ${localStorage.getItem("token")}` }, timeout: 90000,
  });
  const raw = res.data?.url || `/api/upload/files/${res.data?.path}`;
  return raw.startsWith("http") ? raw : `${BACKEND_ORIGIN}${raw}`;
}

export function SizeHint({ size, extra }) {
  return (
    <p className="text-[11px] text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-1 inline-block" data-testid="size-hint">
      Önerilen: <b>{sizeText(size)} px</b>{extra ? <> · {extra}</> : null}
    </p>
  );
}

/** Tek görsel alanı (yükle / değiştir / kaldır) + önerilen ölçü. */
export function ImageSlot({ value, onChange, size, label }) {
  const [busy, setBusy] = useState(false);
  const pick = async (file) => {
    if (!file) return;
    setBusy(true);
    try { onChange(await uploadImageFile(file)); toast.success("Görsel yüklendi"); }
    catch (e) { toast.error(`Görsel yüklenemedi: ${e?.response?.data?.detail || e.message}`); }
    finally { setBusy(false); }
  };
  return (
    <div>
      {label && <div className="text-xs font-medium text-gray-700 mb-1">{label}</div>}
      <div className="relative group border rounded bg-gray-50 overflow-hidden" style={{ aspectRatio: `${size[0]} / ${size[1]}` }}>
        {value ? <img src={value} alt="" className="w-full h-full object-contain" /> : (
          <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-xs">{sizeText(size)}</div>
        )}
        <label className="absolute inset-0 flex items-center justify-center cursor-pointer bg-black/0 hover:bg-black/30 transition">
          <input type="file" accept="image/*" className="hidden" onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }} />
          <span className={`flex items-center gap-1 rounded bg-white/90 px-2 py-1 text-[11px] font-medium ${value ? "opacity-0 group-hover:opacity-100" : ""}`}>
            <Upload size={12} /> {busy ? "Yükleniyor…" : value ? "Değiştir" : "Görsel yükle"}
          </span>
        </label>
        {value && (
          <button type="button" onClick={() => onChange("")} className="absolute top-1 right-1 w-6 h-6 bg-red-500 text-white rounded-full flex items-center justify-center" aria-label="Görseli kaldır"><X size={13} /></button>
        )}
      </div>
      <div className="mt-1"><SizeHint size={size} /></div>
    </div>
  );
}

function useCategories() {
  const [cats, setCats] = useState([]);
  useEffect(() => {
    axios.get(`${API}/categories`).then((r) => {
      const rows = Array.isArray(r.data) ? r.data : (r.data?.categories || []);
      setCats(rows.map((c) => ({ id: String(c.id), name: c.full_name || c.name, root: !c.parent_id })));
    }).catch(() => setCats([]));
  }, []);
  return cats;
}

function CategoryPicker({ value = [], onChange, hint }) {
  const cats = useCategories();
  const [q, setQ] = useState("");
  const sel = new Set((value || []).map(String));
  const shown = cats.filter((c) => !q || c.name.toLocaleLowerCase("tr").includes(q.toLocaleLowerCase("tr")));
  return (
    <div className="border rounded p-2 bg-white">
      <div className="flex items-center gap-2 mb-1">
        <Search size={13} className="text-gray-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Kategori ara…" className="flex-1 text-xs border-0 outline-none" />
        {sel.size > 0 && <button type="button" className="text-[11px] text-red-600" onClick={() => onChange([])}>Temizle</button>}
      </div>
      {hint && <p className="text-[10px] text-gray-500 mb-1">{hint}</p>}
      <div className="max-h-36 overflow-y-auto space-y-0.5">
        {shown.map((c) => (
          <label key={c.id} className={`flex items-center gap-2 text-xs px-1 rounded ${c.root ? "font-semibold" : ""}`}>
            <input type="checkbox" checked={sel.has(c.id)} onChange={(e) => {
              const next = new Set(sel); if (e.target.checked) next.add(c.id); else next.delete(c.id);
              onChange([...(value || []).filter((x) => next.has(String(x))), ...[...next].filter((x) => !(value || []).map(String).includes(x))]);
            }} />
            {c.name}
          </label>
        ))}
      </div>
    </div>
  );
}

function ProductPicker({ value = [], onChange, max = 24 }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState([]);
  const [names, setNames] = useState({});
  useEffect(() => {
    (value || []).forEach((id) => {
      if (names[id]) return;
      axios.get(`${API}/products/${encodeURIComponent(id)}`).then((r) => setNames((m) => ({ ...m, [id]: r.data?.name || id }))).catch(() => {});
    });
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps
  const search = async () => {
    if (!q.trim()) return;
    const r = await axios.get(`${API}/products?search=${encodeURIComponent(q)}&limit=10`).catch(() => null);
    setRes(r?.data?.products || []);
  };
  return (
    <div className="border rounded p-2 bg-white space-y-2">
      <div className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); search(); } }}
          placeholder="Ürün adı ile ara…" className="flex-1 border rounded px-2 py-1 text-xs" />
        <button type="button" onClick={search} className="px-2 py-1 bg-black text-white rounded text-xs">Ara</button>
      </div>
      {res.length > 0 && (
        <div className="max-h-32 overflow-y-auto border rounded">
          {res.map((p) => (
            <button type="button" key={p.id} className="w-full text-left text-xs px-2 py-1 hover:bg-gray-50 border-b"
              onClick={() => { if (!(value || []).includes(p.id) && (value || []).length < max) { onChange([...(value || []), p.id]); setNames((m) => ({ ...m, [p.id]: p.name })); } }}>
              + {p.name}
            </button>
          ))}
        </div>
      )}
      <div className="space-y-1">
        {(value || []).map((id, i) => (
          <div key={id} className="flex items-center justify-between text-xs bg-gray-50 rounded px-2 py-1">
            <span className="truncate">{i + 1}. {names[id] || id}</span>
            <button type="button" className="text-red-600" onClick={() => onChange(value.filter((x) => x !== id))} aria-label="Kaldır"><X size={12} /></button>
          </div>
        ))}
        {!(value || []).length && <p className="text-[11px] text-gray-400">Ürün seçilmedi.</p>}
      </div>
    </div>
  );
}

/** Kaynak + (kategori / ürün) seçimi — sekme/sütun ortak düzenleyicisi. */
function SourceEditor({ spec, onChange }) {
  return (
    <div className="space-y-2">
      <select value={spec.source || "newest"} onChange={(e) => onChange({ ...spec, source: e.target.value })} className="w-full border rounded px-2 py-1.5 text-sm">
        {PRODUCT_SOURCES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>
      {spec.source === "category" && <CategoryPicker value={spec.category_ids} onChange={(v) => onChange({ ...spec, category_ids: v })} />}
      {spec.source === "manual" && <ProductPicker value={spec.product_ids} onChange={(v) => onChange({ ...spec, product_ids: v })} />}
    </div>
  );
}

const Field = ({ label, children, hint }) => (
  <label className="block">
    <span className="block text-xs font-medium text-gray-700 mb-1">{label}</span>
    {children}
    {hint && <span className="block text-[10px] text-gray-500 mt-0.5">{hint}</span>}
  </label>
);
const inputCls = "w-full border rounded px-2 py-1.5 text-sm";

export const HOME_BLOCK_TYPES = ["ads_block", "deals_tabs", "product_grid_212", "best_sellers", "product_columns"];

/** Yeni blok türlerinin ayar düzenleyicisi. formData.settings üzerinde çalışır. */
export default function HomeBlockFields({ formData, setFormData }) {
  const st = formData.settings || {};
  const set = (patch) => setFormData({ ...formData, settings: { ...st, ...patch } });

  if (formData.type === "ads_block") {
    const items = [0, 1, 2].map((i) => (st.items || [])[i] || {});
    const setItem = (i, patch) => { const next = items.map((x, j) => (j === i ? { ...x, ...patch } : x)); set({ items: next }); };
    return (
      <div className="space-y-4" data-testid="ads-block-editor">
        <p className="text-xs text-gray-600">Ana sayfada slider'ın altındaki <b>3'lü reklam kartı</b>. Her kartta solda görsel, sağda kısa yazı ve bağlantı bulunur.</p>
        {items.map((it, i) => (
          <div key={i} className="border rounded-lg p-3 bg-gray-50 grid grid-cols-1 md:grid-cols-2 gap-3">
            <ImageSlot label={`${i + 1}. kart görseli`} value={it.image} onChange={(v) => setItem(i, { image: v })} size={SIZES.ads[i]} />
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-1">
                <Field label="Ön yazı"><input className={inputCls} value={it.pre || ""} onChange={(e) => setItem(i, { pre: e.target.value })} placeholder="Atölyeniz için" /></Field>
                <Field label="Kalın yazı"><input className={inputCls} value={it.strong || ""} onChange={(e) => setItem(i, { strong: e.target.value })} placeholder="BÜYÜK" /></Field>
                <Field label="Son yazı"><input className={inputCls} value={it.post || ""} onChange={(e) => setItem(i, { post: e.target.value })} placeholder="FIRSATLAR" /></Field>
              </div>
              <Field label="Bağlantı"><input className={inputCls} value={it.link || ""} onChange={(e) => setItem(i, { link: e.target.value })} placeholder="/kategori-adi veya https://…" /></Field>
              <div className="grid grid-cols-2 gap-1">
                <Field label="Buton yazısı"><input className={inputCls} value={it.cta || ""} onChange={(e) => setItem(i, { cta: e.target.value })} placeholder="Hemen İncele" /></Field>
                <Field label="İndirim yüzdesi" hint="Doluysa buton yerine '%20 indirim' rozeti"><input className={inputCls} value={it.upto || ""} onChange={(e) => setItem(i, { upto: e.target.value.replace(/[^0-9]/g, "") })} placeholder="20" /></Field>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (formData.type === "deals_tabs") {
    const sp = st.special || { mode: "auto" };
    const tabs = [0, 1, 2].map((i) => (st.tabs || [])[i] || { label: "", source: "newest" });
    const setTab = (i, patch) => set({ tabs: tabs.map((t, j) => (j === i ? { ...t, ...patch } : t)) });
    return (
      <div className="space-y-4" data-testid="deals-tabs-editor">
        <div className="border rounded-lg p-3 bg-gray-50 space-y-2">
          <div className="text-sm font-semibold">Günün Fırsatı (sol kart, geri sayımlı)</div>
          <Field label="Kart başlığı"><input className={inputCls} value={sp.title || ""} onChange={(e) => set({ special: { ...sp, title: e.target.value } })} placeholder="Günün Fırsatı" /></Field>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1"><input type="radio" checked={sp.mode !== "manual"} onChange={() => set({ special: { ...sp, mode: "auto" } })} /> Otomatik (en yüksek indirimli ürün)</label>
            <label className="flex items-center gap-1"><input type="radio" checked={sp.mode === "manual"} onChange={() => set({ special: { ...sp, mode: "manual" } })} /> Ürünü ben seçeyim</label>
          </div>
          {sp.mode === "manual" && <ProductPicker value={sp.product_id ? [sp.product_id] : []} max={1} onChange={(v) => set({ special: { ...sp, product_id: v[0] || "" } })} />}
        </div>
        {tabs.map((t, i) => (
          <div key={i} className="border rounded-lg p-3 bg-gray-50 space-y-2">
            <div className="text-sm font-semibold">{i + 1}. sekme</div>
            <Field label="Sekme adı" hint="Boş bırakılırsa sekme gösterilmez"><input className={inputCls} value={t.label || ""} onChange={(e) => setTab(i, { label: e.target.value })} /></Field>
            <SourceEditor spec={t} onChange={(v) => setTab(i, v)} />
          </div>
        ))}
      </div>
    );
  }

  if (formData.type === "product_grid_212") {
    return (
      <div className="space-y-3" data-testid="grid-212-editor">
        <p className="text-xs text-gray-600">Gri zeminli <b>2-1-2 ürün ızgarası</b>: ilk sekme + kategori sekmeleri; her sekmede 5 ürün (ortada büyük).</p>
        <div className="grid grid-cols-2 gap-2">
          <Field label="İlk sekme adı"><input className={inputCls} value={st.first_label || ""} onChange={(e) => set({ first_label: e.target.value })} placeholder="En İyi Fırsatlar" /></Field>
          <Field label="İlk sekme kaynağı">
            <select className={inputCls} value={st.first_source || "discounted"} onChange={(e) => set({ first_source: e.target.value })}>
              {PRODUCT_SOURCES.filter((s) => !["category", "manual"].includes(s.value)).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Toplam sekme sayısı"><input type="number" min={1} max={10} className={inputCls} value={st.max_tabs || 6} onChange={(e) => set({ max_tabs: Math.max(1, Math.min(10, Number(e.target.value) || 6)) })} /></Field>
        <CategoryPicker value={st.category_ids} onChange={(v) => set({ category_ids: v })} hint="Kategori sekmeleri — seçilmezse ana kategoriler sırasıyla kullanılır." />
      </div>
    );
  }

  if (formData.type === "best_sellers") {
    return (
      <div className="space-y-3" data-testid="bestsellers-editor">
        <p className="text-xs text-gray-600">Başlık + sağda sekmeler; 6'lı kart grupları kaydırılır. Başlık, üstteki <b>Başlık</b> alanından gelir.</p>
        <div className="grid grid-cols-2 gap-2">
          <Field label="İlk sekme adı"><input className={inputCls} value={st.first_label || ""} onChange={(e) => set({ first_label: e.target.value })} placeholder="İlk 20" /></Field>
          <Field label="Kategori sekmesi sayısı"><input type="number" min={0} max={6} className={inputCls} value={st.max_tabs ?? 3} onChange={(e) => set({ max_tabs: Math.max(0, Math.min(6, Number(e.target.value) || 0)) })} /></Field>
        </div>
        <CategoryPicker value={st.category_ids} onChange={(v) => set({ category_ids: v })} hint="Seçilmezse ana kategoriler kullanılır." />
      </div>
    );
  }

  if (formData.type === "product_columns") {
    const cols = [0, 1, 2].map((i) => (st.columns || [])[i] || { title: "", source: "featured" });
    const setCol = (i, patch) => set({ columns: cols.map((c, j) => (j === i ? { ...c, ...patch } : c)) });
    return (
      <div className="space-y-3" data-testid="columns-editor">
        <p className="text-xs text-gray-600">Sayfa altında yan yana <b>3 küçük ürün listesi</b> (her biri 3 ürün). Bu blok açıkken alt bilgideki aynı listeler ana sayfada tekrar gösterilmez.</p>
        {cols.map((c, i) => (
          <div key={i} className="border rounded-lg p-3 bg-gray-50 space-y-2">
            <Field label={`${i + 1}. sütun başlığı`} hint="Boşsa sütun gösterilmez"><input className={inputCls} value={c.title || ""} onChange={(e) => setCol(i, { title: e.target.value })} /></Field>
            <SourceEditor spec={c} onChange={(v) => setCol(i, v)} />
          </div>
        ))}
      </div>
    );
  }
  return null;
}
