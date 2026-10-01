// Checkout yardımcıları — saf fonksiyonlar (UI'dan bağımsız, test edilebilir).

// Para biçimi (Shopify TR görünümü): ₺3.699,50
export function formatTRY(value) {
  const n = Number(value) || 0;
  const neg = n < 0;
  const [int, dec] = Math.abs(n).toFixed(2).split(".");
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${neg ? "-" : ""}₺${grouped},${dec}`;
}

// Telefon alanı: yalnızca rakam (ve baştaki tek +) kabul edilir — harf/sembol engellenir
export const sanitizePhone = (v) => {
  const raw = (v || "").replace(/[^\d+]/g, "");
  const plus = raw.startsWith("+") ? "+" : "";
  const digits = raw.replace(/\+/g, "").slice(0, 15);
  return plus + digits;
};

// Tahmini teslimat aralığı (iş günü bazlı; hafta sonu atlanır) — TR pazarı dönüşüm sinyali
export function estimateDelivery(minDays = 2, maxDays = 4, now = new Date()) {
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
  return `${fmt(addBiz(now, minDays))} - ${fmt(addBiz(now, maxDays))}`;
}

// Kodu HARF-DUYARSIZ + TÜRKÇE-I DUYARSIZ tek forma indir (İ/ı → I). Böylece 'HOSGELDİN',
// 'hosgeldin', 'hosgeldın' hepsi kayıtlı 'HOSGELDIN' ile eşleşir (kullanıcı isteği).
export const foldCode = (s) => {
  const folded = (s || "").trim()
    .replace(/[İı]/g, "I").replace(/[Şş]/g, "S").replace(/[Ğğ]/g, "G")
    .replace(/[Üü]/g, "U").replace(/[Öö]/g, "O").replace(/[Çç]/g, "C")
    .toUpperCase();
  const compact = folded.replace(/[\s_-]+/g, "");
  return ["HOSGELDIN", "HOSGELDIN10"].includes(compact) ? "HOSGELDIN10" : folded;
};

// TCKN algoritma kontrolü (11 hane, ilk hane 0 olamaz, 10. ve 11. hane kontrol basamakları).
export function isValidTCKN(value) {
  const s = String(value || "");
  if (!/^[1-9]\d{10}$/.test(s)) return false;
  const d = s.split("").map(Number);
  const odd = d[0] + d[2] + d[4] + d[6] + d[8];
  const even = d[1] + d[3] + d[5] + d[7];
  const d10 = (((odd * 7) - even) % 10 + 10) % 10;
  const d11 = (d.slice(0, 10).reduce((a, b) => a + b, 0)) % 10;
  return d[9] === d10 && d[10] === d11;
}

// Sepet satırlarını analytics (pixel/dataLayer) için ortak biçime çevirir.
export function analyticsItems(items, brand) {
  return (items || []).map((it) => ({
    product_id: it.productId, name: it.name, price: it.price, quantity: it.quantity,
    category: it.category || it.categoryName || "",
    sku: it.sku || it.stockCode || "",
    size: it.size || "", color: it.color || "",
    list_price: it.list_price || it.price,
    sale_price: it.sale_price || it.price,
    brand: it.brand || brand,
    breadcrumb: it.breadcrumb || "",
  }));
}

// Kart numarasından marka tespiti (yalnız görsel vurgu için).
export function detectCardBrand(number) {
  const n = String(number || "").replace(/\D/g, "");
  if (/^4/.test(n)) return "visa";
  if (/^(5[1-5]|2(2[2-9]|[3-6]\d|7[01]|720))/.test(n)) return "mastercard";
  if (/^9792|^65/.test(n)) return "troy";
  if (/^3[47]/.test(n)) return "amex";
  return "";
}

export const ADDRESS_REQUIRED = ["first_name", "last_name", "address", "city", "district", "phone"];

// Adres alanlarını doğrular; { alan: mesaj } döner.
export function validateAddress(a, prefix) {
  const errs = {};
  const msgs = {
    first_name: "Ad girin",
    last_name: "Soyad girin",
    address: "Adres girin",
    city: "İl seçin",
    district: "İlçe seçin",
    phone: "Telefon numarası girin",
  };
  ADDRESS_REQUIRED.forEach((k) => {
    if (!String((a && a[k]) || "").trim()) errs[`${prefix}.${k}`] = msgs[k];
  });
  const digits = String((a && a.phone) || "").replace(/\D/g, "");
  if (!errs[`${prefix}.phone`] && digits.length < 10) {
    errs[`${prefix}.phone`] = "Geçerli bir telefon numarası girin (en az 10 hane)";
  }
  return errs;
}

// "Apartman, daire" opsiyonel satırını tek adres alanına birleştirir (backend tek alan bekler).
export function mergeAddressLine(a) {
  if (!a) return a;
  const { address2, ...rest } = a;
  const extra = String(address2 || "").trim();
  return extra ? { ...rest, address: `${String(rest.address || "").trim()} ${extra}`.trim() } : rest;
}
