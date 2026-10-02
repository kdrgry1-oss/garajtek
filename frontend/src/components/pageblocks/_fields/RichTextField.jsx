// Mini zengin metin editörü: Kalın, İtalik, satır sonu, vurgu rengi (span.hl), üst/alt simge, bağlantı.
// Çıktı backend beyaz listesiyle aynı alt küme (strong, em, br, span.hl, sup, sub, a[href]).
import { useEffect, useRef } from "react";
import { sanitizeHtml } from "../../../lib/sanitizeHtml";
import { smallBtn } from "./widgets";

export function normalizeHtml(html) {
  let s = String(html || "")
    .replace(/<div><br\s*\/?><\/div>/gi, "<br>")
    .replace(/<\/(div|p)>\s*<(div|p)[^>]*>/gi, "<br>")
    .replace(/<\/?(div|p)[^>]*>/gi, "")
    .replace(/<b(\s[^>]*)?>/gi, "<strong>").replace(/<\/b>/gi, "</strong>")
    .replace(/<i(\s[^>]*)?>/gi, "<em>").replace(/<\/i>/gi, "</em>")
    .replace(/&nbsp;/g, " ");
  s = sanitizeHtml(s);
  return s.replace(/<span(?![^>]*class="hl")[^>]*>(.*?)<\/span>/gi, "$1").replace(/(<br>)+$/i, "");
}

export default function RichTextField({ field, value, onChange }) {
  const ref = useRef(null);
  const last = useRef(value || "");
  const marks = new Set(field.marks || ["strong", "em", "br", "span_highlight", "sup", "sub", "link"]);
  useEffect(() => {
    if (ref.current && (value || "") !== last.current) { ref.current.innerHTML = value || ""; last.current = value || ""; }
  }, [value]);
  useEffect(() => { if (ref.current) ref.current.innerHTML = value || ""; }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const emit = () => { const h = normalizeHtml(ref.current.innerHTML); last.current = h; onChange(h); };
  const cmd = (c, arg) => { ref.current.focus(); document.execCommand(c, false, arg); emit(); };
  const wrapHl = () => {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount || sel.isCollapsed) return;
    const r = sel.getRangeAt(0);
    const span = document.createElement("span");
    span.className = "hl";
    try { r.surroundContents(span); } catch { return; }
    emit();
  };
  return (
    <div className="border border-gray-300 rounded bg-white">
      <div className="flex flex-wrap gap-1 p-1 border-b bg-gray-50">
        {marks.has("strong") && <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); cmd("bold"); }} title="Kalın"><b>K</b></button>}
        {marks.has("em") && <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); cmd("italic"); }} title="İtalik"><i>İ</i></button>}
        {marks.has("br") && <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); cmd("insertHTML", "<br>"); }} title="Satır sonu">↵ Satır</button>}
        {marks.has("span_highlight") && <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); wrapHl(); }} title="Vurgu rengi"><span className="text-yellow-500 font-bold">A</span> Vurgu</button>}
        {marks.has("sup") && <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); cmd("superscript"); }} title="Üst simge">x²</button>}
        {marks.has("sub") && <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); cmd("subscript"); }} title="Alt simge">x₂</button>}
        {marks.has("link") && <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); const u = window.prompt("Bağlantı adresi (/sayfa/... veya https://...)"); if (u) cmd("createLink", u); }} title="Bağlantı">🔗</button>}
        <button type="button" className={smallBtn} onMouseDown={(e) => { e.preventDefault(); cmd("removeFormat"); }} title="Biçimi temizle">Temizle</button>
      </div>
      <div ref={ref} contentEditable suppressContentEditableWarning role="textbox" aria-multiline="true" aria-label={field.label}
        className="px-2 py-1.5 text-sm min-h-[2.5rem] focus:outline-none" onInput={emit} onBlur={emit}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); if (marks.has("br")) cmd("insertHTML", "<br>"); } }} data-testid={`rt-${field.name}`} />
    </div>
  );
}
