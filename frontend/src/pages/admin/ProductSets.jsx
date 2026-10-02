// Katalog › Ürün Setleri — set oluştur/düzenle (bileşen seçici, adet, set indirimi, canlı
// fiyat/stok önizlemesi). Setler "Ürün Setleri" kategorisinde ürün olarak listelenir; vitrinde
// "Seti Sepete Ekle" tüm bileşenleri ayrı kalem olarak ekler. Kurallar: backend/product_sets.py
import { useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Plus, Trash2, Edit2, Search, X, ExternalLink, Package } from "lucide-react";
import { uploadImageFile } from "../../lib/uploadImage";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const auth = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });
const tl = (n) => `${(Number(n) || 0).toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ₺`;
const EMPTY = { name: "", short_description: "", description: "", images: [], set_items: [], set_discount_pct: 5,
  is_active: true, is_featured: false, meta_title: "", meta_description: "" };

function ComponentPicker({ onPick, exclude }) {
  const [q, setQ] = useState("");
  const [rows, setRows] = useState([]);
  const t = useRef(null);
  useEffect(() => {
    clearTimeout(t.current);
    t.current = setTimeout(() => {
      axios.get(`${API}/admin/product-sets/search`, { params: { q, limit: 15 }, headers: auth() })
        .then((r) => setRows(r.data?.items || [])).catch(() => setRows([]));
    }, 250);
    return () => clearTimeout(t.current);
  }, [q]);
  return (
    <div className="rounded-lg border border-gray-200" data-testid="set-component-picker">
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Search size={14} className="text-gray-400" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ürün adı, stok kodu veya barkod ile ara"
          className="w-full text-sm outline-none" data-testid="set-picker-search" />
      </div>
      <ul className="max-h-56 overflow-auto divide-y">
        {rows.filter((r) => !exclude.has(r.id)).map((r) => (
          <li key={r.id} className="flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-gray-50">
            {r.image ? <img src={r.image} alt="" className="h-8 w-8 rounded object-contain bg-gray-50" /> : <Package size={16} className="text-gray-300" />}
            <span className="flex-1 truncate">{r.name}</span>
            <span className={`text-xs ${r.stock > 0 ? "text-green-700" : "text-red-600"}`}>{r.stock > 0 ? `Stok ${r.stock}` : "Tükendi"}</span>
            <span className="w-24 text-right text-xs text-gray-600">{tl(r.unit_price)}</span>
            <button type="button" onClick={() => onPick(r)} className="rounded bg-gray-900 px-2 py-0.5 text-xs text-white"
              data-testid={`set-pick-${r.id}`}>Ekle</button>
          </li>
        ))}
        {!rows.length && <li className="px-3 py-3 text-xs text-gray-400">Sonuç yok</li>}
      </ul>
    </div>
  );
}

