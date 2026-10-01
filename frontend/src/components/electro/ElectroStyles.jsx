// Electro tema CSS'inin (public/electro/electro.css) yalnız VİTRİN rotalarında etkin olmasını sağlar.
// İlk yüklemede index.html (admin dışı yollarda) <link id="electro-css"> ekler; SPA içinde
// /admin'e geçilince devre dışı bırakılır, vitrine dönülünce (veya admin'den başlanmışsa) eklenir.
// Kurallar ayrıca `.electro` kapsamına alındığından admin (Tailwind) hiçbir koşulda etkilenmez.
import { useLayoutEffect } from "react";
import { useLocation } from "react-router-dom";

// Open Sans artık tema CSS'inde kendi sunucumuzdan (public/electro/fonts) yüklenir.
// ?v= içerik özeti (craco.config.js) → tema değişince önbellek kırılır.
const LINKS = [
  ["electro-css", `/electro/electro.css?v=${process.env.REACT_APP_ELECTRO_CSS_VER || "1"}`],
];

export default function ElectroStyles() {
  const { pathname } = useLocation();
  const isAdmin = (pathname || "").startsWith("/admin");
  useLayoutEffect(() => {
    LINKS.forEach(([id, href]) => {
      let el = document.getElementById(id);
      if (isAdmin) { if (el) el.disabled = true; return; }
      if (!el) {
        el = document.createElement("link");
        el.id = id; el.rel = "stylesheet"; el.href = href;
        document.head.appendChild(el);
      }
      el.disabled = false;
    });
  }, [isAdmin]);
  return null;
}
