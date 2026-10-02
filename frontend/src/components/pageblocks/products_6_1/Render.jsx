// B3 products_6_1 — "Çok Satanlar" 6+1 (şablon v1.0 homepage-3/products-6-1.php) / 8+1 (v2.0 home-v3 Products-8-1).
// Tam genişlik #f9f9f9 bant (58 px). Başlık satırı: başlık + haplar (bağlantı veya kendi kaynağıyla sekme).
// Solda 6 (veya 8) küçük kart, sağda sabit yükseklikli görselli büyük ürün + küçük resimler.
import { useMemo, useState } from "react";
import useProductSource from "../_shared/useProductSource";
import ProductCard from "../_shared/ProductCard";
import SectionHeader from "../_shared/SectionHeader";
import MainProduct from "../product_grid_212/MainProduct";
import "./style.css";

const MANUAL = { kind: "manual", category_ids: [], include_children: true, tag: "", brand_ids: [], sort: "default", exclude_out_of_stock: false, exclude_ids: [], fill_with: "none" };

export default function Render({ settings }) {
  const st = settings;
  const count = Number(st.count) === 8 ? 8 : 6;
  const header = st.header || {};
  const pills = (header.pills || []).filter((p) => p && p.label);
  const initial = Math.max(0, pills.findIndex((p) => p.active));
  const [pill, setPill] = useState(null);
  const activePill = pill ?? initial;
  const cur = pills[activePill];
  const source = useMemo(() => {
    const s = cur && cur.as_tab && cur.source && cur.source.kind ? cur.source : st.source;
    return s ? { ...s, limit: Math.max(Number(s.limit) || 0, count + 1) } : null;
  }, [cur, st.source, count]);
  const list = useProductSource(source);
  const manual = useProductSource(st.main_product_mode === "manual" && st.main_product ? { ...MANUAL, product_ids: [st.main_product], limit: 1 } : null);
  const big = (st.main_product_mode === "manual" && (manual || [])[0]) || (list || [])[0] || null;
  const rest = (list || []).filter((p) => !big || p.id !== big.id).slice(0, count);
  const onPill = pills.some((p) => p.as_tab) ? (i) => { if (pills[i]?.as_tab) setPill(i); } : undefined;
  return (
    <div className={`container pdb-61${count === 8 ? " pdb-61--8" : ""}`} data-testid="products-6-1">
      <SectionHeader value={header} field="header" activePill={activePill} onPill={onPill} className="pdb-61__header" />
      {!list ? (
        <div className="pdb-61__cols">
          <ul className="pdb-61__grid">{Array.from({ length: count }).map((_, i) => <li key={i}><div className="pdb-skel" style={{ height: 300 }} /></li>)}</ul>
          <div className="pdb-61__main"><div className="pdb-skel w-100" style={{ height: 610 }} /></div>
        </div>
      ) : !list.length ? (
        st.empty_text ? <div className="text-center py-6 text-gray-90" data-pd-field="empty_text">{st.empty_text}</div> : null
      ) : (
        <div className="pdb-61__cols" key={activePill}>
          <ul className="pdb-61__grid">
            {rest.map((p, i) => (
              <li key={p.id}><ProductCard product={p} card="grid" as="div" className="remove-divider" innerClassName="product-item__inner bg-white p-3" listName="products_6_1" index={i} /></li>
            ))}
          </ul>
          <ul className="pdb-61__main">
            {big && <MainProduct product={big} thumbnails={st.thumbnails} lightbox={!!st.lightbox} imageHeight={Number(st.main_image_height) || 367} listName="products_6_1" />}
          </ul>
        </div>
      )}
    </div>
  );
}
