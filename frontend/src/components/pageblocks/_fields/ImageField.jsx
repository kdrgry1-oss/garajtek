// Görsel alanı (SPEC §5.1/6): sürükle-bırak yükleme, önerilen ölçü ipucu + kalite uyarısı, önerilen orana
// kırpma, odak noktası (tıkla → focal → vitrinde object-position), alt metin, mobil görsel, medya kütüphanesi,
// istemci sıkıştırma (2400 px, WebP 0.86).
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import axios from "axios";
import { Crop, ImageIcon, Library, Upload, X } from "lucide-react";
import { API, authHeaders, BACKEND_ORIGIN, clientCompress, cropToRatio, imageSize, uploadMedia } from "./adminData";
import { inputCls, smallBtn } from "./widgets";

const abs = (u) => (u && u.startsWith("/") && BACKEND_ORIGIN ? `${BACKEND_ORIGIN}${u}` : u);
const isVideo = (u) => /\.(mp4|webm|mov|m4v|ogg)(\?|$)/i.test(String(u || ""));

function MediaLibrary({ onPick, onClose, video }) {
  const [items, setItems] = useState(null);
  useEffect(() => {
    axios.get(`${API}/page-design/media?limit=80`, { headers: authHeaders() }).then((r) => setItems(r.data?.items || [])).catch(() => setItems([]));
  }, []);
  const list = (items || []).filter((x) => (video ? /^video\//.test(x.type || "") || isVideo(x.url) : !/^video\//.test(x.type || "")));
  return (
    <div className="fixed inset-0 z-[100] bg-black/40 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Medya kütüphanesi" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-4 py-2 border-b">
          <div className="font-semibold text-sm">Medya kütüphanesi</div>
          <button type="button" onClick={onClose} aria-label="Kapat"><X size={16} /></button>
        </div>
        <div className="p-3 overflow-auto grid grid-cols-4 sm:grid-cols-6 gap-2">
          {items === null && <div className="col-span-6 text-sm text-gray-500">Yükleniyor…</div>}
          {items && !list.length && <div className="col-span-6 text-sm text-gray-500">Henüz yüklenmiş dosya yok.</div>}
          {list.map((m) => (
            <button key={m.url} type="button" className="border rounded overflow-hidden hover:ring-2 hover:ring-yellow-400 bg-gray-50 aspect-square" title={m.name}
              onClick={() => onPick(m)}>
              {isVideo(m.url) ? <span className="text-[10px]">{m.name || "video"}</span> : <img src={abs(m.url)} alt={m.name} className="w-full h-full object-cover" loading="lazy" />}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function Slot({ url, onFile, onClear, onPickLib, label, rec, busy, focal, onFocal, testId }) {
  const [drag, setDrag] = useState(false);
  const ref = useRef(null);
  const ratio = rec ? `${rec[0]} / ${rec[1]}` : "16 / 9";
  return (
    <div>
      <div className={`relative border-2 rounded overflow-hidden bg-gray-50 ${drag ? "border-yellow-400 border-dashed" : "border-gray-200"}`}
        style={{ aspectRatio: ratio, maxHeight: 180 }}
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f) onFile(f); }} data-testid={testId}>
        {url ? (
          isVideo(url) ? <video src={abs(url)} className="w-full h-full object-cover" muted /> : (
            <img ref={ref} src={abs(url)} alt="" className={`w-full h-full object-cover ${onFocal ? "cursor-crosshair" : ""}`}
              style={focal ? { objectPosition: `${focal.x * 100}% ${focal.y * 100}%` } : undefined}
              onClick={(e) => {
                if (!onFocal) return;
                const r = e.currentTarget.getBoundingClientRect();
                onFocal({ x: Math.round(((e.clientX - r.left) / r.width) * 100) / 100, y: Math.round(((e.clientY - r.top) / r.height) * 100) / 100 });
              }} />
          )
        ) : (
          <label className="absolute inset-0 flex flex-col items-center justify-center text-gray-400 text-xs cursor-pointer">
            <ImageIcon size={20} />
            <span className="mt-1">{busy ? "Yükleniyor…" : `${label} — sürükleyin veya tıklayın`}</span>
            {rec && <span>{rec[0]} × {rec[1]} px</span>}
            <input type="file" accept="image/*,video/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onFile(f); }} />
          </label>
        )}
        {url && focal && onFocal && (
          <span className="absolute w-4 h-4 -ml-2 -mt-2 rounded-full border-2 border-white bg-yellow-400 shadow pointer-events-none"
            style={{ left: `${focal.x * 100}%`, top: `${focal.y * 100}%` }} aria-hidden="true" />
        )}
      </div>
      <div className="flex flex-wrap gap-1 mt-1">
        <label className={`${smallBtn} cursor-pointer`}>
          <Upload size={12} /> {url ? "Değiştir" : "Yükle"}
          <input type="file" accept="image/*,video/*" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) onFile(f); }} />
        </label>
        <button type="button" className={smallBtn} onClick={onPickLib}><Library size={12} /> Kütüphane</button>
        {url && <button type="button" className={`${smallBtn} text-red-600`} onClick={onClear}><X size={12} /> Kaldır</button>}
      </div>
    </div>
  );
}

export default function ImageField({ field, value, onChange }) {
  const v = value && typeof value === "object" ? value : (typeof value === "string" && value ? { url: value } : null);
  const rec = field.recommended || null;
  const mrec = field.mobile_recommended || null;
  const [busy, setBusy] = useState(false);
  const [lib, setLib] = useState(null);
  const [cropOn, setCropOn] = useState(!!field.aspect_lock);
  const [dims, setDims] = useState(null);
  const video = /video/.test(field.accept || "") && !/image/.test(field.accept || "");

  useEffect(() => {
    let alive = true;
    if (v?.url && !isVideo(v.url)) imageSize(v.url).then((d) => { if (alive) setDims(d); });
    else setDims(null);
    return () => { alive = false; };
  }, [v?.url]);

  const put = (patch) => {
    const next = { ...(v || { url: "", alt: "" }), ...patch };
    onChange(next.url || next.mobile_url ? next : null);
  };

  const upload = async (file, which = "url") => {
    if (!file) return;
    setBusy(true);
    try {
      const vid = /^video\//.test(file.type);
      let f = file;
      const r = which === "mobile_url" ? mrec : rec;
      if (!vid && cropOn && r) f = await cropToRatio(f, r[0] / r[1], (which === "mobile_url" ? v?.mobile_focal : v?.focal) || { x: 0.5, y: 0.5 });
      let w = 0; let h = 0;
      if (!vid) ({ file: f, w, h } = await clientCompress(f));
      const url = await uploadMedia(f, { video: vid });
      const patch = { [which]: url };
      if (which === "url" && w && h) { patch.w = w; patch.h = h; }
      put(patch);
      toast.success(vid ? "Video yüklendi" : "Görsel yüklendi");
    } catch (e) {
      toast.error(`Yüklenemedi: ${e?.response?.data?.detail || e.message}`);
    } finally { setBusy(false); }
  };

  // ölçü ipucu ve kalite uyarısı
  let hint = null;
  if (rec) {
    const base = `Önerilen ${rec[0]}×${rec[1]} px`;
    if (dims) {
      const pct = Math.round((dims[0] / rec[0]) * 100);
      const ratioDiff = Math.abs(dims[0] / dims[1] - rec[0] / rec[1]) > 0.03;
      const small = dims[0] < rec[0] * 0.9;
      hint = (
        <p className={`text-[11px] rounded px-2 py-1 inline-block border ${small || ratioDiff ? "text-amber-800 bg-amber-50 border-amber-200" : "text-blue-700 bg-blue-50 border-blue-100"}`} data-testid="size-hint">
          {base} — yüklenen {dims[0]}×{dims[1]}, %{pct}{small ? " (küçük: bulanık görünebilir)" : ""}{ratioDiff ? " · oran farklı, kırpılacak" : ""}
        </p>
      );
    } else {
      hint = <p className="text-[11px] text-blue-700 bg-blue-50 border border-blue-100 rounded px-2 py-1 inline-block" data-testid="size-hint">{base}</p>;
    }
  }

  return (
    <div className="space-y-1.5">
      <Slot url={v?.url} label={video ? "Video" : "Görsel"} rec={rec} busy={busy} focal={v?.focal || (field.focal_default ? field.focal_default : null)}
        onFocal={v?.url && !isVideo(v?.url) ? (f) => put({ focal: f }) : null} testId={`image-${field.name}`}
        onFile={(f) => upload(f, "url")} onClear={() => onChange(v?.mobile_url ? { ...v, url: "" } : null)} onPickLib={() => setLib("url")} />
      <div className="flex flex-wrap items-center gap-2">
        {hint}
        {rec && !video && (
          <label className="text-[11px] flex items-center gap-1"><input type="checkbox" checked={cropOn} onChange={(e) => setCropOn(e.target.checked)} /> <Crop size={11} /> Yüklerken önerilen orana kırp</label>
        )}
      </div>
      {v?.url && !isVideo(v.url) && (
        <>
          <div className="text-[11px] text-gray-500">Odak noktası: görselde önemli yere tıklayın{v.focal ? ` (%${Math.round(v.focal.x * 100)}, %${Math.round(v.focal.y * 100)})` : ""}.</div>
          <input type="text" className={inputCls} placeholder="Alternatif metin (erişilebilirlik ve SEO için)" value={v.alt || ""} onChange={(e) => put({ alt: e.target.value })} aria-label="Alternatif metin" />
          {!v.alt && <div className="text-[11px] text-amber-700">Alternatif metin girmeniz önerilir.</div>}
        </>
      )}
      {field.allow_mobile && (
        <details className="border rounded p-2 bg-gray-50" open={!!v?.mobile_url}>
          <summary className="text-xs font-medium cursor-pointer">Mobil görsel (opsiyonel){mrec ? ` — önerilen ${mrec[0]}×${mrec[1]} px` : ""}</summary>
          <div className="mt-2">
            <Slot url={v?.mobile_url} label="Mobil görsel" rec={mrec} busy={busy} focal={v?.mobile_focal} onFocal={v?.mobile_url ? (f) => put({ mobile_focal: f }) : null}
              onFile={(f) => upload(f, "mobile_url")} onClear={() => { const n = { ...(v || {}) }; delete n.mobile_url; delete n.mobile_focal; onChange(n.url ? n : null); }} onPickLib={() => setLib("mobile_url")} />
          </div>
        </details>
      )}
      {lib && <MediaLibrary video={video} onClose={() => setLib(null)} onPick={(m) => { put({ [lib]: m.url, ...(lib === "url" && m.w && m.h ? { w: m.w, h: m.h } : {}) }); setLib(null); }} />}
    </div>
  );
}
