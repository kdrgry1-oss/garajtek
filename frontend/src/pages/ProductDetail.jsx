import { useState, useEffect, useRef } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import { sanitizeHtml } from "../lib/sanitizeHtml";
import axios from "axios";
import { toast } from "sonner";
import Header from "../components/Header";
import Footer from "../components/Footer";
import ProductCard from "../components/ProductCard";
import { optimizeImg } from "../lib/img";
import { slugify } from "../lib/slug";
import { priceView } from "../lib/price";
import { applyRuntimeSeo, setProductSeo } from "../lib/seo";
import { useCart } from "../context/CartContext";
import { useFavorites } from "../context/FavoritesContext";
import { useAuth } from "../context/AuthContext";
import { useShipping } from "../lib/shipping";
import { trackViewContent, trackAddToCart } from "../utils/pixelEvents";
import { sortLikeSize } from "../utils/sizeSort";
import Breadcrumb from "../components/electro/Breadcrumb";
import Carousel from "../components/electro/Carousel";
import QuantityInput from "../components/electro/QuantityInput";
import useCategoryTree, { categoryPath } from "../components/electro/useCategoryTree";
import { toggleCompare } from "../components/electro/compare";
import { fmtPrice } from "../components/electro/format";
import NotFound from "./NotFound";
import { SITE_NAME } from "../lib/brand";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Tahmini teslimat aralığı (kargoya verilme + iş günü; hafta sonu atlanır)
function estimateDelivery(minDays = 2, maxDays = 4) {
  const addBiz = (base, n) => {
    const r = new Date(base);
    let added = 0;
    while (added < n) {
      r.setDate(r.getDate() + 1);
      const wd = r.getDay();
      if (wd !== 0 && wd !== 6) added++;
    }
    return r;
  };
  const fmt = (d) => d.toLocaleDateString("tr-TR", { day: "numeric", month: "long" });
  const now = new Date();
  return `${fmt(addBiz(now, minDays))} - ${fmt(addBiz(now, maxDays))}`;
}

// "xx saat yy dakika içinde kargoda" kargo aciliyeti + geri sayım.
// KURAL: Kargo YALNIZ iş günlerinde (Cmt/Paz + resmi tatiller hariç). Cutoff 10:30.
//  • İş günü ve 10:30'dan ÖNCE → bugün kargoda + geri sayım ("S saat D dakika içinde kargoda")
//  • İş günü 10:30'dan SONRA (gün dönmese de) → bir sonraki İŞ GÜNÜ kargoda ("yarın kargoda")
//  • Hafta sonu / resmi tatil → sonraki iş günü ("Pazartesi kargoda")
// Geri sayımda yalnız SAAT ve DAKİKA gösterilir; saniye gösterilmez (dakikada bir güncellenir).
const _TR_DAYS = ["Pazar", "Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi"];
// Resmi tatiller. Sabit ulusal bayramlar MM-DD; her yıl kayan dini bayramlar YYYY-MM-DD
// olarak eklenir (aşağıya ilgili yılın Ramazan/Kurban tarihleri girilebilir).
const TR_PUBLIC_HOLIDAYS = new Set([
  "01-01", // Yılbaşı
  "04-23", // Ulusal Egemenlik ve Çocuk Bayramı
  "05-01", // Emek ve Dayanışma Günü
  "05-19", // Atatürk'ü Anma, Gençlik ve Spor Bayramı
  "07-15", // Demokrasi ve Millî Birlik Günü
  "08-30", // Zafer Bayramı
  "10-29", // Cumhuriyet Bayramı
  // Dini bayramlar (değişken tarihli) — örn: "2026-03-20", "2026-05-27" ...
]);
function _isHolidayDate(d, extraHolidays) {
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const iso = `${d.getFullYear()}-${mm}-${dd}`;
  if (extraHolidays && extraHolidays.has(iso)) return true;
  return TR_PUBLIC_HOLIDAYS.has(`${mm}-${dd}`) || TR_PUBLIC_HOLIDAYS.has(iso);
}
function _isWorkingDay(d, cfg) {
  const wd = d.getDay(); // 0=Paz..6=Cmt
  const iso = wd === 0 ? 7 : wd; // 1=Pzt..7=Paz
  const workDays = (cfg && cfg.workDays) || [1, 2, 3, 4, 5];
  const holidays = cfg && cfg.holidays;
  const exclude = !cfg || cfg.exclude !== false;
  if (!workDays.includes(iso)) return false;
  if (exclude && _isHolidayDate(d, holidays)) return false;
  return true;
}
// AYAR: kesim saati / çalışma günleri / resmî tatiller İşletme Kuralları'ndan (cfg) gelir;
// cfg verilmezse varsayılan 12:00 + hafta içi + sabit millî tatiller.
// KURAL (kullanıcı isteği): HER ZAMAN canlı geri sayım göster (mesai saatlerine göre).
//  • İş günü ve cutoff'tan (12:00) ÖNCE → "X saat Y dakika içinde sipariş verirsen bugün kargoda"
//    ("bugün kargoda" yeşil). Aynı gün → direkt saat/dakika sayar.
//  • Cutoff geçti / hafta sonu / tatil → sonraki İŞ GÜNÜ cutoff'una kadar geri sayım
//    "1 gün X saat içinde sipariş verirsen en geç yarın kargoda" ("yarın kargoda" yeşil).
function shippingCutoff(cfg) {
  const cutoffHour = cfg && cfg.cutoffHour != null ? cfg.cutoffHour : 12;
  const cutoffMinute = cfg && cfg.cutoffMinute != null ? cfg.cutoffMinute : 0;
  const now = new Date();

  const todayCutoff = new Date(now); todayCutoff.setHours(cutoffHour, cutoffMinute, 0, 0);
  const sameDay = _isWorkingDay(now, cfg) && now.getTime() < todayCutoff.getTime();

  let target, greenLabel, sameDayMode;
  if (sameDay) {
    target = todayCutoff;
    greenLabel = "bugün kargoda";
    sameDayMode = true;
  } else {
    // Sonraki İŞ GÜNÜ (hafta sonu + tatil atlanır) cutoff'u
    const next = new Date(now); next.setHours(0, 0, 0, 0);
    do { next.setDate(next.getDate() + 1); } while (!_isWorkingDay(next, cfg));
    target = new Date(next); target.setHours(cutoffHour, cutoffMinute, 0, 0);
    const tomorrow = new Date(now); tomorrow.setHours(0, 0, 0, 0); tomorrow.setDate(tomorrow.getDate() + 1);
    const isTomorrow = next.toDateString() === tomorrow.toDateString();
    greenLabel = `${isTomorrow ? "yarın" : _TR_DAYS[next.getDay()]} kargoda`;
    sameDayMode = false;
  }

  // Geri sayım (hedef cutoff'a kadar). Gün varsa "G gün S saat", yoksa "S saat D dakika".
  const remMs = Math.max(0, target.getTime() - now.getTime());
  const days = Math.floor(remMs / 86400000);
  const h = Math.floor((remMs % 86400000) / 3600000);
  const m = Math.floor((remMs % 3600000) / 60000);
  let left;
  if (days >= 1) left = `${days} gün ${h} saat`;
  else if (h >= 1) left = `${h} saat ${m} dakika`;
  else left = `${m} dakika`;

  return {
    countdown: true,
    // Aynı gün → "...sipariş verirsen bugün kargoda"; değilse → "...en geç yarın kargoda"
    prefix: sameDayMode
      ? `${left} içinde sipariş verirsen`
      : `${left} içinde sipariş verirsen en geç`,
    green: greenLabel,   // yeşil vurgulanacak kısım
  };
}

