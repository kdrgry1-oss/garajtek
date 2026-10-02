// A12 text_block — başlık + zengin metin (+ görsel/bağlantı). Eski HTML içerik (legacy_html) temizlenerek basılır.
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import { plainText } from "../_shared/schema";

export default function Render({ settings }) {
  const st = settings;
  const img = st.image?.url ? st.image : null;
  const href = linkHref(st.link);
  if (!st.title && !plainText(st.body) && !img && !st.legacy_html) return null;
  const align = st.align === "center" ? "text-center mx-auto" : st.align === "right" ? "text-right ml-auto" : "";
  return (
    <div data-testid="text-block">
      {st.title && (
        <div className="border-bottom border-color-1 mb-4"><h3 className="section-title mb-0 pb-2 font-size-22" data-pd-field="title">{st.title}</h3></div>
      )}
      <div className="row align-items-center">
        {img && (
          <div className="col-md-6 mb-4 mb-md-0">
            <SmartLink link={st.link} fallback="div"><SmartImage image={img} width={1200} field="image" /></SmartLink>
          </div>
        )}
        <div className={img ? "col-md-6" : "col-12"}>
          <div className={align} style={{ maxWidth: st.max_width ? `${st.max_width}px` : undefined }}>
            <RichText as="div" html={st.body} className="font-size-16 text-gray-90" field="body" />
            {st.legacy_html && <RichText as="div" html={st.legacy_html} field="legacy_html" />}
            {href && st.button_text && <SmartLink link={st.link} className="btn btn-primary-dark-w px-5 rounded-pill mt-3" field="button_text">{st.button_text}</SmartLink>}
          </div>
        </div>
      </div>
    </div>
  );
}
