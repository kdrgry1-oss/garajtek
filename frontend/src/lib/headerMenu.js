// Header menüsü — tek kaynak.
// Vitrin Header'ı ve Admin "Menü Yönetimi" sayfası bu varsayılanı paylaşır.
// Panelden kayıt yapıldığında menü /api/page-blocks/header-menu'den gelir;
// kayıt yoksa (veya API'ye ulaşılamazsa) aşağıdaki MİNİMAL, katalogdan bağımsız
// varsayılan kullanılır. Mağazaya özel sekmeler/kolonlar panelden tanımlanır.
// "/en-yeniler", "/tum-urunler" ve "/sale" backend'in sanal kategori slug'larıdır.

export const DEFAULT_MENU_TABS = [
  { id: "yeni", label: "YENİ", type: "link", link: "/en-yeniler", style: "accent", active: true },
  { id: "kategoriler", label: "KATEGORİLER", type: "link", link: "/tum-urunler", style: "normal", active: true },
  { id: "sale", label: "SALE", type: "link", link: "/sale", style: "sale", active: true },
];

// Link'ten ürün-fetch slug'ı türet: "/elbise" → "elbise", "/giyim?kategori=etek" → "etek"
export function slugFromLink(link) {
  const s = String(link || "");
  const m = s.match(/[?&]kategori=([^&#]+)/);
  if (m) return decodeURIComponent(m[1]);
  const seg = s.split("?")[0].split("#")[0].split("/").filter(Boolean).pop();
  return seg || "";
}

// Menü API'den bir kez çekilir, tüm Header mount'ları aynı promise'i paylaşır.
// Üyelere özel kategoriler misafirden gizlendiği için menü OTURUMA göre değişir:
// istek oturum token'ıyla atılır ve önbellek token'a göre ayrılır (girişten sonra üye menüsü).
let _menuPromise = null;
let _menuTokenKey = null;
// SENKRON önbellek (titreme önleme): son gelen menü modülde + localStorage'da tutulur; Header
// İLK karede bununla çizilir. Eskiden her sayfa açılışında önce koddaki varsayılan menü
// (GİYİM/AKSESUAR…) bir kare görünüp sonra panelden gelen menüye dönüyordu.
// Misafir/üye menüsü farklı (üyelere özel kategoriler) → ayrı anahtar.
const _MENU_LS = "hdr_menu_v1";
const _menuResolved = {};
const _audKey = () => {
  try { return localStorage.getItem("token") ? "m" : "g"; } catch { return "g"; }
};
export function getCachedMenu() {
  const k = _audKey();
  if (_menuResolved[k]) return _menuResolved[k];
  try {
    const d = JSON.parse(localStorage.getItem(`${_MENU_LS}:${k}`) || "null");
    if (Array.isArray(d) && d.length) { _menuResolved[k] = d; return d; }
  } catch { /* yoksay */ }
  return null;
}
export function fetchHeaderMenu(apiBase) {
  let tok = null;
  try { tok = localStorage.getItem("token"); } catch { tok = null; }
  if (_menuPromise && _menuTokenKey !== (tok || "")) _menuPromise = null;
  if (!_menuPromise) {
    _menuTokenKey = tok || "";
    const aud = tok ? "m" : "g";
    _menuPromise = fetch(`${apiBase}/page-blocks/header-menu`,
      tok ? { headers: { Authorization: `Bearer ${tok}` } } : undefined)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const tabs = Array.isArray(d?.tabs) ? d.tabs.filter((t) => t && t.label) : [];
        const out = tabs.length ? tabs : DEFAULT_MENU_TABS;
        _menuResolved[aud] = out;
        try { localStorage.setItem(`${_MENU_LS}:${aud}`, JSON.stringify(out)); } catch { /* yoksay */ }
        return out;
      })
      .catch(() => { _menuPromise = null; return getCachedMenu() || DEFAULT_MENU_TABS; });
  }
  return _menuPromise;
}

// Üst duyuru barı (rotating_text) + sayaç sırası — ana sayfa bloklarından okunur ki
// Header'ı kendi başına çağıran TÜM sayfalarda ana sayfadaki üst şerit aynen görünsün.
// Tek istek paylaşılır; 5 dk sonra tazelenir (panelden yapılan değişiklik yansısın).
let _barsPromise = null;
let _barsAt = 0;
const _BARS_LS = "hdr_bars_v1";
let _barsResolved = null;
export function getCachedBars() {
  if (_barsResolved) return _barsResolved;
  try {
    const d = JSON.parse(localStorage.getItem(_BARS_LS) || "null");
    if (d && typeof d === "object") { _barsResolved = d; return d; }
  } catch { /* yoksay */ }
  return null;
}
export function fetchTopBars(apiBase) {
  if (!_barsPromise || Date.now() - _barsAt > 5 * 60 * 1000) {
    _barsAt = Date.now();
    _barsPromise = fetch(`${apiBase}/page-blocks?page=home`)
      .then((r) => (r.ok ? r.json() : []))
      .then((list) => {
        const blocks = (Array.isArray(list) ? list : []).filter((b) => b && b.is_active);
        const rotating = blocks.find((b) => b.type === "rotating_text") || null;
        const countdown = blocks.find((b) => b.type === "countdown_bar") || null;
        const announcementFirst = !!(rotating && countdown)
          && (Number(rotating.sort_order ?? 0) < Number(countdown.sort_order ?? 0));
        // "Tüm sayfalarda footer üstünde göster" açık marka şeridi (brands_carousel.show_on_all_pages)
        const brands = blocks.find((b) => b.type === "brands_carousel" && b.settings && b.settings.show_on_all_pages) || null;
        const out = { rotating, announcementFirst, brands };
        _barsResolved = out;
        try { localStorage.setItem(_BARS_LS, JSON.stringify(out)); } catch { /* yoksay */ }
        return out;
      })
      .catch(() => { _barsPromise = null; return { rotating: null, announcementFirst: false }; });
  }
  return _barsPromise;
}

// SALE menüsü (SALE sekmesinin açılır listesi) — Admin › Kampanyalar › SALE Menüsü'nden.
// Yayında olmayan kampanyalar sunucuda zaten süzülür. Tek istek paylaşılır; 5 dk'da tazelenir.
let _saleMenuPromise = null;
let _saleMenuAt = 0;
export function fetchSaleMenu(apiBase) {
  if (!_saleMenuPromise || Date.now() - _saleMenuAt > 5 * 60 * 1000) {
    _saleMenuAt = Date.now();
    _saleMenuPromise = fetch(`${apiBase}/sale-menu`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => (Array.isArray(d?.items) ? d.items.filter((i) => i && i.label && i.url) : []))
      .catch(() => { _saleMenuPromise = null; return []; });
  }
  return _saleMenuPromise;
}
