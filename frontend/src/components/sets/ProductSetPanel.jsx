// Ürün sayfası — set ürünü ise bileşen listesi, "ayrı ayrı alırsanız / set fiyatı" özeti ve
// "Seti Sepete Ekle" düğmesi (tüm bileşenler ayrı kalem olarak, set başlığı altında eklenir).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { useCart } from "../../context/CartContext";
import { optimizeImg } from "../../lib/img";
import { fmtPrice } from "../electro/format";
import "./sets.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ProductSetPanel({ product }) {
  const isSet = product?.product_type === "set";
  const { addSet } = useCart();
  const [data, setData] = useState(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (!isSet || !product?.id) return undefined;
    let alive = true;
    fetch(`${API}/product-sets/${encodeURIComponent(product.id)}`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((d) => { if (alive) setData(d); })
      .catch(() => { if (alive) setErr(true); });
    return () => { alive = false; };
  }, [isSet, product?.id]);

  if (!isSet) return null;
  if (err) return <p className="text-red font-size-14">Set içeriği yüklenemedi.</p>;
  if (!data) return <div className="gt-set-panel is-loading" data-testid="set-panel-loading">Set içeriği yükleniyor…</div>;

  const { components = [], pricing = {} } = data;
  const anyInStock = components.some((c) => c.in_stock);
  const onAdd = () => {
    const n = addSet(data, 1);
    if (n) {
      toast.success(pricing.missing_count
        ? `${data.set.name} sepete eklendi — ${pricing.missing_count} ürünü sepette değiştirin`
        : `${data.set.name} sepete eklendi`);
    }
  };

  return (
    <div className="gt-set-panel mb-4" data-testid="set-panel">
      <div className="gt-set-panel-head">
        <span className="gt-set-badge">SET</span>
        <h3 className="font-size-16 font-weight-bold mb-0">Set içeriği ({components.length} ürün)</h3>
      </div>
      <ul className="gt-set-list list-unstyled mb-0">
        {components.map((c) => (
          <li key={c.product_id} className="gt-set-item" data-testid={`set-component-${c.product_id}`}>
            <Link to={`/${c.slug}`} className="gt-set-thumb">
              <img src={optimizeImg(c.image, 120) || "/placeholder.jpg"} alt={c.name} width="56" height="56" loading="lazy" />
            </Link>
            <div className="gt-set-info">
              <Link to={`/${c.slug}`} className="gt-set-name">{c.name}</Link>
              <div className="font-size-12 text-gray-5">
                {c.quantity > 1 ? `${c.quantity} adet · ` : ""}{c.variant?.size ? `${c.variant.size} · ` : ""}
                {c.in_stock
                  ? <span className="gt-stock is-in">Stokta</span>
                  : <span className="gt-stock is-out" data-testid={`set-oos-${c.product_id}`}>Tükendi — sepette değiştirilebilir</span>}
              </div>
            </div>
            <div className="gt-set-price">
              {c.list_unit_price > c.unit_price && <del>{fmtPrice(c.list_unit_price * c.quantity)}</del>}
              <span>{fmtPrice(c.unit_price * c.quantity)}</span>
            </div>
          </li>
        ))}
      </ul>
      <div className="gt-set-sum">
        <div className="gt-set-sum-row"><span>Ayrı ayrı alırsanız</span><del data-testid="set-separate-total">{fmtPrice(pricing.components_total)}</del></div>
        <div className="gt-set-sum-row is-main"><span>Set fiyatı</span><strong data-testid="set-price">{fmtPrice(pricing.set_price)}</strong></div>
        {pricing.savings > 0 && (
          <div className="gt-set-sum-row text-green"><span>Set avantajı (%{pricing.discount_pct})</span><span data-testid="set-savings">-{fmtPrice(pricing.savings)}</span></div>
        )}
        {pricing.missing_count > 0 && (
          <p className="gt-set-sum-note" data-testid="set-missing-note">
            {pricing.missing_count} ürün şu an stokta yok: sepette “Bu ürünü değiştir” ile aynı kategoriden başka bir ürün seçebilirsiniz.
            Set indirimi, set tamamlandığında uygulanır.
          </p>
        )}
      </div>
      <button type="button" className="btn btn-primary-dark-w btn-block mt-3 gt-set-add" onClick={onAdd} disabled={!anyInStock}
        data-testid="set-add-to-cart">
        <i className="ec ec-add-to-cart mr-2 font-size-20" />Seti Sepete Ekle
      </button>
    </div>
  );
}
