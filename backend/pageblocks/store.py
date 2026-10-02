"""Sayfa düzeni depolama: page_layouts (yayın + taslak), page_layout_revisions (son 50 + rev 0 yedek),
page_blocks aynası ve settings.site_design (global alanlar). SPEC §5.2."""
from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone

from . import (
    TOP_BAR_TYPES, all_fields, apply_schedule, assign_item_ids, deep_merge, default_global, default_home, get_schema,
    global_schemas, instantiate, public_block, validate_layout, with_defaults,
)
from .migrations import migrate_block, run_migration, _category_ctx

MAX_REVISIONS = 50
PAGE_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,39}$")

_ensured = set()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def valid_page(page: str) -> bool:
    return bool(PAGE_RE.match(str(page or "")))


async def ensure(db, page: str = "home") -> dict:
    """Geçişi (bir kez) çalıştırır; sayfanın yayın belgesini döner (yoksa varsayılanla oluşturur)."""
    if "migration" not in _ensured:
        try:
            await run_migration(db)
        finally:
            _ensured.add("migration")
    doc = await db.page_layouts.find_one({"id": f"{page}:published"}, {"_id": 0})
    if doc:
        return doc
    blocks = default_home() if page == "home" else []
    for i, b in enumerate(blocks, start=1):
        b["sort_order"] = i
        b["page"] = page
    doc = {"id": f"{page}:published", "page": page, "rev": 0 if page != "home" else 1, "blocks": blocks,
           "global": {}, "updated_at": now_iso(), "updated_by": "sistem", "published_at": now_iso()}
    await db.page_layouts.replace_one({"id": doc["id"]}, doc, upsert=True)
    if blocks:
        await _mirror(db, page, blocks)
    return doc


async def get_global(db) -> dict:
    """Yayındaki global alanlar (varsayılanlarla doldurulmuş)."""
    doc = await db.settings.find_one({"id": "site_design"}, {"_id": 0}) or {}
    pub = doc.get("published") if isinstance(doc.get("published"), dict) else {}
    out = {}
    for k in global_schemas():
        out[k] = with_defaults(k, pub.get(k) or {})
    return out


async def get_draft(db, page: str):
    return await db.page_layouts.find_one({"id": f"{page}:draft"}, {"_id": 0})


async def save_draft(db, page: str, blocks: list, global_: dict | None, *, if_match, user: str):
    """Taslağı yazar. Dönüş: (doküman | None, çakışma_dokümanı | None, hatalar, uyarılar)."""
    pub = await ensure(db, page)
    cur = await get_draft(db, page)
    if cur is not None and str(if_match or "") != str(cur.get("rev")):
        return None, cur, [], []
    clean, g, errors, warnings = validate_layout(blocks, global_ if global_ is not None else
                                                 (cur or {}).get("global") or await get_global(db))
    rev = int((cur or {}).get("rev") or 0) + 1
    doc = {"id": f"{page}:draft", "page": page, "rev": rev,
           "base_rev": (cur or {}).get("base_rev", pub.get("rev", 0)), "blocks": clean, "global": g,
           "updated_at": now_iso(), "updated_by": user}
    if cur is None:
        await db.page_layouts.insert_one(dict(doc))
    else:
        res = await db.page_layouts.update_one({"id": f"{page}:draft", "rev": cur.get("rev")}, {"$set": doc})
        if not res.matched_count:  # yarış: arada başka yazım
            return None, await get_draft(db, page), [], []
    return doc, None, errors, warnings


async def discard_draft(db, page: str) -> bool:
    res = await db.page_layouts.delete_one({"id": f"{page}:draft"})
    return bool(res.deleted_count)


