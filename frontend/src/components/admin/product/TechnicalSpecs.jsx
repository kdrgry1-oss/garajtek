/**
 * TechnicalSpecs — Admin ürün formu "Teknik Özellikler" sekmesi (ekipman ürünleri).
 *
 * Alan tanımları ve kategori şablonları backend'den gelir:
 *   GET /api/products/meta/spec-templates  (varsayılan: backend/data/spec_templates.json)
 * Değerler formData.specs (yapılandırılmış), formData.extra_specs (serbest anahtar/değer)
 * alanlarına yazılır; backend kaydederken tip/birim doğrular (product_specs.py).
 *
 * Paket boyutları / brüt ağırlık / desi YENİ alan değildir: kargo hesabının kullandığı mevcut
 * width / depth / height / product_weight / cargo_weight alanları düzenlenir.
 */
import { useEffect, useMemo, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

let _cfgCache = null;
let _cfgPromise = null;
export function loadSpecConfig() {
  if (_cfgCache) return Promise.resolve(_cfgCache);
  if (!_cfgPromise) {
    _cfgPromise = axios.get(`${API}/products/meta/spec-templates`)
      .then((r) => { _cfgCache = r.data; return _cfgCache; })
      .catch((e) => { _cfgPromise = null; throw e; });
  }
  return _cfgPromise;
}

const inputCls = "w-full border-gray-200 border px-3 py-2 rounded-lg focus:border-black outline-none transition-all text-sm";
const labelCls = "block text-xs font-bold text-gray-500 uppercase mb-1";

/** Seçili kategorilerin (ve atalarının) slug'ları. */
function categorySlugs(selected, categories) {
  const byId = new Map((categories || []).map((c) => [String(c.id), c]));
  const out = new Set();
  for (const id of selected || []) {
    let cur = byId.get(String(id));
    let guard = 0;
    while (cur && guard++ < 20) {
      if (cur.slug) out.add(cur.slug);
      cur = cur.parent_id ? byId.get(String(cur.parent_id)) : null;
    }
  }
  return [...out];
}

function SpecInput({ field, value, onChange }) {
  const t = field.type;
  const id = `spec-${field.key}`;
  const unit = field.unit ? <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 pointer-events-none">{field.unit}</span> : null;
  if (t === "number" || t === "int") {
    return (
      <div className="relative">
        <input id={id} data-testid={id} type="number" inputMode="decimal" step={t === "int" ? 1 : "any"}
          min={field.min ?? undefined} max={field.max ?? undefined}
          value={value ?? ""} onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value)}
          className={`${inputCls} ${field.unit ? "pr-14" : ""}`} />
        {unit}
      </div>
    );
  }
  if (t === "select") {
    const opts = field.options || [];
    const custom = value && !opts.includes(value);
    return (
      <div className="space-y-1">
        <select id={id} data-testid={id} value={custom ? "__custom" : (value || "")}
          onChange={(e) => onChange(e.target.value === "__custom" ? (value || " ") : (e.target.value || undefined))}
          className={`${inputCls} bg-white`}>
          <option value="">— Seçiniz —</option>
          {opts.map((o) => <option key={o} value={o}>{o}</option>)}
          {field.free && <option value="__custom">Diğer (elle yaz)…</option>}
        </select>
        {custom && (
          <input type="text" value={String(value).trimStart()} onChange={(e) => onChange(e.target.value || undefined)}
            placeholder="Değer yazın" className={inputCls} data-testid={`${id}-custom`} />
        )}
      </div>
    );
  }
  if (t === "multiselect") {
    const cur = Array.isArray(value) ? value : [];
    const opts = [...new Set([...(field.options || []), ...cur])];
    const toggle = (o) => {
      const next = cur.includes(o) ? cur.filter((x) => x !== o) : [...cur, o];
      onChange(next.length ? next : undefined);
    };
    return (
      <div className="flex flex-wrap gap-1.5" data-testid={id}>
        {opts.map((o) => (
          <button type="button" key={o} onClick={() => toggle(o)}
            className={`px-2.5 py-1 rounded-md border text-xs ${cur.includes(o) ? "bg-black text-white border-black" : "bg-white text-gray-700 border-gray-200 hover:border-gray-400"}`}>
            {o}
          </button>
        ))}
        {field.free && (
          <input type="text" placeholder="+ ekle" className="border border-dashed border-gray-300 rounded-md px-2 py-1 text-xs w-24"
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                const v = e.currentTarget.value.trim();
                if (v && !cur.includes(v)) onChange([...cur, v]);
                e.currentTarget.value = "";
              }
            }} />
        )}
      </div>
    );
  }
  if (t === "bool") {
    return (
      <select id={id} data-testid={id} value={value === true ? "1" : value === false ? "0" : ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : e.target.value === "1")}
        className={`${inputCls} bg-white`}>
        <option value="">— Belirtilmedi —</option>
        <option value="1">Evet</option>
        <option value="0">Hayır</option>
      </select>
    );
  }
  if (t === "dimensions") {
    const v = value || {};
    const set = (k, x) => {
      const next = { ...v, [k]: x === "" ? undefined : x };
      Object.keys(next).forEach((kk) => next[kk] === undefined && delete next[kk]);
      onChange(Object.keys(next).length ? next : undefined);
    };
    return (
      <div className="grid grid-cols-3 gap-2" data-testid={id}>
        {[["w", "En"], ["d", "Boy"], ["h", "Yükseklik"]].map(([k, l]) => (
          <div key={k} className="relative">
            <input type="number" min="0" step="any" placeholder={l} value={v[k] ?? ""} onChange={(e) => set(k, e.target.value)}
              className={`${inputCls} pr-9`} aria-label={`${field.label} ${l}`} />
            <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-gray-400">{field.unit || "cm"}</span>
          </div>
        ))}
      </div>
    );
  }
  if (t === "textarea") {
    return <textarea id={id} data-testid={id} rows={3} value={value || ""} onChange={(e) => onChange(e.target.value || undefined)} className={inputCls} />;
  }
  return (
    <div className="relative">
      <input id={id} data-testid={id} type="text" value={value || ""} placeholder={field.placeholder || ""}
        onChange={(e) => onChange(e.target.value || undefined)} className={`${inputCls} ${field.unit ? "pr-12" : ""}`} />
      {unit}
    </div>
  );
}

