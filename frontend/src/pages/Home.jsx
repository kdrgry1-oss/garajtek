// Ana sayfa — Sayfa Tasarımı'nda YAYINDAKİ düzen (/api/page-blocks?page=home) blok kayıt defteriyle
// (components/pageblocks/registry) çizilir. Her blok kendi klasöründeki Render.jsx'tir; panel formu ve
// backend doğrulaması aynı schema.json'u kullanır. Varsayılan düzen şablon v1.0 home.html sırasıdır
// (registry.defaultHome — defaults.json'lardan üretilir). Önizleme: pages/PagePreview.jsx (aynı renderer).
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import Header from "../components/Header";
import RotatingText from "../components/RotatingText";
import Footer from "../components/Footer";
import PageRenderer, { hasProductColumns, prepareBlocks } from "../components/pageblocks/_shared/PageRenderer";
import { PageCtx } from "../components/pageblocks/_shared/PageCtx";
import { defaultHome, TOP_BAR_TYPES, withDefaults } from "../components/pageblocks/registry";
import { useSiteDesign } from "../lib/siteDesign";
import { SITE_NAME } from "../lib/brand";
import "../components/pageblocks/_shared/pageblocks.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LS = "home_layout_v2";

function readCache() {
  try { const d = JSON.parse(localStorage.getItem(LS) || "null"); return Array.isArray(d) ? d : null; } catch { return null; }
}

function HomeSkeleton() {
  return (
    <div data-testid="home-skeleton">
      <div className="bg-gray-1 mb-5 el-hero-v1"><div className="el-hero-v1__row" /></div>
      <div className="container">
        <div className="row mb-5">{[0, 1, 2].map((i) => <div key={i} className="col-md-4 mb-4"><div className="el-skel" style={{ height: 132 }} /></div>)}</div>
        <div className="row mb-5">{[0, 1, 2, 3].map((i) => <div key={i} className="col-6 col-md-3 mb-4"><div className="el-skel" style={{ height: 320 }} /></div>)}</div>
      </div>
    </div>
  );
}

/** Üst bar blokları (dönen yazı + geri sayım): Header'a verilir; sıraları panelden. */
export function topBarsOf(blocks) {
  const act = (blocks || []).filter((b) => b && b.is_active !== false);
  const rotating = act.find((b) => b.type === "rotating_text") || null;
  const countdown = act.find((b) => b.type === "countdown_bar") || null;
  const rIdx = rotating ? blocks.indexOf(rotating) : -1;
  const cIdx = countdown ? blocks.indexOf(countdown) : -1;
  const pos = rotating ? withDefaults("rotating_text", rotating.settings).position : "above_topbar";
  return { rotating, countdown, announcementFirst: !!(rotating && countdown) && rIdx < cIdx, position: pos };
}

/** Header + akış + Footer — vitrin ve önizleme aynı kabuğu kullanır. */
export function HomeShell({ blocks, loading, ctx, isMember = false }) {
  const sd = useSiteDesign();
  const bars = topBarsOf(blocks || []);
  const hideWidgets = useMemo(() => hasProductColumns(blocks || []), [blocks]);
  // İlk görünür akış bloğu bir hero mu? (dikey menü yalnız o zaman slider'ın üstünde açık başlar)
  const heroFirst = useMemo(() => {
    if (loading) return true;
    const first = prepareBlocks(blocks || [], { isMember }).find((p) => !TOP_BAR_TYPES.has(p.block.type));
    return !first || ["hero_slider", "hero_tabs"].includes(first.block.type);
  }, [blocks, loading, isMember]);
  return (
    <div className="sf-page" data-testid="home-page">
      <Header announcement={bars.rotating ? <RotatingText block={bars.rotating} /> : null} announcementFirst={bars.announcementFirst} announcementPosition={bars.position} heroFirst={heroFirst} />
      <main id="content" role="main" className="electro el-page">
        <h1 className="sr-only">{SITE_NAME} — Oto Servis ve Garaj Ekipmanları</h1>
        <PageCtx.Provider value={ctx}>
          {loading ? <HomeSkeleton /> : <PageRenderer blocks={blocks} isMember={isMember} layout={sd.site_page_layout?.home_layout === "left_sidebar" ? "left_sidebar" : "full"} revealDefault={sd.site_theme?.reveal_default !== false} />}
        </PageCtx.Provider>
      </main>
      <Footer hideWidgets={hideWidgets} />
    </div>
  );
}

const STORE_CTX = { preview: false, page: "home", selectedId: null };

export default function Home() {
  const [blocks, setBlocks] = useState(readCache);
  const [loading, setLoading] = useState(() => !readCache());
  const [member] = useState(() => { try { return !!localStorage.getItem("token"); } catch { return false; } });

  useEffect(() => {
    // ?pd-noanim=1 → giriş animasyonları kapalı (ekran görüntüsü / piksel karşılaştırma testleri)
    try { if (/[?&]pd-noanim=1/.test(window.location.search)) document.documentElement.classList.add("pd-no-anim"); } catch { /* yoksay */ }
    let alive = true;
    axios.get(`${API}/page-blocks?page=home`)
      .then((r) => {
        if (!alive) return;
        const list = Array.isArray(r.data) ? r.data : null;
        // Yayında hiç blok yoksa (yeni kurulum / API hatası) şablon varsayılan düzeni
        const flow = list && list.length ? list : defaultHome();
        setBlocks(flow);
        try { if (list) localStorage.setItem(LS, JSON.stringify(list)); } catch { /* yoksay */ }
      })
      .catch(() => { if (alive && !blocks) setBlocks(defaultHome()); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return <HomeShell blocks={blocks || []} loading={loading && !blocks} ctx={STORE_CTX} isMember={member} />;
}
