// Electro ürün kartı ("product-item__outer / __inner / __body / __footer").
// Varyantlar:
//   grid     → vitrin/kategori ızgarası (varsayılan)
//   card     → yatay kart (Electro "Bestsellers" — product-item__card)
//   list     → küçük liste (footer "Öne Çıkanlar/İndirimdekiler" — product-item__list)
//   listview → kategori sayfası liste görünümü (açıklama + sağda fiyat/sepete ekle)
// Mevcut davranışlar korunur: sepete ekle (varyant seçimi gerekiyorsa ürüne yönlendirir),
// favori, tükendi, indirim rozeti, "3 Al 2 Öde" promo rozeti, select_item analitiği, data-testid'ler.
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useCart } from "../context/CartContext";
import { useFavorites } from "../context/FavoritesContext";
import { optimizeImg, firstImage } from "../lib/img";
import { trackSelectItem } from "../lib/dataLayer";
import { fmtPrice, productHref, priceOf, isSoldOut, needsVariantChoice } from "./electro/format";
import { toggleCompare, useCompare } from "./electro/compare";
import useCategoryTree from "./electro/useCategoryTree";
import { CodBadge } from "./electro/CodInfo";
import { useSiteDesign } from "../lib/siteDesign";

/** Kart yazıları: Sayfa Tasarımı › Genel Alanlar › Tema › Ürün kartı (sepete ekle / favori / karşılaştır). */
export function useCardTexts() {
  const c = useSiteDesign()?.site_theme?.card || {};
  return { add: c.add_to_cart_text || "Sepete Ekle", fav: c.wishlist_text || "Favori", cmp: c.compare_text || "Karşılaştır" };
}

function stripHtml(s) {
  return String(s || "").replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
}

export function CardPrice({ product, size = "grid" }) {
  const pv = priceOf(product);
  if (size === "list") {
    return pv.hasDiscount ? (
      <div className="prodcut-price mt-auto flex-horizontal-center">
        <ins className="font-size-15 text-decoration-none text-red">{fmtPrice(pv.display)}</ins>
        <del className="font-size-12 text-gray-9 ml-2">{fmtPrice(pv.list)}</del>
      </div>
    ) : (
      <div className="prodcut-price mt-auto"><div className="font-size-15">{fmtPrice(pv.display)}</div></div>
    );
  }
  return pv.hasDiscount ? (
    <div className="prodcut-price d-flex align-items-center flex-wrap position-relative">
      <ins className="font-size-20 text-red text-decoration-none mr-2">{fmtPrice(pv.display)}</ins>
      <del className="font-size-12 tex-gray-6 position-absolute bottom-100">{fmtPrice(pv.list)}</del>
    </div>
  ) : (
    <div className="prodcut-price"><div className="text-gray-100">{fmtPrice(pv.display)}</div></div>
  );
}

export function useProductActions(product, { listId = "", listName = "", index } = {}) {
  const { addItem } = useCart();
  const { isFavorite, toggleFavorite } = useFavorites();
  const navigate = useNavigate();
  const compare = useCompare();
  const soldOut = isSoldOut(product);
  const href = productHref(product);

  const select = () => { try { trackSelectItem({ product, listId, listName, index }); } catch (_) { /* silent */ } };
  const add = (e) => {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    if (soldOut) { toast.error("Bu ürün tükendi"); return; }
    // Seçim gerektiren (birden çok varyantlı) üründe seçim yapılmadan sepete eklenmez → ürün sayfası.
    if (needsVariantChoice(product)) { select(); navigate(href); return; }
    const vs = (product.variants || []).filter((v) => v && v.id);
    addItem(product, vs.length === 1 ? vs[0] : null);
    toast.success("Ürün sepete eklendi");
  };
  const fav = (e) => { if (e) { e.preventDefault(); e.stopPropagation(); } toggleFavorite(product); };
  const cmp = (e) => {
    if (e) { e.preventDefault(); e.stopPropagation(); }
    const r = toggleCompare(product);
    toast.success(r.added ? "Karşılaştırma listesine eklendi" : "Karşılaştırma listesinden çıkarıldı");
  };
  return {
    soldOut, href, select, add, fav, cmp,
    isFav: isFavorite(product.id),
    inCompare: compare.some((p) => p.id === product.id),
  };
}