def _summary(old_blocks, new_blocks) -> str:
    o = {b.get("id"): b for b in old_blocks or []}
    n = {b.get("id"): b for b in new_blocks or []}
    added = [i for i in n if i not in o]
    removed = [i for i in o if i not in n]
    changed = [i for i in n if i in o and json.dumps(n[i].get("settings"), sort_keys=True) != json.dumps(o[i].get("settings"), sort_keys=True)
               or (i in o and (n[i].get("is_active") != o[i].get("is_active") or n[i].get("title") != o[i].get("title")))]
    moved = [i for i in n if i in o] != [i for i in o if i in n]
    parts = []
    if changed:
        parts.append(f"{len(changed)} blok değişti")
    if added:
        parts.append(f"{len(added)} blok eklendi")
    if removed:
        parts.append(f"{len(removed)} blok silindi")
    if moved:
        parts.append("sıra değişti")
    return ", ".join(parts) or "Genel alanlar / küçük değişiklik"


async def _mirror(db, page: str, blocks: list):
    q = {"page": page} if page != "home" else {"$or": [{"page": "home"}, {"page": None}, {"page": {"$exists": False}}]}
    await db.page_blocks.delete_many(q)
    for b in blocks:
        await db.page_blocks.insert_one({**copy.deepcopy(b), "page": page})


async def publish(db, page: str, *, user: str, if_match=None, blocks=None, global_=None):
    """Taslağı (veya verilen düzeni) doğrular ve TEK yazımla yayına alır. Dönüş: (doc, hatalar, durum)."""
    pub = await ensure(db, page)
    draft = await get_draft(db, page)
    if blocks is None:
        if not draft:
            return None, [{"message": "Yayınlanacak taslak yok."}], 400
        if if_match is not None and str(if_match) != str(draft.get("rev")):
            return None, [{"message": "Taslak başka bir yönetici tarafından değiştirildi."}], 409
        blocks, global_ = draft.get("blocks") or [], draft.get("global") or {}
    clean, g, errors, _w = validate_layout(blocks, global_ or await get_global(db), strict=True)
    if errors:
        return None, errors, 422
    last = await db.page_layout_revisions.find({"page": page}, {"_id": 0, "rev": 1}).sort("rev", -1).limit(1).to_list(1)
    rev = max(int(pub.get("rev") or 0), int(last[0]["rev"]) if last else 0) + 1
    ts = now_iso()
    for b in clean:
        b["page"] = page
    doc = {"id": f"{page}:published", "page": page, "rev": rev, "blocks": clean, "global": g,
           "updated_at": ts, "updated_by": user, "published_at": ts, "published_by": user}
    await db.page_layouts.replace_one({"id": doc["id"]}, doc, upsert=True)  # atomik geçiş
    await db.page_layout_revisions.insert_one({
        "id": f"{page}:rev:{rev}", "page": page, "rev": rev, "blocks": clean, "global": g, "published_at": ts,
        "published_by": user, "summary": _summary(pub.get("blocks"), clean)})
    revs = await db.page_layout_revisions.find({"page": page, "rev": {"$gt": 0}}, {"_id": 0, "rev": 1}).sort("rev", -1).to_list(None)
    for r in revs[MAX_REVISIONS:]:
        await db.page_layout_revisions.delete_one({"page": page, "rev": r["rev"]})
    await db.settings.update_one({"id": "site_design"}, {"$set": {"published": g, "rev": rev, "updated_at": ts,
                                                                  "updated_by": user}}, upsert=True)
    await _mirror(db, page, clean)
    await db.page_layouts.delete_one({"id": f"{page}:draft"})
    _PUBLIC_CACHE.clear()
    return doc, [], 200


async def list_revisions(db, page: str) -> list:
    rows = await db.page_layout_revisions.find({"page": page}, {"_id": 0, "blocks": 0, "global": 0}).sort("rev", -1).to_list(None)
    return rows


async def get_revision(db, page: str, rev: int):
    return await db.page_layout_revisions.find_one({"page": page, "rev": rev}, {"_id": 0})


