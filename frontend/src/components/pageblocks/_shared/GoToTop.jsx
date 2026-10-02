// "Yukarı çık" düğmesi (site_theme.go_to_top).
import { useEffect, useState } from "react";
import { useSiteDesign } from "../../../lib/siteDesign";

export default function GoToTop() {
  const g = useSiteDesign().site_theme?.go_to_top || {};
  const [show, setShow] = useState(false);
  useEffect(() => {
    if (!g.enabled) return undefined;
    const on = () => setShow(window.scrollY > (Number(g.offset) || 400));
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, [g.enabled, g.offset]);
  if (!g.enabled || !show) return null;
  return (
    <button type="button" className={`pd-gotop${g.position === "bottom-left" ? " pd-gotop--left" : ""}`} aria-label="Sayfanın başına dön"
      onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} data-testid="go-to-top">
      <i className="fas fa-arrow-up" />
    </button>
  );
}
