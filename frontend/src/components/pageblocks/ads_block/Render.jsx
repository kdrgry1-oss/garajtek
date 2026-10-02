// A2 ads_block — şablon home-v1-ads-block (3 sütun: 410×281, 410×281, 714×486 + metin). Grup A geliştirir.
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import { plainText } from "../_shared/schema";
import { trackSelectPromotion } from "../../../lib/dataLayer";

const SIZES = [[410, 281], [410, 281], [714, 486], [410, 281]];
const RATIO = { "60_40": ["col-6 col-xl-5 col-wd-6 pr-0", "col-6 col-xl-7 col-wd-6"], "62_38": ["col-7 pr-0", "col-5"], "50_50": ["col-6 pr-0", "col-6"] };
const promo = (id, name) => { try { trackSelectPromotion({ promotionId: id, promotionName: name }); } catch { /* yoksay */ } };

function colClass(n, i, count) {
  if (n === 2) return "col-md-6 mb-4 mb-md-0";
  if (n === 4) return "col-6 col-lg-3 mb-4 mb-lg-0";
  return `${i === 2 && count === 3 ? "col-md-12" : "col-md-6"} col-lg-4 mb-4 mb-lg-0`;
}

export default function Render({ settings }) {
  const st = settings;
  const items = (st.items || []).filter(Boolean);
  if (!items.length) return null;
  const n = Number(st.columns) || 3;
  const [imgCol, txtCol] = RATIO[st.ratio] || RATIO["60_40"];
  return (
    <div data-testid="ads-block">
      <div className="row">
        {items.slice(0, 4).map((it, i) => {
          const f = `items.${i}`;
          const size = SIZES[i] || SIZES[0];
          return (
            <div className={colClass(n, i, items.length)} key={it._id || i}>
              <SmartLink link={it.link} fallback="div" className="d-block text-gray-90 el-ad" data-testid={`ad-${i + 1}`}
                onClick={() => promo(`ad_${i + 1}`, plainText(it.text) || linkHref(it.link))}>
                <div className="min-height-132 py-1 d-flex align-items-center" style={{ backgroundColor: st.card_background || undefined }}>
                  <div className={imgCol}>
                    <SmartImage image={it.image} size={size} width={420} className="img-fluid el-ad__img" field={`${f}.image`}
                      style={{ aspectRatio: `${size[0]} / ${size[1]}`, transform: it.image_rotation ? `rotate(${it.image_rotation}deg)` : undefined }} />
                  </div>
                  <div className={txtCol}>
                    <RichText as="div" html={it.text} className="mb-2 pb-1 font-weight-light text-ls-n1 text-lh-23 el-banner-text" field={`${f}.text`}
                      style={{ fontSize: `${Number(st.text_size) || 1.286}em` }} />
                    {it.action_type === "upto" || it.action_type === "from_price" ? (
                      <div className="text-gray-90 el-ad__upto">
                        {it.action_prefix && <span className="font-size-12 text-uppercase mr-1" data-pd-field={`${f}.action_prefix`}>{it.action_prefix}</span>}
                        {it.action_type === "from_price" && it.currency && <span className="font-size-20 font-weight-bold" data-pd-field={`${f}.currency`}>{it.currency}</span>}
                        <span className="font-size-30 font-weight-bold" data-pd-field={`${f}.action_value`}>{it.action_value}</span>
                        {it.action_suffix && <span className={it.action_type === "from_price" ? "font-size-20 font-weight-bold" : "font-size-12 ml-1"} data-pd-field={`${f}.action_suffix`}>{it.action_suffix}</span>}
                      </div>
                    ) : it.action_text ? (
                      <div className="link text-gray-90 font-weight-bold font-size-15">
                        <span data-pd-field={`${f}.action_text`}>{it.action_text}</span>
                        <span className="link__icon ml-1"><span className="link__icon-inner"><i className="ec ec-arrow-right-categproes" /></span></span>
                      </div>
                    ) : null}
                  </div>
                </div>
              </SmartLink>
            </div>
          );
        })}
      </div>
    </div>
  );
}
