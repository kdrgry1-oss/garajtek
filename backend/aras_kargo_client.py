"""
Aras Kargo SOAP istemcisi (Sevkiyat Entegrasyonu + Müşteri Bilgi Sorgulama Servisleri).

Kaynak: Aras Kargo resmî dokümanları
  - "ARAS KARGO SEVKİYAT ENTEGRASYONU WEB SERVİS DÖKÜMANI" (SetOrder / GetOrder /
    GetOrderWithIntegrationCode / CancelDispatch)
  - "Aras Kargo - Müşteri Bilgi Sorgulama Servisleri" (GetQueryJSON / GetQueryXML, QueryType)
  - "Kargo Takip Entegrasyonu" (takip linkleri)
(esasweb.araskargo.com.tr > Tanımlamalar > Entegrasyonlar > XML Servisleri'nden indirilir.)

İKİ AYRI SERVİS VE İKİ AYRI KULLANICI vardır:
  1) Sevkiyat (ASMX, SOAP 1.1, ns http://tempuri.org/):
       test : https://customerservicestest.araskargo.com.tr/arascargoservice/arascargoservice.asmx
       canlı: https://customerws.araskargo.com.tr/arascargoservice.asmx
     SetOrder ile alıcı/paket bilgisi gönderilir. KARGO TAKİP NO bu anda OLUŞMAZ; Aras şubesi
     paketi (PieceDetail.BarcodeNumber) okutup irsaliye kestiğinde oluşur.
  2) Bilgi sorgulama (WCF, SOAP 1.1):
       test : https://customerservicestest.araskargo.com.tr/ArasCargoIntegrationService.svc
       canlı: https://customerservices.araskargo.com.tr/ArasCargoCustomerIntegrationService/ArasCargoIntegrationService.svc
     GetQueryJSON(loginInfo, queryInfo) — loginInfo: <LoginInfo><UserName/><Password/><CustomerCode/></LoginInfo>
     QueryType=1 + IntegrationCode (MÖK) → KARGO TAKİP NO, DURUM KODU (1..7), TESLİM TARİHİ …
     QueryType=9 + TrackingNumber → kargo hareketleri.

Kimlik bilgileri koda gömülmez; providers_config(kind=cargo).providers.aras altında şifreli tutulur.
Tüm fonksiyonlar SENKRONDUR (httpx) — çağıran asyncio.to_thread ile çalıştırır (MNG istemcisiyle aynı).
"""
from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

from cargo_carriers.common import (
    CarrierError, xml_escape, soap_post, extract_tag, extract_blocks, soap_fault,
    phone10, tr_upper, clip, fmt_num,
    ST_CREATED, ST_ACCEPTED, ST_IN_TRANSIT, ST_OUT_FOR_DELIVERY, ST_DELIVERED,
    ST_RETURNED, ST_UNKNOWN,
)

logger = logging.getLogger(__name__)

SHIP_URL_TEST = "https://customerservicestest.araskargo.com.tr/arascargoservice/arascargoservice.asmx"
SHIP_URL_PROD = "https://customerws.araskargo.com.tr/arascargoservice.asmx"
QUERY_URL_TEST = "https://customerservicestest.araskargo.com.tr/ArasCargoIntegrationService.svc"
QUERY_URL_PROD = ("https://customerservices.araskargo.com.tr/ArasCargoCustomerIntegrationService/"
                  "ArasCargoIntegrationService.svc")
TEMPURI = "http://tempuri.org/"
# WCF BasicHttpBinding varsayılan SOAPAction biçimi (sözleşme adı IArasCargoIntegrationService)
QUERY_ACTION_PREFIX = "http://tempuri.org/IArasCargoIntegrationService/"

