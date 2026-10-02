"""Rapor yardımcıları — tek-belge (kanonik) sipariş seçimi, tarih eşleşmesi, iade ve
adet metrikleri.

Eskiden burada başka bir altyapıdan aktarılmış ÇİFT sipariş kopyalarını rapordan
düşen bir süzgeç vardı; bu mağazada öyle bir aktarım olmadığından süzgeç kaldırıldı.
`load_dup_order_numbers` / `dup_nor` / `merge_match` geriye dönük uyum için korunur
ve etkisizdir (no-op).
"""
import time
from typing import List

_cache = {"at": -1e9, "nums": []}  # type: ignore


async def load_dup_order_numbers() -> List[str]:
    """Geriye dönük uyum: elenecek kopya yok → boş liste."""
    _cache["at"] = time.monotonic()
    return []


def dup_filter_state() -> int:
    """Kopya süzgecinin durumu: -1 = hiç yüklenmedi, aksi halde elenen numara sayısı.
    Rapor önbellek anahtarına girer — elemesiz hesaplanan sonuç elemeli isteğe dönmesin."""
    nums = _cache["nums"]
    return -1 if nums is None else len(nums)


def dup_nor() -> dict:
    """Geriye dönük uyum: hariç tutulacak kopya yok → {}."""
    return {}


def merge_match(base: dict) -> dict:
    """Bir $match dict'ine dup hariç-tutmayı (varsa) ekler. base'i mutasyona uğratmaz."""
    nor = dup_nor()
    if not nor:
        return base
    out = dict(base or {})
    out.update(nor)  # top-level $nor; mevcut $or/status/tarih anahtarlarıyla AND'lenir
    return out


def canonical_order_stages() -> list:
    """Mongo aggregation stages that enforce one document per real order.

    Historical imports can leave two documents with the same ``order_number``.
    Reports must consistently select the newest terminal/partial-cancel document,
    while orders without an order number remain distinct by their internal id.
    Call this immediately after the report's initial ``$match`` and before any
    ``$unwind`` or metric grouping.
    """

    terminal = [
        "cancelled", "cancel_refunded", "return_requested", "return_approved",
        "return_in_transit", "returned", "refunded", "partial_refunded",
    ]
    return [
        {"$addFields": {
            "_report_order_number": {"$trim": {"input": {"$toString": {"$ifNull": ["$order_number", ""]}}}},
            "_report_terminal": {"$cond": [{"$in": ["$status", terminal]}, 1, 0]},
            "_report_partial_cancel": {"$cond": [{"$gt": [{"$ifNull": ["$partial_cancel_amount", 0]}, 0]}, 1, 0]},
        }},
        {"$addFields": {
            "_report_dedupe_key": {"$cond": [
                {"$ne": ["$_report_order_number", ""]},
                {"$concat": ["order:", "$_report_order_number"]},
                {"$concat": ["id:", {"$toString": {"$ifNull": ["$id", "$_id"]}}]},
            ]},
        }},
        {"$sort": {
            "_report_dedupe_key": 1,
            "_report_terminal": -1,
            "_report_partial_cancel": -1,
            "updated_at": -1,
            "created_at": -1,
        }},
        {"$group": {"_id": "$_report_dedupe_key", "_report_doc": {"$first": "$$ROOT"}}},
        {"$replaceRoot": {"newRoot": "$_report_doc"}},
    ]


def effective_order_date_match(start: str, end: str | None = None) -> dict:
    """Date predicate shared by every order-backed report.

    ``marketplace_order_date`` (external order time on legacy records) wins when present;
    ``created_at`` is the normal source for site orders.
    """

    bounds = {"$gte": start}
    if end is not None:
        bounds["$lte"] = end
    return {"$or": [
        {"marketplace_order_date": dict(bounds)},
        {"marketplace_order_date": {"$in": [None, ""]}, "created_at": dict(bounds)},
    ]}


def split_confirmed_return(quantity: int, amount: float, returned: int) -> tuple[int, float, int, float]:
    """Split one order line into kept/net and confirmed-return portions."""
    qty = max(0, int(quantity or 0))
    ret = min(qty, max(0, int(returned or 0)))
    kept = qty - ret
    kept_amount = float(amount or 0) * kept / qty if qty else 0.0
    return kept, kept_amount, ret, float(amount or 0) - kept_amount


