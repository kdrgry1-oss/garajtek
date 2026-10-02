// Blok testleri için ortak yardımcılar (grup ajanları da kullanır): render, fetch taklidi, data-pd-field denetimi.
import { act } from "react";
import { createRoot } from "react-dom/client";
import { PageCtx } from "./_shared/PageCtx";
import { getBlock, withDefaults } from "./registry";
import { clearProductSourceCache } from "./_shared/useProductSource";

global.IS_REACT_ACT_ENVIRONMENT = true;

/** resolve-products / brands vb. için fetch taklidi. products: kaynak başına dönecek liste. */
export function mockFetch(products = []) {
  clearProductSourceCache();
  global.fetch = jest.fn((url, opts) => {
    let body = { results: [] };
    if (String(url).includes("resolve-products")) {
      const n = JSON.parse(opts?.body || "{}").sources?.length || 0;
      body = { results: Array.from({ length: n }, () => products) };
    } else if (String(url).includes("/page-blocks/brands")) body = { items: [] };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) });
  });
  return global.fetch;
}

/** Bloğu varsayılanlarıyla (veya verilen ayarlarla) render eder → {container, unmount}. */
export async function renderBlock(type, settings = {}, { preview = false } = {}) {
  const entry = getBlock(type);
  const st = withDefaults(type, settings);
  const container = document.createElement("div");
  container.className = "electro";
  document.body.appendChild(container);
  const root = createRoot(container);
  const { Render, schema } = entry;
  await act(async () => {
    root.render(
      <PageCtx.Provider value={{ preview, page: "home", selectedId: null }}>
        <Render block={{ id: "b1", type, title: schema.title, settings: st }} settings={st} schema={schema} ctx={{ preview }} />
      </PageCtx.Provider>,
    );
  });
  await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  return { container, unmount: () => act(() => root.unmount()) };
}

/** SPEC §9: görünür her metin düğümü data-pd-field (panelden) ya da data-pd-data / .product-item (katalog) altında olmalı. */
export function hardcodedTexts(container) {
  const out = [];
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  let n = walker.nextNode();
  while (n) {
    const t = n.textContent.replace(/\s+/g, " ").trim();
    if (t && !/^[\s:·|/–—%₺,.\-+×x\d]*$/.test(t)) {
      const el = n.parentElement;
      if (!el.closest("[data-pd-field],[data-pd-data],[data-pd-placeholder],.product-item,.sr-only,script,style")) out.push(t);
    }
    n = walker.nextNode();
  }
  return out;
}
