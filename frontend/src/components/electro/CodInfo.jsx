// Kapıda ödeme görünürlüğü — ürün sayfası satırı, ürün kartı rozeti, sepet notu.
// Kapıda ödeme kapalıysa (ayarlar) hiçbiri görünmez. Kurallar: backend/cod_rules.py
import { useCodCheck, useCodInfo, productCodAllowed } from "../../lib/cod";
import { fmtPrice } from "./format";
import "../sets/sets.css";

const feeText = (fee) => (Number(fee) > 0 ? `+${fmtPrice(fee)} hizmet bedeli` : "ek ücret yok");

function limitsText(info) {
  const min = Number(info?.min_total) || 0;
  const max = Number(info?.max_total) || 0;
  if (min && max) return `${fmtPrice(min)} – ${fmtPrice(max)} arası siparişlerde`;
  if (min) return `${fmtPrice(min)} ve üzeri siparişlerde`;
  if (max) return `${fmtPrice(max)} tutarına kadar siparişlerde`;
  return "";
}

/** Ürün sayfası: fiyat/sepete ekle yakınında "Kapıda Ödeme" bilgi satırı. */
export function CodInfoRow({ product }) {
  const info = useCodInfo();
  const ids = product?.product_type === "set"
    ? (product.set_items || []).map((i) => i.product_id)
    : [product?.id];
  const price = Number(product?.sale_price) > 0 && Number(product?.sale_price) < Number(product?.price)
    ? Number(product.sale_price) : Number(product?.price) || 0;
  // Ürün tek başına alt sınırın altında olsa da sepet toplamı yetebilir → limit kontrolünü
  // ürün sayfasında yalnız bilgi olarak gösteririz; ürün/kategori kapatması ise kesindir.
  const check = useCodCheck(info?.enabled ? ids : [], Math.max(price, Number(info?.min_total) || 0));
  if (!info || !info.enabled || !product) return null;
  const blocked = check.available === false && (check.blocked || []).length > 0;
  if (blocked) {
    return (
      <p className="el-cod-row is-off font-size-13 text-gray-90 mb-3" data-testid="pdp-cod-unavailable">
        <i className="fas fa-hand-holding-usd mr-2" />
        {product.product_type === "set" ? "Bu sette kapıda ödemeye uygun olmayan ürün var" : "Bu ürün kapıda ödemeye uygun değildir"} (kart veya havale/EFT ile ödenebilir).
      </p>
    );
  }
  const lim = limitsText(info);
  return (
    <div className="el-cod-row d-flex align-items-start mb-3" data-testid="pdp-cod-row">
      <span className="el-cod-ico"><i className="fas fa-hand-holding-usd" /></span>
      <div>
        <div className="font-size-14"><strong>Kapıda Ödeme</strong> <span className="text-gray-90">— {feeText(info.fee)}</span></div>
        <div className="font-size-12 text-gray-5">
          Nakit veya kartla teslimatta ödeyin{lim ? ` · ${lim}` : ""}.
        </div>
      </div>
    </div>
  );
}

/** Ürün kartı: küçük "Kapıda Ödeme" rozeti (İşletme Kuralları'ndan kapatılabilir). */
export function CodBadge({ product, className = "" }) {
  const info = useCodInfo();
  if (!info || !info.enabled || info.card_badge === false) return null;
  if (product?.product_type === "set") return null; // set uygunluğu bileşenlere bağlı — sayfada gösterilir
  if (!productCodAllowed(product, info)) return null;
  return (
    <span className={`el-cod-badge ${className}`} data-testid={`cod-badge-${product.id}`} title={`Kapıda ödeme: ${feeText(info.fee)}`}>
      <i className="fas fa-hand-holding-usd mr-1" />Kapıda Ödeme
    </span>
  );
}

/** Sepet özeti: "Kapıda ödeme seçeneği mevcut" / uygun değilse nedeni. */
export function CartCodNote({ items, total }) {
  const info = useCodInfo();
  const ids = (items || []).map((i) => i.productId);
  const check = useCodCheck(info?.enabled ? ids : [], total);
  if (!info || !info.enabled || check.available === null) return null;
  return check.available ? (
    <p className="font-size-13 text-green mb-2" data-testid="cart-cod-available">
      <i className="fas fa-hand-holding-usd mr-1" />Kapıda ödeme seçeneği mevcut ({feeText(info.fee)}).
    </p>
  ) : (
    <p className="font-size-12 text-gray-90 mb-2" data-testid="cart-cod-unavailable">
      <i className="fas fa-hand-holding-usd mr-1" />{check.reason}
    </p>
  );
}
