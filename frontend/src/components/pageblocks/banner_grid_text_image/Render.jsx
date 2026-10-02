// A5 banner_grid_text_image — şablon v2.0 home-v5 "Banners" (L6819) / home-v7 (L3856): her satırda .col-lg-8 geniş
// metinli banner (bg-gray-17 / bg-gray-1; h2.font-size-28 başlık, p açıklama, özellik listesi, "from $399" fiyat,
// 446×262 görsel) + .col-md-6.col-lg-4 küçük görsel banner. Geniş banner sağdaysa görsel solda (şablon 2. satır).
import { Fragment } from "react";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import RichText from "../_shared/RichText";
import { plainText } from "../_shared/schema";
import "./bgti.css";

/** Şablondaki gibi baştaki para birimi üst simge: "₺4.990" → <sup>₺</sup>4.990 */
function Price({ v }) {
  const m = String(v).match(/^(\D+?)\s*(\d.*)$/);
  return m ? <><sup>{m[1]}</sup>{m[2]}</> : <>{v}</>;
}

function Wide({ w, f, side, st }) {
  const specs = String(w.specs || "").split("|").map((x) => x.trim()).filter(Boolean);
  const text = (
    <div className={side === "left" ? "col-md-6" : "col-md-6 mb-4 mb-md-0"}>
      <div className={side === "left" ? "ml-md-7 mt-6 mt-md-0 ml-4" : "ml-4 ml-md-0 ml-wd-4"} style={{ color: w.text_color || undefined }}>
        {plainText(w.title) && <RichText as="h2" html={w.title} field={`${f}.title`} className={`${side === "left" ? "max-width-270 " : ""}text-lh-1dot2 pd-bgti__title`} style={{ color: "inherit" }} />}
        {w.text && <p className="font-size-18 font-size-14-lg font-weight-light" style={{ color: "inherit" }} data-pd-field={`${f}.text`}>{w.text}</p>}
        {specs.length > 0 && (
          <ul className="list-unstyled d-flex flex-wrap u-header__navbar-nav-divider" data-pd-field={`${f}.specs`}>
            {specs.map((x, k) => <li key={k} className="u-header__nav-item"><span className={k === 0 ? "mr-1" : "mx-1"}>{x}</span></li>)}
          </ul>
        )}
        {(w.price || w.price_prefix) && (
          <div className="text-lh-28">
            {w.price_prefix && <span className="font-size-18 font-size-14-lg font-weight-light mr-1" data-pd-field={`${f}.price_prefix`}>{w.price_prefix}</span>}
            {w.price && <span className="font-weight-semi-bold pd-bgti__price" data-pd-field={`${f}.price`}><Price v={w.price} /></span>}
          </div>
        )}
      </div>
    </div>
  );
  const img = (
    <div className={side === "left" ? "col-md-6" : "col-md-6 mb-4 mb-md-0"}>
      <SmartImage image={w.image} size={[446, 262]} width={600} className="img-fluid" field={`${f}.image`} />
    </div>
  );
  return (
    <div className="col-lg-8 mb-5">
      <div style={{ backgroundColor: w.background || undefined }}>
        <SmartLink link={w.link} fallback="div" className="row align-items-center text-gray-90 pd-bgti__wide">
          {side === "left" ? <>{text}{img}</> : <>{img}{text}</>}
        </SmartLink>
      </div>
    </div>
  );
}

function Small({ s, f }) {
  return (
    <div className="col-md-6 col-lg-4 mb-5">
      <div className="h-100">
        <SmartLink link={s.link} fallback="div" className="d-block">
          <SmartImage image={s.image} size={[446, 262]} width={600} className="img-fluid" alt={s.alt || ""} field={`${f}.image`} />
        </SmartLink>
      </div>
    </div>
  );
}

export default function Render({ settings }) {
  const st = settings;
  const rows = (st.rows || []).filter(Boolean).slice(0, 3);
  if (!rows.length) return null;
  return (
    <div data-testid="banner-grid-text-image" className="pd-bgti" style={{ "--pd-bgti-ts": `${Number(st.title_size) || 28}px`, "--pd-bgti-ps": `${Number(st.price_size) || 46}px` }}>
      <div className="row">
        {rows.map((r, i) => {
          const side = r.wide_side === "right" ? "right" : "left";
          const wide = <Wide key="w" w={r.wide || {}} f={`rows.${i}.wide`} side={side} st={st} />;
          const small = <Small key="s" s={r.small || {}} f={`rows.${i}.small`} />;
          return <Fragment key={r._id || i}>{side === "left" ? <>{wide}{small}</> : <>{small}{wide}</>}</Fragment>;
        })}
      </div>
    </div>
  );
}