def allocate_order_total(line_amounts: list[float], order_total: float) -> list[float]:
    """Allocate the authoritative order total across product lines.

    Marketplace history contains more than one item-price representation.  Report
    revenue must therefore close to ``orders.total`` (the same source used by the
    sales breakdown), while preserving each line's relative share.  The last line
    receives the rounding remainder so the returned values add up to the cent.
    """
    amounts = [max(0.0, float(value or 0)) for value in (line_amounts or [])]
    target = max(0.0, round(float(order_total or 0), 2))
    if not amounts:
        return []
    base = sum(amounts)
    if base <= 0:
        # There is no defensible product-level weight.  Keep the full value visible
        # on one line rather than inventing equal unit prices.
        return [target] + [0.0] * (len(amounts) - 1)
    allocated = [round(target * value / base, 2) for value in amounts]
    allocated[-1] = round(allocated[-1] + target - sum(allocated), 2)
    return allocated


def partial_cancel_net_values(total: float, units: int, cancel_amount: float,
                              cancel_units: int, total_scope: str = "") -> tuple[float, int]:
    """Return the active remainder without subtracting an active-only total twice.

    New harici kanal reconciliation records explicitly mark totals/items that already
    contain only active package lines. Legacy records have no marker and retain the
    historical full-order subtraction behaviour.
    """
    total = max(0.0, float(total or 0))
    units = max(0, int(units or 0))
    if str(total_scope or "").strip().lower() == "active":
        return total, units
    amount = min(total, max(0.0, float(cancel_amount or 0)))
    cancelled = min(max(0, int(cancel_units or 0)), max(0, units - 1))
    return round(total - amount, 2), units - cancelled


def product_quantity_metrics(net: int, cancelled: int, returned: int) -> dict:
    """Kanonik ürün adetleri ve iki açıkça adlandırılmış iade oranı.

    Brüt oran: iade / (net + iptal + iade).
    Operasyonel oran: iade / (net + iade), yani iptaller paydaya girmez.
    """
    net = max(0, int(net or 0))
    cancelled = max(0, int(cancelled or 0))
    returned = max(0, int(returned or 0))
    gross = net + cancelled + returned
    sold_excluding_cancels = net + returned
    return {
        "gross_qty": gross,
        "gross_return_rate_pct": round(100 * returned / gross, 2) if gross else 0.0,
        "return_rate_excluding_cancels_pct": (
            round(100 * returned / sold_excluding_cancels, 2)
            if sold_excluding_cancels else 0.0
        ),
    }


def kept_gross_revenue(net_revenue: float, gross_revenue: float,
                       discount_amount: float) -> float:
    """Net kalan satışın indirim-öncesi karşılığını aynı ürün indirim oranıyla bul."""
    net_revenue = max(0.0, float(net_revenue or 0))
    gross_revenue = max(0.0, float(gross_revenue or 0))
    paid_before_returns = max(0.0, gross_revenue - float(discount_amount or 0))
    if gross_revenue <= 0 or paid_before_returns <= 0:
        return net_revenue
    return net_revenue * gross_revenue / paid_before_returns


def reconciled_platform_breakdown(product: dict) -> list[dict]:
    """Platform kırılımını ürünün kanonik net adet/ciro toplamına kuruşu kuruşuna eşitle."""
    qty = max(0, int((product or {}).get("qty") or 0))
    revenue = float((product or {}).get("revenue") or 0)
    rows = [dict(row) for row in ((product or {}).get("platform_breakdown") or [])]
    if not rows:
        rows = [{"platform": (product or {}).get("top_platform") or "site",
                 "qty": qty, "revenue": revenue}]
    rows[0]["revenue"] = float(rows[0].get("revenue") or 0) + (
        revenue - sum(float(row.get("revenue") or 0) for row in rows))
    rows[0]["qty"] = int(rows[0].get("qty") or 0) + (
        qty - sum(int(row.get("qty") or 0) for row in rows))
    return rows


