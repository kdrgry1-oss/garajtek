// B2 product_grid_212 — Kategori sekmeli büyük ürün ızgarası (tam genişlik #f9f9f9 bant, 58 px iç boşluk).
//   2_1_2 (vars.) : şablon v1.0 2-1-2-product-grid.php — nav-inline kategori sekmeleri, sütunlar
//                   %23.685 / %52.63 / %23.685 (2 + 1 büyük + 2), büyük ürün 600×600.
//   4_1_4         : v2.0 index Products-4-1-4 — 4 + 1 büyük (küçük resim galerili) + 4.
// Gezinme "tabs" (ürün kümesini değiştirir) veya "links" (kategori sayfasına gider; ilk sekmenin ürünleri gösterilir).
import { useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard from "../_shared/ProductCard";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import useCategoryTree from "../../electro/useCategoryTree";
import MainProduct from "./MainProduct";

const SRC_BASE = { product_ids: [], tag: "", brand_ids: [], sort: "default", exclude_out_of_stock: false, exclude_ids: [], fill_with: "none" };
const catSource = (c, limit) => ({ ...SRC_BASE, kind: "category", category_ids: [String(c.id)], include_children: true, limit });

function Skeleton({ big }) {
  return (
    <div className="pdb-212__cols">
      <div className="pdb-212__side"><div className="pdb-skel" style={{ height: 350, marginBottom: 7 }} /><div className="pdb-skel" style={{ height: 350 }} /></div>
      <div className="pdb-212__mid"><div className="pdb-skel" style={{ height: big }} /></div>
      <div className="pdb-212__side"><div className="pdb-skel" style={{ height: 350, marginBottom: 7 }} /><div className="pdb-skel" style={{ height: 350 }} /></div>
    </div>
  );
}

function Nav({ tabs, active, setActive, mode, v1, align }) {
  const label = (t) => <span {...(t.field ? { "data-pd-field": t.field } : { "data-pd-data": "" })}>{t.label}</span>;
  if (v1) {
    return (
      <div className="pdb-212__navwrap">
        <ul className={`pdb-212__nav${align === "center" ? " pdb-212__nav--center" : ""}`} role="tablist">
          {tabs.map((t, i) => (
            <li key={t.key}>
              {mode === "links" && linkHref(t.link) ? (
                <SmartLink link={t.link} className={i === 0 ? "active" : ""}>{label(t)}</SmartLink>
              ) : (
                <a href={`#sekme-${i}`} role="tab" aria-selected={i === active} className={i === active ? "active" : ""}
                  onClick={(e) => { e.preventDefault(); setActive(i); }}>{label(t)}</a>
              )}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <div className="position-relative text-center z-index-2 mb-3">
      <ul className={`nav nav-classic nav-tab nav-tab-sm px-md-3 justify-content-start ${align === "left" ? "" : "justify-content-lg-center"} flex-nowrap flex-lg-wrap overflow-auto overflow-lg-visble border-md-down-bottom-0 pb-1 pb-lg-0 mb-n1 mb-lg-0`} role="tablist">
        {tabs.map((t, i) => (
          <li className="nav-item flex-shrink-0 flex-lg-shrink-1" key={t.key}>
            {mode === "links" && linkHref(t.link) ? (
              <SmartLink link={t.link} className={`nav-link${i === 0 ? " active" : ""}`}><div className="d-md-flex justify-content-md-center align-items-md-center">{label(t)}</div></SmartLink>
            ) : (
              <a href={`#sekme-${i}`} role="tab" aria-selected={i === active} className={`nav-link${i === active ? " active" : ""}`} onClick={(e) => { e.preventDefault(); setActive(i); }}>
                <div className="d-md-flex justify-content-md-center align-items-md-center">{label(t)}</div>
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const v1 = st._variant !== "4_1_4";
  const need = v1 ? 5 : 9;
  const tree = useCategoryTree();
  const roots = tree.menuRoots || tree.roots || [];
  const auto = st.nav_auto_categories || {};
  const tabs = useMemo(() => {
    const fixed = (st.nav_items || []).map((t, i) => ({ t, i })).filter(({ t }) => t && (t.label || t.source?.category_ids?.length)).map(({ t, i }) => {
      const cid = t.source?.kind === "category" ? (t.source.category_ids || [])[0] : null;
      const node = cid ? tree.byId?.get(String(cid)) : null;
      return { key: t._id || `n${i}`, label: t.label || node?.name || "", source: t.source,
        link: linkHref(t.link) ? t.link : (node ? { kind: "category", url: `/${node.slug}` } : null), field: t.label ? `nav_items.${i}.label` : null };
    });
    const ex = new Set((auto.exclude || []).map(String));
    const autos = auto.enabled ? roots.filter((c) => !ex.has(String(c.id))).slice(0, Math.max(0, Number(auto.max) || 0))
      .map((c) => ({ key: `c${c.id}`, label: c.name, source: catSource(c, need), link: { kind: "category", url: `/${c.slug}` } })) : [];
    return [...fixed, ...autos].slice(0, 12);
  }, [st.nav_items, auto.enabled, auto.max, auto.exclude, roots, tree.byId, need]); // eslint-disable-line react-hooks/exhaustive-deps
  const [picked, setActive] = useState(0);
  const active = st.nav_mode === "links" ? 0 : Math.min(picked, Math.max(0, tabs.length - 1));
  const cur = tabs[active];
  const list = useProductSource(cur ? cur.source : null);
  const manual = useProductSource(st.main_product_mode === "manual" && st.main_product ? { ...SRC_BASE, kind: "manual", product_ids: [st.main_product], limit: 1 } : null);
  if (!tabs.length) return null;
  const big = (st.main_product_mode === "manual" && (manual || [])[0]) || (list || [])[0] || null;
  const rest = (list || []).filter((p) => !big || p.id !== big.id);
  const nav = <Nav tabs={tabs} active={active} setActive={setActive} mode={st.nav_mode} v1={v1} align={st.nav_align} />;
  const empty = st.empty_text ? <div className="text-center py-6 text-gray-90" data-pd-field="empty_text">{st.empty_text}</div> : null;

  if (v1) {
    const side = (items) => (
      <ul className="pdb-212__side">
        {items.map((p) => <ProductCard key={p.id} product={p} card="grid" as="li" className="remove-divider" innerClassName="product-item__inner bg-white p-3 h-100" listName="products_212" />)}
      </ul>
    );
    return (
      <div className="container pdb-212" data-testid="products-212">
        {st.title && <h2 className="sr-only" data-pd-field="title">{st.title}</h2>}
        {nav}
        {!list ? <Skeleton big={720} /> : !list.length ? empty : (
          <div className={`pdb-212__cols${st.column_widths === "25_50_25" ? " pdb-212__cols--25" : ""}`} key={active}>
            {side(rest.slice(0, 2))}
            <ul className="pdb-212__mid">
              {big && <MainProduct product={big} thumbnails={st.main_thumbnails ? 3 : 0} lightbox={!!st.lightbox} listName="products_212" />}
            </ul>
            {side(rest.slice(2, 4))}
          </div>
        )}
      </div>
    );
  }

  const cell = (p, i) => (
    <li key={p.id} className={`col-xl-6 product-item max-width-xl-100 remove-divider${i >= 2 ? " d-md-none d-wd-block" : ""}`}>
      <ProductCard product={p} card="grid" as="div" className="h-100 remove-divider" innerClassName="product-item__inner bg-white p-3" listName="products_414" />
    </li>
  );
  return (
    <div className="container products-group-4-1-4" data-testid="products-212">
      {st.title && <h2 className="sr-only" data-pd-field="title">{st.title}</h2>}
      {nav}
      <div className="tab-content">
        <div className="tab-pane fade pt-2 show active" role="tabpanel">
          {!list ? <Skeleton big={560} /> : !list.length ? empty : (
            <div className="row no-gutters" key={active}>
              <div className="col-md-3 col-wd-4 d-md-flex d-wd-block">
                <ul className="row list-unstyled products-group no-gutters mb-0 flex-xl-column flex-wd-row">{rest.slice(0, 4).map(cell)}</ul>
              </div>
              <div className="col-md-6 col-wd-4 products-group-1">
                <ul className="row list-unstyled products-group no-gutters bg-white h-100 mb-0">
                  {big && <MainProduct product={big} thumbnails={st.main_thumbnails ? 3 : 0} lightbox={!!st.lightbox} aspect="564 / 520" listName="products_414" />}
                </ul>
              </div>
              <div className="col-md-3 col-wd-4 d-md-flex d-wd-block">
                <ul className="row list-unstyled products-group no-gutters mb-0 flex-xl-column flex-wd-row">{rest.slice(4, 8).map(cell)}</ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
