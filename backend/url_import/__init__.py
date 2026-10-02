"""URL'den Ürün Aktar — referans mağaza sayfalarından GEÇİCİ demo ürünleri içe aktarır.

Modüller:
  fetcher   SSRF korumalı HTTP istemcisi (yalnız http/https, özel/loopback/link-local/metadata IP
            engeli, standart port, en çok 3 yönlendirme ve her adımda yeniden denetim, 5 MB HTML
            sınırı, çerez saklanmaz, host başına 1 istek/sn)
  parser    ürün sayfası (JSON-LD → microdata → OpenGraph → platform seçicileri → genel) ve
            listeleme sayfası (ürün linkleri + sayfalama) ayrıştırıcıları
  sanitize  açıklama HTML'i için izin listeli temizleyici
  specs_map Türkçe teknik özellik etiketlerini product_specs alanlarına eşler
  catmap    kırıntı + başlık anahtar kelimeleriyle garaj kategori ağacına eşleme
  job       arka plan işi, ürün yazımı (demo etiketi, noindex) ve kaldırma

Tüm kayıtlar `demo: True`, `seed_source: "url_import_v1"`, `noindex: True` taşır; Demo İçerik →
Kaldır ve araç sayfasındaki "İçe aktarılanları sil" bu kayıtları ve indirilen görselleri siler.
"""

SEED_SOURCE = "url_import_v1"
