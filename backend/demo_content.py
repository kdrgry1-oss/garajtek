"""Demo içerik paketi — gerçek ürünler eklenene kadar vitrini dolu gösterir.

Ne yükler? (v2)
  * 25 örnek ekipman ürünü (lift, kompresör, lastik, kaldırma, takım arabası, lokma/anahtar, test
    cihazları…; Türkçe ad, teknik tablo + yapılandırılmış `specs`, fiyat/indirim, stok (bir kısmı 0),
    varyant, kargo ölçüsü/ağırlığı, KDV %20, SEO meta) — görseller backend/assets/demo/img/products
  * 3 ÜRÜN SETİ ("Ürün Setleri" kategorisinde; biri stokta olmayan bileşen içerir) — product_sets.py
  * 3 ana sayfa hero slaytı (+ mobil), 4 küçük fırsat banner'ı, 1 tam genişlik banner, marka logoları
Her kayıt `demo: True` ve `seed_source: "garajtek_demo_v2"` ile etiketlenir; KALDIR işlemi YALNIZ
demo etiketli (v1 dahil) ürün/banner/dosyaları siler, başka hiçbir şeye dokunmaz. Yükleme
idempotenttir ve eski sürümü YÜKSELTİR: önce v1/v2 demo kayıtları kaldırılır, sonra v2 yüklenir.

Kullanım:
  * Panel: Sayfa Tasarımı › Demo İçerik (POST/DELETE /api/admin/demo-content — yalnız süper yönetici)
  * Komut satırı: backend/seed_demo.py (bkz. dosya başı; servis DURDURULMUŞKEN çalışır)
Görseller uygulamanın kullandığı depoya yüklenir (R2 / MEDIA_DIR / veritabanı) → URL'ler
üretimde de çalışır.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

DEMO_TAG = "garajtek_demo_v2"
ALL_TAGS = ["garajtek_demo_v1", DEMO_TAG]  # kaldırma/yükseltme: eski sürümler dahil
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "demo", "img")


def _spec_html(intro: str, bullets: list[str], specs: list[tuple[str, str]]) -> str:
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in specs)
    lis = "".join(f"<li>{b}</li>" for b in bullets)
    return (f"<p>{intro}</p><h3>Öne Çıkan Özellikler</h3><ul>{lis}</ul>"
            f"<h3>Teknik Özellikler</h3><table><tbody>{rows}</tbody></table>"
            "<p><em>Bu ürün demo içeriktir; gerçek ürünler eklendiğinde panelden kaldırılabilir.</em></p>")


def _p(key, name, brand, cats, price, sale, stock, featured, specs, intro, bullets, *, variants=None,
       spec=None, dims=(0, 0, 0), kg=0.0, cod_disabled=False, images=3, model="", variant_label="Seçenek"):
    """Demo ürün tanımı. specs: görünen teknik tablo [(ad, değer)]; spec: yapılandırılmış
    `specs` nesnesi (anahtarlar ekipman şablonuyla aynı); dims: (en, derinlik, yükseklik) cm."""
    return {"key": key, "name": name, "brand": brand, "cats": cats, "price": price, "sale": sale,
            "stock": stock, "featured": featured, "specs": specs, "intro": intro, "bullets": bullets,
            "variants": variants, "spec": spec or {}, "dims": dims, "kg": kg, "cod_disabled": cod_disabled,
            "images": images, "model": model, "variant_label": variant_label}


# 25 örnek ürün — garajtek.com'un referans aldığı iki ekipman mağazasının (grayzer.net,
# algikitelli.com.tr) sattığı ürün TİPLERİNDEN derlendi; ad/açıklama/teknik tablo ve görseller
# ÖZGÜNDÜR (metin/görsel kopyalanmadı), markalar kurgusal demo markalarıdır. Fiyatlar 2026 TR
# piyasa seviyesinde, KDV dahil. Ağır/hacimli liftler kapıda ödemeye KAPALI (ambar teslim).
P = [
    _p("lift2-4t", "4 Ton Çift Sütunlu Hidrolik Lift – Tabandan Bağlantılı", "GarajTek Pro",
       ["iki-sutunlu-liftler"], 139900, 129900, 4, True,
       [("Kaldırma Kapasitesi", "4.000 kg"), ("Kaldırma Yüksekliği", "1.900 mm"), ("Motor Gücü", "2,2 kW"),
        ("Kaldırma Süresi", "≈ 50 sn"), ("Sütunlar Arası", "2.800 mm"), ("Kilit", "Otomatik mekanik kilit")],
       "Bakım ve onarım servisleri için tabandan bağlantılı, çift silindirli iki sütunlu lift. Asimetrik kol yapısıyla kapı açma mesafesi geniş.",
       ["Çift hidrolik silindir, senkron halat", "Otomatik kol kilitleme", "Asimetrik / simetrik kol kurulumu", "CE uygunluk belgeli, 24 ay garanti"],
       variants=[("220V Monofaze", 2), ("380V Trifaze", 2)], cod_disabled=True, variant_label="Elektrik Bağlantısı",
       spec={"kapasite_ton": 4, "kaldirma_yuksekligi_mm": 1900, "motor_gucu_kw": 2.2, "garanti_ay": 24, "mense": "Türkiye"},
       dims=(300, 60, 60), kg=640, model="GTP-L40"),
    _p("lift2-5t", "5 Ton Tam Otomatik Üstten Bağlantılı İki Sütunlu Lift", "Liftmax",
       ["iki-sutunlu-liftler"], 174500, None, 2, False,
       [("Kaldırma Kapasitesi", "5.000 kg"), ("Kaldırma Yüksekliği", "1.950 mm"), ("Motor Gücü", "3 kW"),
        ("Kilit", "Elektromanyetik otomatik"), ("Toplam Yükseklik", "4.250 mm")],
       "Hafif ticari araçlar ve SUV'lar için güçlendirilmiş sütunlu, üstten bağlantılı tam otomatik lift.",
       ["Elektromanyetik kilit açma", "Üst limit güvenlik switch'i", "Uzun kol seti dahil"],
       variants=[("380V Trifaze", 2)], cod_disabled=True, variant_label="Elektrik Bağlantısı",
       spec={"kapasite_ton": 5, "kaldirma_yuksekligi_mm": 1950, "motor_gucu_kw": 3, "voltaj": "380 V", "faz": "Trifaze", "garanti_ay": 24},
       dims=(320, 70, 70), kg=780, model="LM-500T"),
    _p("scissor-32t", "3,2 Ton Makaslı Hidrolik Lift – 2 Metre Platform", "Liftmax",
       ["makasli-liftler"], 175000, 162500, 3, True,
       [("Kaldırma Kapasitesi", "3.200 kg"), ("Platform Uzunluğu", "2.000 mm"), ("Minimum Yükseklik", "110 mm"),
        ("Kaldırma Yüksekliği", "1.000 mm"), ("Kilit", "Pnömatik emniyet kilidi")],
       "Lastik, fren ve rot-balans servisleri için zemin üstü montajlı, alçak profilli makaslı lift.",
       ["Pnömatik emniyet kilidi", "Taşınabilir hidrolik ünite", "Kauçuk takoz seti dahil"],
       cod_disabled=True, spec={"kapasite_ton": 3.2, "kaldirma_yuksekligi_mm": 1000, "calisma_basinci_bar": 6, "garanti_ay": 24},
       dims=(210, 60, 30), kg=560, model="LM-S32"),
    _p("moto-lift", "500 Kg Hidrolik Motosiklet Lifti", "Teknolift",
       ["motosiklet-liftleri"], 32900, 29900, 7, False,
       [("Kapasite", "500 kg"), ("Platform", "2.200 × 680 mm"), ("Kaldırma", "Ayak pompalı hidrolik"), ("Maks. Yükseklik", "780 mm")],
       "Motosiklet, scooter ve ATV servisleri için teker kelepçeli hidrolik çalışma platformu.",
       ["Ön teker kelepçesi", "Çıkarılabilir arka panel", "Taşıma tekerlekleri"],
       spec={"kapasite_kg": 500, "guc_kaynagi": "Hidrolik", "garanti_ay": 24},
       dims=(220, 70, 25), kg=135, model="TL-M500"),
    _p("comp-200", "200 Lt 3 HP Çift Kafa Pistonlu Hava Kompresörü (Yağlı, Döküm)", "Airpro",
       ["pistonlu-kompresorler", "indirimli-urunler"], 28900, 25900, 9, True,
       [("Tank Hacmi", "200 Lt"), ("Motor Gücü", "3 HP / 2,2 kW"), ("Hava Debisi", "360 Lt/dk"),
        ("Maks. Basınç", "8 bar"), ("Silindir", "2 kafa, döküm")],
       "Atölye ve servisler için yağlı, döküm silindirli, iki kafalı pistonlu kompresör.",
       ["Termik motor koruması", "Çift çıkışlı regülatör ve manometre", "Döküm gövde, uzun ömür"],
       variants=[("220V", 5), ("380V", 4)], variant_label="Voltaj",
       spec={"tank_hacmi_lt": 200, "motor_gucu_kw": 2.2, "calisma_basinci_bar": 8, "hava_debisi_lt_dk": 360, "garanti_ay": 24},
       dims=(150, 50, 95), kg=118, model="AP-2003"),
    _p("comp-50-silent", "50 Lt Sessiz ve Yağsız Hava Kompresörü 1,5 HP", "Airpro",
       ["sessiz-ve-yagsiz-kompresorler"], 11900, 10490, 14, True,
       [("Tank Hacmi", "50 Lt"), ("Ses Seviyesi", "59 dB"), ("Hava Debisi", "160 Lt/dk"), ("Maks. Basınç", "8 bar")],
       "Boya, detay ve kapalı alan işleri için yağsız, temiz hava üreten sessiz kompresör.",
       ["59 dB sessiz çalışma", "Yağsız motor, bakım gerektirmez", "Hafif ve kompakt"],
       spec={"tank_hacmi_lt": 50, "motor_gucu_kw": 1.1, "calisma_basinci_bar": 8, "voltaj": "220 V", "garanti_ay": 24},
       dims=(80, 40, 70), kg=38, model="AP-50S"),
    _p("impact-12", "1/2\" Havalı Somun Sökme Tabancası 1.350 Nm İkiz Çekiç", "Torkmatik",
       ["havali-somun-sokme-makineleri"], 3490, 2990, 40, True,
       [("Lokma Girişi", "1/2\""), ("Maks. Tork", "1.350 Nm"), ("Devir", "7.000 dev/dk"), ("Hava Tüketimi", "142 Lt/dk"), ("Ağırlık", "2,1 kg")],
       "İkiz çekiç mekanizmalı, lastik servisleri için güçlü ve hafif havalı somun sökme tabancası.",
       ["İkiz çekiç mekanizma", "3 kademeli güç ayarı", "Kompozit gövde, darbe dayanımlı"],
       spec={"lokma_girisi": "1/2\"", "tork_nm": 1350, "calisma_basinci_bar": 6.3, "garanti_ay": 12},
       dims=(25, 10, 22), kg=2.1, model="TM-1350"),
    _p("tire-changer", "Yarı Otomatik Lastik Sökme Takma Makinesi 10–24 inç", "Balanstek",
       ["lastik-sokme-takma-makineleri"], 69900, 64900, 4, True,
       [("Jant Aralığı", "10\" – 24\""), ("Motor", "1,1 kW"), ("Çalışma Basıncı", "8 – 10 bar"), ("Maks. Lastik Çapı", "1.050 mm")],
       "Binek ve hafif ticari araç lastikleri için pnömatik kafa kilitli yarı otomatik sökme takma makinesi.",
       ["Pnömatik kafa kilidi", "Lastik şişirme tabancası dahil", "Çift hızlı tabla"],
       variants=[("220V", 2), ("380V", 2)], variant_label="Voltaj",
       spec={"jant_araligi_inc": "10-24", "motor_gucu_kw": 1.1, "calisma_basinci_bar": 10, "garanti_ay": 24},
       dims=(100, 80, 100), kg=210, model="BT-TC24"),
    _p("balancer", "Otomatik Ölçü Kollu Dijital Balans Makinesi 10–24 inç", "Balanstek",
       ["lastik-balans-makineleri"], 59900, 54900, 5, True,
       [("Jant Çapı", "10\" – 24\""), ("Hassasiyet", "±1 g"), ("Ölçüm Süresi", "7 sn"), ("Programlar", "ALU-S, statik, gizli ağırlık")],
       "Otomatik mesafe ölçüm kollu, ALU programlı dijital balans makinesi.",
       ["Otomatik mesafe kolu", "ALU-S ve gizli ağırlık programı", "Koruma kapağı ile otomatik başlatma"],
       spec={"jant_araligi_inc": "10-24", "voltaj": "220 V", "garanti_ay": 24},
       dims=(100, 80, 120), kg=145, model="BT-B885"),
    _p("inflator", "Dijital Manometreli Lastik Şişirme Tabancası 0–12 Bar", "Airpro",
       ["lastik-sisirme-cihazlari"], 1490, 1190, 60, False,
       [("Ölçüm Aralığı", "0 – 12 bar"), ("Hortum", "50 cm"), ("Ekran", "Dijital, aydınlatmalı")],
       "Kalibre dijital manometreli, hızlı bağlantılı lastik şişirme tabancası.",
       ["Kauçuk korumalı gövde", "Hava boşaltma valfi", "bar / psi / kPa birim seçimi"],
       spec={"calisma_basinci_bar": 12, "garanti_ay": 12}, dims=(30, 10, 20), kg=0.9, model="AP-DG12"),
    _p("floor-jack-3t", "3 Ton Çift Pistonlu Hızlı Kaldırmalı Servis Krikosu", "Torkmatik",
       ["yer-krikolari", "indirimli-urunler"], 5900, 4990, 25, True,
       [("Kapasite", "3.000 kg"), ("Min. Yükseklik", "85 mm"), ("Maks. Yükseklik", "500 mm"), ("Ağırlık", "34 kg")],
       "Çift pistonlu hızlı kaldırma sistemiyle profesyonel servis tipi yer krikosu.",
       ["Çift piston hızlı kaldırma", "Aşırı yük emniyet valfi", "360° döner arka tekerlek"],
       spec={"kapasite_ton": 3, "kaldirma_yuksekligi_mm": 500, "garanti_ay": 24}, dims=(75, 38, 20), kg=34, model="TM-FJ3"),
    _p("engine-crane", "2 Ton Katlanır Hidrolik Motor İndirme Vinci", "Teknolift",
       ["motor-vincleri"], 17900, 15900, 6, False,
       [("Kapasite", "2.000 kg (4 kademe)"), ("Maks. Kaldırma", "2.350 mm"), ("Bom Uzunluğu", "1.050 – 1.450 mm"), ("Katlanmış Ölçü", "1.300 × 650 mm")],
       "Motor ve şanzıman sökme-takma işleri için katlanabilir ayaklı, 4 kademeli hidrolik atölye vinci.",
       ["Katlanır ayaklar, az yer kaplar", "Çift etkili hidrolik pompa", "Emniyet valfi ve zincirli kanca"],
       spec={"kapasite_ton": 2, "kaldirma_yuksekligi_mm": 2350, "guc_kaynagi": "Hidrolik", "garanti_ay": 24},
       dims=(140, 70, 35), kg=82, model="TL-EC2"),
    _p("press-20t", "20 Ton Hidrolik Atölye Presi (Manometreli)", "Teknolift",
       ["hidrolik-presler"], 21900, None, 0, False,
       [("Kapasite", "20 ton"), ("Piston Kursu", "150 mm"), ("Çalışma Aralığı", "0 – 900 mm"), ("Manometre", "Ø 80 mm")],
       "Rulman, burç ve pim sökme-takma işleri için ayarlanabilir tablalı H tipi hidrolik pres.",
       ["Kademeli tabla yüksekliği", "Manometre ile kuvvet takibi", "V-blok seti dahil"],
       spec={"kapasite_ton": 20, "guc_kaynagi": "Hidrolik", "garanti_ay": 24}, dims=(80, 60, 160), kg=96, model="TL-P20"),
    _p("cart-full-185", "185 Parça 7 Çekmeceli Dolu Takım Arabası", "Atölye Pro",
       ["dolu-takim-arabalari", "indirimli-urunler"], 32500, 29900, 6, True,
       [("Çekmece", "7 adet (6 dolu)"), ("Parça Sayısı", "185"), ("Malzeme", "Cr-V çelik el aletleri"), ("Ölçü", "680 × 460 × 1.000 mm")],
       "Lokma, anahtar, tornavida ve pense setleri köpük tepsilere yerleştirilmiş dolu takım arabası.",
       ["Köpük tepsili düzen", "Bilyalı raylar, merkezi kilit", "Frenli tekerlek"],
       spec={"parca_sayisi": 185, "cekmece_sayisi": 7, "garanti_ay": 24}, dims=(70, 48, 100), kg=88, model="AP-185"),
    _p("cart-empty-7", "7 Çekmeceli Boş Takım Arabası (Bilyalı Ray)", "Atölye Pro",
       ["takim-arabalari"], 12900, 11490, 8, False,
       [("Çekmece", "7 adet"), ("Taşıma", "350 kg"), ("Ölçü", "680 × 460 × 1.000 mm"), ("Kaplama", "Elektrostatik toz boya")],
       "Bilyalı raylı, merkezi kilitli, kauçuk kaplı üst yüzeyli çelik takım arabası.",
       ["Bilyalı raylar", "Merkezi kilit", "Kauçuk kaplı üst yüzey"],
       spec={"cekmece_sayisi": 7, "kapasite_kg": 350, "garanti_ay": 24}, dims=(70, 48, 100), kg=56, model="AP-C7"),
    _p("socket-108", "108 Parça 1/4\"–1/2\" Krom Vanadyum Lokma Takımı", "Torkmatik",
       ["lokma-setleri"], 3890, 3290, 45, True,
       [("Parça Sayısı", "108"), ("Lokma Girişi", "1/4\" ve 1/2\""), ("Malzeme", "Cr-V çelik"), ("Cırcır", "72 diş")],
       "Krom vanadyum çelikten, sağlam taşıma çantalı geniş kapsamlı lokma takımı.",
       ["72 dişli cırcır kolları", "Derin ve kısa lokmalar", "Bits uçlar ve uzatmalar dahil"],
       variants=[("Metrik", 30), ("Metrik + İnç", 15)], variant_label="Ölçü Sistemi",
       spec={"parca_sayisi": 108, "lokma_girisi": "1/4\" + 1/2\"", "garanti_ay": 24}, dims=(45, 33, 9), kg=6.2, model="TM-108"),
    _p("socket-94", "94 Parça 1/2\" Darbeli Lokma ve Uç Seti", "Torkmatik",
       ["lokma-setleri"], 4650, None, 0, False,
       [("Parça Sayısı", "94"), ("Lokma Girişi", "1/2\""), ("Malzeme", "Cr-Mo darbeli çelik")],
       "Havalı ve akülü somun sökme makineleri için darbeye dayanıklı Cr-Mo lokma seti.",
       ["Darbeli Cr-Mo çelik", "Fosfat kaplama", "Plastik taşıma çantası"],
       spec={"parca_sayisi": 94, "lokma_girisi": "1/2\"", "garanti_ay": 24}, dims=(42, 30, 9), kg=7.4, model="TM-94D"),
    _p("torque-wrench", "1/2\" Klik Tip Tork Anahtarı 40–210 Nm", "Torkmatik",
       ["tork-anahtarlari"], 4490, 3990, 18, False,
       [("Ölçüm Aralığı", "40 – 210 Nm"), ("Giriş", "1/2\""), ("Hassasiyet", "±%4"), ("Uzunluk", "485 mm")],
       "Kalibrasyon sertifikalı, çift yönlü klik tip tork anahtarı — bijon ve motor işlerinde güvenli sıkma.",
       ["Kalibrasyon sertifikası", "Çift yönlü cırcır", "Kilitli ayar sapı"],
       spec={"lokma_girisi": "1/2\"", "tork_nm": 210, "garanti_ay": 12}, dims=(55, 10, 8), kg=1.6, model="TM-TW210"),
    _p("wrench-12", "12 Parça Yıldız-Açık Ağız Kombine Anahtar Takımı 8–19 mm", "Torkmatik",
       ["anahtar-takimlari", "yildiz-iki-agiz-anahtarlar"], 1690, 1390, 50, False,
       [("Ölçüler", "8 – 19 mm"), ("Malzeme", "Cr-V"), ("Kaplama", "Saten krom")],
       "15° açılı yıldız ağızlı kombine anahtar takımı, rulo çantalı.",
       ["15° açılı yıldız ağız", "Saten krom kaplama", "Rulo taşıma çantası"],
       spec={"parca_sayisi": 12, "garanti_ay": 24}, dims=(35, 20, 5), kg=2.3, model="TM-W12"),
    _p("battery-tester", "12V Dijital Akü Test Cihazı (CCA 100–2000)", "Diagnox",
       ["aku-test-ve-takviye-cihazlari"], 2790, 2390, 20, False,
       [("Voltaj", "12 V"), ("CCA Aralığı", "100 – 2.000"), ("Standartlar", "SAE, EN, DIN, IEC, JIS"), ("Ekran", "LCD, Türkçe")],
       "Akü sağlığı, marş ve şarj sistemi testlerini saniyeler içinde yapan dijital test cihazı.",
       ["Marş ve şarj sistemi testi", "Türkçe menü", "Ters bağlantı koruması"],
       spec={"voltaj": "12 V", "garanti_ay": 12}, dims=(25, 15, 8), kg=0.6, model="DX-BT12"),
    _p("booster", "12/24V Akü Takviye ve Şarj Cihazı 1.000 A", "Diagnox",
       ["aku-test-ve-takviye-cihazlari"], 12900, None, 8, False,
       [("Çıkış Voltajı", "12 V / 24 V"), ("Takviye Akımı", "1.000 A"), ("Şarj Akımı", "60 A"), ("Giriş", "220 V")],
       "Binek ve ticari araçlar için tekerlekli, takviye (start) ve şarj fonksiyonlu servis cihazı.",
       ["Start ve şarj modu", "Termik aşırı yük koruması", "Uzun pens kabloları"],
       spec={"voltaj": "220 V", "guc_kaynagi": "Elektrik", "garanti_ay": 24}, dims=(45, 40, 80), kg=29, model="DX-B1000"),
    _p("oil-drain-80", "80 Lt Pnömatik Atık Yağ Toplama ve Boşaltma Cihazı", "Teknolift",
       ["yag-bosaltma-ve-degistirme-cihazlari"], 9900, 8790, 7, True,
       [("Tank", "80 Lt"), ("Huni Yüksekliği", "1.350 – 1.900 mm"), ("Boşaltma", "Pnömatik"), ("Ön Hazne", "8 Lt, şeffaf")],
       "Lift altı kullanım için teleskopik hunili, pnömatik boşaltmalı atık yağ toplama cihazı.",
       ["Seviye göstergesi", "Teleskopik huni", "Pnömatik boşaltma"],
       spec={"tank_hacmi_lt": 80, "calisma_basinci_bar": 8, "garanti_ay": 24}, dims=(60, 60, 110), kg=32, model="TL-OD80"),
    _p("smoke-tester", "Duman Kaçak Tespit Cihazı (EVAP / Emme Hattı)", "Diagnox",
       ["duman-kacak-test-cihazlari"], 10560, 9490, 9, True,
       [("Kullanım", "Emme, egzoz, EVAP, turbo hattı"), ("Besleme", "12 V araç aküsü"), ("Debimetre", "Dahili"), ("Duman Sıvısı", "Mineral yağ bazlı")],
       "Vakum ve EVAP kaçaklarını yoğun, zararsız dumanla dakikalar içinde görünür kılan test cihazı.",
       ["Dahili debimetre ve basınç göstergesi", "EVAP adaptör seti", "Akü ile çalışır, taşınabilir"],
       spec={"voltaj": "12 V", "guc_kaynagi": "Akülü", "garanti_ay": 12}, dims=(40, 30, 30), kg=7.8, model="DX-SM3"),
    _p("work-light", "50 W Şarjlı LED Çalışma Lambası IP65", "Voltix",
       ["led-lambalar-ve-calisma-isiklari"], 1450, 1190, 55, False,
       [("Güç", "50 W"), ("Işık Akısı", "4.500 lm"), ("Çalışma Süresi", "6 saat"), ("Koruma", "IP65")],
       "Tripodlu, şarjlı, suya ve toza dayanıklı atölye aydınlatması.",
       ["IP65 koruma", "3 kademeli parlaklık", "USB çıkışlı powerbank"],
       spec={"guc_w": 50, "guc_kaynagi": "Akülü", "garanti_ay": 12}, dims=(30, 15, 35), kg=2.4, model="VX-WL50"),
    _p("workbench", "2 Metre Takım Tezgahı – Delikli Panolu, 4 Çekmeceli", "Atölye Pro",
       ["takim-tezgahlari"], 16500, 14900, 5, False,
       [("Uzunluk", "2.000 mm"), ("Tabla", "Kayın masif 40 mm"), ("Taşıma", "800 kg"), ("Çekmece", "4 adet")],
       "Mengene montajına uygun masif tablalı, delikli takım panolu atölye tezgahı.",
       ["Delikli takım panosu", "4 bilyalı çekmece", "Ayarlanabilir ayak"],
       spec={"kapasite_kg": 800, "cekmece_sayisi": 4, "garanti_ay": 24}, dims=(205, 70, 25), kg=115, model="AP-WB200"),
]

# Demo ÜRÜN SETLERİ (Ürün Setleri kategorisi). items: (ürün anahtarı, adet, varyant adı | None).
# "Atölye El Aletleri Seti" bilerek STOKTA OLMAYAN bir bileşen (94 parça darbeli lokma seti)
# içerir → sepette "Bu ürünü değiştir" akışı (aynı alt kategoriden 108 parça set) denenebilir.
# "Oto Servis Kurulum Seti" kapıda ödemeye kapalı bir lift içerir → kasada kapıda ödeme sunulmaz.
SETS = [
    {"key": "set-lastikci", "name": "Lastikçi Başlangıç Seti", "pct": 7, "featured": True,
     "intro": "Yeni açılan lastik servisleri için sökme-takma, balans, hava ve somun sökme ekipmanı tek sette.",
     "items": [("tire-changer", 1, "380V"), ("balancer", 1, None), ("comp-200", 1, "380V"),
               ("impact-12", 1, None), ("inflator", 1, None)]},
    {"key": "set-oto-servis", "name": "Oto Servis Kurulum Seti", "pct": 6, "featured": True,
     "intro": "Mekanik servis kurulumu için lift, kaldırma, yağ değişimi ve arıza tespit ekipmanları.",
     "items": [("lift2-4t", 1, "380V Trifaze"), ("floor-jack-3t", 1, None), ("engine-crane", 1, None),
               ("oil-drain-80", 1, None), ("smoke-tester", 1, None), ("battery-tester", 1, None)]},
    {"key": "set-el-aletleri", "name": "Atölye El Aletleri Seti", "pct": 10, "featured": True,
     "intro": "Takım arabası, lokma ve anahtar takımları, tork anahtarı, havalı tabanca ve aydınlatma — atölyenin el aletleri tek seferde.",
     "items": [("cart-empty-7", 1, None), ("socket-94", 1, None), ("torque-wrench", 1, None),
               ("wrench-12", 1, None), ("impact-12", 1, None), ("work-light", 2, None)]},
]

HEROES = [
    ("hero-1", "İki Sütunlu Liftlerde Sezon Fırsatı", "4 TON ÇİFT SÜTUNLU LİFT — 129.900 ₺'DEN BAŞLAYAN FİYATLAR", "/iki-sutunlu-liftler"),
    ("hero-2", "Kompresör ve Havalı Aletler", "ATÖLYENİN GÜCÜ — %15'E VARAN İNDİRİM", "/kompresorler"),
    ("hero-3", "Lastik Servisi Ekipmanları", "SÖKME TAKMA + BALANS SETLERİNDE AVANTAJ", "/lastik-ekipmanlari"),
]
SMALL = [
    ("small-1", "Lokma takımlarında büyük fırsat", "/lokma-takimlari"),
    ("small-2", "Kompresör sezonu başladı", "/kompresorler"),
    ("small-3", "Arıza tespiti artık çok kolay", "/test-ve-ariza-tespit-cihazlari"),
    ("small-4", "Ürün setleri — tek tıkla sepette", "/urun-setleri"),
]
WIDE = ("wide-1", "Atölyenizi kazançla donatın", "/indirimli-urunler")
# Ana sayfa "Reklam Bannerları" bloğu (şablon ads-block: 410x281, 410x281, 714x486)
ADS = [("ad-1", "/lokma-takimlari"), ("ad-2", "/kompresorler"), ("ad-3", "/takim-arabalari-ve-tezgahlar")]
BRANDS = ["GarajTek Pro", "Liftmax", "Airpro", "Torkmatik", "Balanstek", "Voltix", "Weldon", "Diagnox", "Teknolift", "Atölye Pro"]


def _read(rel: str) -> bytes:
    with open(os.path.join(IMG_DIR, rel), "rb") as f:
        return f.read()


async def demo_status(db) -> dict:
    q = {"seed_source": {"$in": ALL_TAGS}}
    return {
        "products": await db.products.count_documents({**q, "product_type": {"$ne": "set"}}),
        "sets": await db.products.count_documents({**q, "product_type": "set"}),
        "banners": await db.banners.count_documents(q),
        "files": await db.files.count_documents(q),
        "available_products": len(P),
        "available_sets": len(SETS),
        "version": DEMO_TAG,
        "outdated": await db.products.count_documents({"seed_source": {"$in": [t for t in ALL_TAGS if t != DEMO_TAG]}}) > 0,
    }


async def remove_demo(db) -> dict:
    """YALNIZ demo etiketli kayıtları siler."""
    from routes.upload import delete_stored_file

    q = {"seed_source": {"$in": ALL_TAGS}}
    files = await db.files.find(q, {"_id": 0, "id": 1, "r2_key": 1, "r2_url": 1, "storage_path": 1}).to_list(5000)
    urls = set()
    for rec in files:
        if rec.get("r2_url"):
            urls.add(rec["r2_url"])
        if rec.get("storage_path"):
            urls.add(f"/api/upload/files/{rec['storage_path']}")
    blocks_cleaned = await _strip_from_blocks(db, urls)
    for rec in files:
        await delete_stored_file(rec)
    pr = await db.products.delete_many({**q, "demo": True})
    br = await db.banners.delete_many({**q, "demo": True})
    return {"removed_products": pr.deleted_count, "removed_banners": br.deleted_count, "removed_files": len(files),
            "blocks_cleaned": blocks_cleaned}


def _is_demo(url, urls):
    u = str(url or "")
    return bool(u) and (u in urls or any(u.endswith(x) for x in urls if x.startswith("/api/")))


async def _layout_docs(db):
    """Ana sayfa yayın + taslak belgeleri (Sayfa Tasarımı v2, page_layouts)."""
    try:
        from pageblocks import store
        await store.ensure(db, "home")
    except Exception:  # noqa: BLE001
        pass
    return [d for d in [await db.page_layouts.find_one({"id": "home:published"}, {"_id": 0}),
                        await db.page_layouts.find_one({"id": "home:draft"}, {"_id": 0})] if d]


async def _save_layout(db, doc, *, mirror: bool):
    await db.page_layouts.replace_one({"id": doc["id"]}, doc, upsert=True)
    if mirror:
        await db.page_blocks.delete_many({"$or": [{"page": "home"}, {"page": None}, {"page": {"$exists": False}}]})
        for b in doc.get("blocks") or []:
            await db.page_blocks.insert_one({**b, "page": "home"})
    try:
        from pageblocks.products import clear_cache
        clear_cache()
    except Exception:  # noqa: BLE001
        pass


def _strip_value(v, urls):
    """Ayar ağacında demo görsellerini kaldırır. Dönüş: (yeni_değer, değişti_mi)."""
    if isinstance(v, dict):
        if "url" in v and _is_demo(v.get("url"), urls) and set(v) <= {"url", "alt", "w", "h", "focal", "mobile_url",
                                                                      "mobile_focal", "crop"}:
            return None, True
        ch = False
        out = {}
        for k, x in v.items():
            nx, c = _strip_value(x, urls)
            out[k] = nx
            ch = ch or c
        return out, ch
    if isinstance(v, list):
        ch = False
        out = []
        for x in v:
            nx, c = _strip_value(x, urls)
            ch = ch or c
            out.append(nx)
        return out, ch
    return v, False


async def _strip_from_blocks(db, urls) -> int:
    """Ana sayfa bloklarından YALNIZ demo görsellerini çıkarır (yöneticinin eklediklerine dokunmaz).
    Görseli demo olan hero slaytları ve marka logoları tümden kaldırılır."""
    if not urls:
        return 0
    n = 0
    for doc in await _layout_docs(db):
        changed_doc = False
        for blk in doc.get("blocks") or []:
            st = blk.get("settings") or {}
            ch = False
            if blk.get("type") == "hero_slider" and isinstance(st.get("slides"), list):
                keep = [x for x in st["slides"] if not _is_demo(((x or {}).get("background") or {}).get("url"), urls)]
                if len(keep) != len(st["slides"]):
                    st["slides"], ch = keep, True
            if blk.get("type") == "brands_carousel" and isinstance(st.get("brands"), list):
                keep = [x for x in st["brands"] if not _is_demo(((x or {}).get("logo") or {}).get("url"), urls)]
                if len(keep) != len(st["brands"]):
                    st["brands"], ch = keep, True
                    if not keep:
                        st["source"] = "catalog"
            st2, c2 = _strip_value(st, urls)
            if ch or c2:
                st2.pop("_demo", None)
                if blk.get("type") == "hero_slider" and not st2.get("slides"):
                    from pageblocks import default_settings
                    st2["slides"] = default_settings("hero_slider", st2.get("_variant"))["slides"]
                blk["settings"] = st2
                changed_doc = True
                n += 1
        if changed_doc:
            await _save_layout(db, doc, mirror=doc["id"].endswith(":published"))
    return n


async def load_demo(db, create_product) -> dict:
    """Demo içeriği yükler. `create_product(data) -> {"id": ...}` panelin ürün oluşturma akışıdır
    (barkod/varyant id/slug/kategori ataları aynı kurallarla üretilir)."""
    from routes.upload import store_image_bytes

    removed = await remove_demo(db)  # idempotent: eski demo setini temizle
    tag = {"demo": True, "seed_source": DEMO_TAG}

    async def upload(rel: str) -> str:
        res = await store_image_bytes(_read(rel), "image/webp", "webp", f"demo-{os.path.basename(rel)}", extra=tag)
        return res["url"]

    await _ensure_set_category(db)
    cats = {c["slug"]: c for c in await db.categories.find({}, {"_id": 0, "id": 1, "slug": 1, "name": 1}).to_list(5000)}
    now = datetime.now(timezone.utc)
    created, skipped = [], []
    by_key = {}
    for i, d in enumerate(P):
        cslugs = d["cats"]
        cat_ids = [cats[s]["id"] for s in cslugs if s in cats]
        if not cat_ids:
            skipped.append(d["name"])
            continue
        images = [await upload(f"products/{d['key']}-{n}.webp") for n in range(1, d["images"] + 1)]
        price, sale = d["price"], d["sale"]
        w, dep, h = d["dims"]
        intro = d["intro"]
        data = {
            "name": d["name"],
            "brand": d["brand"],
            "manufacturer": d["brand"],
            "price": float(price),
            "sale_price": float(sale) if sale else None,
            "categories": cat_ids,
            "category_id": cat_ids[0],
            "category_name": cats[cslugs[0]]["name"] if cslugs[0] in cats else "",
            "images": images,
            "description": _spec_html(intro, d["bullets"], d["specs"]),
            "short_description": intro,
            "attributes": [{"name": k, "value": v} for k, v in d["specs"]],
            "stock": d["stock"],
            "stock_code": f"GT-DEMO-{i + 1:03d}",
            "is_active": True,
            "is_featured": d["featured"],
            "is_new": i % 4 == 0,
            "is_free_shipping": price >= 5000,
            "vat_rate": 20,
        }
        if d["variants"]:
            data["variants"] = [{"size": v, "stock": st} for v, st in d["variants"]]
        res = await create_product(data)
        pid = res.get("id")
        ids = res.get("product_ids") or [pid]
        desi = round(w * dep * h / 3000.0, 1) if (w and dep and h) else 0
        specs, extra_specs = _canonical_specs({"model": d["model"], **d["spec"]})
        extra = {
            # create_product yalnız bilinen alanları alır → kargo/SEO/teknik alanlar burada yazılır
            "specs": specs, "extra_specs": extra_specs,
            **({"variant_labels": {"size": d["variant_label"]}} if d["variants"] else {}),
            "width": w, "depth": dep, "height": h, "product_weight": d["kg"], "cargo_weight": desi,
            "meta_title": f"{d['name']} | GarajTek"[:70],
            "meta_description": intro[:155],
            "cod_disabled": bool(d["cod_disabled"]),
            "vat_rate": 20, "vat_included": True,
        }
        await db.products.update_many(
            {"id": {"$in": ids}},
            {"$set": {**tag, **extra, "created_at": (now - timedelta(hours=i * 7)).isoformat(),
                      "sold_count": (len(P) - i) * 3 % 41}})
        created.extend(ids)
        by_key[d["key"]] = pid

    sets_created = await _load_sets(db, create_product, cats, by_key, upload, tag, now)
    banners = 0
    for n, (key, title, subtitle, link) in enumerate(HEROES):
        await db.banners.insert_one({
            "id": f"demo-{key}", "title": title, "subtitle": subtitle,
            "image": await upload(f"banners/{key}.webp"), "mobile_image": await upload(f"banners/{key}-m.webp"),
            "video_url": "", "link": link, "device": "all", "position": "home", "sort_order": n,
            "is_active": True, "start_date": None, "end_date": None, "created_at": now.isoformat(), **tag,
        })
        banners += 1
    for n, (key, title, link) in enumerate(SMALL + [WIDE]):
        await db.banners.insert_one({
            "id": f"demo-{key}", "title": title, "subtitle": "",
            "image": await upload(f"banners/{key}.webp"), "mobile_image": "", "video_url": "",
            "link": link, "device": "all", "position": "home_wide" if key.startswith("wide") else "home_small",
            "sort_order": n, "is_active": True, "start_date": None, "end_date": None,
            "created_at": now.isoformat(), **tag,
        })
        banners += 1
    # image_url/link_url eş alanları (banners.py ile aynı şema)
    for b in await db.banners.find({"seed_source": DEMO_TAG}, {"_id": 0, "id": 1, "image": 1, "link": 1}).to_list(50):
        await db.banners.update_one({"id": b["id"]}, {"$set": {"image_url": b["image"], "link_url": b["link"]}})

    filled = await _fill_blocks(db, upload)
    return {"created_products": len(created), "created_sets": len(sets_created), "skipped": skipped,
            "banners": banners, "blocks_filled": filled, "replaced": removed, "version": DEMO_TAG}


def _canonical_specs(raw: dict):
    """Demo teknik özelliklerini ekipman şablonunun kanonik `specs` alanlarına çevirir
    (product_specs.normalize_specs; ör. kapasite_ton → lifting_capacity_kg). Modül yoksa ham değer."""
    try:
        import product_specs as _psp
        return _psp.normalize_specs(raw, _psp.default_config())
    except Exception:  # noqa: BLE001
        return raw, []


async def _ensure_set_category(db) -> None:
    """Demo setleri "Ürün Setleri" kategorisine yazılır; kategori yoksa (eski kurulum / panelden
    silinmiş) demo yüklemesi açıkça istendiği için ağaçtaki tanımıyla oluşturulur."""
    from product_sets import SET_CATEGORY_SLUG
    if await db.categories.find_one({"slug": SET_CATEGORY_SLUG}, {"_id": 1}):
        return
    from seed_categories import load_tree, seed_categories
    node = next((n for n in load_tree() if n["slug"] == SET_CATEGORY_SLUG), None)
    if node:
        await seed_categories(db, [{**node, "parent": None}])


async def _load_sets(db, create_product, cats, by_key, upload, tag, now) -> list:
    from product_sets import SET_CATEGORY_SLUG, refresh_set
    set_cat = cats.get(SET_CATEGORY_SLUG)
    out = []
    for n, st in enumerate(SETS):
        items = []
        for key, qty, vname in st["items"]:
            pid = by_key.get(key)
            if not pid:
                continue
            row = {"product_id": pid, "quantity": qty}
            if vname:
                prod = await db.products.find_one({"id": pid}, {"_id": 0, "variants": 1}) or {}
                v = next((v for v in prod.get("variants") or [] if v.get("size") == vname), None)
                if v and v.get("id"):
                    row["variant_id"] = v["id"]
            items.append(row)
        if len(items) < 2:
            continue
        names = []
        for it in items:
            p = await db.products.find_one({"id": it["product_id"]}, {"_id": 0, "name": 1})
            names.append(f"{it['quantity']} × {p['name']}" if it["quantity"] > 1 else p["name"])
        desc = (f"<p>{st['intro']}</p><h3>Set İçeriği</h3><ul>" + "".join(f"<li>{x}</li>" for x in names)
                + f"</ul><p><strong>Set avantajı:</strong> tüm ürünler birlikte alındığında %{st['pct']} set indirimi. "
                  "Stokta olmayan bir ürün sepette aynı kategoriden başka bir ürünle değiştirilebilir; "
                  "set eksik kalırsa indirim uygulanmaz.</p>"
                  "<p><em>Bu set demo içeriktir; gerçek ürünler eklendiğinde panelden kaldırılabilir.</em></p>")
        images = [await upload(f"products/{st['key']}-{k}.webp") for k in (1, 2)]
        cat_ids = [set_cat["id"]] if set_cat else []
        res = await create_product({
            "name": st["name"], "brand": "GarajTek", "manufacturer": "GarajTek", "price": 1.0, "stock": 0,
            "categories": cat_ids, "category_id": cat_ids[0] if cat_ids else "",
            "category_name": set_cat["name"] if set_cat else "", "images": images, "description": desc,
            "short_description": st["intro"], "is_active": True, "is_featured": st["featured"], "vat_rate": 20,
            "stock_code": f"GT-SET-{n + 1:02d}",
        })
        sid = res.get("id")
        await db.products.update_one({"id": sid}, {"$set": {
            **tag, "product_type": "set", "set_items": items, "set_discount_pct": float(st["pct"]),
            "meta_title": f"{st['name']} | GarajTek", "meta_description": st["intro"][:155],
            "is_new": True, "created_at": (now - timedelta(minutes=n)).isoformat(), "sold_count": 0}})
        doc = await db.products.find_one({"id": sid}, {"_id": 0})
        await refresh_set(db, doc)
        out.append(sid)
    return out


def _img(url, w, h, alt=""):
    return {"url": url, "alt": alt, "w": w, "h": h}


def _link(url):
    return {"kind": "url", "url": url, "new_tab": False}


async def _fill_blocks(db, upload) -> int:
    """Sayfa Tasarımı'ndaki ana sayfa bloklarının BOŞ görsel alanlarını demo görselleriyle doldurur
    (dolu alanlara dokunmaz). Yayın belgesi (ve varsa taslak) güncellenir; v2 alan yolları:
    hero_slider.slides[].background, ads_block.items[].image, full_banner.image, brands_carousel.brands[]."""
    from pageblocks import assign_item_ids, all_fields, get_schema
    n = 0
    cache: dict = {}

    async def up(rel):
        if rel not in cache:
            cache[rel] = await upload(rel)
        return cache[rel]

    for doc in await _layout_docs(db):
        changed = False
        for blk in doc.get("blocks") or []:
            st = blk.setdefault("settings", {})
            t = blk.get("type")
            if t == "hero_slider" and not any((x or {}).get("background") for x in st.get("slides") or []):
                slides = []
                for key, title, subtitle, link in HEROES:
                    bg = _img(await up(f"banners/{key}.webp"), 1920, 422, title)
                    bg["mobile_url"] = await up(f"banners/{key}-m.webp")
                    slides.append({"background": bg, "layout": "price", "title": title, "subtitle": subtitle,
                                   "pretitle": "", "price_prefix": "", "price": "",
                                   "button": {"text": "Hemen İncele", "style": "primary", "link": _link(link)}})
                st["slides"] = slides
                st["_demo"] = True
                changed = True
            elif t == "ads_block":
                items = st.get("items") or []
                ch = False
                for i, (key, link) in enumerate(ADS):
                    if i < len(items) and isinstance(items[i], dict) and not items[i].get("image"):
                        items[i]["image"] = _img(await up(f"banners/{key}.webp"), 410, 281)
                        if not ((items[i].get("link") or {}).get("url")):
                            items[i]["link"] = _link(link)
                        ch = True
                if ch:
                    st["items"] = items
                    changed = True
            elif t == "full_banner" and not st.get("image"):
                st["image"] = _img(await up(f"banners/{WIDE[0]}.webp"), 1170, 207, WIDE[1])
                if not ((st.get("link") or {}).get("url")):
                    st["link"] = _link(WIDE[2])
                st["_demo"] = True
                changed = True
            elif t == "brands_carousel" and not st.get("brands"):
                from routes.upload import store_image_bytes
                brands = []
                for i, name in enumerate(BRANDS):
                    rel = f"brands/brand-{i + 1}.png"
                    if rel not in cache:
                        with open(os.path.join(IMG_DIR, rel), "rb") as f:
                            res = await store_image_bytes(f.read(), "image/png", "png", f"demo-brand-{i + 1}.png",
                                                          extra={"demo": True, "seed_source": DEMO_TAG})
                        cache[rel] = res["url"]
                    brands.append({"logo": _img(cache[rel], 200, 60, name), "name": name,
                                   "link": {"kind": "search", "url": f"/arama?q={name}", "new_tab": False}})
                st["brands"] = brands
                st["source"] = "manual"
                st["_demo"] = True
                changed = True
            else:
                continue
            sch = get_schema(t)
            if sch:
                assign_item_ids(all_fields(sch), st)
        if changed:
            await _save_layout(db, doc, mirror=doc["id"].endswith(":published"))
            n += 1
    return n
