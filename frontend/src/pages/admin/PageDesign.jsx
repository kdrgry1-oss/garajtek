// Sayfa Tasarımı (SPEC §5.1) — vitrin ana sayfasıyla %100 eşdeğer, şemadan üretilen düzenleyici.
//   Sol (360px): [Bloklar] sürükle-bırak liste (gizle/göster, cihaz görünürlüğü, zamanlama rozeti,
//                "değiştirildi" noktası, çoğalt, sil) + seçili bloğun şemadan otomatik formu (sekmeli)
//                [Genel Alanlar] tema, üst bar, header, dikey menü, menüler, e-bülten, footer…
//   Sağ: GERÇEK vitrin önizlemesi (iframe /onizleme/sayfa/home) — postMessage ile anında senkron,
//        tıkla-seç, bloklar arası "+ Blok ekle", cihaz genişlikleri 1440 / 1024 / 390.
//   Üst çubuk: geri al / ileri al (100 adım), otomatik taslak kaydı (3 sn, If-Match), Yayınla (atomik),
//              hata listesi, çakışma çözümü, revizyonlar, taslağı at, şablon düzenini yükle.
// Blok tipi değiştirilemez; varyant değiştirilebilir. Her blok/alan "Şablon varsayılanına sıfırla".
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";
import {
  AlertTriangle, ArrowDown, ArrowUp, Clock, Copy, ExternalLink, Eye, EyeOff, GripVertical, History, LayoutTemplate, Monitor,
  Plus, Redo2, RotateCcw, Smartphone, Tablet, Trash2, Undo2, X,
} from "lucide-react";
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import {
  allFields, applyVariant, CATEGORIES, defaultSettings, duplicateBlock, getBlock, getGlobal, getSchema, globalKeys, instantiate,
  isModified, listBlocks, resetBlock, withDefaults, withGlobalDefaults,
} from "../../components/pageblocks/registry";
import SchemaForm from "../../components/pageblocks/_fields/SchemaForm";
import { normErrPath } from "../../components/pageblocks/_fields/SchemaForm";
import { clone } from "../../components/pageblocks/_shared/schema";
import DemoContentCard from "../../components/admin/DemoContentCard";
import { appConfirm } from "../../components/admin/AppConfirm";
import { useAuth } from "../../context/AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const PAGE = "home";
const HISTORY = 100;
const DEVICES = [["desktop", 1440, Monitor, "Masaüstü"], ["tablet", 1024, Tablet, "Tablet"], ["mobile", 390, Smartphone, "Mobil"]];
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });
const ask = (m) => (appConfirm ? appConfirm(m) : Promise.resolve(window.confirm(m)));

const GLOBAL_GROUPS = [
  ["site_theme", "Tema"], ["site_page_layout", "Sayfa Düzeni"], ["site_contact", "İletişim Bilgileri"], ["site_topbar", "Üst Bar"], ["site_header", "Header"],
  ["site_departments_menu", "Dikey Menü"], ["site_secondary_menu", "Ana / İkincil Menü"], ["site_newsletter", "E-Bülten"],
  ["site_footer_widgets", "Footer Ürün Sütunları"], ["site_footer_contact", "Footer İletişim"], ["site_footer_links", "Footer Bağlantıları"],
  ["site_footer_bottom", "Footer Alt Şerit"],
];
const MENU_LINKS = { site_topbar: "topbar", site_departments_menu: "departments", site_secondary_menu: "center" };

function ago(ts) {
  if (!ts) return "";
  const s = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (s < 60) return `${s} sn önce`;
  return `${Math.round(s / 60)} dk önce`;
}

function hasSchedule(b) {
  const sc = b?.settings?._visibility?.schedule;
  return !!(sc && (sc.start || sc.end));
}

