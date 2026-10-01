"""
PTT Kargo SOAP istemcisi (PttVeriYukleme + GonderiTakipV2).

Kaynak: PTT Genel Müdürlüğü "Ptt Veri Yükleme Web Servisi Kullanım Dokümanı" (2016) ve
"PTT Entegrasyon Giriş" dokümanı (anlaşma yapılan Başmüdürlükten temin edilir).

Servisler
  Veri yükleme (Axis2, ns http://kabul.ptt.gov.tr / xsd http://kabul.ptt.gov.tr/xsd):
     canlı: https://pttws.ptt.gov.tr/PttVeriYukleme/services/Sorgu
     test : https://pttws.ptt.gov.tr/PttVeriYuklemeTest/services/Sorgu
     - kabulEkle2(input{dongu[], dosyaAdi, gonderiTip=NORMAL, gonderiTur=KARGO, kullanici=PttWs,
                       musteriId, sifre})   → gönderi ön kaydı (barkodNo bizden gider)
     - barkodVeriSil(inpDelete{barcode, dosyaAdi, musteriId, sifre}) → kabul edilmemiş kaydı siler
  Gönderi takip (ns http://takip.ptt.gov.tr / xsd http://takip.ptt.gov.tr/xsd):
     canlı: https://pttws.ptt.gov.tr/GonderiTakipV2/services/Sorgu
     test : https://pttws.ptt.gov.tr/GonderiTakipV2Test/services/Sorgu
     - gonderiSorgu(input{barkod, kullanici=musteriId, sifre}) → BARNO + hareket satırları (dongu)

Barkod: PTT müşteriye 12 haneli bir barkod ARALIĞI verir; 13. hane check digit'tir
(1,3,1,3… ağırlıklı toplam, bir üst 10'un katına tamamlayan sayı). Bkz. check_digit().

Tüm fonksiyonlar SENKRONDUR (httpx) — çağıran asyncio.to_thread ile çalıştırır.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

from cargo_carriers.common import (
    CarrierError, xml_escape, soap_post, extract_tag, extract_blocks, soap_fault,
    phone10, tr_upper, clip, fmt_num, ascii_fold,
    ST_CREATED, ST_ACCEPTED, ST_IN_TRANSIT, ST_OUT_FOR_DELIVERY, ST_DELIVERED,
    ST_RETURNED, ST_FAILED, ST_CANCELLED, ST_UNKNOWN,
)

logger = logging.getLogger(__name__)

KABUL_URL_PROD = "https://pttws.ptt.gov.tr/PttVeriYukleme/services/Sorgu"
KABUL_URL_TEST = "https://pttws.ptt.gov.tr/PttVeriYuklemeTest/services/Sorgu"
TAKIP_URL_PROD = "https://pttws.ptt.gov.tr/GonderiTakipV2/services/Sorgu"
TAKIP_URL_TEST = "https://pttws.ptt.gov.tr/GonderiTakipV2Test/services/Sorgu"


def endpoints(env: str = "test", *, kabul_url: str = "", takip_url: str = "") -> Dict[str, str]:
    live = str(env or "").lower() in ("prod", "production", "live", "canli", "canlı")
    return {
        "kabul": kabul_url or (KABUL_URL_PROD if live else KABUL_URL_TEST),
        "takip": takip_url or (TAKIP_URL_PROD if live else TAKIP_URL_TEST),
        "live": live,
    }


def tracking_url(barcode: str = "") -> str:
    bc = str(barcode or "").strip()
    if not bc:
        return "https://gonderitakip.ptt.gov.tr/"
    return f"https://gonderitakip.ptt.gov.tr/Track/Verify?q={bc}"


# ---------------------------------------------------------------------------
# Barkod (13 hane = 12 haneli aralık numarası + check digit)
# ---------------------------------------------------------------------------
def check_digit(twelve: str) -> str:
    """Doküman 4-1: rakamlar soldan 1,3,1,3… ile çarpılıp toplanır; toplamı bir üstteki
    10'un katına tamamlayan sayı check digit'tir (toplam 10'un katıysa 0).
    Örnek: 275036569845 → toplam 124 → 6."""
    s = str(twelve or "").strip()
    if len(s) != 12 or not s.isdigit():
        raise ValueError("PTT barkodu check digit için 12 haneli rakam olmalı")
    total = sum(int(ch) * (1 if i % 2 == 0 else 3) for i, ch in enumerate(s))
    return str((10 - total % 10) % 10)


def make_barcode(twelve) -> str:
    s = str(twelve).zfill(12)
    return s + check_digit(s)


def is_valid_barcode(code: str) -> bool:
    c = str(code or "").strip()
    return len(c) == 13 and c.isdigit() and check_digit(c[:12]) == c[12]


def parse_range(start, end) -> Optional[tuple]:
    """Ayarlardaki barkod aralığı (12 hane; 13 hane girilmişse son hane atılır) → (int, int)."""
    def _n(v):
        d = re.sub(r"\D", "", str(v or ""))
        if len(d) == 13:
            d = d[:12]
        return int(d) if len(d) == 12 else None
    a, b = _n(start), _n(end)
    if a is None or b is None or b < a:
        return None
    return a, b


# ---------------------------------------------------------------------------
# kabulEkle2
# ---------------------------------------------------------------------------
# InputDongu2 xs:sequence sırası (Axis2 sıra dışı elemanı sessizce yok sayar/hata verir);
# gondericibilgi 'en' ile 'iadeAAdres' arasındadır.
_DONGU_PRE = ["aAdres", "aIlKodu", "aIlceKodu", "agirlik", "aliciAdi", "aliciEmail", "aliciIlAdi",
              "aliciIlceAdi", "aliciSms", "aliciTel", "barkodNo", "boy", "deger_ucreti", "desi",
              "ekhizmet", "en"]
_DONGU_POST = ["iadeAAdres", "iadeAIlKodu", "iadeAIlceKodu", "iadeAliciAdi", "iadeAliciEmail",
               "iadeAliciIlAdi", "iadeAliciIlceAdi", "iadeAliciTel", "musteriReferansNo",
               "odeme_sart_ucreti", "odemesekli", "rezerve1", "ucret", "yukseklik"]


def merge_ek_hizmet(*codes) -> str:
    """Ek hizmet kodlarını (2'şer harf) tekrarsız birleştirir: 'SB' + 'OS' → 'SBOS'."""
    seen: List[str] = []
    for c in codes:
        c = re.sub(r"[^A-Z]", "", tr_upper(c or "").replace("İ", "I"))
        for i in range(0, len(c) - 1, 2):
            part = c[i:i + 2]
            if part not in seen:
                seen.append(part)
    return "".join(seen)


def build_dongu(*, barcode: str, receiver_name: str, address: str, city: str, town: str,
                phone: str, email: str = "", reference: str = "", desi: float = 1, kg: float = 1,
                is_cod: bool = False, cod_amount: float = 0.0, odeme_sekli: str = "",
                ek_hizmet: str = "", cod_service_code: str = "OS", posta_ceki_no: str = "",
                declared_value: float = 0.0, dims: Optional[Dict] = None) -> Dict:
    """Doküman 3-2-2 alanlarına göre tek gönderi (dongu) sözlüğü."""
    gsm = phone10(phone)
    eh = merge_ek_hizmet(ek_hizmet, cod_service_code if is_cod else "",
                         "DK" if declared_value and declared_value > 0 else "")
    d = {
        "aAdres": clip(address, 255),
        "agirlik": str(max(1, int(round(float(kg or 0) * 1000)))),   # GRAM
        "aliciAdi": clip(receiver_name, 100),
        "aliciEmail": clip(email, 100),
        "aliciIlAdi": clip(tr_upper(city), 100),
        "aliciIlceAdi": clip(tr_upper(town), 100),
        "aliciSms": gsm if len(gsm) == 10 else "",
        "barkodNo": str(barcode),
        "desi": fmt_num(desi),
        "ekhizmet": eh,
        "musteriReferansNo": clip(reference, 100),
        "odemesekli": str(odeme_sekli or "").upper(),
        "rezerve1": re.sub(r"\D", "", str(posta_ceki_no or ""))[:8],
    }
    if is_cod:
        d["odeme_sart_ucreti"] = f"{float(cod_amount or 0):.2f}"
    if declared_value and declared_value > 0:
        d["deger_ucreti"] = f"{float(declared_value):.2f}"
    for k_src, k_dst in (("length", "boy"), ("width", "en"), ("height", "yukseklik")):
        v = (dims or {}).get(k_src)
        if v:
            d[k_dst] = str(int(round(float(v))))
    return d


def build_sender_xml(sender: Optional[Dict]) -> str:
    """gondericibilgi (opsiyonel). Ad/adres/il/ilçe eksikse HİÇ gönderilmez → PTT sistemde kayıtlı
    müşteri bilgisini gönderici kabul eder (doküman: 'Gönderici Bilgi … Hayır')."""
    s = sender or {}
    name = str(s.get("name") or "").strip()
    if not (name and s.get("address") and s.get("city") and s.get("district")):
        return ""
    ad, _, soyad = name.partition(" ")
    tel = phone10(s.get("phone"))
    e = xml_escape
    return (
        "<xsd:gondericibilgi>"
        f"<xsd:gonderici_adi>{e(clip(ad, 50))}</xsd:gonderici_adi>"
        f"<xsd:gonderici_adresi>{e(clip(s.get('address'), 255))}</xsd:gonderici_adresi>"
        + (f"<xsd:gonderici_email>{e(s.get('email'))}</xsd:gonderici_email>" if s.get("email") else "")
        + f"<xsd:gonderici_il_ad>{e(tr_upper(s.get('city')))}</xsd:gonderici_il_ad>"
        f"<xsd:gonderici_ilce_ad>{e(tr_upper(s.get('district')))}</xsd:gonderici_ilce_ad>"
        + (f"<xsd:gonderici_posta_kodu>{e(s.get('postal_code'))}</xsd:gonderici_posta_kodu>" if s.get("postal_code") else "")
        + (f"<xsd:gonderici_sms>{e(tel)}</xsd:gonderici_sms>" if tel else "")
        + f"<xsd:gonderici_soyadi>{e(clip(soyad or ad, 50))}</xsd:gonderici_soyadi>"
        + (f"<xsd:gonderici_telefonu>{e(tel)}</xsd:gonderici_telefonu>" if tel else "")
        + "<xsd:gonderici_ulke_id>052</xsd:gonderici_ulke_id>"
        "</xsd:gondericibilgi>"
    )


def build_kabul_envelope(dongu: Dict, *, musteri_id: str, sifre: str, dosya_adi: str,
                         sender: Optional[Dict] = None) -> str:
    def emit(keys):
        return "".join(f"<xsd:{k}>{xml_escape(dongu[k])}</xsd:{k}>"
                       for k in keys if dongu.get(k) not in (None, ""))
    inner = emit(_DONGU_PRE) + build_sender_xml(sender) + emit(_DONGU_POST)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" '
        'xmlns:kab="http://kabul.ptt.gov.tr" xmlns:xsd="http://kabul.ptt.gov.tr/xsd">'
        "<soap:Header/><soap:Body><kab:kabulEkle2><kab:input>"
        f"<xsd:dongu>{inner}</xsd:dongu>"
        f"<xsd:dosyaAdi>{xml_escape(clip(dosya_adi, 50))}</xsd:dosyaAdi>"
        "<xsd:gonderiTip>NORMAL</xsd:gonderiTip>"
        "<xsd:gonderiTur>KARGO</xsd:gonderiTur>"
        "<xsd:kullanici>PttWs</xsd:kullanici>"
        f"<xsd:musteriId>{xml_escape(musteri_id)}</xsd:musteriId>"
        f"<xsd:sifre>{xml_escape(sifre)}</xsd:sifre>"
        "</kab:input></kab:kabulEkle2></soap:Body></soap:Envelope>"
    )


def parse_kabul_response(xml: str) -> Dict:
    """Output2: hataKodu (1 = başarılı), aciklama, dongu{donguHataKodu, donguAciklama, barkod,
    Barkod_quid}. Pratikte takip linki donguAciklama içinde de gelebiliyor."""
    if not xml:
        return {"ok": False, "message": "PTT servisinden boş yanıt"}
    fault = soap_fault(xml)
    if fault:
        return {"ok": False, "message": f"SOAP Fault: {fault}"}
    hk = extract_tag(xml, "hataKodu")
    aciklama = extract_tag(xml, "aciklama")
    dhk = extract_tag(xml, "donguHataKodu")
    dacik = extract_tag(xml, "donguAciklama")
    barkod = extract_tag(xml, "barkod")
    quid = extract_tag(xml, "Barkod_quid") or extract_tag(xml, "barkod_quid")
    if not quid and re.match(r"^https?://", dacik or "", re.I):
        quid = dacik
    ok = hk == "1" and dhk in ("", "1")
    if ok:
        return {"ok": True, "barcode": barkod, "tracking_link": quid, "message": aciklama or "Gönderi kaydedildi"}
    detail = dacik if (dacik and not re.match(r"^https?://", dacik, re.I)) else aciklama
    return {"ok": False, "code": hk, "line_code": dhk,
            "message": detail or f"PTT hataKodu={hk or '?'} donguHataKodu={dhk or '-'}"}


def kabul_ekle2(dongu: Dict, *, musteri_id: str, sifre: str, dosya_adi: str, env: str = "test",
                sender: Optional[Dict] = None, kabul_url: str = "") -> Dict:
    url = endpoints(env, kabul_url=kabul_url)["kabul"]
    body = build_kabul_envelope(dongu, musteri_id=musteri_id, sifre=sifre, dosya_adi=dosya_adi, sender=sender)
    raw = soap_post(url, body, headers={"Content-Type": 'application/soap+xml; charset=utf-8; action="kabulEkle2"'})
    res = parse_kabul_response(raw)
    res["raw"] = raw[:2000]
    return res


# ---------------------------------------------------------------------------
# barkodVeriSil (kabul edilmemiş gönderiyi siler)
# ---------------------------------------------------------------------------
def build_delete_envelope(*, barcode: str, musteri_id: str, sifre: str, dosya_adi: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:kab="http://kabul.ptt.gov.tr" xmlns:xsd="http://kabul.ptt.gov.tr/xsd">'
        "<soapenv:Header/><soapenv:Body><kab:barkodVeriSil><kab:inpDelete>"
        f"<xsd:barcode>{xml_escape(barcode)}</xsd:barcode>"
        + (f"<xsd:dosyaAdi>{xml_escape(dosya_adi)}</xsd:dosyaAdi>" if dosya_adi else "")
        + f"<xsd:musteriId>{xml_escape(musteri_id)}</xsd:musteriId>"
        f"<xsd:sifre>{xml_escape(sifre)}</xsd:sifre>"
        "</kab:inpDelete></kab:barkodVeriSil></soapenv:Body></soapenv:Envelope>"
    )


def parse_delete_response(xml: str) -> Dict:
    fault = soap_fault(xml)
    if fault:
        return {"ok": False, "message": f"SOAP Fault: {fault}"}
    hk = extract_tag(xml, "hataKodu")
    msg = extract_tag(xml, "aciklama")
    return {"ok": hk == "1", "code": hk, "message": msg or ("Silindi" if hk == "1" else f"PTT hataKodu={hk or '?'}")}


def barkod_veri_sil(*, barcode: str, musteri_id: str, sifre: str, dosya_adi: str = "",
                    env: str = "test", kabul_url: str = "") -> Dict:
    url = endpoints(env, kabul_url=kabul_url)["kabul"]
    raw = soap_post(url, build_delete_envelope(barcode=barcode, musteri_id=musteri_id, sifre=sifre,
                                               dosya_adi=dosya_adi),
                    headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"barkodVeriSil"'})
    res = parse_delete_response(raw)
    res["raw"] = raw[:1500]
    return res


# ---------------------------------------------------------------------------
# gonderiSorgu (takip)
# ---------------------------------------------------------------------------
# Hareket kodu (IKODU) → ortak durum (PTT durum kodları listesi, üst durum grupları)
IKODU_MAP = {
    1: ST_ACCEPTED, 701: ST_ACCEPTED,                               # KABUL
    77: ST_IN_TRANSIT, 8: ST_IN_TRANSIT, 9: ST_IN_TRANSIT, 3: ST_IN_TRANSIT, 6: ST_IN_TRANSIT,
    11: ST_IN_TRANSIT, 91: ST_IN_TRANSIT, 92: ST_IN_TRANSIT, 149: ST_IN_TRANSIT,   # SEVK
    7: ST_OUT_FOR_DELIVERY,                                         # DAĞITIM
    99: ST_RETURNED, 151: ST_RETURNED, 154: ST_RETURNED, 155: ST_RETURNED,
    156: ST_RETURNED, 161: ST_RETURNED, 120: ST_RETURNED, 141: ST_RETURNED,       # İADE
    100: ST_DELIVERED, 157: ST_DELIVERED, 202: ST_DELIVERED, 252: ST_DELIVERED,
    807: ST_DELIVERED, 812: ST_DELIVERED,                           # TESLİM
    101: ST_FAILED, 109: ST_FAILED, 124: ST_FAILED, 126: ST_FAILED, 140: ST_FAILED,  # TESLİM EDİLEMEDİ
    2: ST_CANCELLED,                                                # KABUL İPTAL
}


def status_from_event(ikodu, islem: str = "") -> str:
    try:
        code = int(str(ikodu).strip())
    except (TypeError, ValueError):
        code = None
    if code is not None and code in IKODU_MAP:
        return IKODU_MAP[code]
    t = ascii_fold(islem)
    if not t:
        return ST_UNKNOWN
    if "teslimedilemedi" in t or "adresteyok" in t or "kabuledilmedi" in t:
        return ST_FAILED
    if "gondericisineteslim" in t or "iade" in t:
        return ST_RETURNED
    if "teslimedildi" in t or ("teslimalindi" in t and "kargomatik" in t):
        return ST_DELIVERED
    if "dagitic" in t or "dagitim" in t:
        return ST_OUT_FOR_DELIVERY
    if "kabul" in t or "kayitedildi" in t:
        return ST_ACCEPTED
    if "sevk" in t or "torba" in t or "zimmet" in t or "gelis" in t:
        return ST_IN_TRANSIT
    return ST_UNKNOWN


def build_takip_envelope(operation: str, params: Dict) -> str:
    inner = "".join(f"<xsd:{k}>{xml_escape(v)}</xsd:{k}>" for k, v in params.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:tak="http://takip.ptt.gov.tr" xmlns:xsd="http://takip.ptt.gov.tr/xsd">'
        "<soapenv:Header/><soapenv:Body>"
        f"<tak:{operation}><tak:input>{inner}</tak:input></tak:{operation}>"
        "</soapenv:Body></soapenv:Envelope>"
    )


def parse_takip_response(xml: str) -> Dict:
    """gonderiSorgu yanıtı → {ok, found, barcode, events[], status, status_text}.
    sonucKodu test ortamında güvenilmez (başarıda 10 dönebiliyor) → BARNO/hareket varlığı esas."""
    if not xml:
        return {"ok": False, "found": False, "message": "PTT servisinden boş yanıt"}
    fault = soap_fault(xml)
    if fault:
        return {"ok": False, "found": False, "message": f"SOAP Fault: {fault}"}
    msg = extract_tag(xml, "sonucAciklama")
    barno = extract_tag(xml, "BARNO")
    events = []
    for blk in extract_blocks(xml, "dongu"):
        ev = {k: extract_tag(blk, k) for k in ("siraNo", "ITARIH", "ISAAT", "ISLEM", "IMERK", "IKODU")}
        ev["status"] = status_from_event(ev.get("IKODU"), ev.get("ISLEM", ""))
        events.append(ev)
    found = bool(barno or events)
    status = ST_CREATED
    status_text = ""
    if events:
        last = events[-1]
        try:   # siraNo varsa en büyük sıra = son hareket
            last = max(events, key=lambda e: int(e.get("siraNo") or 0))
        except ValueError:
            pass
        status = last["status"] if last["status"] != ST_UNKNOWN else ST_IN_TRANSIT
        status_text = last.get("ISLEM") or ""
    delivered_at = ""
    if status == ST_DELIVERED:
        d = next((e for e in reversed(events) if e["status"] == ST_DELIVERED), events[-1] if events else {})
        delivered_at = f"{d.get('ITARIH', '')} {d.get('ISAAT', '')}".strip()
    low = ascii_fold(msg)
    auth_err = any(k in low for k in ("sifre", "yetki", "kullanici", "musteribulunamadi"))
    return {"ok": not auth_err, "found": found, "barcode": barno, "events": events, "status": status,
            "status_text": status_text, "delivered_at": delivered_at,
            "message": msg or ("" if found else "Barkod PTT sisteminde henüz işlem görmedi"),
            "auth_error": auth_err}


def gonderi_sorgu(*, barcode: str, musteri_id: str, sifre: str, env: str = "test",
                  takip_url: str = "") -> Dict:
    url = endpoints(env, takip_url=takip_url)["takip"]
    raw = soap_post(url, build_takip_envelope("gonderiSorgu", {"barkod": barcode, "kullanici": musteri_id,
                                                               "sifre": sifre}),
                    headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"gonderiSorgu"'})
    res = parse_takip_response(raw)
    res["raw"] = raw[:2000]
    res["tracking_url"] = tracking_url(barcode)
    return res


def test_connection(*, musteri_id: str, sifre: str, env: str = "test", range_start: str = "",
                    takip_url: str = "") -> Dict:
    """Takip servisine aralık başlangıcından üretilmiş sentetik barkodla gonderiSorgu atar.
    'Barkod bulunamadı' yanıtı kimlik bilgilerinin geçerli olduğunu gösterir; SOAP Fault veya
    şifre/yetki mesajı başarısızdır."""
    rng = parse_range(range_start, range_start)
    bc = make_barcode(rng[0]) if rng else "0000000000000"
    try:
        r = gonderi_sorgu(barcode=bc, musteri_id=musteri_id, sifre=sifre, env=env, takip_url=takip_url)
    except CarrierError as e:
        return {"ok": False, "message": e.message}
    if not r.get("ok"):
        return {"ok": False, "message": r.get("message") or "PTT isteği reddetti"}
    note = "" if rng else " (Barkod aralığı girilmedi — gönderi oluşturmak için zorunlu)"
    return {"ok": True, "message": f"PTT takip servisi yanıt verdi: {r.get('message') or 'OK'}{note}"}