/** Varyant seçenek adları (ör. "Kapasite", "Voltaj", "Model") — Varyantlar sekmesinde kullanılır. */
export function VariantLabelsField({ formData, setFormData }) {
  const vl = formData.variant_labels || {};
  const set = (k, v) => setFormData((prev) => ({ ...prev, variant_labels: { ...(prev.variant_labels || {}), [k]: v } }));
  return (
    <div className="bg-white p-4 rounded-xl border shadow-sm" data-testid="variant-labels">
      <div className="text-xs font-bold text-gray-500 uppercase mb-2">Varyant seçenek adları</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label className={labelCls}>1. seçenek adı</label>
          <input list="variant-label-suggestions" value={vl.size || ""} onChange={(e) => set("size", e.target.value)}
            placeholder="Seçenek (ör. Kapasite, Model, Voltaj)" className={inputCls} data-testid="variant-label-size" />
        </div>
        <div>
          <label className={labelCls}>2. seçenek adı</label>
          <input list="variant-label-suggestions" value={vl.color || ""} onChange={(e) => set("color", e.target.value)}
            placeholder="Renk / Tip (opsiyonel)" className={inputCls} data-testid="variant-label-color" />
        </div>
      </div>
      <datalist id="variant-label-suggestions">
        {["Seçenek", "Model", "Kapasite", "Voltaj", "Tank Hacmi", "Ölçü", "Uzunluk", "Parça Sayısı", "Renk", "Tip"].map((x) => <option key={x} value={x} />)}
      </datalist>
      <p className="text-[10px] text-gray-400 mt-1">Vitrinde seçim kutusunun başlığı olarak gösterilir. Boş bırakılırsa "Seçenek" yazar.</p>
    </div>
  );
}

