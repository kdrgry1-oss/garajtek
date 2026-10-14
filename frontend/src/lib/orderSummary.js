/**
 * Sipariş özeti yardımcıları — sipariş başarı sayfası ve Hesabım › Siparişlerim kartı.
 *
 * Sunucu toplamı şöyle kuruyor (backend/routes/orders.py create_order):
 *   total = subtotal − indirimler + kargo + gift_wrap_price + cod_fee
 * Özet yalnız ara toplam / indirim / kargo gösterirse satırlar toplamı tutmaz;
 * hediye paketi ve kapıda ödeme hizmet bedeli de ayrı satır olarak gösterilmeli.
 */

const _num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

/** Kargodan sonra, Toplam'dan önce gösterilecek ek ücret satırları (yalnız > 0 olanlar). */
export function orderExtraFeeRows(order) {
  const rows = [];
  const gift = _num(order?.gift_wrap_price);
  if (gift > 0) rows.push({ key: "gift_wrap", label: "Hediye Paketi", amount: gift });
  const cod = _num(order?.cod_fee);
  if (cod > 0) rows.push({ key: "cod_fee", label: "Kapıda Ödeme Hizmet Bedeli", amount: cod });
  return rows;
}

/**
 * Başarı sayfası alt metni: e-posta yoksa "e-postanıza gönderildi" denmez
 * (kapıda ödeme hızlı siparişinde e-posta isteğe bağlı).
 * by-number ucu e-postayı maskeli döndürür ("ab***@x.com") — boş değilse adres vardır.
 */
export function orderHasEmail(order) {
  const e = String(order?.shipping_address?.email || order?.email || "").trim();
  return e.includes("@");
}