# Dokümandaki SetOrder geri dönüş kodları (kısaltılmış Türkçe açıklamalar)
SETORDER_ERRORS = {
    "935": "Alıcı telefonu yalnız rakamlardan oluşmalı",
    "937": "Sipariş numarası (IntegrationCode) eksik",
    "938": "Alıcı adresi eksik",
    "939": "Alıcı adı eksik",
    "940": "Şehir adı eksik",
    "941": "İlçe adı eksik",
    "942": "Alıcı ödemeli tahsilatlı kargo gönderisi yapılamaz",
    "1000": "Kullanıcı adı veya şifre yanlış",
    "1001": "Entegrasyon bilgileri güncellenemedi — müşteri temsilcinizle görüşün",
    "1002": "Aras şube bilginiz tanımlı değil — müşteri temsilcinizle görüşün",
    "60020": "İrsaliyesi kesilmiş gönderi güncellenemez",
    "70020": "Toplam parça sayısı ile gönderilen parça sayısı eşit değil",
    "70022": "Parça barkod bilgisi eksik",
    "70027": "Bu barkod daha önce gönderilmiş",
    "70029": "İrsaliyesi kesilmiş gönderi güncellenemez",
    "70030": "Parçaların barkod numaraları aynı olamaz",
    "70035": "Bir siparişe ait bilgiler en fazla 20 kez gönderilebilir",
}
CANCEL_RESULTS = {
    "0": "Başarılı",
    "1": "Sipariş silindi",
    "999": "İrsaliyesi kesilmiş sipariş iptal edilemez",
    "936": "Hata oluştu",
    "-1": "Kayıt bulunamadı",
    "-2": "Kullanıcı adı veya şifre hatalı",
}

# QueryType=1 DURUM KODU → ortak durum (doküman: 1 Çıkış Şubesinde, 2 Yolda, 3 Teslimat Şubesinde,
# 4 Teslimatta, 5 Parçalı Teslimat, 6 Teslim Edildi, 7 Yönlendirildi)
DURUM_KODU_MAP = {
    "1": ST_ACCEPTED,
    "2": ST_IN_TRANSIT,
    "3": ST_IN_TRANSIT,
    "4": ST_OUT_FOR_DELIVERY,
    "5": ST_IN_TRANSIT,
    "6": ST_DELIVERED,
    "7": ST_IN_TRANSIT,
}


def endpoints(env: str = "test", *, ship_url: str = "", query_url: str = "") -> Dict[str, str]:
    live = str(env or "").lower() in ("prod", "production", "live", "canli", "canlı")
    return {
        "ship": ship_url or (SHIP_URL_PROD if live else SHIP_URL_TEST),
        "query": query_url or (QUERY_URL_PROD if live else QUERY_URL_TEST),
        "live": live,
    }


def tracking_url(tracking_no: str = "") -> str:
    """Müşteri takip linki (Kargo Takip Entegrasyonu dokümanı, 13 haneli takip no ile)."""
    tn = str(tracking_no or "").strip()
    if not tn:
        return "https://www.araskargo.com.tr/tr/cargo-tracking"
    return f"https://kargotakip.araskargo.com.tr/mainpage.aspx?code={tn}"


def piece_barcode(integration_code: str, piece_no: int = 1) -> str:
    """Parça barkodu: IntegrationCode + 2 haneli parça sırası (ör. W10063 → W1006301).
    Aras şubesi bu değeri okutur; her parça için benzersiz olmalı (hata 70027/70030)."""
    code = "".join(ch for ch in str(integration_code or "") if ch.isalnum())
    return f"{code}{int(piece_no):02d}"


