// Ürün Setleri — sepet/çekmece/kasa parçaları (Electro görünümü).
// Sepette setin kalemleri bir başlık altında gruplanır; stokta olmayan bileşen satın alınamaz
// ve "Bu ürünü değiştir" kutusuyla gösterilir. Kural: lib/productSets.js.
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useCart } from "../../context/CartContext";
import { optimizeImg } from "../../lib/img";
import { priceView } from "../../lib/price";
import { replaceHref, writeReplaceCtx } from "../../lib/productSets";
import { fmtPrice } from "../electro/format";
import "./sets.css";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const isGroupStart = (item, prev) => !!item?.setId && prev?.setId !== item.setId;
const isGroupEnd = (item, next) => !!item?.setId && next?.setId !== item.setId;

function useStartReplace() {
  const navigate = useNavigate();
  const { setIsOpen } = useCart();
  return (line) => {
    writeReplaceCtx({
      lineId: line.id, setId: line.setId, slot: line.setSlot, setName: line.setName,
      productName: line.name, categoryId: line.replaceCategory?.id || null,
      categorySlug: line.replaceCategory?.slug || "", categoryName: line.replaceCategory?.name || "",
    });
    setIsOpen(false);
    navigate(replaceHref(line));
  };
}

export const OOS_MESSAGE = "Bu ürün stokta bulunmamaktadır. Başka bir ürünle değiştirmek ister misiniz?";
export const DISCONTINUED_MESSAGE = "Bu ürün artık satışta değil. Başka bir ürünle değiştirmek ister misiniz?";

