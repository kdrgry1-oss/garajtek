"""
services/birfatura_out.py — BirFatura OutEBelgeV2 API ile DOĞRUDAN satış faturası kesimi (push).

Özel Entegrasyon (services/birfatura.py, BirFatura siparişi ÇEKER) yanında ikinci yol: admin
panelden tek sipariş için faturayı biz keseriz.

    POST {base}/api/OutEBelgeV2/GetUserPK                 {"kn": VKN/TCKN}    → alıcı PK etiketleri
    POST {base}/api/OutEBelgeV2/SendBasicInvoiceFromModel {"invoice": {...}}  → invoiceNo, pdfLink
    POST {base}/api/OutEBelgeV2/GetPDFLinkByUUID          {"uuids": [ettn], "systemType": "EFATURA"|"EARSIV"}
    POST {base}/api/OutEBelgeV2/GetNumberOfCredits        {"kn": ...}         → kalan kontör (Result: string)

Her çağrıda X-Api-Key, X-Secret-Key, X-Integration-Key başlıkları. Yanıt zarfı
{"Success": bool, "Message": str, "Code": str, "Result": ...}.

KAYNAK: BirFatura "OutEBelgeV2 API" resmî dokümanı (JSON dökümü tests/fixtures/
birfatura_outebelgev2.json). Alan adları şemadan BİREBİR alınmıştır; şemada açıklanmayan
davranışlar "VARSAYIM:" ile işaretlidir.

Tutar hesapları YENİDEN YAZILMAZ: services/birfatura.map_order() (Özel Entegrasyon için resmî
şemaya karşı test edilmiş KDV ayrımı, iskonto dağıtımı, kargo/kapıda ödeme/hediye paketi/vade
farkı) çıktısı OutEBelgeV2 `Invoice` modeline çevrilir (PascalCase → camelCase, aynı anlamlı alanlar).

Bu modül veritabanına DOKUNMAZ; ağ çağrıları OutClient içindedir (httpx, zaman aşımı, TLS
doğrulaması AÇIK, yönlendirme izlenmez). Sırlar hiçbir mesaja/loga yazılmaz.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from urllib.parse import urlsplit

from services import birfatura as bf

PROVIDER = "birfatura_outebelgev2"
API_PREFIX = "/api/OutEBelgeV2"
DEFAULT_BASE_URL = "https://uygulama.edonustur.com"   # dokümandaki baseUrl
# Dokümanda "BirFatura ortamı için" API bilgileri sayfası uygulama.birfatura.com'da. VARSAYIM:
# API uçları da aynı host altında sunulur; doküman yalnız edonustur adresini baseUrl verir.
BASE_URL_CHOICES = [
    {"value": "https://uygulama.edonustur.com", "label": "E-Dönüştür (dokümandaki varsayılan)"},
    {"value": "https://uygulama.birfatura.com", "label": "BirFatura"},
]
# Sırlar başka bir adrese gönderilemesin (SSRF / anahtar sızıntısı): yalnız bu alan adları.
ALLOWED_BASE_HOSTS = ("edonustur.com", "*.edonustur.com", "birfatura.com", "*.birfatura.com")

SYSTEM_EFATURA = "EFATURA"
SYSTEM_EARSIV = "EARSIV"
TYPE_LABEL = {SYSTEM_EFATURA: "e-fatura", SYSTEM_EARSIV: "e-arsiv"}

# Resmî şema: Invoice ve OrderDetail alanları (sıra şemadaki gibi).
INVOICE_FIELDS = (
    "orderCode", "orderDate", "invoiceDate", "invoiceExplanation", "eInvoiceId", "isDocumentNoAuto", "ettn",
    "receiverTag", "billingName", "billingAddress", "billingTown", "billingCity", "billingMobilePhone",
    "billingPhone", "billingPhone2", "taxOffice", "taxNo", "email", "shipCompany", "cargoCampaignCode",
    "shippingName", "shippingAddress", "shippingTown", "shippingCity", "shippingCountry", "shippingZipCode",
    "shippingPhone", "deliveryFeeType", "paymentType", "currency", "currencyRate",
    "totalPaidTaxExcluding", "totalPaidTaxIncluding", "productsTotalTaxExcluding", "productsTotalTaxIncluding",
    "shippingChargeTotalTaxExcluding", "shippingChargeTotalTaxIncluding",
    "installmentChargeTotalTaxExcluding", "installmentChargeTotalTaxIncluding",
    "bankTransferDiscountTotalTaxExcluding", "bankTransferDiscountTotalTaxIncluding",
    "payingAtTheDoorChargeTotalTaxExcluding", "payingAtTheDoorChargeTotalTaxIncluding",
    "discountTotalTaxExcluding", "discountTotalTaxIncluding", "orderDetails",
)
INVOICE_REQUIRED = ("invoiceDate", "ettn", "billingName", "billingAddress", "billingCity", "taxNo",
                    "totalPaidTaxExcluding", "totalPaidTaxIncluding",
                    "productsTotalTaxExcluding", "productsTotalTaxIncluding", "orderDetails")
DETAIL_FIELDS = (
    "productCode", "barcode", "productBrand", "productName", "productNote", "productQuantityType",
    "productQuantity", "vatRate", "productUnitPriceTaxExcluding", "productUnitPriceTaxIncluding",
    "discountIsPercentUnit", "discountRateUnit", "discountUnitTaxExcluding", "discountUnitTaxIncluding",
)
DETAIL_REQUIRED = ("productCode", "productName", "productQuantity", "vatRate",
                   "productUnitPriceTaxExcluding", "productUnitPriceTaxIncluding")

FIELD_LABELS = {
    "billingName": "fatura adı", "billingAddress": "fatura adresi", "billingCity": "fatura şehri",
    "taxNo": "VKN/TCKN", "orderDetails": "ürün satırı", "invoiceDate": "fatura tarihi", "ettn": "ETTN",
}

# Faturası kesilemeyecek sipariş durumları (iptal / iade / ödeme alınamadı / onay öncesi).
CANCEL_RETURN_STATUSES = {
    "cancelled", "cancel_refunded", "cancel_requested", "payment_failed",
    "return_requested", "return_in_transit", "returned", "refunded", "partial_refunded",
}
PRE_CONFIRM_STATUSES = {"pending", "awaiting_payment", "payment_notified"}
_HAVALE_PMS = {"bank_transfer", "havale", "eft", "havale_eft", "banka_havale", "havale/eft"}
_SETTLED_PAY = {"paid", "completed", "success", "succeeded", "captured"}


# ---------------------------------------------------------------------------
# Ayar doğrulama
# ---------------------------------------------------------------------------
def normalize_base_url(url) -> Optional[str]:
    """https + izinli BirFatura/E-Dönüştür host'u + yol yok → 'https://host'. Aksi None."""
    s = str(url or "").strip().rstrip("/")
    if not s:
        return None
    try:
        p = urlsplit(s)
    except Exception:
        return None
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None, 443):
        return None
    if p.path not in ("", "/") or p.query or p.fragment:
        return None
    if not bf.host_allowed(f"https://{p.hostname}/", list(ALLOWED_BASE_HOSTS)):
        return None
    return f"https://{p.hostname.lower()}"


