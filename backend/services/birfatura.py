"""
services/birfatura.py — BirFatura "Özel Entegrasyon" sözleşmesi: saf (DB'siz) yardımcılar.

BirFatura ÇEKME (pull) modeliyle çalışır: mağaza kendi sitesinde aşağıdaki uçları açar,
BirFatura panelindeki "Özel Entegrasyon" mağazasına site adresi + API şifresi (token) girilir;
BirFatura bu adresin sonuna sabit yolları ekleyip periyodik olarak POST eder:

    POST {site}/api/orderStatus        → {"OrderStatus":   [{"Id": int, "Value": str}]}
    POST {site}/api/paymentMethods     → {"PaymentMethods":[{"Id": int, "Value": str}]}
    POST {site}/api/orders             ← {"orderStatusId", "startDateTime", "endDateTime"}
                                       → {"Orders": [Order...]}
    POST {site}/api/invoiceLinkUpdate  ← {"orderId", "faturaUrl", "faturaNo", "faturaTarihi"}
    POST {site}/api/orderCargoUpdate   ← {"orderId", "orderStatusId", "cargoTrackingCode",
                                          "cargoTrackingCodeUrl", "cargoCompany", "updateDateTime"}
                                       → {"Success": bool, "Message": str}

Kimlik doğrulama: her istekte `token` HTTP başlığı (panelde "API Şifresi"). Tarih biçimi
her iki yönde `dd.MM.yyyy HH:mm:ss` (Türkiye saati).

KAYNAK: BirFatura'nın resmî dokümanı (developers.birfatura.com/dokuman/ozel-entegrasyon-api,
app.swaggerhub.com/apis-docs/birfatura/orders) bu ortamdan erişilemedi (egress engeli). Alan
adları, zorunluluklar ve uç yolları, resmî dokümandan birebir türetilmiş açık kaynak
uygulamalardan alındı:
  - github.com/aenzenith/laravel-birfatura (tests/Fixtures/contract.php: resmî şemanın alan
    listesi + zorunlu alanlar; routes/birfatura.php: uç yolları; docs/*: geri yazım gövdeleri)
  - github.com/gurkanbicer/birfatura-whmcs (api.php: `token` başlığı, yanıt zarfları)
VARSAYIMLAR (BirFatura dokümanında açıklanmayan noktalar) "VARSAYIM:" ile işaretlidir.

Bu modül veritabanına DOKUNMAZ; route katmanı (routes/integrations_birfatura.py) siparişi
okur, buradaki fonksiyonlarla sözleşme biçimine çevirir. Böylece eşleme birim testlenebilir.
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

try:  # Türkiye saati (DST yok, sabit +03:00) — zoneinfo yoksa sabit ofset
    from zoneinfo import ZoneInfo
    TR_TZ = ZoneInfo("Europe/Istanbul")
except Exception:  # pragma: no cover
    TR_TZ = timezone(timedelta(hours=3))

DATE_FMT = "%d.%m.%Y %H:%M:%S"

# ---------------------------------------------------------------------------
# Sözlükler
# ---------------------------------------------------------------------------
# Durum GRUPLARI: BirFatura panelinde "hangi durumdaki siparişler faturalansın" seçimi bu
# listeden yapılır; BirFatura seçilen Id'yi `orderStatusId` olarak geri gönderir. Id'ler
# SABİT kalmalıdır (BirFatura saklar). Admin grupların adını/kapsadığı site durumlarını
# değiştirebilir; Id değiştirilemez.
DEFAULT_STATUS_GROUPS = [
    {"id": 1, "name": "Onaylandı (faturalanabilir)",
     "statuses": ["confirmed", "preparing", "processing", "ready_to_ship",
                  "shipped", "in_transit", "out_for_delivery", "delivered"]},
    {"id": 2, "name": "Kargoya Verildi",
     "statuses": ["shipped", "in_transit", "out_for_delivery"]},
    {"id": 3, "name": "Teslim Edildi", "statuses": ["delivered"]},
]

# Ödeme yöntemleri sözlüğü (sabit Id). Site siparişinde yalnız kart / havale-EFT / kapıda ödeme var.
PAYMENT_METHODS = [
    {"Id": 1, "Value": "Kredi Kartı"},
    {"Id": 2, "Value": "Banka EFT-Havale"},
    {"Id": 3, "Value": "Kapıda Ödeme"},
]
_PM_BANK = {"bank_transfer", "havale", "eft", "havale_eft", "banka_havale", "havale/eft"}
_PM_COD = {"cash_on_delivery", "kapida", "kapida_odeme", "cod"}

# Hizmet satırları için sabit sanal ürün kimlikleri (sözleşme ProductId'yi zorunlu tutar).
GIFT_WRAP_PRODUCT_ID = 900000001

DEFAULT_SETTINGS = {
    "enabled": False,
    "status_groups": DEFAULT_STATUS_GROUPS,
    "date_field": "created_at",          # created_at | updated_at — aralık filtresi hangi alana bakar
    "discount_mode": "net",              # net | line  (bkz. map_order)
    "default_vat_rate": None,            # None → settings.main.default_vat_rate → 10
    "shipping_vat_rate": 20,             # kargo hizmeti KDV %
    "service_vat_rate": 20,              # hediye paketi / kapıda ödeme hizmet bedeli KDV %
    "default_tckn": "11111111111",       # TCKN'siz bireysel müşteri (GİB e-Arşiv standardı)
    "only_site_orders": True,            # pazaryeri siparişleri hariç
    "skip_invoiced_elsewhere": True,     # başka yoldan (manuel/eski entegratör) faturalanmışlar hariç
    "max_window_days": 31,
    "trusted_invoice_hosts": ["birfatura.com", "*.birfatura.com"],
    "store_cargo_updates": True,         # orderCargoUpdate ile gelen takip no siparişe yazılsın
    "invoice_explanation": "Sipariş No: {order_number}",
}

_SITE_PLATFORMS = {"", "web", "site", "website", "mobile", "app"}


# ---------------------------------------------------------------------------
# Tarih
# ---------------------------------------------------------------------------
def parse_bf_date(value) -> Optional[datetime]:
    """'dd.MM.yyyy HH:mm:ss' (Türkiye saati) → tz-aware UTC datetime. Katı: başka biçim None."""
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not re.fullmatch(r"\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}", s):
        return None
    try:
        dt = datetime.strptime(s, DATE_FMT)
    except ValueError:
        return None
    return dt.replace(tzinfo=TR_TZ).astimezone(timezone.utc)


def parse_any_dt(value) -> Optional[datetime]:
    """Siparişte saklı tarih (ISO string ya da datetime) → tz-aware UTC."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            try:
                dt = datetime.fromisoformat(s[:19])
            except ValueError:
                return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def fmt_bf_date(value) -> str:
    dt = parse_any_dt(value)
    if not dt:
        return ""
    return dt.astimezone(TR_TZ).strftime(DATE_FMT)


