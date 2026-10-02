// Görsel girilmemiş alan — şablon ölçüsünde nötr yer tutucu (ölçü yazısı soluk). Sayfa düzeni bozulmaz.
export const sizeText = (s) => (Array.isArray(s) ? `${s[0]} × ${s[1]}` : "");

export default function Placeholder({ size = [16, 9], className = "", style, label, fill = false, field }) {
  return (
    <div className={`el-ph${fill ? " el-ph--fill" : ""} ${className}`} style={fill ? style : { aspectRatio: `${size[0]} / ${size[1]}`, ...style }}
      aria-hidden="true" data-pd-field={field} data-pd-placeholder="">
      <span className="el-ph__size">{label || sizeText(size)}</span>
    </div>
  );
}
