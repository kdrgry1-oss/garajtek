// C1 best_sellers — şablon best-sellers-products-cards-carousel: başlık + kategori hapları + 2 satırlı
// yatay kart karuseli (sayfa = sütun × satır). Grup C geliştirir.
import { useMemo, useState } from "react";
import SectionHeader from "../_shared/SectionHeader";
import BlockCarousel from "../_shared/BlockCarousel";
import ProductCard from "../_shared/ProductCard";
import useProductSource from "../_shared/useProductSource";
import useCategoryTree from "../../electro/useCategoryTree";

const COLS = { 2: "col-md-6", 3: "col-wd-3 col-md-4", 4: "col-md-3" };
function chunk(arr, n) { const out = []; for (let i = 0; i < arr.length; i += n) out.push(arr.slice(i, i + n)); return out; }

export default function Render({ settings }) {
  const st = settings;
  const tree = useCategoryTree();
  const roots = tree.menuRoots || tree.roots || [];
  const auto = st.pills_auto_categories || {};
  const header = useMemo(() => {
    const h = { ...(st.header || {}) };
    const pills = [...(h.pills || [])];
    if (auto.enabled) {
      roots.slice(0, Math.max(0, Number(auto.max) || 0)).forEach((c) => pills.push({
        _id: `auto-${c.id}`, label: c.name, as_tab: true, active: false, link: { kind: "category", url: `/${c.slug}` },
        source: { kind: "category", category_ids: [String(c.id)], limit: st.source?.limit || 12 },
      }));
    }
    h.pills = pills;
    return h;
  }, [st.header, auto.enabled, auto.max, roots, st.source]); // eslint-disable-line react-hooks/exhaustive-deps
  const initial = Math.max(0, (header.pills || []).findIndex((p) => p.active));
  const [pill, setPill] = useState(initial);
  const p = (header.pills || [])[pill];
  const src = pill > 0 && p?.source ? p.source : st.source;
  const list = useProductSource(st.pills_as_tabs ? src : st.source);
  const cols = Number(st.columns) || 3;
  const rows = Math.max(1, Number(st.rows_per_slide) || 2);
  const perPage = cols * rows;
  if (list && !list.length && pill === 0) return null;
  return (
    <div className="space-top-2" data-testid="bestsellers">
      <SectionHeader value={header} activePill={pill} onPill={st.pills_as_tabs ? setPill : undefined} className="border-color-1 flex-md-nowrap border-sm-bottom-0" />
      {!list ? (
        <div className="py-6"><div className="el-skel" style={{ height: 260 }} /></div>
      ) : list.length === 0 ? (
        <div className="py-6 text-center text-gray-90" data-pd-field="empty_text">{st.empty_text}</div>
      ) : (
        <BlockCarousel key={pill} value={{ ...st.carousel, per_view: { 0: 1 }, rows: 1 }} className="u-slick--gutters-2 overflow-hidden u-slick-overflow-visble pt-3 pb-6"
          dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-4">
          {chunk(list, perPage).map((group, gi) => (
            <ul className="row list-unstyled products-group no-gutters mb-0 overflow-visible" key={gi}>
              {group.map((prod, i) => (
                <ProductCard key={prod.id} product={prod} card={st.card === "grid" ? "grid" : "horizontal"} as="li" listName="bestsellers" index={gi * perPage + i}
                  className={`${COLS[cols] || COLS[3]} border-bottom border-md-bottom-0${i % cols === cols - 1 ? " remove-divider-xl" : ""}`} />
              ))}
            </ul>
          ))}
        </BlockCarousel>
      )}
    </div>
  );
}
