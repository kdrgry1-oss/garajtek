/**
 * Admin menü tanımı — tek kaynak.
 * Her grup bir `key` ile tanımlanır; kullanıcı tercihlerinin (sıra/gizleme)
 * referans aldığı sabit anahtar budur. Etiketleri değiştirebilirsiniz, key'leri
 * DEĞİŞTİRMEYİN — aksi takdirde mevcut tercihler bozulur.
 */
import {
  LayoutDashboard, Package, ShoppingCart, Tags, Image, Megaphone, FileText, Settings, Palette, RotateCcw, Store, GitMerge, XCircle, Trash2, Cable, Shield, Users, MessageSquare, PenTool, Truck, CreditCard, AlertTriangle, TrendingUp, Link2, BellRing, Lock, Mail, Rss, GraduationCap,
} from "lucide-react";

// Default sıralama (kullanıcı tercihi yoksa kullanılır):
// Siparişler → Katalog → Raporlar → Tasarım → Üyeler →
// Pazarlama → SEO → Entegrasyonlar → Sistem → Ayarlar
export const navigationGroups = [
  {
    key: "siparisler",
    label: "Siparişler",
    icon: ShoppingCart,
    children: [
      { label: "Tüm Siparişler", path: "/admin/siparisler", icon: ShoppingCart },
      { label: "İadeler", path: "/admin/iadeler", icon: RotateCcw },
      { label: "İptaller", path: "/admin/iptaller", icon: XCircle },
      { label: "Havale/EFT Bildirimleri", path: "/admin/havale-bildirimleri", icon: CreditCard },
      { label: "Ödeme Kaydı Bulunmayan", path: "/admin/odeme-bekleyen-siparisler", icon: AlertTriangle },
      { label: "Ödeme İzi (Numaradan)", path: "/admin/odeme-izi", icon: CreditCard },
      { label: "Silinen Siparişler", path: "/admin/silinen-siparisler", icon: Trash2 },
    ],
  },
  {
    key: "katalog",
    label: "Katalog",
    icon: Package,
    children: [
      { label: "Tüm Ürünler", path: "/admin/urunler", icon: Package },
      { label: "Ürün Setleri", path: "/admin/urun-setleri", icon: Package },
      { label: "Kategoriler", path: "/admin/kategoriler", icon: Tags },
      { label: "Kategori Sıralama", path: "/admin/kategori-siralama", icon: LayoutDashboard },
      { label: "Markalar", path: "/admin/markalar", icon: Store },
      { label: "Etiketler", path: "/admin/etiketler", icon: Tags },
      { label: "Ürün Özellikleri", path: "/admin/urun-ozellikleri", icon: Tags },
      { label: "Varyantlar", path: "/admin/varyantlar", icon: GitMerge },
      { label: "XML Feed'ler", path: "/admin/xml-feedler", icon: Rss },
      { label: "Stok & Fiyat Alarm", path: "/admin/stok-alarm", icon: BellRing },
      { label: "Toplu Fiyat/Stok (Excel)", path: "/admin/toplu-fiyat-stok", icon: Package },
      { label: "Stok Uyarıları", path: "/admin/stok-uyarilari", icon: BellRing },
    ],
  },
  {
    key: "raporlar",
    label: "Raporlar",
    icon: TrendingUp,
    children: [
      { label: "Satış Raporları", path: "/admin/raporlar/satis", icon: TrendingUp },
      { label: "Kâr & Stok Değer", path: "/admin/raporlar/kar-stok", icon: TrendingUp },
      { label: "Ürün Raporları", path: "/admin/raporlar/urun", icon: Package },
      { label: "Stok Raporu", path: "/admin/raporlar/stok", icon: Package },
    ],
  },
  {
    key: "tasarim",
    label: "Tasarım",     // ← eski adı "İçerik"
    icon: PenTool,
    children: [
      { label: "Bannerlar & Sliderlar", path: "/admin/bannerlar", icon: Image },
      { label: "Popuplar", path: "/admin/popuplar", icon: BellRing },
      { label: "Duyurular", path: "/admin/duyurular", icon: BellRing },
      { label: "Menü Yönetimi", path: "/admin/menu-yonetimi", icon: LayoutDashboard },
      { label: "Sayfa Tasarımı", path: "/admin/sayfa-tasarimi", icon: Palette },
      { label: "Footer Tasarımı", path: "/admin/footer-tasarim", icon: Palette },
      { label: "Sayfalar (CMS)", path: "/admin/sayfalar", icon: FileText },
    ],
  },
  {
    key: "uyeler",
    label: "Üyeler",
    icon: Users,
    children: [
      { label: "Üye Listesi", path: "/admin/uyeler", icon: Users },
      { label: "Müşteri Segmentleri (RFM)", path: "/admin/musteri-segmentleri", icon: Users },
      { label: "Destek Talepleri", path: "/admin/tickets", icon: MessageSquare },
      { label: "Bloklu Müşteriler", path: "/admin/bloklu-musteriler", icon: Users },
      { label: "Pazarlama İzinleri (E-posta/SMS)", path: "/admin/izinler", icon: Users },
    ],
  },
  {
    key: "egitim",
    label: "Eğitim & Yardım",
    path: "/admin/egitim",
    icon: GraduationCap,
  },
  {
    key: "pazarlama",
    label: "Pazarlama",
    icon: Megaphone,
    children: [
      { label: "Kampanyalar", path: "/admin/kampanyalar", icon: Megaphone },
      { label: "Kargo/Ödeme Kuralları", path: "/admin/kargo-odeme-kurallari", icon: Truck },
      { label: "Kuponlar", path: "/admin/kuponlar", icon: Tags },
      { label: "Hediye Çekleri", path: "/admin/hediye-cekleri", icon: Tags },
      { label: "E-posta Pazarlama", path: "/admin/eposta-pazarlama", icon: Mail },
      { label: "Ürün Yorumları", path: "/admin/yorumlar", icon: MessageSquare },
      { label: "Terkedilmiş Sepetler", path: "/admin/terkedilmis-sepet", icon: ShoppingCart },
      { label: "Kaynak & Funnel", path: "/admin/kaynak", icon: TrendingUp },
    ],
  },
  {
    key: "seo",
    label: "SEO",
    icon: FileText,
    children: [
      { label: "Meta Yönetimi", path: "/admin/seo/meta", icon: FileText },
      { label: "301 Yönlendirmeler", path: "/admin/seo/yonlendirmeler", icon: Link2 },
    ],
  },
  {
    key: "entegrasyonlar",
    label: "Entegrasyonlar",
    icon: Cable,
    children: [
      { label: "Tüm Entegrasyonlar", path: "/admin/entegrasyonlar", icon: Cable },
      { label: "Ödeme Tipleri", path: "/admin/odeme-tipleri", icon: CreditCard },
      { label: "Kargo Firmaları", path: "/admin/ayarlar/kargo", icon: Truck },
      { label: "BirFatura (e-Fatura)", path: "/admin/birfatura", icon: FileText },
      { label: "Reklam Pikselleri & CAPI", path: "/admin/ayarlar/pixel", icon: TrendingUp },
      { label: "SMS & İYS (NetGSM)", path: "/admin/iys", icon: MessageSquare },
    ],
  },
  {
    key: "sistem",
    label: "Sistem",
    icon: Shield,
    children: [
      { label: "Otomasyon Durumu", path: "/admin/otomasyon", icon: Cable },
      { label: "Güvenlik Paneli", path: "/admin/guvenlik-paneli", icon: Shield },
      { label: "Kullanıcı İşlem Geçmişi", path: "/admin/islem-gecmisi", icon: FileText },
      { label: "Sistem Sağlığı", path: "/admin/sistem-sagligi", icon: Cable },
      { label: "Secrets Vault", path: "/admin/secrets-vault", icon: Lock },
    ],
  },
  {
    key: "ayarlar",
    label: "Ayarlar",
    icon: Settings,
    children: [
      { label: "Genel Ayarlar", path: "/admin/ayarlar", icon: Settings },
      { label: "Mail Yönetimi", path: "/admin/mail-yonetimi", icon: Mail },
      { label: "Webmail'e Git", href: "https://mail.garajtek.com", external: true, icon: Mail },
    ],
  },
];

