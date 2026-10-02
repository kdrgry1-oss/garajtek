"""`product_source` çözümleyici — POST /api/page-blocks/resolve-products (SPEC §2.3).

Tek uç, çoklu kaynak; 60 sn bellek içi önbellek (misafir/üye ayrı). Eşlemeler:
  featured → is_featured, discounted → indirimli (sale_price < price veya koşulsuz otomatik kampanya kapsamı),
  best_sellers → sales_count desc, newest → created_at desc, top_rated → rating desc (yoksa best_sellers),
  category → category_ids (atalı liste; include_children=False ise yalnız birincil/seçili kategoriler),
  manual → product_ids sırasıyla, tag → tags, brand → brand_ids (markalar koleksiyonundan ada çevrilir).
`recently_viewed` istemcide localStorage'dan `manual` olarak çözülür.
"""
from __future__ import annotations

import hashlib
import json
import random
import time

CACHE_TTL = 60
_CACHE: dict = {}
_HEAVY = {"_id": 0, "description": 0, "catalog_fields": 0, "seo": 0, "long_description": 0, "spec_html": 0}


def _key(src: dict, member: bool) -> str:
    return hashlib.sha1((json.dumps(src, sort_keys=True) + ("m" if member else "g")).encode()).hexdigest()


def clear_cache():
    _CACHE.clear()


def _eff_stock(p: dict) -> int:
    vs = p.get("variants") or []
    if vs:
        return sum(int(v.get("stock") or 0) for v in vs if isinstance(v, dict))
    try:
        return int(p.get("stock") or 0)
    except (TypeError, ValueError):
        return 0


def _price(p: dict) -> float:
    try:
        sp = float(p.get("sale_price") or 0)
        pr = float(p.get("price") or 0)
        return sp if 0 < sp < pr else pr
    except (TypeError, ValueError):
        return 0.0


def _disc(p: dict) -> float:
    try:
        pr = float(p.get("price") or 0)
        return (pr - _price(p)) / pr if pr else 0.0
    except (TypeError, ValueError):
        return 0.0


_SORTS = {
    "newest": [("created_at", -1)], "price_asc": None, "price_desc": None, "popular": [("sales_count", -1), ("created_at", -1)],
    "name_asc": [("name", 1)],
}
_KIND_SORT = {"newest": [("created_at", -1)], "best_sellers": [("sales_count", -1), ("created_at", -1)],
              "top_rated": [("rating", -1), ("sales_count", -1)], "featured": [("created_at", -1)],
              "discounted": [("created_at", -1)], "category": [("created_at", -1)], "tag": [("created_at", -1)],
              "brand": [("created_at", -1)]}


async def _base_query(db, member: bool) -> dict:
    q = {"is_active": True, "is_deleted": {"$ne": True}}
    if not member:
        try:
            from routes.products import _members_only_cat_ids, members_only_exclusion
            mo = await _members_only_cat_ids()
            if mo:
                q["$and"] = members_only_exclusion(mo)
        except Exception:  # noqa: BLE001
            pass
    return q


async def _discount_clause(db) -> dict | None:
    try:
        from routes.products import _auto_campaigns_for_badges
        camps = await _auto_campaigns_for_badges()
    except Exception:  # noqa: BLE001
        camps = []
    ors = [{"$expr": {"$and": [{"$gt": [{"$ifNull": ["$sale_price", 0]}, 0]}, {"$lt": ["$sale_price", "$price"]}]}}]
    for c in camps:
        ac = [str(x) for x in (c.get("categories") or []) if x]
        ap = [str(x) for x in (c.get("products") or []) if x]
        if ac:
            ors.append({"category_ids": {"$in": ac}})
        if ap:
            ors.append({"id": {"$in": ap}})
        if not ac and not ap:
            return None  # genel kampanya → tüm ürünler indirimde
    return {"$or": ors}


