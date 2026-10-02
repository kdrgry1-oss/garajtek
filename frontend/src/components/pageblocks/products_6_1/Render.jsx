// GRUP B ajanı dolduracak (SPEC §3). Şimdilik nötr yer tutucu: vitrinde hiçbir şey çizmez,
// Sayfa Tasarımı önizlemesinde blok adını ve "hazırlanıyor" notunu gösterir.
// Props: { block, settings, ctx } — settings varsayılanlarla doldurulmuş + zamanlaması süzülmüş gelir.
import StubBlock from "../_shared/StubBlock";

export default function Render(props) {
  return <StubBlock {...props} />;
}
