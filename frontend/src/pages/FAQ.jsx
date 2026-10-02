/**
 * FAQ.jsx — Sıkça Sorulan Sorular (sekmeli + akordeon).
 * Sitenin fontu miras alınır (font-inherit). Sorular/önemli alanlar kalın, cevaplar ince.
 * İçerik kullanıcıdan geldiği için cevaplar HTML olarak (dangerouslySetInnerHTML) render edilir.
 */
import { useState, useEffect } from "react";
import axios from "axios";
import { sanitizeHtml } from "../lib/sanitizeHtml";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Breadcrumb from "../components/electro/Breadcrumb";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Admin "Sayfalar > Sıkça Sorulan Sorular" (slug: sss) içeriği <önek>FaqTab / FaqQ / FaqA /
// FaqIcon sınıf yapısındadır (önek serbest, ör. "storeFaqTab").
// Bunu ayrıştırıp sekmeli akordeon verisine çeviririz → SSS ARTIK PANELDEN DÜZENLENEBİLİR.
// Ayrıştırma başarısızsa aşağıdaki gömülü FAQ_DATA yedeğe düşer.
function parseFaqHtml(html) {
  try {
    if (!html || html.indexOf("FaqTab") === -1) return null;
    const doc = new DOMParser().parseFromString(html, "text/html");
    const hasCls = (el, suffix) => !!(el && el.classList) && Array.from(el.classList).some((c) => c.endsWith(suffix));
    const tabs = Array.from(doc.querySelectorAll('[class*="FaqTab"]')).filter((el) => hasCls(el, "FaqTab"));
    if (!tabs.length) return null;
    const out = [];
    tabs.forEach((tab, ti) => {
      const target = (tab.getAttribute("data-target") || "").replace("#", "");
      const label = (tab.textContent || "").trim();
      const panel = target ? doc.getElementById(target) : null;
      const items = [];
      if (panel) {
        Array.from(panel.querySelectorAll('[class*="FaqQ"]')).filter((el) => hasCls(el, "FaqQ")).forEach((q) => {
          const qc = q.cloneNode(true);
          Array.from(qc.querySelectorAll('[class*="FaqIcon"]')).filter((el) => hasCls(el, "FaqIcon")).forEach((s) => s.remove());
          let a = q.nextElementSibling;
          while (a && !hasCls(a, "FaqA")) a = a.nextElementSibling;
          items.push({ q: (qc.textContent || "").trim(), a: a ? a.innerHTML : "" });
        });
      }
      if (items.length) out.push({ id: target || `t${ti}`, label, items });
    });
    return out.length ? out : null;
  } catch { return null; }
}

// Zengin metin editöründen gelen sade yapı: <h3> = sekme, <h4> = soru, sonraki öğeler = yanıt.
// (CMS › Sayfalar › SSS bu düzende düzenlenir; FaqTab sınıflı eski içerik yukarıda ayrıştırılır.)
function parseHeadingFaq(html) {
  try {
    if (!html || !/<h3[\s>]/i.test(html) || !/<h4[\s>]/i.test(html)) return null;
    const doc = new DOMParser().parseFromString(`<div id="faq-root">${html}</div>`, "text/html");
    const root = doc.getElementById("faq-root");
    const out = [];
    let tab = null;
    let item = null;
    Array.from(root.children).forEach((el) => {
      const tag = el.tagName.toLowerCase();
      if (tag === "h3") {
        const label = (el.textContent || "").trim();
        tab = { id: `t${out.length}`, label, items: [] };
        out.push(tab);
        item = null;
      } else if (tag === "h4" && tab) {
        item = { q: (el.textContent || "").trim(), a: "" };
        tab.items.push(item);
      } else if (item) {
        item.a += el.outerHTML;
      }
    });
    const tabs = out.filter((t) => t.items.length);
    return tabs.length ? tabs : null;
  } catch { return null; }
}