def secret_hint(value: str) -> str:
    v = str(value or "")
    return v[-4:] if len(v) >= 8 else ""


# ---------------------------------------------------------------------------
# Uygunluk
# ---------------------------------------------------------------------------
def block_reason(order: dict) -> Optional[str]:
    """Faturası doğrudan kesilemeyecek sipariş için Türkçe sebep; uygunsa None."""
    st = str(order.get("status") or "")
    if st in CANCEL_RETURN_STATUSES:
        return f"İptal/iade sürecindeki siparişe fatura kesilemez (durum: {st})."
    if st in PRE_CONFIRM_STATUSES:
        return f"Fatura yalnız ONAYLANMIŞ siparişe kesilebilir (durum: {st}). Önce siparişi onaylayın."
    pm = str(order.get("payment_method") or "").lower()
    if pm in _HAVALE_PMS and str(order.get("payment_status") or "").lower() not in _SETTLED_PAY:
        return "Havale/EFT ödemesi onaylanmadan fatura kesilemez. Önce ödemeyi 'Ödendi' olarak işaretleyin."
    if not [it for it in (order.get("items") or []) if isinstance(it, dict)]:
        return "Siparişte ürün satırı yok."
    if bf.D(order.get("total")) <= Decimal("0.009"):
        return "Sipariş tutarı 0 (tamamı hediye çeki/puan) — fatura kesilemez."
    return None


def existing_invoice(order: dict) -> Optional[dict]:
    """Sipariş herhangi bir yoldan faturalanmışsa özet; değilse None."""
    if not (order.get("invoice_issued") or order.get("invoice_number") or order.get("invoice_pdf_url")):
        return None
    return {
        "invoice_number": order.get("invoice_number") or "",
        "invoice_pdf_url": order.get("invoice_pdf_url") or "",
        "invoice_uuid": order.get("invoice_uuid") or "",
        "invoice_type": order.get("invoice_type") or "",
        "invoice_provider": order.get("invoice_provider") or "",
        "invoice_issued_at": order.get("invoice_issued_at") or "",
    }


