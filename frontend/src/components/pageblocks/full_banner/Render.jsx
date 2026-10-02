// A3 full_banner — şablon home-banner (T1 inc/blocks/homepage/home-banner.php): .fullbanner-ad > a > img (1170×207,
// img-responsive), alt boşluk 70 px. Varyant text_overlay — T2 index "Full banner": 1400×206 arka plan üzerinde
// h1 (32 px, 300, <strong>) + ana renk kutuda "STARTING AT" / fiyat.
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import { plainText } from "../_shared/schema";
import { optimizeImg } from "../../../lib/img";
import { trackSelectPromotion } from "../../../lib/dataLayer";

export default function Render({ settings, block }) {
  const st = settings;
  const img = st.image;
  const onClick = () => { try { trackSelectPromotion({ promotionId: "full_banner", promotionName: block?.title || linkHref(st.link) }); } catch { /* yoksay */ } };
  if (st._variant === "text_overlay") {
    const bg = img?.url ? `url("${optimizeImg(img.url, 1400)}")` : undefined;
    return (
      <div data-testid="full-banner" className="pd-fullbanner pd-fullbanner--text">
        <SmartLink link={st.link} fallback="div" className="d-block text-gray-90" onClick={onClick}>
          <div className="bg-img-hero position-relative" data-pd-field="image"
            style={{ backgroundImage: bg, backgroundColor: st.background_color || undefined, minHeight: st.min_height ? `${st.min_height}px` : undefined,
              backgroundPosition: img?.focal ? `${Math.round(img.focal.x * 100)}% ${Math.round(img.focal.y * 100)}%` : undefined, color: st.text_color || undefined }}>
            <div className="space-top-2-md p-4 pt-6 pt-md-8 pt-lg-6 pt-xl-8 pb-lg-4 px-xl-8 px-lg-6">
              <div className="flex-horizontal-center mt-lg-3 mt-xl-0 overflow-auto overflow-md-visble">
                {plainText(st.title) && (
                  <RichText as="h2" html={st.title} field="title" className="text-lh-38 font-weight-light mb-0 flex-shrink-0 flex-md-shrink-1 text-uppercase"
                    style={{ fontSize: `${Number(st.title_size) || 32}px`, color: "inherit" }} />
                )}
                {(st.price || st.price_label) && (
                  <div className="ml-5 flex-content-center flex-shrink-0">
                    <div className="rounded-lg px-6 py-2" style={{ backgroundColor: st.price_box_color || "var(--electro-primary)" }}>
                      {st.price_label && <em className="font-size-14 font-weight-light d-block" data-pd-field="price_label">{st.price_label}</em>}
                      {st.price && <div className="font-size-30 font-weight-bold text-lh-1" data-pd-field="price">{st.price}</div>}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </SmartLink>
      </div>
    );
  }
  const ratio = img?.w && img?.h ? `${img.w} / ${img.h}` : "1170 / 207";
  return (
    <div data-testid="full-banner" className="pd-fullbanner fullbanner-ad">
      <SmartLink link={st.link} fallback="div" className="d-block" onClick={onClick}>
        <SmartImage image={img} size={[1170, 207]} width={1400} className="img-fluid w-100 d-block" style={{ aspectRatio: ratio }} field="image"
          alt={img?.alt || block?.title || ""} />
      </SmartLink>
    </div>
  );
}
