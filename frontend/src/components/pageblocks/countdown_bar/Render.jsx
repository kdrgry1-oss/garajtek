// A15 countdown_bar — üst bar bloğu: sayfa akışında değil Header'da (tüm sayfalarda) çizilir.
import CountdownBar from "../../CountdownBar";

export default function Render({ block, settings }) {
  return <CountdownBar block={{ ...block, settings }} />;
}