# ---------------------------------------------------------------------------
# Alıcı (GetUserPK)
# ---------------------------------------------------------------------------
def receiver_tax_no(mapped: dict) -> str:
    """map_order çıktısından alıcı vergi no. Şemada tek alan var (`taxNo`, "vergi kimlik no");
    VARSAYIM: bireysel/şahıs şirketi TCKN'si de `taxNo`'ya yazılır (şemada ayrı TCKN alanı yok)."""
    return str(mapped.get("TaxNo") or mapped.get("SSNTCNo") or "").strip()


def should_query_user(tax_no: str, settings: dict) -> bool:
    """GetUserPK yalnız gerçek bir VKN/TCKN için sorgulanır (varsayılan 11111111111 değil)."""
    d = re.sub(r"\D", "", tax_no or "")
    return len(d) in (10, 11) and d != str(settings.get("default_tckn") or "11111111111") and len(set(d)) > 1


def pick_receiver(results) -> tuple:
    """GetUserPK `Result` → (e-Fatura mükellefi mi, alıcı etiketi | None).

    Şema: identifier, title, type2, name, pkGbTurKod, firstCreationTime. VARSAYIM: etiket (alias,
    'urn:mail:...') şemada adı açıkça verilmediği için 'urn:mail:' ile başlayan ilk alan değeri
    alınır (öncelik: name, identifier, title, type2); pkGbTurKod 'GB' (gönderici kutusu) olan
    kayıtlar elenir. Liste boş değilse alıcı e-Fatura mükellefidir."""
    rows = [r for r in (results or []) if isinstance(r, dict)]
    rows = [r for r in rows if not str(r.get("pkGbTurKod") or "").strip().upper().startswith("GB")]
    if not rows:
        return False, None
    for r in rows:
        for k in ("name", "identifier", "title", "type2"):
            v = r.get(k)
            if isinstance(v, str) and v.strip().lower().startswith("urn:mail:"):
                return True, v.strip()
    return True, None


# ---------------------------------------------------------------------------
# Fatura modeli
# ---------------------------------------------------------------------------
def _lc(key: str) -> str:
    return key[:1].lower() + key[1:]


def _tr_date(value=None) -> str:
    dt = bf.parse_any_dt(value) if value is not None else datetime.now(timezone.utc)
    if not dt:
        return ""
    return dt.astimezone(bf.TR_TZ).date().isoformat()


def build_invoice(order: dict, settings: dict, *, ettn: str, receiver_tag: Optional[str] = None,
                  vat_map: Optional[dict] = None, default_vat_rate=None, product_meta: Optional[dict] = None,
                  invoice_date: Optional[str] = None) -> dict:
    """Sipariş → SendBasicInvoiceFromModel `invoice` nesnesi (yalnız şemadaki alanlar)."""
    m = bf.map_order(order, settings, vat_map=vat_map, default_vat_rate=default_vat_rate,
                     product_meta=product_meta, bf_order_id=0)
    inv: dict = {}
    for k, v in m.items():
        lk = _lc(k)
        if lk in INVOICE_FIELDS and lk not in ("orderDate", "orderDetails") and v not in (None, ""):
            inv[lk] = v
    inv["orderDate"] = _tr_date(order.get("created_at")) or None
    inv["invoiceDate"] = invoice_date or _tr_date()
    inv["isDocumentNoAuto"] = True      # numara BirFatura'da tanımlı seriden otomatik atanır
    inv["ettn"] = ettn
    inv["taxNo"] = receiver_tax_no(m)
    if receiver_tag:
        inv["receiverTag"] = receiver_tag   # yalnız e-Fatura (şema)
    # Havale indirimi ürün satırlarına dağıtıldı (map_order) → ayrı alan 0.
    inv["bankTransferDiscountTotalTaxExcluding"] = 0
    inv["bankTransferDiscountTotalTaxIncluding"] = 0

    details = []
    for d in m.get("OrderDetails") or []:
        line = {}
        for k, v in d.items():
            lk = _lc(k)
            if lk in DETAIL_FIELDS and v not in (None, ""):
                line[lk] = v
        variants = d.get("Variants") or []
        if variants:
            line["productNote"] = ", ".join(f"{x.get('Type')}: {x.get('Value')}" for x in variants)[:250]
        if "discountUnitTaxIncluding" in line:
            line["discountIsPercentUnit"] = 0   # sabit tutar (şema: 1 = yüzde, 0 = sabit)
        details.append(line)
    inv["orderDetails"] = details
    return {k: inv[k] for k in INVOICE_FIELDS if k in inv and inv[k] is not None}


