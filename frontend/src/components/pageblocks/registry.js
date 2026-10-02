// Blok kayıt defteri (SPEC §2.1). Her blok bir klasördür: <key>/schema.json + defaults.json + Render.jsx
// (+ thumb.png, Render.test.jsx). Klasörler `index.generated.js` üzerinden otomatik toplanır — bu dosya
// `python scripts/sync_block_schemas.py` ile ÜRETİLİR; grup ajanları registry.js'e/indexe DOKUNMAZ.
// Panel formu, vitrin renderer'ı ve backend doğrulaması AYNI schema.json'dan beslenir.
import { BLOCKS, GLOBALS } from "./index.generated";
import COMMON from "./_common.json";
import { assignIds, clone, deepMerge, fillItems, isObj, stripIds, uid } from "./_shared/schema";

export const SCHEMA_VERSION = 2;

export const CATEGORIES = [
  { key: "slider", label: "Slider" },
  { key: "banner", label: "Banner" },
  { key: "urun", label: "Ürün" },
  { key: "firsat", label: "Fırsat" },
  { key: "kategori", label: "Kategori" },
  { key: "marka", label: "Marka" },
  { key: "icerik", label: "İçerik" },
  { key: "kenar", label: "Kenar Çubuğu" },
  { key: "ust_bar", label: "Üst Bar" },
];

export const TOP_BAR_TYPES = new Set(["rotating_text", "countdown_bar"]);

// SPEC §6.1 — şablon v1.0 ana sayfa sırası
export const DEFAULT_HOME = [
  ["hero_slider", "v1", "Ana Slider"],
  ["ads_block", "v1", "Reklam Kutuları"],
  ["deals_tabs", "v1", "Özel Teklif ve Ürün Sekmeleri"],
  ["product_grid_212", "2_1_2", "Kategori Fırsatları (2-1-2)"],
  ["best_sellers", "", "Çok Satanlar"],
  ["full_banner", "image", "Tam Genişlik Banner"],
  ["product_slider", "", "Yeni Eklenenler"],
  ["brands_carousel", "", "Markalar"],
  ["product_columns", "", "Alt Ürün Sütunları"],
];

export const getBlock = (key) => BLOCKS[key] || null;
export const getSchema = (key) => (BLOCKS[key] ? BLOCKS[key].schema : GLOBALS[key] ? GLOBALS[key].schema : null);
export const blockKeys = () => Object.keys(BLOCKS);
export const globalKeys = () => Object.keys(GLOBALS);
export const getGlobal = (key) => GLOBALS[key] || null;

/** Galeri listesi: (stub'lar `includeStubs` yoksa gizlenir) */
export function listBlocks({ includeStubs = false, page = "home" } = {}) {
  return Object.entries(BLOCKS)
    .filter(([, b]) => includeStubs || b.schema.status !== "stub")
    .filter(([, b]) => { const ap = b.schema.allowed_pages || ["*"]; return ap.includes("*") || ap.includes(page); })
    .map(([key, b]) => ({ key, ...b }));
}

export function commonFields(schema) {
  const out = [];
  (schema?.common || []).forEach((g) => {
    const grp = COMMON[g];
    (grp?.fields || []).forEach((f) => out.push({ ...f, tab: f.tab || grp.tab }));
  });
  return out;
}

export const allFields = (schema) => [...(schema?.fields || []), ...commonFields(schema)];

function commonDefaults(schema) {
  const d = clone(COMMON.defaults || {});
  const keep = { section: "_section", visibility: "_visibility", reveal: "_reveal" };
  const out = {};
  Object.entries(keep).forEach(([g, k]) => { if ((schema.common || []).includes(g) && d[k]) out[k] = d[k]; });
  if (out._section) out._section.width = schema.layout === "sidebar" ? "container" : (schema.layout || "container");
  return out;
}

export function firstVariant(schema) {
  return (schema?.variants || [])[0]?.value ?? "";
}

