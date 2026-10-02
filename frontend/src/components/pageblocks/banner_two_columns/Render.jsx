// A4 banner_two_columns — şablon v2.0 home-v3 "Banner 2 columns" (L6220) / home-v7 "Banner" (L1915):
// .row > .col-md-6 (v7: .col-lg-6) .mb-3.mb-md-0 > a > img.img-fluid (690×150).
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";

export default function Render({ settings }) {
  const st = settings;
  const items = (st.items || []).filter(Boolean).slice(0, 2);
  if (!items.length) return null;
  const bp = st.stack_below === "lg" ? "lg" : "md";
  const gap = Number(st.gap ?? 30);
  const radius = Number(st.radius) || 0;
  return (
    <div data-testid="banner-two-columns" className="pd-b2c">
      <div className="row" style={{ marginLeft: -gap / 2, marginRight: -gap / 2 }}>
        {items.map((it, i) => (
          <div key={it._id || i} className={`${items.length === 1 ? "col-12" : `col-${bp}-6`} ${i === 0 && items.length > 1 ? `mb-3 mb-${bp}-0` : ""}`}
            style={{ paddingLeft: gap / 2, paddingRight: gap / 2 }}>
            <SmartLink link={it.link} fallback="div" className="d-block overflow-hidden" style={radius ? { borderRadius: radius } : undefined}>
              <SmartImage image={it.image} size={[690, 150]} width={900} className="img-fluid w-100 d-block" alt={it.alt || ""} field={`items.${i}.image`} />
            </SmartLink>
          </div>
        ))}
      </div>
    </div>
  );
}