# ---------------------------------------------------------------------------
# SetOrder
# ---------------------------------------------------------------------------
def build_order(*, integration_code: str, receiver_name: str, receiver_address: str,
                receiver_phone: str, city: str, town: str, pieces: int = 1, desi: float = 1,
                kg: float = 1, invoice_number: str = "", waybill_number: str = "",
                description: str = "", is_cod: bool = False, cod_amount: float = 0.0,
                cod_collection_type: str = "0", payor_type: str = "1",
                receiver_gsm: str = "", sender_account_address_id: str = "") -> Dict:
    """Siparişten Aras 'Order' nesnesini (doküman alan adları/limitleriyle) üretir."""
    pieces = max(1, int(pieces or 1))
    per_desi = (float(desi or 0) / pieces) if pieces else float(desi or 0)
    per_kg = (float(kg or 0) / pieces) if pieces else float(kg or 0)
    details = [{
        "BarcodeNumber": piece_barcode(integration_code, i + 1),
        "VolumetricWeight": fmt_num(per_desi),
        "Weight": fmt_num(per_kg),
        "ProductNumber": "",
        "Description": clip(description, 64),
    } for i in range(pieces)]
    phone = phone10(receiver_phone)
    gsm = phone10(receiver_gsm) if receiver_gsm else ""
    return {
        "TradingWaybillNumber": clip(waybill_number or integration_code, 16),
        "InvoiceNumber": clip(invoice_number, 20),
        "IntegrationCode": clip(integration_code, 32),
        "ReceiverName": clip(receiver_name, 100),
        "ReceiverAddress": clip(receiver_address, 250),
        "ReceiverPhone1": phone,
        "ReceiverPhone3": gsm or (phone if phone.startswith("5") else ""),
        "ReceiverCityName": clip(tr_upper(city), 40),
        "ReceiverTownName": clip(tr_upper(town), 16),
        "VolumetricWeight": fmt_num(desi, 3),
        "Weight": fmt_num(kg, 3),
        "PieceCount": str(pieces),
        "Description": clip(description, 255),
        # Doküman: 942 = "Alıcı ödemeli tahsilatlı kargo yapılamaz" → COD'da ücret göndericide (1)
        "PayorTypeCode": "1" if is_cod else (str(payor_type) if str(payor_type) in ("1", "2") else "1"),
        "IsWorldWide": "0",
        "IsCod": "1" if is_cod else "0",
        "CodAmount": fmt_num(cod_amount) if is_cod else "0",
        "CodCollectionType": (str(cod_collection_type) if str(cod_collection_type) in ("0", "1") else "0") if is_cod else "0",
        "CodBillingType": "0",                       # doküman: sabit "0"
        "PieceDetails": details,
        "SenderAccountAddressId": str(sender_account_address_id or ""),
    }


_ORDER_FIELD_ORDER = [
    "TradingWaybillNumber", "InvoiceNumber", "ReceiverName", "ReceiverAddress", "ReceiverPhone1",
    "ReceiverPhone3", "ReceiverCityName", "ReceiverTownName", "VolumetricWeight", "Weight",
    "PieceCount", "IntegrationCode", "Description", "PayorTypeCode", "IsWorldWide", "IsCod",
    "CodAmount", "CodCollectionType", "CodBillingType",
]


def build_set_order_envelope(order: Dict, *, username: str, password: str) -> str:
    """SetOrder SOAP 1.1 zarfı (dokümandaki örnek XML yapısı)."""
    u, p = xml_escape(username), xml_escape(password)
    parts = [f"<UserName>{u}</UserName>", f"<Password>{p}</Password>"]
    for k in _ORDER_FIELD_ORDER:
        v = order.get(k)
        if v in (None, ""):
            continue
        parts.append(f"<{k}>{xml_escape(v)}</{k}>")
    pieces_xml = "".join(
        "<PieceDetail>"
        f"<VolumetricWeight>{xml_escape(d.get('VolumetricWeight'))}</VolumetricWeight>"
        f"<Weight>{xml_escape(d.get('Weight'))}</Weight>"
        f"<BarcodeNumber>{xml_escape(d.get('BarcodeNumber'))}</BarcodeNumber>"
        f"<ProductNumber>{xml_escape(d.get('ProductNumber'))}</ProductNumber>"
        f"<Description>{xml_escape(d.get('Description'))}</Description>"
        "</PieceDetail>"
        for d in (order.get("PieceDetails") or [])
    )
    parts.append(f"<PieceDetails>{pieces_xml}</PieceDetails>")
    sa = order.get("SenderAccountAddressId")
    parts.append(f"<SenderAccountAddressId>{xml_escape(sa)}</SenderAccountAddressId>" if sa else "<SenderAccountAddressId />")
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        '<soap:Body><SetOrder xmlns="http://tempuri.org/"><orderInfo><Order>'
        + "".join(parts) +
        f"</Order></orderInfo><userName>{u}</userName><password>{p}</password></SetOrder>"
        "</soap:Body></soap:Envelope>"
    )