# ---------------------------------------------------------------------------
# Tutar yardımcıları (Decimal, yarım-yukarı)
# ---------------------------------------------------------------------------
def D(v) -> Decimal:
    try:
        if v is None or v == "":
            return Decimal("0")
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def q(v: Decimal, places: int = 2) -> Decimal:
    return v.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def num(v: Decimal, places: int = 2):
    """JSON'a sayı olarak yaz: tamsa int, değilse float (sözleşme `number`)."""
    r = q(v, places).normalize()
    if r == r.to_integral_value():
        return int(r)
    return float(r)


def excl(incl: Decimal, rate) -> Decimal:
    rate = D(rate)
    return incl * Decimal(100) / (Decimal(100) + rate)


def pair(prefix: str, incl: Decimal, rate=None, excl_value: Optional[Decimal] = None, places: int = 2) -> dict:
    ex = excl_value if excl_value is not None else excl(incl, rate)
    return {f"{prefix}TaxExcluding": num(ex, places), f"{prefix}TaxIncluding": num(incl, places)}


# ---------------------------------------------------------------------------
# Kimlikler
# ---------------------------------------------------------------------------
def numeric_order_id(order: dict) -> Optional[int]:
    """Sözleşme OrderId için `integer (long)` önerir. Site sipariş no 'W10001' → 10001.
    Eşlenemeyen (eski/yedek biçim) siparişte None → route katmanı kalıcı sayaçtan atar."""
    v = order.get("birfatura_order_id")
    if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
        return int(v)
    m = re.fullmatch(r"W(\d{1,15})", str(order.get("order_number") or "").strip(), re.I)
    return int(m.group(1)) if m else None


