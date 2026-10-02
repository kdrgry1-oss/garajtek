// B2 product_grid_212 — şablon 2-1-2-product-grid: kategori sekmeli 2 + büyük ürün + 2. Grup B geliştirir (4_1_4).
import { useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard, { FeaturedBigCard } from "../_shared/ProductCard";
import SmartLink from "../_shared/SmartLink";
import useCategoryTree from "../../electro/useCategoryTree";

const COLS = { "23_52_23": ["col-md-3", "col-md-6"], "25_50_25": ["col-md-3", "col-md-6"] };
const catSource = (c, limit = 5) => ({ kind: "category", category_ids: [String(c.id)], include_children: true, limit, product_ids: [], tag: "", brand_ids: [], sort: "default", exclude_out_of_stock: false, exclude_ids: [], fill_with: "none" });

export default function Render({ settings }) {
  const st = settings;
  const tree = useCategoryTree();
  const roots = tree.menuRoots || tree.roots || [];
  const auto = st.nav_auto_categories || {};
  const tabs = useMemo(() => {
    const fixed = (st.nav_items || []).filter((t) => t && (t.label || t.source?.category_ids?.length)).map((t, i) => {
      const cid = t.source?.kind === "category" ? (t.source.category_ids || [])[0] : null;
      const node = cid ? tree.byId?.get(String(cid)) : null;
      return { key: t._id || `n${i}`, label: t.label || node?.name || "", source: t.source, link: t.link?.url ? t.link : (node ? { kind: "category", url: `/${node.slug}` } : null), field: `nav_items.${i}.label` };
    });
    const ex = new Set((auto.exclude || []).map(String));
    const autos = auto.enabled ? roots.filter((c) => !ex.has(String(c.id))).slice(0, Math.max(0, Number(auto.max) || 0))
      .map((c) => ({ key: `c${c.id}`, label: c.name, source: catSource(c), link: { kind: "category", url: `/${c.slug}` }, data: true })) : [];
    return [...fixed, ...autos];
  }, [st.nav_items, auto.enabled, auto.max, auto.exclude, roots, tree.byId]); // eslint-disable-line react-hooks/exhaustive-deps
  const [active, setActive] = useState(0);
  const cur = tabs[Math.min(active, Math.max(0, tabs.length - 1))];
  const list = useProductSource(cur ? cur.source : null);
  const manual = useProductSource(st.main_product_mode === "manual" && st.main_product ? { kind: "manual", product_ids: [st.main_product] } : null);
  if (!tabs.length) return null;
  const big = st.main_product_mode === "manual" ? (manual || [])[0] || (list || [])[0] : (list || [])[0];
  const rest = (list || []).filter((p) => !big || p.id !== big.id);
  const [side, mid] = COLS[st.column_widths] || COLS["23_52_23"];
  const cell = (p) => <ProductCard key={p.id} product={p} as="li" className="col-12 remove-divider" innerClassName="product-item__inner bg-white p-3" listName="products_212" />;
  return (
    <div className="products-group-4-1-4 el-212" data-testid="products-212">
      {st.title && <h2 className="sr-only" data-pd-field="title">{st.title}</h2>}
      <div className="position-relative text-center z-index-2 mb-3">
        <ul className="nav nav-classic nav-tab nav-tab-sm px-md-3 justify-content-start justify-content-lg-center flex-nowrap flex-lg-wrap overflow-auto overflow-lg-visble border-md-down-bottom-0 pb-1 pb-lg-0 mb-n1 mb-lg-0" role="tablist">
          {tabs.map((t, i) => (
            <li className="nav-item flex-shrink-0 flex-lg-shrink-1" key={t.key}>
              {st.nav_mode === "links" && t.link ? (
                <SmartLink link={t.link} className="nav-link"><div className="d-md-flex justify-content-md-center align-items-md-center" {...(t.field ? { "data-pd-field": t.field } : { "data-pd-data": "" })}>{t.label}</div></SmartLink>
              ) : (
                <a href="#urunler" role="tab" aria-selected={i === active} className={`nav-link${i === active ? " active" : ""}`} onClick={(e) => { e.preventDefault(); setActive(i); }}>
                  <div className="d-md-flex justify-content-md-center align-items-md-center" {...(t.field ? { "data-pd-field": t.field } : { "data-pd-data": "" })}>{t.label}</div>
                </a>
              )}
            </li>
          ))}
        </ul>
      </div>
      <div className="tab-content">
        <div className="tab-pane fade pt-2 show active" role="tabpanel">
          {!list ? (
            <div className="row no-gutters">{[0, 1, 2].map((i) => <div key={i} className="col-md-4 p-2"><div className="el-skel" style={{ height: 420 }} /></div>)}</div>
          ) : !list.length ? (
            <div className="text-center py-6 text-gray-90" data-pd-field="empty_text">{st.empty_text}</div>
          ) : (
            <div className="row no-gutters">
              <div className={side}><ul className="row list-unstyled products-group no-gutters mb-0 h-100 el-212__side">{rest.slice(0, 2).map(cell)}</ul></div>
              <div className={`${mid} products-group-1`}>
                <ul className="row list-unstyled products-group no-gutters bg-white h-100 mb-0">
                  {big && <FeaturedBigCard product={big} thumbnails={st.main_thumbnails !== false} listName="products_212" />}
                </ul>
              </div>
              <div className={side}><ul className="row list-unstyled products-group no-gutters mb-0 h-100 el-212__side">{rest.slice(2, 4).map(cell)}</ul></div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
