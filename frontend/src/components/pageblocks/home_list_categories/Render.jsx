// D2 home_list_categories — şablon v1 homepage-3 home-list-categories (+ _home-list-categories.scss):
//   section > header h2.h1 + ul.categories > li.category (lg 4/12, md 6/12; sağda 1px #eaeaea ayraç; 2.857em alt boşluk)
//   > .media (.media-left img 150 px + .media-body h4.media-heading (1.286em) + ul.sub-categories (0.929em #9d9c9c))
//   + a.see-all (sağa yaslı, kalın, #9d9c9c).
// v2: şablon v2.0 home-v3 “Top Categories this Month” (col-4 col-wd-3 + border-right; görsel col-md-5, metin col-md-7,
//   h4.font-size-18 + ul.font-size-13.text-lh-21 (text-gray-15) + sağa yaslı kalın “See all”).
// Kategoriler: menüdeki ana kategorilerden otomatik (ad/görsel/alt kategoriler katalogdan → data-pd-data) ya da elle.
import useCategoryTree from "../../electro/useCategoryTree";
import SectionHeader from "../_shared/SectionHeader";
import SmartImage from "../_shared/SmartImage";
import SmartLink, { linkHref } from "../_shared/SmartLink";
import { optimizeImg } from "../../../lib/img";
import "./style.css";

export const catHref = (c) => (c ? `/${c.slug || c.id}` : "");
export const catImage = (c) => (c && (c.image || c.image_url)) || "";

/** Ayarlar + kategori ağacı → kart listesi. Kataloğdan gelen metinler `data: true` taşır. */
export function buildCards(st, tree) {
  const roots = (tree && (tree.menuRoots || tree.roots)) || [];
  const byId = (tree && tree.byId) || new Map();
  const autoSubs = (c, n, base) => (c && c.children ? c.children.slice(0, Math.max(0, n)) : []).map((s, j) => ({
    key: s.id, label: s.name, link: { kind: "category", id: String(s.id), url: catHref(s) }, data: true, field: `${base}.sub_links.${j}`,
  }));
  if (st.source !== "manual") {
    return roots.slice(0, Number(st.auto_max) || 6).map((c) => ({
      key: c.id, name: c.name, nameData: true, href: catHref(c), link: { kind: "category", id: String(c.id), url: catHref(c) },
      image: catImage(c) ? { url: catImage(c), alt: c.name } : null, imageData: true,
      subs: autoSubs(c, Number(st.sub_limit ?? 4), ""), seeAll: st.see_all_text, seeAllField: "see_all_text",
    }));
  }
  return (st.categories || []).map((it, i) => {
    const f = `categories.${i}`;
    const c = it.category ? byId.get(String(it.category)) : null;
    const ownLink = it.link_override && linkHref(it.link_override) ? it.link_override : null;
    const link = ownLink || (c ? { kind: "category", id: String(c.id), url: catHref(c) } : null);
    const img = it.image_override && it.image_override.url ? it.image_override : (catImage(c) ? { url: catImage(c), alt: c.name } : null);
    const subs = it.sub_mode === "manual"
      ? (it.sub_links || []).filter((s) => s && s.label).map((s, j) => ({ key: s._id || j, label: s.label, link: s.link, field: `${f}.sub_links.${j}.label` }))
      : autoSubs(c, Number(it.sub_limit ?? 4), f);
    return {
      key: it._id || i, name: it.name_override || (c ? c.name : ""), nameData: !it.name_override, nameField: `${f}.name_override`,
      link, image: img, imageData: !(it.image_override && it.image_override.url), imageField: `${f}.image_override`, subs,
      seeAll: it.see_all_text || st.see_all_text, seeAllField: it.see_all_text ? `${f}.see_all_text` : "see_all_text",
    };
  }).filter((x) => x.name || x.image);
}

const txtAttr = (data, field) => (data ? { "data-pd-data": "" } : { "data-pd-field": field });

function Img({ card, className, size = [250, 232], width = 300 }) {
  if (card.image && card.imageData) return <img className={className} src={optimizeImg(card.image.url, width)} alt={card.image.alt || card.name} loading="lazy" data-pd-data="" />;
  return <SmartImage image={card.image} size={size} width={width} className={className} field={card.imageField} alt={card.name} />;
}

