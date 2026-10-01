// Mesafeli Satış Sözleşmesi / Ön Bilgilendirme Formu — sayfadan ayrılmadan modalda okunur.
// İçerik CMS'ten (/api/pages/{slug}) gelir ve sanitize edilir.
import { useEffect, useState } from "react";
import axios from "axios";
import { sanitizeHtml } from "../../lib/sanitizeHtml";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LegalModal({ slug, fallbackTitle, onClose }) {
  const [page, setPage] = useState(null);
  const [state, setState] = useState("loading");

  useEffect(() => {
    let alive = true;
    setState("loading");
    axios.get(`${API}/pages/${slug}`)
      .then((r) => { if (alive) { setPage(r.data || null); setState(r.data ? "ok" : "missing"); } })
      .catch(() => { if (alive) setState("missing"); });
    return () => { alive = false; };
  }, [slug]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="gt-modal-backdrop" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }} data-testid="legal-modal">
      <div className="gt-modal" role="dialog" aria-modal="true" aria-label={page?.title || fallbackTitle}>
        <div className="gt-modal-head">
          <h2 className="gt-h2">{page?.title || fallbackTitle}</h2>
          <button type="button" className="gt-icon-btn" onClick={onClose} aria-label="Kapat" data-testid="legal-modal-close">
            <svg viewBox="0 0 20 20" width="18" height="18"><path d="M5 5l10 10M15 5L5 15" stroke="currentColor" strokeWidth="1.8" /></svg>
          </button>
        </div>
        <div className="gt-modal-body">
          {state === "loading" && <p className="gt-muted">Yükleniyor…</p>}
          {state === "missing" && (
            <p className="gt-muted">
              Metin şu anda yüklenemedi.{" "}
              <a href={`/sayfa/${slug}`} target="_blank" rel="noreferrer">Yeni sekmede açın</a>.
            </p>
          )}
          {state === "ok" && (
            <div className="gt-legal-content" dangerouslySetInnerHTML={{ __html: sanitizeHtml(page.content || "") }} />
          )}
        </div>
        <div className="gt-modal-foot">
          <button type="button" className="gt-btn gt-btn-secondary" onClick={onClose}>Kapat</button>
        </div>
      </div>
    </div>
  );
}
