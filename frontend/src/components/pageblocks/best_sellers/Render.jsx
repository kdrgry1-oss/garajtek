// C1 best_sellers — Ürün Kartları Karuseli (Çok Satanlar).
// Şablon: v1.0 best-sellers-products-cards-carousel.php (h2 + nav-inline "Top 20" + 3 kategori; columns-3, sayfa
// başına 2 satır yatay kart, Owl items:1 + noktalar) ve v2.0 index "Prodcut-cards-carousel" (space-top-2, hap başlık,
// u-slick--gutters-2 pt-3 pb-6, ul.row.products-group > li.col-wd-3.col-md-4.product-item__card, remove-divider-xl/wd).
// Sayfa (slayt) boyutu ekran genişliğine göre: mobil = mobile_per_slide, ≥768 = columns × rows, ≥1480 = columns_wide × rows.
// Haplar: “İlk 20” (ana kaynak) + kök kategorilerden otomatik N kategori; pills_as_tabs açıksa ürünleri değiştirir.
import { useMemo, useState } from "react";
import SectionHeader from "../_shared/SectionHeader";
import BlockCarousel from "../_shared/BlockCarousel";
import ProductCard from "../_shared/ProductCard";
import useProductSource from "../_shared/useProductSource";
import useCategoryTree from "../../electro/useCategoryTree";
import { EmptyNote, Skeleton, useViewportWidth } from "../product_slider/viewport";
import "../product_slider/style.css";
import "./style.css";

const MD = { 1: "col-md-12", 2: "col-md-6", 3: "col-md-4", 4: "col-md-3", 6: "col-md-2" };
const WD = { 1: "col-wd-12", 2: "col-wd-6", 3: "col-wd-4", 4: "col-wd-3", 5: "col-wd-2gdot4", 6: "col-wd-2" };

function chunk(arr, n) { const out = []; for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n)); return out; }

export function pageLayout(st, w) {
  const rows = Math.max(1, Math.min(3, Number(st.rows_per_slide) || 2));
  const cols = Math.max(1, Number(st.columns) || 3);
  const colsWd = Math.max(1, Number(st.columns_wide) || cols);
  if (w < 768) return { perPage: Math.max(1, Number(st.mobile_per_slide) || 3), cols: 1 };
  if (w >= 1480) return { perPage: colsWd * rows, cols: colsWd };
  return { perPage: cols * rows, cols };
}

/** Kart sınıfları — şablon: col-wd-3 col-md-4, mobilde son kart hariç alt çizgi, satır sonunda ayırıcı yok. */
export function itemClass(i, n, colsMd, colsWd, grid) {
  return [
    grid ? "col-6" : "", MD[colsMd] || MD[3], WD[colsWd] || WD[4],
    i < n - 1 ? "border-bottom border-md-bottom-0" : "",
    i % colsMd === colsMd - 1 ? "remove-divider-md-lg remove-divider-xl" : "",
    i % colsWd === colsWd - 1 ? "remove-divider-wd" : "",
  ].filter(Boolean).join(" ");
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const tree = useCategoryTree();
  const roots = tree.menuRoots || tree.roots || [];
  const auto = st.pills_auto_categories || {};
  const limit = st.source?.limit || 12;
  const header = useMemo(() => {
    const h = { ...(st.header || {}) };
    const pills = [...(h.pills || [])];
    if (h.right === "pills" && auto.enabled) {
      roots.slice(0, Math.max(0, Number(auto.max) || 0)).forEach((c) => pills.push({
        _id: `auto-${c.id}`, label: c.name, as_tab: true, active: false, _auto: true, link: { kind: "category", id: String(c.id), url: `/${c.slug}` },
        source: { ...(st.source || {}), kind: "category", category_ids: [String(c.id)], include_children: true, product_ids: [], limit },
      }));
    }
    h.pills = pills.filter((p) => p && p.label);
    return h;
  }, [st.header, auto.enabled, auto.max, roots, st.source, limit]); // eslint-disable-line react-hooks/exhaustive-deps
  const initial = Math.max(0, (header.pills || []).findIndex((p) => p.active));
  const [pill, setPill] = useState(initial);
  const p = (header.pills || [])[pill];
  const src = st.pills_as_tabs && p?.source && p.source.kind ? p.source : st.source;
  const list = useProductSource(src);
  const w = useViewportWidth();
  const { perPage, cols } = pageLayout(st, w);
  const colsMd = Math.max(1, Number(st.columns) || 3);
  const colsWd = Math.max(1, Number(st.columns_wide) || colsMd);
  const grid = st.card === "grid";
  // ana kaynak boşsa (ilk sekme) bölüm vitrinde hiç çizilmez
  if (list && !list.length && src === st.source) return <EmptyNote preview={ctx?.preview} text="Çok satanlar: seçilen kaynakta ürün yok (vitrinde bu bölüm gizlenir)." />;
  const onPill = st.pills_as_tabs ? setPill : undefined;
  return (
    <div className="space-top-2 pbs" data-testid="bestsellers">
      <SectionHeader value={header} activePill={pill} onPill={onPill} className="border-color-1 flex-md-nowrap border-sm-bottom-0" />
      {!list ? (
        <div className="pt-3 pb-6"><Skeleton height={grid ? 330 : 260} count={Math.min(cols, 4)} /></div>
      ) : list.length === 0 ? (
        <div className="py-6 text-center text-gray-90" data-pd-field="empty_text">{st.empty_text}</div>
      ) : (
        <BlockCarousel key={`${pill}-${perPage}`} value={{ ...st.carousel, per_view: { 0: 1 }, rows: 1 }} ariaLabel={header.title || undefined}
          className="u-slick--gutters-2 overflow-hidden u-slick-overflow-visble pt-3 pb-6"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-4">
          {chunk(list, perPage).map((group, gi) => (
            <ul className="row list-unstyled products-group no-gutters mb-0 overflow-visible" key={gi}>
              {group.map((prod, i) => {
                const cls = itemClass(i, group.length, colsMd, colsWd, grid);
                return <ProductCard key={prod.id} product={prod} card={grid ? "grid" : "horizontal"} as="li" listName="bestsellers" index={gi * perPage + i} className={cls} />;
              })}
            </ul>
          ))}
        </BlockCarousel>
      )}
    </div>
  );
}
