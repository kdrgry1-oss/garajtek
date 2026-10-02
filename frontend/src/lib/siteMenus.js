// Vitrin menü grupları (Admin › Tasarım › Menü Yönetimi) — /api/site-menus.
// Gruplar: topbar (üst bar), hamburger (☰ yan menü), departments (Tüm Kategoriler sol menü),
// center (orta menünün sağ yazısı; sekmeler header-menu'de), mobile (mobil menü).
// Tek istek paylaşılır; son yanıt localStorage'da tutulur → ilk karede titreme olmaz.

export const MENU_DEFAULTS = {
  topbar: {
    welcome: "",
    items: [
      { id: "tb-store", label: "Mağazamız", link: "/sayfa/iletisim", icon: "ec ec-map-pointer" },
      { id: "tb-track", label: "Sipariş Takibi", link: "/siparis-takip", icon: "ec ec-transport" },
      { id: "tb-shop", label: "Mağaza", link: "/tum-urunler", icon: "ec ec-shopping-bag" },
      { id: "tb-account", label: "Hesabım", link: "/hesabim", icon: "ec ec-user", special: "account" },
    ],
  },
  departments: {
    mode: "auto",
    max_roots: 14,
    quick: [
      { id: "dq-deals", label: "Günün Fırsatları", link: "/sale", style: "bold" },
      { id: "dq-top", label: "En Çok Satanlar", link: "/tum-urunler?sort=popular&order=desc", style: "bold" },
      { id: "dq-new", label: "Yeni Ürünler", link: "/en-yeniler", style: "bold" },
    ],
    items: [],
  },
  hamburger: {
    mode: "auto",
    quick: [
      { id: "hq-deals", label: "Günün Fırsatları", link: "/sale", style: "bold" },
      { id: "hq-new", label: "Yeni Ürünler", link: "/en-yeniler", style: "bold" },
    ],
    items: [],
    show_account_links: true,
  },
  center: { right_text: "Ücretsiz Kargo Fırsatları", right_link: "/sayfa/kargo-ve-teslimat" },
  mobile: { mode: "same", items: [] },
};

const LS = "site_menus_v1";
let _promise = null;
let _resolved = null;

export function getCachedSiteMenus() {
  if (_resolved) return _resolved;
  try {
    const d = JSON.parse(localStorage.getItem(LS) || "null");
    if (d && typeof d === "object") { _resolved = { ...MENU_DEFAULTS, ...d }; return _resolved; }
  } catch { /* yoksay */ }
  return MENU_DEFAULTS;
}

export function fetchSiteMenus(apiBase, { force = false } = {}) {
  if (force) _promise = null;
  if (!_promise) {
    let tok = null;
    try { tok = localStorage.getItem("token"); } catch { tok = null; }
    _promise = fetch(`${apiBase}/site-menus`, tok ? { headers: { Authorization: `Bearer ${tok}` } } : undefined)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        const out = { ...MENU_DEFAULTS, ...(d && typeof d === "object" ? d : {}) };
        _resolved = out;
        try { localStorage.setItem(LS, JSON.stringify(out)); } catch { /* kota */ }
        return out;
      })
      .catch(() => { _promise = null; return getCachedSiteMenus(); });
  }
  return _promise;
}
