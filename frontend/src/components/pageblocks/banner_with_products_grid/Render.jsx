// B7 banner_with_products_grid — Banner + Ürün Izgarası (v2.0 home-v2/v4/v7 "Smartphones & Tablets" vb., home-v10
// "Categories menu and Product"). Başlık satırında hap sekmeler (her sekme kendi ürün kaynağı); yanda 360×616 banner,
// büyük ürün, kategori listesi veya kutulu menü; sağda cihaz başına sütunlu ürün ızgarası.
import { useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard from "../_shared/ProductCard";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import MainProduct from "../product_grid_212/MainProduct";
import GridHeader from "../product_grid/GridHeader";
import { colCounts, colsStyle, dividerClasses } from "../deals_tabs/gridUtil";
import "./style.css";

const MANUAL = { kind: "manual", category_ids: [], include_children: true, tag: "", brand_ids: [], sort: "default", exclude_out_of_stock: false, exclude_ids: [], fill_with: "none" };

function CategoryList({ links }) {
  return (
    <div className="col-12 col-xl-auto pr-lg-2">
      <div className="min-width-200 mt-xl-5">
        <ul className="list-group list-group-flush flex-nowrap flex-xl-wrap flex-row flex-xl-column overflow-auto overflow-xl-visble mb-3 mb-xl-0">
          {links.map(({ c, i }) => (
            <li className="border-color-1 list-group-item border-lg-down-0 flex-shrink-0 flex-xl-shrink-1" key={c._id || i}>
              <SmartLink link={c.link} className="hover-on-bold py-1 px-3 text-gray-90 d-block" field={`category_links.${i}.label`}>{c.label}</SmartLink>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function Menu({ title, links }) {
  return (
    <div className="d-none d-xl-block col-xl-auto mb-6 mb-md-0">
      <div className="bg-white borders-radius-10 box-shadow-3 mb-5">
        <div className="max-width-270 min-width-270">
          {title && <div className="border-bottom mx-3 mt-3 mb-2"><h5 className="section-title section-title__sm mb-0 pb-2 font-weight-bold font-size-18 mx-1" data-pd-field="menu_title">{title}</h5></div>}
          <ul className="list-unstyled mb-0 pb-2">
            {links.map(({ c, i }) => (
              <li key={c._id || i}><SmartLink link={c.link} className="d-block px-4 py-2 text-gray-90 font-weight-bold" field={`category_links.${i}.label`}>{c.label}</SmartLink></li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const tabs = useMemo(() => (st.tabs || []).map((t, i) => ({ t, i })).filter(({ t }) => t && t.label), [st.tabs]);
  const [picked, setPicked] = useState(null);
  const def = Math.max(0, tabs.findIndex(({ t }) => t.active));
  const activePos = picked !== null && picked < tabs.length ? picked : def;
  const cur = tabs[activePos];
  const list = useProductSource(cur ? cur.t.source : null);
  const featured = useProductSource(st.side === "featured_product" && st.featured_product ? { ...MANUAL, product_ids: [st.featured_product], limit: 1 } : null);
  const cols = colCounts(st.columns, { desktop: 4, tablet: 3, mobile: 2 });
  if (!tabs.length) return null;
  // Sağ taraf: "Haplar" → sekme hapları (+ başlığın kendi hap bağlantıları); "Bağlantı" → sekme hapları + "Tümünü gör";
  // "Hiçbiri" (veya ok/geri sayım) → sekme hapı yok, başlangıçta seçili sekmenin ürünleri gösterilir.
  const hr = st.header?.right || "pills";
  const tabPills = (hr === "pills" || hr === "link") && tabs.length > 1 ? tabs.map(({ t }) => ({ label: t.label, as_tab: true, link: { kind: "none", url: "" } })) : [];
  const extra = hr === "pills" ? (st.header?.pills || []).map((p, j) => ({ p, j })).filter(({ p }) => p && p.label) : [];
  const header = { ...(st.header || {}), right: tabPills.length || extra.length ? "pills" : hr === "link" ? "link" : "none",
    pills: [...tabPills, ...extra.map(({ p }) => ({ label: p.label, as_tab: false, link: p.link || { kind: "none", url: "" } }))] };
  const pillField = (pos) => (pos < tabPills.length ? `tabs.${tabs[pos].i}.label` : `header.pills.${extra[pos - tabPills.length].j}.label`);
  const links = (st.category_links || []).map((c, i) => ({ c, i })).filter(({ c }) => c && c.label);
  const banner = st.banner || {};
  let side = null;
  if (st.side === "banner") {
    const img = <SmartImage image={banner.image} size={[360, 616]} width={720} field="banner.image" className="img-fluid" />;
    side = (
      <>
        {st.show_list && links.length > 0 && <CategoryList links={links} />}
        <div className="col-md-6 col-lg-auto mb-4 mb-md-0"><div className="pdb-bpg__banner">{linkHref(banner.link) ? <SmartLink link={banner.link} className="d-block">{img}</SmartLink> : img}</div></div>
      </>
    );
  } else if (st.side === "featured_product") {
    // ürün seçilmediyse etkin sekmenin ilk ürünü büyük gösterilir (ızgaradan çıkarılır)
    const p = (featured || [])[0] || (!st.featured_product ? (list || [])[0] : null);
    side = p ? <div className="col-md-6 col-lg-4 col-xl-3 mb-4 mb-md-0"><ul className="list-unstyled h-100 mb-0 d-flex"><MainProduct product={p} thumbnails={3} listName="banner_products_grid" aspect="1 / 1" /></ul></div> : null;
  } else if (st.side === "category_list" && links.length) {
    side = <CategoryList links={links} />;
  } else if (st.side === "menu" && links.length) {
    side = <Menu title={st.menu_title} links={links} />;
  }
  const grid = (
    <div className="col-md pl-md-0 min-width-0">
      <div className="tab-content">
        <div className="tab-pane show active pt-2" role="tabpanel" key={activePos}>
          {!list ? <div className="pdb-skel" style={{ height: 600 }} /> : !list.length ? (
            st.empty_text ? <div className="text-center py-6 text-gray-90" data-pd-field="empty_text">{st.empty_text}</div> : null
          ) : (
            <ul className="pdb-cols list-unstyled products-group no-gutters mb-0" style={colsStyle(cols)}>
              {list.filter((p) => !(st.side === "featured_product" && !st.featured_product && p === list[0])).map((p, i) => <ProductCard key={p.id} product={p} card={st.card || "grid"} as="li" listName="banner_products_grid" index={i} className={dividerClasses(i, cols)} />)}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
  const onPill = (pos) => { if (pos < tabPills.length) setPicked(pos); };
  return (
    <div className="pdb-bpg" data-testid="banner-products-grid">
      <div className="position-relative text-center z-index-2">
        <GridHeader value={header} active={tabPills.length ? activePos : -1} onPill={onPill} className="mb-0" pillField={pillField} withLink={hr === "link"} />
      </div>
      <div className={`row${st.side_position === "right" ? " flex-row-reverse" : ""}`}>
        {side}
        {grid}
      </div>
    </div>
  );
}
