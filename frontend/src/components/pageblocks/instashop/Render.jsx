// A13 instashop — "Atölyemizden" görsel ızgarası (Instagram tarzı).
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import BlockCarousel from "../_shared/BlockCarousel";
import { useStoreInfo } from "../../../lib/storeInfo";
import { socialUrl } from "../../../lib/brand";

export default function Render({ settings }) {
  const st = settings;
  const store = useStoreInfo();
  const igUrl = socialUrl("instagram", store.instagram);
  const items = (st.items || []).filter((x) => x && x.image?.url).slice(0, 12);
  if (!items.length) return null;
  const cols = Number(st.columns) || 6;
  return (
    <div data-testid="instashop">
      <div className="border-bottom border-color-1 mb-3 d-flex justify-content-between align-items-end">
        {st.title && <h3 className="section-title mb-0 pb-2 font-size-22" data-pd-field="title">{st.title}</h3>}
        {st.show_follow && igUrl && st.follow_text && (
          <a href={igUrl} target="_blank" rel="noopener noreferrer" className="font-size-14 text-gray-90 pb-2"><i className="fab fa-instagram mr-1" /><span data-pd-field="follow_text">{st.follow_text}</span></a>
        )}
      </div>
      <BlockCarousel value={{ per_view: { 0: 2, 768: 4, 1200: cols }, gutter: 10, dots: true }}
        dotsClassName="text-center u-slick__pagination u-slick__pagination--long mb-0 mt-3">
        {items.map((it, i) => (
          <SmartLink key={it._id || i} link={it.link} fallback="div" className="d-block rounded overflow-hidden">
            <SmartImage image={it.image} alt={it.alt} width={500} className="img-fluid w-100" style={{ aspectRatio: "1 / 1", objectFit: "cover" }} field={`items.${i}.image`} />
          </SmartLink>
        ))}
      </BlockCarousel>
    </div>
  );
}
