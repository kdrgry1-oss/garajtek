import { BrowserRouter, Routes, Route, Navigate, useParams, useLocation, useNavigationType } from "react-router-dom";
import { useEffect, useLayoutEffect, useRef, lazy, Suspense } from "react";
import { Toaster } from "sonner";
import { CartProvider } from "./context/CartContext";
import { AuthProvider } from "./context/AuthContext";
import { FavoritesProvider } from "./context/FavoritesContext";
import ErrorBoundary from "./components/ErrorBoundary";

// Storefront — sadece ana sayfa (LCP) eager; gerisi route'a girilince yüklenir.
// Bu, ilk açılışta indirilen JS'i ciddi şekilde küçültür (mobil TBT/LCP/FCP iyileşir).
import Home from "./pages/Home";
const GizlilikPolitikasi = lazy(() => import("./pages/GizlilikPolitikasi"));
const Category = lazy(() => import("./pages/Category"));
const CampaignProducts = lazy(() => import("./pages/CampaignProducts"));
const ProductDetail = lazy(() => import("./pages/ProductDetail"));
const Cart = lazy(() => import("./pages/Cart"));
const Checkout = lazy(() => import("./pages/Checkout"));
const Search = lazy(() => import("./pages/Search"));
const StaticPage = lazy(() => import("./pages/StaticPage"));
const FAQ = lazy(() => import("./pages/FAQ"));
const Account = lazy(() => import("./pages/Account"));
const Login = lazy(() => import("./pages/Login"));
const ForgotPassword = lazy(() => import("./pages/ForgotPassword"));
const ResetPassword = lazy(() => import("./pages/ResetPassword"));
const TrackOrder = lazy(() => import("./pages/TrackOrder"));
const OrderSuccess = lazy(() => import("./pages/OrderSuccess"));
const PaymentNotification = lazy(() => import("./pages/PaymentNotification"));
const ReturnRequest = lazy(() => import("./pages/ReturnRequest"));
const GuestReturn = lazy(() => import("./pages/GuestReturn"));
const Wishlist = lazy(() => import("./pages/Wishlist"));
const Compare = lazy(() => import("./pages/Compare"));
const NotFound = lazy(() => import("./pages/NotFound"));

import MarketingPixelsInjector from "./components/MarketingPixelsInjector";
import SlugRouter from "./components/SlugRouter";
import MaintenanceGate from "./components/MaintenanceGate";
import CookieConsent from "./components/CookieConsent";
// DENETİM FIX (#35): admin Duyuru/Popup'larını storefront'ta gösteren bileşenler
const AnnouncementBar = lazy(() => import("./components/AnnouncementBar"));
const SitePopup = lazy(() => import("./components/SitePopup"));
// DENETİM FIX (#5/#6): 301/302 yönlendirme + per-path meta override tüketimi
const SeoManager = lazy(() => import("./components/SeoManager"));
const WhatsAppButton = lazy(() => import("./components/WhatsAppButton"));
import { trackVisit } from "./lib/attribution";

import "./App.css";
import "./storefront.css";
// Electro vitrin teması — uyum kuralları (tamamı `.electro` kapsamlı; admin etkilenmez)
import "./components/electro/electro.css";
import ElectroStyles from "./components/electro/ElectroStyles";

// Rota değişiminde sayfayı anında en üste al — 2./3. sayfaya geçişte veya yeni
// sayfa açıldığında footer'ın önce görünüp sonra yukarı zıplaması engellenir.
function ScrollToTop() {
  const { pathname } = useLocation();
  const navType = useNavigationType();  // "POP" = geri/ileri → scroll'a dokunma, tarayıcı pozisyonu restore etsin
  const prevPath = useRef(pathname);
  useEffect(() => {
    const prev = prevPath.current;
    prevPath.current = pathname;
    // Ürün düzenleme MODAL'ı aç/kapa aslında rota değiştiriyor
    // (/admin/urunler ↔ /admin/urunler/{id}). Bu, aynı liste bağlamı olduğu için
    // başa KAYDIRILMAMALI — kullanıcı listede kaldığı yerde kalsın (kullanıcı isteği).
    const _sameList = (a, b) => {
      const _u = (p) => p === "/admin/urunler" || p.startsWith("/admin/urunler/");
      return _u(a) && _u(b);
    };
    if (_sameList(prev, pathname)) return;
    // Yeni sayfa (PUSH/REPLACE) → en üste al. Geri/ileri (POP) → kullanıcının
    // kaldığı yeri koru (liste → ürün → geri: liste eski scroll'unda açılır).
    if (navType !== "POP") window.scrollTo({ top: 0, behavior: "auto" });
  }, [pathname, navType]);
  return null;
}

// Admin paneli (~75 sayfa + ağır kütüphaneler) AYRI bir chunk olarak,
// sadece /admin'e girilince yüklenir. Storefront ziyaretçileri bunu indirmez.
const AdminApp = lazy(() => import("./AdminApp"));

// Eski /siparis-tamamlandi/:orderNumber linkleri (SPA-içi navigasyon) için client redirect.
// Doğrudan URL/bot istekleri zaten public/_redirects ile gerçek 301 alır; bu, SPA fallback'tir.
function LegacyOrderRedirect() {
  const { orderNumber } = useParams();
  return <Navigate to={`/order-success/${orderNumber}`} replace />;
}