def parse_set_order_response(xml: str) -> Dict:
    """SetOrderResult/OrderResultInfo → {ok, code, message, invoice_key}. ResultCode 0 = başarılı."""
    fault = soap_fault(xml)
    if fault:
        return {"ok": False, "code": "fault", "message": f"SOAP Fault: {fault}", "invoice_key": ""}
    block = (extract_blocks(xml, "OrderResultInfo") or [xml])[0]
    code = extract_tag(block, "ResultCode")
    msg = extract_tag(block, "ResultMessage")
    if code == "":
        return {"ok": False, "code": "parse", "message": "Aras SetOrder yanıtı çözümlenemedi", "invoice_key": ""}
    ok = code == "0"
    if not ok and not msg:
        msg = SETORDER_ERRORS.get(code, f"Aras hata kodu {code}")
    elif not ok and code in SETORDER_ERRORS and SETORDER_ERRORS[code] not in msg:
        msg = f"{msg} ({SETORDER_ERRORS[code]})"
    return {"ok": ok, "code": code, "message": msg or "Başarılı",
            "invoice_key": extract_tag(block, "InvoiceKey"),
            "org_receiver_cust_id": extract_tag(block, "OrgReceiverCustId")}


def set_order(order: Dict, *, username: str, password: str, env: str = "test", ship_url: str = "") -> Dict:
    url = endpoints(env, ship_url=ship_url)["ship"]
    body = build_set_order_envelope(order, username=username, password=password)
    raw = soap_post(url, body, headers={"Content-Type": "text/xml; charset=utf-8",
                                        "SOAPAction": '"http://tempuri.org/SetOrder"'})
    res = parse_set_order_response(raw)
    res["raw"] = raw[:2000]
    return res


# ---------------------------------------------------------------------------
# CancelDispatch / GetOrderWithIntegrationCode
# ---------------------------------------------------------------------------
def _ship_op_envelope(op: str, *, username: str, password: str, integration_code: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{op} xmlns="http://tempuri.org/">'
        f"<userName>{xml_escape(username)}</userName><password>{xml_escape(password)}</password>"
        f"<integrationCode>{xml_escape(integration_code)}</integrationCode>"
        f"</{op}></soap:Body></soap:Envelope>"
    )


def build_cancel_envelope(*, username: str, password: str, integration_code: str) -> str:
    return _ship_op_envelope("CancelDispatch", username=username, password=password,
                             integration_code=integration_code)


def parse_cancel_response(xml: str) -> Dict:
    """CancelDispatchResult → ok: ResultCode 0 veya 1 ('… başarılı bir şekilde silindi')."""
    fault = soap_fault(xml)
    if fault:
        return {"ok": False, "code": "fault", "message": f"SOAP Fault: {fault}"}
    block = (extract_blocks(xml, "CancelDispatchResult") or [xml])[0]
    code = extract_tag(block, "ResultCode")
    msg = extract_tag(block, "ResultMessage")
    if code == "":
        # Bazı sürümler sonucu düz metin döndürür
        code = (block or "").strip() if (block or "").strip().lstrip("-").isdigit() else ""
    ok = code in ("0", "1")
    return {"ok": ok, "code": code, "message": msg or CANCEL_RESULTS.get(code, f"Aras sonuç kodu {code or '?'}")}


def cancel_dispatch(*, username: str, password: str, integration_code: str, env: str = "test",
                    ship_url: str = "") -> Dict:
    url = endpoints(env, ship_url=ship_url)["ship"]
    raw = soap_post(url, build_cancel_envelope(username=username, password=password,
                                               integration_code=integration_code),
                    headers={"Content-Type": "text/xml; charset=utf-8",
                             "SOAPAction": '"http://tempuri.org/CancelDispatch"'})
    res = parse_cancel_response(raw)
    res["raw"] = raw[:1500]
    return res


def get_order_with_integration_code(*, username: str, password: str, integration_code: str,
                                    env: str = "test", ship_url: str = "") -> Dict:
    """SetOrder ile gönderilen kaydı kontrol eder (bağlantı testi için de kullanılır)."""
    url = endpoints(env, ship_url=ship_url)["ship"]
    raw = soap_post(url, _ship_op_envelope("GetOrderWithIntegrationCode", username=username,
                                           password=password, integration_code=integration_code),
                    headers={"Content-Type": "text/xml; charset=utf-8",
                             "SOAPAction": '"http://tempuri.org/GetOrderWithIntegrationCode"'})
    fault = soap_fault(raw)
    if fault:
        return {"ok": False, "message": f"SOAP Fault: {fault}", "found": False, "raw": raw[:1500]}
    orders = extract_blocks(raw, "Order")
    return {"ok": True, "found": bool(orders), "raw": raw[:1500],
            "message": "Kayıt bulundu" if orders else "Kayıt yok (servis yanıt verdi)"}


