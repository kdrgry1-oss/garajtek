// A10 half_banners — iki (en fazla 4) görsel banner (eski blok).
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";

export default function Render({ settings }) {
  const items = (settings.items || []).filter((x) => x && x.image);
  if (!items.length) return null;
  return (
    <div data-testid="half-banners">
      <div className="row">
        {items.slice(0, 4).map((it, i) => (
          <div className={`${items.length === 1 ? "col-12" : "col-md-6"} mb-4`} key={it._id || i}>
            <SmartLink link={it.link} fallback="div" className="d-block">
              <SmartImage image={it.image} alt={it.alt} width={900} className="img-fluid w-100" field={`items.${i}.image`} />
            </SmartLink>
          </div>
        ))}
      </div>
    </div>
  );
}
