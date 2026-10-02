// D9 page_hero — şablon v2.0 about.html: .bg-img-hero.mb-14 (1920×600 arka plan) > .container
//   > .flex-content-center.max-width-620-lg.flex-column.mx-auto.text-center.min-height-564
//   > h1.h1.font-weight-bold + p.text-gray-39.font-size-18.text-lh-default
// (v1 about.html: header.entry-header.header-with-cover-image > .caption h1.entry-title + p.entry-subtitle)
import SmartImage from "../_shared/SmartImage";
import "./style.css";

const px = (v, d) => `${Number(v) || d}px`;

export default function Render({ settings }) {
  const st = settings;
  const mh = st.min_height && typeof st.min_height === "object" ? st.min_height : { desktop: st.min_height, tablet: st.min_height, mobile: st.min_height };
  const align = st.align || "center";
  const style = {
    "--pd-ph-h-d": px(mh.desktop, 564), "--pd-ph-h-t": px(mh.tablet ?? mh.desktop, 420), "--pd-ph-h-m": px(mh.mobile ?? mh.tablet, 300),
    "--pd-ph-w": px(st.max_width, 620), "--pd-ph-tsz": px(st.title_size, 40),
    backgroundColor: st.background_color || undefined,
  };
  const hasBg = !!(st.background && st.background.url);
  return (
    <div className={`pd-ph position-relative${hasBg ? " pd-ph--img" : ""}`} style={style} data-testid="page-hero">
      {hasBg && <SmartImage image={st.background} width={1920} className="pd-ph__bg" fit="cover" field="background" eager />}
      <div className="container position-relative">
        <div className={`flex-content-center flex-column pd-ph__inner pd-ph__inner--${align}`}>
          {st.title && <h1 className="h1 font-weight-bold pd-ph__title" style={{ color: st.title_color || undefined }} data-pd-field="title">{st.title}</h1>}
          {st.text && <p className="font-size-18 text-lh-default pd-ph__text" style={{ color: st.text_color || undefined }} data-pd-field="text">{st.text}</p>}
        </div>
      </div>
    </div>
  );
}