function useCategoryLabel(product) {
  const tree = useCategoryTree();
  const name = product.category_name || (product.category && typeof product.category === "object" ? product.category.name : "");
  const id = product.category_id != null ? String(product.category_id) : null;
  const node = id ? tree.byId.get(id) : null;
  return { label: name || (node && node.name) || "", to: node ? `/${node.slug}` : null };
}

function CardImage({ product, w = 300, className = "img-fluid", boxClass = "el-img-box" }) {
  const src = optimizeImg(firstImage(product) || "/placeholder.jpg", w);
  return (
    <span className={boxClass}>
      <img className={className} src={src} alt={product.name} loading="lazy" decoding="async" width="212" height="200" />
    </span>
  );
}

function Badges({ product, pv, soldOut }) {
  return (
    <>
      {pv.hasDiscount && pv.discountPct > 0 && (
        <span className="el-badge el-badge--sale" data-testid={`discount-badge-${product.id}`}>-%{pv.discountPct}</span>
      )}
      {soldOut && <span className="el-badge el-badge--soldout">Tükendi</span>}
      {!soldOut && <CodBadge product={product} className="el-cod-badge--card" />}
    </>
  );
}

function FooterLinks({ product, a, wishlistLabel }) {
  const tx = useCardTexts();
  return (
    <div className="product-item__footer">
      <div className="border-top pt-2 flex-center-between flex-wrap">
        <a href="#karsilastir" onClick={a.cmp} className={`text-gray-6 font-size-13${a.inCompare ? " text-blue" : ""}`} data-testid={`compare-${product.id}`}>
          <i className="ec ec-compare mr-1 font-size-15" /> {tx.cmp}
        </a>
        <a href="#favori" onClick={a.fav} className={`text-gray-6 font-size-13${a.isFav ? " text-red" : ""}`}
          data-testid={`favorite-${product.id}`} aria-label={a.isFav ? "Favorilerden çıkar" : "Favorilere ekle"} aria-pressed={a.isFav}>
          <i className={`${a.isFav ? "fas fa-heart" : "ec ec-favorites"} mr-1 font-size-15`} /> {a.isFav ? "Favorilerde" : (wishlistLabel || tx.fav)}
        </a>
      </div>
    </div>
  );
}

function AddButton({ product, a }) {
  const tx = useCardTexts();
  return (
    <div className="prodcut-add-cart">
      <a href={a.href} onClick={a.add} className={`btn-add-cart btn-primary transition-3d-hover${a.soldOut ? " disabled" : ""}`}
        data-testid={`quick-add-${product.id}`} aria-label={a.soldOut ? "Tükendi" : "Sepete ekle"} title={a.soldOut ? "Tükendi" : tx.add}>
        <i className="ec ec-add-to-cart" />
      </a>
    </div>
  );
}

