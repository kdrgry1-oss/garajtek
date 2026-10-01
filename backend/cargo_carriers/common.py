"""
cargo_carriers/common.py — Kargo istemcilerinin (Aras / PTT) ortak yardımcıları.

  - SOAP isteği gönderme (httpx, senkron; çağıran taraf asyncio.to_thread ile çalıştırır,
    mng_kargo_client.py'deki desenle aynı)
  - XML kaçış / ad-alanından bağımsız etiket okuma
  - Telefon normalizasyonu (10 hane, başında 0 yok)
  - İl adı normalizasyonu (il_mapping.IL_CODE_TO_NAME — plaka kodu veya serbest yazım → resmî ad)
  - Türkçe büyük harf dönüşümü

Bu modül VERİTABANINA DOKUNMAZ; saf yardımcıdır → birim testleri ağ/DB olmadan çalışır.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional
from xml.sax.saxutils import escape as _xml_escape

DEFAULT_TIMEOUT = 25.0


class CarrierError(Exception):
    """Kargo firması isteği başarısız (ağ / SOAP Fault / iş kuralı hatası)."""

    def __init__(self, message: str, *, code: str = "", raw: str = ""):
        super().__init__(message)
        self.message = message
        self.code = code
        self.raw = raw


def xml_escape(value) -> str:
    """XML metin düğümü için güvenli kaçış (None → '')."""
    if value is None:
        return ""
    return _xml_escape(str(value), {'"': "&quot;", "'": "&apos;"})


def soap_post(url: str, body: str, *, headers: Dict[str, str], timeout: float = DEFAULT_TIMEOUT) -> str:
    """SOAP zarfını POST eder, yanıt gövdesini (str) döndürür.

    HTTP 500 SOAP Fault taşıyabildiği için hata fırlatılmaz — gövde döner, ayrıştırıcı
    Fault'u yakalar. Bağlantı/zaman aşımı hataları CarrierError olur."""
    import httpx

    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.post(url, content=body.encode("utf-8"), headers=headers)
    except httpx.HTTPError as e:  # bağlantı, DNS, TLS, zaman aşımı
        raise CarrierError(f"Kargo servisine bağlanılamadı: {e.__class__.__name__}: {str(e)[:200]}") from e
    text = resp.text or ""
    if resp.status_code >= 400 and "Fault" not in text:
        raise CarrierError(f"Kargo servisi HTTP {resp.status_code} döndürdü", code=str(resp.status_code), raw=text[:2000])
    return text


# --- XML okuma (namespace önekinden bağımsız; PHP entegrasyonlarındaki extract_tag ile aynı mantık) ---
def extract_tag(xml: str, tag: str) -> str:
    """İlk <(ns:)tag>…</(ns:)tag> değerini döndürür (XML varlıkları çözülür)."""
    if not xml:
        return ""
    m = re.search(
        r"<(?:[\w\-]+:)?" + re.escape(tag) + r"(?:\s[^>]*)?>(.*?)</(?:[\w\-]+:)?" + re.escape(tag) + r">",
        xml, re.S,
    )
    if not m:
        return ""
    return _xml_unescape(m.group(1)).strip()


def extract_blocks(xml: str, tag: str) -> List[str]:
    """Tüm <(ns:)tag>…</(ns:)tag> bloklarının iç XML'i."""
    if not xml:
        return []
    return re.findall(
        r"<(?:[\w\-]+:)?" + re.escape(tag) + r"(?:\s[^>]*)?>(.*?)</(?:[\w\-]+:)?" + re.escape(tag) + r">",
        xml, re.S,
    )


def _xml_unescape(s: str) -> str:
    import html
    return html.unescape(s or "")


def soap_fault(xml: str) -> str:
    """SOAP 1.1 <faultstring> veya SOAP 1.2 <Reason><Text> içeriği; Fault yoksa ''."""
    if not xml or "Fault" not in xml:
        return ""
    return extract_tag(xml, "faultstring") or extract_tag(xml, "Text") or "SOAP Fault"