async def _query(db, src: dict, member: bool, limit: int) -> list:
    kind = src.get("kind") or "featured"
    q = await _base_query(db, member)
    ex = [str(x) for x in src.get("exclude_ids") or []]
    if kind == "manual":
        ids = [str(x) for x in src.get("product_ids") or [] if str(x) not in ex]
        if not ids:
            return []
        rows = await db.products.find({**q, "$or": [{"id": {"$in": ids}}, {"slug": {"$in": ids}}]}, _HEAVY).to_list(len(ids) * 2)
        by = {}
        for r in rows:
            by[str(r.get("id"))] = r
            if r.get("slug"):
                by[str(r["slug"])] = r
        out, seen = [], set()
        for i in ids:
            r = by.get(i)
            if r and r.get("id") not in seen:
                seen.add(r.get("id"))
                out.append(r)
        return out
    if kind == "featured":
        q["is_featured"] = True
    elif kind == "discounted":
        dc = await _discount_clause(db)
        if dc:
            q = {"$and": [q, dc]}
    elif kind == "category":
        cids = [str(x) for x in src.get("category_ids") or [] if x]
        if not cids:
            return []
        forms = cids + [int(c) for c in cids if c.isdigit()]
        if src.get("include_children", True):
            q = {"$and": [q, {"$or": [{"category_ids": {"$in": forms}}, {"category_id": {"$in": forms}}]}]}
        else:
            q = {"$and": [q, {"$or": [{"category_id": {"$in": forms}}, {"categories": {"$in": forms}}]}]}
    elif kind == "tag":
        if not src.get("tag"):
            return []
        q["tags"] = src["tag"]
    elif kind == "brand":
        bids = [str(x) for x in src.get("brand_ids") or [] if x]
        if not bids:
            return []
        names = [b.get("name") async for b in db.brands.find({"id": {"$in": bids}}, {"_id": 0, "name": 1}) if b.get("name")]
        q["brand"] = {"$in": names or bids}
    if ex:
        q = {"$and": [q, {"id": {"$nin": ex}}]}
    sort = _SORTS.get(src.get("sort")) if src.get("sort") not in (None, "default") else None
    sort = sort or _KIND_SORT.get(kind) or [("created_at", -1)]
    fetch = max(limit * 3, 24)
    cur = db.products.find(q, _HEAVY)
    for k, d in reversed(sort):
        cur = cur.sort(k, d)
    rows = await cur.to_list(fetch)
    if kind == "top_rated" and not any(r.get("rating") for r in rows):
        rows.sort(key=lambda r: -(r.get("sales_count") or 0))
    s = src.get("sort")
    if s == "price_asc":
        rows.sort(key=_price)
    elif s == "price_desc":
        rows.sort(key=_price, reverse=True)
    elif s == "discount_desc":
        rows.sort(key=_disc, reverse=True)
    elif s == "random_daily":
        rnd = random.Random(time.strftime("%Y%m%d"))
        rnd.shuffle(rows)
    return rows


def _clean(rows: list) -> list:
    try:
        from routes.products import _strip_internal_fields
    except Exception:  # noqa: BLE001
        def _strip_internal_fields(p):
            return p
    return [_strip_internal_fields(dict(r)) for r in rows]


async def resolve_source(db, src: dict, *, member: bool = False, use_cache: bool = True) -> list:
    limit = max(1, min(48, int(src.get("limit") or 6)))
    k = _key(src, member)
    hit = _CACHE.get(k)
    if use_cache and hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    rows = await _query(db, src, member, limit)
    if src.get("exclude_out_of_stock"):
        rows = [r for r in rows if _eff_stock(r) > 0]
    else:  # vitrin kuralı: tükenenler sona
        rows = sorted(rows, key=lambda r: 0 if _eff_stock(r) > 0 else 1) if src.get("kind") != "manual" else rows
    rows = rows[:limit]
    fill = src.get("fill_with") or "none"
    if fill != "none" and len(rows) < limit:
        have = {r.get("id") for r in rows}
        extra = await _query(db, {"kind": fill, "limit": limit, "exclude_ids": list(have)}, member, limit)
        if src.get("exclude_out_of_stock"):
            extra = [r for r in extra if _eff_stock(r) > 0]
        rows += [r for r in extra if r.get("id") not in have][: limit - len(rows)]
    try:
        from routes.products import _auto_campaigns_for_badges, _apply_campaign_badge
        camps = await _auto_campaigns_for_badges()
        for r in rows:
            _apply_campaign_badge(r, camps)
    except Exception:  # noqa: BLE001
        pass
    out = _clean(rows)
    _CACHE[k] = (time.time(), out)
    if len(_CACHE) > 500:
        for kk in sorted(_CACHE, key=lambda x: _CACHE[x][0])[:100]:
            _CACHE.pop(kk, None)
    return out


async def resolve_many(db, sources: list, *, member: bool = False, use_cache: bool = True) -> list:
    from . import _clean_source, _Ctx  # noqa: PLC0415
    ctx = _Ctx(False)
    out = []
    for i, s in enumerate((sources or [])[:30]):
        norm = _clean_source(s, {"max_limit": 48}, f"sources[{i}]", [], ctx)
        out.append(await resolve_source(db, norm, member=member, use_cache=use_cache))
    return out
