// Şema `countdown` değeri → Electro "js-countdown" kutuları. Birimler, Türkçe etiketler, sıfır günü gizleme,
// süre bitince davranış (on_expire: hide_block | hide_timer | show_text | zero). `end` boşsa
// "bugün 23:59 + rolling_days gün" (sürekli yenilenen kampanya).
import { useEffect, useMemo, useState } from "react";

export function countdownEnd(cd, now = new Date()) {
  if (!cd) return null;
  if (cd.end) {
    const t = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$/.test(cd.end) ? `${cd.end.length === 16 ? `${cd.end}:00` : cd.end}+03:00` : cd.end;
    const d = new Date(t);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  const d = new Date(now);
  d.setHours(23, 59, 59, 0);
  d.setDate(d.getDate() + (Number(cd.rolling_days) || 0));
  return d;
}

function parts(end) {
  const ms = Math.max(0, (end ? end.getTime() : 0) - Date.now());
  const s = Math.floor(ms / 1000);
  return { days: Math.floor(s / 86400), hours: Math.floor((s % 86400) / 3600), minutes: Math.floor((s % 3600) / 60), seconds: s % 60, expired: ms <= 0 };
}

/** Geri sayım durumu: {parts, expired, end} — saniyede bir güncellenir. */
export function useCountdown(cd) {
  const end = useMemo(() => countdownEnd(cd), [cd?.end, cd?.rolling_days]); // eslint-disable-line react-hooks/exhaustive-deps
  const [p, setP] = useState(() => parts(end));
  useEffect(() => {
    setP(parts(end));
    if (!end) return undefined;
    const i = setInterval(() => setP(parts(end)), 1000);
    return () => clearInterval(i);
  }, [end]);
  return { ...p, end };
}

const UNITS = ["days", "hours", "minutes", "seconds"];
const pad2 = (n) => String(n).padStart(2, "0");

/** Kutu görünümü (deals). `value` = şema countdown değeri. */
export default function Countdown({ value, field = "countdown", compact = false, className = "", unitClassName, numberClassName, labelClassName, separator = true }) {
  const cd = value || {};
  const st = useCountdown(cd);
  if (!cd.enabled) return null;
  if (st.expired && cd.on_expire === "hide_timer") return null;
  if (st.expired && cd.on_expire === "hide_block") return null;
  if (st.expired && cd.on_expire === "show_text") {
    return <div className={`text-center font-size-15 ${className}`} data-pd-field={`${field}.expired_text`}>{cd.expired_text}</div>;
  }
  let units = (cd.units && cd.units.length ? cd.units : UNITS).filter((u) => UNITS.includes(u));
  if (cd.hide_zero_days && st.days === 0) units = units.filter((u) => u !== "days");
  // gün gösterilmiyorsa saatler günleri de taşır
  const val = (u) => (u === "hours" && !units.includes("days") ? st.hours + st.days * 24 : st[u]);
  const labels = cd.labels || {};
  return (
    <div className={className}>
      {cd.heading && <h6 className="font-size-15 text-gray-2 text-center mb-3" data-pd-field={`${field}.heading`}>{cd.heading}</h6>}
      <div className="js-countdown d-flex justify-content-center" data-testid="deal-countdown" aria-live="off">
        {units.map((u, i) => (
          <div key={u} className="d-flex">
            {separator && i > 0 && <div className="mx-1 pt-1 text-gray-2 font-size-24">:</div>}
            <div className={unitClassName || "text-lh-1"}>
              <div className={numberClassName || `text-gray-2 ${compact ? "font-size-20" : "font-size-30"} bg-gray-4 py-2 px-2 rounded-sm mb-2`}>
                <span>{cd.pad === false ? val(u) : pad2(val(u))}</span>
              </div>
              <div className={labelClassName || "text-gray-2 font-size-12 text-center"} data-pd-field={`${field}.labels.${u}`}>{labels[u]}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
