"""URL'den Ürün Aktar (Katalog) — referans mağaza sayfalarından GEÇİCİ demo ürünleri içe aktarır.

Uçlar (yalnız yönetici + `products.url_import` yetkisi; süper yönetici her yetkiyi geçer):
  GET    /api/admin/url-import/status            içe aktarılan ürün/görsel sayısı + çalışan iş
  POST   /api/admin/url-import/jobs              işi başlatır (arka plan) → {job_id}
  GET    /api/admin/url-import/jobs              son işler (özet)
  GET    /api/admin/url-import/jobs/{id}         ilerleme (panel 1,5 sn'de bir yoklar)
  POST   /api/admin/url-import/jobs/{id}/cancel  iptal isteği
  DELETE /api/admin/url-import/products          url_import_v1 ürünlerini + görsellerini siler
Ayrıntı: backend/url_import/ ve docs/URL_IMPORT.md
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from .deps import db, logger, require_permission
from activity_audit import record_admin_audit

router = APIRouter(prefix="/admin/url-import", tags=["URL'den Ürün Aktar"])
PERM = "products.url_import"
require_url_import = require_permission(PERM)  # testler dependency_overrides ile değiştirir


@router.get("/status")
async def url_import_status(current_user: dict = Depends(require_url_import)):
    from url_import.job import import_status
    return await import_status(db)


@router.post("/jobs")
async def url_import_start(payload: dict, request: Request, current_user: dict = Depends(require_url_import)):
    from url_import.fetcher import BlockedURL
    from url_import.job import start_job, validate_options
    from routes.products import create_product
    from routes.upload import delete_stored_file, store_image_bytes

    try:
        opts = validate_options(payload or {})
    except (ValueError, BlockedURL) as e:
        raise HTTPException(status_code=400, detail=str(e))
    if opts["category_id"]:
        if not await db.categories.find_one({"id": opts["category_id"]}, {"_id": 1}):
            raise HTTPException(status_code=400, detail="Seçilen kategori bulunamadı")

    async def _create(data: dict):
        return await create_product(data, request, current_user)

    try:
        job_id = await start_job(db, opts, create_product=_create, store_image=store_image_bytes,
                                 delete_file=delete_stored_file, user=current_user)
    except RuntimeError as e:
        raise HTTPException(status_code=409, detail=str(e))
    logger.info(f"url import started: {job_id} ({len(opts['urls'])} url)")
    await record_admin_audit(db, action="url_import.start", entity_type="url_import", entity_id=job_id,
                             before={}, after={"urls": opts["urls"][:20], "options": {k: v for k, v in opts.items()
                                                                                      if k != "urls"}},
                             current_user=current_user, request=request, source="catalog.url_import")
    return {"job_id": job_id}


@router.get("/jobs")
async def url_import_jobs(current_user: dict = Depends(require_url_import)):
    rows = await db.url_import_jobs.find({}, {"_id": 0, "id": 1, "status": 1, "created_at": 1, "finished_at": 1,
                                             "counters": 1, "created_by": 1}).sort("created_at", -1).to_list(20)
    return {"jobs": rows}


@router.get("/jobs/{job_id}")
async def url_import_job(job_id: str, current_user: dict = Depends(require_url_import)):
    from url_import.job import get_job
    doc = await get_job(db, job_id)
    if not doc:
        raise HTTPException(status_code=404, detail="İş bulunamadı")
    return doc


@router.post("/jobs/{job_id}/cancel")
async def url_import_cancel(job_id: str, current_user: dict = Depends(require_url_import)):
    r = await db.url_import_jobs.update_one({"id": job_id}, {"$set": {"cancel_requested": True}})
    if not getattr(r, "matched_count", 1):
        raise HTTPException(status_code=404, detail="İş bulunamadı")
    return {"ok": True}


@router.delete("/products")
async def url_import_remove(request: Request, current_user: dict = Depends(require_url_import)):
    from url_import.job import remove_imports, running_job_id
    from routes.upload import delete_stored_file
    if running_job_id():
        raise HTTPException(status_code=409, detail="Çalışan bir içe aktarma işi var; bitmesini bekleyin veya iptal edin")
    res = await remove_imports(db, delete_stored_file)
    logger.info(f"url imports removed: {res}")
    await record_admin_audit(db, action="url_import.remove", entity_type="url_import", entity_id="url_import_v1",
                             before={}, after=res, current_user=current_user, request=request,
                             source="catalog.url_import")
    return res