export default function ProductCard({ product, listId = "", listName = "", index, variant = "grid", as: Tag = "div", className = "", innerClassName, wishlistLabel }) {
  const a = useProductActions(product, { listId, listName, index });
  const tx = useCardTexts();
  const cat = useCategoryLabel(product);
  const pv = priceOf(product);
  const promo = product.promo_badge ? (
    <div className="font-size-12 font-weight-bold text-red text-uppercase mb-1" data-testid={`promo-badge-${product.id}`}>{product.promo_badge}</div>
  ) : null;
  const catLink = cat.label ? (
    <div className="mb-2">{cat.to ? <Link to={cat.to} className="font-size-12 text-gray-5">{cat.label}</Link> : <span className="font-size-12 text-gray-5">{cat.label}</span>}</div>
  ) : <div className="mb-2 font-size-12">&nbsp;</div>;
  const title = (cls = "mb-1 product-item__title") => (
    <h5 className={cls}><Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link></h5>
  );

  if (variant === "list") {
    return (
      <Tag className={`product-item product-item__list row no-gutters mb-6 remove-divider ${className}`} data-testid={`product-card-${product.id}`}>
        <div className="col-auto">
          <Link to={a.href} onClick={a.select} className="d-block width-75 text-center">
            <CardImage product={product} w={150} boxClass="el-img-box el-img-box--sq" />
          </Link>
        </div>
        <div className="col pl-4 d-flex flex-column">
          {title("product-item__title mb-0")}
          <CardPrice product={product} size="list" />
        </div>
      </Tag>
    );
  }

  if (variant === "card") {
    return (
      <Tag className={`product-item product-item__card pb-2 mb-2 pb-md-0 mb-md-0 ${className}`} data-testid={`product-card-${product.id}`}>
        <div className="product-item__outer h-100">
          <div className={innerClassName || "product-item__inner p-md-3 row no-gutters"}>
            <div className="col col-lg-auto product-media-left position-relative">
              <Link to={a.href} onClick={a.select} className="max-width-150 d-block">
                <CardImage product={product} w={300} />
              </Link>
              <Badges product={product} pv={pv} soldOut={a.soldOut} />
            </div>
            <div className="col product-item__body pl-2 pl-lg-3 mr-xl-2 mr-wd-1">
              <div className="mb-4">
                {catLink}
                {promo}
                {title("product-item__title")}
              </div>
              <div className="flex-center-between mb-3">
                <CardPrice product={product} />
                <div className="d-none d-xl-block"><AddButton product={product} a={a} /></div>
              </div>
              <FooterLinks product={product} a={a} wishlistLabel={wishlistLabel} />
            </div>
          </div>
        </div>
      </Tag>
    );
  }

  if (variant === "listview") {
    const desc = stripHtml(product.short_description || product.description).slice(0, 260);
    return (
      <Tag className={`product-item remove-divider ${className}`} data-testid={`product-card-${product.id}`}>
        <div className="product-item__outer w-100">
          <div className="product-item__inner remove-prodcut-hover py-4 row">
            <div className="product-item__header col-6 col-md-4">
              <div className="mb-2 position-relative">
                <Link to={a.href} onClick={a.select} className="d-block text-center"><CardImage product={product} w={400} /></Link>
                <Badges product={product} pv={pv} soldOut={a.soldOut} />
              </div>
            </div>
            <div className="product-item__body col-6 col-md-5">
              <div className="pr-lg-10">
                {catLink}
                {promo}
                {title("product-item__title")}
                <div className="prodcut-price mb-2 d-md-none"><CardPrice product={product} /></div>
                {desc && <p className="font-size-14 text-gray-90 mb-0 d-none d-md-block">{desc}</p>}
              </div>
            </div>
            <div className="product-item__footer col-md-3 d-md-block">
              <div className="mb-3">
                <div className="d-none d-md-block"><CardPrice product={product} /></div>
                <div className="prodcut-add-cart mt-3">
                  <a href={a.href} onClick={a.add} className="btn btn-sm btn-block btn-primary-dark btn-wide transition-3d-hover" data-testid={`quick-add-${product.id}`}>
                    {a.soldOut ? "Tükendi" : tx.add}
                  </a>
                </div>
              </div>
              <div className="flex-horizontal-center justify-content-between justify-content-wd-center flex-wrap border-top pt-3">
                <a href="#karsilastir" onClick={a.cmp} className="text-gray-6 font-size-13 mx-wd-3"><i className="ec ec-compare mr-1 font-size-15" /> {tx.cmp}</a>
                <a href="#favori" onClick={a.fav} className={`text-gray-6 font-size-13 mx-wd-3${a.isFav ? " text-red" : ""}`} data-testid={`favorite-${product.id}`} aria-pressed={a.isFav}>
                  <i className={`${a.isFav ? "fas fa-heart" : "ec ec-favorites"} mr-1 font-size-15`} /> {a.isFav ? "Favorilerde" : tx.fav}
                </a>
              </div>
            </div>
          </div>
        </div>
      </Tag>
    );
  }

  return (
    <Tag className={`product-item ${className}`} data-testid={`product-card-${product.id}`}>
      <div className="product-item__outer h-100">
        <div className={innerClassName || "product-item__inner px-xl-4 p-3"}>
          <div className="product-item__body pb-xl-2">
            {catLink}
            {promo}
            {title()}
            <div className="mb-2 position-relative">
              <Link to={a.href} onClick={a.select} className="d-block text-center" aria-label={product.name}>
                <CardImage product={product} />
              </Link>
              <Badges product={product} pv={pv} soldOut={a.soldOut} />
            </div>
            <div className="flex-center-between mb-1">
              <CardPrice product={product} />
              <AddButton product={product} a={a} />
            </div>
          </div>
          <FooterLinks product={product} a={a} wishlistLabel={wishlistLabel} />
        </div>
      </div>
    </Tag>
  );
}