export default function Render({ settings, ctx }) {
  const st = settings;
  const tree = useCategoryTree();
  const cards = buildCards(st, tree);
  const preview = !!(ctx && ctx.preview);
  const v2 = st._variant === "v2";
  if (!cards.length) {
    if (!preview) return null;
    return <div className="pd-stub" data-testid="home-list-categories" data-empty="">Kategori bulunamadı — Katalog › Kategoriler'den kategori ekleyin ya da “Elle seçilen kategoriler”e geçin.</div>;
  }
  const cols = Number(st.columns) || 3;
  const header = <SectionHeader value={st.header} field="header" className={v2 ? "pd-hlc__header2 mb-5" : "pd-hlc__header"}
    titleClassName={v2 ? "section-title section-title__full d-inline-block mb-0 pb-2 font-size-22" : "h1 pd-hlc__title pd-sh__title"} />;

  if (v2) {
    const colCls = cols === 4 ? "col-6 col-md-4 col-xl-3" : cols === 2 ? "col-6" : "col-4 col-wd-3";
    const xlFull = cards.length >= 3 ? Math.floor(cards.length / 3) * 3 : cards.length;
    const wdFull = cards.length >= 4 ? Math.floor(cards.length / 4) * 4 : cards.length;
    return (
      <section className={`pd-hlc pd-hlc--v2 pd-hlc--c${cols}`} data-testid="home-list-categories">
        {header}
        <div className="row align-items-start">
          {cards.map((c, i) => (
            // şablon: 1200–1479 px'te satırı doldurmayan son kartlar gizlenir (d-xl-none d-wd-block), satır sonunda çizgi yok
            <div key={c.key} className={`${colCls}${st.dividers ? " border-right border-lg-down-0" : ""} mb-8 pd-hlc__col2${cols === 3 && i >= xlFull ? " pd-hlc--xlhide" : ""}${cols === 3 && i >= wdFull ? " pd-hlc--wdhide" : ""}`}>
              <div className="row align-items-center align-items-xl-start">
                {st.show_images && (
                  <div className="col-md-5 mb-3 mb-md-0">
                    <SmartLink link={c.link} fallback="div" className="d-block"><Img card={c} className="img-fluid" size={[300, 300]} /></SmartLink>
                  </div>
                )}
                <div className={st.show_images ? "col-md-7 pl-lg-0" : "col-12"}>
                  <h4 className="font-size-18 mb-0 mb-xl-2 font-size-14-down-lg text-center text-md-left">
                    <SmartLink link={c.link} className="underline-on-hover" {...txtAttr(c.nameData, c.nameField)}>{c.name}</SmartLink>
                  </h4>
                  {c.subs.length > 0 && (
                    <ul className="mb-1 font-size-13 list-unstyled text-lh-21 d-none d-xl-block">
                      {c.subs.map((s) => <li key={s.key}><SmartLink link={s.link} className="text-gray-15 underline-on-hover" {...txtAttr(s.data, s.field)}>{s.label}</SmartLink></li>)}
                    </ul>
                  )}
                  {st.show_see_all && c.seeAll && (
                    <SmartLink link={c.link} className="d-none d-xl-block text-right font-weight-bold text-gray-15 underline-on-hover" field={c.seeAllField}>{c.seeAll}</SmartLink>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className={`pd-hlc pd-hlc--v1 pd-hlc--c${cols}${st.dividers ? " pd-hlc--div" : ""}`} data-testid="home-list-categories"
      style={{ "--pd-hlc-img": `${Number(st.image_width) || 150}px` }}>
      {header}
      <ul className="pd-hlc__list">
        {cards.map((c) => (
          <li key={c.key} className="pd-hlc__cat">
            <div className="pd-hlc__media">
              {st.show_images && (
                <SmartLink link={c.link} fallback="div" className="pd-hlc__left"><Img card={c} className="pd-hlc__img" /></SmartLink>
              )}
              <div className="pd-hlc__body">
                <h4 className="pd-hlc__heading"><SmartLink link={c.link} {...txtAttr(c.nameData, c.nameField)}>{c.name}</SmartLink></h4>
                {c.subs.length > 0 && (
                  <ul className="pd-hlc__subs list-unstyled">
                    {c.subs.map((s) => <li key={s.key} className="cat-item"><SmartLink link={s.link} {...txtAttr(s.data, s.field)}>{s.label}</SmartLink></li>)}
                  </ul>
                )}
              </div>
            </div>
            {st.show_see_all && c.seeAll && <SmartLink link={c.link} className="pd-hlc__see-all" field={c.seeAllField}>{c.seeAll}</SmartLink>}
          </li>
        ))}
      </ul>
    </section>
  );
}
