"""Sayfa Tasarımı v2 uçları (SPEC §5.2): taslak/yayın/revizyon, şemalar, doğrulama, medya kütüphanesi,
public site-design ve ürün kaynağı çözümleyici.

  GET    /api/page-design/schemas                    şemalar + varsayılanlar + ortak gruplar
  GET    /api/page-design/media                      (admin) son yüklenen görseller
  POST   /api/page-design/validate                   (admin) blok / düzen doğrulama (Türkçe hatalar)
  GET    /api/page-design/{page}                     (admin) {published, draft}
  PUT    /api/page-design/{page}/draft               (admin, If-Match: taslak rev) otomatik kayıt
  DELETE /api/page-design/{page}/draft               (admin) taslağı at
  POST   /api/page-design/{page}/publish             (admin) atomik yayın + revizyon
  POST   /api/page-design/{page}/install-default     (admin) şablon varsayılan düzenini taslağa yükle
  GET    /api/page-design/{page}/revisions[/{rev}]   (admin) geçmiş
  POST   /api/page-design/{page}/revisions/{rev}/restore  (admin) sürümü taslağa yükle
  GET    /api/site-design                            (public) yayındaki global alanlar
  POST   /api/page-blocks/resolve-products           (public) ürün kaynakları
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from .deps import db, logger, require_admin
from activity_audit import record_admin_audit
import pageblocks as pb
from pageblocks import store
from pageblocks.products import resolve_many

router = APIRouter(prefix="/page-design", tags=["Sayfa Tasarımı"])
site_router = APIRouter(prefix="/site-design", tags=["Sayfa Tasarımı"])
resolve_router = APIRouter(prefix="/page-blocks", tags=["CMS"])


def _user(u: dict) -> str:
    return str(u.get("email") or u.get("id") or "admin")


def _page(page: str) -> str:
    if not store.valid_page(page):
        raise HTTPException(status_code=404, detail="Geçersiz sayfa")
    return page


def _is_member(request: Request) -> bool:
    try:
        from .products import request_is_member
        return bool(request_is_member(request))
    except Exception:  # noqa: BLE001
        return False


def _is_admin_request(request: Request) -> bool:
    try:
        auth = (request.headers.get("authorization") or "").strip()
        if not auth.lower().startswith("bearer "):
            return False
        from .deps import _decode_jwt_strict
        return bool(_decode_jwt_strict(auth.split(" ", 1)[1].strip()).get("is_admin"))
    except Exception:  # noqa: BLE001
        return False


# ------------------------------------------------------------ şemalar / doğrulama / medya
@router.get("/schemas")
async def get_schemas():
    pb.load_schemas()
    blocks = {k: {"schema": s, "defaults": pb.raw_defaults(k)} for k, s in pb.block_schemas().items()}
    globs = {k: {"schema": s, "defaults": pb.raw_defaults(k)} for k, s in pb.global_schemas().items()}
    return {"version": pb.SCHEMA_VERSION, "blocks": blocks, "globals": globs, "common": pb.common_config()}


@router.get("/media")
async def media_library(limit: int = Query(60, ge=1, le=200), current_user: dict = Depends(require_admin)):
    """Medya kütüphanesi: son yüklenen görseller (yeniden kullanmak için)."""
    rows = await db.files.find({"is_deleted": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).to_list(limit * 2)
    out = []
    for r in rows:
        ct = str(r.get("content_type") or r.get("mime_type") or "")
        url = r.get("r2_url") or r.get("url") or (f"/api/upload/files/{r['storage_path']}" if r.get("storage_path") else "")
        if not url or (ct and not ct.startswith(("image/", "video/"))):
            continue
        out.append({"url": url, "name": r.get("original_name") or r.get("filename") or "", "w": r.get("width"),
                    "h": r.get("height"), "type": ct, "created_at": r.get("created_at")})
        if len(out) >= limit:
            break
    return {"items": out}


@router.post("/validate")
async def validate(payload: dict, current_user: dict = Depends(require_admin)):
    try:
        if isinstance(payload.get("block"), dict):
            clean, errors, warnings = pb.validate_block(payload["block"], strict=True)
            return {"block": clean, "errors": errors, "warnings": warnings}
        blocks, g, errors, warnings = pb.validate_layout(payload.get("blocks") or [], payload.get("global") or {},
                                                         strict=True)
        return {"blocks": blocks, "global": g, "errors": errors, "warnings": warnings}
    except pb.UnknownBlockType as e:
        raise HTTPException(status_code=422, detail=f"Bilinmeyen blok tipi: {e}") from e


# ------------------------------------------------------------ düzen
@router.get("/{page}")
async def get_layout(page: str, current_user: dict = Depends(require_admin)):
    page = _page(page)
    pub = await store.ensure(db, page)
    draft = await store.get_draft(db, page)
    g = await store.get_global(db)
    return {"published": {"rev": pub.get("rev", 0), "blocks": pub.get("blocks") or [], "global": g,
                          "published_at": pub.get("published_at"), "published_by": pub.get("published_by")},
            "draft": ({**draft, "stale": draft.get("base_rev") != pub.get("rev")} if draft else None)}


@router.put("/{page}/draft")
async def put_draft(page: str, payload: dict, request: Request, if_match: str | None = Header(None),
                    current_user: dict = Depends(require_admin)):
    page = _page(page)
    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        raise HTTPException(status_code=400, detail="blocks listesi gerekli")
    try:
        doc, conflict, errors, warnings = await store.save_draft(
            db, page, store.normalize_client_blocks(blocks), payload.get("global"),
            if_match=if_match if if_match is not None else payload.get("rev"), user=_user(current_user))
    except pb.UnknownBlockType as e:
        raise HTTPException(status_code=422, detail=f"Bilinmeyen blok tipi: {e}") from e
    if conflict is not None:
        return JSONResponse(status_code=409, content={
            "detail": "Başka bir yönetici taslakta değişiklik yaptı.", "draft": conflict})
    return {"rev": doc["rev"], "base_rev": doc["base_rev"], "updated_at": doc["updated_at"], "errors": errors,
            "warnings": warnings}


@router.delete("/{page}/draft")
async def delete_draft(page: str, request: Request, current_user: dict = Depends(require_admin)):
    page = _page(page)
    ok = await store.discard_draft(db, page)
    await record_admin_audit(db, action="page_design.discard_draft", entity_type="page_layout", entity_id=page,
                             before={}, after={}, current_user=current_user, request=request, source="content.blocks")
    return {"success": True, "deleted": ok}


@router.post("/{page}/publish")
async def publish(page: str, request: Request, if_match: str | None = Header(None),
                  current_user: dict = Depends(require_admin)):
    page = _page(page)
    before = await store.ensure(db, page)
    try:
        doc, errors, status = await store.publish(db, page, user=_user(current_user), if_match=if_match)
    except pb.UnknownBlockType as e:
        raise HTTPException(status_code=422, detail=f"Bilinmeyen blok tipi: {e}") from e
    if status != 200:
        return JSONResponse(status_code=status, content={
            "detail": errors[0]["message"] if status != 422 else "Yayınlanamadı — hataları düzeltin.",
            "errors": errors})
    try:
        from pageblocks.products import clear_cache
        clear_cache()
    except Exception:  # noqa: BLE001
        pass
    await record_admin_audit(db, action="page_design.publish", entity_type="page_layout", entity_id=page,
                             before={"rev": before.get("rev"), "blocks": len(before.get("blocks") or [])},
                             after={"rev": doc["rev"], "blocks": len(doc["blocks"])}, current_user=current_user,
                             request=request, source="content.blocks")
    return {"success": True, "rev": doc["rev"], "published_at": doc["published_at"]}


@router.post("/{page}/install-default")
async def install_default(page: str, request: Request, replace: bool = Query(True),
                          current_user: dict = Depends(require_admin)):
    page = _page(page)
    doc = await store.default_layout_draft(db, page, replace=replace, user=_user(current_user))
    return {"success": True, "draft": doc}


@router.get("/{page}/revisions")
async def revisions(page: str, current_user: dict = Depends(require_admin)):
    page = _page(page)
    await store.ensure(db, page)
    return {"items": await store.list_revisions(db, page)}


@router.get("/{page}/revisions/{rev}")
async def revision(page: str, rev: int, current_user: dict = Depends(require_admin)):
    page = _page(page)
    lay = await store.revision_layout(db, page, rev)
    if lay is None:
        raise HTTPException(status_code=404, detail="Revizyon bulunamadı")
    meta = await store.get_revision(db, page, rev)
    return {"rev": rev, "summary": meta.get("summary"), "published_at": meta.get("published_at"),
            "published_by": meta.get("published_by"), **lay}


@router.post("/{page}/revisions/{rev}/restore")
async def restore(page: str, rev: int, request: Request, current_user: dict = Depends(require_admin)):
    page = _page(page)
    res = await store.restore_revision(db, page, rev, user=_user(current_user))
    if res is None:
        raise HTTPException(status_code=404, detail="Revizyon bulunamadı")
    doc, errors, warnings = res
    await record_admin_audit(db, action="page_design.restore", entity_type="page_layout", entity_id=page,
                             before={}, after={"rev": rev}, current_user=current_user, request=request,
                             source="content.blocks")
    return {"success": True, "draft": doc, "errors": errors, "warnings": warnings}


# ------------------------------------------------------------ public
@site_router.get("")
async def get_site_design():
    await store.ensure(db, "home")
    return await store.get_global(db)


@resolve_router.post("/resolve-products")
async def resolve_products(payload: dict, request: Request):
    """{sources:[product_source…], preview?: bool} → {results:[[ürün…]…]}. 60 sn önbellek (önizlemede yok)."""
    sources = payload.get("sources") if isinstance(payload, dict) else None
    if not isinstance(sources, list):
        raise HTTPException(status_code=400, detail="sources listesi gerekli")
    no_cache = bool(payload.get("preview")) and _is_admin_request(request)
    try:
        results = await resolve_many(db, sources, member=_is_member(request), use_cache=not no_cache)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[resolve-products] {e}")
        results = [[] for _ in sources]
    return {"results": results}


@resolve_router.get("/brands")
async def catalog_brands():
    """brands_carousel `catalog` kaynağı (public): logosu olan markalar; yoksa aktif ürünlerin marka adları."""
    out, seen = [], set()
    try:
        async for b in db.brands.find({}, {"_id": 0}):
            name = str(b.get("name") or "").strip()
            logo = b.get("logo") or b.get("logo_url") or b.get("image") or ""
            if name and logo and name.lower() not in seen:
                seen.add(name.lower())
                out.append({"name": name, "logo": logo, "url": f"/arama?q={name}"})
    except Exception:  # noqa: BLE001
        pass
    if not out:
        rows = await db.products.find({"is_active": True, "is_deleted": {"$ne": True}, "brand": {"$nin": [None, ""]}},
                                      {"_id": 0, "brand": 1}).sort("created_at", -1).to_list(500)
        for r in rows:
            name = str(r.get("brand") or "").strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                out.append({"name": name, "logo": "", "url": f"/arama?q={name}"})
            if len(out) >= 30:
                break
    return {"items": out}
