"""Aras Kargo SOAP istemcisi — ağ YOK; SOAP yanıtları sahte (mock) XML ile verilir.

Kapsam: SetOrder zarfı (alan adları/limitler, COD, parça barkodları), yanıt çözümleme
(başarı / hata kodu / SOAP Fault), CancelDispatch, GetQueryJSON (QueryType=1) takip ve
durum eşlemesi, takip linki, bağlantı testi.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import aras_kargo_client as ac  # noqa: E402
from cargo_carriers import common  # noqa: E402
from cargo_carriers.common import CarrierError  # noqa: E402


def _order(**kw):
    base = dict(integration_code="W10063", receiver_name="Ayşe Yılmaz",
                receiver_address="Atatürk Mah. Çiçek Sok. No:5 D:3", receiver_phone="+90 (532) 111 22 33",
                city="istanbul", town="kadıköy", pieces=1, desi=3, kg=1.5, invoice_number="GIB2026000001",
                description="2x Tişört")
    base.update(kw)
    return ac.build_order(**base)


SETORDER_OK = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>
<SetOrderResponse xmlns="http://tempuri.org/"><SetOrderResult><OrderResultInfo>
<ResultCode>0</ResultCode><ResultMessage>Başarılı</ResultMessage><InvoiceKey>W10063</InvoiceKey>
<OrgReceiverCustId>123</OrgReceiverCustId></OrderResultInfo></SetOrderResult></SetOrderResponse>
</soap:Body></soap:Envelope>"""

SETORDER_ERR = """<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>
<SetOrderResponse xmlns="http://tempuri.org/"><SetOrderResult><OrderResultInfo>
<ResultCode>1000</ResultCode><ResultMessage></ResultMessage></OrderResultInfo></SetOrderResult>
</SetOrderResponse></soap:Body></soap:Envelope>"""

FAULT = """<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><soap:Fault>
<faultcode>soap:Server</faultcode><faultstring>Server was unable to process request.</faultstring>
</soap:Fault></soap:Body></soap:Envelope>"""


def _query_resp(payload) -> str:
    js = json.dumps(payload, ensure_ascii=False)
    return ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            '<GetQueryJSONResponse xmlns="http://tempuri.org/"><GetQueryJSONResult>'
            + js.replace("&", "&amp;").replace("<", "&lt;") +
            "</GetQueryJSONResult></GetQueryJSONResponse></s:Body></s:Envelope>")


# --------------------------------------------------------------------------- build_order
def test_build_order_normalizes_fields():
    o = _order()
    assert o["IntegrationCode"] == "W10063"
    assert o["TradingWaybillNumber"] == "W10063"
    assert o["ReceiverPhone1"] == "5321112233"           # 10 hane, rakam
    assert o["ReceiverCityName"] == "İSTANBUL"
    assert o["ReceiverTownName"] == "KADIKÖY"
    assert o["PayorTypeCode"] == "1" and o["IsWorldWide"] == "0"
    assert o["IsCod"] == "0" and o["CodAmount"] == "0"
    assert o["PieceCount"] == "1"
    assert o["PieceDetails"][0]["BarcodeNumber"] == "W1006301"
    assert o["VolumetricWeight"] == "3" and o["Weight"] == "1.5"


def test_build_order_length_limits():
    o = _order(town="Kahramankazanilcesiuzunisim", receiver_address="x" * 400, integration_code="A" * 40)
    assert len(o["ReceiverTownName"]) == 16
    assert len(o["ReceiverAddress"]) == 250
    assert len(o["IntegrationCode"]) == 32
    assert len(o["TradingWaybillNumber"]) == 16


def test_build_order_multi_piece_unique_barcodes():
    o = _order(pieces=3, desi=6, kg=3)
    codes = [d["BarcodeNumber"] for d in o["PieceDetails"]]
    assert codes == ["W1006301", "W1006302", "W1006303"]
    assert o["PieceCount"] == "3"
    assert all(d["VolumetricWeight"] == "2" and d["Weight"] == "1" for d in o["PieceDetails"])


def test_build_order_cod_forces_sender_payor():
    o = _order(is_cod=True, cod_amount=1249.9, payor_type="2", cod_collection_type="1")
    assert o["IsCod"] == "1"
    assert o["CodAmount"] == "1249.9"
    assert o["CodCollectionType"] == "1"
    assert o["CodBillingType"] == "0"
    # Doküman hata 942: alıcı ödemeli tahsilatlı gönderi yapılamaz → gönderici öder
    assert o["PayorTypeCode"] == "1"