// ------------------------------------------------------------------ blok satırı
function BlockRow({ block, index, total, selected, errorCount, onSelect, onPatch, onDup, onDel, onMove }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: block.id });
  const entry = getBlock(block.type);
  const vis = block.settings?._visibility || {};
  const legacy = block.settings?._legacy || !entry;
  const setVis = (k) => onPatch({ settings: { ...block.settings, _visibility: { ...vis, [k]: vis[k] === false } } });
  const devIcon = (k, Icon, label) => (
    <button type="button" title={`${label}: ${vis[k] === false ? "gizli" : "görünür"}`} aria-label={`${label} görünürlüğü`} aria-pressed={vis[k] !== false}
      onClick={(e) => { e.stopPropagation(); setVis(k); }} className={`p-0.5 ${vis[k] === false ? "text-gray-300" : "text-gray-600"}`} disabled={legacy}>
      <Icon size={13} />
    </button>
  );
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }}
      className={`group flex items-center gap-1 px-1.5 py-1.5 border rounded mb-1 bg-white ${selected ? "border-yellow-400 ring-1 ring-yellow-300" : "border-gray-200"} ${block.is_active === false ? "opacity-60" : ""}`}
      data-testid={`block-row-${index}`} data-block-type={block.type}>
      <button type="button" className="cursor-grab text-gray-400 p-0.5" aria-label="Sürükle" {...attributes} {...listeners}><GripVertical size={14} /></button>
      <button type="button" className="flex-1 min-w-0 text-left" onClick={onSelect}>
        <div className="flex items-center gap-1">
          <span className="text-[13px] font-medium truncate">{block.title || entry?.schema.title || block.type}</span>
          {isModified(block) && <span className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" title="Şablon varsayılanından değiştirildi" data-testid="modified-dot" />}
          {hasSchedule(block) && <Clock size={12} className="text-blue-600 shrink-0" title="Zamanlı yayın" />}
          {errorCount > 0 && <span className="text-[10px] bg-red-100 text-red-700 rounded px-1 shrink-0">{errorCount} hata</span>}
          {legacy && <AlertTriangle size={12} className="text-amber-500 shrink-0" title="Desteklenmeyen eski blok" />}
        </div>
        <div className="text-[10px] text-gray-500 truncate">{entry?.schema.title || block.type}{entry?.schema.status === "stub" ? " · hazırlanıyor" : ""}</div>
      </button>
      <div className="flex items-center">
        {devIcon("desktop", Monitor, "Masaüstü")}{devIcon("tablet", Tablet, "Tablet")}{devIcon("mobile", Smartphone, "Mobil")}
        <button type="button" className="p-0.5 text-gray-600" title={block.is_active === false ? "Göster" : "Gizle"} aria-label={block.is_active === false ? "Bloğu göster" : "Bloğu gizle"}
          onClick={(e) => { e.stopPropagation(); onPatch({ is_active: block.is_active === false }); }} data-testid={`toggle-${index}`}>
          {block.is_active === false ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
        <button type="button" className="p-0.5 text-gray-600 disabled:opacity-30" aria-label="Yukarı taşı" disabled={!index} onClick={(e) => { e.stopPropagation(); onMove(-1); }}><ArrowUp size={13} /></button>
        <button type="button" className="p-0.5 text-gray-600 disabled:opacity-30" aria-label="Aşağı taşı" disabled={index === total - 1} onClick={(e) => { e.stopPropagation(); onMove(1); }}><ArrowDown size={13} /></button>
        {!legacy && <button type="button" className="p-0.5 text-gray-600" title="Çoğalt" aria-label="Çoğalt" onClick={(e) => { e.stopPropagation(); onDup(); }} data-testid={`dup-${index}`}><Copy size={13} /></button>}
        <button type="button" className="p-0.5 text-red-500" title="Sil" aria-label="Sil" onClick={(e) => { e.stopPropagation(); onDel(); }} data-testid={`del-${index}`}><Trash2 size={13} /></button>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ blok galerisi
function Gallery({ onPick, onClose, existing }) {
  const [cat, setCat] = useState("all");
  const [showStubs, setShowStubs] = useState(false);
  const [variant, setVariant] = useState({});
  const all = listBlocks({ includeStubs: true, page: PAGE });
  const list = all.filter((b) => (showStubs || b.schema.status !== "stub") && (cat === "all" || b.schema.category === cat));
  const cats = CATEGORIES.filter((c) => all.some((b) => b.schema.category === c.key && (showStubs || b.schema.status !== "stub")));
  return (
    <div className="fixed inset-0 z-[90] bg-black/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Blok ekle" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-5xl max-h-[85vh] flex flex-col" onClick={(e) => e.stopPropagation()} data-testid="block-gallery">
        <div className="flex items-center justify-between px-4 py-3 border-b">
          <div className="font-semibold">Blok ekle</div>
          <div className="flex items-center gap-3">
            <label className="text-xs flex items-center gap-1"><input type="checkbox" checked={showStubs} onChange={(e) => setShowStubs(e.target.checked)} /> Hazırlanan blokları da göster</label>
            <button type="button" onClick={onClose} aria-label="Kapat"><X size={18} /></button>
          </div>
        </div>
        <div className="flex flex-wrap gap-1 px-4 py-2 border-b">
          {[{ key: "all", label: "Tümü" }, ...cats].map((c) => (
            <button key={c.key} type="button" onClick={() => setCat(c.key)} className={`px-2.5 py-1 rounded-full text-xs border ${cat === c.key ? "bg-gray-800 text-white border-gray-800" : "bg-white"}`}>{c.label}</button>
          ))}
        </div>
        <div className="p-4 overflow-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {list.map((b) => {
            const s = b.schema;
            const single = s.singleton && existing.has(b.key);
            return (
              <div key={b.key} className={`border rounded-lg overflow-hidden flex flex-col ${single ? "opacity-50" : ""}`} data-testid={`gallery-${b.key}`}>
                <div className="aspect-video bg-gray-100 flex items-center justify-center text-gray-400 text-xs relative">
                  {b.thumb ? <img src={b.thumb} alt="" className="w-full h-full object-cover" loading="lazy" /> : <LayoutTemplate size={28} />}
                  {s.status === "stub" && <span className="absolute top-1 right-1 text-[10px] bg-amber-100 text-amber-800 rounded px-1">hazırlanıyor</span>}
                </div>
                <div className="p-2 flex-1 flex flex-col gap-1">
                  <div className="text-sm font-semibold">{s.title}</div>
                  <div className="text-[11px] text-gray-600 flex-1">{s.description}</div>
                  {(s.template_refs || []).length > 0 && <div className="text-[10px] text-gray-400 truncate" title={s.template_refs.join(", ")}>şablonda: {s.template_refs.map((r) => r.split("/").pop()).join(", ")}</div>}
                  {(s.variants || []).length > 1 && (
                    <select className="border rounded text-xs px-1 py-1" value={variant[b.key] ?? s.variants[0].value} onChange={(e) => setVariant({ ...variant, [b.key]: e.target.value })} aria-label="Görünüm">
                      {s.variants.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
                    </select>
                  )}
                  <button type="button" disabled={single} className="mt-1 inline-flex items-center justify-center gap-1 text-xs bg-yellow-400 hover:bg-yellow-300 rounded px-2 py-1.5 font-semibold disabled:cursor-not-allowed"
                    onClick={() => onPick(b.key, variant[b.key] ?? s.variants?.[0]?.value)} data-testid={`gallery-add-${b.key}`}>
                    <Plus size={13} /> {single ? "Sayfada zaten var" : "Ekle"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ revizyonlar
function Revisions({ onClose, onRestore, onPreview }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    axios.get(`${API}/page-design/${PAGE}/revisions`, { headers: headers() }).then((r) => setItems(r.data?.items || [])).catch(() => setItems([]));
  }, []);
  return (
    <div className="fixed inset-y-0 right-0 z-[80] w-96 bg-white shadow-2xl border-l flex flex-col" role="dialog" aria-label="Revizyonlar" data-testid="revisions-panel">
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="font-semibold">Revizyonlar</div>
        <button type="button" onClick={onClose} aria-label="Kapat"><X size={18} /></button>
      </div>
      <div className="flex-1 overflow-auto p-3 space-y-2">
        {items === null && <div className="text-sm text-gray-500">Yükleniyor…</div>}
        {items && !items.length && <div className="text-sm text-gray-500">Henüz revizyon yok.</div>}
        {(items || []).map((r) => (
          <div key={r.rev} className="border rounded p-2 text-xs" data-testid={`rev-${r.rev}`}>
            <div className="flex justify-between font-semibold"><span>#{r.rev}</span><span>{r.published_at ? new Date(r.published_at).toLocaleString("tr-TR") : ""}</span></div>
            <div className="text-gray-600">{r.published_by} — {r.summary}</div>
            <div className="flex gap-1 mt-1">
              <button type="button" className="border rounded px-2 py-0.5 hover:bg-gray-50" onClick={() => onPreview(r.rev)}>Bu sürümü önizle</button>
              <button type="button" className="border rounded px-2 py-0.5 hover:bg-yellow-50" onClick={() => onRestore(r.rev)} data-testid={`restore-${r.rev}`}>Bu sürüme geri dön</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ ana bileşen
export default function PageDesign() {
  const { user } = useAuth();
  const superAdmin = !!(user?.is_super_admin || user?.role === "super_admin" || user?.role_id === "super_admin");
  const [loading, setLoading] = useState(true);
  const [doc, setDoc] = useState({ blocks: [], global: {} });
  const [published, setPublished] = useState(null);
  const [past, setPast] = useState([]);
  const [future, setFuture] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [focusPath, setFocusPath] = useState(null);
  const qAlan = (() => { try { return new URLSearchParams(window.location.search).get("alan") || ""; } catch { return ""; } })();
  const [leftTab, setLeftTab] = useState(qAlan ? "global" : "blocks");
  const [globalKey, setGlobalKey] = useState(qAlan && getGlobal(qAlan) ? qAlan : "site_theme");
  const [device, setDevice] = useState("desktop");
  const [gallery, setGallery] = useState(null);
  const [showRevs, setShowRevs] = useState(false);
  const [revPreview, setRevPreview] = useState(null);
  const [rev, setRev] = useState(null);
  const [saveState, setSaveState] = useState({ status: "idle", at: 0, changes: 0 });
  const [errors, setErrors] = useState([]);
  const [publishErrors, setPublishErrors] = useState(null);
  const [conflict, setConflict] = useState(null);
  const [, tick] = useState(0);
  const iframeRef = useRef(null);
  const boxRef = useRef(null);
  const [boxW, setBoxW] = useState(1000);
  const dirty = useRef(false);
  const lastPush = useRef({ t: 0, key: "" });
  const revRef = useRef(null);
  revRef.current = rev;

  // ---------------------------------------------------------- yükle
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/page-design/${PAGE}`, { headers: headers() });
      const pub = r.data.published;
      const dr = r.data.draft;
      setPublished(pub);
      const src = dr || pub;
      setDoc({ blocks: clone(src.blocks || []), global: withGlobalDefaults(src.global || pub.global || {}) });
      setRev(dr ? dr.rev : null);
      setPast([]); setFuture([]);
      setSaveState({ status: dr ? "saved" : "idle", at: dr ? Date.parse(dr.updated_at) || Date.now() : 0, changes: 0 });
      if (dr?.stale) toast.warning("Taslak, yayındaki sürümden eski bir temele dayanıyor. Yayınlarsanız yayındaki değişikliklerin üzerine yazılır.");
      setSelectedId((cur) => cur || (src.blocks || [])[0]?.id || null);
    } catch (e) {
      toast.error(`Sayfa tasarımı yüklenemedi: ${e?.response?.data?.detail || e.message}`);
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(() => tick((x) => x + 1), 5000); return () => clearInterval(t); }, []);

  // ---------------------------------------------------------- değişiklik + geçmiş
  const docRef = useRef(doc);
  docRef.current = doc;
  const markDirty = (n = 1) => { dirty.current = true; setSaveState((st) => ({ ...st, status: "dirty", changes: st.changes + n })); };
  const commit = useCallback((updater, coalesceKey = "") => {
    const cur = docRef.current;
    const next = typeof updater === "function" ? updater(cur) : updater;
    if (!next || next === cur) return;
    const now = Date.now();
    const merge = !!coalesceKey && lastPush.current.key === coalesceKey && now - lastPush.current.t < 800;
    if (!merge) { setPast((p) => [...p.slice(-(HISTORY - 1)), cur]); setFuture([]); }
    lastPush.current = { t: now, key: coalesceKey };
    docRef.current = next;
    setDoc(next);
    markDirty(merge ? 0 : 1);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const undo = useCallback(() => {
    if (!past.length) return;
    const prev = past[past.length - 1];
    setPast(past.slice(0, -1));
    setFuture([docRef.current, ...future].slice(0, HISTORY));
    docRef.current = prev; setDoc(prev); lastPush.current = { t: 0, key: "" }; markDirty(1);
  }, [past, future]); // eslint-disable-line react-hooks/exhaustive-deps
  const redo = useCallback(() => {
    if (!future.length) return;
    const nxt = future[0];
    setFuture(future.slice(1));
    setPast([...past, docRef.current].slice(-HISTORY));
    docRef.current = nxt; setDoc(nxt); lastPush.current = { t: 0, key: "" }; markDirty(1);
  }, [past, future]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const onKey = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.key.toLowerCase() !== "z") return;
      const tag = (e.target?.tagName || "").toLowerCase();
      if ((tag === "input" || tag === "textarea" || e.target?.isContentEditable)) return;
      e.preventDefault();
      if (e.shiftKey) redo(); else undo();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redo]);

  const patchBlock = (id, patch, key) => commit((d) => ({ ...d, blocks: d.blocks.map((b) => (b.id === id ? { ...b, ...patch } : b)) }), key);
  const setSettings = (id, settings) => patchBlock(id, { settings }, `settings:${id}`);
  const setGlobal = (k, v) => commit((d) => ({ ...d, global: { ...d.global, [k]: v } }), `global:${k}`);

  // ---------------------------------------------------------- otomatik taslak (3 sn)
  const saveDraft = useCallback(async (force = false, overrideRev) => {
    if (!dirty.current && !force) return true;
    dirty.current = false;
    setSaveState((s) => ({ ...s, status: "saving" }));
    const body = { blocks: docRef.current.blocks, global: docRef.current.global };
    const r0 = overrideRev !== undefined ? overrideRev : revRef.current;
    try {
      const r = await axios.put(`${API}/page-design/${PAGE}/draft`, body, { headers: { ...headers(), ...(r0 != null ? { "If-Match": String(r0) } : {}) } });
      setRev(r.data.rev);
      setErrors(r.data.errors || []);
      setSaveState((s) => ({ ...s, status: "saved", at: Date.now() }));
      return true;
    } catch (e) {
      if (e?.response?.status === 409) { setConflict(e.response.data?.draft || {}); setSaveState((s) => ({ ...s, status: "conflict" })); }
      else { dirty.current = true; setSaveState((s) => ({ ...s, status: "error" })); toast.error(`Taslak kaydedilemedi: ${e?.response?.data?.detail || e.message}`); }
      return false;
    }
  }, []);
  useEffect(() => {
    if (loading || !dirty.current) return undefined;
    const t = setTimeout(() => { saveDraft(); }, 3000);
    return () => clearTimeout(t);
  }, [doc, loading, saveDraft]);
  useEffect(() => {
    const warn = (e) => { if (dirty.current) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  // ---------------------------------------------------------- önizleme köprüsü
  const previewDoc = revPreview || doc;
  const postDraft = useCallback(() => {
    const w = iframeRef.current?.contentWindow;
    if (!w) return;
    w.postMessage({ type: "pd:draft", layout: { blocks: previewDoc.blocks }, global: previewDoc.global, selectedId }, window.location.origin);
  }, [previewDoc, selectedId]);
  useEffect(() => { const t = setTimeout(postDraft, 150); return () => clearTimeout(t); }, [postDraft]);
  useEffect(() => {
    const onMsg = (e) => {
      if (e.origin !== window.location.origin || e.source !== iframeRef.current?.contentWindow) return;
      const m = e.data || {};
      if (m.type === "pd:ready") postDraft();
      else if (m.type === "pd:select") { setLeftTab("blocks"); setSelectedId(m.blockId); setFocusPath(m.field ? `${m.field}#${Date.now()}` : null); }
      else if (m.type === "pd:insert") setGallery({ index: m.index });
    };
    window.addEventListener("message", onMsg);
    return () => window.removeEventListener("message", onMsg);
  }, [postDraft]);
  const selectBlock = (id) => {
    setSelectedId(id); setFocusPath(null);
    iframeRef.current?.contentWindow?.postMessage({ type: "pd:select", blockId: id }, window.location.origin);
  };
  useEffect(() => {
    if (!boxRef.current || typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(([en]) => setBoxW(en.contentRect.width));
    ro.observe(boxRef.current);
    return () => ro.disconnect();
  }, []);

  // ---------------------------------------------------------- blok işlemleri
  const insertAt = (key, variant, index) => {
    const b = instantiate(key, variant || undefined);
    commit((d) => {
      const i = index == null ? d.blocks.length : Math.max(0, Math.min(d.blocks.length, index));
      return { ...d, blocks: [...d.blocks.slice(0, i), b, ...d.blocks.slice(i)] };
    });
    setSelectedId(b.id);
    setGallery(null);
    setTimeout(() => iframeRef.current?.contentWindow?.postMessage({ type: "pd:select", blockId: b.id }, window.location.origin), 400);
  };
  const dupBlock = (id) => {
    const d = docRef.current;
    const i = d.blocks.findIndex((b) => b.id === id);
    const c = duplicateBlock(d.blocks[i]);
    commit({ ...d, blocks: [...d.blocks.slice(0, i + 1), c, ...d.blocks.slice(i + 1)] });
    setSelectedId(c.id);
  };
  const delBlock = async (id) => {
    const b = doc.blocks.find((x) => x.id === id);
    if (!(await ask(`“${b?.title || b?.type}” bloğu silinsin mi? (Geri al ile geri getirebilirsiniz)`))) return;
    commit((d) => ({ ...d, blocks: d.blocks.filter((x) => x.id !== id) }));
    if (selectedId === id) setSelectedId(null);
  };
  const moveBlock = (id, dir) => commit((d) => {
    const i = d.blocks.findIndex((b) => b.id === id);
    const j = i + dir;
    if (j < 0 || j >= d.blocks.length) return d;
    return { ...d, blocks: arrayMove(d.blocks, i, j) };
  });
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    commit((d) => {
      const ids = d.blocks.map((b) => b.id);
      return { ...d, blocks: arrayMove(d.blocks, ids.indexOf(active.id), ids.indexOf(over.id)) };
    });
  };

  // ---------------------------------------------------------- yayın / at / geri yükle
  const publish = async () => {
    if (!(await saveDraft(true))) return;
    try {
      await axios.post(`${API}/page-design/${PAGE}/publish`, {}, { headers: headers() });
      toast.success("Yayınlandı — vitrin güncellendi.");
      setPublishErrors(null);
      dirty.current = false;
      await load();
    } catch (e) {
      if (e?.response?.status === 422) { setPublishErrors(e.response.data?.errors || []); setErrors(e.response.data?.errors || []); toast.error("Yayınlanamadı — hataları düzeltin."); }
      else toast.error(`Yayınlanamadı: ${e?.response?.data?.detail || e.message}`);
    }
  };
  const discard = async () => {
    if (!(await ask("Taslak atılsın mı? Yayındaki sürüme dönülür; kaydedilmemiş tüm değişiklikler kaybolur."))) return;
    await axios.delete(`${API}/page-design/${PAGE}/draft`, { headers: headers() }).catch(() => {});
    dirty.current = false;
    await load();
    toast.success("Taslak atıldı.");
  };
  const restore = async (r) => {
    if (!(await ask(`#${r} numaralı sürüm taslağa yüklensin mi? (Yayınlamadan önce kontrol edebilirsiniz)`))) return;
    await saveDraft(true);
    await axios.post(`${API}/page-design/${PAGE}/revisions/${r}/restore`, {}, { headers: headers() });
    setRevPreview(null); setShowRevs(false);
    dirty.current = false;
    await load();
    toast.success(`#${r} sürümü taslağa yüklendi.`);
  };
  const previewRev = async (r) => {
    const res = await axios.get(`${API}/page-design/${PAGE}/revisions/${r}`, { headers: headers() });
    setRevPreview({ blocks: res.data.blocks || [], global: withGlobalDefaults(res.data.global || {}), rev: r });
  };
  const installDefault = async () => {
    if (!(await ask("Şablon (v1.0 ana sayfa) düzeni yüklensin mi? Üst barlar dışındaki bloklar şablon bloklarıyla değiştirilir — geri al ile dönebilirsiniz."))) return;
    const top = doc.blocks.filter((b) => b.type === "rotating_text" || b.type === "countdown_bar");
    const fresh = [["hero_slider", "v1", "Ana Slider"], ["ads_block", "v1", "Reklam Kutuları"], ["deals_tabs", "v1", "Özel Teklif ve Ürün Sekmeleri"],
      ["product_grid_212", "2_1_2", "Kategori Fırsatları (2-1-2)"], ["best_sellers", "", "Çok Satanlar"], ["full_banner", "image", "Tam Genişlik Banner"],
      ["product_slider", "", "Yeni Eklenenler"], ["brands_carousel", "", "Markalar"], ["product_columns", "", "Alt Ürün Sütunları"]].map(([k, v, t]) => instantiate(k, v || undefined, t));
    commit((d) => ({ ...d, blocks: [...top, ...fresh] }));
  };
  const resolveConflict = async (mode) => {
    const server = conflict || {};
    setConflict(null);
    if (mode === "theirs") { dirty.current = false; await load(); return; }
    if (mode === "merge") {
      const mine = new Map(doc.blocks.map((b) => [b.id, b]));
      const merged = (server.blocks || []).map((b) => mine.get(b.id) || b);
      doc.blocks.forEach((b) => { if (!merged.some((x) => x.id === b.id)) merged.push(b); });
      commit((d) => ({ ...d, blocks: merged }));
    }
    setRev(server.rev);
    await saveDraft(true, server.rev);
  };

  // ---------------------------------------------------------- türetilmiş
  const selected = doc.blocks.find((b) => b.id === selectedId) || null;
  const entry = selected ? getBlock(selected.type) : null;
  const blockErrors = (id) => errors.filter((e) => e.block_id === id);
  const fields = useMemo(() => (entry ? allFields(entry.schema) : []), [entry]);
  const tabs = useMemo(() => [...(entry?.schema.tabs || ["İçerik"]), "Görünürlük"], [entry]);
  const defaults = useMemo(() => (selected && entry ? defaultSettings(selected.type, selected.settings?._variant) : {}), [selected?.type, selected?.settings?._variant, entry]); // eslint-disable-line react-hooks/exhaustive-deps
  const existing = useMemo(() => new Set(doc.blocks.map((b) => b.type)), [doc.blocks]);
  const devW = DEVICES.find((d) => d[0] === device)[1];
  const scale = Math.min(1, (boxW - 16) / devW);
  const status = {
    idle: "Yayındaki sürüm — değişiklik yok",
    dirty: `Taslak — ${saveState.changes} değişiklik, kaydediliyor…`,
    saving: "Taslak kaydediliyor…",
    saved: `Taslak — ${saveState.changes} değişiklik, ${ago(saveState.at)} otomatik kaydedildi`,
    error: "Taslak kaydedilemedi — tekrar denenecek",
    conflict: "Çakışma — başka bir yönetici değişiklik yaptı",
  }[saveState.status];
  const hasDraft = rev != null || saveState.status === "dirty";

  if (loading && !published) return <div className="p-8 text-gray-500" data-testid="page-design-loading">Sayfa tasarımı yükleniyor…</div>;

  return (
    <div className="flex flex-col h-[calc(100vh-64px)] -m-4 md:-m-6 bg-gray-100" data-testid="page-design">
      {/* üst çubuk */}
      <div className="flex flex-wrap items-center gap-2 px-3 py-2 bg-white border-b">
        <select className="border rounded px-2 py-1 text-sm" value={PAGE} aria-label="Sayfa" onChange={() => {}}><option value="home">Sayfa: Ana Sayfa</option></select>
        <div className="inline-flex rounded border overflow-hidden" role="group" aria-label="Cihaz">
          {DEVICES.map(([k, w, Icon, l]) => (
            <button key={k} type="button" onClick={() => setDevice(k)} aria-pressed={device === k} title={`${l} (${w}px)`}
              className={`px-2 py-1 flex items-center gap-1 text-xs ${device === k ? "bg-gray-800 text-white" : "bg-white"}`} data-testid={`device-${k}`}><Icon size={14} />{l}</button>
          ))}
        </div>
        <button type="button" className="p-1.5 border rounded disabled:opacity-30" onClick={undo} disabled={!past.length} title="Geri al (Ctrl+Z)" aria-label="Geri al" data-testid="undo"><Undo2 size={15} /></button>
        <button type="button" className="p-1.5 border rounded disabled:opacity-30" onClick={redo} disabled={!future.length} title="İleri al (Ctrl+Shift+Z)" aria-label="İleri al" data-testid="redo"><Redo2 size={15} /></button>
        <button type="button" className="px-2 py-1 border rounded text-xs flex items-center gap-1" onClick={() => setShowRevs(true)} data-testid="open-revisions"><History size={14} /> Revizyonlar</button>
        <span className={`text-xs ml-2 ${saveState.status === "error" || saveState.status === "conflict" ? "text-red-600" : "text-gray-600"}`} data-testid="save-status">{status}</span>
        <div className="flex-1" />
        {revPreview && <span className="text-xs bg-blue-50 text-blue-800 border border-blue-200 rounded px-2 py-1">#{revPreview.rev} önizleniyor <button type="button" className="underline ml-1" onClick={() => setRevPreview(null)}>kapat</button></span>}
        <button type="button" className="px-2 py-1 border rounded text-xs flex items-center gap-1" onClick={installDefault} title="Şablon v1.0 ana sayfa düzeni"><LayoutTemplate size={14} /> Şablon düzeni</button>
        {hasDraft && <button type="button" className="px-2 py-1 border rounded text-xs text-red-600" onClick={discard} data-testid="discard-draft">Taslağı at</button>}
        <a href={`/onizleme/sayfa/${PAGE}`} target="_blank" rel="noreferrer" className="px-2 py-1 border rounded text-xs flex items-center gap-1" onClick={() => saveDraft(true)}><ExternalLink size={14} /> Önizle</a>
        <button type="button" onClick={publish} disabled={saveState.status === "saving"} className="px-3 py-1.5 rounded bg-yellow-400 hover:bg-yellow-300 font-semibold text-sm disabled:opacity-50" data-testid="publish">
          Yayınla{errors.length ? ` (${errors.length} hata)` : ""}
        </button>
      </div>
      {publishErrors && publishErrors.length > 0 && (
        <div className="bg-red-50 border-b border-red-200 px-3 py-2 text-xs text-red-800" data-testid="publish-errors">
          <div className="flex justify-between font-semibold">Yayınlanamadı — şu alanları düzeltin:<button type="button" onClick={() => setPublishErrors(null)} aria-label="Kapat"><X size={14} /></button></div>
          <ul className="list-disc ml-5 mt-1 max-h-24 overflow-auto">
            {publishErrors.map((e, i) => (
              <li key={i}><button type="button" className="underline text-left" onClick={() => { if (e.block_id) { setLeftTab("blocks"); selectBlock(e.block_id); setFocusPath(`${normErrPath(e.path)}#${Date.now()}`); } else if (e.global_key) { setLeftTab("global"); setGlobalKey(e.global_key); } }}>{e.label} — {e.message}</button></li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-1 min-h-0">
        {/* sol panel */}
        <aside className="w-[360px] shrink-0 bg-white border-r flex flex-col min-h-0" aria-label="Düzenleyici">
          <div className="flex border-b" role="tablist">
            {[["blocks", "Bloklar"], ["global", "Genel Alanlar"]].map(([k, l]) => (
              <button key={k} type="button" role="tab" aria-selected={leftTab === k} onClick={() => setLeftTab(k)}
                className={`flex-1 py-2 text-sm ${leftTab === k ? "border-b-2 border-yellow-400 font-semibold" : "text-gray-600"}`} data-testid={`tab-${k}`}>{l}</button>
            ))}
          </div>
          <div className="flex-1 overflow-auto p-2">
            {leftTab === "blocks" ? (
              <>
                <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
                  <SortableContext items={doc.blocks.map((b) => b.id)} strategy={verticalListSortingStrategy}>
                    {doc.blocks.map((b, i) => (
                      <BlockRow key={b.id} block={b} index={i} total={doc.blocks.length} selected={b.id === selectedId} errorCount={blockErrors(b.id).length}
                        onSelect={() => selectBlock(b.id)} onPatch={(p) => patchBlock(b.id, p)} onDup={() => dupBlock(b.id)} onDel={() => delBlock(b.id)} onMove={(d) => moveBlock(b.id, d)} />
                    ))}
                  </SortableContext>
                </DndContext>
                <button type="button" className="w-full mt-1 py-2 border-2 border-dashed rounded text-sm text-gray-700 hover:border-yellow-400 flex items-center justify-center gap-1"
                  onClick={() => setGallery({ index: selected ? doc.blocks.indexOf(selected) + 1 : null })} data-testid="add-block"><Plus size={15} /> Blok Ekle</button>
                {selected && (
                  <div className="mt-3 border-t pt-3" data-testid="block-editor">
                    {!entry || selected.settings?._legacy ? (
                      <div className="text-xs bg-amber-50 border border-amber-200 rounded p-2 text-amber-800">
                        <b>Desteklenmeyen eski blok</b> ({selected.type}). Vitrinde gösterilmez. Silmek size kalmış; verisi yedekte korunur.
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center gap-2 mb-2">
                          <input className="flex-1 border rounded px-2 py-1 text-sm font-semibold" value={selected.title || ""} placeholder={entry.schema.title}
                            onChange={(e) => patchBlock(selected.id, { title: e.target.value }, `title:${selected.id}`)} aria-label="Blok adı (yalnız panelde)" />
                          <button type="button" className="text-xs border rounded px-2 py-1 flex items-center gap-1 hover:bg-yellow-50" title="Şablon varsayılanına sıfırla"
                            onClick={async () => { if (await ask("Bu blok şablon varsayılanına sıfırlansın mı? (Geri al ile dönebilirsiniz)")) commit((d) => ({ ...d, blocks: d.blocks.map((b) => (b.id === selected.id ? resetBlock(b) : b)) })); }}
                            data-testid="reset-block"><RotateCcw size={12} /> Şablon varsayılanına sıfırla</button>
                        </div>
                        <div className="text-[11px] text-gray-500 mb-2">Blok tipi: <b>{entry.schema.title}</b> (değiştirilemez)</div>
                        {(entry.schema.variants || []).length > 1 && (
                          <label className="block text-xs mb-3">Görünüm
                            <select className="mt-1 w-full border rounded px-2 py-1 text-sm" value={selected.settings?._variant || entry.schema.variants[0].value}
                              onChange={async (e) => { const v = e.target.value; if (await ask("Görünüm değiştirilsin mi? Bu görünüme özgü varsayılan ayarlar uygulanır, diğer alanlarınız korunur.")) commit((d) => ({ ...d, blocks: d.blocks.map((b) => (b.id === selected.id ? applyVariant(b, v) : b)) })); }}
                              data-testid="variant-select">
                              {entry.schema.variants.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
                            </select>
                          </label>
                        )}
                        {selected.settings?._migration_errors?.length > 0 && (
                          <div className="text-[11px] bg-amber-50 border border-amber-200 rounded p-2 mb-2 text-amber-800">Geçiş uyarıları: {selected.settings._migration_errors.join(" · ")}</div>
                        )}
                        <SchemaForm key={selected.id} fields={fields} tabs={tabs} value={withDefaults(selected.type, selected.settings)} defaults={defaults}
                          onChange={(s) => setSettings(selected.id, s)} errors={blockErrors(selected.id)} ctx={{ superAdmin }}
                          focusPath={focusPath ? focusPath.split("#")[0] : null} testId="block-form" />
                      </>
                    )}
                  </div>
                )}
                <div className="mt-6"><DemoContentCard onChanged={load} /></div>
              </>
            ) : (
              <div data-testid="global-editor">
                <select className="w-full border rounded px-2 py-1.5 text-sm mb-3" value={globalKey} onChange={(e) => setGlobalKey(e.target.value)} aria-label="Genel alan">
                  {GLOBAL_GROUPS.filter(([k]) => globalKeys().includes(k)).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
                {getGlobal(globalKey)?.schema.description && <div className="text-[11px] text-gray-500 mb-2">{getGlobal(globalKey).schema.description}</div>}
                {MENU_LINKS[globalKey] && (
                  <Link to={`/admin/menu-yonetimi?grup=${MENU_LINKS[globalKey]}`} className="inline-block text-xs text-blue-700 underline mb-3">Menü öğelerini düzenle → Menü Yönetimi</Link>
                )}
                {globalKey === "site_theme" && <ThemePresets value={doc.global.site_theme} onChange={(v) => setGlobal("site_theme", v)} />}
                <SchemaForm key={globalKey} fields={getSchema(globalKey)?.fields || []} tabs={getSchema(globalKey)?.tabs || ["İçerik"]}
                  value={withDefaults(globalKey, doc.global[globalKey])} defaults={defaultSettings(globalKey)}
                  onChange={(v) => setGlobal(globalKey, v)} errors={errors.filter((e) => e.global_key === globalKey).map((e) => ({ ...e, path: e.path.replace(`${globalKey}.`, "") }))}
                  ctx={{ superAdmin }} testId="global-form" />
                <button type="button" className="mt-3 text-xs border rounded px-2 py-1 flex items-center gap-1" onClick={async () => { if (await ask("Bu alan şablon varsayılanına sıfırlansın mı?")) setGlobal(globalKey, defaultSettings(globalKey)); }}>
                  <RotateCcw size={12} /> Şablon varsayılanına sıfırla
                </button>
              </div>
            )}
          </div>
        </aside>
        {/* önizleme */}
        <section ref={boxRef} className="flex-1 min-w-0 overflow-auto p-2" aria-label="Canlı önizleme">
          <div style={{ width: devW * scale, height: `calc((100vh - 130px))`, margin: "0 auto" }}>
            <iframe ref={iframeRef} title="Canlı önizleme" src={`/onizleme/sayfa/${PAGE}`} data-testid="preview-frame"
              style={{ width: devW, height: `calc((100vh - 130px) / ${scale})`, transform: `scale(${scale})`, transformOrigin: "0 0", border: 0, background: "#fff", boxShadow: "0 1px 6px rgba(0,0,0,.15)" }}
              onLoad={() => setTimeout(postDraft, 50)} />
          </div>
        </section>
      </div>
      {gallery && <Gallery existing={existing} onClose={() => setGallery(null)} onPick={(k, v) => insertAt(k, v, gallery.index)} />}
      {showRevs && <Revisions onClose={() => { setShowRevs(false); setRevPreview(null); }} onRestore={restore} onPreview={previewRev} />}
      {conflict && (
        <div className="fixed inset-0 z-[95] bg-black/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" data-testid="conflict-dialog">
          <div className="bg-white rounded-lg shadow-xl p-5 max-w-md w-full">
            <div className="font-semibold mb-2">Başka bir yönetici değişiklik yaptı</div>
            <p className="text-sm text-gray-600 mb-4">Taslak siz düzenlerken başka bir oturumda değiştirildi ({conflict.updated_by || "bilinmiyor"}). Ne yapalım?</p>
            <div className="flex flex-wrap gap-2 justify-end">
              <button type="button" className="border rounded px-3 py-1.5 text-sm" onClick={() => resolveConflict("theirs")}>Vazgeç (onların sürümü)</button>
              <button type="button" className="border rounded px-3 py-1.5 text-sm" onClick={() => resolveConflict("merge")}>Birleştir</button>
              <button type="button" className="rounded px-3 py-1.5 text-sm bg-yellow-400 font-semibold" onClick={() => resolveConflict("mine")}>Üzerine yaz</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function ThemePresets({ value, onChange }) {
  const opts = (getSchema("site_theme")?.fields || []).find((f) => f.name === "preset")?.options || [];
  return (
    <div className="mb-3">
      <div className="text-xs font-semibold mb-1">Renk ön ayarları</div>
      <div className="flex flex-wrap gap-1.5">
        {opts.filter((o) => o.primary).map((o) => (
          <button key={o.value} type="button" title={o.label} aria-label={o.label} onClick={() => onChange({ ...value, preset: o.value, primary_color: o.primary, primary_dark: o.primary_dark, text_on_primary: o.text_on_primary })}
            className={`w-7 h-7 rounded-full border-2 ${value?.preset === o.value ? "border-gray-900" : "border-white shadow"}`} style={{ background: o.primary }} data-testid={`preset-${o.value}`} />
        ))}
      </div>
    </div>
  );
}
