// AdminApp.jsx — Tüm admin paneli burada. App.js bunu React.lazy ile
// ayrı bir chunk olarak yükler; böylece mağaza (storefront) ziyaretçileri
// ~75 admin sayfasını ve ağır kütüphaneleri (recharts, xlsx vb.) İNDİRMEZ.
import { Routes, Route, Navigate } from "react-router-dom";

import AdminLayout from "./pages/admin/AdminLayout";
import AdminDashboard from "./pages/admin/Dashboard";
import AdminProducts from "./pages/admin/Products";
import ProductSets from "./pages/admin/ProductSets";
import AdminOrders from "./pages/admin/Orders";
import AdminCategories from "./pages/admin/Categories";
import AdminVariants from "./pages/admin/Variants";
import AdminBanners from "./pages/admin/Banners";
import SettingsWorkspace from "./pages/admin/SettingsWorkspace";
import AdminCampaigns from "./pages/admin/Campaigns";
import AdminPages from "./pages/admin/Pages";
import AdminPageDesign from "./pages/admin/PageDesign";
import AdminCategoryOrder from "./pages/admin/CategoryOrder";
import AdminMenu from "./pages/admin/MenuAdmin";
import EmailMarketing from "./pages/admin/EmailMarketing";
import AdminIntegrations from "./pages/admin/Integrations";
import Payments from "./pages/admin/Payments";
import BirFatura from "./pages/admin/BirFatura";
import AdminLogin from "./pages/admin/AdminLogin";
import AdminReturns from "./pages/admin/Returns";
import AdminCancellations from "./pages/admin/Cancellations";
import DeletedOrders from "./pages/admin/DeletedOrders";
import ProductAttributes from "./pages/admin/ProductAttributes";
import Members from "./pages/admin/Members";
import Consents from "./pages/admin/Consents";
import Attribution from "./pages/admin/Attribution";
import Coupons from "./pages/admin/Coupons";
import GiftCards from "./pages/admin/GiftCards";
import ProductReviews from "./pages/admin/ProductReviews";
import AbandonedCarts from "./pages/admin/AbandonedCarts";
import { SalesReport, ProductsReport, StockReport, MembersReport } from "./pages/admin/Reports";
import { SeoRedirects, SeoMeta } from "./pages/admin/SeoAdmin";
import {
  Brands, ProductTags, Announcements, Popups,
  StockAlerts, HavaleNotifications, Tickets, ShippingPaymentRules,
  ExtraReports,
} from "./pages/admin/CatalogExtras";
import TrainingPanel from "./pages/admin/TrainingPanel";
import BlockedCustomers from "./pages/admin/BlockedCustomers";
import PaymentTrace from "./pages/admin/PaymentTrace";
import ReportsAdvanced from "./pages/admin/ReportsAdvanced";
import ReportsInsights from "./pages/admin/ReportsInsights";
import XmlFeeds from "./pages/admin/XmlFeeds";
import BulkPriceStock from "./pages/admin/BulkPriceStock";
import StockAlerts2 from "./pages/admin/StockAlerts";
import CustomerSegments from "./pages/admin/CustomerSegments";
import AutomationStatus from "./pages/admin/AutomationStatus";
import SecurityDashboard from "./pages/admin/SecurityDashboard";
import SystemHealth from "./pages/admin/SystemHealth";
import SecretsVault from "./pages/admin/SecretsVault";
import MailServer from "./pages/admin/MailServer";
import IysAdmin from "./pages/admin/IysAdmin";
import ReportsExtended from "./pages/admin/ReportsExtended";
import ActivityHistory from "./pages/admin/ActivityHistory";