# --- Telefon / il / metin ---
def phone10(p) -> str:
    """Türkiye telefonunu 10 haneye indirger (+90/0 öneki atılır). Kargo servisleri
    (Aras ReceiverPhone1 String(10), PTT aliciSms Numeric(10)) bu biçimi ister."""
    digits = re.sub(r"\D", "", str(p or ""))
    if digits.startswith("90") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits[-10:] if len(digits) > 10 else digits


def tr_upper(s) -> str:
    """Türkçe kurallarıyla büyük harf (i→İ, ı→I)."""
    return str(s or "").replace("i", "İ").replace("ı", "I").upper()


def ascii_fold(s) -> str:
    """Karşılaştırma anahtarı: küçük harf, Türkçe/aksan işaretleri atılmış, boşluksuz."""
    t = str(s or "").replace("İ", "i").replace("I", "ı").lower()
    t = t.replace("ı", "i")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", t)


_IL_BY_FOLD: Optional[Dict[str, str]] = None
_IL_ALIASES = {"icel": "Mersin", "afyon": "Afyonkarahisar", "maras": "Kahramanmaraş",
               "urfa": "Şanlıurfa", "antep": "Gaziantep", "izmit": "Kocaeli", "adapazari": "Sakarya"}


def normalize_il(city) -> str:
    """İl adını il_mapping'deki resmî ada çevirir (plaka kodu '34' / 'istanbul' / 'İSTANBUL' →
    'İstanbul'). Tanınmazsa girdi kırpılmış haliyle döner (kargo firması kendi eşler)."""
    global _IL_BY_FOLD
    raw = str(city or "").strip()
    if not raw:
        return ""
    try:
        from il_mapping import IL_CODE_TO_NAME
    except Exception:  # pragma: no cover - modül her zaman var
        IL_CODE_TO_NAME = {}
    if raw.isdigit():
        return IL_CODE_TO_NAME.get(raw.zfill(2), raw)
    if _IL_BY_FOLD is None:
        _IL_BY_FOLD = {ascii_fold(v): v for v in IL_CODE_TO_NAME.values()}
    key = ascii_fold(raw)
    if key in _IL_BY_FOLD:
        return _IL_BY_FOLD[key]
    if key in _IL_ALIASES:
        return _IL_ALIASES[key]
    return raw


def fmt_num(v, nd: int = 2) -> str:
    """Ondalık sayı → '12.5' / '3' biçimi (gereksiz sıfırsız, nokta ayraçlı)."""
    try:
        f = round(float(v or 0), nd)
    except (TypeError, ValueError):
        f = 0.0
    s = f"{f:.{nd}f}".rstrip("0").rstrip(".")
    return s or "0"


def clip(s, n: int) -> str:
    return str(s or "").strip()[:n]


def is_cod_order(order: dict) -> bool:
    """Kapıda ödeme siparişi mi? (orders.py MNG akışıyla aynı ölçüt)."""
    pm = str(order.get("payment_method") or "").lower()
    return pm in ("cash_on_delivery", "kapida", "kapida_odeme", "cod")


# --- Ortak gönderi durum sözlüğü (taşıyıcıdan bağımsız) ---
# Senkron mantığı (service.apply_tracking) bu değerlerle sipariş durumunu çevirir.
ST_CREATED = "created"                # kayıt açıldı, kargo henüz teslim almadı
ST_ACCEPTED = "accepted"              # şube kabul / ilk okutma → "Kargoya Verildi"
ST_IN_TRANSIT = "in_transit"
ST_OUT_FOR_DELIVERY = "out_for_delivery"
ST_DELIVERED = "delivered"
ST_RETURNED = "returned"
ST_FAILED = "failed"                  # teslim edilemedi (tekrar denenecek)
ST_CANCELLED = "cancelled"
ST_UNKNOWN = "unknown"

STATUS_LABELS_TR = {
    ST_CREATED: "Kargo kaydı oluşturuldu",
    ST_ACCEPTED: "Kargo şubesi teslim aldı",
    ST_IN_TRANSIT: "Transfer sürecinde",
    ST_OUT_FOR_DELIVERY: "Dağıtımda",
    ST_DELIVERED: "Teslim edildi",
    ST_RETURNED: "İade sürecinde",
    ST_FAILED: "Teslim edilemedi",
    ST_CANCELLED: "İptal edildi",
    ST_UNKNOWN: "Bilinmiyor",
}