/** defaults.json + varyant yaması + ortak grup varsayılanları (backend default_settings ile aynı). */
export function defaultSettings(key, variant) {
  const entry = BLOCKS[key] || GLOBALS[key];
  if (!entry) return {};
  const { schema } = entry;
  let out = deepMerge(commonDefaults(schema), clone(entry.defaults || {}));
  const vs = schema.variants || [];
  const v = variant != null && vs.some((x) => String(x.value) === String(variant)) ? variant : firstVariant(schema);
  const vv = vs.find((x) => String(x.value) === String(v));
  if (vv && vv.defaults_patch) out = deepMerge(out, vv.defaults_patch);
  if (schema.scope !== "global") { out._v = SCHEMA_VERSION; out._variant = v; }
  return out;
}

/** Eksik alanları (repeater öğeleri dahil) varsayılandan doldurur. */
export function withDefaults(key, settings) {
  const entry = BLOCKS[key] || GLOBALS[key];
  if (!entry) return settings || {};
  const st = isObj(settings) ? settings : {};
  return fillItems(allFields(entry.schema), deepMerge(defaultSettings(key, st._variant), st));
}

/** Varsayılanlarla DOLU yeni blok (galeriden ekleme). */
export function instantiate(key, variant, title) {
  const entry = BLOCKS[key];
  if (!entry) throw new Error(`Bilinmeyen blok: ${key}`);
  const settings = withDefaults(key, variant ? { _variant: variant } : {});
  assignIds(allFields(entry.schema), settings, true);
  return { id: uid(), type: key, title: title ?? entry.schema.title, is_active: true, settings };
}

export function defaultHome() {
  return DEFAULT_HOME.map(([k, v, t], i) => ({ ...instantiate(k, v || undefined, t), sort_order: i + 1 }));
}

/** Çoğalt: yeni blok id'si + repeater öğelerine yeni `_id`. */
export function duplicateBlock(block) {
  const entry = BLOCKS[block.type];
  const copy = clone(block);
  copy.id = uid();
  copy.title = block.title ? `${block.title} (Kopya)` : "Kopya";
  if (entry && isObj(copy.settings)) assignIds(allFields(entry.schema), copy.settings, true);
  return copy;
}

/** Şablon varsayılanından farklı mı? (`_id`'ler yok sayılır) */
export function isModified(block) {
  if (!block || !BLOCKS[block.type] || block.settings?._legacy) return false;
  const d = defaultSettings(block.type, block.settings?._variant);
  const cur = withDefaults(block.type, block.settings);
  const strip = (o) => { const x = stripIds(o); delete x._migration_errors; delete x._demo; return x; };
  return JSON.stringify(strip(cur)) !== JSON.stringify(strip(d));
}

/** Bloğu şablon varsayılanına sıfırlar (id, başlık, görünürlük korunur). */
export function resetBlock(block) {
  const s = withDefaults(block.type, { _variant: block.settings?._variant });
  assignIds(allFields(BLOCKS[block.type].schema), s, true);
  return { ...block, settings: s };
}

/** Varyant değiştir: değişmeyen alanlar korunur, varyant yaması uygulanır. */
export function applyVariant(block, variant) {
  const schema = BLOCKS[block.type]?.schema;
  const vv = (schema?.variants || []).find((x) => String(x.value) === String(variant));
  const s = deepMerge(block.settings || {}, vv?.defaults_patch || {});
  s._variant = variant;
  return { ...block, settings: withDefaults(block.type, s) };
}

export function defaultGlobal() {
  const out = {};
  Object.keys(GLOBALS).forEach((k) => { out[k] = defaultSettings(k); });
  return out;
}

export function withGlobalDefaults(global) {
  const out = {};
  Object.keys(GLOBALS).forEach((k) => { out[k] = withDefaults(k, (global || {})[k] || {}); });
  return out;
}

export { BLOCKS, GLOBALS, COMMON };