export default function TechnicalSpecs({ formData, setFormData, categories }) {
  const [cfg, setCfg] = useState(_cfgCache);
  const [err, setErr] = useState("");
  const [showAll, setShowAll] = useState(false);
  useEffect(() => {
    let alive = true;
    loadSpecConfig().then((c) => { if (alive) setCfg(c); }).catch(() => { if (alive) setErr("Teknik özellik tanımları yüklenemedi"); });
    return () => { alive = false; };
  }, []);

  const specs = formData.specs || {};
  const slugs = useMemo(() => categorySlugs(formData.categories, categories), [formData.categories, categories]);
  const template = useMemo(() => {
    if (!cfg) return null;
    return (cfg.templates || []).find((t) => (t.category_slugs || []).some((s) => slugs.includes(s))) || null;
  }, [cfg, slugs]);

  if (err) return <div className="p-4 text-sm text-red-600">{err}</div>;
  if (!cfg) return <div className="p-4 text-sm text-gray-500">Yükleniyor…</div>;

  const visible = new Set([...(cfg.common_fields || []), ...((template && template.fields) || [])]);
  // Değeri dolu alanlar şablon dışında kalsa da gösterilir (veri gizlenmesin).
  Object.keys(specs).forEach((k) => visible.add(k));
  const isVisible = (f) => showAll || !template || visible.has(f.key);

  const setSpec = (k, v) => setFormData((prev) => {
    const next = { ...(prev.specs || {}) };
    if (v === undefined || v === null || v === "") delete next[k]; else next[k] = v;
    return { ...prev, specs: next };
  });
  const setTop = (k, v) => setFormData((prev) => ({ ...prev, [k]: v }));
  const extra = Array.isArray(formData.extra_specs) ? formData.extra_specs : [];
  const setExtra = (rows) => setFormData((prev) => ({ ...prev, extra_specs: rows }));

  const w = Number(formData.width) || 0, d = Number(formData.depth) || 0, h = Number(formData.height) || 0;
  const autoDesi = w && d && h ? Math.round((w * d * h / 3000) * 100) / 100 : 0;

  return (
    <div className="space-y-6" data-testid="technical-specs">
      <div className="flex flex-wrap items-center justify-between gap-3 bg-gray-50 border rounded-xl px-4 py-3">
        <div className="text-sm text-gray-700">
          Şablon: <b data-testid="spec-template-name">{template ? template.label : "Genel (kategori seçilmedi / şablon yok)"}</b>
          <span className="text-xs text-gray-500 ml-2">Görünen alanlar ürünün kategorisine göre belirlenir. Tüm alanlar isteğe bağlıdır.</span>
        </div>
        {template && (
          <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer">
            <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} data-testid="spec-show-all" />
            Tüm alanları göster
          </label>
        )}
      </div>

      {(cfg.groups || []).map((g) => {
        const fields = (cfg.fields || []).filter((f) => f.group === g.key && isVisible(f));
        const isGeneral = g.key === "genel";
        const isSize = g.key === "boyut";
        if (!fields.length && !isGeneral && !isSize) return null;
        return (
          <section key={g.key} className="bg-white p-6 rounded-xl border shadow-sm" data-testid={`spec-group-${g.key}`}>
            <h3 className="font-semibold text-gray-900 border-b pb-2 mb-4">{g.label}</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {isGeneral && (
                <>
                  <div>
                    <label className={labelCls}>Marka</label>
                    <input value={formData.brand || ""} onChange={(e) => setTop("brand", e.target.value)} className={inputCls} data-testid="spec-brand" />
                  </div>
                  <div>
                    <label className={labelCls}>Barkod / GTIN</label>
                    <input value={formData.barcode || ""} onChange={(e) => setTop("barcode", e.target.value.replace(/\s+/g, ""))}
                      placeholder="EAN-13 / GTIN" className={`${inputCls} font-mono`} data-testid="spec-barcode" />
                  </div>
                  <div>
                    <label className={labelCls}>Renk (opsiyonel)</label>
                    <input value={formData.color || ""} onChange={(e) => setTop("color", e.target.value)} placeholder="ör. Kırmızı / Gri" className={inputCls} data-testid="spec-color" />
                  </div>
                </>
              )}
              {fields.map((f) => (
                <div key={f.key} className={f.type === "textarea" || f.type === "multiselect" ? "md:col-span-2 lg:col-span-3" : ""}>
                  <label className={labelCls} htmlFor={`spec-${f.key}`}>{f.label}{f.unit && f.type !== "dimensions" ? ` (${f.unit})` : ""}</label>
                  <SpecInput field={f} value={specs[f.key]} onChange={(v) => setSpec(f.key, v)} />
                </div>
              ))}
            </div>
            {isSize && (
              <div className="mt-5 pt-4 border-t">
                <div className="text-xs font-bold text-gray-500 uppercase mb-3">Paket / Kargo (kargo desi hesabında kullanılır)</div>
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                  {[["width", "Paket En", "cm"], ["depth", "Paket Boy", "cm"], ["height", "Paket Yükseklik", "cm"], ["product_weight", "Brüt Ağırlık", "kg"], ["cargo_weight", "Desi (elle)", "desi"]].map(([k, l, u]) => (
                    <div key={k}>
                      <label className="block text-[10px] font-bold text-gray-500 uppercase mb-1">{l}</label>
                      <div className="relative">
                        <input type="number" min="0" step="any" value={formData[k] || ""} onChange={(e) => setTop(k, e.target.value === "" ? 0 : e.target.value)}
                          className={`${inputCls} pr-11`} data-testid={`spec-pkg-${k}`} />
                        <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-gray-400">{u}</span>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="text-[11px] text-gray-500 mt-2" data-testid="spec-desi-hint">
                  {autoDesi ? <>Hesaplanan desi: <b>{autoDesi}</b> (En × Boy × Yükseklik / 3000). Paket ölçüleri girildiğinde elle desi yerine bu kullanılır.</>
                    : "Paket ölçüleri boşsa kargo, elle girilen desiyi kullanır."}
                </p>
              </div>
            )}
          </section>
        );
      })}

      <section className="bg-white p-6 rounded-xl border shadow-sm" data-testid="extra-specs">
        <div className="flex items-center justify-between border-b pb-2 mb-4">
          <h3 className="font-semibold text-gray-900">Ek Teknik Özellikler</h3>
          <button type="button" onClick={() => setExtra([...extra, { name: "", value: "" }])}
            className="text-xs px-3 py-1.5 bg-black text-white rounded-lg" data-testid="extra-spec-add">+ Satır ekle</button>
        </div>
        {extra.length === 0 && <p className="text-xs text-gray-500">Şablonda olmayan özellikler için serbest satır ekleyin (ör. "Piston Çapı" → "90 mm").</p>}
        <div className="space-y-2">
          {extra.map((r, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_auto] gap-2">
              <input value={r.name} placeholder="Özellik adı" onChange={(e) => setExtra(extra.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))} className={inputCls} />
              <input value={r.value} placeholder="Değer" onChange={(e) => setExtra(extra.map((x, j) => (j === i ? { ...x, value: e.target.value } : x)))} className={inputCls} />
              <button type="button" aria-label="Satırı sil" onClick={() => setExtra(extra.filter((_, j) => j !== i))} className="px-3 text-red-600 hover:bg-red-50 rounded-lg">×</button>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