// Son gezilen ürünler — localStorage'da küçük anlık görüntü (snapshot) listesi.
const RV_KEY = "store_recently_viewed";
const readRecentlyViewed = () => {
  try { return JSON.parse(localStorage.getItem(RV_KEY) || "[]"); } catch { return []; }
};
const pushRecentlyViewed = (snap) => {
  if (!snap || !snap.id) return;
  try {
    const list = readRecentlyViewed().filter((x) => x && x.id !== snap.id);
    list.unshift(snap);
    localStorage.setItem(RV_KEY, JSON.stringify(list.slice(0, 12)));
  } catch { /* sessiz */ }
};

export default function ProductDetail() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { addItem, isOpen: cartOpen } = useCart();
  const catTree = useCategoryTree();
  const [pdpTab, setPdpTab] = useState("description");
  const touchX = useRef(0);
  const { isFavorite, toggleFavorite } = useFavorites();
  const { freeShippingThreshold } = useShipping();
  const { user } = useAuth();
  // A5: kargo geri sayım kuralları (kesim saati / çalışma günleri / resmî tatiller) İşletme
  // Kuralları'ndan gelir — kodda sabit değil. Her dakika yeniden hesaplanır.
  const [shipCfg, setShipCfg] = useState(null);
  const [, _tickShip] = useState(0);
  useEffect(() => {
    axios.get(`${API}/business-rules`).then((r) => {
      const d = r.data || {};
      const [ch, cm] = String(d["shipping.same_day_cutoff"] || "12:00").split(":").map((x) => parseInt(x, 10));
      setShipCfg({
        cutoffHour: ch, cutoffMinute: cm,
        workDays: Array.isArray(d["shipping.work_days"]) ? d["shipping.work_days"] : [1, 2, 3, 4, 5],
        holidays: new Set(d["official_holidays"] || []),
        exclude: d["shipping.exclude_official_holidays"] !== false,
        // Vitrin görünüm anahtarları (İşletme Kuralları → varsayılan açık)
        showCompleteLook: d["product.complete_the_look_enabled"] !== false,
        showCountdown: d["product.shipping_countdown_enabled"] !== false,
        showSocialShare: d["product.social_share_enabled"] !== false,
        lowStockBadge: d["product.low_stock_badge_enabled"] !== false,
        lowStockThreshold: Number(d["product.low_stock_badge_threshold"] ?? 5),
      });
    }).catch(() => {});
  }, []);
  useEffect(() => { const t = setInterval(() => _tickShip((n) => n + 1), 60000); return () => clearInterval(t); }, []);

  // İade ve Değişim akordiyonu — merchant'ın 'iade-kosullari' sayfasını DİNAMİK gösterir
  // (sayfa güncellenince akordiyon da güncellenir). Fetch başarısızsa sabit kısa metne düşer.
  const [returnPolicyHtml, setReturnPolicyHtml] = useState("");
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/pages/iade-kosullari`)
      .then((r) => { if (alive) setReturnPolicyHtml(r?.data?.content || ""); })
      .catch(() => { /* sessiz — fallback metin gösterilir */ });
    return () => { alive = false; };
  }, []);
  const [product, setProduct] = useState(null);
  const [similarProducts, setSimilarProducts] = useState([]);
  const [recentItems, setRecentItems] = useState([]); // son gezilenler (önceki sayfalardan)
  // Son gezilen kartların fiyat/kampanyası CANLI tazelenir: localStorage'daki eski
  // anlık görüntüler kampanyayı bilmediğinden indirimli (kırmızı) fiyat görünmüyordu.
  // Sepetle aynı sunucu-otoriter kaynak: POST /products/cart-pricing.
  const _rvIdsKey = recentItems.map((x) => x && x.id).filter(Boolean).join(",");
  useEffect(() => {
    if (!_rvIdsKey) return;
    let cancel = false;
    axios.post(`${API}/products/cart-pricing`, { product_ids: _rvIdsKey.split(",") })
      .then((r) => {
        if (cancel || !r.data?.items) return;
        const items = r.data.items;
        setRecentItems((prev) => {
          // PASİF/SİLİNMİŞ ÜRÜNLERİ AT: cart-pricing bulunan her ürün için is_active döner.
          // Sunucudan HİÇ dönmeyen (info yok) = silinmiş; is_active===false = pasif. İkisi de
          // "Son Gezdiklerin"de gösterilmez (kırık görsel / satılamayan ürün sızmasın).
          const next = prev
            .filter((it) => {
              const info = items[it.id];
              return info && info.is_active !== false;
            })
            .map((it) => {
              const info = items[it.id];
              return {
                ...it,
                price: info.price, sale_price: info.sale_price,
                campaign_discount_percent: info.campaign_discount_percent,
              };
            });
          // Değişiklik yoksa aynı referansı koru (gereksiz render/döngü olmasın)
          const unchanged = next.length === prev.length && next.every((it, i) =>
            it.id === prev[i].id
            && Number(it.price) === Number(prev[i].price)
            && Number(it.sale_price || 0) === Number(prev[i].sale_price || 0)
            && Number(it.campaign_discount_percent || 0) === Number(prev[i].campaign_discount_percent || 0));
          if (unchanged) return prev;
          // Temizlenmiş listeyi localStorage'a da yaz (pasifler bir daha yüklenmesin)
          try { localStorage.setItem(RV_KEY, JSON.stringify(next.slice(0, 12))); } catch { /* sessiz */ }
          return next;
        });
      })
      .catch(() => {});
    return () => { cancel = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [_rvIdsKey]);
  const [loading, setLoading] = useState(true);
  const [selectedImage, setSelectedImage] = useState(0);
  // Masaüstü büyük görsel büyüteci (hover → imlecin olduğu bölge büyür)
  const [zoom, setZoom] = useState({ on: false, x: 50, y: 50 });
  const [selectedSize, setSelectedSize] = useState(null);
  const [selectedVariant, setSelectedVariant] = useState(null);
  const [quantity, setQuantity] = useState(1);
  // Kargo geri sayımı: dakikada bir yeniden render (saniye gösterilmez, saat+dakika canlı düşer)
  const [, setShipTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setShipTick((t) => t + 1), 30000);
    return () => clearInterval(id);
  }, []);
  const [showStickyHeader, setShowStickyHeader] = useState(false);
  const [mobileImageIdx, setMobileImageIdx] = useState(0);
  const [expandedSections, setExpandedSections] = useState({
    description: true,   // Ürün Özellikleri varsayılan açık — bilgi gizli accordion'da kalmasın
    shipping: false,
    returns: false
  });
  // Sepete eklendi mikro-etkileşimi: buton kısa süre "Eklendi ✓" gösterir
  const [justAdded, setJustAdded] = useState(false);
  // "Gelince Haber Ver" — stokta olmayan beden için e-posta toplama
  const [notifyOpen, setNotifyOpen] = useState(false);
  const [notifyEmail, setNotifyEmail] = useState("");
  const [notifySubmitting, setNotifySubmitting] = useState(false);

  // Ürün değerlendirmeleri (yorum + puan). Backend: GET /reviews/product/:id (onaylı),
  // POST /reviews (auth, moderasyon → pending). Admin onayı sonrası listede görünür.
  const [reviews, setReviews] = useState([]);
  const [reviewAvg, setReviewAvg] = useState(0);
  const [reviewTotal, setReviewTotal] = useState(0);
  const [rvRating, setRvRating] = useState(0);
  const [rvTitle, setRvTitle] = useState("");
  const [rvComment, setRvComment] = useState("");
  const [rvSubmitting, setRvSubmitting] = useState(false);
  const rvLoggedIn = !!localStorage.getItem("token");

  useEffect(() => {
    if (!product?.id) return;
    (async () => {
      try {
        const { data } = await axios.get(`${API}/reviews/product/${product.id}`);
        setReviews(data.items || []);
        setReviewAvg(data.average_rating || 0);
        setReviewTotal(data.total || 0);
      } catch { /* yorum yoksa sessiz geç */ }
    })();
  }, [product?.id]);

  const submitReview = async () => {
    if (rvRating < 1) { toast.error("Lütfen 1-5 yıldız seçin"); return; }
    setRvSubmitting(true);
    try {
      await axios.post(`${API}/reviews`,
        { product_id: product.id, rating: rvRating, title: rvTitle, comment: rvComment },
        { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
      toast.success("Yorumunuz alındı, moderasyon sonrası yayınlanacak");
      setRvRating(0); setRvTitle(""); setRvComment("");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Yorum gönderilemedi");
    } finally {
      setRvSubmitting(false);
    }
  };

  // Edge ile aynı canonical runtime SEO sonucunu SPA gezinmesinde de uygula.
  // Backend yalnız gerçek ürün verisini JSON-LD'ye ekler; veri yoksa uydurmaz.
  useEffect(() => {
    if (!product) return;
    const controller = new AbortController();
    applyRuntimeSeo(`/urun/${product.slug || product.id}`, () => setProductSeo(product), {
      signal: controller.signal,
    });
    return () => {
      controller.abort();
      document.querySelectorAll('script[data-seo="runtime"]').forEach((el) => el.remove());
    };
  }, [product]);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [slug]);

  // Sticky header on scroll
  useEffect(() => {
    const handleScroll = () => {
      setShowStickyHeader(window.scrollY > 400);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let cancel = false;
    // Ürünler arası geçişte (A→B) önceki ürünün seçili varyantı/bedeni KALMASIN —
    // aksi halde B'nin bedeni stoksuzken A'nın varyantı sepete B ürünüyle düşüyordu.
    setSelectedVariant(null);
    setSelectedSize("");
    (async () => {
      try {
        const res = await axios.get(`${API}/products/${slug}`, { signal: controller.signal });
        if (cancel) return;   // A→B hızlı geçişte eski ürünün geç dönen verisi yeni sayfayı EZMESİN
        setProduct(res.data);

        // Son gezilenler: önceki listeyi (mevcut ürün hariç) göster, sonra mevcut
        // ürünü snapshot olarak kaydet (bir sonraki sayfada görünsün).
        try {
          const _p = res.data;
          setRecentItems(readRecentlyViewed().filter((x) => x && x.id !== _p.id).slice(0, 10));
          const _rvImg = (() => {
            const im = (_p.images && _p.images[0]) || _p.image || "";
            return (typeof im === "object" && im !== null) ? (im.url || im.src || "") : im;
          })();
          pushRecentlyViewed({
            id: _p.id,
            name: _p.name,
            slug: _p.slug || _p.id,
            image: _rvImg,
            price: _p.price,
            sale_price: _p.sale_price,
            // Kampanya olmadan kaydedilirse kartta indirim görünmüyordu
            campaign_discount_percent: _p.campaign_discount_percent,
          });
        } catch { /* sessiz */ }

        // Canonical URL: ürün id/eski slug ile açıldıysa doğru slug'a yönlendir (SEO + tutarlı URL)
        if (res.data?.slug && res.data.slug !== slug) {
          navigate(`/${res.data.slug}`, { replace: true });
        }

        // Varsayılan/ilk uygun bedeni önce belirle — ViewContent'in Meta content_id'si
        // seçili bedenin Ticimax varyant id'si olsun (katalog eşleşmesi için).
        // ?beden=XL ile gelindiyse (WhatsApp/AI linki) o bedeni ön-seç (stokluysa).
        let _wantSize = "";
        try { _wantSize = (new URLSearchParams(window.location.search).get("beden") || "").trim(); } catch { _wantSize = ""; }
        const _bySize = _wantSize
          ? (res.data?.variants || []).find((v) => String(v.size || "").toUpperCase() === _wantSize.toUpperCase() && (v.stock || 0) > 0)
          : null;
        const defaultVariant =
          _bySize ||
          (res.data?.variants || []).find((v) => (v.stock || 0) > 0) ||
          (res.data?.variants || [])[0] || null;

        // FAZ 9+ — Pixel ViewContent event
        trackViewContent({
          product_id: res.data.id,
          name: res.data.name,
          category: res.data.category_name,
          price: res.data.sale_price || res.data.price,
          variant_id: defaultVariant?.id,
        });

        if (defaultVariant && (defaultVariant.stock || 0) > 0) {
          setSelectedVariant(defaultVariant);
          setSelectedSize(defaultVariant.size);
        }

        // Benzer ürünler — GERÇEK ürün-tipi kategorisinden (promo/sanal kategoriler HARİÇ).
        // Backend /products/{id}/similar: category_ids içinden en spesifik gerçek tip
        // kategoriyi seçer; yoksa ürün adından tip çıkarır; hiçbiri tutmazsa BOŞ döner
        // (İNDİRİM/KOLEKSİYONLAR gibi promo birincil-kategori kaynaklı alakasız öneri düzeltmesi).
        try {
          // Aynı kategori, stokta, fiyatı yakın en çok 12 ürün → "Benzer Ürünler" karuseli.
          const simRes = await axios.get(`${API}/products/${res.data.id}/similar?limit=12`);
          setSimilarProducts((simRes.data?.similar || []).filter(p => p.id !== res.data.id));
        } catch {
          // benzer ürün getirilemezse sessizce geç
        }

      } catch (err) {
        if (cancel || axios.isCancel?.(err) || err.name === "CanceledError") return;
        // ÜYELERE ÖZEL: misafir üyelere özel ürüne (ya da /:slug ile üyelere özel kategoriye)
        // girerse "bulunamadı" yerine GİRİŞ sayfasına yönlendirilir (giriş sonrası geri döner).
        if (err?.response?.status === 404 && !(() => { try { return localStorage.getItem("token"); } catch { return null; } })()) {
          let mo = err?.response?.data?.detail === "members_only";
          if (!mo) {
            try {
              const c = await axios.get(`${API}/categories/${encodeURIComponent(slug)}`);
              mo = !!(c.data?.members_only || c.data?.members_only_effective);
            } catch { /* kategori de değil → normal "bulunamadı" */ }
          }
          if (mo && !cancel) {
            navigate(`/giris?redirect=${encodeURIComponent("/" + slug)}`, { replace: true });
            return;
          }
        }
        console.error(err);
      } finally {
        if (!cancel) setLoading(false);
      }
    })();
    return () => { cancel = true; controller.abort(); };
  }, [slug]);

  const handleAddToCart = () => {
    if (product.variants?.length > 0 && !selectedVariant) {
      toast.error(`Lütfen ${(product.variant_labels?.size || "seçenek").toLocaleLowerCase("tr")} seçiniz`);
      return;
    }

    // Varyantsız ürünlerde ürün stoğu yoksa engelle (tükendi)
    if (!(product.variants?.length > 0) && (Number(product.stock) || 0) <= 0) {
      toast.error("Bu ürün tükendi");
      return;
    }
    
    // Check stock for selected variant (string/null/negatif stoğa karşı sağlam)
    const _selStock = Number(selectedVariant?.stock);
    if (selectedVariant && (!Number.isFinite(_selStock) || _selStock < quantity)) {
      toast.error(_selStock > 0 ? `Yetersiz stok! Mevcut stok: ${_selStock}` : "Bu seçenek tükendi");
      return;
    }
    
    addItem(product, selectedVariant, quantity);
    // FAZ 9+ — Pixel AddToCart event
    trackAddToCart({
      product_id: product.id,
      name: product.name,
      category: product.category_name,
      price: selectedVariant?.price || product.sale_price || product.price,
      quantity,
      size: selectedVariant?.size,
      color: selectedVariant?.color,
      variant_id: selectedVariant?.id,
    });
    toast.success(selectedVariant 
      ? `${product.name} - ${selectedVariant.size} sepete eklendi` 
      : "Ürün sepete eklendi"
    );
    setJustAdded(true);
    setTimeout(() => setJustAdded(false), 1600);
  };

  const handleSizeSelect = (variant) => {
    setSelectedVariant(variant);
    setSelectedSize(variant.size);
    // Beden değişince açık bildirim formunu kapat (stoklu bedene geçilirse gizlenir)
    if (variant.stock > 0) setNotifyOpen(false);
    // Beden değişince ViewContent'i seçili bedenin Meta katalog id'siyle yeniden gönder
    // (Meta content_id = o bedenin Ticimax varyant id'si — her beden için doğru eşleşme).
    if (product) {
      trackViewContent({
        product_id: product.id,
        name: product.name,
        category: product.category_name,
        price: variant.price || product.sale_price || product.price,
        variant_id: variant.id,
      });
    }
  };

  const handleStockNotify = async () => {
    const email = notifyEmail.trim();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      toast.error("Lütfen geçerli bir e-posta adresi giriniz");
      return;
    }
    setNotifySubmitting(true);
    try {
      const res = await axios.post(`${API}/stock-notify`, {
        product_id: product.id,
        size: selectedVariant?.size || selectedSize || "",
        email,
      });
      toast.success(res.data?.message || "Talebiniz alındı, stoğa girince haber vereceğiz.");
      setNotifyOpen(false);
      setNotifyEmail("");
    } catch (err) {
      toast.error(err.response?.data?.detail || "Bir hata oluştu, lütfen tekrar deneyin.");
    } finally {
      setNotifySubmitting(false);
    }
  };

  // Y28: Varyantsız ürünlere UYDURMA beden (XS–XL) ve sahte stok (10) üretilmez — bu sahte
  // varyantlar sepete gerçek dışı beden/stok yazıp mükerrer satır ve yanlış sipariş oluşturuyordu.
  // Varyantsız ürün beden seçici göstermez; ekleme varyantsız (tek ürün) olarak yapılır.
  const sizes = product?.variants?.length > 0
    ? sortLikeSize(product.variants, v => v.size)
    : [];

  if (loading) {
    return (
      <div className="sf-page">
        <Header />
        <main className="electro el-page">
          <div className="container py-6">
            <div className="row">
              <div className="col-md-5 mb-4"><div className="el-skel" style={{ aspectRatio: "1 / 1" }} /></div>
              <div className="col-md-7">
                <div className="el-skel mb-3" style={{ height: 32, width: "70%" }} />
                <div className="el-skel mb-3" style={{ height: 20, width: "30%" }} />
                <div className="el-skel" style={{ height: 160 }} />
              </div>
            </div>
          </div>
        </main>
        <Footer />
      </div>
    );
  }

  if (!product) {
    return <NotFound message="Aradığınız ürün bulunamadı veya artık satışta değil." />;
  }

  // İndirim görünümü TEK KAYNAK (lib/price) — vitrin kartlarıyla birebir aynı.
  const _pv = priceView(product);
  // Sepetle AYNI mantık: varyant fiyat farkı (price_diff / price_adjustment) gösterilen fiyata eklenir.
  const variantPriceDiff = selectedVariant?.price_diff || selectedVariant?.price_adjustment || 0;
  const hasDiscount = _pv.hasDiscount;
  const listUnit = _pv.list + variantPriceDiff;
  const displayPrice = _pv.display + variantPriceDiff;

  const allImages = product.images || [];
  const uniqueImages = allImages.length > 1 && allImages[0] === allImages[1] ? allImages.slice(1) : allImages;
  const displayImages = uniqueImages
    .filter((img) => !(typeof img === "object" && img !== null && img.is_size_table))
    .map((img) => (typeof img === "object" && img !== null ? (img.url || img.src || img.image || "") : img))
    .filter(Boolean);
  if (!displayImages.length) displayImages.push("/placeholder.jpg");
  const curImg = displayImages[selectedImage] || displayImages[0];

  const hasVariants = (product.variants?.length || 0) > 0;
  const productOOS = !hasVariants && (Number(product.stock) || 0) <= 0;
  const oosSelected = (selectedVariant && Number(selectedVariant.stock) <= 0) || productOOS;
  const stockNow = hasVariants ? Number(selectedVariant?.stock || 0) : Number(product.stock || 0);
  const maxQty = Math.max(1, Math.min(Number(product.max_order_qty) || 9999, stockNow || 1));
  const isFav = isFavorite(product.id);
  const catNode = product.category_id != null ? catTree.byId.get(String(product.category_id)) : null;
  const catPath = catNode ? categoryPath(catTree, catNode) : [];
  const attrs = Array.isArray(product.attributes)
    ? product.attributes.filter((a) => a && a.name && String(a.value ?? "").trim())
    : product.attributes && typeof product.attributes === "object"
      ? Object.entries(product.attributes).map(([name, v]) => ({ name, value: typeof v === "object" ? v?.value : v })).filter((a) => String(a.value ?? "").trim())
      : [];
  // Teknik Özellikler: backend'in gruplu tablosu (product.spec_table — marka, model, kapasite,
  // güç, boyut/paket/desi, ek özellikler) + stok kodu / teslim süresi / ürün özellikleri.
  const specGroups = Array.isArray(product.spec_table) ? product.spec_table.filter((g) => g && g.rows && g.rows.length) : [];
  const otherRows = [
    !specGroups.length && product.brand && ["Marka", product.brand],
    product.stock_code && ["Stok Kodu", product.stock_code],
    product.estimated_delivery && ["Tahmini Teslim", `${product.estimated_delivery} iş günü`],
    ...attrs.map((a) => [a.name, String(a.value)]),
  ].filter(Boolean);
  const shortList = attrs.slice(0, 5);
  const shareUrl = typeof window !== "undefined" ? window.location.href : "";
  if (otherRows.length) specGroups.push({ key: "diger", group: "Diğer Bilgiler", rows: otherRows.map(([label, value]) => ({ label, value })) });
  const specRows = specGroups.flatMap((g) => g.rows);
  const enc = encodeURIComponent;
  const copyLink = async () => {
    try { await navigator.clipboard.writeText(shareUrl); toast.success("Bağlantı kopyalandı"); } catch { toast.error("Kopyalanamadı"); }
  };
  const nativeShare = async () => {
    try {
      if (navigator.share) await navigator.share({ title: product.name, url: shareUrl });
      else { await navigator.clipboard.writeText(shareUrl); toast.success("Bağlantı kopyalandı"); }
    } catch { /* iptal */ }
  };
  const tabs = [
    ["description", "Açıklama"],
    specRows.length > 0 && ["specification", "Teknik Özellikler"],
    ["shipping", "Kargo & İade"],
    ["reviews", `Değerlendirmeler${reviewTotal > 0 ? ` (${reviewTotal})` : ""}`],
  ].filter(Boolean);
  const activeTab = tabs.some((t) => t[0] === pdpTab) ? pdpTab : (tabs.find((t) => t[0] === "description") || tabs[0])[0];
  const stars = (val, size = "") => [1, 2, 3, 4, 5].map((i) => (
    <small key={i} className={`${i <= Math.round(val || 0) ? "fas fa-star" : "far fa-star text-muted"} ${size}`} />
  ));

  return (
    <div className="sf-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb testId="pdp-breadcrumb" items={[
          ...(catPath.length ? catPath.map((c) => ({ label: c.name, to: `/${c.slug}` }))
            : product.category_name ? [{ label: product.category_name, to: `/${slugify(product.category_name)}` }] : []),
          { label: product.name },
        ]} />

        {/* Mobil/masaüstü yapışkan ürün çubuğu — sepet paneli açıkken gizlenir */}
        {showStickyHeader && !cartOpen && !oosSelected && (
          <div className="el-sticky-atc d-xl-none" data-testid="sticky-product-bar">
            <div className="d-flex align-items-center">
              <img src={optimizeImg(displayImages[0], 150)} alt="" width="44" height="44" className="mr-2" style={{ objectFit: "contain" }} />
              <div className="flex-grow-1 min-width-0 mr-2">
                <div className="font-size-13 el-line-1">{product.name}</div>
                <div className={`font-size-15 font-weight-bold${hasDiscount ? " text-red" : ""}`}>{fmtPrice(displayPrice)}</div>
              </div>
              <button type="button" onClick={handleAddToCart} className="btn btn-primary-dark-w px-4 py-2 rounded-pill font-size-14" data-testid="sticky-add-to-cart">Sepete Ekle</button>
            </div>
          </div>
        )}

        <div className="container">
          <div className="mb-xl-14 mb-6">
            <div className="row">
              {/* Galeri */}
              <div className="col-md-5 mb-4 mb-md-0" data-testid="pdp-gallery">
                <div className="position-relative mb-2">
                  <a
                    href={curImg}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Görseli yeni sekmede tam boyutta aç"
                    data-testid="pdp-image-fullsize"
                    className="el-pdp-main d-flex"
                    onMouseEnter={() => setZoom((z) => ({ ...z, on: true }))}
                    onMouseLeave={() => setZoom({ on: false, x: 50, y: 50 })}
                    onMouseMove={(e) => {
                      if (window.innerWidth < 992) return;
                      const r = e.currentTarget.getBoundingClientRect();
                      setZoom({ on: true, x: ((e.clientX - r.left) / r.width) * 100, y: ((e.clientY - r.top) / r.height) * 100 });
                    }}
                    onTouchStart={(e) => { touchX.current = e.touches[0].clientX; }}
                    onTouchEnd={(e) => {
                      const dx = e.changedTouches[0].clientX - (touchX.current || 0);
                      if (Math.abs(dx) > 40) { e.preventDefault(); setSelectedImage((i) => (i + (dx < 0 ? 1 : -1) + displayImages.length) % displayImages.length); }
                    }}
                  >
                    <img src={optimizeImg(curImg, 1200)} alt={product.name} width="720" height="660" fetchPriority="high" loading="eager" decoding="async"
                      style={zoom.on && window.innerWidth >= 992 ? { transform: "scale(2)", transformOrigin: `${zoom.x}% ${zoom.y}%` } : undefined} />
                  </a>
                  {hasDiscount && _pv.discountPct > 0 && <span className="el-badge el-badge--sale" style={{ top: 8, left: 8 }}>-%{_pv.discountPct}</span>}
                  {user?.is_admin && (
                    <Link to={`/admin/urunler/${product.id}`} target="_blank" rel="noopener noreferrer" title="Ürünü düzenle (admin) — yeni sekmede açılır"
                      data-testid="pdp-admin-edit" className="btn btn-dark btn-icon rounded-circle position-absolute" style={{ left: 8, bottom: 8 }}>
                      <i className="fas fa-pen btn-icon__inner" />
                    </Link>
                  )}
                </div>
                {displayImages.length > 1 && (
                  <div className="row mx-gutters-1" data-testid="pdp-thumb-strip">
                    {displayImages.slice(0, 10).map((img, index) => (
                      <div className="col-3 col-xl-2gdot4 mb-1" key={img + index} style={{ flex: "0 0 20%", maxWidth: "20%" }}>
                        <button type="button" className={`el-pdp-thumb${index === selectedImage ? " active" : ""}`} onClick={() => setSelectedImage(index)} onMouseEnter={() => setSelectedImage(index)}
                          aria-label={`Görsel ${index + 1}`} data-testid={`pdp-thumb-${index}`}>
                          <img src={optimizeImg(img, 200)} alt="" loading="lazy" width="80" height="80" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Ürün bilgisi */}
              <div className="col-md-7 mb-md-6 mb-lg-0">
                <div className="mb-2">
                  <div className="border-bottom mb-3 pb-md-1 pb-3">
                    {(catNode || product.category_name) && (
                      <Link to={catNode ? `/${catNode.slug}` : `/${slugify(product.category_name)}`} className="font-size-12 text-gray-5 mb-2 d-inline-block">{catNode?.name || product.category_name}</Link>
                    )}
                    {product.promo_badge ? <div className="font-size-14 font-weight-bold text-red text-uppercase mb-1" data-testid="promo-badge">{product.promo_badge}</div> : null}
                    <h1 className="font-size-25 text-lh-1dot2">{product.name}</h1>
                    <div className="mb-2">
                      <button type="button" className="btn btn-link p-0 d-inline-flex align-items-center small font-size-15 text-lh-1" data-testid="pdp-rating-jump"
                        onClick={() => { setPdpTab("reviews"); document.getElementById("pdp-tabs")?.scrollIntoView({ behavior: "smooth" }); }} aria-label="Değerlendirmeleri gör">
                        <div className="text-warning mr-2">{stars(reviewAvg)}</div>
                        <span className="text-secondary font-size-13">{reviewTotal > 0 ? `(${reviewTotal} değerlendirme)` : "(İlk değerlendirmeyi siz yapın)"}</span>
                      </button>
                    </div>
                    <div className="d-md-flex align-items-center">
                      {product.brand && <span className="font-weight-bold font-size-15 mr-md-3 text-gray-90">{product.brand}</span>}
                      <div className="text-gray-9 font-size-14">Stok Durumu: {oosSelected
                        ? <span className="text-red font-weight-bold">Tükendi</span>
                        : <span className="text-green font-weight-bold">{stockNow > 0 && stockNow <= 20 ? `${stockNow} adet stokta` : "Stokta"}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="flex-horizontal-center flex-wrap mb-4">
                    <button type="button" onClick={() => toggleFavorite(product)} className={`btn btn-link p-0 text-gray-6 font-size-13 mr-2${isFav ? " text-red" : ""}`} data-testid="pdp-favorite-btn" aria-pressed={isFav}>
                      <i className={`${isFav ? "fas fa-heart" : "ec ec-favorites"} mr-1 font-size-15`} /> {isFav ? "Favorilerde" : "Favorilere Ekle"}
                    </button>
                    <button type="button" onClick={() => { const r = toggleCompare(product); toast.success(r.added ? "Karşılaştırma listesine eklendi" : "Karşılaştırma listesinden çıkarıldı"); }}
                      className="btn btn-link p-0 text-gray-6 font-size-13 ml-2" data-testid="pdp-compare-btn">
                      <i className="ec ec-compare mr-1 font-size-15" /> Karşılaştır
                    </button>
                  </div>
                  {shortList.length > 0 && (
                    <div className="mb-2">
                      <ul className="font-size-14 pl-3 ml-1 text-gray-110">
                        {shortList.map((a) => <li key={a.name}>{a.name}: {String(a.value)}</li>)}
                      </ul>
                    </div>
                  )}
                  {product.short_description && <p>{String(product.short_description).replace(/<[^>]*>/g, "")}</p>}
                  {(selectedVariant?.stock_code || product.stock_code) && <p><strong>Stok Kodu</strong>: {selectedVariant?.stock_code || product.stock_code}</p>}

                  <div className="mb-4" data-testid="pdp-price">
                    <div className="d-flex align-items-baseline">
                      <ins className="font-size-36 text-decoration-none">{fmtPrice(displayPrice)}</ins>
                      {hasDiscount && <del className="font-size-20 ml-2 text-gray-6">{fmtPrice(listUnit)}</del>}
                    </div>
                    {_pv.campaignLabel && <div className="font-size-13 text-green">{_pv.campaignLabel}</div>}
                  </div>


                  {hasVariants && (
                    <div className="border-top border-bottom py-3 mb-4" data-testid="pdp-variants">
                      <div className="d-flex align-items-center flex-wrap">
                        <h6 className="font-size-14 mb-0 mr-3">
                          {product.variant_labels?.size || "Seçenek"}
                          {selectedVariant && <span className="font-weight-normal text-gray-90">: {selectedVariant.size}</span>}
                        </h6>
                        <div className="d-flex flex-wrap">
                          {sizes.map((variant, index) => {
                            const isSelected = selectedSize === variant.size;
                            const isOOS = Number(variant.stock) <= 0;
                            return (
                              <button key={index} type="button" onClick={() => handleSizeSelect(variant)} data-testid={`size-btn-${variant.size}`}
                                title={isOOS ? "Tükendi" : undefined}
                                className={`btn btn-sm border rounded-pill mr-2 mb-1 px-3 el-variant-btn${isSelected ? " active" : ""}${isOOS ? " oos" : ""}`}>
                                {variant.size}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  )}

                  {(shipCfg?.lowStockBadge !== false) && stockNow > 0 && stockNow <= (shipCfg?.lowStockThreshold ?? 5) && (
                    <p className="mb-3 font-size-14 font-weight-bold text-red" data-testid="pdp-low-stock"><i className="fas fa-fire mr-1" /> Son {stockNow} ürün!</p>
                  )}

                  <div className="d-md-flex align-items-end mb-3">
                    {!oosSelected && (
                      <div className="max-width-150 mb-4 mb-md-0">
                        <h6 className="font-size-14">Adet</h6>
                        <QuantityInput value={quantity} onChange={setQuantity} min={Math.max(1, Number(product.min_order_qty) || 1)} max={maxQty} testId="pdp-qty" />
                      </div>
                    )}
                    <div className={oosSelected ? "" : "ml-md-3"}>
                      {oosSelected ? (
                        <button type="button" onClick={() => setNotifyOpen((v) => !v)} data-testid="notify-toggle-btn" className="btn px-5 btn-primary-dark transition-3d-hover">
                          <i className="ec ec-mail mr-2 font-size-20" /> Gelince Haber Ver
                        </button>
                      ) : (
                        <button type="button" onClick={handleAddToCart} data-testid="add-to-cart-btn" disabled={hasVariants && !selectedVariant}
                          className={`btn px-5 transition-3d-hover ${justAdded ? "btn-success" : "btn-primary-dark"}`}>
                          {hasVariants && !selectedVariant ? "Seçenek Seçiniz" : justAdded
                            ? <><i className="fas fa-check mr-2" /> Sepete Eklendi</>
                            : <><i className="ec ec-add-to-cart mr-2 font-size-20" /> Sepete Ekle</>}
                        </button>
                      )}
                    </div>
                  </div>

                  {oosSelected && notifyOpen && (
                    <div className="border rounded p-3 mb-3 bg-gray-1" data-testid="stock-notify-form">
                      <p className="font-size-13 mb-2">{selectedVariant?.size ? <><strong>{selectedVariant.size}</strong> seçeneği</> : "Bu ürün"} tükendi. Stoğa girince e-posta ile haber verelim.</p>
                      <div className="input-group">
                        <input type="email" className="form-control" value={notifyEmail} onChange={(e) => setNotifyEmail(e.target.value)}
                          onKeyDown={(e) => { if (e.key === "Enter") handleStockNotify(); }} placeholder="E-posta adresiniz" data-testid="stock-notify-email-input" />
                        <div className="input-group-append">
                          <button type="button" className="btn btn-dark" onClick={handleStockNotify} disabled={notifySubmitting} data-testid="stock-notify-submit-btn">{notifySubmitting ? "Gönderiliyor…" : "Gönder"}</button>
                        </div>
                      </div>
                    </div>
                  )}

                  {(shipCfg?.showCountdown !== false) && (() => {
                    const c = shippingCutoff(shipCfg);
                    return (
                      <p className="font-size-14 mb-3" data-testid="pdp-shipping-cutoff">
                        <i className="ec ec-transport mr-2 text-green" />{c.prefix} <strong className="text-green">{c.green}</strong>
                      </p>
                    );
                  })()}

                  <div className="row text-center border-top border-bottom py-3 mx-0 mb-3" data-testid="pdp-trust-badges">
                    <div className="col-4 border-right"><i className="ec ec-returning font-size-24 d-block mb-1" /><span className="font-size-12">Kolay İade</span></div>
                    <div className="col-4 border-right"><i className="ec ec-transport font-size-24 d-block mb-1" /><span className="font-size-12">Hızlı Teslimat</span></div>
                    <div className="col-4"><i className="ec ec-payment font-size-24 d-block mb-1" /><span className="font-size-12">Taksitli Ödeme</span></div>
                  </div>

                  {(shipCfg?.showSocialShare !== false) && (
                    <div className="d-flex align-items-center flex-wrap font-size-13" data-testid="pdp-social-share">
                      <span className="text-gray-90 mr-2"><i className="fas fa-share-alt mr-1" /> Paylaş:</span>
                      <a className="btn btn-icon btn-soft-dark btn-xs rounded-circle mr-1" href={`https://wa.me/?text=${enc(product.name + " " + shareUrl)}`} target="_blank" rel="noopener noreferrer" aria-label="WhatsApp'ta paylaş"><i className="fab fa-whatsapp btn-icon__inner" /></a>
                      <a className="btn btn-icon btn-soft-dark btn-xs rounded-circle mr-1" href={`https://twitter.com/intent/tweet?text=${enc(product.name)}&url=${enc(shareUrl)}`} target="_blank" rel="noopener noreferrer" aria-label="X'te paylaş"><i className="fab fa-twitter btn-icon__inner" /></a>
                      <a className="btn btn-icon btn-soft-dark btn-xs rounded-circle mr-1" href={`https://www.facebook.com/sharer/sharer.php?u=${enc(shareUrl)}`} target="_blank" rel="noopener noreferrer" aria-label="Facebook'ta paylaş"><i className="fab fa-facebook-f btn-icon__inner" /></a>
                      <button type="button" className="btn btn-icon btn-soft-dark btn-xs rounded-circle mr-1" onClick={copyLink} aria-label="Bağlantıyı kopyala"><i className="fas fa-link btn-icon__inner" /></button>
                      {typeof navigator !== "undefined" && navigator.share && <button type="button" className="btn btn-link p-0 font-size-13 d-md-none" onClick={nativeShare}>Diğer…</button>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Sekmeler: Birlikte Alınanlar / Açıklama / Özellikler / Kargo & İade / Değerlendirmeler */}
          <div className="mb-8" id="pdp-tabs">
            <div className="position-relative position-md-static px-md-6">
              <ul className="nav nav-classic nav-tab nav-tab-lg justify-content-xl-center flex-nowrap flex-xl-wrap overflow-auto overflow-xl-visble border-0 pb-1 pb-xl-0 mb-n1 mb-xl-0" role="tablist">
                {tabs.map(([key, label]) => (
                  <li className="nav-item flex-shrink-0 flex-xl-shrink-1 z-index-2" key={key}>
                    <a href={`#${key}`} role="tab" aria-selected={activeTab === key} className={`nav-link${activeTab === key ? " active" : ""}`}
                      onClick={(e) => { e.preventDefault(); setPdpTab(key); }} data-testid={`pdp-tab-${key}`}>{label}</a>
                  </li>
                ))}
              </ul>
            </div>
            <div className="borders-radius-17 border p-4 mt-4 mt-md-0 px-lg-10 py-lg-9">
              <div className="tab-content">
                {activeTab === "description" && (
                  <div className="tab-pane fade active show el-prose" role="tabpanel" data-testid="pdp-description"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(product.description) || "<p>Ürün açıklaması bulunmamaktadır.</p>" }} />
                )}
                {activeTab === "specification" && (
                  <div className="tab-pane fade active show" role="tabpanel" data-testid="pdp-specification">
                    <div className="mx-md-5 pt-1">
                      {specGroups.map((g) => (
                        <div key={g.key || g.group} className="mb-4" data-testid={`pdp-spec-group-${g.key || "x"}`}>
                          <h3 className="font-size-18 mb-3">{g.group}</h3>
                          <div className="table-responsive">
                            <table className="table table-hover el-spec-table mb-0">
                              <tbody>
                                {g.rows.map((r, i) => (
                                  <tr key={r.label + i}><th className={`px-4 px-xl-5 font-weight-normal text-gray-90 w-50${i === 0 ? " border-top-0" : ""}`} scope="row">{r.label}</th><td className={`font-weight-bold${i === 0 ? " border-top-0" : ""}`}>{r.value}</td></tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {activeTab === "shipping" && (
                  <div className="tab-pane fade active show" role="tabpanel">
                    <div className="row">
                      <div className="col-md-6 mb-4">
                        <h3 className="font-size-18 mb-3">Kargo ve Teslimat</h3>
                        <p><strong>Ücretsiz Kargo:</strong> {(freeShippingThreshold != null ? Number(freeShippingThreshold) : 4000).toLocaleString("tr-TR")} ₺ ve üzeri siparişlerde kargo ücretsizdir.</p>
                        <p><strong>Hazırlık:</strong> Siparişiniz ödeme onayının ardından 1–2 iş günü içinde kargoya teslim edilir. Büyük hacimli ekipmanlar (lift, kompresör vb.) anlaşmalı nakliye ile gönderilir.</p>
                        <p><strong>Takip:</strong> Kargo takip numaranız SMS ve/veya e-posta ile iletilir.</p>
                      </div>
                      <div className="col-md-6 mb-4">
                        <h3 className="font-size-18 mb-3">İade ve Değişim</h3>
                        {returnPolicyHtml
                          ? <div className="el-prose font-size-14" dangerouslySetInnerHTML={{ __html: sanitizeHtml(returnPolicyHtml) }} />
                          : <p>14 gün içinde iade ve değişim hakkınız bulunmaktadır.</p>}
                      </div>
                    </div>
                  </div>
                )}
                {activeTab === "reviews" && (
                  <div className="tab-pane fade active show" role="tabpanel" id="reviews" data-testid="product-reviews">
                    <div className="row mb-8">
                      <div className="col-md-6">
                        <div className="mb-3">
                          <h3 className="font-size-18 mb-6">{reviewTotal > 0 ? `${reviewTotal} değerlendirmeye göre` : "Henüz değerlendirme yok"}</h3>
                          <h2 className="font-size-30 font-weight-bold text-lh-1 mb-0">{(reviewAvg || 0).toFixed(1)}</h2>
                          <div className="text-lh-1">genel puan</div>
                        </div>
                        <ul className="list-unstyled">
                          {[5, 4, 3, 2, 1].map((n) => {
                            const cnt = reviews.filter((r) => Math.round(r.rating) === n).length;
                            const pct = reviews.length ? Math.round((cnt / reviews.length) * 100) : 0;
                            return (
                              <li className="py-1" key={n}>
                                <div className="row align-items-center mx-gutters-2 font-size-1">
                                  <div className="col-auto mb-2 mb-md-0"><div className="text-warning text-ls-n2 font-size-16" style={{ width: 80 }}>{stars(n)}</div></div>
                                  <div className="col-auto mb-2 mb-md-0"><div className="progress ml-xl-5" style={{ height: 10, width: 200, maxWidth: "50vw" }}><div className="progress-bar" role="progressbar" style={{ width: `${pct}%` }} aria-valuenow={pct} aria-valuemin="0" aria-valuemax="100" /></div></div>
                                  <div className="col-auto text-right"><span className={cnt ? "text-gray-90" : "text-muted"}>{cnt}</span></div>
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                      <div className="col-md-6">
                        <h3 className="font-size-18 mb-5">Değerlendirme Yazın</h3>
                        {rvLoggedIn ? (
                          <div>
                            <div className="row align-items-center mb-4">
                              <div className="col-md-4 col-lg-3"><span className="form-label mb-0">Puanınız</span></div>
                              <div className="col-md-8 col-lg-9">
                                <div className="text-warning text-ls-n2 font-size-20">
                                  {[1, 2, 3, 4, 5].map((i) => (
                                    <button key={i} type="button" className="btn btn-link p-0 text-warning mr-1" onClick={() => setRvRating(i)} aria-label={`${i} yıldız`}>
                                      <i className={i <= rvRating ? "fas fa-star" : "far fa-star"} />
                                    </button>
                                  ))}
                                </div>
                              </div>
                            </div>
                            <div className="form-group mb-3 row">
                              <div className="col-md-4 col-lg-3"><label htmlFor="rvTitle" className="form-label">Başlık</label></div>
                              <div className="col-md-8 col-lg-9"><input id="rvTitle" className="form-control" value={rvTitle} onChange={(e) => setRvTitle(e.target.value)} maxLength={120} placeholder="Opsiyonel" /></div>
                            </div>
                            <div className="form-group mb-3 row">
                              <div className="col-md-4 col-lg-3"><label htmlFor="rvComment" className="form-label">Yorumunuz</label></div>
                              <div className="col-md-8 col-lg-9"><textarea id="rvComment" className="form-control" rows={3} value={rvComment} onChange={(e) => setRvComment(e.target.value)} maxLength={2000} /></div>
                            </div>
                            <div className="row">
                              <div className="offset-md-4 offset-lg-3 col-auto">
                                <button type="button" onClick={submitReview} disabled={rvSubmitting} className="btn btn-primary-dark btn-wide transition-3d-hover">{rvSubmitting ? "Gönderiliyor…" : "Gönder"}</button>
                                <p className="font-size-12 text-gray-90 mt-2 mb-0">Yorumunuz moderasyon sonrası yayınlanır.</p>
                              </div>
                            </div>
                          </div>
                        ) : (
                          <p>Değerlendirme yapmak için <Link to={`/giris?redirect=${encodeURIComponent("/" + (product.slug || product.id))}`} className="text-blue">giriş yapın</Link>.</p>
                        )}
                      </div>
                    </div>
                    {reviews.map((r) => (
                      <div className="border-bottom pb-4 mb-4" key={r.id}>
                        <div className="text-warning text-ls-n2 font-size-16 mb-2">{stars(r.rating)}</div>
                        {r.title && <h4 className="font-size-15 mb-1">{r.title}</h4>}
                        {r.comment && <p className="text-gray-90">{r.comment}</p>}
                        <div className="mb-2">
                          <strong>{r.user_name || "Müşteri"}</strong>
                          {(r.source === "trendyol" || r.verified) && <span className="badge badge-success ml-2">Doğrulanmış Alışveriş</span>}
                          <span className="font-size-13 text-gray-23 ml-2">- {r.created_at ? new Date(r.created_at).toLocaleDateString("tr-TR", { day: "numeric", month: "long", year: "numeric" }) : ""}</span>
                        </div>
                        {r.admin_reply && <div className="ml-3 pl-3 border-left"><div className="font-size-12 font-weight-bold">{SITE_NAME}</div><div className="font-size-13">{r.admin_reply}</div></div>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {similarProducts.length > 0 && shipCfg?.showCompleteLook !== false && (
            <div className="mb-6" data-testid="similar-grid">
              <div className="border-bottom border-color-1 mb-2"><h3 className="section-title mb-0 pb-2 font-size-22">Benzer Ürünler</h3></div>
              <Carousel perView={{ base: 2, md: 3, lg: 4, xl: 5, wd: 6 }} className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
                ariaLabel="Benzer Ürünler"
                dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0">
                {similarProducts.slice(0, 12).map((p, i) => (
                  <div className="js-slide products-group" key={p.id} data-testid={`similar-${p.id}`}>
                    <ProductCard product={p} listName="similar" index={i} innerClassName="product-item__inner px-wd-4 p-2 p-md-3" wishlistLabel="Favori" />
                  </div>
                ))}
              </Carousel>
            </div>
          )}

          {recentItems.length > 0 && (
            <div className="mb-6" data-testid="recently-viewed">
              <div className="border-bottom border-color-1 mb-2"><h3 className="section-title mb-0 pb-2 font-size-22">Son Gezdikleriniz</h3></div>
              <Carousel perView={{ base: 2, md: 3, lg: 4, xl: 5, wd: 7 }} className="position-static overflow-hidden u-slick-overflow-visble pb-7 pt-2 px-1"
                dotsClassName="text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 mt-md-0">
                {recentItems.map((p, i) => (
                  <div className="js-slide products-group" key={p.id} data-testid={`recent-${p.id}`}>
                    <ProductCard product={p} listName="recently_viewed" index={i} innerClassName="product-item__inner px-wd-4 p-2 p-md-3" wishlistLabel="Favori" />
                  </div>
                ))}
              </Carousel>
            </div>
          )}
        </div>

      </main>
      <Footer />
    </div>
  );
}
