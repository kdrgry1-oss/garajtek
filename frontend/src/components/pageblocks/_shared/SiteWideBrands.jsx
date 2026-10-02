// Marka şeridi diğer sayfalarda: ana sayfadaki "Marka Logoları Karuseli" bloğunda "Tüm sayfalarda footer üstünde
// göster" açıksa, şablondaki gibi her sayfanın altında (footer üstü) aynı ayarlarla çizilir. Ana sayfada blok zaten akıştadır.
import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { fetchTopBars, getCachedBars } from "../../../lib/headerMenu";
import { usePreviewState } from "../../../lib/pagePreview";
import { getBlock, withDefaults } from "../registry";
import BlockFrame from "./BlockFrame";
import { barAllowed } from "./topBars";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SiteWideBrands() {
  const loc = useLocation();
  const pv = usePreviewState();
  const [block, setBlock] = useState(() => getCachedBars()?.brands || null);
  useEffect(() => {
    let alive = true;
    fetchTopBars(API).then((b) => { if (alive) setBlock(b?.brands || null); }).catch(() => {});
    return () => { alive = false; };
  }, []);
  if (pv.active || loc.pathname === "/" || !block || !barAllowed(block)) return null;
  const entry = getBlock("brands_carousel");
  if (!entry || !entry.Render) return null;
  const { Render, schema } = entry;
  const st = withDefaults("brands_carousel", block.settings);
  return (
    <div className="electro" data-testid="sitewide-brands">
      <BlockFrame block={block} schema={schema} settings={st} index={0} revealDefault={false}>
        <Render block={block} settings={st} schema={schema} ctx={{ preview: false, page: "*" }} />
      </BlockFrame>
    </div>
  );
}