// Bu Routes, App.js'te "/admin/*" altına mount edilir; bu yüzden yollar
// /admin'e göreceli yazılır (örn. "urunler" => /admin/urunler).
export default function AdminApp() {
  return (
    <Routes>
      <Route path="login" element={<AdminLogin />} />
      <Route element={<AdminLayout />}>
        <Route index element={<AdminDashboard />} />
        <Route path="urunler" element={<AdminProducts />} />
        <Route path="urunler/:productId" element={<AdminProducts />} />
        <Route path="urun-setleri" element={<ProductSets />} />
        <Route path="siparisler" element={<AdminOrders key="orders-all" />} />
        <Route path="odeme-bekleyen-siparisler" element={<AdminOrders key="orders-unpaid" unpaidView />} />
        <Route path="kategoriler" element={<AdminCategories />} />
        <Route path="kategori-siralama" element={<AdminCategoryOrder />} />
        <Route path="varyantlar" element={<AdminVariants />} />
        <Route path="xml-feedler" element={<XmlFeeds />} />
        <Route path="sayfa-tasarimi" element={<AdminPageDesign />} />
        {/* Footer artık Sayfa Tasarımı › Genel Alanlar'da (SPEC §4.7) */}
        <Route path="footer-tasarim" element={<Navigate to="/admin/sayfa-tasarimi?alan=site_footer_links" replace />} />
        <Route path="menu-yonetimi" element={<AdminMenu />} />
        <Route path="eposta-pazarlama" element={<EmailMarketing />} />
        <Route path="bannerlar" element={<AdminBanners />} />
        <Route path="kampanyalar" element={<AdminCampaigns />} />
        <Route path="entegrasyonlar" element={<AdminIntegrations />} />
        <Route path="odeme-tipleri" element={<Payments />} />
        <Route path="birfatura" element={<BirFatura />} />
        <Route path="iadeler" element={<AdminReturns />} />
        <Route path="iptaller" element={<AdminCancellations />} />
        <Route path="silinen-siparisler" element={<DeletedOrders />} />
        <Route path="iade-edilenler" element={<Navigate to="/admin/iadeler" replace />} />
        <Route path="sayfalar" element={<AdminPages />} />
        <Route path="ayarlar" element={<SettingsWorkspace />} />
        <Route path="ayarlar/isletme-kurallari" element={<Navigate to="/admin/ayarlar?tab=business-rules" replace />} />
        <Route path="egitim" element={<TrainingPanel />} />
        <Route path="ayarlar/menu-duzeni" element={<Navigate to="/admin/ayarlar?tab=menu-layout" replace />} />
        <Route path="ayarlar/kargo" element={<Navigate to="/admin/ayarlar?tab=cargo" replace />} />
        <Route path="ayarlar/gonderici-adresi" element={<Navigate to="/admin/ayarlar?tab=sender-address" replace />} />
        <Route path="ayarlar/bildirim" element={<Navigate to="/admin/ayarlar?tab=notifications" replace />} />
        <Route path="ayarlar/eposta" element={<Navigate to="/admin/ayarlar?tab=email" replace />} />
        <Route path="ayarlar/bildirim/sablonlar" element={<Navigate to="/admin/ayarlar?tab=notification-templates" replace />} />
        <Route path="bloklu-musteriler" element={<BlockedCustomers />} />
        <Route path="ayarlar/pixel" element={<Navigate to="/admin/ayarlar?tab=pixels" replace />} />
        <Route path="ayarlar/capi-loglar" element={<Navigate to="/admin/ayarlar?tab=capi" replace />} />
        <Route path="odeme-izi" element={<PaymentTrace />} />
        <Route path="raporlar/iade-ve-trend" element={<Navigate to="/admin/raporlar/urun" replace />} />
        <Route path="raporlar/konum-kanal" element={<Navigate to="/admin/raporlar/satis" replace />} />
        <Route path="ayarlar/sosyal-giris" element={<Navigate to="/admin/ayarlar?tab=social-login" replace />} />
        <Route path="ayarlar/siparis-durumlari" element={<Navigate to="/admin/ayarlar?tab=order-statuses" replace />} />
        <Route path="toplu-fiyat-stok" element={<BulkPriceStock />} />
        <Route path="stok-uyarilari" element={<StockAlerts2 />} />
        <Route path="musteri-segmentleri" element={<CustomerSegments />} />
        <Route path="otomasyon" element={<AutomationStatus />} />
        <Route path="guvenlik-paneli" element={<SecurityDashboard />} />
        <Route path="islem-gecmisi" element={<ActivityHistory />} />
        <Route path="sistem-sagligi" element={<SystemHealth />} />
        <Route path="secrets-vault" element={<SecretsVault />} />
        <Route path="mail-yonetimi" element={<MailServer />} />
        <Route path="iys" element={<IysAdmin />} />
        <Route path="urun-ozellikleri" element={<ProductAttributes />} />
        <Route path="cariler" element={<Navigate to="/admin/ayarlar?tab=vendors" replace />} />
        <Route path="kullanicilar" element={<Navigate to="/admin/ayarlar?tab=users-roles" replace />} />
        <Route path="uyeler" element={<Members />} />
        <Route path="izinler" element={<Consents />} />
        <Route path="kaynak" element={<Attribution />} />
        <Route path="kuponlar" element={<Coupons />} />
        <Route path="hediye-cekleri" element={<GiftCards />} />
        <Route path="yorumlar" element={<ProductReviews />} />
        <Route path="terkedilmis-sepet" element={<AbandonedCarts />} />
        <Route path="raporlar/karar-kurulu" element={<Navigate to="/admin/raporlar/urun" replace />} />
        <Route path="raporlar/satis" element={<SalesReport />} />
        <Route path="raporlar/urun" element={<ProductsReport />} />
        <Route path="raporlar/stok" element={<StockReport />} />
        <Route path="raporlar/uye" element={<MembersReport />} />
        <Route path="seo/meta" element={<SeoMeta />} />
        <Route path="seo/yonlendirmeler" element={<SeoRedirects />} />
        <Route path="markalar" element={<Brands />} />
        <Route path="etiketler" element={<ProductTags />} />
        <Route path="duyurular" element={<Announcements />} />
        <Route path="popuplar" element={<Popups />} />
        <Route path="stok-alarm" element={<StockAlerts />} />
        <Route path="havale-bildirimleri" element={<HavaleNotifications />} />
        <Route path="tickets" element={<Tickets />} />
        <Route path="kargo-odeme-kurallari" element={<ShippingPaymentRules />} />
        <Route path="doviz" element={<Navigate to="/admin/ayarlar?tab=currency" replace />} />
        <Route path="toplu-mail" element={<Navigate to="/admin/eposta-pazarlama" replace />} />
        <Route path="raporlar/gelismis" element={<Navigate to="/admin/raporlar/satis" replace />} />
        <Route path="raporlar/kar-stok" element={<ReportsExtended />} />
      </Route>
    </Routes>
  );
}
