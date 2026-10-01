"""
cargo_carriers/packages.py — Siparişin koli ölçüsünü (adet / desi / kg) hesaplar.

Öncelik:
  1) order.cargo_package = {pieces, desi, kg}  (yönetici siparişe özel girdiyse)
  2) Ürün alanları (models.Product / Ticimax şeması):
       desi = width × depth × height / 3000  (cm)  — yoksa cargo_weight (KARGOAGIRLIGI)
       kg   = product_weight (URUNAGIRLIGI) → weight → cargo_weight
     satır miktarı ile çarpılıp toplanır.
  3) Kargo ayarlarındaki varsayılan desi/kg (taşıyıcı alanı → genel Kargo Ayarları → 1).
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Optional


def _f(v) -> float:
    try:
        x = float(str(v).replace(",", "."))
        return x if x > 0 and math.isfinite(x) else 0.0
    except (TypeError, ValueError):
        return 0.0


def item_measure(product: Optional[Dict], item: Optional[Dict] = None) -> Dict[str, float]:
    """Tek ürün için (miktar 1) desi/kg. Bilinmeyen değer 0 döner."""
    p = product or {}
    it = item or {}
    w, d, h = _f(p.get("width")), _f(p.get("depth")), _f(p.get("height"))
    desi = (w * d * h / 3000.0) if (w and d and h) else _f(p.get("cargo_weight"))
    kg = _f(p.get("product_weight")) or _f(p.get("weight")) or _f(it.get("weight")) or _f(p.get("cargo_weight"))
    return {"desi": desi, "kg": kg}


def compute_package(order: Dict, products_by_id: Dict[str, Dict], *, default_desi: float = 1.0,
                    default_kg: float = 1.0) -> Dict:
    ov = order.get("cargo_package") or {}
    if ov and (_f(ov.get("desi")) or _f(ov.get("kg"))):
        return {"pieces": max(1, int(_f(ov.get("pieces")) or 1)),
                "desi": round(_f(ov.get("desi")) or default_desi, 2),
                "kg": round(_f(ov.get("kg")) or default_kg, 2), "source": "order"}
    total_desi = 0.0
    total_kg = 0.0
    unknown_desi = unknown_kg = False
    for it in order.get("items") or []:
        qty = max(1, int(_f(it.get("quantity")) or 1))
        m = item_measure(products_by_id.get(str(it.get("product_id") or "")), it)
        if m["desi"]:
            total_desi += m["desi"] * qty
        else:
            unknown_desi = True
        if m["kg"]:
            total_kg += m["kg"] * qty
        else:
            unknown_kg = True
    desi = total_desi if total_desi and not unknown_desi else max(total_desi, default_desi)
    kg = total_kg if total_kg and not unknown_kg else max(total_kg, default_kg)
    return {"pieces": 1, "desi": round(max(desi, 0.1), 2), "kg": round(max(kg, 0.1), 2),
            "source": "products" if (total_desi or total_kg) else "defaults"}


async def load_products(db, items: Iterable[Dict]) -> Dict[str, Dict]:
    ids = list({str(it.get("product_id")) for it in items or [] if it.get("product_id")})
    if not ids:
        return {}
    out: Dict[str, Dict] = {}
    proj = {"_id": 0, "id": 1, "width": 1, "depth": 1, "height": 1, "weight": 1,
            "product_weight": 1, "cargo_weight": 1}
    async for p in db.products.find({"id": {"$in": ids}}, proj):
        out[str(p.get("id"))] = p
    return out
