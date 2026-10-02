// "Bu ürünü değiştir" bağlamı: ?degistir=<setId>:<ürünId> ile açılan kategori sayfasında (ve
// müşteri ürün sayfasına geçse de) üstte şerit gösterir. Bu sırada sepete eklenen, o kategoriden
// ilk ürün setin boş yuvasına yazılır (CartContext.addItem). Uygulama genelinde bir kez bağlanır.
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useCart } from "../../context/CartContext";
import { clearReplaceCtx, findPendingByParam, readReplaceCtx, writeReplaceCtx } from "../../lib/productSets";
import "./sets.css";

export default function SetReplaceBanner() {
  const location = useLocation();
  const { pendingItems = [] } = useCart();
  const [ctx, setCtx] = useState(() => readReplaceCtx());

  useEffect(() => {
    const sync = () => setCtx(readReplaceCtx());
    window.addEventListener("set-replace-ctx", sync);
    return () => window.removeEventListener("set-replace-ctx", sync);
  }, []);

  // URL parametresinden bağlamı kur (link paylaşıldı / sayfa yenilendi).
  useEffect(() => {
    const raw = new URLSearchParams(location.search).get("degistir");
    if (!raw) return;
    const line = findPendingByParam(pendingItems, raw);
    if (line && (!ctx || ctx.lineId !== line.id)) {
      writeReplaceCtx({
        lineId: line.id, setId: line.setId, slot: line.setSlot, setName: line.setName, productName: line.name,
        categoryId: line.replaceCategory?.id || null, categorySlug: line.replaceCategory?.slug || "",
        categoryName: line.replaceCategory?.name || "",
      });
    }
  }, [location.search, pendingItems, ctx]);

  // Yuva doldu / kalem silindi → bağlamı kapat.
  useEffect(() => {
    if (ctx && !pendingItems.some((p) => p.id === ctx.lineId)) clearReplaceCtx();
  }, [ctx, pendingItems]);

  if (!ctx || location.pathname.startsWith("/odeme") || location.pathname.startsWith("/admin")) return null;
  const onCategory = ctx.categorySlug && location.pathname === `/${ctx.categorySlug}`;
  return (
    <div className="gt-set-replace-banner" role="status" data-testid="set-replace-banner">
      <div className="container d-flex align-items-center flex-wrap">
        <i className="fas fa-exchange-alt mr-2" />
        <span className="mr-2">
          {ctx.setName
            ? <><strong>{ctx.setName}</strong> setini tamamlamak için </>
            : <>Stokta olmayan <strong>{ctx.productName}</strong> yerine </>}
          {onCategory ? "bu kategoriden" : <>“{ctx.categoryName || "ilgili"}” kategorisinden</>} bir ürün seçin
          {ctx.setName && <span className="d-none d-md-inline"> — stokta olmayan: {ctx.productName}</span>}.
        </span>
        {!onCategory && ctx.categorySlug && <Link to={`/${ctx.categorySlug}`} className="gt-set-replace-link mr-2">Kategoriye git</Link>}
        <button type="button" className="gt-set-replace-cancel ml-auto" onClick={clearReplaceCtx} data-testid="set-replace-cancel">Vazgeç</button>
      </div>
    </div>
  );
}
