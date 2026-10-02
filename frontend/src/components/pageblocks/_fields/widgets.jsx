// Şema alan tipleri için panel widget'ları (SPEC §2.3). Tümü kontrollü: {field, value, onChange, ctx}.
// Karmaşık widget'lar ayrı dosyalarda: ImageField, LinkField, RichTextField, ProductSourceField, Pickers.
import { useState } from "react";
import { ChevronDown, ChevronRight, Copy, Eye, EyeOff, GripVertical, Plus, Trash2, Clock } from "lucide-react";
import { DndContext, closestCenter, KeyboardSensor, PointerSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { clone, isObj, itemDefault, plainText, uid, assignIds, DEVICES } from "../_shared/schema";

export const inputCls = "w-full border border-gray-300 rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-yellow-300 focus:border-yellow-400 bg-white";
export const smallBtn = "inline-flex items-center gap-1 text-xs px-2 py-1 rounded border border-gray-300 bg-white hover:bg-gray-50";

export function TextInput({ field, value, onChange, multiline }) {
  const max = field.max_length || (multiline ? 2000 : 200);
  const v = value ?? "";
  const common = {
    value: v, maxLength: max, placeholder: field.placeholder || "", className: inputCls,
    onChange: (e) => onChange(e.target.value), "aria-label": field.label,
  };
  return (
    <div>
      {multiline ? <textarea rows={field.rows || 3} {...common} /> : <input type="text" {...common} />}
      {String(v).length > max * 0.8 && <div className="text-[10px] text-gray-500 text-right">{String(v).length}/{max}</div>}
    </div>
  );
}

export function NumberInput({ field, value, onChange }) {
  return (
    <div className="flex items-center gap-1">
      <input type="number" className={inputCls} value={value ?? ""} min={field.min} max={field.max} step={field.step || 1} aria-label={field.label}
        onChange={(e) => { const n = e.target.value === "" ? "" : Number(e.target.value); onChange(n); }} />
      {field.unit && <span className="text-xs text-gray-500 shrink-0">{field.unit}</span>}
    </div>
  );
}

export function BoolInput({ field, value, onChange }) {
  return (
    <button type="button" role="switch" aria-checked={!!value} aria-label={field.label} onClick={() => onChange(!value)}
      className={`relative inline-flex h-5 w-9 shrink-0 rounded-full transition ${value ? "bg-yellow-400" : "bg-gray-300"}`}>
      <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition ${value ? "left-4" : "left-0.5"}`} />
    </button>
  );
}

export function SelectInput({ field, value, onChange }) {
  const opts = field.options || [];
  if (opts.length <= 4 && !field.dropdown) {
    return (
      <div className="inline-flex flex-wrap rounded border border-gray-300 overflow-hidden" role="radiogroup" aria-label={field.label}>
        {opts.map((o) => (
          <button key={String(o.value)} type="button" role="radio" aria-checked={String(value) === String(o.value)} onClick={() => onChange(o.value)}
            className={`px-2.5 py-1 text-xs border-r last:border-r-0 border-gray-300 ${String(value) === String(o.value) ? "bg-yellow-300 font-semibold" : "bg-white hover:bg-gray-50"}`}>
            {o.label}
          </button>
        ))}
      </div>
    );
  }
  return (
    <select className={inputCls} value={value ?? ""} aria-label={field.label}
      onChange={(e) => { const o = opts.find((x) => String(x.value) === e.target.value); onChange(o ? o.value : e.target.value); }}>
      {opts.map((o) => <option key={String(o.value)} value={String(o.value)}>{o.label}</option>)}
    </select>
  );
}

const THEME_COLORS = [
  ["var(--primary)", "Tema ana rengi"], ["#fed700", "Sarı"], ["#333e48", "Koyu"], ["#ffffff", "Beyaz"], ["#f5f5f5", "Açık gri"],
  ["#f9f9f9", "Gri bant"], ["#eaeaea", "Footer gri"], ["#df3737", "İndirim kırmızısı"], ["#0077d0", "Bağlantı mavisi"], ["#000000", "Siyah"],
];

export function ColorInput({ field, value, onChange }) {
  const v = value || "";
  const isHex = /^#[0-9a-f]{6}$/i.test(v);
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2">
        <input type="color" value={isHex ? v : "#ffffff"} onChange={(e) => onChange(e.target.value)} className="h-8 w-10 border rounded cursor-pointer" aria-label={field.label} />
        <input type="text" className={inputCls} value={v} placeholder="Varsayılan" onChange={(e) => onChange(e.target.value.trim())} />
        <button type="button" className={smallBtn} onClick={() => onChange("")} title="Şablon varsayılanı">Varsayılan</button>
      </div>
      {field.palette === "theme" && (
        <div className="flex flex-wrap gap-1">
          {THEME_COLORS.map(([c, l]) => (
            <button key={c} type="button" title={l} onClick={() => onChange(c)}
              className={`h-5 w-5 rounded border ${v === c ? "ring-2 ring-offset-1 ring-yellow-400" : "border-gray-300"}`}
              style={{ background: c === "var(--primary)" ? "linear-gradient(135deg,#fed700 50%,#333e48 50%)" : c }} />
          ))}
          {field.allow_transparent && <button type="button" className={smallBtn} onClick={() => onChange("transparent")}>Şeffaf</button>}
        </div>
      )}
    </div>
  );
}

/** ISO (ofsetli) ↔ datetime-local (İstanbul saati). */
export function DateTimeInput({ field, value, onChange }) {
  const toLocal = (s) => {
    if (!s) return "";
    if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(s)) return s;
    const d = new Date(s);
    if (Number.isNaN(d.getTime())) return "";
    const ist = new Date(d.getTime() + 3 * 3600 * 1000);
    return ist.toISOString().slice(0, 16);
  };
  return (
    <div className="flex items-center gap-1">
      <input type={field.with_time === false ? "date" : "datetime-local"} className={inputCls} value={toLocal(value)} aria-label={field.label}
        onChange={(e) => onChange(e.target.value ? `${e.target.value.length === 10 ? `${e.target.value}T00:00` : e.target.value}:00+03:00` : "")} />
      {value && <button type="button" className={smallBtn} onClick={() => onChange("")}>Temizle</button>}
    </div>
  );
}

export function HtmlInput({ field, value, onChange, ctx }) {
  if (!ctx?.superAdmin) return <div className="text-xs text-gray-500 italic">Yalnız süper yönetici düzenleyebilir.</div>;
  return <textarea rows={6} className={`${inputCls} font-mono text-xs`} value={value || ""} onChange={(e) => onChange(e.target.value)} aria-label={field.label} />;
}

const ICONS = ["ec ec-transport", "ec ec-customers", "ec ec-returning", "ec ec-payment", "ec ec-tag", "ec ec-support", "ec ec-newsletter",
  "ec ec-map-pointer", "ec ec-shopping-bag", "ec ec-user", "ec ec-favorites", "ec ec-compare", "ec ec-search", "ec ec-phone", "ec ec-mail",
  "ec ec-dollar", "ec ec-add-to-cart", "ec ec-arrow-right-categproes", "fa fa-list-ul", "fas fa-tools", "fas fa-truck", "fas fa-shield-alt",
  "fas fa-percent", "fas fa-headset", "fas fa-wrench", "fas fa-car", "fas fa-cog", "fas fa-bolt", "fab fa-instagram", "fab fa-whatsapp"];

export function IconInput({ field, value, onChange }) {
  const [open, setOpen] = useState(false);
  const v = isObj(value) ? value : { icon: typeof value === "string" ? value : "" };
  return (
    <div>
      <div className="flex items-center gap-2">
        <span className="h-8 w-8 border rounded flex items-center justify-center bg-gray-50 electro-icon-preview"><i className={v.icon} /></span>
        <input type="text" className={inputCls} value={v.icon || ""} placeholder="ec ec-transport" onChange={(e) => onChange({ ...v, icon: e.target.value })} aria-label={field.label} />
        <button type="button" className={smallBtn} onClick={() => setOpen((o) => !o)}>Galeri</button>
      </div>
      {open && (
        <div className="mt-1 grid grid-cols-8 gap-1 border rounded p-1 bg-white max-h-40 overflow-auto">
          {ICONS.map((ic) => (
            <button key={ic} type="button" title={ic} onClick={() => { onChange({ ...v, icon: ic }); setOpen(false); }}
              className={`h-8 border rounded flex items-center justify-center hover:bg-yellow-50 ${v.icon === ic ? "ring-2 ring-yellow-400" : ""}`}><i className={ic} /></button>
          ))}
        </div>
      )}
    </div>
  );
}

export function SpacingInput({ field, value, onChange }) {
  const v = isObj(value) ? value : { top: 0, bottom: 0 };
  return (
    <div className="flex items-center gap-2 text-xs">
      <label className="flex items-center gap-1">Üst <input type="number" className={`${inputCls} w-20`} value={v.top ?? 0} min={0} onChange={(e) => onChange({ ...v, top: Number(e.target.value) || 0 })} /></label>
      <label className="flex items-center gap-1">Alt <input type="number" className={`${inputCls} w-20`} value={v.bottom ?? 0} min={0} onChange={(e) => onChange({ ...v, bottom: Number(e.target.value) || 0 })} /></label>
      <span className="text-gray-500">px</span>
    </div>
  );
}

// ------------------------------------------------------------------ responsive
export function ResponsiveWrap({ value, onChange, children }) {
  const [dev, setDev] = useState("desktop");
  const isResp = isObj(value) && DEVICES.some((d) => d in value);
  const cur = isResp ? value[dev] : value;
  const set = (x) => {
    const base = isResp ? value : { desktop: value, tablet: value, mobile: value };
    onChange({ ...base, [dev]: x });
  };
  const labels = { desktop: "Masaüstü", tablet: "Tablet", mobile: "Mobil" };
  return (
    <div>
      <div className="inline-flex mb-1 rounded border border-gray-300 overflow-hidden" role="tablist" aria-label="Cihaz">
        {DEVICES.map((d) => (
          <button key={d} type="button" role="tab" aria-selected={dev === d} onClick={() => setDev(d)}
            className={`px-2 py-0.5 text-[11px] ${dev === d ? "bg-gray-800 text-white" : "bg-white"}`}>{labels[d]}</button>
        ))}
      </div>
      {children(cur, set)}
    </div>
  );
}

// ------------------------------------------------------------------ repeater
function itemTitle(field, item, i) {
  const tpl = field.item_label || "";
  const m = tpl.match(/\{\{(\w+)\}\}/);
  let t = m ? item?.[m[1]] : "";
  if (isObj(t)) t = t.label || t.url || "";
  t = plainText(t);
  return t || `${field.item_noun || "Öğe"} ${i + 1}`;
}

function SortableItem({ id, children }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }}>
      {children({ ...attributes, ...listeners })}
    </div>
  );
}

export function RepeaterInput({ field, value, onChange, renderFields, path }) {
  const items = Array.isArray(value) ? value : [];
  const [open, setOpen] = useState(() => new Set());
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 4 } }), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  const ids = items.map((it, i) => it?._id || `i${i}`);
  const max = field.max || 99;
  const set = (i, v) => onChange(items.map((x, k) => (k === i ? v : x)));
  const add = () => {
    const it = assignIds(field.item_fields, { ...clone(itemDefault(field)), _id: uid() }, true);
    onChange([...items, it]);
    setOpen((s) => new Set([...s, it._id]));
  };
  const dup = (i) => {
    const c = assignIds(field.item_fields, { ...clone(items[i]), _id: uid() }, true);
    onChange([...items.slice(0, i + 1), c, ...items.slice(i + 1)]);
  };
  const del = (i) => {
    if (field.min && items.length <= field.min) return;
    onChange(items.filter((_, k) => k !== i));
  };
  const toggle = (id) => setOpen((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return;
    onChange(arrayMove(items, ids.indexOf(active.id), ids.indexOf(over.id)));
  };
  return (
    <div className="space-y-1.5" data-testid={`repeater-${field.name}`}>
      <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          {items.map((it, i) => {
            const id = ids[i];
            const isOpen = open.has(id);
            return (
              <SortableItem key={id} id={id}>
                {(handle) => (
                  <div className={`border rounded bg-white ${it?._hidden ? "opacity-60" : ""}`}>
                    <div className="flex items-center gap-1 px-1.5 py-1 bg-gray-50 border-b">
                      {field.sortable !== false && <button type="button" className="p-1 cursor-grab text-gray-400" aria-label="Sürükle" {...handle}><GripVertical size={14} /></button>}
                      <button type="button" className="flex-1 flex items-center gap-1 text-left text-xs font-medium truncate" onClick={() => toggle(id)} aria-expanded={isOpen}>
                        {isOpen ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
                        <span className="truncate">{itemTitle(field, it, i)}</span>
                        {it?._schedule && (it._schedule.start || it._schedule.end) && <Clock size={12} className="text-blue-600 shrink-0" />}
                      </button>
                      {field.item_toggle !== false && (
                        <button type="button" className="p-1 text-gray-500 hover:text-gray-900" title={it?._hidden ? "Göster" : "Gizle"} aria-label={it?._hidden ? "Göster" : "Gizle"}
                          onClick={() => set(i, { ...it, _hidden: !it?._hidden })}>{it?._hidden ? <EyeOff size={13} /> : <Eye size={13} />}</button>
                      )}
                      {items.length < max && <button type="button" className="p-1 text-gray-500 hover:text-gray-900" title="Çoğalt" aria-label="Çoğalt" onClick={() => dup(i)}><Copy size={13} /></button>}
                      <button type="button" className="p-1 text-red-500 hover:text-red-700 disabled:opacity-30" title="Sil" aria-label="Sil" disabled={!!field.min && items.length <= field.min}
                        onClick={() => del(i)}><Trash2 size={13} /></button>
                    </div>
                    {isOpen && (
                      <div className="p-2 space-y-2">
                        {renderFields(field.item_fields || [], it || {}, (v) => set(i, v), `${path}.${i}`)}
                        {field.item_schedule && (
                          <div className="border-t pt-2">
                            <div className="text-xs font-medium text-gray-700 mb-1">Yayın zamanı (bu öğe)</div>
                            <div className="grid grid-cols-2 gap-2">
                              <DateTimeInput field={{ label: "Başlangıç" }} value={it?._schedule?.start || ""} onChange={(x) => set(i, { ...it, _schedule: { ...(it?._schedule || {}), start: x } })} />
                              <DateTimeInput field={{ label: "Bitiş" }} value={it?._schedule?.end || ""} onChange={(x) => set(i, { ...it, _schedule: { ...(it?._schedule || {}), end: x } })} />
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </SortableItem>
            );
          })}
        </SortableContext>
      </DndContext>
      {items.length < max && (
        <button type="button" className={`${smallBtn} w-full justify-center py-1.5`} onClick={add} data-testid={`repeater-add-${field.name}`}>
          <Plus size={13} /> {field.item_noun || "Öğe"} ekle
        </button>
      )}
      {field.min ? <div className="text-[10px] text-gray-500">En az {field.min}, en fazla {max}.</div> : null}
    </div>
  );
}

// ------------------------------------------------------------------ karusel / geri sayım / başlık satırı
const CAROUSEL_FIELDS = [
  { name: "per_view", type: "_per_view", label: "Kırılım başına görünen adet" },
  { name: "slides_to_scroll", type: "number", label: "Kaydırma adımı", min: 1, max: 12, width: "third" },
  { name: "rows", type: "number", label: "Satır", min: 1, max: 4, width: "third" },
  { name: "gutter", type: "number", label: "Boşluk", unit: "px", min: 0, max: 100, width: "third" },
  { name: "autoplay", type: "bool", label: "Otomatik oynat", width: "third" },
  { name: "interval", type: "number", label: "Aralık", unit: "ms", min: 500, max: 60000, step: 100, width: "third" },
  { name: "pause_on_hover", type: "bool", label: "Üzerindeyken dur", width: "third" },
  { name: "loop", type: "bool", label: "Döngü", width: "third" },
  { name: "rewind", type: "bool", label: "Başa sar", width: "third" },
  { name: "drag", type: "bool", label: "Sürükleme", width: "third" },
  { name: "transition", type: "select", label: "Geçiş", options: [{ value: "slide", label: "Kaydır" }, { value: "fade", label: "Belir" }], width: "half" },
  { name: "speed", type: "number", label: "Hız", unit: "ms", min: 0, max: 5000, step: 50, width: "half" },
  { name: "dots", type: "select", label: "Noktalar", options: [{ value: true, label: "Göster" }, { value: false, label: "Gizle" }, { value: "mobile", label: "Yalnız mobil" }], width: "half" },
  { name: "arrows", type: "select", label: "Oklar", options: [{ value: "none", label: "Yok" }, { value: "header", label: "Başlıkta" }, { value: "side", label: "İki yanda" }, { value: "outer", label: "Dışta" }], width: "half" },
  { name: "last_active_divider", type: "bool", label: "Son kartın ayırıcısını gizle" },
];

function PerViewInput({ value, onChange }) {
  const pv = isObj(value) ? value : { 0: 1 };
  const keys = Object.keys(pv).map(Number).sort((a, b) => a - b);
  return (
    <div className="space-y-1">
      <table className="text-xs w-full">
        <thead><tr className="text-gray-500"><th className="text-left font-normal">En az genişlik (px)</th><th className="text-left font-normal">Adet</th><th /></tr></thead>
        <tbody>
          {keys.map((k) => (
            <tr key={k}>
              <td className="pr-2"><input type="number" className={inputCls} value={k} min={0} onChange={(e) => {
                const n = { ...pv }; const val = n[String(k)]; delete n[String(k)]; n[String(Number(e.target.value) || 0)] = val; onChange(n);
              }} /></td>
              <td className="pr-2"><input type="number" className={inputCls} value={pv[String(k)]} min={1} max={12} onChange={(e) => onChange({ ...pv, [String(k)]: Number(e.target.value) || 1 })} /></td>
              <td><button type="button" className="text-red-500 p-1" aria-label="Kırılımı sil" onClick={() => { const n = { ...pv }; delete n[String(k)]; onChange(n); }}><Trash2 size={12} /></button></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button type="button" className={smallBtn} onClick={() => onChange({ ...pv, [String((keys[keys.length - 1] || 0) + 200)]: pv[String(keys[keys.length - 1])] || 1 })}><Plus size={12} /> Kırılım ekle</button>
    </div>
  );
}

export function CarouselInput({ field, value, onChange, renderFields, path }) {
  const hide = new Set(field.hide || []);
  const fields = CAROUSEL_FIELDS.filter((f) => !hide.has(f.name));
  const v = isObj(value) ? value : {};
  return (
    <div className="space-y-2">
      {fields.some((f) => f.name === "per_view") && (
        <div>
          <div className="text-xs font-medium text-gray-700 mb-1">Kırılım başına görünen adet</div>
          <PerViewInput value={v.per_view} onChange={(x) => onChange({ ...v, per_view: x })} />
        </div>
      )}
      {renderFields(fields.filter((f) => f.name !== "per_view"), v, onChange, path)}
    </div>
  );
}

const COUNTDOWN_FIELDS = [
  { name: "enabled", type: "bool", label: "Geri sayımı göster", width: "half" },
  { name: "end", type: "date_time", label: "Bitiş tarihi", help: "Boş bırakılırsa her gün 23:59'da biter (+ aşağıdaki gün sayısı).", width: "half" },
  { name: "rolling_days", type: "number", label: "Bitiş boşsa: bugün + gün", min: 0, max: 365, width: "half", show_if: { end: [""] } },
  { name: "heading", type: "text", label: "Üst yazı" },
  { name: "units", type: "_units", label: "Birimler" },
  { name: "labels", type: "group", label: "Birim etiketleri", fields: [
    { name: "days", type: "text", label: "Gün", width: "half" }, { name: "hours", type: "text", label: "Saat", width: "half" },
    { name: "minutes", type: "text", label: "Dakika", width: "half" }, { name: "seconds", type: "text", label: "Saniye", width: "half" }] },
  { name: "hide_zero_days", type: "bool", label: "Gün 0 ise gizle", width: "half" },
  { name: "pad", type: "bool", label: "İki haneli (05)", width: "half" },
  { name: "on_expire", type: "select", label: "Süre bitince", dropdown: true, options: [
    { value: "hide_block", label: "Bloğu gizle" }, { value: "hide_timer", label: "Sayacı gizle" },
    { value: "show_text", label: "Yazı göster" }, { value: "zero", label: "00:00 olarak kalsın" }] },
  { name: "expired_text", type: "text", label: "Bitiş yazısı", show_if: { on_expire: ["show_text"] } },
];

export function CountdownInput({ value, onChange, renderFields, path }) {
  const v = isObj(value) ? value : {};
  const units = Array.isArray(v.units) ? v.units : ["days", "hours", "minutes", "seconds"];
  const U = [["days", "Gün"], ["hours", "Saat"], ["minutes", "Dakika"], ["seconds", "Saniye"]];
  return (
    <div className="space-y-2">
      {renderFields(COUNTDOWN_FIELDS.slice(0, 4), v, onChange, path)}
      <div>
        <div className="text-xs font-medium text-gray-700 mb-1">Birimler</div>
        <div className="flex gap-3 text-xs">
          {U.map(([u, l]) => (
            <label key={u} className="flex items-center gap-1">
              <input type="checkbox" checked={units.includes(u)} onChange={(e) => onChange({ ...v, units: e.target.checked ? U.map((x) => x[0]).filter((x) => x === u || units.includes(x)) : units.filter((x) => x !== u) })} /> {l}
            </label>
          ))}
        </div>
      </div>
      {renderFields(COUNTDOWN_FIELDS.slice(5), v, onChange, path)}
    </div>
  );
}

const SECTION_HEADER_FIELDS = [
  { name: "title", type: "text", label: "Başlık" },
  { name: "tag", type: "select", label: "Başlık etiketi", options: [{ value: "h2", label: "H2" }, { value: "h3", label: "H3" }, { value: "sr-only", label: "Gizli (ekran okuyucu)" }], width: "half" },
  { name: "align", type: "select", label: "Hizalama", options: [{ value: "left", label: "Sol" }, { value: "center", label: "Orta" }], width: "half" },
  { name: "underline", type: "bool", label: "Ana renk alt çizgi" },
  { name: "right", type: "select", label: "Sağ taraf", dropdown: true, options: [{ value: "none", label: "Hiçbiri" }, { value: "arrows", label: "Oklar ‹ ›" }, { value: "pills", label: "Hap / sekme bağlantıları" }, { value: "link", label: "“Tümünü gör” bağlantısı" }, { value: "countdown", label: "Geri sayım" }] },
  { name: "pills", type: "repeater", label: "Haplar", item_noun: "Hap", item_label: "{{label}}", max: 12, show_if: { right: ["pills"] },
    item_fields: [{ name: "label", type: "text", label: "Yazı" }, { name: "as_tab", type: "bool", label: "Sekme gibi (ürünleri değiştirir)", width: "half" },
      { name: "active", type: "bool", label: "Başlangıçta seçili", width: "half" }, { name: "link", type: "link", label: "Bağlantı" },
      { name: "source", type: "product_source", label: "Ürün kaynağı (sekme ise)", show_if: { as_tab: [true] } }],
    item_default: { label: "Yeni hap", as_tab: false, active: false, link: { kind: "none", url: "" } } },
  { name: "link", type: "group", label: "Bağlantı", show_if: { right: ["link"] }, fields: [{ name: "label", type: "text", label: "Yazı" }, { name: "link", type: "link", label: "Hedef" }] },
];

export function SectionHeaderInput({ value, onChange, renderFields, path }) {
  return <div className="space-y-2">{renderFields(SECTION_HEADER_FIELDS, isObj(value) ? value : {}, onChange, path)}</div>;
}
