// Sayfa Tasarımı canlı önizleme rotası: /onizleme/sayfa/:page (yalnız geçerli yönetici oturumuyla, noindex).
// Vitrinin GERÇEK Home kabuğu (Header + PageRenderer + Footer) — panel taslağı postMessage ile gelir:
//   panel → iframe : {type:"pd:draft", layout:{blocks}, global, selectedId}, {type:"pd:select", blockId}
//   iframe → panel : {type:"pd:ready"}, {type:"pd:select", blockId, field}, {type:"pd:insert", index},
//                    {type:"pd:height", height}
import { useCallback, useEffect, useLayoutEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import axios from "axios";
import { HomeShell } from "./Home";
import { setPreviewState, postToParent } from "../lib/pagePreview";
import { withGlobalDefaults } from "../components/pageblocks/registry";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function PagePreview() {
  const { page = "home" } = useParams();
  const [blocks, setBlocks] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [error, setError] = useState("");

  // Önizleme modu: taslak global alanlar / üst barlar Header-Footer'a buradan yayılır
  useLayoutEffect(() => {
    setPreviewState({ active: true, page });
    const html = document.documentElement;
    html.classList.add("pd-preview");
    if (/[?&]pd-noanim=1/.test(window.location.search)) html.classList.add("pd-no-anim");
    let meta = document.querySelector('meta[name="robots"]');
    const prev = meta ? meta.getAttribute("content") : null;
    if (!meta) { meta = document.createElement("meta"); meta.setAttribute("name", "robots"); document.head.appendChild(meta); }
    meta.setAttribute("content", "noindex, nofollow");
    return () => {
      setPreviewState({ active: false, blocks: null, global: null, globalMerged: null });
      html.classList.remove("pd-preview", "pd-no-anim");
      if (prev === null) meta.remove(); else meta.setAttribute("content", prev);
    };
  }, [page]);

  // İlk yükleme: taslak (yoksa yayın) — panel pd:draft gönderince yerine geçer
  useEffect(() => {
    let token = null;
    try { token = localStorage.getItem("token"); } catch { token = null; }
    if (!token) { setError("Önizleme için yönetici girişi gerekli."); return; }
    axios.get(`${API}/page-design/${encodeURIComponent(page)}`, { headers: { Authorization: `Bearer ${token}` } })
      .then((r) => {
        const src = r.data?.draft || r.data?.published || {};
        setBlocks((cur) => cur || src.blocks || []);
        const g = r.data?.draft?.global || r.data?.published?.global;
        if (g) setPreviewState({ global: g, globalMerged: withGlobalDefaults(g), blocks: src.blocks || [] });
      })
      .catch((e) => setError(e?.response?.status === 401 || e?.response?.status === 403 ? "Önizleme için yönetici girişi gerekli." : "Önizleme yüklenemedi."));
  }, [page]);

  // Panel → iframe mesajları
  useEffect(() => {
    const onMsg = (e) => {
      if (e.origin !== window.location.origin || !e.data || typeof e.data !== "object") return;
      const m = e.data;
      if (m.type === "pd:draft") {
        const list = Array.isArray(m.layout?.blocks) ? m.layout.blocks : [];
        setBlocks(list);
        setError("");
        const patch = { blocks: list };
        if (m.global) { patch.global = m.global; patch.globalMerged = withGlobalDefaults(m.global); }
        setPreviewState(patch);
        if (m.selectedId !== undefined) setSelectedId(m.selectedId);
      } else if (m.type === "pd:select") {
        setSelectedId(m.blockId || null);
        if (m.scroll !== false && m.blockId) {
          setTimeout(() => {
            const el = document.querySelector(`[data-pd-block="${CSS.escape(m.blockId)}"]`);
            if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 30);
        }
      }
    };
    window.addEventListener("message", onMsg);
    postToParent({ type: "pd:ready", page });
    return () => window.removeEventListener("message", onMsg);
  }, [page]);

  // Önizlemede gezinme yok: bağlantı/form tıklamaları yutulur (tıkla-seç çalışır)
  useEffect(() => {
    const onClick = (e) => {
      const a = e.target.closest && e.target.closest("a[href], form button[type=submit]");
      if (a && !e.target.closest(".pd-insert")) e.preventDefault();
    };
    const onSubmit = (e) => e.preventDefault();
    document.addEventListener("click", onClick, true);
    document.addEventListener("submit", onSubmit, true);
    return () => { document.removeEventListener("click", onClick, true); document.removeEventListener("submit", onSubmit, true); };
  }, []);

  // Yükseklik bildirimi
  useEffect(() => {
    if (typeof ResizeObserver === "undefined") return undefined;
    const ro = new ResizeObserver(() => postToParent({ type: "pd:height", height: document.documentElement.scrollHeight }));
    ro.observe(document.body);
    return () => ro.disconnect();
  }, []);

  const onSelect = useCallback((id, e) => {
    const f = e?.target?.closest ? e.target.closest("[data-pd-field]") : null;
    setSelectedId(id);
    postToParent({ type: "pd:select", blockId: id, field: f ? f.getAttribute("data-pd-field") : null });
  }, []);
  const onInsert = useCallback((index) => postToParent({ type: "pd:insert", index }), []);
  const ctx = useMemo(() => ({ preview: true, page, selectedId, onSelect, onInsert }), [page, selectedId, onSelect, onInsert]);

  if (error) {
    return <div style={{ padding: 40, textAlign: "center", fontFamily: "system-ui, sans-serif" }} data-testid="preview-error">{error}</div>;
  }
  return <HomeShell blocks={blocks || []} loading={!blocks} ctx={ctx} />;
}
