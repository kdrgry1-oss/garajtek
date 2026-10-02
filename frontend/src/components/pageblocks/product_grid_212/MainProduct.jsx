// Grup B büyük ürün kartı (şablon v1.0 `product-main-2-1-2` / `product-main-6-1`): kategori, başlık, büyük görsel
// (opsiyonel küçük resim galerisi + görsel büyütme), 1.786em fiyat, sepete ekle; üzerine gelince Favori/Karşılaştır.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useProductActions } from "../../ProductCard";
import useCategoryTree from "../../electro/useCategoryTree";
import { fmtPrice, priceOf } from "../../electro/format";
import { optimizeImg, galleryImages } from "../../../lib/img";
import Placeholder from "../_shared/Placeholder";
import "./style.css";

function Lightbox({ src, alt, onClose }) {
  useEffect(() => {
    const k = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="pdb-lightbox" role="dialog" aria-modal="true" onClick={onClose} data-testid="pdb-lightbox">
      <img src={optimizeImg(src, 1600)} alt={alt} />
      <button type="button" className="pdb-lightbox__close" aria-label="×" onClick={onClose}>×</button>
    </div>
  );
}

export default function MainProduct({ product, thumbnails = 0, lightbox = false, aspect = "57 / 53", imageHeight, listName = "main_product", className = "", testId }) {
  const a = useProductActions(product, { listName });
  const tree = useCategoryTree();
  const pv = priceOf(product);
  const imgs = galleryImages(product);
  const [cur, setCur] = useState(0);
  const [open, setOpen] = useState(false);
  const node = product.category_id != null ? tree.byId?.get(String(product.category_id)) : null;
  const cat = product.category_name || node?.name || "";
  const src = imgs[cur] || imgs[0];
  const box = imageHeight
    ? <span className="pdb-main__fixed" style={{ height: imageHeight }}>{src ? <img src={optimizeImg(src, 800)} alt={product.name} loading="lazy" /> : null}</span>
    : <span className="pdb-img" style={{ aspectRatio: aspect }}>{src ? <img src={optimizeImg(src, 900)} alt={product.name} loading="lazy" /> : null}</span>;
  const image = src ? box : <Placeholder size={[600, 600]} />;
  const n = Math.max(0, Math.min(4, Number(thumbnails) || 0));
  return (
    <li className={`pdb-main ${className}`} data-pd-data="product" data-testid={testId || `product-card-${product.id}`}>
      <div className="pdb-main__inner">
        <div className="pdb-main__cat">{cat ? (node ? <Link to={`/${node.slug}`} className="font-size-12 text-gray-5">{cat}</Link> : <span className="font-size-12 text-gray-5">{cat}</span>) : " "}</div>
        <h3 className="pdb-main__title"><Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link></h3>
        {lightbox && src ? (
          <button type="button" className="pdb-main__thumb pdb-main__zoom" onClick={() => setOpen(true)} aria-label={product.name}>{image}</button>
        ) : (
          <Link to={a.href} onClick={a.select} className="pdb-main__thumb">{image}</Link>
        )}
        {n > 0 && imgs.length > 1 && (
          <div className="pdb-main__thumbs">
            {imgs.slice(0, n).map((im, i) => (
              <button type="button" key={im} className={`pdb-main__tn${cur === i ? " current" : ""}`} onClick={() => setCur(i)} aria-label={`${product.name} ${i + 1}`}>
                <span className="pdb-img" style={{ aspectRatio: "1 / 1" }}><img src={optimizeImg(im, 180)} alt="" loading="lazy" /></span>
              </button>
            ))}
          </div>
        )}
        <div className="pdb-main__price-row">
          <span className="pdb-main__price"><ins className={pv.hasDiscount ? "" : "pdb-main__regular"}>{fmtPrice(pv.display)}</ins>{pv.hasDiscount && <del>{fmtPrice(pv.list)}</del>}</span>
          <div className="prodcut-add-cart">
            <a href={a.href} onClick={a.add} className={`btn-add-cart btn-primary transition-3d-hover${a.soldOut ? " disabled" : ""}`} data-testid={`quick-add-${product.id}`}
              aria-label={a.soldOut ? "Tükendi" : "Sepete ekle"}><i className="ec ec-add-to-cart" /></a>
          </div>
        </div>
        <div className="pdb-main__hover">
          <a href="#favori" onClick={a.fav} className={`text-gray-6 font-size-13${a.isFav ? " text-red" : ""}`} data-testid={`favorite-${product.id}`}>
            <i className={`${a.isFav ? "fas fa-heart" : "ec ec-favorites"} mr-1 font-size-15`} /> {a.isFav ? "Favorilerde" : "Favori"}
          </a>
          <a href="#karsilastir" onClick={a.cmp} className="text-gray-6 font-size-13" data-testid={`compare-${product.id}`}>
            <i className="ec ec-compare mr-1 font-size-15" /> Karşılaştır
          </a>
        </div>
      </div>
      {open && <Lightbox src={src} alt={product.name} onClose={() => setOpen(false)} />}
    </li>
  );
}