async def revision_layout(db, page: str, rev: int):
    """Revizyonun v2 düzeni (rev 0 ham ise yeniden dönüştürülür)."""
    r = await get_revision(db, page, rev)
    if not r:
        return None
    if r.get("raw"):
        from .migrations import migrate_page, migrate_site_design
        ctx = await _category_ctx(db)
        blocks = migrate_page(r.get("blocks") or [], ctx, page)
        g = r.get("global") or {}
        glob = migrate_site_design(g.get("site_menus"), g.get("footer")) if page == "home" else await get_global(db)
        return {"blocks": blocks, "global": glob}
    return {"blocks": r.get("blocks") or [], "global": r.get("global") or await get_global(db)}


async def restore_revision(db, page: str, rev: int, *, user: str):
    lay = await revision_layout(db, page, rev)
    if lay is None:
        return None
    pub = await ensure(db, page)
    cur = await get_draft(db, page)
    clean, g, errors, warnings = validate_layout(lay["blocks"], lay["global"])
    doc = {"id": f"{page}:draft", "page": page, "rev": int((cur or {}).get("rev") or 0) + 1,
           "base_rev": pub.get("rev", 0), "blocks": clean, "global": g, "updated_at": now_iso(), "updated_by": user,
           "restored_from": rev}
    await db.page_layouts.replace_one({"id": doc["id"]}, doc, upsert=True)
    return doc, errors, warnings


async def default_layout_draft(db, page: str, *, replace: bool, user: str):
    """Şablon varsayılan ana sayfasını taslağa yükler (replace: üst barlar dışındakileri değiştirir)."""
    pub = await ensure(db, page)
    cur = await get_draft(db, page) or {}
    base = cur.get("blocks") if cur else pub.get("blocks")
    base = copy.deepcopy(base or [])
    if replace:
        base = [b for b in base if b.get("type") in TOP_BAR_TYPES]
    blocks = base + default_home()
    clean, g, errors, warnings = validate_layout(blocks, cur.get("global") or await get_global(db))
    doc = {"id": f"{page}:draft", "page": page, "rev": int(cur.get("rev") or 0) + 1,
           "base_rev": cur.get("base_rev", pub.get("rev", 0)), "blocks": clean, "global": g,
           "updated_at": now_iso(), "updated_by": user}
    await db.page_layouts.replace_one({"id": doc["id"]}, doc, upsert=True)
    return doc


# ------------------------------------------------------------ vitrin
_PUBLIC_CACHE: dict = {}


async def public_blocks(db, page: str, *, is_member: bool = False) -> list:
    """Yalnız yayındaki + aktif + zamanı gelmiş + hedef kitleye uygun bloklar."""
    pub = await ensure(db, page)
    blocks = []
    for b in pub.get("blocks") or []:
        if b.get("is_active") is False or not get_schema(b.get("type")):
            continue
        st = b.get("settings") or {}
        if st.get("_legacy"):
            continue
        aud = (st.get("_visibility") or {}).get("audience") or "all"
        if (aud == "members" and not is_member) or (aud == "guests" and is_member):
            continue
        blocks.append(b)
    out = []
    for b in apply_schedule(blocks):
        st = dict(b["settings"])
        st.pop("_migration_errors", None)
        out.append(public_block({**b, "settings": st, "page": page}))
    return out


def normalize_client_blocks(blocks) -> list:
    """İstemciden gelen bloklara eksik `_id`'leri verir (taslak kayıtta da kalıcı olsun)."""
    out = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        s = get_schema(b.get("type"))
        if s and isinstance(b.get("settings"), dict) and not b["settings"].get("_legacy"):
            assign_item_ids(all_fields(s), b["settings"])
        out.append(b)
    return out


__all__ = ["ensure", "get_global", "get_draft", "save_draft", "discard_draft", "publish", "list_revisions",
           "get_revision", "revision_layout", "restore_revision", "default_layout_draft", "public_blocks",
           "valid_page", "instantiate", "default_global", "deep_merge", "migrate_block"]