# ---------------------------------------------------------------------------
# Bilgi sorgulama — GetQueryJSON
# ---------------------------------------------------------------------------
def build_query_envelope(*, username: str, password: str, customer_code: str, query_type: int,
                         params: Optional[Dict] = None, method: str = "GetQueryJSON") -> str:
    login = (f"<LoginInfo><UserName>{xml_escape(username)}</UserName>"
             f"<Password>{xml_escape(password)}</Password>"
             f"<CustomerCode>{xml_escape(customer_code)}</CustomerCode></LoginInfo>")
    q = "".join(f"<{k}>{xml_escape(v)}</{k}>" for k, v in (params or {}).items())
    query = f"<QueryInfo><QueryType>{int(query_type)}</QueryType>{q}</QueryInfo>"
    # loginInfo/queryInfo string parametredir → içerideki XML bir kez daha kaçışlanır
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        f'<soap:Body><{method} xmlns="http://tempuri.org/">'
        f"<loginInfo>{xml_escape(login)}</loginInfo><queryInfo>{xml_escape(query)}</queryInfo>"
        f"</{method}></soap:Body></soap:Envelope>"
    )


def _norm(k: str) -> str:
    from cargo_carriers.common import ascii_fold
    return ascii_fold(k)


def parse_query_json_response(xml: str) -> Dict:
    """GetQueryJSONResult (JSON string) → {ok, rows:[{normalize_key: value}], message}.
    Yanıt biçimi: {"QueryResult":{"Cargo":[{...}] | {...}}}; anahtarlar 'KARGO_TAKIP_NO',
    'DURUM_KODU' veya boşluklu/Türkçe ('KARGO TAKİP NO') gelebilir → normalize edilir."""
    fault = soap_fault(xml)
    if fault:
        return {"ok": False, "rows": [], "message": f"SOAP Fault: {fault}"}
    payload = extract_tag(xml, "GetQueryJSONResult")
    if not payload:
        return {"ok": True, "rows": [], "message": "Kayıt bulunamadı"}
    try:
        data = json.loads(payload)
    except ValueError:
        # Hata mesajı düz metin olarak dönebilir (ör. yetkisiz kullanıcı)
        return {"ok": False, "rows": [], "message": payload[:300]}
    rows: List[Dict] = []

    def walk(o):
        if isinstance(o, dict):
            if any(isinstance(v, (str, int, float)) for v in o.values()) and \
                    any(_norm(k) in ("kargotakipno", "durumkodu", "musteriozelkodu", "islemtarihi") for k in o):
                rows.append({_norm(k): ("" if v is None else str(v)) for k, v in o.items()
                             if not isinstance(v, (dict, list))})
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for it in o:
                walk(it)

    walk(data)
    msg = ""
    if isinstance(data, dict) and not rows:
        msg = str(data.get("Message") or data.get("ErrorMessage") or "")
    return {"ok": True, "rows": rows, "message": msg or ("" if rows else "Kayıt bulunamadı")}


def query_json(*, username: str, password: str, customer_code: str, query_type: int,
               params: Optional[Dict] = None, env: str = "test", query_url: str = "") -> Dict:
    url = endpoints(env, query_url=query_url)["query"]
    raw = soap_post(url, build_query_envelope(username=username, password=password,
                                              customer_code=customer_code, query_type=query_type,
                                              params=params),
                    headers={"Content-Type": "text/xml; charset=utf-8",
                             "SOAPAction": f'"{QUERY_ACTION_PREFIX}GetQueryJSON"'})
    res = parse_query_json_response(raw)
    res["raw"] = raw[:2000]
    return res


