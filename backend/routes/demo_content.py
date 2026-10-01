"""Demo içerik — panelden yükle / kaldır (yalnız süper yönetici).

Uygulama süreci içinde çalışır → localdb tek-süreç kilidiyle çakışmaz; servisi durdurmak gerekmez.
Ayrıntı: backend/demo_content.py
"""
from fastapi import APIRouter, Depends, Request

from .deps import db, require_super_admin, logger
from activity_audit import record_admin_audit

router = APIRouter(prefix="/admin/demo-content", tags=["Demo içerik"])


@router.get("")
async def demo_content_status(current_user: dict = Depends(require_super_admin)):
    from demo_content import demo_status
    return await demo_status(db)


@router.post("")
async def demo_content_load(request: Request, current_user: dict = Depends(require_super_admin)):
    from demo_content import load_demo
    from routes.products import create_product

    async def _create(data: dict):
        return await create_product(data, request, current_user)

    res = await load_demo(db, _create)
    logger.info(f"demo content loaded: {res}")
    await record_admin_audit(db, action="demo_content.load", entity_type="demo_content", entity_id="garajtek_demo_v1",
                             before={}, after=res, current_user=current_user, request=request, source="settings.demo")
    return res


@router.delete("")
async def demo_content_remove(request: Request, current_user: dict = Depends(require_super_admin)):
    from demo_content import remove_demo
    res = await remove_demo(db)
    logger.info(f"demo content removed: {res}")
    await record_admin_audit(db, action="demo_content.remove", entity_type="demo_content", entity_id="garajtek_demo_v1",
                             before={}, after=res, current_user=current_user, request=request, source="settings.demo")
    return res
