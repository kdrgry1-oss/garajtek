// SpecFacets — kategori filtre panelinde teknik özellik süzgeçleri (Kapasite, Güç Kaynağı,
// Voltaj, Faz, Basınç, Tank Hacmi, Lokma Ölçüsü…). Değerler ve adetler backend'den:
//   GET /api/products/meta/spec-facets?category=<slug>
// Seçimler URL'de ?spec_<anahtar>=a,b olarak tutulur; /api/products aynı parametreleri süzer.
import { useEffect, useState } from "react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const _cache = new Map();

/** URLSearchParams içindeki spec_* parametrelerini sorgu dizgesine çevirir ("&spec_x=a,b"). */
export function specQueryString(searchParams) {
  let q = "";
  for (const [k, v] of searchParams.entries()) {
    if (k.startsWith("spec_") && v) q += `&${encodeURIComponent(k)}=${encodeURIComponent(v)}`;
  }
  return q;
}

/** Etkin spec_* süzgeç sayısı (Temizle rozeti için). */
export function specFilterCount(searchParams) {
  let n = 0;
  for (const [k, v] of searchParams.entries()) if (k.startsWith("spec_") && v) n += v.split(",").filter(Boolean).length;
  return n;
}

function SpecGroup({ facet, selected, onToggle }) {
  const [more, setMore] = useState(false);
  const items = facet.values || [];
  const shown = more ? items : items.slice(0, 6);
  return (
    <div className="border-bottom pb-4 mb-4" data-testid={`spec-facet-${facet.key}`}>
      <h4 className="font-size-14 mb-3 font-weight-bold">{facet.label}</h4>
      {shown.map((it) => {
        const val = String(it.value);
        const id = `spec-${facet.key}-${val}`.replace(/[^\w-]/g, "_");
        return (
          <div key={val} className="form-group d-flex align-items-center justify-content-between mb-2 pb-1">
            <div className="custom-control custom-checkbox">
              <input type="checkbox" className="custom-control-input" id={id} checked={selected.includes(val)} onChange={() => onToggle(val)} />
              <label className="custom-control-label" htmlFor={id}>
                {it.label}<span className="text-gray-25 font-size-12 font-weight-normal"> ({it.count})</span>
              </label>
            </div>
          </div>
        );
      })}
      {items.length > 6 && (
        <button type="button" className="link link-collapse small font-size-13 text-gray-27 d-inline-flex mt-2 btn btn-link p-0" onClick={() => setMore((v) => !v)} aria-expanded={more}>
          <span className="link__icon text-gray-27 bg-white"><span className="link__icon-inner">{more ? "−" : "+"}</span></span>
          <span className="ml-1">{more ? "Daha az göster" : "Daha fazla göster"}</span>
        </button>
      )}
    </div>
  );
}

export default function SpecFacets({ slug, searchParams, onToggle }) {
  const key = slug || "all";
  const [facets, setFacets] = useState(() => _cache.get(key) || []);
  useEffect(() => {
    let alive = true;
    if (_cache.has(key)) { setFacets(_cache.get(key)); return undefined; }
    const catQ = slug && slug !== "all" ? `?category=${encodeURIComponent(slug)}` : "";
    axios.get(`${API}/products/meta/spec-facets${catQ}`)
      .then((r) => { const f = r.data?.facets || []; _cache.set(key, f); if (alive) setFacets(f); })
      .catch(() => { if (alive) setFacets([]); });
    return () => { alive = false; };
  }, [key, slug]);
  if (!facets.length) return null;
  return (
    <div data-testid="spec-facets">
      {facets.map((f) => (
        <SpecGroup key={f.key} facet={f}
          selected={(searchParams.get(`spec_${f.key}`) || "").split(",").filter(Boolean)}
          onToggle={(v) => onToggle(`spec_${f.key}`, v)} />
      ))}
    </div>
  );
}