/** Aynı en alt kategoriden stoklu öneriler (sözleşme 7.4) — seçilen ürün kalemin yerine geçer. */
function Alternatives({ line, limit }) {
  const { replacePending } = useCart();
  const navigate = useNavigate();
  const [rows, setRows] = useState(null);
  useEffect(() => {
    if (typeof fetch !== "function") return undefined;
    let alive = true;
    fetch(`${API}/storefront/alternatives?product_id=${encodeURIComponent(line.productId)}&limit=${limit}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (alive) setRows((d && d.items) || []); })
      .catch(() => { if (alive) setRows([]); });
    return () => { alive = false; };
  }, [line.productId, limit]);
  if (!rows || !rows.length) return null;
  const pick = (p) => {
    const vs = (p.variants || []).filter((v) => v && v.id && Number(v.stock) > 0);
    if ((p.variants || []).length > 1) {
      // Seçenek gerektiren ürün: ürün sayfasında seçilip eklenince yuvaya yazılır
      writeReplaceCtx({ lineId: line.id, setId: line.setId || null, slot: line.setSlot || null, setName: line.setName || "",
        productName: line.name, categoryId: line.replaceCategory?.id || null,
        categorySlug: line.replaceCategory?.slug || "", categoryName: line.replaceCategory?.name || "" });
      navigate(`/${p.slug || p.id}`);
      return;
    }
    if (replacePending(line.id, p, vs[0] || null)) {
      try { toast.success(`${line.name} yerine ${p.name} sepete eklendi`); } catch { /* yoksay */ }
    }
  };
  return (
    <div className="gt-alt" data-testid={`alternatives-${line.productId}`}>
      <div className="gt-alt-title">Stokta olan benzer ürünler</div>
      <div className="gt-alt-row">
        {rows.map((p) => {
          const pv = priceView(p);
          return (
            <div key={p.id} className="gt-alt-card" data-testid={`alt-${p.id}`}>
              <img src={optimizeImg(p.images?.[0], 160) || "/placeholder.jpg"} alt={p.name} width="64" height="64" loading="lazy" />
              <div className="gt-alt-name" title={p.name}>{p.name}</div>
              <div className="gt-alt-price">{fmtPrice(pv.display)}</div>
              <button type="button" className="btn btn-xs btn-primary-dark-w gt-alt-pick" onClick={() => pick(p)} data-testid={`alt-pick-${p.id}`}>Bununla değiştir</button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/** Tükenen kalem kutusu (set bileşeni ya da sonradan tükenen herhangi bir kalem) — sepet,
 *  çekmece ve kasa ortak. Mesaj sözleşme 7.4 metnidir; öneriler aynı en alt kategoriden gelir. */
export function PendingLineBox({ line, compact = false }) {
  const { removeItem } = useCart();
  const startReplace = useStartReplace();
  const testKey = line.setSlot || line.productId;
  return (
    <div className={`gt-set-pending${compact ? " is-compact" : ""}`} data-testid={`set-pending-${testKey}`}>
      <img src={optimizeImg(line.image, 120) || "/placeholder.jpg"} alt={line.name} width="56" height="56" loading="lazy" />
      <div className="gt-set-pending-body">
        <div className="gt-set-pending-name">{line.name}</div>
        <div className="gt-set-pending-msg" data-testid="oos-message"><i className="fas fa-exclamation-triangle mr-1" />{line.discontinued ? DISCONTINUED_MESSAGE : OOS_MESSAGE}</div>
        {line.setId && <div className="font-size-12 text-gray-90 mb-1">“{line.setName}” setinin parçası — değiştirdiğiniz ürünle set indirimi korunur.</div>}
        <div className="gt-set-pending-actions">
          <button type="button" className="btn btn-primary-dark-w btn-xs gt-set-replace-btn" onClick={() => startReplace(line)}
            data-testid={`set-replace-${testKey}`}>
            <i className="fas fa-exchange-alt mr-1" />Bu ürünü değiştir
          </button>
          <button type="button" className="btn btn-link btn-xs text-gray-90 p-0 ml-2" onClick={() => removeItem(line.id)}
            data-testid={`set-pending-remove-${testKey}`}>{line.setId ? "Setten çıkar" : "Sepetten çıkar"}</button>
        </div>
        {line.replaceCategory?.name && !compact && (
          <div className="font-size-12 text-gray-5 mt-1">{line.replaceCategory.name} kategorisinden başka bir ürün seçebilirsiniz.</div>
        )}
        <Alternatives line={line} limit={compact ? 3 : 6} />
      </div>
    </div>
  );
}

/** Sepet tablosu: set başlığı satırı (grubun ilk kalemi önünde). */
export function SetGroupHeaderRow({ item, prev, colSpan = 6 }) {
  const { pendingItems = [] } = useCart();
  if (!isGroupStart(item, prev)) return null;
  const missing = pendingItems.filter((p) => p.setId === item.setId).length;
  return (
    <tr className="gt-set-head-row" data-testid={`set-group-${item.setId}`}>
      <td colSpan={colSpan}>
        <div className="gt-set-head">
          <span className="gt-set-badge">SET</span>
          <Link to={`/${item.setSlug || item.setId}`} className="gt-set-title">{item.setName}</Link>
          {missing > 0
            ? <span className="gt-set-note text-red">{missing} ürün değiştirilmeli — set indirimi tamamlanınca uygulanır</span>
            : <span className="gt-set-note text-green">Set indirimi sepet toplamında uygulanır</span>}
        </div>
      </td>
    </tr>
  );
}

/** Sepet tablosu: grubun son kaleminden sonra bekleyen bileşen satırları. */
export function SetPendingRows({ item, next, colSpan = 6, orphans = false }) {
  const { pendingItems = [], items = [] } = useCart();
  let list = [];
  if (orphans) {
    const live = new Set(items.map((i) => i.setId).filter(Boolean));
    list = pendingItems.filter((p) => !live.has(p.setId));
  } else if (isGroupEnd(item, next)) {
    list = pendingItems.filter((p) => p.setId === item.setId);
  }
  if (!list.length) return null;
  return list.map((line) => (
    <tr key={line.id} className="gt-set-pending-row" data-testid={`cart-pending-${line.id}`}>
      <td colSpan={colSpan}><PendingLineBox line={line} /></td>
    </tr>
  ));
}

/** Sepet üstü bilgi şeridi: bekleyen bileşen varsa kasaya geçmeden önce uyarır. */
export function SetPendingNotice({ className = "mb-4" }) {
  const { pendingItems = [], refreshStock } = useCart();
  useEffect(() => { if (refreshStock) refreshStock(); }, [refreshStock]); // sepet/çekmece açılınca stok tazele
  if (!pendingItems.length) return null;
  return (
    <div className={`gt-set-notice ${className}`} role="status" data-testid="set-pending-notice">
      <i className="fas fa-info-circle mr-2" />
      Sepetinizdeki <strong>{pendingItems.length}</strong> ürün stokta bulunmamaktadır. Ödemeye geçmeden önce
      başka bir ürünle değiştirin ya da sepetten çıkarın.
    </div>
  );
}

/** Mini sepet (çekmece) için başlık + bekleyen kalemler. */
export function MiniSetHeader({ item, prev }) {
  if (!isGroupStart(item, prev)) return null;
  return (
    <li className="gt-set-mini-head" data-testid={`mini-set-group-${item.setId}`}>
      <span className="gt-set-badge">SET</span> {item.setName}
    </li>
  );
}

export function MiniSetPending({ item, next, orphans = false }) {
  const { pendingItems = [], items = [] } = useCart();
  let list = [];
  if (orphans) {
    const live = new Set(items.map((i) => i.setId).filter(Boolean));
    list = pendingItems.filter((p) => !live.has(p.setId));
  } else if (isGroupEnd(item, next)) {
    list = pendingItems.filter((p) => p.setId === item.setId);
  }
  return list.map((line) => (
    <li key={line.id} className="mb-3"><PendingLineBox line={line} compact /></li>
  ));
}

/** Kasa: bekleyen bileşen varken sipariş verilemez — kullanıcı değiştirir ya da çıkarır. */
export function SetPendingGuard() {
  const { pendingItems = [], removeItem, refreshStock } = useCart();
  useEffect(() => { if (refreshStock) refreshStock(); }, [refreshStock]); // kasada son stok kontrolü
  if (!pendingItems.length) return null;
  return (
    <div className="gt-set-guard" role="alert" data-testid="checkout-set-guard">
      <p className="gt-set-guard-title"><strong>Sepetinizdeki {pendingItems.length} ürün stokta bulunmamaktadır.</strong></p>
      <p className="gt-set-guard-text">Başka bir ürünle değiştirin ya da bu ürün(ler) olmadan devam edin. Set ürünlerinde set indirimi yalnız set tamamken uygulanır.</p>
      {pendingItems.map((l) => <PendingLineBox key={l.id} line={l} compact />)}
      <div className="gt-set-guard-actions">
        <Link to="/sepet" className="gt-btn-secondary" data-testid="guard-back-to-cart">Sepete dön</Link>
        <button type="button" className="gt-btn-link" onClick={() => pendingItems.forEach((l) => removeItem(l.id))}
          data-testid="guard-remove-pending">Bu ürün(ler) olmadan devam et</button>
      </div>
    </div>
  );
}

/** Kasa sipariş özeti kalemi altında set etiketi. */
export function SetLineTag({ item }) {
  if (!item?.setId) return null;
  return (
    <p className="gt-line-set" data-testid="summary-set-tag">
      <span className="gt-set-badge">SET</span> {item.setName}
      {item.replacedFrom ? <span className="gt-line-set-repl"> · {item.replacedFrom} yerine</span> : null}
    </p>
  );
}
