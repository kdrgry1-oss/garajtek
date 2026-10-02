// Şema `image` değeri → <picture> (mobil kaynak, odak noktası → object-position, lazy) veya video.
// Görsel yoksa şablon ölçüsünde yer tutucu.
import { optimizeImg } from "../../../lib/img";
import Placeholder from "./Placeholder";

export const isVideoUrl = (u) => typeof u === "string" && /\.(mp4|webm|mov|m4v|ogg)(\?|$)/i.test(u);
const pos = (f) => (f && typeof f.x === "number" ? `${Math.round(f.x * 100)}% ${Math.round(f.y * 100)}%` : undefined);

export default function SmartImage({
  image, size, width = 1200, className = "img-fluid", style, fit, alt, field, eager = false, placeholder = true,
  phClassName = "", phFill = false, mobileWidth = 800, quality,
}) {
  const url = image && (image.url || image.mobile_url);
  if (!url) {
    return placeholder ? <Placeholder size={size || [16, 9]} className={phClassName} fill={phFill} field={field} /> : null;
  }
  const a = alt ?? (image.alt || "");
  const objStyle = { ...(fit ? { objectFit: fit, objectPosition: pos(image.focal) } : {}), ...style };
  if (isVideoUrl(image.url)) {
    return <video className={className} style={objStyle} src={image.url} muted loop playsInline autoPlay preload={eager ? "auto" : "none"} data-pd-field={field} />;
  }
  const dims = image.w && image.h ? { width: image.w, height: image.h } : {};
  return (
    <picture data-pd-field={field}>
      {image.mobile_url && (
        <source media="(max-width: 767px)" srcSet={optimizeImg(image.mobile_url, mobileWidth)} />
      )}
      <img className={className} style={{ ...objStyle, ...(image.mobile_focal && fit ? { "--pd-mobile-pos": pos(image.mobile_focal) } : {}) }}
        src={optimizeImg(image.url || image.mobile_url, width, quality)} alt={a} {...dims}
        loading={eager ? "eager" : "lazy"} decoding="async" fetchPriority={eager ? "high" : "auto"} />
    </picture>
  );
}