def map_status(row: Dict) -> str:
    """QueryType=1 satırı → ortak durum. TİP KODU 3 (iade edildi) önceliklidir."""
    if str(row.get("tipkodu") or "").strip() == "3":
        return ST_RETURNED
    code = str(row.get("durumkodu") or "").strip()
    if code in DURUM_KODU_MAP:
        return DURUM_KODU_MAP[code]
    text = _norm(row.get("durumu") or "")
    if "teslimedildi" in text:
        return ST_DELIVERED
    if "iade" in text:
        return ST_RETURNED
    return ST_UNKNOWN


def parse_tracking_rows(rows: List[Dict], integration_code: str = "") -> Dict:
    """QueryType=1 satırlarından (ilk eşleşen) takip özeti üretir."""
    row = None
    ic = _norm(integration_code)
    for r in rows:
        if not ic or _norm(r.get("musteriozelkodu") or "") == ic:
            row = r
            break
    row = row or (rows[0] if rows else None)
    if not row:
        return {"found": False, "status": ST_CREATED, "tracking_number": "", "status_text": ""}
    tn = str(row.get("kargotakipno") or "").strip()
    status = map_status(row)
    if status == ST_UNKNOWN and tn:
        status = ST_ACCEPTED   # takip no oluştu = şube irsaliye kesti
    return {
        "found": True,
        "tracking_number": tn,
        "status": status,
        "status_code": str(row.get("durumkodu") or ""),
        "status_text": str(row.get("durumu") or ""),
        "delivered_at": " ".join(x for x in (row.get("teslimtarihi"), row.get("teslimsaati")) if x).strip(),
        "delivered_to": str(row.get("teslimalan") or ""),
        "origin_branch": str(row.get("cikissube") or ""),
        "dest_branch": str(row.get("varissube") or ""),
        "return_reason": str(row.get("iadesebebi") or ""),
        "tracking_url": tracking_url(tn),
    }


def track_by_integration_code(*, username: str, password: str, customer_code: str,
                              integration_code: str, env: str = "test", query_url: str = "") -> Dict:
    res = query_json(username=username, password=password, customer_code=customer_code,
                     query_type=1, params={"IntegrationCode": integration_code}, env=env,
                     query_url=query_url)
    if not res.get("ok"):
        return {"ok": False, "error": res.get("message") or "Aras sorgu hatası", "raw": res.get("raw")}
    out = parse_tracking_rows(res.get("rows") or [], integration_code)
    out["ok"] = True
    out["raw"] = res.get("raw")
    return out


def test_connection(*, username: str, password: str, customer_code: str = "",
                    query_username: str = "", query_password: str = "", env: str = "test",
                    ship_url: str = "", query_url: str = "") -> Dict:
    """Sevkiyat servisine GetOrderWithIntegrationCode ile, (bilgi verildiyse) sorgu servisine
    GetQueryJSON(QueryType=1) ile gerçek istek atar. Kimlik hatası/SOAP Fault → başarısız."""
    details = []
    ok = True
    try:
        r = get_order_with_integration_code(username=username, password=password,
                                            integration_code="BAGLANTI-TESTI", env=env, ship_url=ship_url)
        if r.get("ok"):
            details.append("Sevkiyat servisi (SetOrder) yanıt verdi")
        else:
            ok = False
            details.append(f"Sevkiyat servisi: {r.get('message')}")
    except CarrierError as e:
        ok = False
        details.append(f"Sevkiyat servisi: {e.message}")
    qu, qp = (query_username or username), (query_password or password)
    if customer_code:
        try:
            r2 = query_json(username=qu, password=qp, customer_code=customer_code, query_type=1,
                            params={"IntegrationCode": "BAGLANTI-TESTI"}, env=env, query_url=query_url)
            if r2.get("ok"):
                details.append("Bilgi sorgulama servisi (GetQueryJSON) yanıt verdi")
            else:
                ok = False
                details.append(f"Bilgi sorgulama: {r2.get('message')}")
        except CarrierError as e:
            ok = False
            details.append(f"Bilgi sorgulama: {e.message}")
    else:
        details.append("Müşteri kodu girilmedi → takip sorgusu (durum senkronu) çalışmaz")
    return {"ok": ok, "message": " · ".join(details)}
