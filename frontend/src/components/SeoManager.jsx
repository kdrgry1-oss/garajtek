/**
 * =============================================================================
 * SeoManager.jsx — SEO yönlendirme (301/302) + meta override tüketimi
 * =============================================================================
 * DENETİM FIX (#5 + #6): Admin'de tanımlanan 301/302 yönlendirmeler ve per-path
 * meta override'ları (title/description/og_image/noindex) storefront tarafından
 * HİÇ okunmuyordu. Bu bileşen her rota değişiminde:
 *   1) GET /api/seo/resolve-redirect?path=... — found ise hedefe yönlendirir
 *      (301 → replace, 302 → assign). Yalnız admin'de tanımlı from_path'ler
 *      döndüğü için geçerli sayfalar ETKİLENMEZ.
 *   2) Gezinmede önceki sayfanın meta'sını sıfırlar (resetSeoDefaults) ve sayfa
 *      bileşeni meta'sını kendisi uygulamayan rotalarda GET /api/seo/page-meta
 *      (panel genel SEO ayarları + per-path override + noindex) uygular.
 *
 * Not: SPA client-side; gerçek 301 için public/_redirects (edge) birincildir.
 * Bu, edge kapsamayan dinamik yönlendirmeler için tamamlayıcı fallback'tir.
 * Savunmacı: uç hatası → hiçbir şey yapmaz (mağazayı asla kırmaz).
 * =============================================================================
 */
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import axios from "axios";
import { applyRuntimeSeo, resetSeoDefaults, routeOwnsSeo } from "../lib/seo";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SeoManager() {
  const location = useLocation();
  const firstRun = useRef(true);

  useEffect(() => {
    const path = location.pathname || "/";
    let cancel = false;
    const controller = new AbortController();

    // 0) SIZINTI ÖNLEME: SPA gezinmesinde önceki sayfanın title/description/canonical/
    //    robots(noindex dahil)/OG/JSON-LD değerleri sıfırlanır. İlk yüklemede DOKUNULMAZ
    //    (edge middleware ilk HTML'e o URL'in doğru meta'sını basmıştır).
    if (firstRun.current) firstRun.current = false;
    else resetSeoDefaults(path);
    // Sahipsiz rotalar (ana sayfa, /sss, /sepet, …) → sunucu page-meta (panel genel SEO
    // ayarları + per-path override + noindex) — edge ile AYNI kaynak.
    if (!routeOwnsSeo(path)) applyRuntimeSeo(path, null, { signal: controller.signal });

    // 1) Yönlendirme çözümle
    axios
      .get(`${API}/seo/resolve-redirect`, { params: { path } })
      .then((r) => {
        if (cancel || !r?.data?.found || !r.data.to) return;
        const to = r.data.to;
        // Kendine yönlendirme döngüsünü engelle
        if (to === path) return;
        if (String(r.data.status_code) === "302") {
          window.location.assign(to);
        } else {
          window.location.replace(to);
        }
      })
      .catch(() => {});

    // 2) Meta override: artık /api/seo/page-meta içinde uygulanıyor (ayrı /seo/meta çağrısı
    //    yolu bırakıldığında geri alınmadığı için override sonraki sayfalara sızıyordu).

    return () => { cancel = true; controller.abort(); };
  }, [location.pathname]);

  return null;
}