function StorefrontScope({ children }) {
  const { pathname } = useLocation();
  const isAdmin = (pathname || "").startsWith("/admin");
  const section = pathname === "/" ? "home"
    : pathname.startsWith("/kategori/") ? "category"
    : pathname.startsWith("/urun/") ? "product"
    : pathname === "/sepet" ? "cart"
    : pathname === "/odeme" ? "checkout"
    : pathname === "/hesabim" ? "account"
    : pathname === "/giris" ? "login"
    : pathname === "/favoriler" ? "wishlist"
    : pathname.startsWith("/sayfa/") || pathname === "/gizlilik" || pathname.includes("sorulan") ? "static"
    : "utility";
  // DOM'a yeni bir wrapper eklemeyerek mevcut tema/CSS child selector'larını bozma.
  // Layout effect admin'e geçişte scope'u boyamadan önce kaldırır.
  useLayoutEffect(() => {
    document.body.classList.toggle("storefront-shell", !isAdmin);
    if (!isAdmin) document.body.setAttribute("data-storefront-section", section);
    else document.body.removeAttribute("data-storefront-section");
    return () => {
      document.body.classList.remove("storefront-shell");
      document.body.removeAttribute("data-storefront-section");
    };
  }, [isAdmin, section]);
  return children;
}

// CHECKOUT (/odeme) dikkat dağıtmayan Shopify düzenindedir: kendi sade header'ını çizer;
// global duyuru barı / popup / WhatsApp butonu orada gösterilmez. (Checkout ajanı — küçük değişiklik)
function HideOnCheckout({ children }) {
  const { pathname } = useLocation();
  return pathname === "/odeme" ? null : children;
}

function App() {
  useEffect(() => {
    // UTM/referrer yakalama — render'ı bloklamaması için mount sonrası.
    if (typeof window !== "undefined" && !window.__STORE_TRACKED__) {
      window.__STORE_TRACKED__ = true;
      trackVisit();
    }
  }, []);

  return (
    <ErrorBoundary>
    <AuthProvider>
      <CartProvider>
        <FavoritesProvider>
          <BrowserRouter>
            <ScrollToTop />
            <Toaster position="top-center" richColors />
            <MarketingPixelsInjector />
            <CookieConsent />
            <StorefrontScope>
            <ElectroStyles />
            {/* Storefront Duyuru barı + Popup + SEO. Bu bileşenler güvenli (aktif
                popup/duyuru/yönlendirme yoksa hiçbir şey render etmez). */}
            <Suspense fallback={null}>
              <SeoManager />
              <HideOnCheckout>
                <AnnouncementBar />
                <SitePopup />
                <WhatsAppButton />
              </HideOnCheckout>
            </Suspense>
            <MaintenanceGate>
              <Suspense fallback={<div style={{ padding: 40, textAlign: "center", color: "#888" }}>Yükleniyor…</div>}>
                <Routes>
                <Route path="/" element={<Home />} />
                <Route path="/kategori/:slug" element={<Category />} />
                <Route path="/sepet" element={<Cart />} />
                <Route path="/odeme" element={<Checkout />} />
                <Route path="/arama" element={<Search />} />
                <Route path="/sayfa/:slug" element={<StaticPage />} />
                <Route path="/gizlilik" element={<GizlilikPolitikasi />} />
                <Route path="/sikca-sorulan-sorular" element={<FAQ />} />
                <Route path="/sss" element={<FAQ />} />
                <Route path="/hesabim" element={<Account />} />
                <Route path="/giris" element={<Login />} />
                <Route path="/sifremi-unuttum" element={<ForgotPassword />} />
                <Route path="/sifre-sifirla" element={<ResetPassword />} />
                <Route path="/siparis-takip" element={<TrackOrder />} />
                <Route path="/siparis-takip/:trackingCode" element={<TrackOrder />} />
                <Route path="/order-success/:orderNumber" element={<OrderSuccess />} />
                <Route path="/siparis-tamamlandi/:orderNumber" element={<LegacyOrderRedirect />} />
                <Route path="/odeme-bildirimi/:orderNumber" element={<PaymentNotification />} />
                <Route path="/iade/:orderNumber" element={<ReturnRequest />} />
                <Route path="/iade-islemleri" element={<GuestReturn />} />
                <Route path="/favoriler" element={<Wishlist />} />
                <Route path="/karsilastir" element={<Compare />} />

                {/* Tema önizleme */}

                {/* Admin — lazy yüklenen ayrı chunk. /admin/login dahil tüm admin
                    rotaları AdminApp içindeki kendi <Routes>'unda tanımlı. */}
                <Route
                  path="/admin/*"
                  element={<AdminApp />}
                />

                {/* Ürün detay — SEO dostu kök URL. Statik rotalar dinamikten önce
                    eşleştiği için /sepet, /giris, /admin vb. her zaman önceliklidir. */}
                <Route path="/kampanya/:id" element={<CampaignProducts />} />
                <Route path="/urun/:slug" element={<ProductDetail />} />
                <Route path="/:slug" element={<SlugRouter />} />
                <Route path="*" element={<NotFound />} />
                </Routes>
              </Suspense>
            </MaintenanceGate>
            </StorefrontScope>
          </BrowserRouter>
        </FavoritesProvider>
      </CartProvider>
    </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
