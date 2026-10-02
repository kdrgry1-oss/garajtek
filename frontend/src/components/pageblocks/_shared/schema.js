// Şema yardımcıları — backend/pageblocks/__init__.py ile AYNI anlam (deep_merge, with_defaults,
// assign_item_ids, apply_schedule). Panel formu, önizleme ve vitrin bu fonksiyonları paylaşır.

export const DEVICES = ["desktop", "tablet", "mobile"];
export const DEFAULT_TZ = "Europe/Istanbul";

export const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
export const clone = (v) => (v === undefined ? v : JSON.parse(JSON.stringify(v)));

/** `over` kazanır; nesneler özyinelemeli, diziler/skalerler değiştirilir. */
export function deepMerge(base, over) {
  // tamamen sayısal anahtarlı nesne (karusel per_view kırılım tablosu) bütün olarak değiştirilir (backend ile aynı)
  if (isObj(over) && Object.keys(over).length && Object.keys(over).every((k) => /^\d+$/.test(k))) return clone(over);
  if (isObj(base) && isObj(over)) {
    const out = { ...clone(base) };
    Object.keys(over).forEach((k) => { out[k] = k in out ? deepMerge(out[k], over[k]) : clone(over[k]); });
    return out;
  }
  return clone(over);
}

export function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function uid() {
  try { if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID(); } catch { /* yoksay */ }
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

export function fieldDefault(f) {
  if (f && "default" in f) return clone(f.default);
  if (f && f.type === "group") {
    const o = {};
    (f.fields || []).forEach((x) => { const d = fieldDefault(x); if (d !== undefined) o[x.name] = d; });
    return o;
  }
  return undefined;
}

export function itemDefault(field) {
  const base = {};
  (field.item_fields || []).forEach((f) => { const d = fieldDefault(f); if (d !== undefined && d !== null) base[f.name] = d; });
  return deepMerge(base, field.item_default || {});
}

/** Repeater öğelerini item_default ile doldurur (özyinelemeli). */
export function fillItems(fields, value) {
  if (!isObj(value)) return value;
  (fields || []).forEach((f) => {
    const v = value[f.name];
    if (f.type === "repeater" && Array.isArray(v)) {
      const d = itemDefault(f);
      value[f.name] = v.map((it) => (isObj(it) ? fillItems(f.item_fields, deepMerge(d, it)) : it));
    } else if (f.type === "group" && isObj(v)) {
      fillItems(f.fields, v);
    }
  });
  return value;
}

/** Repeater öğelerine kalıcı `_id` (yoksa). `fresh` → hepsini yeniler (çoğaltma). */
export function assignIds(fields, value, fresh = false) {
  if (!isObj(value)) return value;
  (fields || []).forEach((f) => {
    const v = value[f.name];
    if (f.type === "repeater" && Array.isArray(v)) {
      v.forEach((it) => { if (isObj(it)) { if (fresh || !it._id) it._id = uid(); assignIds(f.item_fields, it, fresh); } });
    } else if (f.type === "group" && isObj(v)) {
      assignIds(f.fields, v, fresh);
    } else if (f.type === "section_header" && isObj(v) && Array.isArray(v.pills)) {
      v.pills.forEach((p) => { if (isObj(p) && (fresh || !p._id)) p._id = uid(); });
    }
  });
  return value;
}

/** Karşılaştırma için `_id`'leri atar. */
export function stripIds(v) {
  if (Array.isArray(v)) return v.map(stripIds);
  if (isObj(v)) {
    const o = {};
    Object.keys(v).forEach((k) => { if (k !== "_id") o[k] = stripIds(v[k]); });
    return o;
  }
  return v;
}

// --------------------------------------------------------------- yol yardımcıları
export function splitPath(path) {
  if (Array.isArray(path)) return path;
  return String(path || "").split(".").filter((x) => x !== "").map((x) => (/^\d+$/.test(x) ? Number(x) : x));
}

export function getPath(obj, path) {
  return splitPath(path).reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

export function setPath(obj, path, value) {
  const parts = splitPath(path);
  if (!parts.length) return value;
  const [k, ...rest] = parts;
  const base = Array.isArray(obj) ? [...obj] : { ...(obj || {}) };
  base[k] = rest.length ? setPath(base[k] ?? (typeof rest[0] === "number" ? [] : {}), rest, value) : value;
  return base;
}

// --------------------------------------------------------------- show_if
/** show_if: {alan: [değerler]} (VE); "_variant" kök varyantı, "$parent.x" bir üst nesne, "$root.x" kök. */
export function showIf(field, scope, ctx = {}) {
  const cond = field && field.show_if;
  if (!cond) return true;
  return Object.keys(cond).every((k) => {
    let v;
    if (k === "_variant") v = ctx.root ? ctx.root._variant : undefined;
    else if (k.startsWith("$parent.")) v = getPath(ctx.parent, k.slice(8));
    else if (k.startsWith("$root.")) v = getPath(ctx.root, k.slice(6));
    else v = scope ? scope[k] : undefined;
    const allowed = Array.isArray(cond[k]) ? cond[k] : [cond[k]];
    return allowed.some((a) => String(a) === String(v ?? ""));
  });
}

// --------------------------------------------------------------- responsive
export const isResponsive = (v) => isObj(v) && DEVICES.some((d) => d in v) && !("top" in v && "bottom" in v && !("desktop" in v));

export function resolveResponsive(v, device = "desktop") {
  if (!isResponsive(v)) return v;
  if (device in v && v[device] !== undefined && v[device] !== null && v[device] !== "") return v[device];
  return v.desktop ?? v.tablet ?? v.mobile;
}

// --------------------------------------------------------------- zamanlama
function parseDt(s) {
  const t = String(s || "").trim();
  if (!t) return null;
  // ofsetsiz "YYYY-MM-DDTHH:MM" → İstanbul (UTC+3, yaz saati yok)
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(t)) return new Date(`${t.length === 16 ? `${t}:00` : t}+03:00`);
  const d = new Date(t);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function scheduleActive(sc, now = new Date()) {
  if (!isObj(sc)) return true;
  const s = parseDt(sc.start);
  let e = parseDt(sc.end);
  if (s && now < s) return false;
  if (e) {
    if (String(sc.end).trim().length <= 16) e = new Date(e.getTime() + 59999);
    if (now > e) return false;
  }
  return true;
}

export function filterItems(fields, value, now = new Date()) {
  if (!isObj(value)) return value;
  const out = { ...value };
  (fields || []).forEach((f) => {
    const v = out[f.name];
    if (f.type === "repeater" && Array.isArray(v)) {
      out[f.name] = v.filter((it) => isObj(it) && !it._hidden && scheduleActive(it._schedule, now)).map((it) => filterItems(f.item_fields, it, now));
    } else if (f.type === "group" && isObj(v)) {
      out[f.name] = filterItems(f.fields, v, now);
    }
  });
  return out;
}

/** Zengin metnin düz metni (boş mu kontrolü). */
export const plainText = (html) => String(html || "").replace(/<br\s*\/?>/gi, " ").replace(/<[^>]+>/g, "").replace(/&nbsp;/g, " ").trim();