def test_set_order_envelope_structure_and_escaping():
    xml = ac.build_set_order_envelope(_order(receiver_name="A & B <Ltd>"), username="neodyum", password="nd&2580")
    assert '<SetOrder xmlns="http://tempuri.org/"><orderInfo><Order>' in xml
    assert "<UserName>neodyum</UserName>" in xml and "<password>nd&amp;2580</password>" in xml
    assert "<ReceiverName>A &amp; B &lt;Ltd&gt;</ReceiverName>" in xml
    assert "<PieceDetails><PieceDetail>" in xml and "<BarcodeNumber>W1006301</BarcodeNumber>" in xml
    assert "<SenderAccountAddressId />" in xml
    # well-formed
    from xml.dom import minidom
    minidom.parseString(xml.encode("utf-8"))


# --------------------------------------------------------------------------- responses
def test_parse_set_order_success():
    r = ac.parse_set_order_response(SETORDER_OK)
    assert r["ok"] is True and r["code"] == "0" and r["invoice_key"] == "W10063"


def test_parse_set_order_error_code_gets_turkish_message():
    r = ac.parse_set_order_response(SETORDER_ERR)
    assert r["ok"] is False and r["code"] == "1000"
    assert "şifre" in r["message"].lower()


def test_parse_set_order_fault():
    r = ac.parse_set_order_response(FAULT)
    assert r["ok"] is False and "Server was unable" in r["message"]


def test_set_order_posts_to_test_endpoint(monkeypatch):
    seen = {}

    def fake_post(url, body, headers, timeout=25):
        seen.update(url=url, body=body, headers=headers)
        return SETORDER_OK

    monkeypatch.setattr(ac, "soap_post", fake_post)
    r = ac.set_order(_order(), username="u", password="p", env="test")
    assert r["ok"]
    assert seen["url"] == ac.SHIP_URL_TEST
    assert seen["headers"]["SOAPAction"] == '"http://tempuri.org/SetOrder"'
    ac.set_order(_order(), username="u", password="p", env="prod")
    assert seen["url"] == ac.SHIP_URL_PROD


def test_cancel_dispatch_parsing(monkeypatch):
    ok = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
          '<CancelDispatchResponse xmlns="http://tempuri.org/"><CancelDispatchResult><ResultCode>1</ResultCode>'
          '<ResultMessage>W10063 Başarılı bir şekilde silindi.</ResultMessage></CancelDispatchResult>'
          '</CancelDispatchResponse></soap:Body></soap:Envelope>')
    monkeypatch.setattr(ac, "soap_post", lambda *a, **k: ok)
    r = ac.cancel_dispatch(username="u", password="p", integration_code="W10063")
    assert r["ok"] and "silindi" in r["message"]
    bad = ok.replace("<ResultCode>1</ResultCode>", "<ResultCode>999</ResultCode>").replace(
        "W10063 Başarılı bir şekilde silindi.", "")
    assert ac.parse_cancel_response(bad) == {"ok": False, "code": "999",
                                             "message": "İrsaliyesi kesilmiş sipariş iptal edilemez"}
    env = ac.build_cancel_envelope(username="u", password="p", integration_code="W1")
    assert "<integrationCode>W1</integrationCode>" in env and "<CancelDispatch" in env


# --------------------------------------------------------------------------- tracking
def test_query_envelope_double_escapes_login_xml():
    env = ac.build_query_envelope(username="u&1", password="p", customer_code="123", query_type=1,
                                  params={"IntegrationCode": "W10063"})
    assert "&lt;LoginInfo&gt;&lt;UserName&gt;u&amp;amp;1&lt;/UserName&gt;" in env
    assert "&lt;QueryType&gt;1&lt;/QueryType&gt;&lt;IntegrationCode&gt;W10063" in env


@pytest.mark.parametrize("code,expected", [
    ("1", common.ST_ACCEPTED), ("2", common.ST_IN_TRANSIT), ("3", common.ST_IN_TRANSIT),
    ("4", common.ST_OUT_FOR_DELIVERY), ("6", common.ST_DELIVERED), ("7", common.ST_IN_TRANSIT),
])
def test_status_mapping(code, expected):
    assert ac.map_status({"durumkodu": code}) == expected


def test_status_mapping_return_has_priority():
    assert ac.map_status({"durumkodu": "2", "tipkodu": "3"}) == common.ST_RETURNED


