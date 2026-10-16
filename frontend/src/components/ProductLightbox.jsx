import React, { useEffect, useRef } from "react";
import { createPortal } from "react-dom";

/**
 * Ürün görseli tam ekran galerisi — görsel artık yeni sekmede (koyu tarayıcı ekranında, küçük)
 * açılmaz; sayfa içinde beyaz zeminde büyük açılır. Masaüstünde solda, mobilde altta küçük
 * resimler; ok tuşları / kaydırma ile geçiş, ESC veya arka plana tıklama ile kapanır.
 */
export default function ProductLightbox({ images, index, onIndex, onClose, alt = "", optimize = (u) => u }) {
  const touchX = useRef(null);
  const n = images.length;
  const go = (d) => onIndex((index + d + n) % n);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" && n > 1) onIndex((index + 1) % n);
      else if (e.key === "ArrowLeft" && n > 1) onIndex((index - 1 + n) % n);
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.body.classList.add("gt-lightbox-open");  // WhatsApp vb. yüzen butonlar galerinin üstüne binmesin
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      document.body.classList.remove("gt-lightbox-open");
    };
  }, [index, n, onIndex, onClose]);

  if (!n) return null;
  return createPortal(
    <div className="gt-lightbox" role="dialog" aria-modal="true" aria-label="Ürün görselleri" data-testid="pdp-lightbox"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="gt-lightbox__box">
        <button type="button" className="gt-lightbox__close" onClick={onClose} aria-label="Kapat" data-testid="pdp-lightbox-close">
          <span aria-hidden="true">&times;</span>
        </button>
        {n > 1 && (
          <div className="gt-lightbox__thumbs" data-testid="pdp-lightbox-thumbs">
            {images.map((img, i) => (
              <button type="button" key={img + i} className={i === index ? "active" : ""} onClick={() => onIndex(i)} aria-label={`Görsel ${i + 1}`}>
                <img src={optimize(img, 200)} alt="" loading="lazy" />
              </button>
            ))}
          </div>
        )}
        <div className="gt-lightbox__stage"
          onTouchStart={(e) => { touchX.current = e.touches[0].clientX; }}
          onTouchEnd={(e) => {
            const dx = e.changedTouches[0].clientX - (touchX.current || 0);
            if (n > 1 && Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
          }}>
          <img src={optimize(images[index], 1600)} alt={alt} data-testid="pdp-lightbox-img" />
          {n > 1 && (
            <>
              <button type="button" className="gt-lightbox__nav gt-lightbox__nav--prev" onClick={() => go(-1)} aria-label="Önceki görsel"><span aria-hidden="true">&#8249;</span></button>
              <button type="button" className="gt-lightbox__nav gt-lightbox__nav--next" onClick={() => go(1)} aria-label="Sonraki görsel"><span aria-hidden="true">&#8250;</span></button>
              <div className="gt-lightbox__count">{index + 1} / {n}</div>
            </>
          )}
        </div>
      </div>
    </div>,
    document.body,
  );
}