def numeric_product_id(item: dict) -> int:
    """ProductId (zorunlu, `integer (long)` önerilir). Ürün kimliklerimiz UUID olduğu için
    VARSAYIM: sayısal kart no (urun_karti_id) varsa o; yoksa ürün kimliğinin SHA-1'inden
    deterministik 52-bit tamsayı (JS-güvenli, her çekimde aynı)."""
    for k in ("urun_karti_id", "csv_card_id"):
        v = str(item.get(k) or "").strip()
        if v.isdigit() and len(v) <= 15:
            return int(v)
    key = str(item.get("product_id") or item.get("id") or item.get("sku") or item.get("name") or "")
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:13], 16)


# ---------------------------------------------------------------------------
# Ayar / filtre
# ---------------------------------------------------------------------------
def merged_settings(doc: Optional[dict]) -> dict:
    out = {k: (list(v) if isinstance(v, list) else v) for k, v in DEFAULT_SETTINGS.items()}
    for k, v in (doc or {}).items():
        if k in out and v is not None:
            out[k] = v
    out.update({k: v for k, v in (doc or {}).items() if k not in out})
    return out


def status_dictionary(settings: dict) -> list:
    groups = settings.get("status_groups") or DEFAULT_STATUS_GROUPS
    return [{"Id": int(g["id"]), "Value": str(g.get("name") or f"Durum {g['id']}")}
            for g in groups if isinstance(g, dict) and str(g.get("id", "")).lstrip("-").isdigit()]


def statuses_for_group(settings: dict, group_id: int) -> Optional[list]:
    for g in settings.get("status_groups") or DEFAULT_STATUS_GROUPS:
        try:
            if int(g.get("id")) == int(group_id):
                return [str(s) for s in (g.get("statuses") or [])]
        except Exception:
            continue
    return None


def payment_type(order: dict) -> dict:
    pm = str(order.get("payment_method") or "").strip().lower()
    if pm in _PM_BANK:
        return PAYMENT_METHODS[1]
    if pm in _PM_COD:
        return PAYMENT_METHODS[2]
    return PAYMENT_METHODS[0]


def is_site_order(order: dict) -> bool:
    return str(order.get("platform") or order.get("marketplace") or "").strip().lower() in _SITE_PLATFORMS


def skip_reason(order: dict, settings: dict) -> Optional[str]:
    """Faturalanmaması gereken sipariş için kısa sebep; uygunsa None."""
    if settings.get("only_site_orders", True) and not is_site_order(order):
        return "site dışı kanal kaydı"
    if not (order.get("items") or []):
        return "kalem yok"
    if D(order.get("total")) <= Decimal("0.009"):
        return "tutar 0 (tamamı hediye çeki/puan)"
    if (settings.get("skip_invoiced_elsewhere", True) and order.get("invoice_issued")
            and str(order.get("invoice_provider") or "") != "birfatura"):
        return "başka yoldan faturalanmış"
    return None


# ---------------------------------------------------------------------------
# Taraflar
# ---------------------------------------------------------------------------
def _digits(s) -> str:
    return re.sub(r"\D", "", str(s or ""))


def _phone(s) -> str:
    d = _digits(s)
    if d.startswith("90") and len(d) == 12:
        d = d[2:]
    if len(d) == 10:
        d = "0" + d
    return d


