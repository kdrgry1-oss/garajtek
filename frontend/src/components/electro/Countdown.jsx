// Electro "js-countdown" — jquery.countdown yerine saf React. endDate: Date | ISO | ms.
import { useEffect, useState } from "react";

function parts(end) {
  const ms = Math.max(0, new Date(end).getTime() - Date.now());
  const s = Math.floor(ms / 1000);
  return { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60, done: ms <= 0 };
}
const p2 = (n) => String(n).padStart(2, "0");

export default function Countdown({ endDate, showDays = false, compact = false }) {
  const [t, setT] = useState(() => parts(endDate));
  useEffect(() => {
    setT(parts(endDate));
    const i = setInterval(() => setT(parts(endDate)), 1000);
    return () => clearInterval(i);
  }, [endDate]);
  const hours = showDays ? t.h : t.h + t.d * 24;
  const cells = [
    ...(showDays ? [[t.d, "GÜN"]] : []),
    [hours, "SAAT"], [t.m, "DAK"], [t.s, "SN"],
  ];
  return (
    <div className="js-countdown d-flex justify-content-center" data-testid="deal-countdown" aria-live="off">
      {cells.map(([v, label], i) => (
        <div key={label} className="d-flex">
          {i > 0 && <div className="mx-1 pt-1 text-gray-2 font-size-24">:</div>}
          <div className="text-lh-1">
            <div className={`text-gray-2 ${compact ? "font-size-20" : "font-size-30"} bg-gray-4 py-2 px-2 rounded-sm mb-2`}>
              <span>{p2(v)}</span>
            </div>
            <div className="text-gray-2 font-size-12 text-center">{label}</div>
          </div>
        </div>
      ))}
    </div>
  );
}
