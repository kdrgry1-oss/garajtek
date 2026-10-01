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
        const parsed = parseFaqHtml(r?.data?.content || "");
        if (alive && parsed && parsed.length) { setData(parsed); setActiveTab(parsed[0].id); }
      })
      .catch(() => { /* yedek gömülü veri kalır */ });
    return () => { alive = false; };
  }, []);

  const panel = data.find((t) => t.id === activeTab) || data[0];

  return (
    <div className="sf-page min-h-screen bg-white flex flex-col">
      <Header />
      <main className="flex-1 max-w-[1200px] w-full mx-auto px-3 md:px-4 pt-8 pb-24">
        <h1 className="text-center text-[22px] md:text-[28px] font-bold mb-6 md:mb-8">Sıkça Sorulan Sorular</h1>

        {/* Sekmeler */}
        <div role="tablist" aria-label="SSS Kategorileri" className="flex flex-wrap justify-center gap-2.5 md:gap-3.5">
          {data.map((t) => {
            const active = t.id === activeTab;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                onClick={() => { setActiveTab(t.id); setOpenKey(null); }}
                className={`rounded-md px-3.5 py-3.5 md:px-5 md:py-4 min-w-[140px] md:min-w-[160px] text-xs md:text-sm font-bold tracking-wide transition-all bg-white ${
                  active ? "border border-black shadow-[0_0_0_1px_#111_inset]" : "border border-gray-200 hover:border-gray-400 hover:-translate-y-px"
                }`}
                type="button"
              >
                {t.label}
              </button>
            );
          })}
        </div>

        {/* Panel */}
        <div className="mt-5 md:mt-6">
          <div className="space-y-2.5">
            {panel.items.map((item, i) => {
              const key = `${panel.id}:${i}`;
              const open = openKey === key;
              return (
                <div key={key}>
                  <button
                    type="button"
                    onClick={() => setOpenKey(open ? null : key)}
                    className={`w-full text-left bg-white border border-gray-200 rounded-md px-4 py-4 flex items-center justify-between gap-3 font-semibold text-sm md:text-[15px] ${open ? "rounded-b-none" : ""}`}
                  >
                    <span>{item.q}</span>
                    <span className={`text-xl leading-none transition-transform ${open ? "rotate-90" : ""}`}>›</span>
                  </button>
                  {open && (
                    <div
                      className="bg-white border border-t-0 border-gray-200 rounded-b-md px-4 py-4 text-sm text-gray-700 font-normal leading-relaxed [&_b]:font-semibold [&_b]:text-black"
                      dangerouslySetInnerHTML={{ __html: sanitizeHtml(item.a) }}
                    />
                  )}
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