def product_platform_metrics(net_rows: list[dict], event_rows: list[dict]) -> list[dict]:
    """Build scope-safe product metrics for each sales channel.

    ``net_rows`` contains kept sales, while ``event_rows`` contains cancelled and
    returned units/amounts. Keeping both in one row prevents a channel rate from
    accidentally using the all-channel denominator.
    """
    platforms: dict[str, dict] = {}
    for row in net_rows or []:
        key = str(row.get("platform") or "site").strip().lower() or "site"
        dst = platforms.setdefault(key, {"platform": key, "net_qty": 0, "net_revenue": 0.0,
                                         "cancel_qty": 0, "cancel_total": 0.0,
                                         "return_qty": 0, "return_total": 0.0})
        dst["net_qty"] += max(0, int(row.get("qty") or 0))
        dst["net_revenue"] += max(0.0, float(row.get("revenue") or 0))
    for row in event_rows or []:
        key = str(row.get("platform") or "site").strip().lower() or "site"
        dst = platforms.setdefault(key, {"platform": key, "net_qty": 0, "net_revenue": 0.0,
                                         "cancel_qty": 0, "cancel_total": 0.0,
                                         "return_qty": 0, "return_total": 0.0})
        dst["cancel_qty"] += max(0, int(row.get("cancel") or row.get("cancel_qty") or 0))
        dst["cancel_total"] += max(0.0, float(row.get("cancel_total") or 0))
        dst["return_qty"] += max(0, int(row.get("return") or row.get("return_qty") or 0))
        dst["return_total"] += max(0.0, float(row.get("return_total") or 0))
    result = []
    for dst in platforms.values():
        metrics = product_quantity_metrics(
            dst["net_qty"], dst["cancel_qty"], dst["return_qty"])
        dst.update(metrics)
        dst["gross_revenue"] = round(
            dst["net_revenue"] + dst["cancel_total"] + dst["return_total"], 2)
        for key in ("net_revenue", "cancel_total", "return_total"):
            dst[key] = round(dst[key], 2)
        result.append(dst)
    return sorted(result, key=lambda row: (-row["net_revenue"], row["platform"]))


def payment_report_group_key(order: dict) -> str:
    """Ödeme raporu kovası: site siparişlerinde gerçek ödeme yöntemi; site dışı
    (geçmişten kalan) kanal kayıtları tek "other" kovasında toplanır."""
    from sales_channels import channel_of, OTHER
    if channel_of(order) == OTHER:
        return OTHER
    return str((order or {}).get("payment_method") or "—").strip().lower() or "—"


def dedupe_return_records(records: list[dict]) -> list[dict]:
    """Keep one current document per return id, without merging distinct returns.

    Historical imports can leave multiple versions of the same ``customer_returns``
    record.  A repeated id is one return, while two different ids for the same
    order can be legitimate separate return attempts and must both survive.
    """
    terminal = {"returned", "refunded", "partial_refunded", "return_approved",
                "approved", "completed", "complete"}

    def rank(row: dict):
        status = str((row or {}).get("status") or "").lower()
        return (1 if status in terminal else 0,
                str((row or {}).get("updated_at") or (row or {}).get("created_at") or ""))

    best: dict[str, dict] = {}
    anonymous: list[dict] = []
    for row in records or []:
        rid = str((row or {}).get("id") or (row or {}).get("_id") or "").strip()
        if not rid:
            anonymous.append(row)
            continue
        current = best.get(rid)
        if current is None or rank(row) > rank(current):
            best[rid] = row
    return list(best.values()) + anonymous


def dedupe_return_items(items: list[dict]) -> list[dict]:
    """Remove repeated item ids inside one return; id-less lines remain distinct."""
    out: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items or []):
        item = item or {}
        iid = str(item.get("id") or item.get("return_item_id")
                  or item.get("claim_item_id") or "").strip()
        key = f"id:{iid}" if iid else f"row:{index}"
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


async def load_dup_dep():
    """Router bağımlılığı — handler'dan ÖNCE cache'i tazeler (salt-okuma)."""
    try:
        await load_dup_order_numbers()
    except Exception:
        pass
    return True
