import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from url_import.name_fix import fix_name  # noqa: E402
from url_import.keyword_cats import match  # noqa: E402


def test_name_fixes():
    assert fix_name("2 Metre 1O Çekmece Takım Tezgahı (Dolaplı)") == "2 Metre 10 Çekmece Takım Tezgahı (Dolaplı)"
    assert fix_name("013-RC0168 Rico Gress Pompası 500 Cc") == "013-RC0168 Rico Gres Pompası 500 Cc"
    assert fix_name("4 Ton Hidrolik Üstten Baglantili Tam Otomatik Arac Lifti") == \
        "4 Ton Hidrolik Üstten Bağlantılı Tam Otomatik Araç Lifti"
    assert fix_name("RK0051 RICO TORX TORNAVİDA SETİ") == "RK0051 Rico Torx Tornavida Seti"
    assert fix_name("FK 1/2 MİNİ HAVALI SOMUN SÖKME") == "FK 1/2 Mini Havalı Somun Sökme"
    assert fix_name("İzeltaş 0340020010 Cırcır Kombine Anahtar 10 Mm") == "İzeltaş 0340020010 Cırcır Kombine Anahtar 10 mm"
    assert fix_name("DHT 500KG DİKEY ŞANZIMAN KRİKOSU") == "DHT 500 kg Dikey Şanzıman Krikosu"
    keep = "Bosch Pense Seti 3 Parça (Kargaburun, Yan Keski, Pense) 1600A02C0S"
    assert fix_name(keep) == keep
    for n in ("RK0051 RICO TORX TORNAVİDA SETİ", "SwissTron 100LT HAVALI YAĞ BOŞALTMA"):
        assert fix_name(fix_name(n)) == fix_name(n)


def test_makas_overrides():
    assert match("Rico 025-RC4614 Şarjlı Bağ Makası", has_category=True) == "elektrikli-ve-sarjli-el-aletleri"
    assert match("DHT D12006000 Makaslı Kriko 1.5 Ton", has_category=True) == "yer-krikolari"
    assert match("2 METRE 3,5 TON MEKANİK KİLİTLİ MAKASLI LİFT", has_category=True) is None
