"""Kapıda ödeme (COD) kuralları — vitrin gösterimi ve sipariş doğrulaması TEK kaynaktan.

  * Açık/kapalı: settings.main.payment_methods.cash_on_delivery is True (checkout ile aynı kural)
  * Hizmet bedeli: İşletme Kuralları › shipping.cod_fee
  * Alt / üst sipariş tutarı: shipping.cod_min_total / shipping.cod_max_total (0 = sınırsız)
  * Ürün bazında kapatma: product.cod_disabled (panel ürün formu "Kapıda ödemeye kapalı") veya
    eski altyapı alanı catalog_fields.URUNKAPIDAODEMEYASAKLI
  * Kategori bazında kapatma: category.cod_disabled (panel kategori formu) — alt kategoriler ve
    o kategorideki tüm ürünler (category_ids ataları kapsar) kapıda ödemeye kapanır.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

COD_METHODS = ("cash_on_delivery", "kapida", "kapida_odeme", "cod")


def _truthy(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "evet", "yes", "e", "x")
    return bool(v)


async def cod_config(db) -> Dict[str, Any]:
    from business_rules import get_rule
    s = await db.settings.find_one({"id": "main"}, {"_id": 0, "payment_methods": 1, "cod_default_applied": 1}) or {}
    if s and not s.get("cod_default_applied"):
        await ensure_cod_default(db)  # tek seferlik varsayılan (yönetici seçimi korunur)
        s = await db.settings.find_one({"id": "main"}, {"_id": 0, "payment_methods": 1}) or {}
    enabled = ((s.get("payment_methods") or {}).get("cash_on_delivery")) is True

    async def num(key, d):
        try:
            return max(0.0, float(await get_rule(db, key, d) or 0))
        except (TypeError, ValueError):
            return float(d)

    excluded = []
    if enabled:
        excluded = [str(c["id"]) for c in await db.categories.find(
            {"cod_disabled": True}, {"_id": 0, "id": 1}).to_list(2000) if c.get("id") is not None]
    return {
        "enabled": enabled,
        "fee": await num("shipping.cod_fee", 10),
        "min_total": await num("shipping.cod_min_total", 0),
        "max_total": await num("shipping.cod_max_total", 0),
        "card_badge": _truthy(await get_rule(db, "storefront.cod_card_badge", True)),
        "excluded_category_ids": excluded,
    }


def product_cod_blocked(prod: dict, excluded_category_ids: Iterable[str]) -> bool:
    if not prod:
        return False
    if _truthy(prod.get("cod_disabled")):
        return True
    if _truthy((prod.get("catalog_fields") or {}).get("URUNKAPIDAODEMEYASAKLI")):
        return True
    ex = {str(x) for x in (excluded_category_ids or [])}
    if not ex:
        return False
    cids = {str(c) for c in (prod.get("category_ids") or []) if c}
    if prod.get("category_id"):
        cids.add(str(prod["category_id"]))
    return bool(cids & ex)


async def blocked_names(db, products: List[dict]) -> List[str]:
    cfg_ex = [str(c["id"]) for c in await db.categories.find(
        {"cod_disabled": True}, {"_id": 0, "id": 1}).to_list(2000) if c.get("id") is not None]
    return [p.get("name") or p.get("id") for p in products if product_cod_blocked(p, cfg_ex)]


async def ensure_cod_default(db) -> str:
    """Açılış kancası (idempotent, tek seferlik): kapıda ödemeyi varsayılan olarak AÇAR —
    yalnız yönetici bu ayarı hiç açıkça değiştirmediyse. settings.main.cod_default_applied
    işareti yazılır; yönetici sonradan kapatırsa bir daha açılmaz.
    "Açıkça değiştirildi" = audit_logs'ta payment_methods'u değiştiren settings.update kaydı var.
    Dönüş: "enabled" | "kept" (yönetici seçimi korundu) | "done" (önceden uygulandı) | "no-settings"."""
    import json
    doc = await db.settings.find_one({"id": "main"}, {"_id": 0, "payment_methods": 1, "cod_default_applied": 1})
    if not doc:
        return "no-settings"  # ilk GET /settings varsayılanı (kapıda ödeme açık + işaret) yazar
    if doc.get("cod_default_applied"):
        return "done"
    pm = dict(doc.get("payment_methods") or {})
    explicit = False
    if "cash_on_delivery" in pm:
        async for a in db.audit_logs.find({"action": "settings.update", "entity.id": "main"}, {"_id": 0, "diff": 1}):
            if "payment_methods" in json.dumps(a.get("diff") or {}, ensure_ascii=False, default=str):
                explicit = True
                break
    upd = {"cod_default_applied": True}
    if not explicit:
        pm.setdefault("credit_card", True)
        pm.setdefault("bank_transfer", True)
        pm["cash_on_delivery"] = True
        upd["payment_methods"] = pm
    await db.settings.update_one({"id": "main"}, {"$set": upd})
    return "kept" if explicit else "enabled"