def violations(inv: dict) -> list:
    """Şemada zorunlu olup boş kalan alanlar (Türkçe etiketle)."""
    out = []
    for f in INVOICE_REQUIRED:
        v = inv.get(f)
        if v is None or v == "" or v == []:
            out.append(FIELD_LABELS.get(f, f))
    for i, line in enumerate(inv.get("orderDetails") or []):
        for f in DETAIL_REQUIRED:
            if line.get(f) in (None, ""):
                out.append(f"{i + 1}. satır {f}")
    return out


def expected_total(order: dict) -> Decimal:
    """Müşterinin ödediği (faturalanacak) tutar: sipariş toplamı + taksit vade farkı."""
    vf, _inst = bf.installment_charge(order)
    return bf.q(bf.D(order.get("total"))) + vf


def total_problems(order: dict, inv: dict) -> list:
    """Sipariş toplamı ↔ fatura toplamı ↔ satırların toplamı tutarlılığı."""
    probs = []
    lines = inv.get("orderDetails") or []
    tol = max(Decimal("0.05"), Decimal("0.01") * len(lines))
    paid = bf.D(inv.get("totalPaidTaxIncluding"))
    exp = expected_total(order)
    if abs(paid - exp) > tol:
        probs.append(f"Fatura toplamı ({bf.q(paid)} TL) sipariş toplamıyla ({bf.q(exp)} TL) uyuşmuyor.")
    lines_incl = sum((bf.D(x.get("productUnitPriceTaxIncluding")) - bf.D(x.get("discountUnitTaxIncluding")))
                     * bf.D(x.get("productQuantity")) for x in lines)
    extras = sum(bf.D(inv.get(f"{p}TaxIncluding")) for p in (
        "shippingChargeTotal", "payingAtTheDoorChargeTotal", "installmentChargeTotal"))
    extras -= bf.D(inv.get("discountTotalTaxIncluding")) + bf.D(inv.get("bankTransferDiscountTotalTaxIncluding"))
    if abs(lines_incl + extras - paid) > tol:
        probs.append(f"Satırların toplamı ({bf.q(lines_incl + extras)} TL) fatura toplamıyla ({bf.q(paid)} TL) uyuşmuyor.")
    if bf.D(inv.get("totalPaidTaxExcluding")) > paid + tol:
        probs.append("KDV hariç toplam, KDV dahil toplamdan büyük.")
    return probs


def summary(inv: dict, system_type: Optional[str]) -> dict:
    incl = bf.D(inv.get("totalPaidTaxIncluding"))
    ex = bf.D(inv.get("totalPaidTaxExcluding"))
    return {
        "total_incl": bf.num(incl), "total_excl": bf.num(ex), "vat": bf.num(incl - ex),
        "currency": inv.get("currency") or "TRY", "lines": len(inv.get("orderDetails") or []),
        "receiver": {"name": inv.get("billingName") or "", "tax_no": inv.get("taxNo") or "",
                     "tax_office": inv.get("taxOffice") or "", "city": inv.get("billingCity") or "",
                     "email": inv.get("email") or ""},
        "system_type": system_type, "invoice_type": TYPE_LABEL.get(system_type or "", ""),
    }


# ---------------------------------------------------------------------------
# Hata metinleri
# ---------------------------------------------------------------------------
class OutError(Exception):
    """BirFatura çağrısı başarısız. `maybe_sent`: istek gitmiş olabilir (zaman aşımı/bağlantı koptu)."""

    def __init__(self, message: str, *, status: int = 0, kind: str = "api", maybe_sent: bool = False):
        super().__init__(message)
        self.message = message
        self.status = status
        self.kind = kind
        self.maybe_sent = maybe_sent


def _clean(s, secrets=(), maxlen: int = 300) -> str:
    t = re.sub(r"<[^>]+>", " ", str(s or ""))
    t = re.sub(r"[\x00-\x1f\x7f]+", " ", t)
    for sec in secrets:
        if sec and len(sec) >= 4:
            t = t.replace(sec, "***")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:maxlen]


