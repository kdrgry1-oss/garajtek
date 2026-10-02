# -*- coding: utf-8 -*-
"""Kurumsal / hukuki CMS sayfalarının VARSAYILAN içerikleri (sürüm: LEGAL_SEED_VERSION).

• Metinler özgündür; 6502 sayılı TKHK, Mesafeli Sözleşmeler Yönetmeliği, Garanti Belgesi
  Yönetmeliği, 6698 sayılı KVKK (md.9 — 7499 s. Kanun ile değişik hâli), 6563 sayılı ETDHK ve
  İYS düzenlemeleri esas alınarak hazırlanmıştır. YAYINDAN ÖNCE BİR HUKUKÇUYA KONTROL
  ETTİRİLMESİ ÖNERİLİR.
• Firma bilgisi metne GÖMÜLMEZ: {{sirket.*}} / {{site.*}} yer tutucuları sayfa sunulurken
  (GET /api/pages/{slug}) Ayarlar › Şirket Bilgileri'nden doldurulur (bkz. legal_pages.py).
• {{alici.*}} / {{siparis.*}} yer tutucuları ödeme ekranındaki sözleşme penceresinde
  sipariş verileriyle doldurulur; normal sayfa görünümünde açıklama metni gösterilir.
• Admin bu sayfaları CMS › Sayfalar'dan düzenleyebilir; düzenlenmiş sayfaya seed dokunmaz.
"""

LEGAL_SEED_VERSION = 1

# Eski / alternatif adresler → kanonik slug (eski linkler ve sahibin istediği adresler çalışsın).
SLUG_ALIASES = {
    "kvkk-aydinlatma-metni": "kvkk",
    "gizlilik-politikasi": "gizlilik",
    "mesafeli-satis-sozlesmesi": "mesafeli-satis",
    "on-bilgilendirme-formu": "on-bilgilendirme",
    "iade-ve-degisim": "iade-kosullari",
    "teslimat-ve-kargo": "kargo-ve-teslimat",
    "garanti-ve-teknik-servis": "garanti-kosullari",
    "cerezler": "cerez-politikasi",
    "sikca-sorulan-sorular": "sss",
}

_SATICI_BLOK = """<table>
<tbody>
<tr><th>Ünvan</th><td>{{sirket.unvan}}</td></tr>
<tr><th>Marka / Site</th><td>{{site.ad}} — {{site.url}}</td></tr>
<tr><th>Adres</th><td>{{sirket.adres}}</td></tr>
<tr><th>Telefon</th><td>{{sirket.telefon}}</td></tr>
<tr><th>E-posta</th><td>{{sirket.eposta}}</td></tr>
<tr><th>KEP Adresi</th><td>{{sirket.kep}}</td></tr>
<tr><th>Vergi Dairesi / VKN</th><td>{{sirket.vergi_dairesi}} / {{sirket.vkn}}</td></tr>
<tr><th>MERSİS No</th><td>{{sirket.mersis}}</td></tr>
<tr><th>Ticaret Sicil No</th><td>{{sirket.ticaret_sicil}}</td></tr>
</tbody>
</table>"""

_ALICI_BLOK = """<table>
<tbody>
<tr><th>Ad Soyad / Ünvan</th><td>{{alici.ad}}</td></tr>
<tr><th>Teslimat Adresi</th><td>{{alici.adres}}</td></tr>
<tr><th>Telefon</th><td>{{alici.telefon}}</td></tr>
<tr><th>E-posta</th><td>{{alici.eposta}}</td></tr>
<tr><th>Fatura Bilgileri</th><td>{{alici.fatura}}</td></tr>
</tbody>
</table>"""

_SIPARIS_BLOK = """<p><strong>Sipariş tarihi:</strong> {{siparis.tarih}}</p>
{{siparis.urunler}}
<table>
<tbody>
<tr><th>Ürünler toplamı (KDV dahil)</th><td>{{siparis.ara_toplam}}</td></tr>
<tr><th>İndirimler</th><td>{{siparis.indirim}}</td></tr>
<tr><th>Kargo / teslimat bedeli</th><td>{{siparis.kargo}}</td></tr>
<tr><th>Toplam ödenecek tutar (KDV dahil)</th><td><strong>{{siparis.toplam}}</strong></td></tr>
<tr><th>Ödeme yöntemi</th><td>{{siparis.odeme}}</td></tr>
</tbody>
</table>"""

_CAYMA_ISTISNALARI = """<ul>
<li>Fiyatı finansal piyasalardaki dalgalanmalara bağlı olarak değişen ve satıcının kontrolünde olmayan mallar,</li>
<li>Alıcının istekleri veya kişisel ihtiyaçları doğrultusunda hazırlanan, ölçüye / projeye özel üretilen, kesilen, boyanan veya özel sipariş üzerine yurt dışından getirtilen mallar,</li>
<li>Çabuk bozulabilen veya son kullanma tarihi geçebilecek mallar,</li>
<li>Tesliminden sonra ambalaj, bant, mühür, paket gibi koruyucu unsurları açılmış olup iadesi sağlık ve hijyen açısından uygun olmayan mallar,</li>
<li>Tesliminden sonra başka ürünlerle karışan ve doğası gereği ayrıştırılması mümkün olmayan mallar (ör. kullanılmış yağ, gres, kimyasal sarf malzemeleri),</li>
<li>Ambalajı açılmış yazılım, lisans kodu, dijital içerik ve elektronik ortamda anında ifa edilen hizmetler,</li>
<li>Cayma süresi sona ermeden önce alıcının onayıyla ifasına başlanan hizmetler (ör. talep üzerine yapılan kurulum, montaj, devreye alma hizmeti).</li>
</ul>"""

_CAYMA_FORMU = """<h4>Cayma Formu (örnek)</h4>
<p>Kime: {{sirket.unvan}} — {{sirket.adres}} — {{sirket.eposta}}</p>
<p>Bu formla aşağıdaki ürünlere ilişkin mesafeli satış sözleşmesinden cayma hakkımı kullandığımı bildiririm.</p>
<ul>
<li>Sipariş numarası / tarihi: ……………………</li>
<li>Ürün(ler) ve adet: ……………………</li>
<li>Teslim aldığım tarih: ……………………</li>
<li>Ad soyad, adres, telefon: ……………………</li>
<li>İade edilecek IBAN (havale / kapıda ödeme siparişlerinde): ……………………</li>
<li>Tarih ve imza (yazılı bildirimde): ……………………</li>
</ul>"""

