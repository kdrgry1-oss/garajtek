"""Ürün Setleri + Kapıda ödeme vitrin uçları.

Vitrin:
  GET  /api/product-sets/{id|slug}     set + bileşenler (fiyat, stok, en alt kategori) + fiyat özeti
  GET  /api/storefront/cod-info        kapıda ödeme açık mı, bedeli, alt/üst limit, kartta rozet
  POST /api/storefront/cod-check       sepet için kapıda ödeme uygun mu (ürün/kategori/limit)
  POST /api/storefront/cart-stock      sepet kalemlerinin güncel stoğu (tükenen kalem → "değiştir")
  GET  /api/storefront/alternatives    tükenen ürün için aynı EN ALT kategoriden stoklu öneriler
  POST /api/storefront/quick-order     Hızlı Sipariş: stok kodu/barkod + adet listesi tek istekte çözülür
  POST /api/storefront/cod-quote       "Kapıda Ödeme ile Sipariş Ver" tutar önizlemesi (sipariş kurallarıyla aynı)
Panel (Katalog › Ürün Setleri):
  GET/POST /api/admin/product-sets, GET/PUT/DELETE /api/admin/product-sets/{id}
  POST /api/admin/product-sets/preview  canlı fiyat/stok önizlemesi
  GET  /api/admin/product-sets/search   bileşen seçici (ad / stok kodu / barkod)
Kurallar ve veri modeli: backend/product_sets.py, backend/cod_rules.py
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from .deps import db, require_admin, require_permission, logger
import product_sets as ps
from cod_rules import cod_config, product_cod_blocked

router = APIRouter(tags=["Ürün Setleri"])


async def _find_set(ref: str):
    ref = str(ref or "").strip()
    doc = await db.products.find_one({"id": ref, "product_type": "set"}, {"_id": 0})
    if not doc:
        doc = await db.products.find_one({"slug": ref, "product_type": "set"}, {"_id": 0})
    return doc


def _public_set(doc: dict) -> dict:
    keep = ("id", "name", "slug", "images", "description", "short_description", "set_discount_pct",
            "brand", "meta_title", "meta_description", "price", "sale_price", "stock", "is_active")
    return {k: doc.get(k) for k in keep}


@router.get("/product-sets/{ref}")
async def get_product_set(ref: str):
    doc = await _find_set(ref)
    if not doc or doc.get("is_active") is False or doc.get("is_deleted"):
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    res = await ps.refresh_set(db, doc)
    return {"set": _public_set(doc), **res}


@router.get("/storefront/cod-info")
async def cod_info():
    return await cod_config(db)


@router.post("/storefront/cod-check")
async def cod_check(payload: dict):
    """payload: {product_ids: [...], subtotal}. Kasa kapıda ödemeyi buna göre gösterir;
    sipariş oluşturma (routes/orders.create_order) aynı kuralları ayrıca uygular."""
    cfg = await cod_config(db)
    if not cfg["enabled"]:
        return {"available": False, "reason": "Kapıda ödeme şu anda kullanılamıyor.", "blocked": [], "fee": cfg["fee"]}
    ids = [str(x) for x in (payload.get("product_ids") or []) if x][:200]
    prods = await db.products.find({"id": {"$in": ids}}, {"_id": 0, "id": 1, "name": 1, "cod_disabled": 1,
                                                         "catalog_fields": 1, "category_id": 1,
                                                         "category_ids": 1}).to_list(200) if ids else []
    blocked = [p.get("name") or p["id"] for p in prods if product_cod_blocked(p, cfg["excluded_category_ids"])]
    sub = float(payload.get("subtotal") or 0)
    reason = ""
    if blocked:
        reason = "Sepetinizdeki şu ürün(ler) kapıda ödemeye uygun değil: " + ", ".join(blocked[:5])
    elif cfg["min_total"] and sub < cfg["min_total"]:
        reason = f"Kapıda ödeme {cfg['min_total']:,.0f} ₺ ve üzeri siparişlerde geçerlidir.".replace(",", ".")
    elif cfg["max_total"] and sub > cfg["max_total"]:
        reason = f"Kapıda ödeme en fazla {cfg['max_total']:,.0f} ₺ tutarındaki siparişlerde geçerlidir.".replace(",", ".")
    return {"available": not reason, "reason": reason, "blocked": blocked, "fee": cfg["fee"],
            "min_total": cfg["min_total"], "max_total": cfg["max_total"]}


_CARD_FIELDS = {"_id": 0, "id": 1, "name": 1, "slug": 1, "images": 1, "price": 1, "sale_price": 1, "stock": 1,
                "variants": 1, "category_id": 1, "category_ids": 1, "brand": 1, "stock_code": 1, "barcode": 1,
                "is_active": 1, "product_type": 1, "cod_disabled": 1, "campaign_discount_percent": 1}


def _card(p: dict) -> dict:
    out = {k: p.get(k) for k in _CARD_FIELDS if k != "_id"}
    out["images"] = (p.get("images") or [])[:1]
    out["variants"] = [{"id": v.get("id"), "size": v.get("size"), "color": v.get("color"), "stock": v.get("stock"),
                        "price_diff": v.get("price_diff") or v.get("price_adjustment") or 0,
                        "barcode": v.get("barcode"), "stock_code": v.get("stock_code")}
                       for v in (p.get("variants") or []) if isinstance(v, dict) and v.get("id")]
    return out


@router.post("/storefront/cart-stock")
async def cart_stock(payload: dict):
    """Sözleşme 7.3: sepetteki ürün sipariş tamamlanmadan tükenirse kullanıcı bilgilendirilir.
    payload: {lines: [{product_id, variant_id?, quantity}]} → {items: {"pid|vid": {...}}}"""
    lines = [ln for ln in (payload.get("lines") or []) if isinstance(ln, dict) and ln.get("product_id")][:300]
    ids = list({str(ln["product_id"]) for ln in lines})
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": ids}}, {"_id": 0, "id": 1, "stock": 1, "variants": 1, "is_active": 1, "is_deleted": 1,
                                "category_id": 1, "category_ids": 1}).to_list(400)} if ids else {}
    by_id = await ps._category_maps(db) if prods else {}
    out = {}
    for ln in lines:
        pid, vid = str(ln["product_id"]), (str(ln.get("variant_id")) if ln.get("variant_id") else "")
        p = prods.get(pid)
        active = bool(p) and p.get("is_active") is not False and not p.get("is_deleted")
        stock = ps.item_stock(p, vid or None) if active else 0
        qty = max(1, int(ps._f(ln.get("quantity"), 1) or 1))
        out[f"{pid}|{vid}"] = {"stock": stock, "active": active, "available": active and stock >= 1,
                               "enough": active and stock >= qty,
                               "leaf_category": ps.leaf_category(p, by_id) if p else None}
    return {"items": out}


@router.get("/storefront/alternatives")
async def alternatives(product_id: str, limit: int = 8):
    """Sözleşme 7.4: tükenen ürün için aynı EN ALT kategoriden stokta olan ürünler."""
    p = await db.products.find_one({"id": product_id}, {"_id": 0, "id": 1, "category_id": 1, "category_ids": 1})
    if not p:
        return {"category": None, "items": []}
    leaf = ps.leaf_category(p, await ps._category_maps(db))
    if not leaf:
        return {"category": None, "items": []}
    q = {"$or": [{"category_ids": leaf["id"]}, {"category_id": leaf["id"]}], "id": {"$ne": product_id},
         "is_active": {"$ne": False}, "is_deleted": {"$ne": True}, "product_type": {"$ne": "set"}, "stock": {"$gt": 0}}
    rows = await db.products.find(q, _CARD_FIELDS).sort("sold_count", -1).limit(max(1, min(20, limit))).to_list(20)
    return {"category": leaf, "items": [_card(r) for r in rows]}


@router.post("/storefront/quick-order")
async def quick_order(payload: dict):
    """Hızlı Sipariş (sözleşme 7.2 — set dışı senaryolar): [{code, qty}] stok kodu / barkod /
    varyant barkodu ile TEK istekte çözülür; vitrin hepsini tek sepet güncellemesiyle ekler."""
    raw = [ln for ln in (payload.get("lines") or []) if isinstance(ln, dict) and str(ln.get("code") or "").strip()][:300]
    codes = list({str(ln["code"]).strip() for ln in raw})
    if not codes:
        return {"found": [], "missing": []}
    rx = [{"stock_code": c} for c in codes] + [{"barcode": c} for c in codes] + \
         [{"variants.barcode": c} for c in codes] + [{"variants.stock_code": c} for c in codes]
    prods = await db.products.find({"$or": rx, "is_active": {"$ne": False}, "is_deleted": {"$ne": True},
                                    "product_type": {"$ne": "set"}}, _CARD_FIELDS).to_list(600)
    idx = {}
    for p in prods:
        for key in (p.get("stock_code"), p.get("barcode")):
            if key:
                idx.setdefault(str(key).strip().lower(), (p, None))
        for v in p.get("variants") or []:
            for key in (v.get("barcode"), v.get("stock_code")):
                if key:
                    idx[str(key).strip().lower()] = (p, v)
    found, missing = [], []
    for ln in raw:
        code = str(ln["code"]).strip()
        hit = idx.get(code.lower())
        if not hit:
            missing.append(code)
            continue
        p, v = hit
        qty = max(1, min(999, int(ps._f(ln.get("qty") or ln.get("quantity"), 1) or 1)))
        found.append({"code": code, "quantity": qty, "product": _card(p),
                      "variant": ({"id": v.get("id"), "size": v.get("size"), "color": v.get("color"),
                                   "stock": v.get("stock"), "price_diff": v.get("price_diff") or v.get("price_adjustment") or 0,
                                   "barcode": v.get("barcode"), "stock_code": v.get("stock_code")} if v else None),
                      "stock": ps.item_stock(p, v.get("id") if v else None)})
    return {"found": found, "missing": missing}


@router.post("/storefront/cod-quote")
async def cod_quote(payload: dict):
    """Ürün sayfası "Kapıda Ödeme ile Sipariş Ver" — sipariş oluşturmayla (routes/orders.create_order)
    AYNI fiyat/kampanya/kargo/hizmet bedeli kurallarıyla tutar hesaplar ve gönderilecek kalemleri
    döner. Sipariş yine normal POST /api/orders ile (payment_method=cash_on_delivery) açılır;
    sunucu tutarı ve kuralları orada tekrar doğrular. payload: {product_id, variant_id?, quantity, email?}"""
    from .coupons import evaluate_cart_promotions
    from .settings import resolve_shipping_fee, resolve_free_shipping_threshold
    from shipping_rules import shipping_quote

    cfg = await cod_config(db)
    pid = str(payload.get("product_id") or "")
    qty = max(1, min(99, int(ps._f(payload.get("quantity"), 1) or 1)))
    prod = await db.products.find_one({"id": pid}, {"_id": 0})
    if not prod or prod.get("is_active") is False or prod.get("is_deleted"):
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    lines = []
    if ps.is_set(prod):
        comps = await ps.set_components(db, prod)
        if any(not c["in_stock"] or c["stock"] < c["quantity"] * qty for c in comps):
            return {"available": False, "reason": "Setteki bir ürün şu an stokta yok. Seti sepete ekleyip ürünü değiştirebilirsiniz."}
        for c in comps:
            lines.append({"product_id": c["product_id"], "variant_id": c["variant_id"], "quantity": c["quantity"] * qty,
                          "price": c["unit_price"], "name": c["name"], "image": c["image"],
                          "size": (c.get("variant") or {}).get("size"), "category_id": c.get("category_id"),
                          "set_id": prod["id"], "set_slot": c["product_id"]})
        check_prods = await db.products.find({"id": {"$in": [ln["product_id"] for ln in lines]}}, {"_id": 0}).to_list(300)
    else:
        vid = str(payload.get("variant_id") or "") or None
        if prod.get("variants") and not vid:
            return {"available": False, "reason": "Lütfen bir seçenek seçin."}
        stock = ps.item_stock(prod, vid)
        if stock < qty:
            return {"available": False, "reason": ("Bu ürün stokta bulunmamaktadır." if stock <= 0
                                                    else f"Bu üründen en fazla {stock} adet sipariş verebilirsiniz.")}
        var = next((v for v in prod.get("variants") or [] if v.get("id") == vid), None) if vid else None
        lines.append({"product_id": pid, "variant_id": vid, "quantity": qty, "price": ps.unit_price(prod, vid),
                      "name": prod.get("name"), "image": (prod.get("images") or [""])[0],
                      "size": (var or {}).get("size"), "category_id": prod.get("category_id")})
        check_prods = [prod]
    subtotal = round(sum(ln["price"] * ln["quantity"] for ln in lines), 2)
    reason = ""
    if not cfg["enabled"]:
        reason = "Kapıda ödeme şu anda kullanılamıyor."
    else:
        blocked = [p.get("name") for p in check_prods if product_cod_blocked(p, cfg["excluded_category_ids"])]
        if blocked:
            reason = "Bu ürün kapıda ödemeye uygun değildir: " + ", ".join(blocked[:3])
        elif cfg["min_total"] and subtotal < cfg["min_total"]:
            reason = f"Kapıda ödeme {cfg['min_total']:.0f} ₺ ve üzeri siparişlerde geçerlidir."
        elif cfg["max_total"] and subtotal > cfg["max_total"]:
            reason = f"Kapıda ödeme en fazla {cfg['max_total']:.0f} ₺ tutarındaki siparişlerde geçerlidir."
    ev = await evaluate_cart_promotions(
        cart_total=subtotal,
        items=[{"product_id": ln["product_id"], "category_id": ln.get("category_id"), "qty": ln["quantity"],
                "price": ln["price"], **({"set_id": ln["set_id"], "set_slot": ln["set_slot"]} if ln.get("set_id") else {})}
               for ln in lines],
        user_id=None, email=str(payload.get("email") or ""), entered_code="", payment_method="cash_on_delivery",
        excluded_ids=[])
    discount = min(subtotal, round(float(ev.get("total_discount") or 0), 2))
    sset = await db.settings.find_one({"id": "main"}, {"_id": 0, "shipping_fee": 1, "free_shipping_threshold": 1,
                                                       "cargo_fees": 1, "default_cargo_company": 1}) or {}
    fee = float(resolve_shipping_fee(sset) or 0)
    thr = await resolve_free_shipping_threshold(sset)
    thr = float(thr) if thr not in (None, "") else None
    sq = shipping_quote(subtotal, [discount], thr, fee, bool(ev.get("free_shipping")))
    total = round(subtotal - discount + sq["cost"] + cfg["fee"], 2)
    return {"available": not reason, "reason": reason, "lines": lines, "subtotal": subtotal, "discount": discount,
            "promotions": [{"title": a.get("title"), "discount": a.get("discount")} for a in ev.get("applied") or []
                           if float(a.get("discount") or 0) > 0],
            "shipping": sq["cost"], "cod_fee": cfg["fee"], "total": total}


# ───────────────────────────── Panel ─────────────────────────────

def _clean_payload(p: dict) -> dict:
    out = {}
    for k in ("name", "description", "short_description", "meta_title", "meta_description", "brand"):
        if k in p:
            out[k] = str(p.get(k) or "")
    if "images" in p:
        out["images"] = [str(x) for x in (p.get("images") or []) if x][:10]
    if "is_active" in p:
        out["is_active"] = bool(p.get("is_active"))
    if "is_featured" in p:
        out["is_featured"] = bool(p.get("is_featured"))
    if "set_items" in p:
        out["set_items"] = ps.clean_set_items(p.get("set_items"))
    if "set_discount_pct" in p:
        try:
            out["set_discount_pct"] = max(0.0, min(90.0, float(p.get("set_discount_pct") or 0)))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Set indirimi yüzdesi geçersiz")
    return out


async def _validate_items(items: list, self_id: str = ""):
    if len(items) < 2:
        raise HTTPException(status_code=400, detail="Bir sette en az 2 farklı ürün olmalı.")
    pids = [i["product_id"] for i in items]
    found = {p["id"]: p for p in await db.products.find({"id": {"$in": pids}},
                                                       {"_id": 0, "id": 1, "product_type": 1}).to_list(ps.MAX_SET_ITEMS + 10)}
    for pid in pids:
        if pid not in found:
            raise HTTPException(status_code=400, detail=f"Bileşen ürün bulunamadı: {pid}")
        if ps.is_set(found[pid]) or pid == self_id:
            raise HTTPException(status_code=400, detail="Bir set başka bir seti içeremez.")


@router.get("/admin/product-sets")
async def admin_list_sets(current_user: dict = Depends(require_admin)):
    out = []
    for s in await db.products.find({"product_type": "set", "is_deleted": {"$ne": True}}, {"_id": 0}).to_list(500):
        res = await ps.refresh_set(db, s)
        out.append({**_public_set(s), "set_items": s.get("set_items") or [], "pricing": res["pricing"],
                    "component_count": len(res["components"])})
    out.sort(key=lambda x: x.get("name") or "")
    return {"sets": out}


@router.get("/admin/product-sets/search")
async def admin_search_components(q: str = "", limit: int = 20, current_user: dict = Depends(require_admin)):
    q = (q or "").strip()
    query = {"product_type": {"$ne": "set"}, "is_deleted": {"$ne": True}}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"name": rx}, {"stock_code": rx}, {"barcode": rx}, {"id": q}]
    prods = await db.products.find(query, {"_id": 0, "id": 1, "name": 1, "price": 1, "sale_price": 1,
                                           "stock": 1, "images": 1, "stock_code": 1, "variants": 1,
                                           "is_active": 1}).limit(max(1, min(50, limit))).to_list(50)
    return {"items": [{
        "id": p["id"], "name": p.get("name"), "stock": p.get("stock", 0), "stock_code": p.get("stock_code"),
        "image": (p.get("images") or [""])[0], "unit_price": ps.unit_price(p), "is_active": p.get("is_active", True),
        "variants": [{"id": v.get("id"), "size": v.get("size"), "stock": v.get("stock")}
                     for v in (p.get("variants") or []) if isinstance(v, dict) and v.get("id")],
    } for p in prods]}


@router.post("/admin/product-sets/preview")
async def admin_preview(payload: dict, current_user: dict = Depends(require_admin)):
    doc = {"set_items": ps.clean_set_items(payload.get("set_items")),
           "set_discount_pct": payload.get("set_discount_pct") or 0}
    comps = await ps.set_components(db, doc)
    return {"components": comps, "pricing": ps.set_pricing(comps, doc["set_discount_pct"])}


@router.get("/admin/product-sets/{sid}")
async def admin_get_set(sid: str, current_user: dict = Depends(require_admin)):
    doc = await _find_set(sid)
    if not doc:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    res = await ps.refresh_set(db, doc)
    return {"set": {**_public_set(doc), "set_items": doc.get("set_items") or []}, **res}


async def create_set_product(data: dict, request: Request, current_user: dict, extra: dict | None = None) -> dict:
    """Seti panelin ürün oluşturma akışıyla açar (slug/kart id aynı kurallarla), sonra set
    alanlarını yazar ve türetilmiş fiyat/stoku hesaplar. Demo yükleyici de bunu kullanır."""
    from routes.products import create_product
    clean = _clean_payload(data)
    if not clean.get("name"):
        raise HTTPException(status_code=400, detail="Set adı gerekli")
    await _validate_items(clean.get("set_items") or [])
    if not clean.get("images"):
        pids = [i["product_id"] for i in clean["set_items"]]
        prods = {p["id"]: p for p in await db.products.find({"id": {"$in": pids}}, {"_id": 0, "id": 1, "images": 1}).to_list(50)}
        clean["images"] = [prods[p]["images"][0] for p in pids if (prods.get(p) or {}).get("images")][:4]
    cat_id = await ps.ensure_set_category(db)
    cats = [cat_id] if cat_id else []
    for c in data.get("extra_categories") or []:
        if c and str(c) not in cats:
            cats.append(str(c))
    res = await create_product({
        "name": clean["name"], "description": clean.get("description", ""),
        "short_description": clean.get("short_description", ""), "images": clean.get("images", []),
        "brand": clean.get("brand", ""), "price": 1, "stock": 0, "categories": cats,
        "category_id": cats[0] if cats else "", "is_active": clean.get("is_active", True),
        "is_featured": clean.get("is_featured", False), "vat_rate": 20,
    }, request, current_user)
    sid = res.get("id")
    now = datetime.now(timezone.utc).isoformat()
    await db.products.update_one({"id": sid}, {"$set": {
        "product_type": "set", "set_items": clean.get("set_items") or [],
        "set_discount_pct": clean.get("set_discount_pct", 0),
        "meta_title": clean.get("meta_title", ""), "meta_description": clean.get("meta_description", ""),
        "updated_at": now, **(extra or {})}})
    doc = await db.products.find_one({"id": sid}, {"_id": 0})
    await ps.refresh_set(db, doc)
    return doc


@router.post("/admin/product-sets")
async def admin_create_set(payload: dict, request: Request,
                           current_user: dict = Depends(require_permission("products.edit"))):
    doc = await create_set_product(payload, request, current_user)
    logger.info(f"product set created: {doc['id']}")
    return {"id": doc["id"], "slug": doc.get("slug")}


@router.put("/admin/product-sets/{sid}")
async def admin_update_set(sid: str, payload: dict, current_user: dict = Depends(require_permission("products.edit"))):
    doc = await _find_set(sid)
    if not doc:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    upd = _clean_payload(payload)
    if "set_items" in upd:
        await _validate_items(upd["set_items"], doc["id"])
    if not upd:
        return {"ok": True}
    upd["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.products.update_one({"id": doc["id"]}, {"$set": upd})
    doc.update(upd)
    await ps.refresh_set(db, doc)
    return {"ok": True, "id": doc["id"]}


@router.delete("/admin/product-sets/{sid}")
async def admin_delete_set(sid: str, current_user: dict = Depends(require_permission("products.delete"))):
    doc = await _find_set(sid)
    if not doc:
        raise HTTPException(status_code=404, detail="Set bulunamadı")
    await db.products.delete_one({"id": doc["id"], "product_type": "set"})
    return {"deleted": doc["id"]}
