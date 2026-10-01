"""PTT Kargo SOAP istemcisi — ağ YOK; SOAP yanıtları sahte XML ile verilir.

Kapsam: barkod check digit (resmî doküman örneği), aralık ayrıştırma, kabulEkle2 zarfı
(alan sırası, gram, COD → OS + odeme_sart_ucreti), yanıt çözümleme, barkodVeriSil,
gonderiSorgu hareketleri + durum eşlemesi, takip linki, bağlantı testi.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ptt_kargo_client as pc  # noqa: E402
from cargo_carriers import common  # noqa: E402
from cargo_carriers.common import CarrierError  # noqa: E402


# --------------------------------------------------------------------------- barkod
def test_check_digit_official_example():
    # PTT Veri Yükleme dokümanı 4-1: 275036569845 → toplam 124 → check digit 6
    assert pc.check_digit("275036569845") == "6"
    assert pc.make_barcode("275036569845") == "2750365698456"


def test_check_digit_zero_when_sum_multiple_of_ten():
    # 1*1 + 9*3 + 0... = 28 → 2 ; craft: "000000000019" → 1*1? positions: idx10 (1x1)=1, idx11 (3x9)=27 → 28 → 2
    assert pc.check_digit("000000000019") == "2"
    # 5*1 + 5*3 = 20 → 0
    assert pc.check_digit("000000000055") == "0"


def test_check_digit_validation_and_validity():
    with pytest.raises(ValueError):
        pc.check_digit("12345")
    assert pc.is_valid_barcode("2750365698456")
    assert not pc.is_valid_barcode("2750365698457")


def test_parse_range_accepts_12_or_13_digits():
    assert pc.parse_range("275036560000", "2750365699996") == (275036560000, 275036569999)
    assert pc.parse_range("", "1") is None
    assert pc.parse_range("275036569999", "275036560000") is None


def test_merge_ek_hizmet():
    assert pc.merge_ek_hizmet("sb", "OS", "") == "SBOS"
    assert pc.merge_ek_hizmet("SBOS", "OS") == "SBOS"


# --------------------------------------------------------------------------- kabulEkle2
def _dongu(**kw):
    base = dict(barcode="2750365698456", receiver_name="Mehmet Öz", address="Cumhuriyet Cd. 12 Çankaya Ankara",
                city="ankara", town="çankaya", phone="0532 111 22 33", email="m@example.com",
                reference="W10063", desi=2.5, kg=1.25, odeme_sekli="MH", ek_hizmet="SB")
    base.update(kw)
    return pc.build_dongu(**base)


def test_build_dongu_units_and_fields():
    d = _dongu()
    assert d["agirlik"] == "1250"                  # gram
    assert d["desi"] == "2.5"
    assert d["aliciSms"] == "5321112233"
    assert d["aliciIlAdi"] == "ANKARA" and d["aliciIlceAdi"] == "ÇANKAYA"
    assert d["ekhizmet"] == "SB"
    assert "odeme_sart_ucreti" not in d
    assert d["musteriReferansNo"] == "W10063"


def test_build_dongu_cod_adds_os_and_amount():
    d = _dongu(is_cod=True, cod_amount=899.5)
    assert d["ekhizmet"] == "SBOS"
    assert d["odeme_sart_ucreti"] == "899.50"


def test_kabul_envelope_order_and_constants():
    xml = pc.build_kabul_envelope(_dongu(is_cod=True, cod_amount=10), musteri_id="900000001", sifre="s<1",
                                  dosya_adi="W10063-2750365698456")
    for frag in ("<xsd:gonderiTip>NORMAL</xsd:gonderiTip>", "<xsd:gonderiTur>KARGO</xsd:gonderiTur>",
                 "<xsd:kullanici>PttWs</xsd:kullanici>", "<xsd:musteriId>900000001</xsd:musteriId>",
                 "<xsd:sifre>s&lt;1</xsd:sifre>", "<kab:kabulEkle2>"):
        assert frag in xml
    # Axis2 sıra kuralı: aAdres < barkodNo < ekhizmet < musteriReferansNo < odeme_sart_ucreti
    idx = [xml.index(f"<xsd:{t}>") for t in ("aAdres", "barkodNo", "ekhizmet", "musteriReferansNo", "odeme_sart_ucreti")]
    assert idx == sorted(idx)
    assert "gondericibilgi" not in xml           # gönderici bilgisi verilmedi → PTT kayıtlı bilgiyi kullanır
    from xml.dom import minidom
    minidom.parseString(xml.encode("utf-8"))


def test_kabul_envelope_sender_block_between_en_and_iade():
    sender = {"name": "Garaj Tekstil", "address": "Sanayi Sit. 1", "city": "Bursa", "district": "Osmangazi",
              "phone": "02241112233"}
    d = _dongu()
    d["en"] = "20"
    xml = pc.build_kabul_envelope(d, musteri_id="1", sifre="2", dosya_adi="x", sender=sender)
    assert xml.index("<xsd:en>") < xml.index("<xsd:gondericibilgi>") < xml.index("<xsd:musteriReferansNo>")
    assert "<xsd:gonderici_ulke_id>052</xsd:gonderici_ulke_id>" in xml
    assert "<xsd:gonderici_il_ad>BURSA</xsd:gonderici_il_ad>" in xml


KABUL_OK = """<soapenv:Envelope xmlns:soapenv="http://www.w3.org/2003/05/soap-envelope"><soapenv:Body>
<ns:kabulEkle2Response xmlns:ns="http://kabul.ptt.gov.tr"><ns:return xmlns:ax="http://kabul.ptt.gov.tr/xsd">
<ax:aciklama>BASARILI</ax:aciklama><ax:dongu><ax:barkod>2750365698456</ax:barkod>
<ax:donguAciklama>https://gonderitakip.ptt.gov.tr/Track/Verify?q=abc</ax:donguAciklama>
<ax:donguHataKodu>1</ax:donguHataKodu><ax:donguSonuc>true</ax:donguSonuc></ax:dongu>
<ax:hataKodu>1</ax:hataKodu></ns:return></ns:kabulEkle2Response></soapenv:Body></soapenv:Envelope>"""


def test_parse_kabul_success_and_url_in_dongu_aciklama():
    r = pc.parse_kabul_response(KABUL_OK)
    assert r["ok"] and r["barcode"] == "2750365698456"
    assert r["tracking_link"].startswith("https://gonderitakip.ptt.gov.tr")


def test_parse_kabul_line_error():
    bad = KABUL_OK.replace("<ax:donguHataKodu>1<", "<ax:donguHataKodu>-5<").replace(
        "https://gonderitakip.ptt.gov.tr/Track/Verify?q=abc", "Barkod daha once kullanilmis").replace(
        "<ax:hataKodu>1<", "<ax:hataKodu>-1<")
    r = pc.parse_kabul_response(bad)
    assert r["ok"] is False and r["message"] == "Barkod daha once kullanilmis"


def test_parse_kabul_fault_and_empty():
    fault = ('<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body><soap:Fault>'
             '<soap:Reason><soap:Text xml:lang="en">Unauthorized</soap:Text></soap:Reason></soap:Fault>'
             '</soap:Body></soap:Envelope>')
    assert pc.parse_kabul_response(fault) == {"ok": False, "message": "SOAP Fault: Unauthorized"}
    assert pc.parse_kabul_response("")["ok"] is False


def test_kabul_ekle2_endpoint_and_content_type(monkeypatch):
    seen = {}

    def fake(url, body, headers, timeout=25):
        seen.update(url=url, headers=headers)
        return KABUL_OK

    monkeypatch.setattr(pc, "soap_post", fake)
    r = pc.kabul_ekle2(_dongu(), musteri_id="1", sifre="2", dosya_adi="d", env="test")
    assert r["ok"] and seen["url"] == pc.KABUL_URL_TEST
    assert 'action="kabulEkle2"' in seen["headers"]["Content-Type"]
    pc.kabul_ekle2(_dongu(), musteri_id="1", sifre="2", dosya_adi="d", env="prod")
    assert seen["url"] == pc.KABUL_URL_PROD


def test_barkod_veri_sil(monkeypatch):
    ok = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
          '<ns:barkodVeriSilResponse xmlns:ns="http://kabul.ptt.gov.tr"><ns:return><ax:aciklama xmlns:ax="x">'
          'Silme islemi basarili</ax:aciklama><ax:hataKodu xmlns:ax="x">1</ax:hataKodu></ns:return>'
          '</ns:barkodVeriSilResponse></soapenv:Body></soapenv:Envelope>')
    monkeypatch.setattr(pc, "soap_post", lambda *a, **k: ok)
    r = pc.barkod_veri_sil(barcode="2750365698456", musteri_id="1", sifre="2")
    assert r["ok"] and "basarili" in r["message"]
    env = pc.build_delete_envelope(barcode="X", musteri_id="1", sifre="2")
    assert "<kab:inpDelete><xsd:barcode>X</xsd:barcode>" in env


# --------------------------------------------------------------------------- takip
def _takip(rows, barno="2750365698456", msg="ISLEM BASARILI"):
    dongu = "".join(
        f"<ax:dongu><ax:IKODU>{r[0]}</ax:IKODU><ax:IMERK>{r[1]}</ax:IMERK><ax:ISAAT>{r[2]}</ax:ISAAT>"
        f"<ax:ISLEM>{r[3]}</ax:ISLEM><ax:ITARIH>{r[4]}</ax:ITARIH><ax:siraNo>{i + 1}</ax:siraNo></ax:dongu>"
        for i, r in enumerate(rows))
    return ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
            '<ns:gonderiSorguResponse xmlns:ns="http://takip.ptt.gov.tr"><ns:return xmlns:ax="http://takip.ptt.gov.tr/xsd">'
            f"<ax:BARNO>{barno}</ax:BARNO>{dongu}<ax:sonucAciklama>{msg}</ax:sonucAciklama>"
            "<ax:sonucKodu>10</ax:sonucKodu></ns:return></ns:gonderiSorguResponse></soapenv:Body></soapenv:Envelope>")


def test_takip_delivered():
    xml = _takip([(1, "BURSA", "10:00:00", "Kabul Edildi", "01/10/2026"),
                  (77, "BURSA", "18:00:00", "Sevk Edildi", "01/10/2026"),
                  (7, "ANKARA", "09:00:00", "Dağıtıcıya Verildi", "03/10/2026"),
                  (100, "ANKARA", "11:30:00", "Teslim Edildi", "03/10/2026")])
    r = pc.parse_takip_response(xml)
    assert r["ok"] and r["found"] and r["barcode"] == "2750365698456"
    assert r["status"] == common.ST_DELIVERED
    assert r["delivered_at"] == "03/10/2026 11:30:00"
    assert [e["status"] for e in r["events"]] == [common.ST_ACCEPTED, common.ST_IN_TRANSIT,
                                                  common.ST_OUT_FOR_DELIVERY, common.ST_DELIVERED]


def test_takip_status_from_text_when_code_unknown():
    assert pc.status_from_event("", "Gönderi Dağıtıcıya Verildi") == common.ST_OUT_FOR_DELIVERY
    assert pc.status_from_event(None, "Teslim Edilemedi - Adreste Yok") == common.ST_FAILED
    assert pc.status_from_event("abc", "İade Edilecek") == common.ST_RETURNED
    assert pc.status_from_event(None, "") == common.ST_UNKNOWN


def test_takip_not_yet_processed():
    r = pc.parse_takip_response(_takip([], barno="", msg="Kayit bulunamadi"))
    assert r["ok"] and not r["found"] and r["status"] == common.ST_CREATED


def test_takip_auth_error():
    r = pc.parse_takip_response(_takip([], barno="", msg="Kullanici adi veya sifre hatali"))
    assert r["ok"] is False and r["auth_error"]


def test_gonderi_sorgu_request(monkeypatch):
    seen = {}

    def fake(url, body, headers, timeout=25):
        seen.update(url=url, body=body, headers=headers)
        return _takip([(1, "BURSA", "10:00:00", "Kabul Edildi", "01/10/2026")])

    monkeypatch.setattr(pc, "soap_post", fake)
    r = pc.gonderi_sorgu(barcode="2750365698456", musteri_id="900000001", sifre="x", env="prod")
    assert seen["url"] == pc.TAKIP_URL_PROD and seen["headers"]["SOAPAction"] == '"gonderiSorgu"'
    assert "<xsd:barkod>2750365698456</xsd:barkod><xsd:kullanici>900000001</xsd:kullanici>" in seen["body"]
    assert r["status"] == common.ST_ACCEPTED
    assert r["tracking_url"] == "https://gonderitakip.ptt.gov.tr/Track/Verify?q=2750365698456"


def test_connection_test(monkeypatch):
    monkeypatch.setattr(pc, "soap_post", lambda *a, **k: _takip([], barno="", msg="Kayit bulunamadi"))
    r = pc.test_connection(musteri_id="1", sifre="2", range_start="275036560000")
    assert r["ok"] and "yanıt verdi" in r["message"]

    def boom(*a, **k):
        raise CarrierError("Kargo servisine bağlanılamadı: ConnectTimeout")
    monkeypatch.setattr(pc, "soap_post", boom)
    assert pc.test_connection(musteri_id="1", sifre="2")["ok"] is False
