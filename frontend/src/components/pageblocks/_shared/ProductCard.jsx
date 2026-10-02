// Ürün kartı varyantları (SPEC §3 tablo): grid | grid_small | horizontal | list_small | featured_big | deal | image_only.
// grid/grid_small/horizontal/list_small mevcut vitrin kartını (components/ProductCard) kullanır — kategori
// sayfalarıyla birebir aynı görünüm ve davranış (sepete ekle, favori, karşılaştır, analitik). Global kart
// ayarları (favori/karşılaştır/kategori/eski fiyat/indirim rozeti) tema CSS'iyle uygulanır (ThemeVars).
import { useState } from "react";
import { Link } from "react-router-dom";
import BaseCard, { CardPrice, useProductActions } from "../../ProductCard";
import { optimizeImg, galleryImages, firstImage } from "../../../lib/img";
import { fmtPrice, priceOf } from "../../electro/format";

export function FeaturedBigCard({ product, thumbnails = true, listName = "featured_big", aspect = "564 / 420", className = "col product-item remove-divider", as: Tag = "li" }) {
  const a = useProductActions(product, { listName });
  const imgs = galleryImages(product);
  const [cur, setCur] = useState(0);
  const cat = product.category_name;
  return (
    <Tag className={className} data-testid={`product-card-${product.id}`}>
      <div className="product-item__outer h-100 w-100 prodcut-box-shadow">
        <div className="product-item__inner bg-white p-3">
          <div className="product-item__body d-flex flex-column">
            <div className="mb-1">
              {cat && <div className="mb-2"><span className="font-size-12 text-gray-5">{cat}</span></div>}
              <h5 className="mb-0 product-item__title"><Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link></h5>
            </div>
            <div className="mb-1">
              <Link to={a.href} onClick={a.select} className="d-block text-center my-4">
                <span className="el-img-box" style={{ aspectRatio: aspect }}>
                  <img className="img-fluid" src={optimizeImg(imgs[cur] || "/placeholder.jpg", 800)} alt={product.name} loading="lazy" />
                </span>
              </Link>
              {thumbnails && imgs.length > 1 && (
                <div className="row mx-gutters-2 mb-3">
                  {imgs.slice(0, 4).map((im, i) => (
                    <div className="col-auto" key={im}>
                      <button type="button" className={`el-thumb-btn${cur === i ? " active" : ""}`} onClick={() => setCur(i)} aria-label={`Görsel ${i + 1}`}>
                        <img src={optimizeImg(im, 120)} alt="" loading="lazy" width="60" height="60" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="flex-center-between mb-3">
              <CardPrice product={product} />
              <div className="prodcut-add-cart">
                <a href={a.href} onClick={a.add} className="btn-add-cart btn-primary transition-3d-hover" data-testid={`quick-add-${product.id}`} aria-label="Sepete ekle"><i className="ec ec-add-to-cart" /></a>
              </div>
            </div>
          </div>
          <div className="product-item__footer">
            <div className="border-top pt-2 flex-center-between flex-wrap">
              <a href="#karsilastir" onClick={a.cmp} className="text-gray-6 font-size-13" data-testid={`compare-${product.id}`}><i className="ec ec-compare mr-1 font-size-15" /> Karşılaştır</a>
              <a href="#favori" onClick={a.fav} className={`text-gray-6 font-size-13${a.isFav ? " text-red" : ""}`} data-testid={`favorite-${product.id}`}><i className="ec ec-favorites mr-1 font-size-15" /> Favorilere Ekle</a>
            </div>
          </div>
        </div>
      </div>
    </Tag>
  );
}

/** Fırsat kartı gövdesi (görsel + ad + fiyat) — çerçeve/geri sayım/stok çağıran blokta. */
export function DealProduct({ product, titleHtml, image, listName = "deal" }) {
  const a = useProductActions(product, { listName });
  const pv = priceOf(product);
  const src = image?.url || firstImage(product);
  return (
    <div className="product-item" data-testid={`product-card-${product.id}`}>
      <div className="mb-4">
        <Link to={a.href} onClick={a.select} className="d-block text-center">
          <span className="el-img-box" style={{ aspectRatio: "320 / 300" }}>
            <img className="img-fluid" src={optimizeImg(src, 640)} alt={product.name} loading="lazy" width="320" height="300" />
          </span>
        </Link>
      </div>
      <h5 className="mb-2 font-size-14 text-center mx-auto max-width-180 text-lh-18">
        {titleHtml ? <Link to={a.href} onClick={a.select} className="text-blue font-weight-bold" dangerouslySetInnerHTML={{ __html: titleHtml }} data-pd-field="deal.title_override" />
          : <Link to={a.href} onClick={a.select} className="text-blue font-weight-bold">{product.name}</Link>}
      </h5>
      <div className="d-flex align-items-center justify-content-center mb-3">
        {pv.hasDiscount && <del className="font-size-18 mr-2 text-gray-2">{fmtPrice(pv.list)}</del>}
        <ins className="font-size-30 text-red text-decoration-none">{fmtPrice(pv.display)}</ins>
      </div>
    </div>
  );
}

export default function ProductCard({ product, card = "grid", as = "div", className = "", listName, index, innerClassName, thumbnails }) {
  if (!product) return null;
  switch (card) {
    case "grid_small":
      return <BaseCard product={product} as={as} className={className} listName={listName} index={index}
        innerClassName={innerClassName || "product-item__inner px-wd-4 p-2 p-md-3"} wishlistLabel="Favori" />;
    case "horizontal":
      return <BaseCard product={product} variant="card" as={as} className={className} listName={listName} index={index} innerClassName={innerClassName} />;
    case "list_small":
      return <BaseCard product={product} variant="list" as={as} className={className} listName={listName} index={index} />;
    case "featured_big":
      return <FeaturedBigCard product={product} thumbnails={thumbnails !== false} listName={listName} as={as === "div" ? "li" : as} className={className || undefined} />;
    case "deal":
      return <DealProduct product={product} listName={listName} />;
    case "image_only": {
      const Tag = as;
      return (
        <Tag className={`product-item ${className}`} data-testid={`product-card-${product.id}`}>
          <Link to={`/${product.slug || product.id}`} className="d-block" aria-label={product.name}>
            <span className="el-img-box el-img-box--sq"><img className="img-fluid" src={optimizeImg(firstImage(product) || "/placeholder.jpg", 600)} alt={product.name} loading="lazy" /></span>
          </Link>
        </Tag>
      );
    }
    case "grid":
    default:
      return <BaseCard product={product} as={as} className={className} listName={listName} index={index} innerClassName={innerClassName} />;
  }
}
