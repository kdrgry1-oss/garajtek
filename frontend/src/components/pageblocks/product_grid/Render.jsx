// B6 product_grid — Ürün Izgarası (v2.0 home-v7 "Recommendation For You", home-v10 "Hot Products Today",
// home-v9 son bakılanlar = yalnız görsel kart). Başlık + "Tümünü gör" bağlantısı (veya hap sekmeler), cihaz başına
// sütun sayısı, kart tipi, isteğe bağlı sayfalama ya da "Daha Fazla Göster" düğmesi.
import { useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard from "../_shared/ProductCard";
import { colCounts, colsStyle, dividerClasses } from "../deals_tabs/gridUtil";
import GridHeader, { initialPill, pillSource } from "./GridHeader";
import { isPreviewActive } from "../../../lib/pagePreview";

/** Son bakılanlar ziyaretçiye özeldir; panel önizlemesinde geçmiş yoksa düzenlenen görünüm boş kalmasın diye
 *  en yeni ürünler örnek olarak gösterilir (vitrinde etkisi yok). */
function previewSample(src) {
  if (!src || src.kind !== "recently_viewed" || !isPreviewActive()) return src;
  let ids = [];
  try { ids = JSON.parse(localStorage.getItem("recently_viewed") || "[]"); } catch { ids = []; }
  return Array.isArray(ids) && ids.length ? src : { ...src, kind: "newest" };
}

export default function Render({ settings }) {
  const st = settings;
  const [pill, setPill] = useState(null);
  const active = pill ?? initialPill(st.header);
  const src = useMemo(() => previewSample(pillSource(st.header, active, st.source)), [st.header, active, st.source]);
  const list = useProductSource(src);
  const base = colCounts(st.columns, { desktop: 6, tablet: 4, mobile: 2 });
  // şablon (home-v7 col-xl-2gdot4-only col-wd-2): 6+ sütunda 1200–1479 px arası bir sütun eksik, yarım satır gizli
  const cols = base.desktop >= 6 ? { ...base, wide: base.desktop, desktop: base.desktop - 1 } : base;
  const more = st.show_more_button || {};
  const perPage = Math.max(1, Number(st.page_size) || 12);
  const [page, setPage] = useState(0);
  const [shown, setShown] = useState(null);
  if (list && !list.length) {
    return st.empty_text ? (
      <div data-testid="product-grid"><GridHeader value={st.header} />
        <div className="text-center py-6 text-gray-90" data-pd-field="empty_text">{st.empty_text}</div></div>
    ) : null;
  }
  const all = list || [];
  const pages = st.pagination ? Math.ceil(all.length / perPage) : 1;
  const cur = Math.min(page, Math.max(0, pages - 1));
  let items = st.pagination ? all.slice(cur * perPage, cur * perPage + perPage) : all;
  const initial = Math.max(1, Number(more.initial) || cols.desktop * 2);
  const visible = shown ?? initial;
  if (!st.pagination && more.enabled) items = items.slice(0, visible);
  const card = st.card === "image_only" || st.card === "horizontal" ? st.card : "grid";
  const gridCols = cols.wide ? { ...cols, xlMax: Math.floor(items.length / cols.desktop) * cols.desktop || items.length } : cols;
  const onPill = (i) => { setPill(i); setPage(0); setShown(null); };
  return (
    <div className="pdb-grid" data-testid="product-grid">
      <GridHeader value={st.header} active={active} onPill={onPill} />
      {!list ? (
        <ul className="pdb-cols list-unstyled mb-0" style={colsStyle(cols)}>{Array.from({ length: cols.desktop }).map((_, i) => <li key={i} className="p-2"><div className="pdb-skel" style={{ height: 280 }} /></li>)}</ul>
      ) : (
        <ul className={`pdb-cols list-unstyled products-group no-gutters mb-0${card === "image_only" ? " pdb-grid--images" : ""}`} style={colsStyle(cols)} key={`${active}-${cur}`}>
          {items.map((p, i) => (
            <ProductCard key={p.id} product={p} card={card} as="li" listName="product_grid" index={i}
              className={`${dividerClasses(i, gridCols)}${card === "image_only" ? " p-2" : ""}`} />
          ))}
        </ul>
      )}
      {st.pagination && pages > 1 && (
        <nav className="d-flex justify-content-center mt-4" aria-label="Sayfalar">
          <ul className="pagination mb-0 pagination-shop justify-content-center">
            {Array.from({ length: pages }).map((_, i) => (
              <li className="page-item" key={i}>
                <a href={`#sayfa-${i + 1}`} className={`page-link${i === cur ? " current" : ""}`} aria-current={i === cur ? "page" : undefined}
                  onClick={(e) => { e.preventDefault(); setPage(i); }}>{i + 1}</a>
              </li>
            ))}
          </ul>
        </nav>
      )}
      {!st.pagination && more.enabled && more.text && all.length > visible && (
        <div className="text-center mt-4">
          <button type="button" className="btn btn-primary-dark-w px-5 rounded-pill transition-3d-hover" onClick={() => setShown(visible + (Number(more.step) || initial))} data-pd-field="show_more_button.text">{more.text}</button>
        </div>
      )}
    </div>
  );
}
