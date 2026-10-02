// A3 full_banner — şablon home-banner (1170×207 görsel bağlantı). Varyant text_overlay (v2.0) Grup A'da.
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import { plainText } from "../_shared/schema";
import { trackSelectPromotion } from "../../../lib/dataLayer";

export default function Render({ settings, block }) {
  const st = settings;
  const img = st.image;
  const ratio = img?.w && img?.h ? `${img.w} / ${img.h}` : "1170 / 207";
  const overlay = st._variant === "text_overlay";
  const onClick = () => { try { trackSelectPromotion({ promotionId: "full_banner", promotionName: block?.title || linkHref(st.link) }); } catch { /* yoksay */ } };
  return (
    <div data-testid="full-banner" className={overlay ? "position-relative" : undefined}>
      <SmartLink link={st.link} fallback="div" className="d-block" onClick={onClick}>
        <SmartImage image={img} size={[1170, 207]} width={1400} className="img-fluid w-100" style={{ aspectRatio: ratio }} field="image" />
      </SmartLink>
      {overlay && (
        <div className="position-absolute d-flex align-items-center justify-content-between px-6" style={{ inset: 0, pointerEvents: "none" }}>
          {plainText(st.title) && <RichText as="h3" html={st.title} className="font-size-24 mb-0 text-uppercase" field="title" />}
          {st.price && (
            <div className="p-3 text-center rounded" style={{ backgroundColor: st.price_box_color || undefined }}>
              {st.price_label && <div className="font-size-12" data-pd-field="price_label">{st.price_label}</div>}
              <div className="font-size-30 font-weight-bold" data-pd-field="price">{st.price}</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
