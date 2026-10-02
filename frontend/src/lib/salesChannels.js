// Satış kanalları (tek kaynak) — backend/sales_channels.py ile aynı kural.
// Mağazanın tek satış kanalı web sitesidir. platform / marketplace alanı boş, "web" veya
// "site" olan sipariş site siparişidir; başka bir değer taşıyan (geçmişten kalan) kayıtlar
// adı verilmeden "Diğer kanal" olarak gösterilir.
export const SITE_VALUES = ["", "web", "site", "website", "online", "manual", "admin"];
export const SITE_LABEL = "Web Sitesi";
export const OTHER_LABEL = "Diğer kanal";

const lc = (v) => String(v ?? "").trim().toLowerCase();

export const isSiteValue = (v) => SITE_VALUES.includes(lc(v));

/** Sipariş site dışı (geçmişten kalan) bir kanala mı ait? */
export const isOtherChannelOrder = (o) =>
  !!o && !(isSiteValue(o.platform) && isSiteValue(o.marketplace));

/** "site" | "other" anahtarı ya da ham değer → görünen ad. */
export const channelLabel = (v) => (v === "site" || isSiteValue(v) ? SITE_LABEL : OTHER_LABEL);

/** Sipariş satırı rozeti. */
export const channelBadge = (o) =>
  isOtherChannelOrder(o)
    ? { label: OTHER_LABEL, bg: "bg-gray-500" }
    : { label: "Web", bg: "bg-gray-800" };
