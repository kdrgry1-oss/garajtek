/**
 * Footer.jsx — Electro footer (ürün widget'ları + ana renk e-bülten şeridi + iletişim/link kolonları +
 * telif & ödeme şeridi). TÜM metin/bağlantı/görseller Sayfa Tasarımı › Genel Alanlar'dan gelir
 * (site_footer_widgets, site_newsletter, site_footer_contact, site_contact, site_footer_links,
 * site_footer_bottom). E-bülten KVKK/İYS onay kutusu ZORUNLU olarak korunur.
 */
import { Link } from "react-router-dom";
import { useState } from "react";
import axios from "axios";
import { sanitizeHtml } from "../lib/sanitizeHtml";
import { useStoreInfo } from "../lib/storeInfo";
import { socialUrl } from "../lib/brand";
import { useSiteDesign, mergeContact, fillTokens } from "../lib/siteDesign";
import Logo from "./electro/Logo";
import useCategoryTree from "./electro/useCategoryTree";
import ProductCard from "./ProductCard";
import useProductSource from "./pageblocks/_shared/useProductSource";
import SmartLink, { linkHref } from "./pageblocks/_shared/SmartLink";
import RichText from "./pageblocks/_shared/RichText";
import SmartImage from "./pageblocks/_shared/SmartImage";
import GoToTop from "./pageblocks/_shared/GoToTop";
import { plainText } from "./pageblocks/_shared/schema";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function NewsletterBand({ nl }) {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState("idle");
  const [msg, setMsg] = useState("");
  const consentPlain = plainText(nl.consent_text);

  const submit = async (e) => {
    e.preventDefault();
    const v = (email || "").trim();
    if (!v || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { setState("error"); setMsg(nl.error_text); return; }
    if (!consent) { setState("error"); setMsg(nl.consent_required_text); return; }
    setState("loading");
    try {
      const r = await axios.post(`${API}/newsletter/subscribe`, { email: v, source: "footer", consent: true, consent_text: consentPlain });
      setState("done"); setMsg(nl.success_text || r?.data?.message); setEmail(""); setConsent(false);
    } catch (err) {
      setState("error"); setMsg(err?.response?.data?.detail || nl.error_text);
    }
  };

  return (
    <div className="bg-primary py-3" data-testid="newsletter-band" style={nl.background && nl.background !== "var(--primary)" ? { backgroundColor: nl.background } : undefined}>
      <div className="container">
        <div className="row align-items-center">
          <div className="col-lg-7 mb-md-3 mb-lg-0">
            <div className="row align-items-center">
              <div className="col-12 col-md-auto flex-horizontal-center">
                {nl.icon?.icon && <i className={`${nl.icon.icon} font-size-40`} />}
                <h2 className="font-size-20 mb-0 ml-3" data-pd-field="site_newsletter.title">{nl.title}</h2>
              </div>
              <div className="col-12 col-md my-3 my-md-0">
                <RichText as="h5" html={nl.marketing_text} className="font-size-15 ml-md-4 mb-0" field="site_newsletter.marketing_text" />
              </div>
            </div>
          </div>
          <div className="col-lg-5">
            {state === "done" ? (
              <div className="font-size-15 font-weight-bold py-2" data-testid="newsletter-done"><i className="fas fa-check-circle mr-2" />{msg}</div>
            ) : (
              <form onSubmit={submit} data-testid="newsletter-form" noValidate>
                <label className="sr-only" htmlFor="subscribeSrEmail">{nl.placeholder}</label>
                <div className="input-group input-group-pill">
                  <input type="email" className="form-control border-0 height-40" id="subscribeSrEmail" placeholder={nl.placeholder}
                    value={email} onChange={(e) => { setEmail(e.target.value); if (state === "error") setState("idle"); }}
                    aria-label={nl.placeholder} data-testid="newsletter-email" />
                  <div className="input-group-append">
                    <button type="submit" className="btn btn-dark btn-sm-wide height-40 py-2" disabled={state === "loading"} data-testid="newsletter-submit"
                      data-pd-field="site_newsletter.button_text">{nl.button_text}</button>
                  </div>
                </div>
                {consentPlain && (
                  <div className="custom-control custom-checkbox mt-2 font-size-12">
                    <input type="checkbox" className="custom-control-input" id="nlConsent" checked={consent}
                      onChange={(e) => { setConsent(e.target.checked); if (state === "error") setState("idle"); }} data-testid="newsletter-consent" />
                    <RichText as="label" html={nl.consent_text} className="custom-control-label text-gray-90" htmlFor="nlConsent" field="site_newsletter.consent_text" />
                  </div>
                )}
                {state === "error" && <div className="font-size-12 text-red mt-1" data-testid="newsletter-error">{msg}</div>}
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function WidgetColumn({ col, i }) {
  const list = useProductSource(col.source);
  if (!list || !list.length) return null;
  return (
    <div className="col-wd-3 col-lg-4">
      <div className="widget-column">
        <div className="border-bottom border-color-1 mb-5">
          <h3 className="section-title section-title__sm mb-0 pb-2 font-size-18" data-pd-field={`site_footer_widgets.columns.${i}.title`}>{col.title}</h3>
        </div>
        <ul className="list-unstyled products-group">
          {list.slice(0, 3).map((p) => <ProductCard key={p.id} product={p} variant="list" as="li" />)}
        </ul>
      </div>
    </div>
  );
}

/** Footer üstü ürün sütunları (site_footer_widgets). */
function FooterWidgets({ cfg }) {
  const cols = (cfg.columns || []).filter((c) => c && !c._hidden && c.title).slice(0, 4);
  if (!cols.length) return null;
  return (
    <div className="container d-none d-lg-block mb-3" data-testid="footer-widgets">
      <div className="row">{cols.map((c, i) => <WidgetColumn key={c._id || i} col={c} i={i} />)}</div>
    </div>
  );
}

/** iyzico logo bandı ("iyzico ile Öde" + Mastercard / Visa / American Express / Troy) — varsayılan ödeme şeridi. */
export function PaymentBand({ url, className = "" }) {
  if (url) {
    return <div className={`el-payband ${className}`} data-testid="payment-icons"><img src={url} alt="Ödeme yöntemleri" height="28" loading="lazy" /></div>;
  }
  return (
    <div className={`el-payband ${className}`} data-testid="payment-icons" aria-label="iyzico ile güvenli ödeme — Mastercard, Visa, American Express, Troy">
      <img src="/payment/iyzico-ile-ode.png" alt="iyzico ile Öde" width="80" height="26" loading="lazy" />
      <img src="/payment/kartlar.png" alt="Mastercard, Visa, American Express, Troy" width="206" height="20" loading="lazy" />
    </div>
  );
}

/** Geliştirici künyesi (sözleşme md. 20) — kodda sabit, panelden değiştirilemez.
 * Logo: public/roofcommerce-logo.svg (yoksa .png). */
function DevCredit() {
  return (
    <a href="https://roofcommerce.com.tr/" target="_blank" rel="noopener" className="el-devcredit d-inline-flex align-items-center mt-1 font-size-12 text-gray-5" data-testid="dev-credit">
      <span className="mr-1">Designed by</span>
      <img src="/roofcommerce-logo.svg" alt="roofcommerce" height="16" width="126" loading="lazy"
        onError={(e) => { if (!e.currentTarget.dataset.fb) { e.currentTarget.dataset.fb = "1"; e.currentTarget.src = "/roofcommerce-logo.png"; } }} />
    </a>
  );
}

const SOCIAL_ICON = { facebook: "fab fa-facebook-f", instagram: "fab fa-instagram", twitter: "fab fa-twitter", youtube: "fab fa-youtube", tiktok: "fab fa-tiktok", linkedin: "fab fa-linkedin-in", pinterest: "fab fa-pinterest-p" };

export default function Footer({ hideWidgets = false }) {
  const info = useStoreInfo();
  const sd = useSiteDesign();
  const tree = useCategoryTree();
  const fw = sd.site_footer_widgets || {};
  const nl = sd.site_newsletter || {};
  const fc = sd.site_footer_contact || {};
  const fl = sd.site_footer_links || {};
  const fb = sd.site_footer_bottom || {};
  const contact = mergeContact(sd.site_contact, info);

  let columns = (fl.columns || []).filter((c) => c && !c._hidden);
  // "İade Talebi" linki her zaman görünür olsun (yasal gereklilik)
  if (columns.length && !columns.some((c) => (c.links || []).some((l) => linkHref(l.link) === "/iade-islemleri"))) {
    columns = columns.map((c, i) => (i === 0 ? { ...c, links: [...(c.links || []), { label: "İade Talebi", link: { kind: "url", url: "/iade-islemleri" } }] } : c));
  }
  let social = (fc.social || []).filter((x) => x && !x._hidden && x.url).map((x) => [x.network, SOCIAL_ICON[x.network] || "fas fa-link", x.url]);
  if (!social.length) {
    social = [["instagram", SOCIAL_ICON.instagram, socialUrl("instagram", info.instagram)], ["tiktok", SOCIAL_ICON.tiktok, socialUrl("tiktok", info.tiktok)]].filter(([, , u]) => u);
  }
  const roots = fl.auto_fill_from_categories ? (tree.menuRoots || tree.roots).slice(0, 12) : [];
  const half = Math.ceil(roots.length / 2);
  const copyright = fillTokens(fb.copyright, { storeName: info.name });

  return (
    <footer className="electro el-footer" data-testid={fl.mode === "html" ? "footer-html" : "footer-structured"}>
      {!hideWidgets && fw.enabled !== false && <FooterWidgets cfg={fw} />}
      {nl.enabled !== false && <NewsletterBand nl={nl} />}
      {fl.mode === "html" && fl.custom_html ? (
        <div className="pt-8 pb-4 bg-gray-13">
          <div className="container mt-1" dangerouslySetInnerHTML={{ __html: sanitizeHtml(fl.custom_html) }} />
        </div>
      ) : (
        <div className="pt-8 pb-4 bg-gray-13">
          <div className="container mt-1">
            <div className="row">
              <div className="col-lg-5">
                {fc.show_logo !== false && <div className="mb-6"><Logo className="d-inline-block" place="footer" /></div>}
                <div className="mb-4">
                  <div className="row no-gutters">
                    {fc.call_us_icon?.icon && <div className="col-auto"><i className={`${fc.call_us_icon.icon} text-primary font-size-56`} /></div>}
                    <div className="col pl-3">
                      <div className="font-size-13 font-weight-light" data-pd-field="site_footer_contact.call_us_text">{fc.call_us_text}</div>
                      {contact.phone
                        ? <a href={`tel:${contact.phone.replace(/\s/g, "")}`} className="font-size-20 text-gray-90">{contact.phone}</a>
                        : <Link to="/sayfa/iletisim" className="font-size-20 text-gray-90" data-pd-field="site_footer_contact.call_us_fallback">{fc.call_us_fallback}</Link>}
                      {contact.phone2 && <div className="font-size-16 mt-1">{contact.phone2}</div>}
                      {contact.whatsapp && <div className="font-size-14 mt-1"><i className="fab fa-whatsapp mr-1" />{contact.whatsapp}</div>}
                    </div>
                  </div>
                </div>
                {(contact.address || contact.email) && (
                  <div className="mb-4">
                    {fc.address_title && <h6 className="mb-1 font-weight-bold" data-pd-field="site_footer_contact.address_title">{fc.address_title}</h6>}
                    {contact.address && <address className="mb-1">{contact.address}</address>}
                    {contact.email && <a href={`mailto:${contact.email}`} className="text-gray-90">{contact.email}</a>}
                    {contact.hours && <div className="font-size-13 mt-1">{contact.hours}</div>}
                  </div>
                )}
                {fc.slogan && <p className="font-size-13 text-gray-90" data-pd-field="site_footer_contact.slogan">{fc.slogan}</p>}
                {social.length > 0 && (
                  <div className="my-4 my-md-4">
                    <ul className="list-inline mb-0 opacity-7">
                      {social.map(([k, icon, url]) => (
                        <li className="list-inline-item mr-0" key={k + url}>
                          <a className="btn font-size-20 btn-icon btn-soft-dark btn-bg-transparent rounded-circle" href={url} target="_blank" rel="noreferrer noopener" aria-label={k}>
                            <span className={`${icon} btn-icon__inner`} />
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
              <div className="col-lg-7">
                <div className="row">
                  {roots.length > 0 && (
                    <>
                      <div className="col-12 col-md mb-4 mb-md-0">
                        {fl.categories_title && <h6 className="mb-3 font-weight-bold" data-pd-field="site_footer_links.categories_title">{fl.categories_title}</h6>}
                        <ul className="list-group list-group-flush list-group-borderless mb-0 list-group-transparent">
                          {roots.slice(0, half).map((c) => <li key={c.id}><Link className="list-group-item list-group-item-action" to={`/${c.slug}`}>{c.name}</Link></li>)}
                        </ul>
                      </div>
                      {roots.length > 1 && (
                        <div className="col-12 col-md mb-4 mb-md-0">
                          <ul className="list-group list-group-flush list-group-borderless mb-0 list-group-transparent mt-md-6">
                            {roots.slice(half).map((c) => <li key={c.id}><Link className="list-group-item list-group-item-action" to={`/${c.slug}`}>{c.name}</Link></li>)}
                          </ul>
                        </div>
                      )}
                    </>
                  )}
                  {columns.slice(0, roots.length ? 2 : 4).map((col, i) => (
                    <div className="col-12 col-md mb-4 mb-md-0" key={col._id || i}>
                      {col.title ? <h6 className="mb-3 font-weight-bold" data-pd-field={`site_footer_links.columns.${i}.title`}>{col.title}</h6> : <div className="mt-md-6" />}
                      <ul className="list-group list-group-flush list-group-borderless mb-0 list-group-transparent">
                        {(col.links || []).filter((l) => l && !l._hidden && l.label).map((l, j) => (
                          <li key={l._id || j}>
                            <SmartLink link={l.link} className="list-group-item list-group-item-action" fallback="span" field={`site_footer_links.columns.${i}.links.${j}.label`}>{l.label}</SmartLink>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="py-2" style={{ backgroundColor: fb.background || "#eaeaea" }} data-testid="footer-bottom">
        <div className="container">
          <div className="flex-center-between d-block d-md-flex">
            <div className="mb-3 mb-md-0">
              <RichText as="div" html={copyright} field="site_footer_bottom.copyright" />
              {(fb.extra_links || []).filter((l) => l && !l._hidden && l.label).length > 0 && (
                <div className="font-size-12 mt-1">
                  {(fb.extra_links || []).filter((l) => l && !l._hidden && l.label).map((l, i) => (
                    <SmartLink key={l._id || i} link={l.link} className="text-gray-90 mr-3" field={`site_footer_bottom.extra_links.${i}.label`}>{l.label}</SmartLink>
                  ))}
                </div>
              )}
              <DevCredit />
            </div>
            <div className="d-flex align-items-center">
              {fb.etbis_qr?.url && <SmartImage image={fb.etbis_qr} width={160} className="mr-3" style={{ maxHeight: 60, width: "auto" }} />}
              {fb.payment_mode === "band_image" ? <PaymentBand url={fb.payment_band_image?.url} />
                : fb.payment_mode === "logos" ? (
                  <div className="el-payband" data-testid="payment-icons">
                    {(fb.payment_logos || []).filter((x) => x && x.image?.url).map((x, i) => <img key={x._id || i} src={x.image.url} alt={x.alt} height="32" style={{ maxWidth: 52 }} className="ml-2" loading="lazy" />)}
                  </div>
                ) : fb.payment_mode === "none" ? null : <PaymentBand />}
            </div>
          </div>
        </div>
      </div>
      <GoToTop />
    </footer>
  );
}