function SetEditor({ initial, onClose, onSaved }) {
  const [f, setF] = useState(() => ({ ...EMPTY, ...initial }));
  const [names, setNames] = useState({}); // id → {name, variants}
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const isEdit = !!initial?.id;

  useEffect(() => {
    const t = setTimeout(() => {
      if (!f.set_items.length) { setPreview(null); return; }
      axios.post(`${API}/admin/product-sets/preview`, { set_items: f.set_items, set_discount_pct: f.set_discount_pct }, { headers: auth() })
        .then((r) => setPreview(r.data)).catch(() => setPreview(null));
    }, 250);
    return () => clearTimeout(t);
  }, [f.set_items, f.set_discount_pct]);

  const comps = useMemo(() => Object.fromEntries((preview?.components || []).map((c) => [c.product_id, c])), [preview]);
  const setItem = (i, patch) => setF((p) => ({ ...p, set_items: p.set_items.map((it, k) => (k === i ? { ...it, ...patch } : it)) }));

  const save = async () => {
    if (!f.name.trim()) { toast.error("Set adı gerekli"); return; }
    if (f.set_items.length < 2) { toast.error("En az 2 ürün seçin"); return; }
    setBusy(true);
    try {
      const body = { ...f, set_discount_pct: Number(f.set_discount_pct) || 0 };
      if (isEdit) await axios.put(`${API}/admin/product-sets/${initial.id}`, body, { headers: auth() });
      else await axios.post(`${API}/admin/product-sets`, body, { headers: auth() });
      toast.success(isEdit ? "Set güncellendi" : "Set oluşturuldu");
      onSaved();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally { setBusy(false); }
  };

  const onUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const url = await uploadImageFile(file);
      setF((p) => ({ ...p, images: [...p.images, url] }));
    } catch { toast.error("Görsel yüklenemedi"); }
    e.target.value = "";
  };

  const pr = preview?.pricing;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-auto bg-black/40 p-4" data-testid="set-editor">
      <div className="w-full max-w-4xl rounded-xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-5 py-3">
          <h2 className="text-lg font-bold">{isEdit ? "Seti Düzenle" : "Yeni Ürün Seti"}</h2>
          <button type="button" onClick={onClose} aria-label="Kapat"><X size={18} /></button>
        </div>
        <div className="grid gap-5 p-5 md:grid-cols-5">
          <div className="space-y-3 md:col-span-3">
            <label className="block text-sm font-medium">Set adı
              <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="mt-1 w-full rounded border px-3 py-2"
                placeholder="ör. Lastikçi Başlangıç Seti" data-testid="set-name" />
            </label>
            <label className="block text-sm font-medium">Kısa açıklama
              <input value={f.short_description} onChange={(e) => setF({ ...f, short_description: e.target.value })} className="mt-1 w-full rounded border px-3 py-2" />
            </label>
            <label className="block text-sm font-medium">Açıklama (HTML olabilir)
              <textarea value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} rows={3} className="mt-1 w-full rounded border px-3 py-2 text-sm" />
            </label>

            <div>
              <div className="mb-1 text-sm font-medium">Set ürünleri</div>
              <table className="w-full text-sm" data-testid="set-items-table">
                <tbody className="divide-y">
                  {f.set_items.map((it, i) => {
                    const c = comps[it.product_id];
                    const nm = c?.name || names[it.product_id]?.name || it.product_id;
                    const vars = names[it.product_id]?.variants || (c?.variant ? [c.variant] : []);
                    return (
                      <tr key={it.product_id}>
                        <td className="py-1.5 pr-2">
                          <div className="font-medium">{nm}</div>
                          {vars.length > 0 && (
                            <select value={it.variant_id || ""} onChange={(e) => setItem(i, { variant_id: e.target.value || undefined })} className="mt-0.5 rounded border px-1 py-0.5 text-xs">
                              <option value="">Seçenek: otomatik (stoklu ilk)</option>
                              {vars.map((v) => <option key={v.id} value={v.id}>{v.size} {Number(v.stock) > 0 ? "" : "(tükendi)"}</option>)}
                            </select>
                          )}
                        </td>
                        <td className="w-20"><input type="number" min="1" max="99" value={it.quantity} onChange={(e) => setItem(i, { quantity: Math.max(1, parseInt(e.target.value, 10) || 1) })}
                          className="w-16 rounded border px-2 py-1" aria-label="Adet" /></td>
                        <td className="w-28 text-right">{c ? tl(c.unit_price * c.quantity) : "…"}</td>
                        <td className="w-24 text-right">{c ? (c.in_stock ? <span className="text-green-700">Stokta</span> : <span className="text-red-600">Tükendi</span>) : ""}</td>
                        <td className="w-8 text-right"><button type="button" onClick={() => setF((p) => ({ ...p, set_items: p.set_items.filter((_, k) => k !== i) }))} aria-label="Çıkar"><Trash2 size={14} className="text-red-500" /></button></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              <div className="mt-2">
                <ComponentPicker exclude={new Set(f.set_items.map((i) => i.product_id))} onPick={(r) => {
                  setNames((n) => ({ ...n, [r.id]: { name: r.name, variants: r.variants || [] } }));
                  setF((p) => ({ ...p, set_items: [...p.set_items, { product_id: r.id, quantity: 1 }] }));
                }} />
              </div>
            </div>
          </div>

          <div className="space-y-3 md:col-span-2">
            <div className="rounded-lg border bg-gray-50 p-3 text-sm" data-testid="set-preview">
              <label className="flex items-center justify-between font-medium">Set indirimi (%)
                <input type="number" min="0" max="90" step="0.5" value={f.set_discount_pct} onChange={(e) => setF({ ...f, set_discount_pct: e.target.value })}
                  className="w-20 rounded border px-2 py-1 text-right" data-testid="set-discount" />
              </label>
              <div className="mt-3 space-y-1">
                <div className="flex justify-between"><span>Ayrı ayrı toplam</span><span>{tl(pr?.components_total)}</span></div>
                <div className="flex justify-between font-bold"><span>Set fiyatı</span><span data-testid="set-preview-price">{tl(pr?.set_price)}</span></div>
                <div className="flex justify-between text-green-700"><span>Müşteri kazancı</span><span>{tl(pr?.savings)}</span></div>
                {pr?.missing_count > 0 && <p className="text-xs text-red-600">{pr.missing_count} ürün stokta yok — müşteri sepette aynı alt kategoriden başka ürünle değiştirebilir; set tamamlanınca indirim uygulanır.</p>}
              </div>
              <p className="mt-2 text-[11px] text-gray-500">Kural: indirim yalnız setin tüm ürünleri (veya aynı alt kategoriden yedekleri) sepetteyken uygulanır. Fiyat ve stok bileşenlerden otomatik hesaplanır.</p>
            </div>
            <div>
              <div className="mb-1 text-sm font-medium">Görseller</div>
              <div className="flex flex-wrap gap-2">
                {f.images.map((u, i) => (
                  <div key={u} className="relative">
                    <img src={u} alt="" className="h-16 w-16 rounded border object-contain" />
                    <button type="button" className="absolute -right-1 -top-1 rounded-full bg-white shadow" onClick={() => setF((p) => ({ ...p, images: p.images.filter((_, k) => k !== i) }))} aria-label="Görseli kaldır"><X size={12} /></button>
                  </div>
                ))}
                <label className="flex h-16 w-16 cursor-pointer items-center justify-center rounded border border-dashed text-xs text-gray-500">
                  <input type="file" accept="image/*" className="hidden" onChange={onUpload} />+ Görsel
                </label>
              </div>
              {!f.images.length && <p className="mt-1 text-[11px] text-gray-500">Görsel eklenmezse bileşenlerin ilk görselleri kullanılır; set kartı için bir kolaj yüklemeniz önerilir.</p>}
            </div>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_active} onChange={(e) => setF({ ...f, is_active: e.target.checked })} /> Vitrinde aktif</label>
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={f.is_featured} onChange={(e) => setF({ ...f, is_featured: e.target.checked })} /> Öne çıkan</label>
            <label className="block text-xs font-medium text-gray-600">SEO başlık
              <input value={f.meta_title} onChange={(e) => setF({ ...f, meta_title: e.target.value })} className="mt-1 w-full rounded border px-2 py-1 text-sm" />
            </label>
            <label className="block text-xs font-medium text-gray-600">SEO açıklama
              <textarea value={f.meta_description} onChange={(e) => setF({ ...f, meta_description: e.target.value })} rows={2} className="mt-1 w-full rounded border px-2 py-1 text-sm" />
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t px-5 py-3">
          <button type="button" onClick={onClose} className="rounded border px-4 py-2 text-sm">İptal</button>
          <button type="button" disabled={busy} onClick={save} className="rounded bg-gray-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" data-testid="set-save">
            {busy ? "Kaydediliyor…" : isEdit ? "Kaydet" : "Seti Oluştur"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ProductSets() {
  const [sets, setSets] = useState(null);
  const [editing, setEditing] = useState(null);
  const load = () => axios.get(`${API}/admin/product-sets`, { headers: auth() })
    .then((r) => setSets(r.data?.sets || [])).catch(() => setSets([]));
  useEffect(() => { load(); }, []);

  const openEdit = async (s) => {
    try {
      const r = await axios.get(`${API}/admin/product-sets/${s.id}`, { headers: auth() });
      setEditing({ ...r.data.set, images: r.data.set.images || [], set_items: r.data.set.set_items || [] });
    } catch { toast.error("Set yüklenemedi"); }
  };
  const remove = async (s) => {
    const msg = `"${s.name}" seti silinsin mi? (Bileşen ürünler silinmez.)`;
    const ok = window.appConfirm ? await window.appConfirm(msg) : window.confirm(msg);
    if (!ok) return;
    try {
      await axios.delete(`${API}/admin/product-sets/${s.id}`, { headers: auth() });
      toast.success("Set silindi");
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || "Silinemedi"); }
  };

  return (
    <div className="space-y-4 p-4" data-testid="admin-product-sets">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-bold">Ürün Setleri</h1>
          <p className="text-sm text-gray-500">Birden çok ürünü tek tıkla sepete ekleten setler. Vitrinde “Ürün Setleri” kategorisinde listelenir.</p>
        </div>
        <button type="button" onClick={() => setEditing({ ...EMPTY })} className="inline-flex items-center gap-1 rounded bg-gray-900 px-3 py-2 text-sm font-semibold text-white" data-testid="new-set-btn">
          <Plus size={16} /> Yeni Set
        </button>
      </div>
      <div className="overflow-x-auto rounded-lg border bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase text-gray-500">
            <tr><th className="px-3 py-2">Set</th><th className="px-3 py-2">Ürün</th><th className="px-3 py-2 text-right">Ayrı toplam</th>
              <th className="px-3 py-2 text-right">Set fiyatı</th><th className="px-3 py-2 text-right">İndirim</th><th className="px-3 py-2">Durum</th><th className="px-3 py-2" /></tr>
          </thead>
          <tbody className="divide-y">
            {sets === null && <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">Yükleniyor…</td></tr>}
            {sets?.length === 0 && <tr><td colSpan={7} className="px-3 py-6 text-center text-gray-400">Henüz set yok. “Yeni Set” ile oluşturun ya da Sayfa Tasarımı › Demo İçerik ile örnek setleri yükleyin.</td></tr>}
            {(sets || []).map((s) => (
              <tr key={s.id} data-testid={`set-row-${s.id}`}>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    {s.images?.[0] ? <img src={s.images[0]} alt="" className="h-10 w-12 rounded object-cover" /> : <Package size={18} className="text-gray-300" />}
                    <span className="font-medium">{s.name}</span>
                  </div>
                </td>
                <td className="px-3 py-2">{s.component_count}</td>
                <td className="px-3 py-2 text-right text-gray-500 line-through">{tl(s.pricing?.components_total)}</td>
                <td className="px-3 py-2 text-right font-semibold">{tl(s.pricing?.set_price)}</td>
                <td className="px-3 py-2 text-right">%{s.set_discount_pct || 0}</td>
                <td className="px-3 py-2 text-xs">
                  {s.is_active === false ? <span className="text-gray-500">Pasif</span> : <span className="text-green-700">Aktif</span>}
                  {s.pricing?.missing_count > 0 && <span className="ml-2 text-red-600">{s.pricing.missing_count} bileşen tükendi</span>}
                </td>
                <td className="px-3 py-2 text-right whitespace-nowrap">
                  <a href={`/${s.slug || s.id}`} target="_blank" rel="noopener noreferrer" className="mr-2 inline-block text-gray-500" title="Vitrinde aç"><ExternalLink size={14} /></a>
                  <button type="button" onClick={() => openEdit(s)} className="mr-2 text-blue-600" title="Düzenle" data-testid={`edit-set-${s.id}`}><Edit2 size={14} /></button>
                  <button type="button" onClick={() => remove(s)} className="text-red-600" title="Sil"><Trash2 size={14} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {editing && <SetEditor initial={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}