def _full_name(a: dict) -> str:
    n = f"{(a.get('first_name') or '').strip()} {(a.get('last_name') or '').strip()}".strip()
    return n or str(a.get("full_name") or a.get("name") or "").strip()


def _addr_line(a: dict) -> str:
    parts = [a.get("address"), a.get("address2"), a.get("neighborhood")]
    return " ".join(str(p).strip() for p in parts if p and str(p).strip())


def billing_fields(order: dict, settings: dict) -> dict:
    ship = order.get("shipping_address") if isinstance(order.get("shipping_address"), dict) else {}
    bill = order.get("billing_address") if isinstance(order.get("billing_address"), dict) else {}
    bill = bill or ship
    info = order.get("billing_info") if isinstance(order.get("billing_info"), dict) else {}
    email = (bill.get("email") or ship.get("email") or order.get("email") or order.get("user_email") or "").strip()
    out = {
        "BillingName": _full_name(bill) or _full_name(ship),
        "BillingAddress": _addr_line(bill) or _addr_line(ship),
        "BillingTown": (bill.get("district") or ship.get("district") or "").strip(),
        "BillingCity": (bill.get("city") or ship.get("city") or "").strip(),
        "BillingMobilePhone": _phone(bill.get("phone") or ship.get("phone") or order.get("phone")),
        "Email": email or None,
    }
    tax_no = _digits(info.get("tax_number") or bill.get("tax_number") or bill.get("vkn"))
    corporate = bool(info.get("is_corporate")) and bool(tax_no)
    if corporate:
        company = (info.get("company_name") or bill.get("company_name") or "").strip()
        if company:
            out["BillingName"] = company
        out["TaxOffice"] = (info.get("tax_office") or bill.get("tax_office") or "").strip() or None
        if len(tax_no) == 11:
            # Şahıs şirketi: vergi kimliği TCKN'dir. VARSAYIM: SSNTCNo + TaxOffice ile gönderilir
            # (sözleşmede bir taraf hem TaxNo hem SSNTCNo taşımaz).
            out["SSNTCNo"] = tax_no
        else:
            out["TaxNo"] = tax_no
    else:
        tckn = _digits(bill.get("tckn") or bill.get("identity_number") or bill.get("tc_no")
                       or info.get("tckn") or info.get("tc_no"))
        out["SSNTCNo"] = tckn if len(tckn) == 11 else str(settings.get("default_tckn") or "11111111111")
    return out


def shipping_fields(order: dict) -> dict:
    ship = order.get("shipping_address") if isinstance(order.get("shipping_address"), dict) else {}
    bill = order.get("billing_address") if isinstance(order.get("billing_address"), dict) else {}
    ship = ship or bill
    return {
        "ShippingName": _full_name(ship),
        "ShippingAddress": _addr_line(ship),
        "ShippingTown": (ship.get("district") or "").strip(),
        "ShippingCity": (ship.get("city") or "").strip(),
        "ShippingCountry": (ship.get("country") or "Türkiye").strip(),
        "ShippingZipCode": (str(ship.get("postal_code") or ship.get("zipcode") or "").strip() or None),
        "ShippingPhone": _phone(ship.get("phone")) or None,
    }


# ---------------------------------------------------------------------------
# Kalemler + toplamlar
# ---------------------------------------------------------------------------
def item_vat_rate(item: dict, vat_map: dict, default_rate) -> int:
    for cand in (item.get("vat_rate"), item.get("kdv_rate"), (vat_map or {}).get(item.get("product_id"))):
        if cand not in (None, ""):
            try:
                r = int(round(float(cand)))
                if 0 <= r <= 100:
                    return r
            except Exception:
                pass
    return int(round(float(default_rate if default_rate not in (None, "") else 10)))


