// Electro fiyat filtresi (ion-rangeslider görünümü) — iki tutamaçlı saf React kaydırıcı.
import { useRef } from "react";

export default function RangeSlider({ min = 0, max = 100, step = 1, value, onChange }) {
  const [lo, hi] = value;
  const track = useRef(null);
  const pct = (v) => (max > min ? ((v - min) / (max - min)) * 100 : 0);
  const fromClientX = (x) => {
    const r = track.current.getBoundingClientRect();
    const raw = min + ((x - r.left) / r.width) * (max - min);
    return Math.round(Math.min(max, Math.max(min, raw)) / step) * step;
  };
  const drag = (which) => (e) => {
    e.preventDefault();
    const move = (ev) => {
      const pt = ev.touches ? ev.touches[0] : ev;
      const v = fromClientX(pt.clientX);
      if (which === 0) onChange([Math.min(v, hi), hi]); else onChange([lo, Math.max(v, lo)]);
    };
    const up = () => {
      window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up);
      window.removeEventListener("touchmove", move); window.removeEventListener("touchend", up);
    };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
    window.addEventListener("touchmove", move, { passive: false }); window.addEventListener("touchend", up);
  };
  const key = (which) => (e) => {
    const d = e.key === "ArrowRight" || e.key === "ArrowUp" ? step : e.key === "ArrowLeft" || e.key === "ArrowDown" ? -step : 0;
    if (!d) return;
    e.preventDefault();
    if (which === 0) onChange([Math.max(min, Math.min(lo + d, hi)), hi]);
    else onChange([lo, Math.min(max, Math.max(hi + d, lo))]);
  };
  return (
    <div className="el-range" data-testid="price-range">
      <div className="el-range__track" ref={track}>
        <div className="el-range__bar" style={{ left: `${pct(lo)}%`, width: `${pct(hi) - pct(lo)}%` }} />
        <span className="el-range__handle" style={{ left: `${pct(lo)}%` }} role="slider" tabIndex={0} aria-label="En düşük fiyat"
          aria-valuemin={min} aria-valuemax={max} aria-valuenow={lo} onMouseDown={drag(0)} onTouchStart={drag(0)} onKeyDown={key(0)} />
        <span className="el-range__handle" style={{ left: `${pct(hi)}%` }} role="slider" tabIndex={0} aria-label="En yüksek fiyat"
          aria-valuemin={min} aria-valuemax={max} aria-valuenow={hi} onMouseDown={drag(1)} onTouchStart={drag(1)} onKeyDown={key(1)} />
      </div>
    </div>
  );
}
