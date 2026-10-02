// Şema `link` değeri ({kind, url, id, slug, new_tab}) → router <Link> / dış <a> / bağlantısız <span>.
// Önizlemede tıklamalar gezinmez (PreviewPage yakalar).
import { Link } from "react-router-dom";

export function linkHref(link) {
  if (!link) return "";
  if (typeof link === "string") return link;
  if (link.kind === "none") return "";
  if (link.kind === "category" && link.slug && !link.url) return `/${link.slug}`;
  if (link.kind === "search" && !link.url && link.label) return `/arama?q=${encodeURIComponent(link.label)}`;
  return link.url || "";
}

const isExternal = (to) => /^(https?:)?\/\//i.test(String(to || "")) || /^(mailto|tel):/i.test(String(to || ""));

export default function SmartLink({ link, to, children, className, field, fallback = "span", onClick, style, ...rest }) {
  const href = to !== undefined ? to : linkHref(link);
  const newTab = !!(link && typeof link === "object" && link.new_tab);
  const pd = field ? { "data-pd-field": field } : {};
  if (!href) {
    if (fallback === null) return <>{children}</>;
    const Tag = fallback;
    return <Tag className={className} style={style} {...pd} {...rest}>{children}</Tag>;
  }
  if (isExternal(href) || newTab) {
    return (
      <a href={href} className={className} style={style} onClick={onClick} {...pd} {...rest}
        {...(newTab || /^https?:/i.test(href) ? { target: "_blank", rel: "noopener noreferrer" } : {})}>{children}</a>
    );
  }
  return <Link to={href} className={className} style={style} onClick={onClick} {...pd} {...rest}>{children}</Link>;
}