def allocate_discount(order: dict, gross_lines: list) -> tuple:
    """Fatura iskontosu ve kalem dağılımı — fatura matrahının tek kuralı (eski e-fatura akışıyla aynı):
      faturalanacak (ürün + kargo) = total − hediye paketi − kapıda ödeme bedeli
      iskonto = (ürün brüt + kargo) − faturalanacak   (kupon, kampanya, havale indirimi,
                hediye çeki ve puan → mağazanın bedelsiz verdiği araçlar iskonto sayılır)
    Dağıtım: checkout'ta dondurulmuş kalem indirimi (items[].discount_amount) varsa o esas;
    kalan kısım brüt paya göre oransal; kuruş kalanı son satıra. Döner (iskonto, [satır iskontosu])."""
    gross = sum(gross_lines, Decimal(0))
    ship = q(D(order.get("shipping_cost")))
    gw = q(D(order.get("gift_wrap_price"))) if order.get("gift_wrap") or D(order.get("gift_wrap_price")) > 0 else Decimal(0)
    cod = q(D(order.get("cod_fee")))
    total = q(D(order.get("total")))
    billable = (total if total > Decimal("0.005") else gross + ship) - gw - cod
    disc = q(gross + ship - billable)
    if disc < Decimal("0.01"):
        disc = q(D(order.get("discount")) + D(order.get("payment_discount")))
    disc = max(Decimal(0), min(disc, gross))
    n = len(gross_lines)
    out = [Decimal(0)] * n
    if disc <= Decimal("0.005") or gross <= Decimal("0.005"):
        return disc, out
    items = order.get("items") or []
    frozen = (len(items) == n and all(isinstance(it, dict) and it.get("discount_amount") is not None
                                      for it in items))
    base = [Decimal(0)] * n
    if frozen:
        base = [max(Decimal(0), min(gross_lines[k], q(D(items[k].get("discount_amount"))))) for k in range(n)]
    rest = max(Decimal(0), disc - sum(base, Decimal(0)))
    alloc = Decimal(0)
    for k in range(n):
        g = gross_lines[k]
        if k < n - 1:
            d = q(base[k] + rest * g / gross)
        else:
            d = q(disc - alloc)
        d = max(Decimal(0), min(d, g))
        alloc += d
        out[k] = d
    return disc, out


def installment_charge(order: dict) -> tuple:
    """Taksit vade farkı (KDV dahil) = iyzico paidPrice − sipariş toplamı (taksit > 1 iken)."""
    iyz = order.get("iyzico_retrieve_response") if isinstance(order.get("iyzico_retrieve_response"), dict) else {}
    try:
        inst = int(float(iyz.get("installment") or order.get("installment") or 1))
    except Exception:
        inst = 1
    charged = q(D(iyz.get("paidPrice") or order.get("paid_amount")))
    base = q(D(order.get("total")))
    vf = q(charged - base) if (charged > 0 and base > 0) else Decimal(0)
    if inst > 1 and vf >= Decimal("0.01"):
        return vf, inst
    return Decimal(0), inst