def test_track_by_integration_code(monkeypatch):
    payload = {"QueryResult": {"Cargo": [{
        "MUSTERI_OZEL_KODU": "W10063", "KARGO_TAKIP_NO": "3513773163316", "DURUM_KODU": "6",
        "DURUMU": "TESLİM EDİLDİ", "TESLIM_TARIHI": "05.10.2026", "TESLIM_SAATI": "14:20",
        "TESLIM_ALAN": "AYŞE", "TIP_KODU": "1"}]}}
    seen = {}

    def fake_post(url, body, headers, timeout=25):
        seen.update(url=url, headers=headers)
        return _query_resp(payload)

    monkeypatch.setattr(ac, "soap_post", fake_post)
    r = ac.track_by_integration_code(username="u", password="p", customer_code="1932448851342",
                                     integration_code="W10063", env="prod")
    assert r["ok"] and r["found"]
    assert r["tracking_number"] == "3513773163316"
    assert r["status"] == common.ST_DELIVERED
    assert r["delivered_at"] == "05.10.2026 14:20"
    assert r["tracking_url"].endswith("code=3513773163316")
    assert seen["url"] == ac.QUERY_URL_PROD
    assert seen["headers"]["SOAPAction"].endswith('IArasCargoIntegrationService/GetQueryJSON"')


def test_track_turkish_spaced_keys_and_single_object(monkeypatch):
    payload = {"QueryResult": {"Cargo": {"MÜŞTERİ ÖZEL KODU": "W1", "KARGO TAKİP NO": "111",
                                         "DURUM KODU": "1", "DURUMU": "ÇIKIŞ ŞUBESİNDE"}}}
    monkeypatch.setattr(ac, "soap_post", lambda *a, **k: _query_resp(payload))
    r = ac.track_by_integration_code(username="u", password="p", customer_code="c", integration_code="W1")
    assert r["tracking_number"] == "111" and r["status"] == common.ST_ACCEPTED


def test_track_not_found(monkeypatch):
    monkeypatch.setattr(ac, "soap_post", lambda *a, **k: _query_resp({"QueryResult": None}))
    r = ac.track_by_integration_code(username="u", password="p", customer_code="c", integration_code="W1")
    assert r["ok"] and r["found"] is False and r["status"] == common.ST_CREATED


def test_track_plain_text_error(monkeypatch):
    raw = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><GetQueryJSONResponse '
           'xmlns="http://tempuri.org/"><GetQueryJSONResult>Kullanıcı adı veya şifre hatalı</GetQueryJSONResult>'
           '</GetQueryJSONResponse></s:Body></s:Envelope>')
    monkeypatch.setattr(ac, "soap_post", lambda *a, **k: raw)
    r = ac.track_by_integration_code(username="u", password="p", customer_code="c", integration_code="W1")
    assert r["ok"] is False and "şifre" in r["error"]


def test_connection_test_reports_network_error(monkeypatch):
    def boom(*a, **k):
        raise CarrierError("Kargo servisine bağlanılamadı: ConnectError")
    monkeypatch.setattr(ac, "soap_post", boom)
    r = ac.test_connection(username="u", password="p", customer_code="c")
    assert r["ok"] is False and "bağlanılamadı" in r["message"]


def test_connection_test_ok(monkeypatch):
    def fake(url, body, headers, timeout=25):
        if "GetQueryJSON" in headers.get("SOAPAction", ""):
            return _query_resp({"QueryResult": None})
        return ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
                '<GetOrderWithIntegrationCodeResponse xmlns="http://tempuri.org/"/></soap:Body></soap:Envelope>')
    monkeypatch.setattr(ac, "soap_post", fake)
    r = ac.test_connection(username="u", password="p", customer_code="c")
    assert r["ok"] is True and "GetQueryJSON" in r["message"]


def test_tracking_url_fallback():
    assert ac.tracking_url("") .startswith("https://www.araskargo.com.tr")


def test_tracking_url_account_link():
    url = ac.tracking_url("", account_id="3EDFB773F97707408998E37D59A98002", receiver_code="W10023")
    assert url == ("https://kargotakip.araskargo.com.tr/mainpage.aspx?"
                   "accountid=3EDFB773F97707408998E37D59A98002&alici_kod=W10023")
    # account id temizlenir; alıcı kodu kaçışlanır
    assert "alici_kod=A%26B" in ac.tracking_url("", account_id="ab<cd>", receiver_code="A&B")
    # hesap yoksa takip no ile eski link
    assert ac.tracking_url("1234567890123").endswith("code=1234567890123")
