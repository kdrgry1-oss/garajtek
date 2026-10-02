// A14 rotating_text — üst bar bloğu: sayfa akışında değil Header'da (tüm sayfalarda) çizilir.
// Bu Render galeri/izole önizleme ve testler içindir.
import RotatingText from "../../RotatingText";

export default function Render({ block, settings }) {
  return <RotatingText block={{ ...block, settings }} />;
}
