"""
İçerik sayfaları (Hakkımızda, KVKK, İade, SSS, Mesafeli Satış, vb.) — Footer/Header/Checkout linkleri.
db.pages koleksiyonu. Public: GET /pages/{slug} (StaticPage.jsx). Admin: liste/ekle/güncelle/sil + seed.
"""
from fastapi import APIRouter, HTTPException, Depends, Request
from datetime import datetime, timezone

from .deps import db, logger, require_admin, generate_id
from activity_audit import record_admin_audit

router = APIRouter(prefix="/pages", tags=["Pages"])


@router.get("")
async def list_pages(current_user: dict = Depends(require_admin)):
    """Admin: tüm içerik sayfaları (aktif/pasif dahil)."""
    rows = await db.pages.find({}, {"_id": 0}).sort("title", 1).to_list(500)
    try:
        from legal_pages import is_pristine
        from legal_content import LEGAL_SLUGS
        for r in rows:
            r["is_seed_page"] = r.get("slug") in LEGAL_SLUGS
            r["is_default_content"] = bool(r["is_seed_page"] and is_pristine(r))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[pages] varsayılan durum hesaplanamadı: {e}")
    return rows


@router.get("/placeholders")
async def page_placeholders_help(current_user: dict = Depends(require_admin)):
    """Admin CMS editörü yardım kutusu: kullanılabilir yer tutucular + şu anki değerleri."""
    from legal_pages import PLACEHOLDER_HELP, ORDER_PLACEHOLDER_HELP, placeholder_values
    vals = await placeholder_values(db)
    return {
        "company": [{"key": k, "label": lbl, "value": vals.get(k, "")} for k, lbl in PLACEHOLDER_HELP],
        "order": [{"key": k, "label": lbl} for k, lbl in ORDER_PLACEHOLDER_HELP],
    }


@router.post("/seed-defaults")
async def seed_default_pages(request: Request, force: bool = False, slugs: str = "",
                             current_user: dict = Depends(require_admin)):
    """Varsayılan kurumsal/hukuki sayfaları kurar veya günceller (legal_content.py).
    force=false (varsayılan): eksik sayfaları ekler; yalnız EL DEĞMEMİŞ (varsayılan içerikli)
           sayfaları yeni sürüme yükseltir — düzenlenmiş sayfalara DOKUNMAZ.
    force=true: `slugs` ile verilen (boşsa tüm) varsayılan sayfaları varsayılan metne döndürür.
    Firma bilgileri metne gömülmez; sayfa sunulurken Şirket Bilgileri'nden doldurulur."""
    from legal_pages import ensure_legal_pages
    from legal_content import LEGAL_SLUGS
    only = {s.strip() for s in (slugs or "").split(",") if s.strip()}
    force_slugs = (only or set(LEGAL_SLUGS)) if force else set()
    before = await db.pages.find({"slug": {"$in": sorted(force_slugs)}}, {"_id": 0}).to_list(100) if force_slugs else []
    res = await ensure_legal_pages(db, force_slugs=force_slugs)
    if force_slugs:
        await record_admin_audit(
            db, action="page.reset_default", entity_type="page", entity_id=",".join(sorted(force_slugs)),
            before={"pages": before}, after=res, current_user=current_user, request=request,
            source="content.pages",
        )
    return {
        "ok": True, **res,
        "message": (f"{len(res['created'])} eklendi, {len(res['updated'])} güncellendi, "
                    f"{len(res['kept_customized'])} düzenlenmiş sayfa korundu"),
    }


@router.get("/{slug}")
async def get_page(slug: str, order_fields: bool = False):
    """Public: slug (veya id) ile aktif içerik sayfası. StaticPage.jsx kullanır.
    {{sirket.*}}/{{site.*}} yer tutucuları Şirket Bilgileri'nden doldurulur (DB'deki içerik ham
    kalır). order_fields=1: {{alici.*}}/{{siparis.*}} korunur — ödeme ekranı penceresi doldurur.
    Eski/alternatif adresler (ör. kvkk-aydinlatma-metni → kvkk) kanonik sayfaya çözülür."""
    from legal_pages import canonical_slug, render_page
    page = await db.pages.find_one(
        {"$or": [{"slug": slug}, {"id": slug}], "is_active": {"$ne": False}},
        {"_id": 0},
    )
    if not page:
        alt = canonical_slug(slug)
        if alt != slug:
            page = await db.pages.find_one({"slug": alt, "is_active": {"$ne": False}}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Sayfa bulunamadı")
    return await render_page(db, page, keep_order_fields=order_fields)


@router.post("")
async def create_page(payload: dict, request: Request, current_user: dict = Depends(require_admin)):
    slug = (payload.get("slug") or "").strip()
    if not slug:
        raise HTTPException(status_code=400, detail="slug zorunlu")
    if await db.pages.find_one({"slug": slug}):
        raise HTTPException(status_code=400, detail="Bu slug zaten kullanılıyor")
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": generate_id(), "title": payload.get("title", ""), "slug": slug,
        "content": payload.get("content", ""), "meta_title": payload.get("meta_title", ""),
        "meta_description": payload.get("meta_description", ""),
        "is_active": payload.get("is_active", True),
        "created_at": now, "updated_at": now,
    }
    await db.pages.insert_one(doc)
    await record_admin_audit(
        db, action="page.create", entity_type="page", entity_id=doc["id"],
        before={}, after=doc, current_user=current_user, request=request, source="content.pages",
    )
    doc.pop("_id", None)
    return doc


@router.put("/{page_id}")
async def update_page(page_id: str, payload: dict, request: Request,
                      current_user: dict = Depends(require_admin)):
    existing = await db.pages.find_one({"$or": [{"id": page_id}, {"slug": page_id}]})
    if not existing:
        raise HTTPException(status_code=404, detail="Sayfa bulunamadı")
    allowed = ("title", "slug", "content", "meta_title", "meta_description", "is_active")
    update_set = {k: payload[k] for k in allowed if k in payload}
    # DENETİM FIX: slug değişiyorsa benzersizlik kontrolü — çakışan slug ulaşılamayan sayfa yapar.
    _new_slug = (update_set.get("slug") or "").strip()
    if _new_slug and _new_slug != (existing.get("slug") or ""):
        _clash = await db.pages.find_one({"slug": _new_slug, "id": {"$ne": existing["id"]}}, {"_id": 0, "id": 1})
        if _clash:
            raise HTTPException(status_code=400, detail="Bu slug zaten kullanılıyor")
    update_set["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.pages.update_one({"id": existing["id"]}, {"$set": update_set})
    await record_admin_audit(
        db, action="page.update", entity_type="page", entity_id=existing["id"],
        before=existing, after={**existing, **update_set}, current_user=current_user,
        request=request, source="content.pages",
    )
    return {"ok": True}


@router.delete("/{page_id}")
async def delete_page(page_id: str, request: Request, current_user: dict = Depends(require_admin)):
    existing = await db.pages.find_one({"$or": [{"id": page_id}, {"slug": page_id}]}, {"_id": 0})
    res = await db.pages.delete_one({"$or": [{"id": page_id}, {"slug": page_id}]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Sayfa bulunamadı")
    await record_admin_audit(
        db, action="page.delete", entity_type="page", entity_id=(existing or {}).get("id") or page_id,
        before=existing or {}, after={}, current_user=current_user, request=request,
        source="content.pages",
    )
    return {"ok": True}