def map_order(order: dict, settings: dict, *, vat_map: Optional[dict] = None,
              default_vat_rate=None, product_meta: Optional[dict] = None,
              site_url: str = "", bf_order_id: Optional[int] = None) -> dict:
    """Site siparişi → BirFatura `Orders[]` öğesi.

    discount_mode:
      "net"  (varsayılan) — iskonto kalemin birim fiyatına yedirilir (birim fiyat = indirimli
             fiyat), DiscountTotal 0. Her satırın KDV matrahı doğrudan doğru çıkar; BirFatura'nın
             iskontoyu nasıl yorumladığından bağımsızdır (en güvenli).
      "line" — kalem brüt fiyatla + DiscountUnitTaxExcluding/Including (birim iskonto) alanı.
             Faturada iskonto sütunu görünür. VARSAYIM: BirFatura satır iskontosunu kalem
             matrahından düşer (alan resmî şemada var; davranışı dokümanda açıklanmıyor).
    Her iki modda da TotalPaid = müşterinin ödediği tutar (vade farkı dahil):
      net : TotalPaid = ProductsTotal + ShippingCharge + PayingAtTheDoorCharge + InstallmentCharge
      line: TotalPaid = ProductsTotal(brüt) − Σ(satır iskontosu) + ShippingCharge + ...
    DiscountTotal (sipariş geneli iskonto) her iki modda 0 gönderilir — iskonto zaten satırlarda;
    VARSAYIM: BirFatura DiscountTotal'ı satır iskontolarına EK bir iskonto olarak uygular,
    bu yüzden toplamı oraya da yazmak çift düşüme yol açardı.
    """
    vat_map = vat_map or {}
    product_meta = product_meta or {}
    dflt = default_vat_rate if default_vat_rate not in (None, "") else (settings.get("default_vat_rate") or 10)
    mode = "line" if settings.get("discount_mode") == "line" else "net"
    items = [it for it in (order.get("items") or []) if isinstance(it, dict)]

    qtys, units, rates = [], [], []
    for it in items:
        try:
            qty = D(it.get("quantity") or it.get("qty") or 1)
        except Exception:
            qty = Decimal(1)
        if qty <= 0:
            qty = Decimal(1)
        qtys.append(qty)
        units.append(q(D(it.get("price") if it.get("price") is not None else it.get("unit_price")), 4))
        rates.append(item_vat_rate(it, vat_map, dflt))
    gross_lines = [q(units[k] * qtys[k]) for k in range(len(items))]
    disc, line_disc = allocate_discount(order, gross_lines)

    details = []
    products_incl = Decimal(0)
    products_excl = Decimal(0)
    line_disc_incl = Decimal(0)
    line_disc_excl = Decimal(0)
    for k, it in enumerate(items):
        meta = product_meta.get(it.get("product_id")) or {}
        rate = rates[k]
        unit = units[k]
        qty = qtys[k]
        d_unit = (line_disc[k] / qty) if qty else Decimal(0)
        size = str(it.get("size") or "").strip()
        color = str(it.get("color") or "").strip()
        variants = [v for v in ([{"Type": "Beden", "Value": size}] if size else [])
                    + ([{"Type": "Renk", "Value": color}] if color else [])]
        code = (str(it.get("sku") or it.get("product_code") or it.get("stock_code") or meta.get("stock_code")
                    or meta.get("sku") or it.get("barcode") or it.get("product_id") or "")).strip()
        line = {
            "ProductId": numeric_product_id({**meta, **it}),
            "ProductCode": code[:100] or "URUN",
            "Barcode": (str(it.get("barcode") or "").strip() or None),
            "ProductBrand": (str(it.get("brand") or meta.get("brand") or "").strip() or None),
            "ProductName": str(it.get("product_name") or it.get("name") or meta.get("name") or "Ürün").strip()[:250],
            "ProductImage": (str(it.get("image") or "").strip() if str(it.get("image") or "").startswith("http") else None),
            "Variants": variants or None,
            "ProductQuantityType": "Adet",
            "ProductQuantity": num(qty, 4),
            "VatRate": rate,
        }
        if mode == "net":
            u = q(unit - d_unit, 4)
            line.update(pair("ProductUnitPrice", u, rate, places=4))
            products_incl += u * qty
            products_excl += excl(u, rate) * qty
        else:
            line.update(pair("ProductUnitPrice", unit, rate, places=4))
            if line_disc[k] > 0:
                du = q(d_unit, 4)
                line.update(pair("DiscountUnit", du, rate, places=4))
                line_disc_incl += du * qty
                line_disc_excl += excl(du, rate) * qty
            products_incl += unit * qty
            products_excl += excl(unit, rate) * qty
        details.append({k2: v for k2, v in line.items() if v is not None})

    svc_rate = int(settings.get("service_vat_rate") or 20)
    gw = q(D(order.get("gift_wrap_price")))
    if gw > 0:
        details.append({
            "ProductId": GIFT_WRAP_PRODUCT_ID, "ProductCode": "HEDIYEPAKETI", "ProductName": "Hediye Paketi",
            "ProductQuantityType": "Adet", "ProductQuantity": 1, "VatRate": svc_rate,
            **pair("ProductUnitPrice", gw, svc_rate, places=4),
        })
        products_incl += gw
        products_excl += excl(gw, svc_rate)

    ship = q(D(order.get("shipping_cost")))
    ship_rate = int(settings.get("shipping_vat_rate") or 20)
    cod = q(D(order.get("cod_fee")))
    vf, inst = installment_charge(order)
    # Vade farkı matraha dahildir ve MALIN KDV oranıyla vergilenir (KDVK 24/c) → en büyük
    # tutarlı ürün satırının oranı.
    goods_rate = rates[max(range(len(rates)), key=lambda i: gross_lines[i])] if rates else int(dflt)

    paid_incl = products_incl - line_disc_incl + ship + cod + vf
    paid_excl = (products_excl - line_disc_excl + excl(ship, ship_rate) + excl(cod, svc_rate)
                 + excl(vf, goods_rate))

    pt = payment_type(order)
    order_number = str(order.get("order_number") or order.get("id") or "")
    expl_tmpl = str(settings.get("invoice_explanation") or "")
    try:
        expl = expl_tmpl.format(order_number=order_number) if expl_tmpl else ""
    except Exception:
        expl = expl_tmpl
    if inst > 1 and vf > 0:
        expl = (expl + f" Taksitli satış ({inst} taksit); vade farkı satış bedeline dahildir.").strip()

    out = {
        "OrderId": bf_order_id if bf_order_id is not None else numeric_order_id(order),
        "OrderCode": order_number,
        "OrderDate": fmt_bf_date(order.get("created_at")),
        "InvoiceExplanation": expl or None,
        **billing_fields(order, settings),
        **shipping_fields(order),
        "ShipCompany": (str(order.get("cargo_provider_name") or "").strip() or None),
        "SalesChannelWebSite": site_url or None,
        "PaymentTypeId": pt["Id"],
        "PaymentType": pt["Value"],
        "Currency": "TRY",
        "CurrencyRate": 1,
        **pair("TotalPaid", paid_incl, excl_value=paid_excl),
        **pair("ProductsTotal", products_incl, excl_value=products_excl),
        **pair("DiscountTotal", Decimal(0), excl_value=Decimal(0)),
        **pair("ShippingChargeTotal", ship, ship_rate),
        **pair("PayingAtTheDoorChargeTotal", cod, svc_rate),
        **pair("InstallmentChargeTotal", vf, goods_rate),
        "OrderDetails": details,
    }
    return {k: v for k, v in out.items() if v is not None}


