// A10 half_banners — eski "İki Banner" bloğu (şemaya taşındı): yan yana 2 (en fazla 4) görsel banner, 570×300.
// Görseli olmayan öğe vitrinde atlanır; Sayfa Tasarımı önizlemesinde şablon ölçüsünde yer tutucu gösterilir.
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import { usePageCtx } from "../_shared/PageCtx";

export default function Render({ settings }) {
  const ctx = usePageCtx();
  const st = settings;
  const all = (st.items || []).map((it, i) => ({ it, i })).filter((x) => x.it && (ctx.preview || x.it.image?.url));
  if (!all.length) return null;
  const gap = Number(st.gap ?? 30);
  const radius = Number(st.radius) || 0;
  return (
    <div data-testid="half-banners">
      <div className="row" style={{ marginLeft: -gap / 2, marginRight: -gap / 2 }}>
        {all.slice(0, 4).map(({ it, i }) => (
          <div className={`${all.length === 1 ? "col-12" : all.length >= 3 ? "col-md-6 col-xl-3" : "col-md-6"} mb-4`} key={it._id || i}
            style={{ paddingLeft: gap / 2, paddingRight: gap / 2 }}>
            <SmartLink link={it.link} fallback="div" className="d-block overflow-hidden" style={radius ? { borderRadius: radius } : undefined}>
              <SmartImage image={it.image} size={[570, 300]} alt={it.alt} width={900} className="img-fluid w-100 d-block" field={`items.${i}.image`} />
            </SmartLink>
          </div>
        ))}
      </div>
    </div>
  );
}
