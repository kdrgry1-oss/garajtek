// A2 ads_block — şablon home-v1-ads-block (T1 inc/blocks/homepage/home-v1-ads-block.php + _ads.scss):
// .ads-block.row > .ad.col-sm-4 > .media (#f5f5f5) > .media-left (%60, görsel) + .media-body (%40; padding 3.286em 0
// 2.143em) > .ad-text (1.286em/200/büyük harf) + .ad-action ("Shop now ›" | .upto prefix/value/suffix | .from).
// v2/v3: 2 sütun, 1.571em, -1px; v2_cards / wide_plus_two: v2.0 gri kartlar (link__icon oku).
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import { plainText } from "../_shared/schema";
import { trackSelectPromotion } from "../../../lib/dataLayer";
import "./ads.css";

const V1_SIZES = [[410, 281], [410, 281], [714, 486], [410, 281]];
const RATIO = { "60_40": [60, 40], "62_38": [62, 38], "50_50": [50, 50] };
const promo = (id, name) => { try { trackSelectPromotion({ promotionId: id, promotionName: name }); } catch { /* yoksay */ } };

function colClass(n) {
  if (n === 2) return "col-12 col-md-6";
  if (n === 4) return "col-12 col-md-6 col-xl-3";
  return "col-12 col-md-4";
}

function Action({ it, f, cards }) {
  const t = it.action_type || "link";
  if (t === "none") return null;
  if (t === "upto" || t === "from_price") {
    return (
      <div className="pd-ads__action">
        <span className={`pd-ads__${t === "upto" ? "upto" : "from"}`}>
          {it.action_prefix && <span className="pd-ads__prefix" data-pd-field={`${f}.action_prefix`}>{it.action_prefix}</span>}
          <span className="pd-ads__value">
            {t === "from_price" && it.currency && <sup data-pd-field={`${f}.currency`}>{it.currency}</sup>}
            <span data-pd-field={`${f}.action_value`}>{it.action_value}</span>
          </span>
          {it.action_suffix && <span className="pd-ads__suffix" data-pd-field={`${f}.action_suffix`}>{it.action_suffix}</span>}
        </span>
        {cards ? <span className="link__icon ml-1"><span className="link__icon-inner"><i className="ec ec-arrow-right-categproes" /></span></span>
          : <span className="pd-ads__arrow" aria-hidden="true"><i className="fa fa-angle-right" /></span>}
      </div>
    );
  }
  if (!it.action_text) return null;
  if (cards) {
    return (
      <div className="link text-gray-90 font-weight-bold font-size-15">
        <span data-pd-field={`${f}.action_text`}>{it.action_text}</span>
        <span className="link__icon ml-1"><span className="link__icon-inner"><i className="ec ec-arrow-right-categproes" /></span></span>
      </div>
    );
  }
  return (
    <div className="pd-ads__action">
      <span className="pd-ads__link" data-pd-field={`${f}.action_text`}>{it.action_text}</span>
      <span className="pd-ads__arrow" aria-hidden="true"><i className="fa fa-angle-right" /></span>
    </div>
  );
}

/** Şablon v1/v2/v3 (.ad .media tablo düzeni). */
function TableAd({ it, i, st, ratio }) {
  const f = `items.${i}`;
  const size = V1_SIZES[i] || V1_SIZES[0];
  return (
    <div className="pd-ads__media">
      <div className="pd-ads__left" style={{ width: `${ratio[0]}%` }}>
        <SmartImage image={it.image} size={size} width={720} className="pd-ads__img" field={`${f}.image`} phClassName="pd-ads__img"
          style={it.image_rotation ? { transform: `rotate(${it.image_rotation}deg)` } : undefined} />
      </div>
      <div className={`pd-ads__body${it.action_type === "upto" || it.action_type === "from_price" ? " pd-ads__body--num" : ""}`} style={{ width: `${ratio[1]}%` }}>
        <RichText as="div" html={it.text} className="pd-ads__text" field={`${f}.text`} />
        <Action it={it} f={f} />
      </div>
    </div>
  );
}

/** v2.0 kartları (bg-gray-1, 190×150 görsel, link__icon). */
function CardAd({ it, i, wide }) {
  const f = `items.${i}`;
  const size = wide ? [350, 300] : [190, 150];
  return (
    <div className={`${wide ? "max-height-152 overflow-hidden" : "min-height-132"} py-1 d-flex align-items-center pd-ads__card`}>
      <div className={wide ? "col-6 col-xl-7 pr-0" : "col-6 col-xl-5 col-wd-6 pr-0"}>
        <SmartImage image={it.image} size={size} width={400} className="img-fluid" field={`${f}.image`}
          style={it.image_rotation ? { transform: `rotate(${it.image_rotation}deg)` } : undefined} />
      </div>
      <div className={wide ? "col-6 col-xl-5" : "col-6 col-xl-7 col-wd-6"}>
        <RichText as="div" html={it.text} className="mb-2 pb-1 font-weight-light text-ls-n1 text-lh-23 pd-ads__text pd-ads__text--card" field={`${f}.text`} />
        <Action it={it} f={f} cards />
      </div>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const v = st._variant || "v1";
  const cards = v === "v2_cards" || v === "wide_plus_two";
  const items = (st.items || []).filter(Boolean).slice(0, 4);
  if (!items.length) return null;
  const n = Number(st.columns) || 3;
  const ratio = RATIO[st.ratio] || RATIO["60_40"];
  const pad = st.body_padding || {};
  const style = {
    "--pd-ads-fs": `${Number(st.text_size) || 1.286}em`,
    "--pd-ads-ls": st.letter_spacing ? `${st.letter_spacing}px` : "-.01em",
    "--pd-ads-bg": st.card_background || "transparent",
    "--pd-ads-color": st.text_color || "#333e48",
    "--pd-ads-pt": `${pad.top ?? 3.286}em`, "--pd-ads-pb": `${pad.bottom ?? 2.143}em`,
    "--pd-ads-gap-m": `${Number(st.gap_mobile ?? 20)}px`,
    ...(st.arrow_color ? { "--pd-ads-arrow": st.arrow_color } : {}),
  };
  const col = (i) => {
    if (v === "wide_plus_two") return i === 0 ? "col-12 col-xl-6" : "col-12 col-md-6 col-xl-3";
    return colClass(n);
  };
  return (
    <div className={`pd-ads pd-ads--${v}${cards ? " pd-ads--cards" : ""}`} data-testid="ads-block" style={style}>
      <div className="row">
        {items.map((it, i) => (
          <div className={`pd-ads__col ${col(i)}`} key={it._id || i}>
            <SmartLink link={it.link} fallback="div" className="pd-ads__ad d-block" data-testid={`ad-${i + 1}`}
              onClick={() => promo(`ad_${i + 1}`, plainText(it.text) || linkHref(it.link))}>
              {cards ? <CardAd it={it} i={i} wide={v === "wide_plus_two" && i === 0} /> : <TableAd it={it} i={i} st={st} ratio={ratio} />}
            </SmartLink>
          </div>
        ))}
      </div>
    </div>
  );
}
