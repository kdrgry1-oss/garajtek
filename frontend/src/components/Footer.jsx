/**
 * Footer.jsx — Electro footer (ürün widget'ları + sarı e-bülten şeridi + iletişim/link kolonları +
 * telif & ödeme şeridi). Admin'in `/api/footer-template` ayarı korunur:
 *   • mode = "html"        → custom_html (sanitize) alt bölümde render edilir
 *   • mode = "structured"  → columns / newsletter / social / copyright alanları kullanılır
 * E-bülten KVKK/İYS onay kutusu ZORUNLU olarak korunur.
 */
import { Link } from "react-router-dom";
import { useEffect, useState } from "react";
import axios from "axios";
import { sanitizeHtml } from "../lib/sanitizeHtml";
import { useStoreInfo } from "../lib/storeInfo";
import { socialUrl } from "../lib/brand";
import ProductCard from "./ProductCard";
import Logo from "./electro/Logo";
import useCategoryTree from "./electro/useCategoryTree";
import { optimizeImg } from "../lib/img";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// KVKK / ticari-ileti onay metni — kutucuk etiketiyle AYNI; abone kaydına ve İYS'ye işlenir.
const CONSENT_TEXT =
  "KVKK Aydınlatma Metni'ni okudum; kampanya ve fırsatlar için ticari elektronik ileti (e-posta) almayı kabul ediyorum.";

