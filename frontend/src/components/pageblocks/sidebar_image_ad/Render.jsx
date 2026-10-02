// D8 sidebar_image_ad — şablon v2.0 home-v2 kenar çubuğu “Image Banner”: aside.mb-8 > a.d-block > img.img-fluid (270×428).
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import "../sidebar_product_list/style.css";

export default function Render({ settings, ctx }) {
  const st = settings;
  const has = !!(st.image && st.image.url);
  if (!has && !(ctx && ctx.preview)) return null;
  return (
    <aside className="pd-sad" data-testid="sidebar-image-ad">
      <SmartLink link={st.link} fallback="div" className="d-block">
        <SmartImage image={st.image} size={[270, 428]} width={600} className="img-fluid" field="image" alt={st.alt} />
      </SmartLink>
    </aside>
  );
}