LEGAL_PAGES = [
    # ------------------------------------------------------------------ HAKKIMIZDA
    {
        "slug": "hakkimizda",
        "title": "Hakkımızda",
        "meta_title": "Hakkımızda | {{site.ad}}",
        "meta_description": "{{site.ad}}: oto servis, lastikçi ve garaj atölyeleri için lift, kompresör, lastik ekipmanı ve atölye donanımı.",
        "content": """<p class="lead"><strong>{{site.ad}}</strong>, oto servisleri, lastikçiler, kaporta-boya atölyeleri, filo bakım noktaları ve kendi garajını donatmak isteyen meraklılar için profesyonel atölye ekipmanlarını tek çatı altında sunan bir çevrim içi mağazadır.</p>
<h3>Ne yapıyoruz?</h3>
<p>Araç liftlerinden kompresörlere, lastik sökme-takma ve balans makinelerinden hidrolik kriko, pres ve motor vinçlerine, el aletlerinden arıza tespit cihazlarına kadar bir atölyenin ihtiyaç duyduğu ekipmanı seçiyor, teknik bilgisiyle birlikte sunuyor ve kapınıza kadar ulaştırıyoruz.</p>
<h3>Neden {{site.ad}}?</h3>
<ul>
<li><strong>Doğru ürün, doğru bilgi:</strong> Kapasite, elektrik bağlantısı, zemin ve kurulum şartları gibi teknik bilgileri satın almadan önce açıkça paylaşırız; emin olamadığınızda ekibimiz size uygun ürünü birlikte seçer.</li>
<li><strong>Faturalı ve garantili satış:</strong> Tüm ürünler faturalı ve garanti belgeli olarak gönderilir; satış sonrası teknik servis ve yedek parça süreçlerinde yanınızdayız.</li>
<li><strong>Ağır yük tecrübesi:</strong> Lift, kompresör gibi büyük hacimli ürünleri paletli ve sigortalı şekilde, anlaşmalı nakliye ve ambar firmalarıyla güvenle taşıtırız.</li>
<li><strong>Güvenli ödeme:</strong> Kart ödemeleri lisanslı ödeme kuruluşu altyapısında 3D Secure ile alınır; havale/EFT ve uygun siparişlerde kapıda ödeme seçenekleri sunulur.</li>
<li><strong>Kurumsal alımlara uygun:</strong> Servis ve işletmeler için kurumsal fatura, e-fatura ve toplu alım desteği sağlarız.</li>
</ul>
<h3>Kurumsal bilgiler</h3>
<p>{{site.ad}}, <strong>{{sirket.unvan}}</strong> tarafından işletilmektedir.<br>
Adres: {{sirket.adres}}<br>
Telefon: {{sirket.telefon}} · E-posta: {{sirket.eposta}}<br>
Vergi Dairesi / No: {{sirket.vergi_dairesi}} / {{sirket.vkn}} · MERSİS: {{sirket.mersis}}</p>
<p>Atölyenizi kurarken ya da büyütürken aklınıza takılan her soru için <a href="/sayfa/iletisim">bize ulaşabilirsiniz</a>.</p>""",
    },
    # ------------------------------------------------------------------ İLETİŞİM
    {
        "slug": "iletisim",
        "title": "İletişim",
        "meta_title": "İletişim | {{site.ad}}",
        "meta_description": "{{site.ad}} iletişim bilgileri: adres, telefon, e-posta ve kurumsal bilgiler.",
        "content": """<p class="lead">Sipariş, ürün seçimi, kurulum, garanti ve kurumsal alımlarla ilgili tüm sorularınız için bize aşağıdaki kanallardan ulaşabilirsiniz.</p>
<h3>Adres</h3>
<p>{{sirket.unvan}}<br>{{sirket.adres}}</p>
<p><a href="https://www.google.com/maps/search/?api=1&amp;query={{sirket.adres_url}}" target="_blank" rel="noopener noreferrer">Haritada görüntüle</a></p>
<h3>Telefon / WhatsApp</h3>
<p><a href="tel:{{sirket.telefon_tel}}">{{sirket.telefon}}</a></p>
<h3>E-posta</h3>
<p><a href="mailto:{{sirket.eposta}}">{{sirket.eposta}}</a></p>
<h3>Çalışma Saatleri</h3>
<p>Pazartesi – Cumartesi: 09:00 – 18:00<br>Pazar ve resmî tatiller: kapalı (siparişleriniz 7/24 alınır).</p>
<h3>Kurumsal Bilgiler</h3>
<p>Ünvan: {{sirket.unvan}}<br>
Vergi Dairesi: {{sirket.vergi_dairesi}} · VKN: {{sirket.vkn}}<br>
MERSİS No: {{sirket.mersis}} · Ticaret Sicil No: {{sirket.ticaret_sicil}}<br>
KEP Adresi: {{sirket.kep}}<br>
Web: {{site.url}}</p>
<h3>Şikâyet ve Başvuru Yolları</h3>
<p>Önce bize ulaşmanızı rica ederiz; çözümsüz kalan tüketici uyuşmazlıklarında, Ticaret Bakanlığınca her yıl ilan edilen parasal sınırlar dahilinde yerleşim yerinizdeki veya işlemin yapıldığı yerdeki Tüketici Hakem Heyetine ya da Tüketici Mahkemesine başvurabilirsiniz. Başvurular e-Devlet üzerinden TÜBİS ile de yapılabilir.</p>""",
    },
    # ------------------------------------------------------------------ KVKK
    {
        "slug": "kvkk",
        "title": "KVKK Aydınlatma Metni",
        "meta_title": "KVKK Aydınlatma Metni | {{site.ad}}",
        "meta_description": "{{sirket.unvan}} 6698 sayılı KVKK kapsamında kişisel verilerin işlenmesine ilişkin aydınlatma metni.",
        "content": """<p>Bu aydınlatma metni, 6698 sayılı Kişisel Verilerin Korunması Kanunu'nun ("KVKK") 10. maddesi ve Aydınlatma Yükümlülüğünün Yerine Getirilmesinde Uyulacak Usul ve Esaslar Hakkında Tebliğ uyarınca, {{site.url}} internet sitesini ("Site") ziyaret eden, üye olan, sipariş veren, bizimle iletişime geçen gerçek kişileri bilgilendirmek amacıyla hazırlanmıştır.</p>
<h3>1. Veri Sorumlusu</h3>
<p>Kişisel verileriniz, veri sorumlusu sıfatıyla <strong>{{sirket.unvan}}</strong> ("{{site.ad}}" veya "Şirket") tarafından işlenmektedir.<br>
Adres: {{sirket.adres}} · Telefon: {{sirket.telefon}} · E-posta: {{sirket.eposta}} · KEP: {{sirket.kep}} · MERSİS: {{sirket.mersis}}</p>
<h3>2. İşlenen Kişisel Veri Kategorileri</h3>
<table>
<thead><tr><th>Kategori</th><th>Örnek veriler</th></tr></thead>
<tbody>
<tr><td>Kimlik</td><td>Ad, soyad; e-fatura/e-arşiv için gerektiğinde T.C. kimlik numarası</td></tr>
<tr><td>İletişim</td><td>Telefon, e-posta, teslimat ve fatura adresi</td></tr>
<tr><td>Müşteri işlem</td><td>Sipariş, sepet, fatura, iade, talep ve şikâyet kayıtları, yazışmalar</td></tr>
<tr><td>Finans</td><td>Ödeme tutarı, ödeme yöntemi, iade için IBAN; kart numarası Şirket tarafından saklanmaz</td></tr>
<tr><td>Kurumsal alıcı bilgisi</td><td>Firma ünvanı, vergi dairesi ve numarası, yetkili kişi bilgileri</td></tr>
<tr><td>İşlem güvenliği</td><td>IP adresi, oturum ve giriş kayıtları, cihaz/tarayıcı bilgisi, şifre özetleri</td></tr>
<tr><td>Pazarlama</td><td>Çerez verileri, kampanya tercihleri, ticari elektronik ileti onayları (yalnızca açık rıza / onay ile)</td></tr>
<tr><td>Görsel / işitsel</td><td>Hasar veya arıza bildirimi için tarafınızca gönderilen fotoğraf ve videolar</td></tr>
</tbody>
</table>
<p>Özel nitelikli kişisel verileriniz (sağlık, din, biyometrik vb.) işlenmemektedir; lütfen bu tür bilgileri formlarda paylaşmayınız.</p>
<h3>3. İşleme Amaçları</h3>
<ul>
<li>Üyelik oluşturulması ve hesabın yönetilmesi,</li>
<li>Siparişin alınması, ödemenin tahsili, ürünün hazırlanması, kargo / nakliye ile teslimi ve kurulum randevusunun planlanması,</li>
<li>Fatura, e-fatura ve e-arşiv faturanın düzenlenmesi, muhasebe ve vergi yükümlülüklerinin yerine getirilmesi,</li>
<li>Cayma, iade, değişim, garanti ve teknik servis süreçlerinin yürütülmesi,</li>
<li>Talep, soru ve şikâyetlerin yanıtlanması; müşteri hizmetleri kalitesinin ölçülmesi,</li>
<li>Bilgi güvenliğinin sağlanması, dolandırıcılık ve kötüye kullanımın önlenmesi, log kayıtlarının tutulması,</li>
<li>Yetkili kamu kurum ve kuruluşlarının talep ve denetimlerine yanıt verilmesi, hukuki uyuşmazlıklarda hakların korunması,</li>
<li>Açık rızanız / onayınız bulunması halinde kampanya, indirim ve yeni ürün duyurularının iletilmesi, size özel öneriler sunulması.</li>
</ul>
<h3>4. Toplama Yöntemi ve Hukuki Sebepler</h3>
<p>Kişisel verileriniz; Site, üyelik ve sipariş formları, e-posta, telefon, WhatsApp, sosyal medya hesaplarımız, çerezler ve benzeri teknolojiler aracılığıyla, kısmen veya tamamen otomatik yollarla ya da veri kayıt sisteminin parçası olarak otomatik olmayan yollarla toplanır ve KVKK md.5/2'de yer alan şu hukuki sebeplere dayanılarak işlenir:</p>
<ul>
<li><strong>Kanunlarda açıkça öngörülmesi (md.5/2-a)</strong> ve <strong>hukuki yükümlülüğün yerine getirilmesi (md.5/2-ç)</strong>: 6502 sayılı Tüketicinin Korunması Hakkında Kanun, 6563 sayılı Elektronik Ticaretin Düzenlenmesi Hakkında Kanun, 213 sayılı Vergi Usul Kanunu, 6102 sayılı Türk Ticaret Kanunu, 5651 sayılı Kanun ve ilgili mevzuat kapsamındaki saklama ve bildirim yükümlülükleri,</li>
<li><strong>Sözleşmenin kurulması veya ifası (md.5/2-c)</strong>: üyelik ve mesafeli satış sözleşmesinin kurulması, siparişin teslimi, iade ve garanti işlemleri,</li>
<li><strong>Bir hakkın tesisi, kullanılması veya korunması (md.5/2-e)</strong>: uyuşmazlıklarda delil olarak kullanılması,</li>
<li><strong>Meşru menfaat (md.5/2-f)</strong>: bilgi güvenliği, hizmet kalitesinin iyileştirilmesi, zorunlu çerezler ve anonim istatistikler,</li>
<li><strong>Açık rıza (md.5/1)</strong>: pazarlama amaçlı iletişim, kişiselleştirilmiş reklam ve analitik / pazarlama çerezleri ile yurt dışına aktarımın açık rızaya dayandığı haller.</li>
</ul>
<h3>5. Kişisel Verilerin Aktarılması</h3>
<p>Kişisel verileriniz, yukarıdaki amaçlarla ve KVKK md.8 ve md.9'a uygun olarak, yalnızca gerekli olduğu ölçüde aşağıdaki alıcı gruplarına aktarılabilir:</p>
<ul>
<li><strong>Kargo ve lojistik firmaları</strong> (ör. MNG Kargo, Aras Kargo, PTT Kargo, anlaşmalı ambar / nakliye firmaları): teslimat için ad, adres, telefon,</li>
<li><strong>Ödeme kuruluşu ve bankalar</strong> (ör. iyzico — İyzi Ödeme ve Elektronik Para Hizmetleri A.Ş.): ödemenin alınması, iadesi ve dolandırıcılık kontrolleri,</li>
<li><strong>E-fatura / e-arşiv entegratörü</strong> (ör. BirFatura) ve Gelir İdaresi Başkanlığı: faturalandırma,</li>
<li><strong>Barındırma, altyapı ve güvenlik hizmeti sağlayıcıları</strong> (ör. Cloudflare — içerik dağıtımı ve saldırı koruması), yazılım ve bakım destek firmaları,</li>
<li><strong>SMS, e-posta ve İleti Yönetim Sistemi (İYS) hizmet sağlayıcıları</strong>: bilgilendirme ve, onay varsa, ticari ileti gönderimi,</li>
<li><strong>Kurulum ve teknik servis iş ortakları, üretici / distribütörler</strong>: kurulum, garanti ve onarım işlemleri,</li>
<li><strong>Muhasebe, mali müşavirlik, hukuk ve denetim danışmanları</strong>,</li>
<li><strong>Yetkili kamu kurum ve kuruluşları</strong> (ör. Ticaret Bakanlığı, Gelir İdaresi, yargı mercileri, kolluk) ile kanunen yetkili özel kişiler.</li>
</ul>
<h4>Yurt dışına aktarım</h4>
<p>Site altyapısında kullanılan bazı hizmet sağlayıcıların (ör. Cloudflare, e-posta gönderim hizmetleri) sunucuları yurt dışında bulunabilir. Bu aktarımlar, 7499 sayılı Kanun ile değişik KVKK md.9 uyarınca; hakkında yeterlilik kararı bulunan ülkelere, yeterlilik kararı yoksa Kurul tarafından ilan edilen <strong>standart sözleşmenin</strong> imzalanması ve imzadan itibaren beş iş günü içinde Kurum'a bildirilmesi gibi <strong>uygun güvencelerden</strong> biri sağlanarak; bunların mümkün olmadığı arızi hallerde ise md.9'daki istisnalara (ör. açık rıza, sözleşmenin ifası için zorunluluk) dayanılarak gerçekleştirilir.</p>
<h3>6. Saklama Süreleri</h3>
<p>Kişisel verileriniz işleme amacının gerektirdiği süre ve ilgili mevzuatta öngörülen azami süreler boyunca saklanır; süre sonunda Kişisel Verilerin Silinmesi, Yok Edilmesi veya Anonim Hale Getirilmesi Hakkında Yönetmelik'e uygun olarak silinir, yok edilir veya anonimleştirilir. Örnek olarak:</p>
<ul>
<li>Sipariş, sözleşme ve fatura kayıtları: Vergi Usul Kanunu ve Türk Ticaret Kanunu uyarınca 5 ila 10 yıl,</li>
<li>Mesafeli sözleşme ve ön bilgilendirme kayıtları: en az 3 yıl,</li>
<li>Site trafik / log kayıtları: 5651 sayılı Kanun ve ikincil düzenlemelerde öngörülen süre (en az 1, en fazla 2 yıl),</li>
<li>Ticari elektronik ileti onay ve ret kayıtları: onayın geri alınmasından itibaren 3 yıl,</li>
<li>Üyelik bilgileri: üyelik süresince ve üyeliğin sona ermesinden sonra olası uyuşmazlıklar için genel zamanaşımı süresi boyunca.</li>
</ul>
<h3>7. İlgili Kişinin Hakları (KVKK md.11)</h3>
<p>Şirketimize başvurarak kişisel verilerinizle ilgili olarak;</p>
<ol type="a">
<li>işlenip işlenmediğini öğrenme,</li>
<li>işlenmişse buna ilişkin bilgi talep etme,</li>
<li>işlenme amacını ve amacına uygun kullanılıp kullanılmadığını öğrenme,</li>
<li>yurt içinde veya yurt dışında aktarıldığı üçüncü kişileri bilme,</li>
<li>eksik veya yanlış işlenmişse düzeltilmesini isteme,</li>
<li>KVKK md.7'deki şartlar çerçevesinde silinmesini veya yok edilmesini isteme,</li>
<li>(e) ve (f) bentleri uyarınca yapılan işlemlerin verilerin aktarıldığı üçüncü kişilere bildirilmesini isteme,</li>
<li>münhasıran otomatik sistemler vasıtasıyla analiz edilmesi suretiyle aleyhinize bir sonucun ortaya çıkmasına itiraz etme,</li>
<li>kanuna aykırı işlenmesi sebebiyle zarara uğramanız halinde zararın giderilmesini talep etme</li>
</ol>
<p>haklarına sahipsiniz.</p>
<h3>8. Başvuru Yöntemi</h3>
<p>Haklarınıza ilişkin taleplerinizi, Veri Sorumlusuna Başvuru Usul ve Esasları Hakkında Tebliğ'e uygun olarak, kimliğinizi tespit edici bilgilerle birlikte:</p>
<ul>
<li>ıslak imzalı dilekçe ile şahsen veya noter aracılığıyla <strong>{{sirket.adres}}</strong> adresine,</li>
<li>güvenli elektronik imza veya mobil imza ile imzalanmış olarak ya da kayıtlı elektronik posta (KEP) ile <strong>{{sirket.kep}}</strong> adresine,</li>
<li>Şirketimizde kayıtlı e-posta adresinizden <strong>{{sirket.eposta}}</strong> adresine</li>
</ul>
<p>iletebilirsiniz. Başvurunuz, talebin niteliğine göre en kısa sürede ve en geç <strong>30 gün</strong> içinde ücretsiz olarak sonuçlandırılır; işlemin ayrıca bir maliyet gerektirmesi halinde Kurul'ca belirlenen tarifedeki ücret talep edilebilir. Başvurunuzun reddedilmesi, cevabı yetersiz bulmanız veya süresinde cevap verilmemesi hallerinde Kişisel Verileri Koruma Kurulu'na şikâyette bulunabilirsiniz.</p>
<h3>9. Veri Sorumluları Sicili (VERBİS)</h3>
<p>Şirketimizin Veri Sorumluları Siciline kayıt yükümlülüğü, Kişisel Verileri Koruma Kurulu'nun belirlediği istisna kriterleri (çalışan sayısı, yıllık mali bilanço ve ana faaliyet konusu) çerçevesinde değerlendirilmekte; yükümlülük doğması halinde kayıt yaptırılmaktadır.</p>
<p>Ayrıntılı bilgi için <a href="/sayfa/gizlilik">Gizlilik Politikası</a> ve <a href="/sayfa/cerez-politikasi">Çerez Politikası</a> sayfalarımızı inceleyebilirsiniz.</p>""",
    },
    # ------------------------------------------------------------------ GİZLİLİK
    {
        "slug": "gizlilik",
        "title": "Gizlilik Politikası",
        "meta_title": "Gizlilik Politikası | {{site.ad}}",
        "meta_description": "{{site.ad}} gizlilik ve güvenlik politikası: verilerinizi nasıl koruyoruz, ödeme güvenliği ve haklarınız.",
        "content": """<p>{{sirket.unvan}} olarak, {{site.url}} adresinde alışveriş yapan ve Siteyi ziyaret eden herkesin gizliliğine saygı duyuyoruz. Bu politika, hangi bilgileri neden topladığımızı, nasıl koruduğumuzu ve sizin hangi seçeneklere sahip olduğunuzu sade bir dille açıklar. Kişisel verilerin işlenmesine ilişkin yasal aydınlatma için <a href="/sayfa/kvkk">KVKK Aydınlatma Metni</a>'ni inceleyiniz.</p>
<h3>1. Hangi bilgileri topluyoruz?</h3>
<ul>
<li><strong>Sizin verdiğiniz bilgiler:</strong> üyelik, sipariş, iletişim ve iade formlarında paylaştığınız ad-soyad, iletişim, adres, fatura ve (kurumsal alımlarda) firma bilgileri.</li>
<li><strong>Otomatik toplanan bilgiler:</strong> IP adresi, tarayıcı/cihaz türü, ziyaret edilen sayfalar, oturum bilgileri ve çerezler.</li>
<li><strong>Üçüncü taraflardan gelen bilgiler:</strong> ödeme kuruluşundan gelen ödeme sonucu, kargo firmalarından gelen teslimat durumu.</li>
</ul>
<h3>2. Bilgileri ne için kullanıyoruz?</h3>
<p>Siparişinizi teslim etmek, faturanızı düzenlemek, iade/garanti işlemlerinizi yürütmek, sorularınızı yanıtlamak, Siteyi güvenli ve çalışır tutmak, yasal yükümlülüklerimizi yerine getirmek ve — yalnızca onay vermeniz halinde — kampanya ve yeniliklerden sizi haberdar etmek için.</p>
<h3>3. Ödeme güvenliği</h3>
<p>Kartlı ödemeler, 6493 sayılı Kanun kapsamında lisanslı ödeme kuruluşu <strong>iyzico</strong> altyapısı üzerinden, 3D Secure doğrulamasıyla ve PCI-DSS uyumlu ortamda alınır. Kart numaranız, son kullanma tarihiniz ve güvenlik kodunuz Şirketimiz sunucularında <strong>saklanmaz ve görülmez</strong>. Sitemizle aranızdaki tüm veri trafiği SSL/TLS ile şifrelenir.</p>
<h3>4. Bilgilerinizi kimlerle paylaşıyoruz?</h3>
<p>Bilgilerinizi satmıyor ve kiralamıyoruz. Yalnızca hizmeti sunmak için zorunlu olan iş ortaklarımızla (kargo/nakliye, ödeme, e-fatura, barındırma, SMS/e-posta, kurulum/servis) ve kanunen yetkili kamu kurumlarıyla, gerektiği kadar paylaşıyoruz. Alıcı grupları ve yurt dışına aktarım ayrıntıları KVKK Aydınlatma Metni'nde yer alır.</p>
<h3>5. Hesap güvenliği</h3>
<p>Şifreniz tek yönlü özetlenerek (hash) saklanır; personelimiz dahil kimse şifrenizi göremez. Hesabınızın güvenliği için şifrenizi kimseyle paylaşmamanızı, başka sitelerde kullandığınız şifreyi kullanmamanızı öneririz. Şirketimiz hiçbir zaman telefon veya e-posta ile şifrenizi ya da kart bilgilerinizi istemez.</p>
<h3>6. Ticari elektronik iletiler</h3>
<p>Kampanya ve tanıtım içerikli SMS, e-posta ve aramalar yalnızca 6563 sayılı Kanun ve Ticari İletişim ve Ticari Elektronik İletiler Hakkında Yönetmelik uyarınca onay vermeniz halinde gönderilir ve İleti Yönetim Sistemi'ne (İYS) kaydedilir. Onayınızı dilediğiniz an, gelen iletideki ret bağlantısı, hesap ayarlarınız, <a href="https://www.iys.org.tr" target="_blank" rel="noopener noreferrer">iys.org.tr</a> veya {{sirket.eposta}} üzerinden ücretsiz olarak geri alabilirsiniz. Sipariş, kargo ve fatura bildirimleri gibi işlem iletileri onaydan bağımsız olarak gönderilir.</p>
<h3>7. Çerezler</h3>
<p>Sitenin çalışması için zorunlu çerezler kullanılır; analitik ve pazarlama çerezleri ise yalnızca onayınızla etkinleşir. Ayrıntılar ve tercih yönetimi için <a href="/sayfa/cerez-politikasi">Çerez Politikası</a>'na bakınız.</p>
<h3>8. Üçüncü taraf bağlantılar</h3>
<p>Sitemizde yer alan üretici, ödeme kuruluşu veya sosyal medya bağlantıları kendi gizlilik politikalarına tabidir; bu sitelerin uygulamalarından Şirketimiz sorumlu değildir.</p>
<h3>9. Çocukların gizliliği</h3>
<p>Sitemiz profesyonel ekipman satışına yöneliktir; 18 yaşından küçüklerin üye olması ve sipariş vermesi amaçlanmamıştır.</p>
<h3>10. Değişiklikler ve iletişim</h3>
<p>Bu politika gerektiğinde güncellenir; güncel sürüm her zaman bu sayfada yayımlanır. Sorularınız için: {{sirket.eposta}} · {{sirket.telefon}} · {{sirket.adres}}</p>""",
    },
    # ------------------------------------------------------------------ ÇEREZ
    {
        "slug": "cerez-politikasi",
        "title": "Çerez Politikası",
        "meta_title": "Çerez Politikası | {{site.ad}}",
        "meta_description": "{{site.ad}} çerez politikası: kullanılan çerez türleri, amaçları ve tercihlerinizi nasıl yöneteceğiniz.",
        "content": """<p>Bu politika, {{sirket.unvan}} tarafından işletilen {{site.url}} internet sitesinde kullanılan çerezler ve benzeri teknolojiler hakkında, 6698 sayılı KVKK ve Kişisel Verileri Koruma Kurumu'nun Çerez Uygulamaları Hakkında Rehberi dikkate alınarak hazırlanmıştır.</p>
<h3>1. Çerez nedir?</h3>
<p>Çerezler, bir internet sitesini ziyaret ettiğinizde tarayıcınıza kaydedilen küçük metin dosyalarıdır. Sepetinizin hatırlanması, oturumunuzun açık kalması, sitenin güvenli çalışması ve — onay vermeniz halinde — ziyaret istatistiklerinin ölçülmesi ve size uygun reklamların gösterilmesi için kullanılır. Benzer amaçla yerel depolama (localStorage) ve piksel etiketleri de kullanılabilir.</p>
<h3>2. Kullandığımız çerez türleri</h3>
<table>
<thead><tr><th>Tür</th><th>Amaç</th><th>Hukuki sebep</th></tr></thead>
<tbody>
<tr><td><strong>Zorunlu</strong></td><td>Oturum, sepet, güvenlik (bot / saldırı koruması — ör. Cloudflare), ödeme adımlarının çalışması, çerez tercihinizin hatırlanması</td><td>Sözleşmenin ifası, meşru menfaat — onay gerekmez</td></tr>
<tr><td><strong>İşlevsel</strong></td><td>Dil, son bakılan ürünler, karşılaştırma ve favori listeleri gibi tercihlerin hatırlanması</td><td>Açık rıza</td></tr>
<tr><td><strong>Analitik / performans</strong></td><td>Ziyaret sayısı, sayfa performansı ve kullanım istatistikleri (ör. Google Analytics)</td><td>Açık rıza</td></tr>
<tr><td><strong>Pazarlama / reklam</strong></td><td>İlgi alanınıza uygun reklam gösterimi ve kampanya ölçümü (ör. Meta Pikseli, Google Ads)</td><td>Açık rıza</td></tr>
</tbody>
</table>
<p>Zorunlu çerezler dışındaki çerezler, site ilk açıldığında gösterilen çerez bildiriminden onay vermediğiniz sürece çalıştırılmaz. Üçüncü taraf çerezleri aracılığıyla bazı verilerin yurt dışındaki sunuculara aktarılması söz konusu olabilir; bu aktarım açık rızanıza ve KVKK md.9'daki şartlara tabidir.</p>
<h3>3. Saklama süresi</h3>
<p>Oturum çerezleri tarayıcınızı kapattığınızda silinir. Kalıcı çerezler amaçlarına göre birkaç günden en fazla iki yıla kadar saklanır; tercih çerezi onayınızı hatırlamak için en fazla bir yıl tutulur.</p>
<h3>4. Tercihlerinizi nasıl yönetirsiniz?</h3>
<ul>
<li>Sayfanın altındaki çerez ayarları bağlantısından veya çerez bildirimindeki seçeneklerden onayınızı dilediğiniz zaman değiştirebilir ya da geri alabilirsiniz.</li>
<li>Tarayıcınızın ayarlarından çerezleri silebilir veya engelleyebilirsiniz (Chrome, Safari, Firefox, Edge ayarlar › gizlilik bölümü). Zorunlu çerezlerin engellenmesi halinde sepet, giriş ve ödeme gibi işlevler çalışmayabilir.</li>
<li>Reklam tercihlerinizi Google ve Meta hesap ayarlarınızdan da yönetebilirsiniz.</li>
</ul>
<h3>5. İletişim</h3>
<p>Çerezler ve kişisel verilerinizle ilgili sorularınız ve KVKK md.11 kapsamındaki başvurularınız için: {{sirket.eposta}} · {{sirket.adres}}. Ayrıntılar için <a href="/sayfa/kvkk">KVKK Aydınlatma Metni</a>.</p>""",
    },
    # ------------------------------------------------------------------ ÖN BİLGİLENDİRME
    {
        "slug": "on-bilgilendirme",
        "title": "Ön Bilgilendirme Formu",
        "meta_title": "Ön Bilgilendirme Formu | {{site.ad}}",
        "meta_description": "{{site.ad}} mesafeli satış ön bilgilendirme formu: satıcı bilgileri, ürün ve fiyat, teslimat, cayma hakkı.",
        "content": """<p>Bu form, 6502 sayılı Tüketicinin Korunması Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği'nin 5. maddesi uyarınca, mesafeli satış sözleşmesi kurulmadan önce ALICI'nın bilgilendirilmesi amacıyla düzenlenmiştir. ALICI, siparişini onaylamadan önce bu formu okuyup anladığını elektronik ortamda teyit eder.</p>
<h3>1. Satıcı Bilgileri</h3>
""" + _SATICI_BLOK + """
<h3>2. Alıcı Bilgileri</h3>
""" + _ALICI_BLOK + """
<h3>3. Ürün, Fiyat ve Ödeme Bilgileri</h3>
<p>Sözleşme konusu ürünlerin temel nitelikleri (marka, model, kapasite, elektrik bağlantı türü, ölçüler, renk, adet) ürün sayfasında ve aşağıda yer almaktadır. Tüm fiyatlara KDV dahildir. Ürün sayfasında ilan edilen fiyat ve kampanyalar, güncellenene veya değiştirilene kadar geçerlidir; sipariş anındaki fiyat esas alınır.</p>
""" + _SIPARIS_BLOK + """
<p>Kredi kartıyla taksitli ödemelerde vade farkı ve taksit tutarı ödeme ekranında gösterilir. Havale/EFT ile ödemelerde sipariş, tutarın SATICI hesabına geçmesiyle işleme alınır. Kapıda ödeme seçeneği sunulan siparişlerde kapıda ödeme hizmet bedeli ödeme ekranında ayrıca gösterilir.</p>
<h3>4. Teslimat</h3>
<ul>
<li>Ürünler, ALICI'nın bildirdiği teslimat adresine, anlaşmalı kargo firmaları (ör. MNG, Aras, PTT Kargo) veya büyük hacimli/ağır ürünlerde anlaşmalı ambar/nakliye firmaları aracılığıyla gönderilir.</li>
<li>Stokta bulunan ürünler genellikle 1–3 iş günü içinde kargoya verilir; tahmini süre ürün sayfasında belirtilir. Teslim süresi, her halükârda sipariş tarihinden itibaren yasal azami süre olan <strong>30 günü</strong> aşamaz.</li>
<li>Teslimat masrafları, ödeme ekranında ve yukarıdaki tabloda gösterilmiştir. Paletli/ağır ürünlerin araçtan indirilmesi ve kat/iç mekâna taşınması, aksi açıkça belirtilmedikçe teslimat bedeline dahil değildir.</li>
<li>Kurulum hizmeti, ürün sayfasında belirtilmişse veya ayrıca satın alınmışsa verilir; kurulum şartları <a href="/sayfa/garanti-kosullari">Garanti ve Teknik Servis</a> sayfasında açıklanmıştır.</li>
</ul>
<h3>5. Cayma Hakkı</h3>
<p>ALICI, tüketici sıfatıyla, ürünü teslim aldığı tarihten itibaren <strong>14 (on dört) gün</strong> içinde hiçbir hukuki ve cezai sorumluluk üstlenmeksizin ve hiçbir gerekçe göstermeksizin sözleşmeden cayma hakkına sahiptir. Birden fazla ürünün ayrı ayrı teslim edildiği siparişlerde süre, son ürünün teslim alındığı gün başlar. ALICI, sözleşmenin kurulmasından ürünün teslimine kadar geçen sürede de cayma hakkını kullanabilir.</p>
<ul>
<li><strong>Bildirim:</strong> Cayma bildirimi süresi içinde {{sirket.eposta}} adresine e-posta, {{sirket.kep}} KEP adresi, yazılı başvuru, {{sirket.telefon}} numaralı hat veya "Hesabım › Siparişlerim › İade Talebi" ekranı üzerinden yapılabilir. Aşağıdaki örnek form kullanılabilir; kullanılması zorunlu değildir.</li>
<li><strong>İade gönderimi:</strong> ALICI, cayma bildiriminden itibaren <strong>10 gün</strong> içinde ürünü, faturası, aksesuarları, kullanım kılavuzu ve varsa hediyeleriyle birlikte SATICI'nın bildireceği anlaşmalı taşıyıcı ile gönderir. Anlaşmalı taşıyıcı ile yapılan iade gönderimlerinin masrafı SATICI'ya aittir. Paletli/ağır ürünlerde iade nakliyesi SATICI tarafından organize edilir.</li>
<li><strong>Bedel iadesi:</strong> SATICI, cayma bildiriminin kendisine ulaştığı tarihten itibaren en geç <strong>14 gün</strong> içinde, teslimat masrafları dahil tahsil edilen tüm ödemeleri, ALICI'nın ödemede kullandığı araçla ve ALICI'ya herhangi bir masraf yüklemeden iade eder. SATICI, ürün kendisine ulaşana veya ALICI ürünü geri gönderdiğine dair belgeyi iletene kadar iadeyi bekletebilir. Kredi kartına yapılan iadelerin hesaba yansıma süresi bankaya bağlıdır.</li>
<li><strong>Değer kaybı:</strong> ALICI, ürünü işleyişine, teknik özelliklerine ve kullanım talimatlarına uygun olarak incelemesi nedeniyle oluşan değişikliklerden sorumlu değildir. Ancak ürünün olağan incelemenin ötesinde kullanılması, zemine sabitlenmesi, montajının / elektrik ya da hava tesisatına bağlantısının yapılarak çalıştırılması veya hasarlanması halinde oluşan değer kaybından ALICI sorumludur.</li>
</ul>
<h4>Cayma hakkının kullanılamayacağı haller</h4>
<p>Mesafeli Sözleşmeler Yönetmeliği md.15 uyarınca aşağıdaki sözleşmelerde cayma hakkı kullanılamaz:</p>
""" + _CAYMA_ISTISNALARI + """
<h4>Ticari / mesleki amaçlı alımlar</h4>
<p>Cayma hakkı ve 6502 sayılı Kanun'daki tüketici hakları, ürünü ticari veya mesleki olmayan amaçlarla satın alan <strong>tüketiciler</strong> içindir. Ürünü ticari veya mesleki faaliyeti kapsamında (ör. servis, atölye, işletme adına, şirket faturası ile) satın alan tacir ve esnaf alıcılar bakımından cayma hakkı uygulanmaz; bu alımlara 6102 sayılı Türk Ticaret Kanunu ve 6098 sayılı Türk Borçlar Kanunu hükümleri uygulanır. SATICI, ticari alıcıların iade taleplerini ticari teamüller çerçevesinde ayrıca değerlendirebilir.</p>
""" + _CAYMA_FORMU + """
<h3>6. Ayıplı Ürün, Garanti ve Şikâyet Yolları</h3>
<p>Ayıplı ürünlerde ALICI, 6502 sayılı Kanun md.11 uyarınca sözleşmeden dönme, ayıp oranında bedel indirimi, ücretsiz onarım veya ayıpsız misliyle değişim haklarından birini kullanabilir. Tüketicilere satılan ürünlerde garanti süresi en az 2 yıldır. Ayrıntılar için <a href="/sayfa/garanti-kosullari">Garanti ve Teknik Servis</a> sayfasına bakınız.</p>
<p>Şikâyet ve itirazlar için öncelikle SATICI'ya başvurulabilir. Uyuşmazlık halinde ALICI, Ticaret Bakanlığınca her yıl belirlenen parasal sınırlar dahilinde yerleşim yerindeki veya tüketici işleminin yapıldığı yerdeki Tüketici Hakem Heyetine ya da Tüketici Mahkemesine başvurabilir.</p>
<h3>7. Diğer</h3>
<p>Sipariş onayı ile birlikte bu form ve Mesafeli Satış Sözleşmesi ALICI'nın e-posta adresine gönderilir ve SATICI tarafından en az 3 yıl süreyle saklanır. Kişisel verilerin işlenmesine ilişkin bilgi <a href="/sayfa/kvkk">KVKK Aydınlatma Metni</a>'nde yer alır.</p>""",
    },
    # ------------------------------------------------------------------ MESAFELİ SATIŞ
    {
        "slug": "mesafeli-satis",
        "title": "Mesafeli Satış Sözleşmesi",
        "meta_title": "Mesafeli Satış Sözleşmesi | {{site.ad}}",
        "meta_description": "{{site.ad}} mesafeli satış sözleşmesi: taraflar, konu, teslimat, cayma hakkı, garanti ve uyuşmazlık çözümü.",
        "content": """<h3>Madde 1 – Taraflar</h3>
<h4>1.1 Satıcı</h4>
""" + _SATICI_BLOK + """
<h4>1.2 Alıcı</h4>
""" + _ALICI_BLOK + """
<p>Bu sözleşmede "ALICI", siparişi veren gerçek veya tüzel kişiyi; "Tüketici" ise ticari veya mesleki olmayan amaçlarla hareket eden ALICI'yı ifade eder.</p>
<h3>Madde 2 – Konu</h3>
<p>İşbu sözleşmenin konusu, ALICI'nın SATICI'ya ait {{site.url}} internet sitesi üzerinden elektronik ortamda siparişini verdiği, aşağıda nitelikleri ve satış fiyatı belirtilen ürünlerin satışı ve teslimine ilişkin olarak 6502 sayılı Tüketicinin Korunması Hakkında Kanun ve Mesafeli Sözleşmeler Yönetmeliği hükümleri gereğince tarafların hak ve yükümlülüklerinin belirlenmesidir.</p>
<h3>Madde 3 – Sözleşme Konusu Ürünler ve Bedel</h3>
""" + _SIPARIS_BLOK + """
<p>Ürünlerin temel nitelikleri ürün sayfasında belirtildiği gibidir. Fiyatlara KDV dahildir. Taksitli ödemelerde vade farkı ödeme ekranında gösterilen tutardır.</p>
<h3>Madde 4 – Genel Hükümler</h3>
<p>4.1. ALICI, sözleşme konusu ürünün temel nitelikleri, satış fiyatı, ödeme şekli ve teslimata ilişkin <a href="/sayfa/on-bilgilendirme">Ön Bilgilendirme Formu</a>'nu okuyup bilgi sahibi olduğunu ve elektronik ortamda gerekli teyidi verdiğini kabul eder. Ön Bilgilendirme Formu bu sözleşmenin ayrılmaz parçasıdır.</p>
<p>4.2. Sözleşme, ALICI'nın siparişi onaylaması ve ödemenin (havale/EFT'de tutarın SATICI hesabına geçmesiyle, kapıda ödemede siparişin onaylanmasıyla) gerçekleşmesiyle kurulur.</p>
<p>4.3. Ürün bedelinin ödenmesinden sonra ALICI'nın kullandığı kartın bankası tarafından bedelin herhangi bir sebeple SATICI'ya ödenmemesi halinde SATICI'nın teslim yükümlülüğü doğmaz; teslim edilmiş ürün, masrafları ALICI'ya ait olmak üzere 3 gün içinde SATICI'ya iade edilir.</p>
<p>4.4. Stok tükenmesi, tedarikçi kaynaklı gecikme veya mücbir sebep gibi nedenlerle sipariş konusu ürünün teslimi imkânsızlaşırsa SATICI, durumu öğrendiği tarihten itibaren 3 gün içinde ALICI'yı bilgilendirir ve tahsil edilen tüm ödemeleri en geç 14 gün içinde iade eder. ALICI'nın açık onayı olmadan eş değer başka ürün gönderilmez.</p>
<p>4.5. Ödemenin kart sahibi olmayan biri tarafından yapıldığı veya kartın haksız kullanıldığının tespiti halinde SATICI, siparişi askıya alma ve kart sahibine ait kimlik/iletişim teyidi isteme hakkını saklı tutar.</p>
<h3>Madde 5 – Teslimat</h3>
<p>5.1. Ürün, ALICI'nın bildirdiği adrese ve kişiye, anlaşmalı kargo veya ambar/nakliye firması aracılığıyla, ambalajı ile birlikte sağlam olarak teslim edilir. Teslim süresi sipariş tarihinden itibaren <strong>30 günü</strong> aşamaz.</p>
<p>5.2. ALICI'nın adreste bulunmaması, hatalı adres bildirmesi veya teslim almaması halinde doğabilecek ek nakliye ve depolama masrafları ALICI'ya aittir; tüketici siparişlerinde bu masraflar ancak ALICI'nın kusuru halinde talep edilir.</p>
<p>5.3. Paletli ve ağır ürünler, aksi kararlaştırılmadıkça aracın ulaşabildiği noktada zemin seviyesine teslim edilir; araçtan indirme ve iç mekâna taşıma için gerekli imkânı (forklift, transpalet, yeterli personel) ALICI sağlar.</p>
<p>5.4. ALICI, teslimat sırasında ambalajı kontrol etmeli; ezik, yırtık, ıslanma gibi hasar belirtisi varsa taşıyıcı görevlisine <strong>hasar tespit tutanağı</strong> düzenletmeli ve mümkünse fotoğraf çekmelidir. Tutanak düzenletilmesi tüketicinin ayıplı mala ilişkin yasal haklarını ortadan kaldırmaz; ancak sürecin hızlı yürütülmesini sağlar.</p>
<p>5.5. Ürün, ALICI veya gösterdiği kişiye teslim edilene kadar oluşan kayıp ve hasarlardan SATICI sorumludur. ALICI'nın, SATICI'nın belirlediği taşıyıcı dışında bir taşıyıcı ile gönderim talep etmesi halinde ürünün bu taşıyıcıya tesliminden itibaren risk ALICI'ya geçer.</p>
<h3>Madde 6 – Cayma Hakkı</h3>
<p>6.1. Tüketici sıfatına sahip ALICI, ürünün kendisine veya gösterdiği üçüncü kişiye teslim tarihinden itibaren <strong>14 gün</strong> içinde herhangi bir gerekçe göstermeksizin ve cezai şart ödemeksizin sözleşmeden cayma hakkına sahiptir.</p>
<p>6.2. Cayma bildirimi; {{sirket.eposta}} adresine e-posta, {{sirket.kep}} KEP adresi, yazılı bildirim, {{sirket.telefon}} numaralı hat veya Site'deki iade talebi ekranı aracılığıyla yapılır. ALICI, bildirimden itibaren 10 gün içinde ürünü SATICI'nın anlaşmalı taşıyıcısı ile, masrafı SATICI'ya ait olmak üzere iade eder.</p>
<p>6.3. SATICI, cayma bildiriminin kendisine ulaşmasından itibaren en geç 14 gün içinde teslimat masrafları dahil tüm ödemeleri ALICI'nın kullandığı ödeme aracıyla iade eder. Kapıda ödeme ve havale/EFT ile yapılan ödemeler ALICI'nın bildireceği kendi adına kayıtlı IBAN'a iade edilir.</p>
<p>6.4. ALICI, ürünün olağan incelemenin ötesinde kullanılması, kurulumunun yapılarak çalıştırılması, zemine/duvara sabitlenmesi, elektrik veya hava tesisatına bağlanması ya da hasarlanması nedeniyle oluşan değer kaybından sorumludur. Fatura, aksesuar, kılavuz ve hediye ürünlerin eksik iadesi halinde eksiklik bedeli iadeden mahsup edilebilir.</p>
<p>6.5. Mesafeli Sözleşmeler Yönetmeliği md.15'te sayılan aşağıdaki hallerde cayma hakkı kullanılamaz:</p>
""" + _CAYMA_ISTISNALARI + """
<p>6.6. Ürünü ticari veya mesleki faaliyeti kapsamında satın alan tacir ve esnaf ALICI'lar tüketici sayılmaz; bu alımlarda cayma hakkı uygulanmaz ve 6102 sayılı TTK ile 6098 sayılı TBK hükümleri geçerlidir. Ticari ALICI, açık ayıpları teslimden itibaren 2 gün, ilk bakışta anlaşılamayan ayıpları ise teslimden itibaren 8 gün içinde inceleyip SATICI'ya bildirmekle yükümlüdür (TTK md.23).</p>
<h3>Madde 7 – Ayıplı Mal ve Garanti</h3>
<p>7.1. Tüketici ALICI, ayıplı ürün teslimi halinde 6502 sayılı Kanun md.11 uyarınca; bedel iadesine hazır olduğunu bildirerek sözleşmeden dönme, ayıp oranında bedel indirimi, aşırı masraf gerektirmediği takdirde ücretsiz onarım veya imkân varsa ayıpsız misli ile değişim haklarından birini kullanabilir. Ayıplı maldan sorumluluk, ayıp daha sonra ortaya çıksa bile teslimden itibaren 2 yıllık zamanaşımına tabidir (ağır kusur ve hile hali saklıdır).</p>
<p>7.2. Tüketicilere satılan ürünler için garanti süresi teslimden itibaren en az 2 yıldır; onarım süresi azami 20 iş günüdür. Garanti kapsamı, kullanıcı hatası ve kurulum şartlarına ilişkin hükümler <a href="/sayfa/garanti-kosullari">Garanti ve Teknik Servis</a> sayfasında açıklanmıştır.</p>
<p>7.3. Kurulum gerektiren ürünlerde (ör. lift, lastik sökme-balans makinesi, büyük kompresör), üreticinin kurulum kılavuzunda belirtilen zemin, elektrik, hava ve ortam şartlarının sağlanması ALICI'nın sorumluluğundadır. Kurulumun yetkisiz kişilerce veya talimatlara aykırı yapılmasından doğan arıza ve zararlar garanti kapsamı dışındadır.</p>
<h3>Madde 8 – Kişisel Veriler ve Elektronik İletiler</h3>
<p>ALICI'ya ait kişisel veriler, <a href="/sayfa/kvkk">KVKK Aydınlatma Metni</a>'nde açıklanan amaç ve hukuki sebeplerle işlenir. Ticari elektronik iletiler yalnızca ALICI'nın onayı ile gönderilir; ALICI onayını her zaman ücretsiz olarak geri alabilir.</p>
<h3>Madde 9 – Mücbir Sebep</h3>
<p>Doğal afet, salgın, savaş, grev, yangın, resmî makam kararları, altyapı ve iletişim arızaları gibi tarafların kontrolü dışında gelişen haller mücbir sebep sayılır. Mücbir sebep süresince tarafların yükümlülükleri askıya alınır; durum 30 günden uzun sürerse taraflar sözleşmeyi feshedebilir ve tahsil edilen bedeller iade edilir.</p>
<h3>Madde 10 – Uyuşmazlıkların Çözümü</h3>
<p>Tüketici uyuşmazlıklarında, Ticaret Bakanlığınca her yıl ilan edilen parasal sınırlar dahilinde ALICI'nın yerleşim yerindeki veya tüketici işleminin yapıldığı yerdeki Tüketici Hakem Heyetleri, bu sınırların üzerindeki uyuşmazlıklarda Tüketici Mahkemeleri yetkilidir; dava şartı arabuluculuğa ilişkin hükümler saklıdır. Ticari alımlarda İstanbul (Merkez) Mahkemeleri ve İcra Daireleri yetkilidir.</p>
<h3>Madde 11 – Yürürlük</h3>
<p>ALICI, siparişini onayladığı anda işbu sözleşmenin tüm koşullarını kabul etmiş sayılır. Sözleşme, sipariş tarihinde ({{siparis.tarih}}) elektronik ortamda kurulmuş olup bir örneği ALICI'nın e-posta adresine gönderilir ve SATICI tarafından en az 3 yıl saklanır.</p>""",
    },
    # ------------------------------------------------------------------ İADE
    {
        "slug": "iade-kosullari",
        "title": "İade ve Değişim Koşulları",
        "meta_title": "İade ve Değişim Koşulları | {{site.ad}}",
        "meta_description": "{{site.ad}} iade ve değişim: 14 gün cayma hakkı, iade adımları, ücretsiz iade kargosu, para iadesi süreleri ve istisnalar.",
        "content": """<p class="lead">Aldığınız ürünü teslim aldığınız tarihten itibaren <strong>14 gün</strong> içinde, herhangi bir gerekçe göstermeden iade edebilirsiniz (tüketici alımları). Aşağıda adım adım süreci ve dikkat etmeniz gerekenleri bulabilirsiniz.</p>
<h3>Cayma Hakkı Süresi</h3>
<p>Cayma süresi ürünü teslim aldığınız gün başlar ve 14 gündür. Birden fazla parça halinde gelen siparişlerde süre son parçanın teslimiyle başlar. Ürün henüz size ulaşmadıysa da siparişinizden vazgeçebilirsiniz.</p>
<h3>İade Süreci (Adım Adım)</h3>
<ol>
<li><strong>Talep oluşturun:</strong> "Hesabım › Siparişlerim" ekranından veya üyeliksiz siparişlerde <a href="/iade-islemleri">İade Talebi</a> sayfasından talebinizi oluşturun ya da {{sirket.eposta}} adresine / {{sirket.telefon}} numarasına sipariş numaranızla bildirin.</li>
<li><strong>İade kodunu alın:</strong> Size anlaşmalı kargo firması için bir iade kodu iletilir. Paletli/ağır ürünlerde iade nakliyesi tarafımızca organize edilir; sizinle alım günü planlanır.</li>
<li><strong>Paketleyin:</strong> Ürünü mümkünse orijinal kutusu, tüm aksesuarları, kullanım kılavuzu, garanti belgesi ve faturasıyla birlikte, taşımada zarar görmeyecek şekilde paketleyin.</li>
<li><strong>Gönderin:</strong> Bildiriminizden itibaren 10 gün içinde paketi iade koduyla anlaşmalı kargoya teslim edin. <strong>Anlaşmalı kargo ile iade ücretsizdir.</strong></li>
<li><strong>Bedel iadesi:</strong> Cayma bildiriminizin bize ulaşmasından itibaren en geç 14 gün içinde ödediğiniz tutar (ilk teslimat ücreti dahil) iade edilir.</li>
</ol>
<h3>Para İadesi Nasıl Yapılır?</h3>
<ul>
<li><strong>Kredi / banka kartı:</strong> Ödeme yaptığınız karta iade edilir. Bankanızın hesabınıza yansıtma süresi genellikle 2–10 iş günüdür; taksitli alımlarda iade, bankanızca taksitler halinde yansıtılabilir.</li>
<li><strong>Havale / EFT ve kapıda ödeme:</strong> Size ait IBAN numarasına iade edilir. Lütfen talebinizde adınıza kayıtlı IBAN bilgisini paylaşın.</li>
</ul>
<h3>İade Koşulları</h3>
<ul>
<li>Ürünü işleyişine ve teknik özelliklerine uygun şekilde inceleyebilirsiniz. Olağan incelemenin ötesinde kullanım, zemine sabitleme, montaj, elektrik/hava tesisatına bağlanıp çalıştırma veya hasar nedeniyle oluşan değer kaybı iade bedelinden düşülebilir.</li>
<li>Eksik aksesuar, kılavuz veya hediye ürün iade edilmezse eksiklik bedeli mahsup edilebilir.</li>
<li>Kurumsal (ticari amaçlı, şirket faturalı) alımlarda yasal cayma hakkı bulunmamakla birlikte, kullanılmamış ve yeniden satılabilir durumdaki ürünler için iade talepleri iyi niyetle değerlendirilir.</li>
</ul>
<h3>İade Edilemeyen Ürünler</h3>
<p>Mevzuat gereği aşağıdaki ürünlerde cayma hakkı kullanılamaz:</p>
""" + _CAYMA_ISTISNALARI + """
<h3>Değişim</h3>
<p>Farklı model, kapasite veya ölçüdeki bir ürünle değişim yapmak isterseniz iade talebinizde belirtmeniz yeterlidir. Ürün tarafımıza ulaşıp kontrol edildikten sonra yeni ürün gönderilir; fiyat farkı varsa ödeme veya iade şeklinde tarafınıza bildirilir.</p>
<h3>Hasarlı, Eksik veya Hatalı Ürün</h3>
<p>Teslimatta paket hasarlıysa kargo görevlisine <strong>hasar tespit tutanağı</strong> düzenletin ve fotoğraf çekin. Ürünün hasarlı, eksik, hatalı veya ayıplı çıkması halinde bize en kısa sürede ulaşın; inceleme sonrasında ürün tarafımızca ücretsiz olarak değiştirilir, onarılır veya bedeli iade edilir. Ayıplı ürünlerde yasal haklarınız 14 günlük cayma süresiyle sınırlı değildir (bkz. <a href="/sayfa/garanti-kosullari">Garanti ve Teknik Servis</a>).</p>
<h3>İade Adresi ve İletişim</h3>
<p>{{sirket.unvan}}<br>{{sirket.adres}}<br>Telefon: {{sirket.telefon}} · E-posta: {{sirket.eposta}}</p>
<p>Lütfen iade kodu almadan veya karşı ödemeli (alıcı ödemeli) gönderim yapmayın; anlaşmalı kargo dışında yapılan gönderimlerde ürün tarafımıza geç ulaşabilir.</p>
""" + _CAYMA_FORMU,
    },
    # ------------------------------------------------------------------ KARGO
    {
        "slug": "kargo-ve-teslimat",
        "title": "Teslimat ve Kargo Bilgileri",
        "meta_title": "Teslimat ve Kargo Bilgileri | {{site.ad}}",
        "meta_description": "{{site.ad}} kargo ve teslimat: gönderim süreleri, kargo ücretleri, paletli/ağır ürün teslimatı ve hasarlı teslimat prosedürü.",
        "content": """<p class="lead">Siparişlerinizi Türkiye'nin her yerine, ürünün ölçü ve ağırlığına uygun taşıma yöntemiyle gönderiyoruz.</p>
<h3>Gönderim Süresi</h3>
<ul>
<li>Stokta bulunan ürünler, ödeme onayından sonra genellikle <strong>1–3 iş günü</strong> içinde kargoya verilir. Hafta sonu ve resmî tatillerde verilen siparişler takip eden ilk iş günü işleme alınır.</li>
<li>Tedarikli veya siparişe özel ürünlerde tahmini süre ürün sayfasında belirtilir.</li>
<li>Her durumda teslimat, sipariş tarihinden itibaren yasal azami süre olan <strong>30 gün</strong> içinde yapılır; gecikme öngörülürse sizi bilgilendirir, dilerseniz siparişinizi ücretsiz iptal ederiz.</li>
</ul>
<h3>Taşıyıcı Firmalar</h3>
<ul>
<li><strong>Standart koliler:</strong> MNG Kargo, Aras Kargo veya PTT Kargo ile adrese teslim.</li>
<li><strong>Ağır ve büyük hacimli ürünler</strong> (lift, büyük kompresör, lastik makinesi, motor vinci vb.): paletli olarak anlaşmalı ambar / nakliye firmalarıyla gönderilir. Bazı bölgelerde ürün, alıcıya en yakın ambar şubesinden teslim alınabilir; bu durumda önceden bilgilendirilirsiniz.</li>
</ul>
<p>Kargonuz yola çıktığında takip numarası SMS / e-posta ile iletilir; durumunu <a href="/siparis-takip">Sipariş Takibi</a> sayfasından izleyebilirsiniz.</p>
<h3>Kargo Ücreti</h3>
<p>Kargo ücreti; ürünün desisi/ağırlığı ve teslimat yöntemine göre hesaplanır ve ödeme adımında siparişi onaylamadan önce açıkça gösterilir. Kampanya dönemlerinde ve belirli tutarın üzerindeki siparişlerde ücretsiz kargo uygulanabilir. Paletli ürünlerde nakliye bedeli ürün sayfasında ya da sipariş öncesinde ayrıca bildirilir.</p>
<h3>Paletli / Ağır Ürün Teslimatı</h3>
<ul>
<li>Teslimat, aksi kararlaştırılmadıkça nakliye aracının ulaşabildiği noktada <strong>zemin seviyesine</strong> yapılır. Araçtan indirme, kat çıkarma ve iç mekâna taşıma hizmete dahil değildir.</li>
<li>İndirme için forklift, transpalet veya yeterli sayıda kişi bulundurmanız gerekir. Lütfen siparişinizde teslimat noktasına ağır vasıta erişimi olup olmadığını, varsa kısıtlamaları belirtin.</li>
<li>Nakliye firması teslimat öncesinde sizi arayarak gün ve saat planlaması yapar; telefonunuzun ulaşılabilir olduğundan emin olun.</li>
</ul>
<h3>Teslim Alırken: Hasar Tespit Prosedürü</h3>
<ol>
<li>Paketi teslim almadan önce görevlinin yanında dış ambalajı kontrol edin (ezik, yırtık, ıslanma, palet kırığı, bant açılması).</li>
<li>Hasar şüphesi varsa paketi görevliyle birlikte açın; hasar varsa <strong>hasar tespit tutanağı</strong> düzenletin, tutanağın bir nüshasını alın ve fotoğraf/video çekin. Ciddi hasarda ürünü teslim almayıp iade edebilirsiniz.</li>
<li>Tutanakla veya tutanaksız fark ettiğiniz her türlü hasar, eksik ya da yanlış ürünü fotoğraflarla birlikte mümkünse <strong>24 saat içinde</strong> {{sirket.eposta}} veya {{sirket.telefon}} üzerinden bize bildirin. Hızlı bildirim, taşıyıcıyla süreci çabuk sonuçlandırmamızı sağlar; tüketici olarak ayıplı mala ilişkin yasal haklarınız saklıdır.</li>
</ol>
<h3>Teslim Edilemeyen Gönderiler</h3>
<p>Adreste bulunamamanız halinde kargo firması bildirim bırakır ve gönderiyi şubede yasal bekleme süresince tutar. Süresi içinde teslim alınmayan gönderiler tarafımıza geri döner; sizinle iletişime geçilerek yeniden gönderim veya iade planlanır.</p>
<h3>Kurulum</h3>
<p>Kurulum hizmeti sunulan ürünlerde, ürün teslim edildikten sonra sizinle randevu planlanır. Kurulum öncesi hazırlık (zemin, elektrik, hava hattı) ve detaylar için <a href="/sayfa/garanti-kosullari">Garanti ve Teknik Servis</a> sayfasına bakınız.</p>""",
    },
    # ------------------------------------------------------------------ GARANTİ
    {
        "slug": "garanti-kosullari",
        "title": "Garanti ve Teknik Servis",
        "meta_title": "Garanti ve Teknik Servis | {{site.ad}}",
        "meta_description": "{{site.ad}} garanti koşulları: 2 yıl yasal garanti, ayıplı mal hakları, kurulum şartları ve teknik servis süreci.",
        "content": """<p class="lead">{{site.ad}} üzerinden satılan tüm ürünler faturalı ve garantili olarak gönderilir. Garanti belgesi ürün kutusunda veya elektronik olarak (e-garanti) tarafınıza iletilir.</p>
<h3>1. Garanti Süresi</h3>
<ul>
<li><strong>Tüketiciler için:</strong> 6502 sayılı Kanun ve Garanti Belgesi Yönetmeliği uyarınca garanti süresi, ürünün teslim tarihinden itibaren <strong>en az 2 yıldır</strong>. Üreticinin daha uzun garanti sunduğu ürünlerde bu süre ürün sayfasında belirtilir.</li>
<li><strong>Ticari alıcılar için:</strong> Garanti süresi ve kapsamı, üretici / ithalatçının garanti şartlarına ve ürün sayfasındaki açıklamaya göre belirlenir.</li>
</ul>
<h3>2. Tüketicinin Seçimlik Hakları</h3>
<p>Ayıplı ürünlerde tüketici; sözleşmeden dönme, ayıp oranında bedel indirimi, ücretsiz onarım veya ayıpsız misliyle değişim haklarından birini seçebilir (6502 s. Kanun md.11). Ücretsiz onarım hakkının kullanılması halinde:</p>
<ul>
<li>Azami tamir süresi <strong>20 iş günüdür</strong>; bu süre arızanın servise, servis yoksa satıcı, üretici veya ithalatçıya bildirildiği tarihte başlar.</li>
<li>Garanti süresi içinde ürünün aynı arızayı ikiden fazla tekrarlaması veya farklı arızaların dörtten fazla ortaya çıkması (ilk teslimden itibaren bir yıl içinde), azami tamir süresinin aşılması ya da servis raporuyla tamirin mümkün olmadığının belirlenmesi hallerinde; tüketici ücretsiz değişim, bedel iadesi veya bedel indirimi talep edebilir.</li>
<li>Onarımda geçen süre garanti süresine eklenir.</li>
</ul>
<h3>3. Garanti Kapsamı Dışındaki Durumlar</h3>
<ul>
<li>Kullanım kılavuzuna aykırı kullanım, kapasitenin üzerinde yükleme (ör. lift / krikonun nominal taşıma kapasitesinin aşılması), darbe, düşme ve taşıma hasarları (ürün size teslim edildikten sonra),</li>
<li>Yanlış voltaj / faz bağlantısı, topraklama eksikliği, uygun olmayan sigorta ve kablo kesiti, şebeke dalgalanmaları,</li>
<li>Yetkisiz kişilerce yapılan kurulum, tamir veya değişiklikler; orijinal olmayan yedek parça veya uygunsuz yağ/sarf malzemesi kullanımı,</li>
<li>Periyodik bakımın (yağ değişimi, filtre, kayış, conta kontrolü, kompresörlerde tank suyu tahliyesi vb.) yapılmaması,</li>
<li>Kullanıma bağlı doğal aşınan parçalar (kayış, conta, lastik pabuç, ped, filtre, kömür, sigorta vb.), ancak bu parçalardaki üretim hataları garanti kapsamındadır.</li>
</ul>
<h3>4. Kurulum Gerektiren Ürünler</h3>
<p>İki/dört direkli ve makaslı liftler, lastik sökme-takma ve balans makineleri, büyük hacimli kompresörler gibi ürünlerin güvenli çalışması doğru kurulumla mümkündür:</p>
<ul>
<li><strong>Zemin:</strong> Liftlerde üretici kılavuzunda belirtilen beton sınıfı ve kalınlığa sahip, düz ve çatlaksız zemin gerekir; dübel/ankraj bağlantısı kılavuza uygun yapılmalıdır.</li>
<li><strong>Elektrik:</strong> Ürünün etiketinde belirtilen gerilim (220 V monofaze / 380 V trifaze), uygun kesitte kablo, sigorta ve kaçak akım koruması ile topraklama sağlanmalıdır. Elektrik bağlantısı yetkili elektrikçi tarafından yapılmalıdır.</li>
<li><strong>Hava hattı:</strong> Pnömatik ekipmanlarda kılavuzda belirtilen çalışma basıncı ve debiye uygun, şartlandırıcılı (filtre-regülatör-yağlayıcı) hava hattı kullanılmalıdır.</li>
<li><strong>Kurulum hizmeti:</strong> Ürün sayfasında kurulumun dahil olduğu belirtilmişse veya ayrıca satın alınmışsa, ürün teslim edildikten sonra yetkili teknisyenle randevu planlanır. Kurulum ücreti, yol ve konaklama gibi giderler aksi belirtilmedikçe ayrıca bildirilir.</li>
<li>Kurulum ve ilk çalıştırma sonrası düzenlenen <strong>kurulum / devreye alma formunun</strong> saklanması garanti işlemlerinde kolaylık sağlar.</li>
</ul>
<h3>5. Teknik Servis Süreci</h3>
<ol>
<li>Arızayı {{sirket.telefon}} veya {{sirket.eposta}} üzerinden; sipariş numarası, ürün seri numarası, arızanın tarifi ve mümkünse fotoğraf/video ile bildirin.</li>
<li>Teknik ekibimiz uzaktan ön tespit yapar; gerekirse yetkili servis yönlendirmesi, yerinde servis veya ürünün servise gönderilmesi planlanır.</li>
<li>Garanti kapsamındaki onarım, parça ve işçilik ile garanti kapsamındaki servis taşıma giderleri tüketiciden talep edilmez. Garanti dışı onarımlarda işleme başlanmadan önce fiyat teklifi sunulur.</li>
<li>Garanti süresi dolan ürünler için yedek parça ve ücretli servis desteği sağlanır; ürünlerin yedek parça bulundurma süresi Satış Sonrası Hizmetler Yönetmeliği'nde belirlenen kullanım ömrü kadardır.</li>
</ol>
<h3>6. Güvenlik Uyarısı</h3>
<p>Kaldırma ekipmanlarının (lift, kriko, vinç) periyodik kontrollerinin İş Sağlığı ve Güvenliği mevzuatı kapsamında yetkili kişilerce yaptırılması işletmenin sorumluluğundadır. Ekipmanı kılavuzdaki güvenlik talimatlarına uygun şekilde kullanınız.</p>
<h3>7. Başvuru</h3>
<p>{{sirket.unvan}} — {{sirket.adres}}<br>Telefon: {{sirket.telefon}} · E-posta: {{sirket.eposta}}</p>
<p>Uyuşmazlık halinde Tüketici Hakem Heyetine veya Tüketici Mahkemesine başvurabilirsiniz.</p>""",
    },
    # ------------------------------------------------------------------ ÜYELİK
    {
        "slug": "uyelik-sozlesmesi",
        "title": "Üyelik Sözleşmesi",
        "meta_title": "Üyelik Sözleşmesi | {{site.ad}}",
        "meta_description": "{{site.ad}} üyelik sözleşmesi: üyelik koşulları, tarafların hak ve yükümlülükleri.",
        "content": """<h3>1. Taraflar</h3>
<p>İşbu Üyelik Sözleşmesi ("Sözleşme"), {{sirket.adres}} adresinde mukim <strong>{{sirket.unvan}}</strong> ("{{site.ad}}") ile {{site.url}} internet sitesine ("Site") üye olan gerçek veya tüzel kişi ("Üye") arasında, Üye'nin üyelik formunu doldurup sözleşmeyi elektronik ortamda onaylamasıyla kurulmuştur.</p>
<h3>2. Konu</h3>
<p>Sözleşmenin konusu; Site'de sunulan hizmetlerden üyelik ile yararlanma koşullarının ve tarafların hak ve yükümlülüklerinin belirlenmesidir. Site üzerinden yapılan her satın alma işlemi ayrıca Ön Bilgilendirme Formu ve Mesafeli Satış Sözleşmesi'ne tabidir.</p>
<h3>3. Üyelik Koşulları</h3>
<ul>
<li>Üye olabilmek için 18 yaşını doldurmuş ve fiil ehliyetine sahip olmak ya da bir tüzel kişiyi temsile yetkili bulunmak gerekir.</li>
<li>Üye, üyelik ve sipariş sırasında verdiği bilgilerin doğru, eksiksiz ve güncel olduğunu kabul eder; değişiklikleri "Hesabım" bölümünden günceller.</li>
<li>Kurumsal üyeler, firma ünvanı ve vergi bilgilerinin doğruluğundan sorumludur.</li>
</ul>
<h3>4. Üye'nin Yükümlülükleri</h3>
<ul>
<li>Hesap bilgilerini ve şifresini gizli tutmak; hesabının yetkisiz kullanıldığını fark ederse derhal {{sirket.eposta}} adresine bildirmek. Bildirim yapılana kadar hesap üzerinden gerçekleştirilen işlemlerden Üye sorumludur.</li>
<li>Site'yi hukuka, ahlaka ve işbu sözleşmeye uygun kullanmak; Site'nin işleyişini bozacak, güvenliğini tehdit edecek (bot, kazıma, saldırı vb.) faaliyetlerde bulunmamak.</li>
<li>Ürün yorumlarında ve değerlendirmelerinde gerçeğe aykırı, yanıltıcı, hakaret içeren, üçüncü kişilerin haklarını ihlal eden veya reklam niteliğinde içerik paylaşmamak.</li>
<li>Site'deki içerikleri ({{site.ad}}'ın izni olmaksızın) kopyalamamak, çoğaltmamak, ticari amaçla kullanmamak.</li>
</ul>
<h3>5. {{site.ad}}'ın Hak ve Yükümlülükleri</h3>
<ul>
<li>{{site.ad}}, Site'nin içeriğini, ürün ve fiyatlarını, kampanya koşullarını ve hizmetlerini önceden bildirimde bulunmaksızın değiştirme hakkına sahiptir; bu değişiklikler onaylanmış siparişleri etkilemez.</li>
<li>Sözleşmeye veya mevzuata aykırı davranan, sahte bilgi kullanan ya da kötüye kullanım tespit edilen üyeliği askıya alabilir veya sona erdirebilir.</li>
<li>Üye'nin kişisel verilerini <a href="/sayfa/kvkk">KVKK Aydınlatma Metni</a> ve <a href="/sayfa/gizlilik">Gizlilik Politikası</a>'na uygun olarak işler ve korur.</li>
<li>Bakım, güncelleme veya teknik arızalar nedeniyle Site'ye erişimin geçici olarak kesilmesinden doğabilecek dolaylı zararlardan, kast veya ağır ihmali bulunmadıkça sorumlu değildir.</li>
</ul>
<h3>6. Elektronik İletiler</h3>
<p>Sipariş, teslimat, fatura ve hesap güvenliğine ilişkin bilgilendirmeler işlem iletisi olarak gönderilir. Kampanya ve tanıtım iletileri yalnızca Üye'nin ayrıca vereceği onay ile (bkz. <a href="/sayfa/acik-riza-metni">Açık Rıza Metni</a>) gönderilir ve İYS'ye kaydedilir; onay her zaman geri alınabilir.</p>
<h3>7. Fikri Mülkiyet</h3>
<p>Site'nin tasarımı, yazılımı, logo ve marka unsurları, metin ve görselleri {{sirket.unvan}}'e veya lisans verenlere aittir. Üretici marka ve görselleri ilgili hak sahiplerinin mülkiyetindedir.</p>
<h3>8. Süre ve Fesih</h3>
<p>Sözleşme süresizdir. Üye, dilediği zaman "Hesabım" bölümünden veya {{sirket.eposta}} adresine bildirerek üyeliğini sonlandırabilir. Üyeliğin sona ermesi, tamamlanmamış siparişlerden ve yasal saklama yükümlülüklerinden doğan hak ve borçları etkilemez.</p>
<h3>9. Delil Sözleşmesi ve Uyuşmazlıklar</h3>
<p>Taraflar, işbu sözleşmeden doğabilecek uyuşmazlıklarda {{site.ad}}'ın elektronik kayıtlarının ve sistem loglarının HMK md.193 uyarınca delil teşkil edeceğini kabul eder; tüketicinin aksini ispat hakkı saklıdır. Tüketici uyuşmazlıklarında Tüketici Hakem Heyetleri ve Tüketici Mahkemeleri yetkilidir.</p>
<h3>10. Değişiklikler</h3>
<p>{{site.ad}}, sözleşmede değişiklik yapabilir; değişiklikler Site'de yayımlandığı tarihte yürürlüğe girer ve önemli değişiklikler Üye'ye ayrıca bildirilir. Üye'nin değişikliği kabul etmemesi halinde üyeliğini sonlandırma hakkı saklıdır.</p>""",
    },
    # ------------------------------------------------------------------ KULLANIM KOŞULLARI
    {
        "slug": "kullanim-kosullari",
        "title": "Kullanım Koşulları",
        "meta_title": "Kullanım Koşulları | {{site.ad}}",
        "meta_description": "{{site.ad}} internet sitesi kullanım koşulları.",
        "content": """<p>{{site.url}} internet sitesi ("Site"), {{sirket.unvan}} ("Şirket") tarafından işletilmektedir. Site'yi ziyaret eden veya kullanan herkes aşağıdaki koşulları kabul etmiş sayılır.</p>
<h3>1. Hizmet Sağlayıcı Bilgileri</h3>
<p>6563 sayılı Elektronik Ticaretin Düzenlenmesi Hakkında Kanun md.3 kapsamında:</p>
""" + _SATICI_BLOK + """
<h3>2. Ürün Bilgileri ve Fiyatlar</h3>
<ul>
<li>Ürün açıklamaları, teknik özellikler ve görseller üretici bilgileri esas alınarak özenle hazırlanır; ancak görseller temsilî olabilir, renk ve aksesuarlarda farklılık bulunabilir. Satın almadan önce kapasite, elektrik ve kurulum şartlarını kontrol etmenizi, emin olmadığınızda bize danışmanızı öneririz.</li>
<li>Fiyatlara KDV dahildir. Açık bir yazım veya sistem hatası nedeniyle ürünün gerçek değerinin çok altında ilan edilen fiyatlarla verilen siparişlerde Şirket, ALICI'yı bilgilendirerek siparişi iptal etme ve ödemeyi derhal iade etme hakkını saklı tutar.</li>
<li>Kampanya ve kupon koşulları ilgili kampanya sayfasında belirtilir; aksi belirtilmedikçe kampanyalar birleştirilemez.</li>
</ul>
<h3>3. Siparişler</h3>
<p>Site üzerinden verilen siparişler <a href="/sayfa/on-bilgilendirme">Ön Bilgilendirme Formu</a> ve <a href="/sayfa/mesafeli-satis">Mesafeli Satış Sözleşmesi</a>'ne tabidir. Stok ve fiyat teyidi yapılamayan, dolandırıcılık şüphesi taşıyan veya ticari olarak makul olmayan miktardaki (bayi alımı vb.) siparişlerde Şirket, bilgilendirme yaparak siparişi reddedebilir; tahsil edilen bedel iade edilir.</p>
<h3>4. Kullanım Kuralları</h3>
<ul>
<li>Site'nin yazılımına, sunucularına ve güvenlik önlemlerine müdahale edilemez; otomatik araçlarla (bot, kazıyıcı vb.) içerik toplanamaz.</li>
<li>Site içeriği (metin, görsel, tasarım, yazılım, marka) Şirket'in yazılı izni olmadan kopyalanamaz, çoğaltılamaz, ticari amaçla kullanılamaz.</li>
<li>Kullanıcılar tarafından gönderilen yorum ve içeriklerden gönderen sorumludur; Şirket hukuka aykırı içerikleri yayından kaldırabilir.</li>
</ul>
<h3>5. Sorumluluğun Sınırlandırılması</h3>
<p>Şirket, Site'nin kesintisiz ve hatasız çalışması için makul özeni gösterir; kast veya ağır ihmali bulunmadıkça teknik arızalar, bakım çalışmaları, internet altyapı sorunları ve üçüncü kişilerin saldırıları nedeniyle oluşabilecek dolaylı zararlardan sorumlu değildir. Bu hüküm, tüketicinin kanundan doğan haklarını sınırlamaz.</p>
<h3>6. Bağlantılı Siteler</h3>
<p>Site'de yer alan üçüncü taraf bağlantılarının içerik ve gizlilik uygulamalarından ilgili site sahipleri sorumludur.</p>
<h3>7. Kişisel Veriler ve Çerezler</h3>
<p>Kişisel verileriniz <a href="/sayfa/kvkk">KVKK Aydınlatma Metni</a> ve <a href="/sayfa/gizlilik">Gizlilik Politikası</a>, çerezler ise <a href="/sayfa/cerez-politikasi">Çerez Politikası</a> kapsamında işlenir.</p>
<h3>8. Uygulanacak Hukuk</h3>
<p>Bu koşullar Türk hukukuna tabidir. Tüketici uyuşmazlıklarında Tüketici Hakem Heyetleri ve Tüketici Mahkemeleri, diğer uyuşmazlıklarda İstanbul (Merkez) Mahkemeleri ve İcra Daireleri yetkilidir.</p>
<h3>9. Değişiklikler</h3>
<p>Şirket bu koşulları güncelleyebilir; güncel metin her zaman bu sayfada yayımlanır. İletişim: {{sirket.eposta}} · {{sirket.telefon}}</p>""",
    },
    # ------------------------------------------------------------------ AÇIK RIZA
    {
        "slug": "acik-riza-metni",
        "title": "Açık Rıza Metni",
        "meta_title": "Açık Rıza Metni (Pazarlama ve Ticari Elektronik İleti) | {{site.ad}}",
        "meta_description": "{{site.ad}} pazarlama faaliyetleri ve ticari elektronik ileti gönderimi için açık rıza ve onay metni.",
        "content": """<p>Bu metin, {{sirket.unvan}} ("{{site.ad}}") tarafından; 6698 sayılı Kişisel Verilerin Korunması Kanunu md.5/1 ve 6563 sayılı Elektronik Ticaretin Düzenlenmesi Hakkında Kanun md.6 ile Ticari İletişim ve Ticari Elektronik İletiler Hakkında Yönetmelik kapsamında, <strong>isteğe bağlı</strong> olarak vereceğiniz açık rıza ve onayın kapsamını açıklar. Onay vermemeniz, alışveriş yapmanıza veya üyeliğinize hiçbir şekilde engel değildir.</p>
<h3>1. Onay verdiğiniz işlemler</h3>
<p>İlgili kutucuğu işaretleyerek;</p>
<ul>
<li>Ad-soyad, e-posta adresi, cep telefonu numarası, alışveriş geçmişi, sepet ve ürün inceleme verilerim ile çerez verilerimin; kampanya, indirim, yeni ürün, etkinlik ve atölye ekipmanlarına ilişkin içeriklerin bana sunulması, ilgi alanıma göre kişiselleştirilmiş teklif ve reklamlar oluşturulması, memnuniyet anketleri yapılması amaçlarıyla işlenmesine,</li>
<li>Bu amaçlarla <strong>SMS, e-posta, telefon araması ve anlık bildirim</strong> yoluyla tarafıma ticari elektronik ileti gönderilmesine ve onayımın İleti Yönetim Sistemi'ne (İYS) kaydedilmesine,</li>
<li>Pazarlama ve reklam hizmetlerinin sunulması için verilerimin, sunucuları yurt dışında bulunabilen e-posta / SMS gönderim, reklam (ör. Google, Meta) ve analitik hizmet sağlayıcılarına KVKK md.9 kapsamında aktarılmasına</li>
</ul>
<p>açık rıza ve onay veriyorum.</p>
<h3>2. Rızanın geri alınması</h3>
<p>Onayınızı dilediğiniz zaman, gerekçe göstermeksizin ve ücretsiz olarak:</p>
<ul>
<li>gelen e-postalardaki "abonelikten çık" bağlantısı veya SMS'lerdeki ret talimatı ile,</li>
<li>"Hesabım › İletişim Tercihleri" bölümünden,</li>
<li><a href="https://www.iys.org.tr" target="_blank" rel="noopener noreferrer">iys.org.tr</a> veya e-Devlet üzerinden,</li>
<li>{{sirket.eposta}} adresine e-posta göndererek</li>
</ul>
<p>geri alabilirsiniz. Ret bildiriminiz en geç 3 iş günü içinde işleme alınır. Rızanın geri alınması, geri alma tarihine kadar yapılan işlemlerin hukuka uygunluğunu etkilemez.</p>
<h3>3. Esnaf ve tacirler</h3>
<p>Mevzuat uyarınca esnaf ve tacirlere önceden onay alınmaksızın ticari elektronik ileti gönderilebilir; bu alıcılar da dilediği zaman ret hakkını kullanarak ileti almayı durdurabilir.</p>
<h3>4. Ayrıntılı bilgi</h3>
<p>Kişisel verilerinizin işlenmesine ilişkin ayrıntılar ve KVKK md.11'deki haklarınız için <a href="/sayfa/kvkk">KVKK Aydınlatma Metni</a>'ni inceleyebilirsiniz. Veri sorumlusu: {{sirket.unvan}}, {{sirket.adres}}.</p>""",
    },
    # ------------------------------------------------------------------ SSS
    {
        "slug": "sss",
        "title": "Sıkça Sorulan Sorular",
        "meta_title": "Sıkça Sorulan Sorular | {{site.ad}}",
        "meta_description": "{{site.ad}} SSS: kargo, kurulum, garanti, ödeme, kapıda ödeme, fatura ve iade hakkında sık sorulan sorular.",
        "content": """<p>Aşağıda en sık sorulan soruların yanıtlarını bulabilirsiniz. Aradığınız yanıtı bulamazsanız <a href="/sayfa/iletisim">bize ulaşın</a>.</p>
<h3>SİPARİŞ &amp; KARGO</h3>
<h4>Siparişim ne zaman kargoya verilir?</h4>
<p>Stoktaki ürünler ödeme onayından sonra genellikle 1–3 iş günü içinde kargoya verilir. Tedarikli ürünlerde tahmini süre ürün sayfasında yazar. Yasal azami teslim süresi 30 gündür.</p>
<h4>Hangi kargo firmalarıyla çalışıyorsunuz?</h4>
<p>Koliler MNG Kargo, Aras Kargo veya PTT Kargo ile; lift, büyük kompresör gibi ağır ürünler paletli olarak anlaşmalı ambar/nakliye firmalarıyla gönderilir.</p>
<h4>Siparişimi nasıl takip ederim?</h4>
<p>Kargoya verildiğinde takip numarası SMS/e-posta ile gönderilir. <a href="/siparis-takip">Sipariş Takibi</a> sayfasından veya "Hesabım" bölümünden durumu görebilirsiniz.</p>
<h4>Ağır ürünler kapıya kadar mı geliyor?</h4>
<p>Paletli ürünler, nakliye aracının ulaşabildiği noktada zemin seviyesine teslim edilir. Araçtan indirme için forklift/transpalet veya yeterli kişi bulundurmanız gerekir; kat çıkarma ve iç mekâna taşıma dahil değildir.</p>
<h4>Paket hasarlı geldi, ne yapmalıyım?</h4>
<p>Görevlinin yanında paketi kontrol edin, hasar varsa hasar tespit tutanağı düzenletin ve fotoğraf çekin. Ardından {{sirket.telefon}} veya {{sirket.eposta}} üzerinden mümkünse 24 saat içinde bize bildirin; ürününüz değiştirilir veya onarılır.</p>
<h3>KURULUM</h3>
<h4>Lift ve makineler için kurulum hizmeti veriyor musunuz?</h4>
<p>Kurulum hizmeti sunulan ürünlerde bu bilgi ürün sayfasında yer alır veya kurulum ayrıca satın alınabilir. Ürün teslim edildikten sonra yetkili teknisyenle randevu planlanır.</p>
<h4>Kurulumdan önce neleri hazırlamalıyım?</h4>
<p>Liftlerde üretici kılavuzundaki beton sınıfı ve kalınlığına uygun düz zemin; tüm elektrikli ürünlerde etiketteki gerilime (220 V / 380 V) uygun, topraklı ve sigortalı tesisat; pnömatik ekipmanlarda uygun basınç ve debide şartlandırıcılı hava hattı gerekir.</p>
<h4>Kurulumu kendim yaparsam garanti devam eder mi?</h4>
<p>Kurulum kılavuza uygun yapıldığı sürece garanti geçerlidir. Talimatlara aykırı veya yetkisiz kurulumdan kaynaklanan arızalar garanti kapsamı dışındadır. Kaldırma ekipmanlarında yetkili kurulum önerilir.</p>
<h3>GARANTİ &amp; SERVİS</h3>
<h4>Ürünlerin garanti süresi nedir?</h4>
<p>Tüketicilere satılan ürünlerde garanti süresi teslimden itibaren en az 2 yıldır. Üreticinin daha uzun garanti verdiği ürünlerde süre ürün sayfasında belirtilir.</p>
<h4>Ürünüm arızalandı, ne yapmalıyım?</h4>
<p>Sipariş numaranız, ürün seri numarası ve arızanın fotoğraf/videosuyla bize ulaşın. Ön tespitten sonra yerinde servis, yetkili servis veya ürünün servise gönderilmesi planlanır. Azami tamir süresi 20 iş günüdür.</p>
<h4>Yedek parça bulabilir miyim?</h4>
<p>Evet. Sattığımız ürünlerin yedek parça ve sarf malzemeleri için bize ulaşabilirsiniz; garanti dışı onarımlarda önce fiyat teklifi sunulur.</p>
<h3>ÖDEME</h3>
<h4>Hangi ödeme yöntemlerini kullanabilirim?</h4>
<p>Kredi/banka kartı (iyzico altyapısı, 3D Secure), havale/EFT ve uygun siparişlerde kapıda ödeme seçenekleri sunulur. Kartlı alımlarda bankanızın taksit seçenekleri ödeme ekranında görüntülenir.</p>
<h4>Kapıda ödeme var mı?</h4>
<p>Belirli tutar ve ürün gruplarında kapıda nakit veya kartla ödeme yapılabilir. Kapıda ödeme hizmet bedeli ve uygunluk ödeme adımında gösterilir. Paletli ve siparişe özel ürünlerde kapıda ödeme sunulmayabilir.</p>
<h4>Kart bilgilerim güvende mi?</h4>
<p>Kart bilgileriniz lisanslı ödeme kuruluşu iyzico tarafından işlenir; sunucularımızda saklanmaz. Tüm site trafiği SSL ile şifrelenir.</p>
<h4>Fiyatlara KDV dahil mi?</h4>
<p>Evet, sitedeki tüm fiyatlara KDV dahildir. Kargo ücreti varsa ödeme adımında ayrıca gösterilir.</p>
<h3>FATURA</h3>
<h4>Fatura gönderiyor musunuz?</h4>
<p>Her siparişe e-arşiv veya e-fatura düzenlenir ve e-posta adresinize gönderilir; dilerseniz "Hesabım" bölümünden de indirebilirsiniz.</p>
<h4>Şirketim adına fatura alabilir miyim?</h4>
<p>Evet. Ödeme adımında "Kurumsal fatura" seçeneğini işaretleyip firma ünvanı, vergi dairesi ve vergi numaranızı girmeniz yeterlidir. E-fatura mükellefiyseniz faturanız e-fatura olarak düzenlenir.</p>
<h4>Faturadaki bilgiyi değiştirebilir miyim?</h4>
<p>Fatura düzenlenmeden önce bize ulaşırsanız bilgiler güncellenebilir. Düzenlenmiş faturalarda değişiklik vergi mevzuatının izin verdiği ölçüde yapılabilir.</p>
<h3>İADE</h3>
<h4>Ürünü iade edebilir miyim?</h4>
<p>Tüketici alımlarında teslimden itibaren 14 gün içinde gerekçe göstermeden iade edebilirsiniz. Anlaşmalı kargo ile iade ücretsizdir. Ayrıntılar için <a href="/sayfa/iade-kosullari">İade ve Değişim Koşulları</a>.</p>
<h4>Şirket adına aldığım ürünü iade edebilir miyim?</h4>
<p>Ticari amaçlı alımlarda yasal cayma hakkı bulunmaz; ancak kullanılmamış ve yeniden satılabilir ürünler için iade talepleriniz iyi niyetle değerlendirilir.</p>
<h4>Para iadem ne zaman yapılır?</h4>
<p>Cayma bildiriminiz bize ulaştıktan sonra en geç 14 gün içinde iade yapılır. Karta yapılan iadelerin hesabınıza yansıma süresi bankanıza bağlıdır.</p>""",
    },
]

LEGAL_SLUGS = [p["slug"] for p in LEGAL_PAGES]