def api_error_text(status: int, payload, op: str, secrets=()) -> str:
    """BirFatura yanıtından admin'e gösterilecek Türkçe, anlaşılır hata metni."""
    msg = res = ""
    if isinstance(payload, dict):
        msg = _clean(payload.get("Message") or payload.get("message"), secrets)
        r = payload.get("Result")
        if isinstance(r, str):
            res = _clean(r, secrets)
    detail = " — ".join(x for x in (msg, res) if x and x != "string")
    if status in (401, 403):
        base = "BirFatura API anahtarları reddedildi (X-Api-Key / X-Secret-Key / X-Integration-Key'i kontrol edin)"
    elif status == 404:
        base = "BirFatura uç noktası bulunamadı (ortam adresi yanlış olabilir)"
    elif status == 429:
        base = "BirFatura istek sınırı aşıldı, biraz sonra tekrar deneyin"
    elif status >= 500:
        base = "BirFatura sunucu hatası"
    elif status >= 400:
        base = "BirFatura isteği reddetti"
    else:
        base = "BirFatura işlemi başarısız"
    return f"{base} ({op}){': ' + detail if detail else ''}."


# ---------------------------------------------------------------------------
# HTTP istemcisi
# ---------------------------------------------------------------------------
class OutClient:
    def __init__(self, base_url: str, api_key: str, secret_key: str, integration_key: str,
                 *, timeout: float = 45.0, transport=None):
        self.base_url = base_url.rstrip("/")
        self._headers = {"X-Api-Key": api_key, "X-Secret-Key": secret_key, "X-Integration-Key": integration_key,
                         "Content-Type": "application/json", "Accept": "application/json"}
        self._secrets = (api_key, secret_key, integration_key)
        self.timeout = timeout
        self.transport = transport

    async def call(self, op: str, body: dict, *, mutating: bool = False):
        """POST {base}/api/OutEBelgeV2/{op}. Başarılıysa yanıt zarfı (dict); değilse OutError."""
        import httpx
        url = f"{self.base_url}{API_PREFIX}/{op}"
        kw = {"timeout": httpx.Timeout(self.timeout, connect=10.0), "verify": True, "follow_redirects": False}
        if self.transport is not None:
            kw["transport"] = self.transport
        try:
            async with httpx.AsyncClient(**kw) as c:
                r = await c.post(url, json=body, headers=self._headers)
        except httpx.ConnectError:
            raise OutError(f"BirFatura'ya bağlanılamadı ({op}). Ağ/ortam adresini kontrol edin.", kind="network")
        except httpx.TimeoutException:
            raise OutError(f"BirFatura zamanında yanıt vermedi ({op}).", kind="timeout", maybe_sent=mutating)
        except httpx.HTTPError as e:
            raise OutError(f"BirFatura bağlantı hatası ({op}): {type(e).__name__}.", kind="network",
                           maybe_sent=mutating)
        try:
            payload = r.json()
        except Exception:
            payload = None
        if r.status_code >= 300 or not isinstance(payload, dict) or payload.get("Success") is not True:
            status = r.status_code if r.status_code >= 300 else 0
            if r.status_code < 300 and not isinstance(payload, dict):
                raise OutError(f"BirFatura beklenmeyen yanıt döndürdü ({op}).", status=r.status_code, kind="api")
            raise OutError(api_error_text(status, payload, op, self._secrets), status=r.status_code, kind="api")
        return payload

    async def get_user_pk(self, kn: str) -> list:
        p = await self.call("GetUserPK", {"kn": kn})
        res = p.get("Result")
        return res if isinstance(res, list) else []

    async def send_basic_invoice(self, invoice: dict) -> dict:
        p = await self.call("SendBasicInvoiceFromModel", {"invoice": invoice}, mutating=True)
        res = p.get("Result")
        return res if isinstance(res, dict) else {}

    async def get_pdf_link(self, ettn: str, system_type: str) -> Optional[str]:
        p = await self.call("GetPDFLinkByUUID", {"uuids": [ettn], "systemType": system_type})
        for row in p.get("Result") or []:
            if isinstance(row, dict) and str(row.get("uuid") or "").lower() == ettn.lower():
                link = safe_link(row.get("pdfLink"))
                if link:
                    return link
        for row in p.get("Result") or []:   # tek UUID sorulduysa uuid alanı boş dönebilir
            if isinstance(row, dict):
                link = safe_link(row.get("pdfLink"))
                if link:
                    return link
        return None

    async def get_credits(self, kn: str) -> str:
        p = await self.call("GetNumberOfCredits", {"kn": kn})
        return _clean(p.get("Result"), self._secrets, 64)


def safe_link(v) -> Optional[str]:
    s = str(v or "").strip()
    if not s or len(s) > 2000 or s == "string":
        return None
    try:
        p = urlsplit(s)
    except Exception:
        return None
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        return None
    return s


def new_ettn() -> str:
    return str(uuid.uuid4())
