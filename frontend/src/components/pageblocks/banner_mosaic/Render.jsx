// A6 banner_mosaic — şablon v2.0 home-v9 "Banner Section" (L2146): .col-lg-5.col-xl-4gdot9 büyük (552×325) +
// .col-lg-7.col-xl-7gdot1 içinde .row.mx-lg-n2 > 6× .col-md-4.px-md-2 küçük (268×155); a.borders-radius-10.overflow-hidden.
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";

export default function Render({ settings }) {
  const st = settings;
  const big = st.big || {};
  const small = (st.small || []).filter(Boolean).slice(0, 6);
  const r = Number(st.radius ?? 10);
  const rs = { borderRadius: r };
  const sc = st.small_columns === "2" ? "col-6" : "col-md-4";
  return (
    <div data-testid="banner-mosaic" className="pd-mosaic">
      <div className="row">
        <div className={small.length ? "col-lg-5 col-xl-4gdot9 mb-3" : "col-12 mb-3"}>
          <SmartLink link={big.link} fallback="div" className="d-block overflow-hidden" style={rs}>
            <SmartImage image={big.image} size={[552, 325]} width={900} className="img-fluid w-100 d-block" alt={big.alt || ""} field="big.image" />
          </SmartLink>
        </div>
        {small.length > 0 && (
          <div className="col-lg-7 col-xl-7gdot1 pl-lg-0">
            <div className="row mx-n2 mx-lg-n2">
              {small.map((it, i) => (
                <div key={it._id || i} className={`${sc} mb-3 px-2`}>
                  <SmartLink link={it.link} fallback="div" className="d-block overflow-hidden" style={rs}>
                    <SmartImage image={it.image} size={[268, 155]} width={500} className="img-fluid w-100 d-block" alt={it.alt || ""} field={`small.${i}.image`} />
                  </SmartLink>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
