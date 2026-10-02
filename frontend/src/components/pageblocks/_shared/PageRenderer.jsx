// Sayfa düzeni → bloklar. Registry'den Render seçer, BlockFrame ile sarar (SPEC §8.4).
//   * Bilinmeyen / `_legacy` / pasif / zamanı gelmemiş bloklar çizilmez (vitrin = önizleme).
//   * Üst bar blokları (rotating_text, countdown_bar) Header'a verilir, akışta çizilmez.
//   * layout "left_sidebar": `layout: sidebar` şemalı bloklar sol kenar çubuğuna, diğerleri ana sütuna.
//   * Önizlemede blok arası "+ Blok ekle" çizgisi ve tıkla-seç.
import { Component, useMemo } from "react";
import { allFields, getBlock, TOP_BAR_TYPES, withDefaults } from "../registry";
import BlockFrame from "./BlockFrame";
import { usePageCtx } from "./PageCtx";
import { filterItems, scheduleActive } from "./schema";

class BlockBoundary extends Component {
  constructor(p) { super(p); this.state = { err: null }; }
  static getDerivedStateFromError(err) { return { err }; }
  componentDidCatch(err) { try { console.error("[pageblocks]", this.props.type, err); } catch { /* yoksay */ } }
  render() {
    if (this.state.err) return this.props.preview ? <div className="pd-stub pd-legacy">Blok çizilemedi: {String(this.state.err.message || this.state.err)}</div> : null;
    return this.props.children;
  }
}

/** Yayın/önizleme kuralları uygulanmış, varsayılanlarla dolu bloklar. */
export function prepareBlocks(blocks, { now = new Date(), isMember = false } = {}) {
  const out = [];
  (blocks || []).forEach((b) => {
    if (!b || b.is_active === false) return;
    const entry = getBlock(b.type);
    if (!entry || b.settings?._legacy) return;
    const st = withDefaults(b.type, b.settings);
    const vis = st._visibility || {};
    if (!scheduleActive(vis.schedule, now)) return;
    if ((vis.audience === "members" && !isMember) || (vis.audience === "guests" && isMember)) return;
    const filtered = filterItems(allFields(entry.schema), st, now);
    if (b.type === "hero_slider" && (st.slides || []).length && !(filtered.slides || []).length) return;
    out.push({ block: b, settings: filtered, entry });
  });
  return out;
}

function Insert({ index }) {
  const ctx = usePageCtx();
  if (!ctx.preview || !ctx.onInsert) return null;
  return (
    <div className="pd-insert" data-testid={`pd-insert-${index}`}>
      <button type="button" onClick={(e) => { e.stopPropagation(); ctx.onInsert(index); }}>+ Blok ekle</button>
    </div>
  );
}

export default function PageRenderer({ blocks, layout = "full", isMember = false, revealDefault = true, renderCtx = {} }) {
  const ctx = usePageCtx();
  const prepared = useMemo(() => prepareBlocks(blocks, { isMember }), [blocks, isMember]);
  const flow = prepared.filter((p) => !TOP_BAR_TYPES.has(p.block.type));
  const render = (p, i) => {
    const { Render, schema } = p.entry;
    const idx = (blocks || []).indexOf(p.block);
    return [
      <Insert key={`ins-${p.block.id}`} index={idx} />,
      <BlockBoundary key={p.block.id} type={p.block.type} preview={ctx.preview}>
        <BlockFrame block={p.block} schema={schema} settings={p.settings} index={i} revealDefault={revealDefault}>
          {Render ? <Render block={p.block} settings={p.settings} schema={schema} ctx={{ ...ctx, ...renderCtx, index: i }} /> : null}
        </BlockFrame>
      </BlockBoundary>,
    ];
  };
  const tail = <Insert key="ins-end" index={(blocks || []).length} />;
  if (layout === "left_sidebar") {
    const side = flow.filter((p) => p.entry.schema.layout === "sidebar");
    const main = flow.filter((p) => p.entry.schema.layout !== "sidebar");
    const firstContained = main.findIndex((p) => (p.settings._section?.width || p.entry.schema.layout) !== "full_bleed");
    const top = firstContained < 0 ? main : main.slice(0, firstContained);
    const rest = firstContained < 0 ? [] : main.slice(firstContained);
    return (
      <>
        {top.map(render)}
        <div className="container">
          <div className="row">
            <div className="d-none d-xl-block col-xl-3 col-wd-2gdot5 pd-sidebar" data-testid="pd-sidebar">{side.map(render)}</div>
            <div className="col-xl-9 col-wd-9gdot5">{rest.map((p, i) => render(p, i + top.length))}</div>
          </div>
        </div>
        {tail}
      </>
    );
  }
  return <>{flow.map(render)}{tail}</>;
}

/** Sayfada (görünür) `product_columns` bloğu var mı? → Footer kendi ürün bandını gizler. */
export function hasProductColumns(blocks) {
  return prepareBlocks(blocks).some((p) => p.block.type === "product_columns");
}
