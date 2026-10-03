"""
routes/cargo_carriers.py — Kargo firması (Aras Kargo, PTT Kargo) uçları.

  GET  /api/cargo-carriers                         → taşıyıcı listesi + varsayılan + desi/kg ayarları
  POST /api/cargo-carriers/settings                → varsayılan taşıyıcı, varsayılan desi/kg
  POST /api/cargo-carriers/{code}/test             → kayıtlı (veya formdaki) bilgilerle canlı bağlantı testi
  POST /api/cargo-carriers/orders/{id}/create      → seçili taşıyıcıda gönderi/barkod oluştur
  POST /api/cargo-carriers/orders/{id}/cancel      → taşıyıcıda iptal + sipariş kargo alanlarını temizle
  POST /api/cargo-carriers/orders/{id}/refresh     → takip sorgusu (+ shipped/delivered çevirme)
  POST /api/cargo-carriers/poll-now                → Aras/PTT toplu durum senkronu (zamanlayıcının yaptığı)
  GET  /api/cargo-carriers/poll-health             → son senkron özeti

orders.py uçları (/orders/{id}/cargo-barcode, /cargo-refresh, /cargo-label) de bu modüldeki
servise yönlenir.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from .deps import db, require_admin, require_permission

router = APIRouter(prefix="/cargo-carriers", tags=["Kargo Firmaları"])


async def _order_or_404(order_id: str) -> dict:
    order = await db.orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Sipariş bulunamadı")
    return order


@router.get("")
async def list_carriers(current_user: dict = Depends(require_admin)):
    from cargo_carriers import CARRIERS, get_carrier_settings, load_carrier_config, resolve_default_code
    settings = await get_carrier_settings(db)
    out = []
    for code, c in CARRIERS.items():
        cfg = await load_carrier_config(db, code)
        configured, env = c.is_configured(cfg), cfg.get("env", "test")
        out.append({"code": code, "key": c.key, "name": c.name, "configured": configured,
                    "env": env, "live_create": True})
    return {"carriers": out, "default_carrier": await resolve_default_code(db), "settings": settings}


@router.post("/settings")
async def save_carrier_settings(payload: dict, current_user: dict = Depends(require_permission("integrations.view"))):
    from cargo_carriers import CARRIERS, CARRIER_SETTINGS_ID, normalize_code
    upd = {"id": CARRIER_SETTINGS_ID, "updated_at": datetime.now(timezone.utc).isoformat(),
           "updated_by": current_user.get("email") or current_user.get("id")}
    if "default_carrier" in payload:
        code = normalize_code(payload.get("default_carrier") or "")
        if code and code not in CARRIERS:
            raise HTTPException(status_code=400, detail="Geçersiz kargo firması")
        upd["default_carrier"] = code
    for k in ("default_desi", "default_kg"):
        if k in payload:
            try:
                v = float(str(payload[k]).replace(",", "."))
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail=f"{k} sayısal olmalı")
            if not (0 < v <= 1000):
                raise HTTPException(status_code=400, detail=f"{k} 0-1000 arasında olmalı")
            upd[k] = v
    if "auto_sync" in payload:
        upd["auto_sync"] = bool(payload["auto_sync"])
    await db.settings.update_one({"id": CARRIER_SETTINGS_ID}, {"$set": upd}, upsert=True)
    return {"success": True, "message": "Kargo ayarları kaydedildi"}


@router.post("/{code}/test")
async def test_carrier(code: str, payload: dict = None, current_user: dict = Depends(require_admin)):
    """Kayıtlı kimlik bilgileriyle (form gönderildiyse maskesiz alanlar üzerine yazılır) canlı test."""
    from cargo_carriers import get_carrier, load_carrier_config
    from cargo_carriers.common import CarrierError
    carrier = get_carrier(code)
    if not carrier:
        raise HTTPException(status_code=404, detail="Kargo firması bulunamadı")
    cfg = await load_carrier_config(db, carrier.code)
    for k, v in ((payload or {}).get("config") or {}).items():
        if v not in (None, "", "********"):
            cfg[k] = v
    if not carrier.is_configured(cfg):
        return {"success": False, "message": f"{carrier.name}: kullanıcı/müşteri no ve şifre girilmemiş"}
    try:
        r = await carrier.test_connection(cfg)
    except CarrierError as e:
        return {"success": False, "message": f"{carrier.name}: {e.message}"}
    env_txt = "CANLI" if str(cfg.get("env")).lower() in ("prod", "canli", "live") else "TEST"
    return {"success": bool(r.get("ok")), "provider": carrier.code,
            "message": f"{carrier.name} ({env_txt}): {r.get('message')}"}


@router.post("/orders/{order_id}/create")
async def create_for_order(order_id: str, carrier: str = Query("", description="ARAS | PTT (boş = varsayılan)"),
                           current_user: dict = Depends(require_permission("orders.cargo"))):
    from routes.orders import create_cargo_barcode
    return await create_cargo_barcode(order_id=order_id, cargo_company=carrier or "AUTO", current_user=current_user)


@router.post("/orders/{order_id}/cancel")
async def cancel_for_order(order_id: str, current_user: dict = Depends(require_permission("orders.cargo"))):
    from cargo_carriers.service import cancel_order_shipment
    return await cancel_order_shipment(db, await _order_or_404(order_id), current_user)


@router.post("/orders/{order_id}/refresh")
async def refresh_for_order(order_id: str, current_user: dict = Depends(require_permission("orders.cargo"))):
    order = await _order_or_404(order_id)
    if str(order.get("cargo_provider_code") or "").upper() in ("ARAS", "PTT"):
        from cargo_carriers.service import refresh_order_tracking
        return await refresh_order_tracking(db, order)
    from routes.orders import refresh_cargo_tracking
    return await refresh_cargo_tracking(order_id=order_id, current_user=current_user)


@router.post("/poll-now")
async def poll_now(current_user: dict = Depends(require_admin)):
    from cargo_carriers.service import poll_tick
    return {"success": True, **(await poll_tick(db))}


@router.get("/poll-health")
async def poll_health(current_user: dict = Depends(require_admin)):
    return await db.settings.find_one({"id": "multi_cargo_poll_health"}, {"_id": 0}) or {}