// Gömülü yedek SSS — firmadan bağımsız, genel metin. Mağazaya özel bilgiler (kargo firması,
// iade adresi, destek hattı, süreler) panelden (Sayfalar > SSS) girilir.
const FAQ_DATA = [
  {
    id: "uyelik",
    label: "ÜYELİK",
    items: [
      { q: "Sipariş vermek için üye olmam gerekiyor mu?", a: 'Üye olarak ya da <b>"Üyeliksiz Devam Et"</b> seçeneğiyle sipariş oluşturabilirsiniz.' },
      { q: "Neden üye olmalıyım?", a: "Siparişlerinizin durumunu takip etmek, kampanyalardan haberdar olmak ve size özel avantajlardan faydalanmak için üye olabilirsiniz." },
      { q: "Üyelik bilgilerimi nasıl güncelleyebilirim?", a: 'Üye girişi yaptıktan sonra <b>"Hesabım"</b> bölümünden üyelik bilgilerinizi güncelleyebilirsiniz.' },
      { q: "Şifremi unuttum, ne yapmalıyım?", a: 'Üye girişi bölümündeki <b>"Şifremi Unuttum"</b> bağlantısına tıklayıp talimatları izleyebilirsiniz.' },
    ],
  },
  {
    id: "online",
    label: "ONLINE ALIŞVERİŞ",
    items: [
      { q: "Siparişimin onaylandığını nasıl anlayabilirim?", a: "Siparişiniz onaylandığında sipariş bilgileriniz kayıtlı e-posta adresinize gönderilir." },
      { q: "Siparişim onaylandıktan sonra değişiklik yapabilir miyim?", a: "Onaylanan siparişlerde değişiklik yapılamamaktadır; siparişinizi iptal edip yeniden oluşturabilirsiniz." },
    ],
  },
  {
    id: "odeme",
    label: "ÖDEME",
    items: [
      { q: "Ürün fiyatlarına KDV dâhil midir?", a: "Sitemizde satılan tüm ürünlerin fiyatlarına KDV dahildir." },
      { q: "Havale yoluyla ödeme yapabiliyor muyum?", a: "Havale/EFT seçeneği aktifse ödeme adımında seçebilirsiniz; banka bilgileri sipariş sonrası paylaşılır." },
      { q: "Taksit seçeneğiniz var mı?", a: "Kart bilgilerinizi girdikten sonra bankanızın sunduğu taksit seçeneklerini ödeme ekranında görebilirsiniz." },
      { q: "Kart bilgilerim güvende midir?", a: "Tüm veri iletimi SSL ile şifrelenir; kart bilgileriniz sitemizde saklanmaz ve ödemeler 3D Secure ile doğrulanır." },
    ],
  },
  {
    id: "kargo",
    label: "KARGO VE TESLİMAT",
    items: [
      { q: "Siparişim ne zaman kargoya verilir?", a: "Siparişiniz hazırlandıktan sonra anlaşmalı kargo firmamıza teslim edilir; kargo takip bilgisi e-posta ile iletilir." },
      { q: "Siparişimi nasıl takip edebilirim?", a: '<b>"Sipariş Takibi"</b> sayfasından ya da "Hesabım" bölümünden siparişinizin durumunu takip edebilirsiniz.' },
      { q: "Paket hasarlı geldi, teslim almalı mıyım?", a: "Hasarlı paketleri teslim almadan kargo görevlisine tutanak tutturmanızı, ardından müşteri hizmetlerimizle iletişime geçmenizi rica ederiz." },
    ],
  },
  {
    id: "iade",
    label: "İADE - DEĞİŞİM",
    items: [
      { q: "Ürünlerde iade süresi ne kadar?", a: "Kullanılmamış ve deforme olmamış ürünleri, yasal cayma süresi içinde iade edebilirsiniz. İade talebinizi <b>\"İade Talebi\"</b> sayfasından oluşturabilirsiniz." },
      { q: "Ürün iadesi yaptığımda ödediğim tutar bana nasıl iade edilecek?", a: "İade paketiniz kontrol edildikten sonra tutar, ödeme yönteminize uygun şekilde iade edilir. Bankanıza bağlı olarak hesabınıza yansıması birkaç iş günü sürebilir." },
      { q: "İade sürecim hakkında nasıl bilgi alabilirim?", a: "İade durumunuzu web sitemiz üzerinden takip edebilir, sorularınız için İletişim sayfasındaki kanallardan bize ulaşabilirsiniz." },
    ],
  },
];

