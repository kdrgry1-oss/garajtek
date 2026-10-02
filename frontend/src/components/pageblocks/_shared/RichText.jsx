// Şema `rich_text` değeri (sunucuda beyaz listeyle temizlenmiş) — istemcide de ikinci kez temizlenir.
import { sanitizeHtml } from "../../../lib/sanitizeHtml";

export default function RichText({ html, as: Tag = "span", className = "", field, ...rest }) {
  const clean = sanitizeHtml(html || "");
  if (!clean) return null;
  return <Tag className={`pd-rt ${className}`} data-pd-field={field} dangerouslySetInnerHTML={{ __html: clean }} {...rest} />;
}
