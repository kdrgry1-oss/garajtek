// D4 categories_icon_carousel — şablon v2.0:
//   v8: .border-top.bg-primary.border-color-8 bant > .container.position-relative > .js-slick-carousel.u-slick.u-slick--gutters-0
//       .position-static.px-1.py-3.text-lh-38 > a.d-block.text-center.width-122.mx-auto > .text-gray-90 i.font-size-30
//       + .px-2.pt-2 h6.font-weight-semi-bold.font-size-13.text-gray-90.text-lh-1dot2
//   v6: .mb-5 > .position-relative > (pb-5 pt-2 px-1) a.bg-on-hover > .bg.pt-4.rounded-circle-top.width-122.height-75 i.font-size-40
//       + .bg-white.px-2.pt-2 h6.font-size-14
//   Ortak: slidesToShow 10 (≥1600) / 8 (≥1200) / 6 (≥992) / 5 (≥768) / 3 (≥554) / 2; yuvarlak yan oklar (yalnız xl), xl altında noktalar.
import BlockCarousel from "../_shared/BlockCarousel";
import SmartImage from "../_shared/SmartImage";
import SmartLink from "../_shared/SmartLink";
import "./style.css";

function Icon({ icon, f, size }) {
  if (icon && icon.image && icon.image.url) {
    return <SmartImage image={icon.image} width={120} className="pd-cicar__img" style={{ height: size, width: "auto" }} field={`${f}.icon`} placeholder={false} />;
  }
  return <i className={`${(icon && icon.icon) || "fas fa-tools"} pd-cicar__i`} data-pd-field={`${f}.icon`} aria-hidden="true" />;
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const v6 = st._variant === "v6";
  const items = (st.items || []).filter((x) => x && (x.label || (x.icon && (x.icon.icon || x.icon.image))));
  if (!items.length) return ctx && ctx.preview ? <div className="container"><div className="pd-stub" data-empty="">Kategori ekleyin.</div></div> : null;
  const vars = {
    "--pd-cicar-isz": `${Number(st.icon_size) || (v6 ? 40 : 30)}px`,
    "--pd-cicar-ic": st.icon_color || "#333e48",
    "--pd-cicar-tc": st.text_color || "#333e48",
    "--pd-cicar-w": `${Number(st.item_width) || 122}px`,
    ...(st.band_color ? { "--pd-cicar-band": st.band_color } : {}),
    ...(st.bubble_color ? { "--pd-cicar-bubble": st.bubble_color } : {}),
  };
  const arrows = {
    sideArrowsClassName: "d-none d-xl-block u-slick__arrow-normal u-slick__arrow-centered--y rounded-circle text-black font-size-30 z-index-2",
    arrowLeftClassName: "fa fa-angle-left u-slick__arrow-inner--left left-n16",
    arrowRightClassName: "fa fa-angle-right u-slick__arrow-inner--right right-n20",
  };
  const slides = items.map((it, i) => {
    const f = `items.${i}`;
    return v6 ? (
      <SmartLink key={it._id || i} link={it.link} fallback="div" className="d-block text-center bg-on-hover mx-auto pd-cicar__item">
        <div className="bg pt-4 rounded-circle-top height-75 pd-cicar__bubble"><Icon icon={it.icon} f={f} size={st.icon_size} /></div>
        <div className="bg-white px-2 pt-2 pd-cicar__label-wrap">
          <h6 className="font-weight-semi-bold font-size-14 mb-0 text-lh-1dot2 pd-cicar__label" data-pd-field={`${f}.label`}>{it.label}</h6>
        </div>
      </SmartLink>
    ) : (
      <SmartLink key={it._id || i} link={it.link} fallback="div" className="d-block text-center mx-auto pd-cicar__item">
        <div className="pd-cicar__icon"><Icon icon={it.icon} f={f} size={st.icon_size} /></div>
        <div className="px-2 pt-2">
          <h6 className="font-weight-semi-bold font-size-13 mb-0 text-lh-1dot2 pd-cicar__label" data-pd-field={`${f}.label`}>{it.label}</h6>
        </div>
      </SmartLink>
    );
  });
  if (v6) {
    return (
      <div className="container pd-cicar pd-cicar--v6" style={vars} data-testid="categories-icon-carousel">
        <div className="position-relative">
          <BlockCarousel value={st.carousel} className="u-slick u-slick--gutters-0 u-slick-overflow-visble pb-5 pt-2 px-1 pd-cicar__car" {...arrows}
            dotsClassName="d-xl-none text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--long mb-0 z-index-n1 mt-3 pt-1">
            {slides}
          </BlockCarousel>
        </div>
      </div>
    );
  }
  return (
    <div className="border-top bg-primary border-color-8 pd-cicar pd-cicar--v8" style={vars} data-testid="categories-icon-carousel">
      <div className="container position-relative">
        <BlockCarousel value={st.carousel} className="u-slick u-slick--gutters-0 u-slick-overflow-visble px-1 py-3 text-lh-38 pd-cicar__car" {...arrows}
          dotsClassName="d-xl-none text-center right-0 bottom-1 left-0 u-slick__pagination u-slick__pagination--dark u-slick__pagination--long mb-2 z-index-n1 mt-4 pt-1">
          {slides}
        </BlockCarousel>
      </div>
    </div>
  );
}
