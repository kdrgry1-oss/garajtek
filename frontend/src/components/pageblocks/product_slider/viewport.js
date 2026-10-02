// Grup C ortak yardımcıları (ürün karuselleri): görünüm genişliği, Owl tarzı per_view çözümü, "last-active" takibi
// ve boş durum notu. BlockCarousel'in CSS kırılımlarıyla (0/576/768/992/1200/1480) birebir aynı eşlemeyi kullanır.
import { useCallback, useEffect, useState } from "react";

const BPS = [0, 576, 768, 992, 1200, 1480];

/** Genişliğin düştüğü Bootstrap kırılımı (BlockCarousel.perViewVars ile aynı). */
export function bpOf(w) {
  let b = 0;
  BPS.forEach((x) => { if (w >= x) b = x; });
  return b;
}

/** {"0":1,"480":2,…} (min-width) → verilen genişlikte görünen adet. */
export function perViewAt(pv, w) {
  const at = bpOf(w);
  const keys = Object.keys(pv || {}).map(Number).filter((n) => !Number.isNaN(n)).sort((a, b) => a - b);
  let v = 1;
  keys.forEach((k) => { if (k <= at) v = Number(pv[String(k)]) || v; });
  return Math.max(1, v);
}

/** Pencere genişliği (yeniden boyutlandırmada güncellenir). */
export function useViewportWidth() {
  const get = () => (typeof window !== "undefined" ? window.innerWidth || 1200 : 1200);
  const [w, setW] = useState(get);
  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    let raf = 0;
    const on = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => setW(get())); };
    window.addEventListener("resize", on);
    return () => { window.removeEventListener("resize", on); cancelAnimationFrame(raf); };
  }, []);
  return w;
}

/**
 * Şablondaki `.owl-item.last-active`: görünen son kartın sağ ayırıcısı gizlenir. Seçili kaydırma noktası ×
 * kaydırma adımı + görünen adet − 1 = son görünen indeks. `onSelect` BlockCarousel'e verilir.
 */
export function useLastActive(carousel, total) {
  const w = useViewportWidth();
  const n = perViewAt(carousel?.per_view || { 0: 1 }, w);
  const step = Math.max(1, Number(carousel?.slides_to_scroll) || 1);
  const [snap, setSnap] = useState(0);
  const onSelect = useCallback((i) => setSnap(i), []);
  const last = Math.min(total - 1, snap * step + n - 1);
  return { onSelect, last: carousel?.last_active_divider ? last : -1, perView: n };
}

/** Önizlemede (yalnız) "bu kaynakta ürün yok" notu; vitrinde blok hiç çizilmez. */
export function EmptyNote({ preview, text }) {
  if (!preview) return null;
  return <div className="pd-stub" data-pd-placeholder="" data-testid="pc-empty">{text}</div>;
}

/** Ürün listesi yüklenirken şablon yüksekliğinde iskelet. */
export function Skeleton({ height = 260, count = 1 }) {
  return (
    <div className="d-flex" aria-hidden="true" data-testid="pc-skeleton">
      {Array.from({ length: count }).map((_, i) => <div key={i} className="el-skel flex-grow-1 mx-1" style={{ height }} />)}
    </div>
  );
}