export default function FAQ() {
  const [data, setData] = useState(FAQ_DATA);          // panel içeriği gelene kadar gömülü yedek
  const [activeTab, setActiveTab] = useState(FAQ_DATA[0].id);
  const [openKey, setOpenKey] = useState(null); // `${tabId}:${index}` — panel başına tek açık

  // Panelden (Sayfalar > SSS) düzenlenen içeriği çek → ayrıştır → kullan.
  useEffect(() => {
    let alive = true;
    axios.get(`${API}/pages/sss`)
      .then((r) => {
        const html = r?.data?.content || "";
        const parsed = parseFaqHtml(html) || parseHeadingFaq(html);
        if (alive && parsed && parsed.length) { setData(parsed); setActiveTab(parsed[0].id); }
      })
      .catch(() => { /* yedek gömülü veri kalır */ });
    return () => { alive = false; };
  }, []);

  const panel = data.find((t) => t.id === activeTab) || data[0];

  return (
    <div className="sf-page" data-testid="faq-page">
      <Header />
      <main id="content" role="main" className="electro el-page">
        <Breadcrumb items={[{ label: "Sıkça Sorulan Sorular" }]} />
        <div className="container">
          <div className="mb-8 text-center">
            <h1>Sıkça Sorulan Sorular</h1>
            <p className="text-gray-44">Aradığınız cevabı bulamazsanız <a href="/sayfa/iletisim" className="text-blue">bize ulaşın</a>.</p>
          </div>
          <div className="position-relative text-center z-index-2 mb-6">
            <ul className="nav nav-classic nav-tab nav-tab-sm px-md-3 justify-content-start justify-content-lg-center flex-nowrap flex-lg-wrap overflow-auto overflow-lg-visble border-md-down-bottom-0 pb-1 pb-lg-0 mb-n1 mb-lg-0" role="tablist" aria-label="SSS Kategorileri">
              {data.map((t) => {
                const active = t.id === activeTab;
                return (
                  <li className="nav-item flex-shrink-0 flex-lg-shrink-1" key={t.id}>
                    <a href={`#${t.id}`} role="tab" aria-selected={active} className={`nav-link${active ? " active" : ""}`}
                      onClick={(e) => { e.preventDefault(); setActiveTab(t.id); setOpenKey(null); }}>
                      <div className="d-md-flex justify-content-md-center align-items-md-center">{t.label}</div>
                    </a>
                  </li>
                );
              })}
            </ul>
          </div>
          <div className="border-bottom border-color-1 mb-6 rounded-0">
            <h3 className="section-title mb-0 pb-2 font-size-25">{panel.label}</h3>
          </div>
          <div id="basicsAccordion" className="mb-12">
            {panel.items.map((item, i) => {
              const key = `${panel.id}:${i}`;
              const open = openKey === key || (openKey === null && i === 0);
              return (
                <div className="card mb-3 border-top-0 border-left-0 border-right-0 border border-color-1 rounded-0" key={key}>
                  <div className="card-header card-collapse bg-transparent-on-hover border-0">
                    <h5 className="mb-0">
                      <button type="button" className={`px-0 btn btn-link btn-block d-flex justify-content-between card-btn py-3 font-size-20 border-0 text-left text-wrap${open ? "" : " collapsed"}`}
                        aria-expanded={open} onClick={() => setOpenKey(open ? `${panel.id}:none` : key)}>
                        <span>{item.q}</span>
                        <span className="card-btn-arrow flex-shrink-0"><i className={`fas ${open ? "fa-chevron-up" : "fa-chevron-down"} text-gray-90 font-size-18`} /></span>
                      </button>
                    </h5>
                  </div>
                  <div className={`collapse${open ? " show" : ""}`}>
                    <div className="card-body pl-0 pb-6 el-prose" dangerouslySetInnerHTML={{ __html: sanitizeHtml(item.a) }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  );
}
