"""Demo içerik paketi — gerçek ürünler eklenene kadar vitrini dolu gösterir.

Ne yükler?
  * ~36 demo ürün (garaj/oto servis kategorilerinde; Türkçe ad, marka, teknik özellik, fiyat/indirim,
    stok, bir kısmında varyant) — görseller backend/assets/demo/img/products altındaki hazır çizimler
  * 3 ana sayfa hero slaytı (+ mobil sürümleri), 4 küçük fırsat banner'ı, 1 tam genişlik banner
Her kayıt `demo: True` ve `seed_source: "garajtek_demo_v1"` ile etiketlenir; KALDIR işlemi YALNIZ
bu etiketli ürün/banner/dosyaları siler, başka hiçbir şeye dokunmaz. Yükleme idempotenttir
(önceden yüklenmişse önce eski demo kayıtları kaldırılır, sonra yeniden yüklenir).

Kullanım:
  * Panel: Ayarlar › Demo İçerik (POST/DELETE /api/admin/demo-content — yalnız süper yönetici)
  * Komut satırı: backend/seed_demo.py (bkz. dosya başı; servis DURDURULMUŞKEN çalışır)
Görseller uygulamanın kullandığı depoya yüklenir (R2 / MEDIA_DIR / veritabanı) → URL'ler
üretimde de çalışır.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

DEMO_TAG = "garajtek_demo_v1"
IMG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "demo", "img")


def _spec_html(intro: str, bullets: list[str], specs: list[tuple[str, str]]) -> str:
    rows = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in specs)
    lis = "".join(f"<li>{b}</li>" for b in bullets)
    return (f"<p>{intro}</p><h3>Öne Çıkan Özellikler</h3><ul>{lis}</ul>"
            f"<h3>Teknik Özellikler</h3><table><tbody>{rows}</tbody></table>"
            "<p><em>Bu ürün demo içeriktir; gerçek ürünler eklendiğinde panelden kaldırılabilir.</em></p>")


# (görsel anahtarı, ad, marka, kategori slug'ları (ilk = birincil), fiyat, indirimli fiyat, stok,
#  öne çıkan, özellikler, açıklama girişi, maddeler, varyantlar [(ad, stok)] | None)
P = [
    ("lift2-4t", "Grayzer 4 Ton İki Sütunlu Lift", "Grayzer", ["iki-sutunlu-liftler"], 94900, 84900, 6, True,
     [("Kaldırma Kapasitesi", "4.000 kg"), ("Kaldırma Yüksekliği", "1.900 mm"), ("Motor Gücü", "2,2 kW"), ("Kaldırma Süresi", "50 sn")],
     "Bakım ve onarım atölyeleri için tabandan kilitli, çift silindirli iki sütunlu lift.",
     ["Otomatik kol kilitleme", "Çift hidrolik silindir", "Asimetrik/simetrik kol kurulumu", "CE sertifikalı"],
     [("220V Monofaze", 3), ("380V Trifaze", 3)]),
    ("lift2-5t", "Liftmax 5 Ton Tabandan Bağlantılı İki Sütunlu Lift", "Liftmax", ["iki-sutunlu-liftler"], 118500, None, 3, False,
     [("Kaldırma Kapasitesi", "5.000 kg"), ("Kaldırma Yüksekliği", "1.950 mm"), ("Motor Gücü", "3 kW")],
     "Hafif ticari araçlar için güçlendirilmiş sütunlu, tabandan bağlantılı lift.",
     ["Uzun kol seti", "Elektromanyetik kilit", "Toz korumalı motor"], None),
    ("scissor-3t", "Grayzer 3 Ton Makaslı Lift (Zemin Üstü)", "Grayzer", ["makasli-liftler"], 126000, 109900, 4, True,
     [("Kaldırma Kapasitesi", "3.000 kg"), ("Platform Uzunluğu", "1.450 mm"), ("Minimum Yükseklik", "105 mm")],
     "Lastik ve fren servisleri için zemin üstü montajlı alçak profil makaslı lift.",
     ["Pnömatik emniyet kilidi", "Taşınabilir hidrolik ünite", "Kauçuk takozlar dahil"], None),
    ("scissor-35t", "Liftmax 3,5 Ton Ultra İnce Makaslı Lift", "Liftmax", ["makasli-liftler"], 139900, None, 2, False,
     [("Kaldırma Kapasitesi", "3.500 kg"), ("Minimum Yükseklik", "98 mm"), ("Kaldırma Yüksekliği", "1.000 mm")],
     "Alçak araçlar için 98 mm ultra ince platform tasarımı.",
     ["Senkronize çift silindir", "Rampa uzatmaları", "Gömme montaj uygun"], None),
    ("moto-lift", "Teknolift 500 kg Motosiklet Lifti", "Teknolift", ["motosiklet-liftleri"], 18900, 16450, 12, False,
     [("Kapasite", "500 kg"), ("Platform", "2.200 x 680 mm"), ("Kaldırma", "Ayak pompalı hidrolik")],
     "Motosiklet ve ATV servisleri için teker kilitli hidrolik platform.",
     ["Ön teker kelepçesi", "Çıkarılabilir arka panel", "Tekerlekli taşıma"], None),
    ("comp-100", "Airpro 100 Lt Pistonlu Hava Kompresörü 3 HP", "Airpro", ["pistonlu-kompresorler", "indirimli-urunler"], 14900, 12490, 18, True,
     [("Tank Hacmi", "100 Lt"), ("Motor Gücü", "3 HP / 2,2 kW"), ("Hava Debisi", "360 Lt/dk"), ("Maks. Basınç", "8 bar")],
     "Atölye ve servisler için yağlı, döküm silindirli pistonlu kompresör.",
     ["Termik motor koruması", "Çift çıkışlı manometre", "Döküm gövde, uzun ömür"], None),
    ("comp-200", "Airpro 200 Lt Çift Silindirli Kompresör 4 HP", "Airpro", ["pistonlu-kompresorler"], 26900, None, 7, False,
     [("Tank Hacmi", "200 Lt"), ("Motor Gücü", "4 HP"), ("Hava Debisi", "530 Lt/dk"), ("Maks. Basınç", "10 bar")],
     "Yoğun kullanım için iki kademeli, düşük devirli kompresör.",
     ["Düşük devir, sessiz çalışma", "Otomatik tahliye", "Büyük tekerlekler"], [("220V", 4), ("380V", 3)]),
    ("comp-50-silent", "Airpro 50 Lt Sessiz ve Yağsız Kompresör", "Airpro", ["sessiz-ve-yagsiz-kompresorler"], 9450, 8490, 15, True,
     [("Tank Hacmi", "50 Lt"), ("Ses Seviyesi", "59 dB"), ("Hava Debisi", "160 Lt/dk")],
     "Boya ve detay işleri için yağsız, temiz hava üreten sessiz kompresör.",
     ["59 dB sessiz çalışma", "Yağsız motor", "Hafif ve kompakt"], None),
    ("impact-12", "Torkmatik 1/2\" Havalı Somun Sökme Tabancası 1.350 Nm", "Torkmatik", ["havali-somun-sokme-makineleri", "havali-aletler"], 3250, 2790, 40, True,
     [("Lokma Girişi", "1/2\""), ("Maks. Tork", "1.350 Nm"), ("Devir", "7.000 dev/dk"), ("Ağırlık", "2,1 kg")],
     "İkiz çekiç mekanizmalı, lastik servisi için güçlü havalı tabanca.",
     ["İkiz çekiç mekanizma", "3 kademeli güç ayarı", "Kompozit gövde"], None),
    ("impact-34", "Torkmatik 3/4\" Havalı Somun Sökme 2.100 Nm", "Torkmatik", ["havali-somun-sokme-makineleri"], 5450, None, 14, False,
     [("Lokma Girişi", "3/4\""), ("Maks. Tork", "2.100 Nm"), ("Devir", "5.200 dev/dk")],
     "Kamyonet ve hafif ticari araçlar için ağır hizmet tipi tabanca.",
     ["Alüminyum gövde", "Uzun mil seçeneği", "Titreşim sönümleyici sap"], None),
    ("tire-changer", "Grayzer Otomatik Lastik Sökme Takma Makinesi 24\"", "Grayzer", ["lastik-sokme-takma-makineleri"], 64900, 58900, 5, True,
     [("Jant Aralığı", "10\" - 24\""), ("Motor", "1,1 kW"), ("Çalışma Basıncı", "8-10 bar")],
     "Binek ve hafif ticari araç lastikleri için yarı otomatik sökme takma makinesi.",
     ["Pnömatik kafa kilidi", "Lastik şişirme tabancası dahil", "Çift hızlı tabla"], [("220V", 3), ("380V", 2)]),
    ("tire-changer-pro", "Grayzer Pro Kolsuz Lastik Sökme Makinesi 26\"", "Grayzer", ["lastik-sokme-takma-makineleri"], 112000, None, 2, False,
     [("Jant Aralığı", "12\" - 26\""), ("Yardımcı Kol", "Çift"), ("Motor", "1,5 kW")],
     "Run-flat ve alçak profil lastikler için yardımcı kollu profesyonel model.",
     ["Kolsuz montaj kafası", "Çift yardımcı kol", "Jant koruyucu set"], None),
    ("balancer", "Balanstek Dijital Lastik Balans Makinesi", "Balanstek", ["lastik-balans-makineleri"], 57900, 52900, 4, True,
     [("Jant Çapı", "10\" - 24\""), ("Hassasiyet", "±1 g"), ("Ölçüm Süresi", "7 sn")],
     "Otomatik mesafe ölçümlü, ALU programlı dijital balans makinesi.",
     ["Otomatik mesafe kolu", "ALU-S programı", "Gizli ağırlık modu"], None),
    ("inflator", "Airpro Manometreli Lastik Şişirme Tabancası", "Airpro", ["lastik-sisirme-cihazlari"], 1290, 990, 85, False,
     [("Ölçüm Aralığı", "0-12 bar"), ("Hortum", "50 cm"), ("Kadran", "80 mm")],
     "Kalibre manometreli, hızlı bağlantılı lastik şişirme tabancası.",
     ["Kauçuk korumalı kadran", "Hava boşaltma valfi"], None),
    ("floor-jack-3t", "Torkmatik 3 Ton Hızlı Kaldırmalı Yer Krikosu", "Torkmatik", ["yer-krikolari", "indirimli-urunler"], 4950, 3990, 30, True,
     [("Kapasite", "3.000 kg"), ("Min. Yükseklik", "85 mm"), ("Maks. Yükseklik", "500 mm")],
     "Çift pistonlu hızlı kaldırma sistemiyle servis tipi yer krikosu.",
     ["Çift piston hızlı kaldırma", "Aşırı yük valfi", "360° döner tekerlek"], None),
    ("floor-jack-25t", "Torkmatik 2,5 Ton Alçak Profil Kriko", "Torkmatik", ["yer-krikolari"], 3150, None, 0, False,
     [("Kapasite", "2.500 kg"), ("Min. Yükseklik", "75 mm")],
     "Alçak araçlar için ince gövdeli kriko.",
     ["75 mm alçak giriş", "Kauçuk eyer"], None),
    ("trans-jack", "Liftmax 500 kg Şanzıman Krikosu", "Liftmax", ["sanziman-krikolari"], 14500, None, 6, False,
     [("Kapasite", "500 kg"), ("Kaldırma Aralığı", "1.100 - 1.950 mm")],
     "Lift altında şanzıman sökme-takma için teleskopik kriko.",
     ["Ayak pompası", "Eğim ayarlı tabla", "5 tekerlekli şasi"], None),
    ("cart-7", "Atölye Pro 7 Çekmeceli Takım Arabası", "Atölye Pro", ["takim-arabalari", "indirimli-urunler"], 12900, 10950, 9, True,
     [("Çekmece", "7 adet"), ("Taşıma", "350 kg"), ("Ölçü", "680 x 460 x 1.000 mm")],
     "Bilyalı raylı, merkezi kilitli çelik takım arabası.",
     ["Bilyalı raylar", "Merkezi kilit", "Kauçuk kaplı üst yüzey"], [("Kırmızı", 5), ("Siyah", 4)]),
    ("cart-5-blue", "Atölye Pro 5 Çekmeceli Takım Arabası Mavi", "Atölye Pro", ["takim-arabalari"], 9800, None, 11, False,
     [("Çekmece", "5 adet"), ("Taşıma", "250 kg")],
     "Kompakt servisler için 5 çekmeceli takım arabası.",
     ["Toz boya kaplama", "Frenli tekerlek"], None),
    ("workbench", "Atölye Pro Delikli Panolu Takım Tezgahı 2 m", "Atölye Pro", ["takim-tezgahlari"], 16500, 14900, 5, False,
     [("Uzunluk", "2.000 mm"), ("Tabla", "Kayın masif 40 mm"), ("Taşıma", "800 kg")],
     "Mengene montajına uygun masif tablalı, çekmeceli tezgah.",
     ["Delikli takım panosu", "4 çekmece", "Ayarlanabilir ayak"], None),
    ("socket-108", "Torkmatik 108 Parça Lokma Takımı 1/4\" - 1/2\"", "Torkmatik", ["lokma-setleri"], 3890, 3290, 50, True,
     [("Parça Sayısı", "108"), ("Lokma Girişi", "1/4\" ve 1/2\""), ("Malzeme", "Cr-V çelik")],
     "Krom vanadyum çelikten, sağlam çantalı geniş lokma takımı.",
     ["72 dişli cırcır kolu", "Derin ve kısa lokmalar", "Bits uçlar dahil"], [("Metrik", 30), ("Metrik + İnç", 20)]),
    ("socket-46", "Torkmatik 46 Parça Lokma Seti 1/4\"", "Torkmatik", ["lokma-setleri"], 1450, None, 70, False,
     [("Parça Sayısı", "46"), ("Lokma Girişi", "1/4\"")],
     "Hassas işler için kompakt lokma seti.",
     ["Cep boy çanta", "Uzatma ve kardan dahil"], None),
    ("wrench-12", "Torkmatik 12 Parça Yıldız Ağızlı Anahtar Takımı", "Torkmatik", ["anahtar-takimlari", "yildiz-iki-agiz-anahtarlar"], 1650, 1390, 60, False,
     [("Ölçüler", "8 - 19 mm"), ("Malzeme", "Cr-V"), ("Kaplama", "Saten krom")],
     "Kombine yıldız-açık ağız anahtar takımı, rulo çantalı.",
     ["15° açılı yıldız ağız", "Rulo çanta"], None),
    ("ratchet-set", "Torkmatik Cırcırlı Kol Seti 3 Parça", "Torkmatik", ["lokma-kollari-ve-circirlar", "circirli-anahtarlar"], 1250, None, 45, False,
     [("Girişler", "1/4\", 3/8\", 1/2\""), ("Diş", "72")],
     "Üç farklı girişte hızlı bırakmalı cırcır kolları.",
     ["Hızlı bırakma butonu", "Ergonomik sap"], None),
    ("drill-18v", "Voltix 18V Kömürsüz Akülü Vidalama", "Voltix", ["akulu-vidalama-makineleri"], 4390, 3790, 25, True,
     [("Voltaj", "18 V"), ("Tork", "60 Nm"), ("Akü", "2 x 2,0 Ah Li-ion")],
     "Kömürsüz motorlu, iki akülü, darbeli vidalama makinesi.",
     ["Kömürsüz motor", "LED aydınlatma", "Sert taşıma çantası"], [("Tek Akülü", 10), ("Çift Akülü", 15)]),
    ("drill-12v", "Voltix 12V Kompakt Akülü Matkap", "Voltix", ["matkaplar"], 2690, None, 20, False,
     [("Voltaj", "12 V"), ("Tork", "30 Nm")],
     "Dar alanlar için hafif ve kompakt akülü matkap.",
     ["1,1 kg ağırlık", "Hızlı şarj"], None),
    ("grinder", "Voltix 125 mm Avuç Taşlama 1.100 W", "Voltix", ["taslama-makineleri"], 2950, 2590, 18, False,
     [("Disk Çapı", "125 mm"), ("Güç", "1.100 W"), ("Devir", "11.500 dev/dk")],
     "Yumuşak kalkışlı, devir ayarlı avuç taşlama.",
     ["Yumuşak kalkış", "Devir ayarı"], None),
    ("welder-200", "Weldon 200A İnverter Gazaltı Kaynak Makinesi", "Weldon", ["kaynak-makineleri"], 7900, 6990, 10, True,
     [("Akım", "30 - 200 A"), ("Tel Çapı", "0,6 - 1,0 mm"), ("Giriş", "220 V")],
     "MIG/MAG ve elektrot kaynağı yapabilen çok fonksiyonlu inverter.",
     ["Gazlı/gazsız tel", "Dijital ekran", "Sinerjik ayar"], None),
    ("welder-160", "Weldon 160A Elektrot Kaynak Makinesi", "Weldon", ["kaynak-makineleri"], 5200, None, 8, False,
     [("Akım", "20 - 160 A"), ("Elektrot", "1,6 - 4,0 mm")],
     "Hafif, taşınabilir inverter elektrot kaynak makinesi.",
     ["Hot start / Arc force", "Taşıma askısı"], None),
    ("work-light", "Lumix 50W Şarjlı LED Çalışma Lambası", "Lumix", ["led-lambalar-ve-calisma-isiklari"], 1350, 1090, 55, False,
     [("Güç", "50 W"), ("Işık Akısı", "4.500 lm"), ("Çalışma Süresi", "6 saat")],
     "Tripodlu, şarjlı, IP65 su geçirmez atölye aydınlatması.",
     ["IP65", "3 kademeli parlaklık"], None),
    ("obd-pro", "Diagnox Pro Tablet Arıza Tespit Cihazı", "Diagnox", ["ariza-tespit-cihazlari"], 23900, 21500, 6, True,
     [("Ekran", "8\" dokunmatik"), ("Protokol", "OBD2 / CAN / J1850"), ("Dil", "Türkçe")],
     "Tüm sistem tarama, servis sıfırlama ve canlı veri destekli tablet cihaz.",
     ["30+ servis fonksiyonu", "Ücretsiz güncelleme (1 yıl)", "Bluetooth VCI"], None),
    ("obd-basic", "Diagnox OBD2 El Tipi Arıza Okuyucu", "Diagnox", ["ariza-tespit-cihazlari"], 3900, None, 30, False,
     [("Ekran", "2,8\" renkli"), ("Fonksiyon", "Arıza oku/sil, canlı veri")],
     "Motor arıza kodlarını okuyup silen el tipi cihaz.",
     ["Tak-çalıştır", "Türkçe menü"], None),
    ("battery-tester", "Diagnox Dijital Akü Test Cihazı 12V", "Diagnox", ["aku-test-ve-takviye-cihazlari"], 2590, 2290, 22, False,
     [("Voltaj", "12 V"), ("CCA Aralığı", "100 - 2.000"), ("Ekran", "LCD")],
     "Akü sağlığı, marş ve şarj sistemi testi yapan dijital cihaz.",
     ["Marş/şarj testi", "Yazdırılabilir rapor"], None),
    ("oil-drain-80", "Teknolift 80 Lt Pnömatik Yağ Boşaltma Cihazı", "Teknolift", ["yag-bosaltma-ve-degistirme-cihazlari"], 9900, 8790, 7, True,
     [("Tank", "80 Lt"), ("Huni Yüksekliği", "1.350 - 1.900 mm"), ("Boşaltma", "Pnömatik")],
     "Lift altı kullanım için teleskopik hunili, pnömatik boşaltmalı yağ toplama cihazı.",
     ["Seviye göstergesi", "Teleskopik huni", "Pnömatik boşaltma"], None),
    ("oil-drain-70", "Teknolift 70 Lt Yağ Emme Boşaltma Cihazı", "Teknolift", ["yag-bosaltma-ve-degistirme-cihazlari"], 7400, None, 9, False,
     [("Tank", "70 Lt"), ("Sonda", "6 adet")],
     "Yağ çubuğu ağzından emiş yapan vakumlu cihaz.",
     ["Ön hazne", "Vakum göstergesi"], None),
    ("bleeder", "Teknolift Fren Hava Alma Cihazı 10 Lt", "Teknolift", ["fren-hava-alma-cihazlari"], 8700, None, 5, False,
     [("Hazne", "10 Lt"), ("Basınç", "0,5 - 2 bar")],
     "Tek kişiyle fren hidroliği değişimi ve hava alma işlemi.",
     ["Ayarlanabilir basınç", "Adaptör seti dahil"], None),
]

HEROES = [
    ("hero-1", "İki Sütunlu Liftlerde Sezon Fırsatı", "4 TON GRAYZER LİFT — 84.900 ₺'DEN BAŞLAYAN FİYATLAR", "/iki-sutunlu-liftler"),
    ("hero-2", "Kompresör ve Havalı Aletler", "ATÖLYENİN GÜCÜ — %15'E VARAN İNDİRİM", "/kompresorler"),
    ("hero-3", "Lastik Servisi Ekipmanları", "SÖKME TAKMA + BALANS SETLERİNDE AVANTAJ", "/lastik-ekipmanlari"),
]
SMALL = [
    ("small-1", "Lokma takımlarında büyük fırsat", "/lokma-takimlari"),
    ("small-2", "Kompresör sezonu başladı", "/kompresorler"),
    ("small-3", "Arıza tespiti artık çok kolay", "/test-ve-ariza-tespit-cihazlari"),
    ("small-4", "Takım arabaları %15 indirimde", "/takim-arabalari-ve-tezgahlar"),
]
WIDE = ("wide-1", "Atölyenizi kazançla donatın", "/indirimli-urunler")


def _read(rel: str) -> bytes:
    with open(os.path.join(IMG_DIR, rel), "rb") as f:
        return f.read()


async def demo_status(db) -> dict:
    q = {"seed_source": DEMO_TAG}
    return {
        "products": await db.products.count_documents(q),
        "banners": await db.banners.count_documents(q),
        "files": await db.files.count_documents(q),
        "available_products": len(P),
    }


async def remove_demo(db) -> dict:
    """YALNIZ demo etiketli kayıtları siler."""
    from routes.upload import delete_stored_file

    q = {"seed_source": DEMO_TAG}
    files = await db.files.find(q, {"_id": 0, "id": 1, "r2_key": 1, "storage_path": 1}).to_list(5000)
    for rec in files:
        await delete_stored_file(rec)
    pr = await db.products.delete_many({**q, "demo": True})
    br = await db.banners.delete_many({**q, "demo": True})
    return {"removed_products": pr.deleted_count, "removed_banners": br.deleted_count, "removed_files": len(files)}


async def load_demo(db, create_product) -> dict:
    """Demo içeriği yükler. `create_product(data) -> {"id": ...}` panelin ürün oluşturma akışıdır
    (barkod/varyant id/slug/kategori ataları aynı kurallarla üretilir)."""
    from routes.upload import store_image_bytes

    removed = await remove_demo(db)  # idempotent: eski demo setini temizle
    tag = {"demo": True, "seed_source": DEMO_TAG}

    async def upload(rel: str) -> str:
        res = await store_image_bytes(_read(rel), "image/webp", "webp", f"demo-{os.path.basename(rel)}", extra=tag)
        return res["url"]

    cats = {c["slug"]: c for c in await db.categories.find({}, {"_id": 0, "id": 1, "slug": 1, "name": 1}).to_list(5000)}
    now = datetime.now(timezone.utc)
    created, skipped = [], []
    for i, (key, name, brand, cslugs, price, sale, stock, featured, specs, intro, bullets, variants) in enumerate(P):
        cat_ids = [cats[s]["id"] for s in cslugs if s in cats]
        if not cat_ids:
            skipped.append(name)
            continue
        images = [await upload(f"products/{key}-{n}.webp") for n in (1, 2, 3)]
        data = {
            "name": name,
            "brand": brand,
            "manufacturer": brand,
            "price": float(price),
            "sale_price": float(sale) if sale else None,
            "categories": cat_ids,
            "category_id": cat_ids[0],
            "category_name": cats[cslugs[0]]["name"] if cslugs[0] in cats else "",
            "images": images,
            "description": _spec_html(intro, bullets, specs),
            "short_description": intro,
            "attributes": [{"name": k, "value": v} for k, v in specs],
            "stock": stock,
            "stock_code": f"DEMO-{i + 1:03d}",
            "is_active": True,
            "is_featured": featured,
            "is_new": i % 4 == 0,
            "is_free_shipping": price >= 5000,
            "vat_rate": 20,
        }
        if variants:
            data["variants"] = [{"size": v, "stock": s} for v, s in variants]
        res = await create_product(data)
        pid = res.get("id")
        ids = res.get("product_ids") or [pid]
        await db.products.update_many(
            {"id": {"$in": ids}},
            {"$set": {**tag, "created_at": (now - timedelta(hours=i * 7)).isoformat(),
                      "sold_count": (len(P) - i) * 3 % 41}})
        created.extend(ids)

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

    return {"created_products": len(created), "skipped": skipped, "banners": banners,
            "replaced": removed}