REQUIRED_ORDER_FIELDS = (
    "OrderId", "OrderCode", "OrderDate", "BillingName", "BillingAddress", "BillingTown", "BillingCity",
    "BillingMobilePhone", "ShippingName", "ShippingAddress", "ShippingTown", "ShippingCity",
    "PaymentTypeId", "Currency", "TotalPaidTaxExcluding", "TotalPaidTaxIncluding",
    "ProductsTotalTaxExcluding", "ProductsTotalTaxIncluding", "OrderDetails",
)


def violations(mapped: dict) -> list:
    """Sözleşmede zorunlu olup boş kalan alanlar (sipariş atlanır ve loglanır)."""
    bad = [f for f in REQUIRED_ORDER_FIELDS if mapped.get(f) in (None, "", [])]
    return bad


# ---------------------------------------------------------------------------
# Geri yazım doğrulama
# ---------------------------------------------------------------------------
_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


def clean_order_ref(v) -> Optional[str]:
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    s = str(v).strip()
    return s if _ID_RE.match(s) else None


def host_allowed(url: str, patterns: list) -> bool:
    from urllib.parse import urlsplit
    try:
        parts = urlsplit(str(url or "").strip())
    except Exception:
        return False
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        return False
    host = parts.hostname.lower().rstrip(".")
    if not patterns:
        return True
    for p in patterns:
        p = str(p or "").strip().lower()
        if not p:
            continue
        if p.startswith("*."):
            if host.endswith(p[1:]) and host != p[2:]:
                return True
        elif host == p:
            return True
    return False


def safe_text(v, maxlen: int = 64) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or len(s) > maxlen or re.search(r"[\x00-\x1f\x7f]", s):
        return None
    return s
