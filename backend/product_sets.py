"""Ürün Setleri — tek tıkla birden çok ürünü sepete ekleyen "set" ürünleri.

VERİ MODELİ
  Set, `products` koleksiyonunda `product_type: "set"` olan bir üründür (kendi adı, görselleri,
  açıklaması, slug'ı, SEO alanları; "Ürün Setleri" (slug: urun-setleri) kategorisinde listelenir):
      set_items:        [{product_id, variant_id?, quantity, note?}]
      set_discount_pct: 0..90 — set bütün olarak alındığında bileşenlere uygulanan indirim
  Set ürününün `price` / `sale_price` / `stock` alanları bileşenlerden TÜRETİLİR (refresh_set):
      price      = Σ bileşen birim fiyatı × adet ("ayrı ayrı alırsanız")
      sale_price = price × (1 − %) ("set fiyatı"; % = 0 ise boş)
      stock      = stokta olan bileşenlerle kaç set çıkar (en az biri stokta değilse yine 1+,
                   çünkü tükenen bileşen sepette "değiştir" akışına düşer; hiçbiri yoksa 0)

SEPET / SİPARİŞ
  Set ürünü sepete TEK KALEM olarak girmez: "Seti Sepete Ekle" bileşenleri ayrı kalemler olarak
  ekler; her kalem `set_id` + `set_slot` (setteki orijinal bileşenin ürün id'si) taşır. Stokta
  olmayan bileşen sepete "değiştirilmesi gerekiyor" durumunda girer (satın alınamaz, toplama
  girmez); müşteri "Bu ürünü değiştir" ile bileşenin en alt kategorisinden başka ürün seçer.

SET İNDİRİMİ KURALI (sunucu-otoriter; kampanya motoru, sipariş, iade/fatura aynı kaynaktan)
  * Set indirimi yalnız setin TÜM bileşen yuvaları sepette doluysa uygulanır.
  * Yuva dolu sayılır: sepette `set_id` = set, `set_slot` = bileşen olan bir kalem varsa ve bu
    kalemin ürünü ya bileşenin kendisi ya da bileşenin EN ALT kategorisinden bir ürünse
    ("değiştir" ile seçilen yedek). Başka kategoriden ürün yuvayı dolduramaz.
  * Tam set sayısı n = min(kalem adedi // bileşen adedi). n = 0 ise indirim yok.
  * İndirim = set_discount_pct × Σ (kalem birim fiyatı × bileşen adedi × n) — yalnız set
    kalemlerine dağıtılır (applied_promotions'ta coupon_id "set:<id>").
  * Bir bileşen sepetten çıkarılırsa ya da tükenmiş bileşen değiştirilmeden bırakılırsa set
    eksik kalır → indirim düşer (kalan ürünler normal fiyatla alınabilir).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

SET_CATEGORY_SLUG = "urun-setleri"
# Sözleşme 7.2: belirlenen satış senaryolarında 100 ürünün tek işlemle sepete eklenmesi → set başına
# en az 100 bileşen (tek GET /product-sets/{id} + tek sepet güncellemesi).
MAX_SET_ITEMS = 200
# Leaf kategori seçerken yok sayılan "sanal/kampanya" kategorileri
_NON_LEAF_SLUGS = {SET_CATEGORY_SLUG, "indirimli-urunler"}


def _f(v, d=0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def unit_price(prod: dict, variant_id: Optional[str] = None) -> float:
    """Sipariş motoruyla AYNI birim fiyat — routes.orders._eff_unit_price ile birebir kural
    (geçerli indirimli fiyat, yoksa liste fiyatı + varyant farkı). Ağır routes.orders içe
    aktarımından kaçınmak için burada tekrarlanır; eşitlik testle korunur."""
    base = _f(prod.get("price"))
    sp = prod.get("sale_price")
    sp = _f(sp, None) if sp not in (None, "") else None
    if sp is not None and 0 < sp < base:
        base = sp
    adj = 0.0
    if variant_id:
        for v in prod.get("variants") or []:
            if isinstance(v, dict) and v.get("id") == variant_id:
                adj = _f(v.get("price_adjustment") or v.get("price_diff"))
                break
    return round(base + adj, 2)


def list_price(prod: dict, variant_id: Optional[str] = None) -> float:
    base = _f(prod.get("price"))
    if variant_id:
        for v in prod.get("variants") or []:
            if isinstance(v, dict) and v.get("id") == variant_id:
                base += _f(v.get("price_adjustment") or v.get("price_diff"))
                break
    return round(base, 2)


def item_stock(prod: dict, variant_id: Optional[str] = None) -> int:
    if not prod or prod.get("is_active") is False:
        return 0
    if variant_id:
        for v in prod.get("variants") or []:
            if isinstance(v, dict) and v.get("id") == variant_id:
                return max(0, int(_f(v.get("stock"))))
        return 0
    return max(0, int(_f(prod.get("stock"))))


def is_set(prod: Optional[dict]) -> bool:
    return bool(prod) and prod.get("product_type") == "set"


def clean_set_items(raw) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for it in raw or []:
        if not isinstance(it, dict):
            continue
        pid = str(it.get("product_id") or "").strip()
        if not pid or pid in seen:
            continue
        seen.add(pid)
        q = max(1, min(99, int(_f(it.get("quantity"), 1) or 1)))
        row = {"product_id": pid, "quantity": q}
        if it.get("variant_id"):
            row["variant_id"] = str(it["variant_id"])
        if it.get("note"):
            row["note"] = str(it["note"])[:120]
        out.append(row)
    return out[:MAX_SET_ITEMS]


async def _category_maps(db):
    cats = await db.categories.find({}, {"_id": 0, "id": 1, "slug": 1, "name": 1, "parent_id": 1}).to_list(10000)
    by_id = {str(c["id"]): c for c in cats if c.get("id") is not None}
    return by_id


def _depth(cid: str, by_id: dict) -> int:
    d, cur, seen = 0, by_id.get(str(cid)), set()
    while cur and cur.get("parent_id") not in (None, "", 0) and str(cur["id"]) not in seen:
        seen.add(str(cur["id"]))
        cur = by_id.get(str(cur["parent_id"]))
        d += 1
    return d


def leaf_category(prod: dict, by_id: dict) -> Optional[dict]:
    """Ürünün EN ALT (en derin) kategorisi — "Bu ürünü değiştir" buraya götürür."""
    ids = [str(c) for c in (prod.get("category_ids") or []) if c]
    if prod.get("category_id"):
        ids.insert(0, str(prod["category_id"]))
    best, best_d = None, -1
    for cid in ids:
        c = by_id.get(cid)
        if not c or c.get("slug") in _NON_LEAF_SLUGS:
            continue
        d = _depth(cid, by_id)
        if d > best_d:
            best, best_d = c, d
    return {"id": str(best["id"]), "slug": best.get("slug"), "name": best.get("name")} if best else None


def in_category(prod: dict, cat_id: str) -> bool:
    ids = {str(c) for c in (prod.get("category_ids") or []) if c}
    if prod.get("category_id"):
        ids.add(str(prod["category_id"]))
    return str(cat_id) in ids


async def set_components(db, set_doc: dict, by_id: Optional[dict] = None) -> List[Dict[str, Any]]:
    """Set bileşenleri — vitrin/sepet için zenginleştirilmiş liste (fiyat, stok, en alt kategori)."""
    items = clean_set_items(set_doc.get("set_items"))
    pids = [i["product_id"] for i in items]
    prods = {p["id"]: p for p in await db.products.find({"id": {"$in": pids}}, {"_id": 0}).to_list(MAX_SET_ITEMS + 10)} if pids else {}
    by_id = by_id if by_id is not None else await _category_maps(db)
    out = []
    for it in items:
        p = prods.get(it["product_id"])
        if not p or is_set(p):
            continue
        vid = it.get("variant_id")
        var = next((v for v in (p.get("variants") or []) if isinstance(v, dict) and v.get("id") == vid), None) if vid else None
        if vid and not var:
            vid = None
        # Varyantlı bileşende varyant seçilmemişse: stoklu ilk varyant (yoksa ilk varyant)
        if not vid and p.get("variants"):
            vs = [v for v in p["variants"] if isinstance(v, dict) and v.get("id")]
            var = next((v for v in vs if _f(v.get("stock")) > 0), vs[0] if vs else None)
            vid = var.get("id") if var else None
        stock = item_stock(p, vid)
        out.append({
            "product_id": p["id"],
            "variant_id": vid,
            "variant": ({"id": var.get("id"), "size": var.get("size"), "color": var.get("color"),
                         "stock": var.get("stock"), "price_diff": var.get("price_diff") or var.get("price_adjustment") or 0,
                         "stock_code": var.get("stock_code"), "barcode": var.get("barcode")} if var else None),
            "quantity": it["quantity"],
            "note": it.get("note", ""),
            "name": p.get("name", ""),
            "slug": p.get("slug") or p["id"],
            "image": (p.get("images") or [""])[0],
            "brand": p.get("brand", ""),
            "price": p.get("price"),
            "sale_price": p.get("sale_price"),
            "unit_price": unit_price(p, vid),
            "list_unit_price": list_price(p, vid),
            "stock": stock,
            "in_stock": stock >= it["quantity"],
            "category_id": p.get("category_id"),
            "category_ids": p.get("category_ids") or [],
            "leaf_category": leaf_category(p, by_id),
            "stock_code": p.get("stock_code"),
            "barcode": p.get("barcode"),
            "campaign_discount_percent": p.get("campaign_discount_percent") or 0,
        })
    return out


def set_pricing(components: List[dict], pct: float) -> Dict[str, Any]:
    pct = max(0.0, min(90.0, _f(pct)))
    total = round(sum(c["unit_price"] * c["quantity"] for c in components), 2)
    avail = round(sum(c["unit_price"] * c["quantity"] for c in components if c["in_stock"]), 2)
    set_price = round(total * (1 - pct / 100.0), 2)
    stocks = [c["stock"] // c["quantity"] for c in components if c["in_stock"]]
    return {
        "components_total": total,          # "Ayrı ayrı alırsanız"
        "set_price": set_price,             # "Set fiyatı"
        "savings": round(total - set_price, 2),
        "discount_pct": pct,
        "available_total": avail,           # stokta olan bileşenler
        "missing_count": sum(1 for c in components if not c["in_stock"]),
        "stock": (min(stocks) if stocks else 0),
    }


async def refresh_set(db, set_doc: dict) -> Dict[str, Any]:
    """Set ürününün türetilmiş fiyat/stok alanlarını bileşenlerden yeniden yazar."""
    comps = await set_components(db, set_doc)
    pr = set_pricing(comps, set_doc.get("set_discount_pct") or 0)
    upd = {
        "price": pr["components_total"],
        "sale_price": pr["set_price"] if pr["discount_pct"] > 0 and pr["set_price"] < pr["components_total"] else None,
        "stock": int(pr["stock"]),
        "variants": [],
    }
    if any(set_doc.get(k) != v for k, v in upd.items()):
        await db.products.update_one({"id": set_doc["id"]}, {"$set": upd})
        set_doc.update(upd)
    return {"components": comps, "pricing": pr}


async def refresh_sets_containing(db, product_ids) -> int:
    """Bileşen fiyatı/stoku değişince onu içeren setleri tazeler."""
    ids = {str(x) for x in (product_ids or []) if x}
    if not ids:
        return 0
    n = 0
    for s in await db.products.find({"product_type": "set"}, {"_id": 0}).to_list(2000):
        if any(str(i.get("product_id")) in ids for i in (s.get("set_items") or []) if isinstance(i, dict)):
            await refresh_set(db, s)
            n += 1
    return n


async def compute_set_discounts(db, items: List[dict]) -> List[Dict[str, Any]]:
    """Kampanya motoru için set indirimleri. items: [{product_id, price, qty, set_id?, set_slot?}].
    Dönüş: [{set_id, title, pct, amount, units: {kalem_index: indirimli_birim_sayısı}}]."""
    groups: Dict[str, List[int]] = {}
    for i, it in enumerate(items or []):
        sid = str((it or {}).get("set_id") or "").strip()
        if sid:
            groups.setdefault(sid, []).append(i)
    if not groups:
        return []
    sets = {s["id"]: s for s in await db.products.find(
        {"id": {"$in": list(groups)}, "product_type": "set"}, {"_id": 0}).to_list(200)}
    need = set()
    for s in sets.values():
        need.update(i["product_id"] for i in clean_set_items(s.get("set_items")))
    for idxs in groups.values():
        need.update(str(items[i].get("product_id")) for i in idxs)
    prods = {p["id"]: p for p in await db.products.find(
        {"id": {"$in": list(need)}}, {"_id": 0, "id": 1, "category_id": 1, "category_ids": 1}).to_list(2000)}
    by_id = await _category_maps(db)
    out = []
    for sid, idxs in groups.items():
        s = sets.get(sid)
        if not s or s.get("is_active") is False:
            continue
        pct = max(0.0, min(90.0, _f(s.get("set_discount_pct"))))
        slots = clean_set_items(s.get("set_items"))
        if pct <= 0 or not slots:
            continue
        chosen: Dict[int, int] = {}   # slot index → kalem index
        used = set()
        ok = True
        for k, slot in enumerate(slots):
            spid = slot["product_id"]
            orig = prods.get(spid)
            leaf = leaf_category(orig, by_id) if orig else None
            hit = None
            for i in idxs:
                if i in used:
                    continue
                it = items[i]
                if str(it.get("set_slot") or it.get("product_id")) != spid:
                    continue
                pid = str(it.get("product_id") or "")
                if pid == spid or (leaf and pid in prods and in_category(prods[pid], leaf["id"])):
                    hit = i
                    break
            if hit is None:
                ok = False
                break
            chosen[k] = hit
            used.add(hit)
        if not ok:
            continue
        n = min(int(_f(items[chosen[k]].get("qty"))) // slots[k]["quantity"] for k in chosen)
        if n < 1:
            continue
        units = {chosen[k]: slots[k]["quantity"] * n for k in chosen}
        base = sum(_f(items[i].get("price")) * u for i, u in units.items())
        amount = round(base * pct / 100.0, 2)
        if amount <= 0:
            continue
        out.append({"set_id": sid, "title": f"Set İndirimi — {s.get('name', 'Ürün Seti')} (%{pct:g})",
                    "pct": pct, "amount": amount, "units": units, "sets": n})
    return out


def apply_to_units(units_list: list, entries: List[dict]) -> None:
    """evaluate_cart_promotions'ın birim tablosunu ([kalem_index, kalan_birim_fiyat]) set
    indirimiyle küçültür → sonraki kampanyalar set-indirimli tutar üzerinden hesaplanır."""
    for e in entries:
        f = 1 - e["pct"] / 100.0
        for idx, cnt in e["units"].items():
            left = cnt
            for u in units_list:
                if left <= 0:
                    break
                if u[0] == idx:
                    u[1] = u[1] * f
                    left -= 1


async def ensure_set_category(db) -> Optional[str]:
    """"Ürün Setleri" kategorisinin id'si (yoksa None)."""
    c = await db.categories.find_one({"slug": SET_CATEGORY_SLUG}, {"_id": 0, "id": 1})
    return str(c["id"]) if c else None