function NewsletterBand({ nl }) {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [state, setState] = useState("idle");
  const [msg, setMsg] = useState("");
  const title = nl?.title || "E-Bültene Kaydolun";
  const description = nl?.description || "...kampanya ve fırsatlardan ilk siz haberdar olun.";

  const submit = async (e) => {
    e.preventDefault();
    const v = (email || "").trim();
    if (!v || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v)) { setState("error"); setMsg("Lütfen geçerli bir e-posta adresi girin."); return; }
    if (!consent) { setState("error"); setMsg("Devam etmek için KVKK / ticari ileti onayını işaretlemelisiniz."); return; }
    setState("loading");
    try {
      const r = await axios.post(`${API}/newsletter/subscribe`, { email: v, source: "footer", consent: true, consent_text: CONSENT_TEXT });
      setState("done"); setMsg(r?.data?.message || "Aramıza hoş geldiniz!"); setEmail(""); setConsent(false);
    } catch (err) {
      setState("error"); setMsg(err?.response?.data?.detail || "Bir sorun oluştu, tekrar deneyin.");
    }
  };

  return (
    <div className="bg-primary py-3" data-testid="newsletter-band">
      <div className="container">
        <div className="row align-items-center">
          <div className="col-lg-7 mb-md-3 mb-lg-0">
            <div className="row align-items-center">
              <div className="col-auto flex-horizontal-center">
                <i className="ec ec-newsletter font-size-40" />
                <h2 className="font-size-20 mb-0 ml-3">{title}</h2>
              </div>
              <div className="col my-4 my-md-0">
                <h5 className="font-size-15 ml-4 mb-0">{description}</h5>
              </div>
            </div>
          </div>
          <div className="col-lg-5">
            {state === "done" ? (
              <div className="font-size-15 font-weight-bold py-2" data-testid="newsletter-done"><i className="fas fa-check-circle mr-2" />{msg}</div>
            ) : (
              <form onSubmit={submit} data-testid="newsletter-form" noValidate>
                <label className="sr-only" htmlFor="subscribeSrEmail">E-posta adresi</label>
                <div className="input-group input-group-pill">
                  <input type="email" className="form-control border-0 height-40" id="subscribeSrEmail" placeholder={nl?.placeholder || "E-posta adresiniz"}
                    value={email} onChange={(e) => { setEmail(e.target.value); if (state === "error") setState("idle"); }}
                    aria-label="E-posta adresi" data-testid="newsletter-email" />
                  <div className="input-group-append">
                    <button type="submit" className="btn btn-dark btn-sm-wide height-40 py-2" disabled={state === "loading"} data-testid="newsletter-submit">Kaydol</button>
                  </div>
                </div>
                <div className="custom-control custom-checkbox mt-2 font-size-12">
                  <input type="checkbox" className="custom-control-input" id="nlConsent" checked={consent}
                    onChange={(e) => { setConsent(e.target.checked); if (state === "error") setState("idle"); }} data-testid="newsletter-consent" />
                  <label className="custom-control-label text-gray-90" htmlFor="nlConsent">
                    <Link to="/sayfa/kvkk" className="text-gray-90 text-underline font-weight-bold">KVKK Aydınlatma Metni</Link>'ni okudum; kampanya ve fırsatlar için ticari elektronik ileti almayı kabul ediyorum.
                  </label>
                </div>
                {state === "error" && <div className="font-size-12 text-red mt-1" data-testid="newsletter-error">{msg}</div>}
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// Varsayılan "Müşteri Hizmetleri" sütunu (admin footer şablonu girilmemişse).
const DEFAULT_COLUMNS = [
  { title: "Müşteri Hizmetleri", links: [
    { to: "/hesabim", label: "Hesabım" },
    { to: "/siparis-takip", label: "Sipariş Takibi" },
    { to: "/favoriler", label: "Favorilerim" },
    { to: "/iade-islemleri", label: "İade Talebi" },
    { to: "/sayfa/iade-kosullari", label: "İade & Değişim" },
    { to: "/sikca-sorulan-sorular", label: "Sıkça Sorulan Sorular" },
    { to: "/sayfa/iletisim", label: "İletişim" },
  ]},
  { title: "Kurumsal", links: [
    { to: "/sayfa/hakkimizda", label: "Hakkımızda" },
    { to: "/sayfa/mesafeli-satis", label: "Mesafeli Satış Sözleşmesi" },
    { to: "/sayfa/kvkk", label: "KVKK Aydınlatma Metni" },
    { to: "/sayfa/gizlilik", label: "Gizlilik Politikası" },
  ]},
];

/** Footer üstü: Öne Çıkanlar / İndirimdekiler / Çok Satanlar mini listeleri (+ banner). */
let _widgetCache = null;
function FooterWidgets() {
  const [data, setData] = useState(_widgetCache);
  useEffect(() => {
    if (_widgetCache) return undefined;
    let alive = true;
    Promise.all([
      axios.get(`${API}/products?limit=3&is_featured=true`).catch(() => null),
      axios.get(`${API}/products/slider-feed?source=discounted&limit=3`).catch(() => null),
      axios.get(`${API}/products?limit=3&sort=popular`).catch(() => null),
      axios.get(`${API}/banners?position=footer&is_active=true`).catch(() => null),
    ]).then(([f, d, p, b]) => {
      let featured = f?.data?.products || [];
      const popular = p?.data?.products || [];
      if (!featured.length) featured = popular;
      const out = { featured, discounted: d?.data?.products || [], popular, banner: (Array.isArray(b?.data) ? b.data : [])[0] || null };
      _widgetCache = out;
      if (alive) setData(out);
    });
    return () => { alive = false; };
  }, []);
  if (!data) return null;
  const cols = [
    ["Öne Çıkan Ürünler", data.featured],
    ["İndirimdeki Ürünler", data.discounted],
    ["Çok Satanlar", data.popular],
  ].filter(([, list]) => list.length);
  if (!cols.length) return null;
  return (
    <div className="container d-none d-lg-block mb-3" data-testid="footer-widgets">
      <div className="row">
        {cols.map(([title, list]) => (
          <div className="col-wd-3 col-lg-4" key={title}>
            <div className="widget-column">
              <div className="border-bottom border-color-1 mb-5">
                <h3 className="section-title section-title__sm mb-0 pb-2 font-size-18">{title}</h3>
              </div>
              <ul className="list-unstyled products-group">
                {list.slice(0, 3).map((p) => <ProductCard key={p.id} product={p} variant="list" as="li" />)}
              </ul>
            </div>
          </div>
        ))}
        {data.banner && (data.banner.image_url || data.banner.image) && (
          <div className="col-wd-3 d-none d-wd-block">
            <Link to={data.banner.link_url || data.banner.link || "/"} className="d-block">
              <img className="img-fluid" src={optimizeImg(data.banner.image_url || data.banner.image, 660)} alt={data.banner.title || ""} loading="lazy" />
            </Link>
          </div>
        )}
      </div>
    </div>
  );
}

function PaymentBadges() {
  const badge = (label, inner) => (
    <span className="d-inline-block bg-white border rounded p-1 ml-1 el-pay" aria-label={label} title={label}>{inner}</span>
  );
  return (
    <div className="text-md-right" data-testid="payment-icons">
      {badge("Visa", <span className="el-pay__visa">VISA</span>)}
      {badge("Mastercard", (
        <svg width="34" height="20" viewBox="0 0 34 20" aria-hidden="true"><circle cx="13" cy="10" r="8" fill="#eb001b" /><circle cx="21" cy="10" r="8" fill="#f79e1b" fillOpacity=".9" /></svg>
      ))}
      {badge("American Express", <span className="el-pay__amex">AMEX</span>)}
      {badge("Troy", <span className="el-pay__troy">troy</span>)}
      {badge("iyzico ile güvenli ödeme", <span className="el-pay__iyz"><i className="fas fa-lock mr-1" />iyzico</span>)}
    </div>
  );
}

export default function Footer() {
  const [tpl, setTpl] = useState(null);
  const info = useStoreInfo();
  const tree = useCategoryTree();

  useEffect(() => {
    let cancel = false;
    axios.get(`${API}/footer-template`)
      .then((r) => { if (!cancel) setTpl(r.data); })
      .catch(() => { if (!cancel) setTpl(null); });
    return () => { cancel = true; };
  }, []);

  let columns = Array.isArray(tpl?.columns) && tpl.columns.length ? tpl.columns : DEFAULT_COLUMNS;
  // "İade Talebi" linki her zaman görünür olsun (admin sütunları override etse bile)
  if (!columns.some((c) => (c.links || []).some((l) => l.to === "/iade-islemleri"))) {
    columns = columns.map((c, i) => (i === 0 && c.links ? { ...c, links: [...c.links, { to: "/iade-islemleri", label: "İade Talebi" }] } : c));
  }
  const s = tpl?.social || {};
  const social = [
    ["facebook", "fab fa-facebook-f", s.facebook],
    ["instagram", "fab fa-instagram", s.instagram || socialUrl("instagram", info.instagram)],
    ["twitter", "fab fa-twitter", s.twitter],
    ["youtube", "fab fa-youtube", s.youtube],
    ["tiktok", "fab fa-tiktok", s.tiktok || socialUrl("tiktok", info.tiktok)],
  ].filter(([, , url]) => url);
  const copyright = tpl?.copyright || null;
  const roots = tree.roots.slice(0, 12);
  const half = Math.ceil(roots.length / 2);

  return (
    <footer className="electro el-footer" data-testid={tpl?.mode === "html" ? "footer-html" : "footer-structured"}>
      <FooterWidgets />
      <NewsletterBand nl={tpl?.newsletter} />
      {tpl?.mode === "html" && tpl?.custom_html ? (
        <div className="pt-8 pb-4 bg-gray-13">
          <div className="container mt-1" dangerouslySetInnerHTML={{ __html: sanitizeHtml(tpl.custom_html) }} />
        </div>
      ) : (
        <div className="pt-8 pb-4 bg-gray-13">
          <div className="container mt-1">
            <div className="row">
              <div className="col-lg-5">
                <div className="mb-6"><Logo className="d-inline-block" /></div>
                <div className="mb-4">
                  <div className="row no-gutters">
                    <div className="col-auto"><i className="ec ec-support text-primary font-size-56" /></div>
                    <div className="col pl-3">
                      <div className="font-size-13 font-weight-light">Sorunuz mu var? Bize ulaşın!</div>
                      {info.phone
                        ? <a href={`tel:${info.phone.replace(/\s/g, "")}`} className="font-size-20 text-gray-90">{info.phone}</a>
                        : <Link to="/sayfa/iletisim" className="font-size-20 text-gray-90">İletişim</Link>}
                      {info.whatsapp && <div className="font-size-14 mt-1"><i className="fab fa-whatsapp mr-1" />{info.whatsapp}</div>}
                    </div>
                  </div>
                </div>
                {(info.address || info.email) && (
                  <div className="mb-4">
                    <h6 className="mb-1 font-weight-bold">İletişim Bilgileri</h6>
                    {info.address && <address className="mb-1">{info.address}</address>}
                    {info.email && <a href={`mailto:${info.email}`} className="text-gray-90">{info.email}</a>}
                  </div>
                )}
                {tpl?.slogan && <p className="font-size-13 text-gray-90">{tpl.slogan}</p>}
                {social.length > 0 && (
                  <div className="my-4 my-md-4">
                    <ul className="list-inline mb-0 opacity-7">
                      {social.map(([k, icon, url]) => (
                        <li className="list-inline-item mr-0" key={k}>
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
                        <h6 className="mb-3 font-weight-bold">Hızlı Erişim</h6>
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
                  {columns.slice(0, roots.length ? 2 : 3).map((col, i) => (
                    <div className="col-12 col-md mb-4 mb-md-0" key={col.title || i}>
                      <h6 className="mb-3 font-weight-bold">{col.title}</h6>
                      <ul className="list-group list-group-flush list-group-borderless mb-0 list-group-transparent">
                        {(col.links || []).map((l) => (
                          <li key={l.to + l.label}><Link className="list-group-item list-group-item-action" to={l.to}>{l.label}</Link></li>
                        ))}
                        {(col.static || []).map((t, j) => <li key={j} className="list-group-item">{t}</li>)}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
      <div className="bg-gray-14 py-2">
        <div className="container">
          <div className="flex-center-between d-block d-md-flex">
            <div className="mb-3 mb-md-0">
              {copyright || <>© {new Date().getFullYear()} <Link to="/" className="font-weight-bold text-gray-90">{info.name}</Link> - Tüm hakları saklıdır</>}
            </div>
            <PaymentBadges />
          </div>
        </div>
      </div>
    </footer>
  );
}
