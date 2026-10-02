import React, { useEffect, useState } from "react";
import SmartLink from "./pageblocks/_shared/SmartLink";
import { barAllowed, barVisClass } from "./pageblocks/_shared/topBars";

// Üst duyuru barı (Sayfa Tasarımı'ndaki "rotating_text" bloğu). Mesaj/bağlantı/renk/süre panelden gelir.
// Ana sayfa ve Header (diğer tüm sayfalar) aynı bileşeni kullanır. v2 şema: settings.messages[{text, link}],
// interval (ms), background, text_color. (Eski texts/interval sn/bg_color okunabilir — geri uyum.)
function messagesOf(st) {
  if (Array.isArray(st?.messages)) return st.messages.filter((m) => m && !m._hidden && String(m.text || "").trim());
  return (st?.texts || []).filter((t) => (t || "").trim()).map((t) => ({ text: t }));
}

export default function RotatingText({ block }) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const st = block?.settings || {};
  const msgs = messagesOf(st);
  const ms = Array.isArray(st.messages) ? Number(st.interval) || 4000 : Math.max(2, Number(st.interval) || 4) * 1000;

  useEffect(() => {
    if (msgs.length < 2) return undefined;
    const interval = setInterval(() => setCurrentIndex((prev) => (prev + 1) % msgs.length), Math.max(1500, ms));
    return () => clearInterval(interval);
  }, [msgs.length, ms]);

  if (msgs.length === 0 || !barAllowed(block)) return null;
  const bg = st.background || st.bg_color || "#ffffff";
  const fg = st.text_color || "#374151";
  const i = currentIndex % msgs.length;
  const m = msgs[i];

  return (
    <div className={`text-center py-1 ${barVisClass(block)}`} style={{ backgroundColor: bg }} data-testid="rotating-text">
      <SmartLink link={m.link} key={currentIndex} className="text-[10px] md:text-[12px] uppercase" field={`messages.${i}.text`}
        style={{ color: fg, fontWeight: 500, letterSpacing: "0.12em" }}>
        {m.text}
      </SmartLink>
    </div>
  );
}