// localStorage anahtarları — kullanıcı bazlı
const orderKey = (uid) => `menuOrder:${uid || "anon"}`;
const hiddenKey = (uid) => `menuHidden:${uid || "anon"}`;

export function loadUserMenuPrefs(userId) {
  try {
    const order = JSON.parse(localStorage.getItem(orderKey(userId)) || "null");
    const hidden = JSON.parse(localStorage.getItem(hiddenKey(userId)) || "[]");
    return { order: Array.isArray(order) ? order : null, hidden: Array.isArray(hidden) ? hidden : [] };
  } catch { return { order: null, hidden: [] }; }
}

export function saveUserMenuPrefs(userId, { order, hidden }) {
  if (Array.isArray(order)) localStorage.setItem(orderKey(userId), JSON.stringify(order));
  if (Array.isArray(hidden)) localStorage.setItem(hiddenKey(userId), JSON.stringify(hidden));
}

export function resetUserMenuPrefs(userId) {
  localStorage.removeItem(orderKey(userId));
  localStorage.removeItem(hiddenKey(userId));
}

/**
 * Kullanıcının görmek istediği sıralı ve filtrelenmiş menü grupları.
 * `order` listesinde olmayan yeni eklenen menü grupları default sırasında sona eklenir.
 */
// Süper-admin'e özel yollar — arka uç zaten kilitli (require_super_admin);
// burada menüden de gizlenir ki kimse 403 alan bir sayfaya tıklamasın.
export const SUPER_ONLY_PATHS = [];

export function isSuperAdmin(perms) {
  return Array.isArray(perms) && perms.includes("*");
}

export function getNavigationFor(userId, perms) {
  const { order, hidden } = loadUserMenuPrefs(userId);
  const hiddenSet = new Set(hidden || []);
  // perms verilmediyse (henüz yüklenmediyse) menü DEĞİŞTİRİLMEZ — yükleme
  // sırasında girdiler bir an kaybolup geri gelmesin.
  const superOk = perms === undefined || perms === null || isSuperAdmin(perms);
  const byKey = Object.fromEntries(navigationGroups.map((g) => [g.key, g]));
  let ordered;
  if (order && order.length) {
    ordered = [];
    const seen = new Set();
    for (const k of order) {
      if (byKey[k]) { ordered.push(byKey[k]); seen.add(k); }
    }
    // Yeni eklenen gruplar listede yoksa sona ekle
    for (const g of navigationGroups) if (!seen.has(g.key)) ordered.push(g);
  } else {
    ordered = navigationGroups;
  }
  const visible = ordered.filter((g) => !hiddenSet.has(g.key));
  if (superOk) return visible;
  return visible
    .map((g) => (g.children
      ? { ...g, children: g.children.filter((c) => !c.superOnly) }
      : g))
    .filter((g) => !g.children || g.children.length > 0);
}
