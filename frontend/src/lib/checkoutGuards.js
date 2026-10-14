/**
 * Kasa (Checkout) koruma yardımcıları — saf fonksiyonlar, jest ile test edilir.
 */

// ── ÇİFT SİPARİŞ KORUMASI: idempotency anahtarı deposu ──
// Anahtar sepet imzasına bağlı ve localStorage'da tutulur: sessionStorage sekmeye özel
// olduğu için aynı sepetle açılan ikinci /odeme sekmesi YENİ anahtar üretip ikinci bir
// sipariş açıyordu. localStorage tüm sekmelerde ortak → aynı sepet = aynı anahtar →
// sunucu mevcut siparişi döndürür. Unutulmuş eski anahtar günler sonra aynı sepetle
// eski (ödenmemiş) siparişi döndürmesin diye anahtar IDEM_TTL_MS sonra yenilenir.
export const IDEM_PREFIX = "store_idem_";
export const IDEM_TTL_MS = 24 * 60 * 60 * 1000;

export function getIdemKey(storage, storeKey, makeKey, now = Date.now()) {
  try {
    const raw = storage.getItem(storeKey);
    if (raw) {
      try {
        const v = JSON.parse(raw);
        if (v && typeof v.k === "string" && v.k && now - Number(v.t || 0) < IDEM_TTL_MS) return v.k;
      } catch { /* eski düz metin kayıt → yenile */ }
    }
    const k = makeKey();
    storage.setItem(storeKey, JSON.stringify({ k, t: now }));
    return k;
  } catch {
    return makeKey();
  }
}

export function clearIdemKeys(storage) {
  try {
    const rm = [];
    for (let i = 0; i < storage.length; i++) {
      const key = storage.key(i);
      if (key && key.indexOf(IDEM_PREFIX) === 0) rm.push(key);
    }
    rm.forEach((k) => storage.removeItem(k));
  } catch { /* yoksay */ }
}

// Bayat sekme: bu sekmenin bellekteki sepeti dolu ama ortak localStorage "cart" boş →
// sepet başka bir sekmede siparişe dönüştürülüp temizlenmiş. (CartContext her değişikliği
// localStorage'a yazdığından aynı sekmede bu durum oluşmaz.)
export function cartClearedElsewhere(storage, itemCount) {
  if (!itemCount) return false;
  try {
    const raw = storage.getItem("cart");
    if (raw == null) return false;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length === 0;
  } catch {
    return false;
  }
}

// ── Ödeme yöntemi ──
export const PM_ORDER = ["credit_card", "bank_transfer", "cash_on_delivery"];

/** Seçili yöntem kullanılabilir değilse ilk kullanılabilir yöntem; hiçbiri yoksa "". */
export function resolvePaymentMethod(current, pmAvail) {
  if (current && pmAvail?.[current]) return current;
  return PM_ORDER.find((k) => pmAvail?.[k]) || "";
}
