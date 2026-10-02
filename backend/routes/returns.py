"""
returns.py — Site iadeleri için toplu gider pusulası (İadeler sayfası).

Eskiden `/integrations/harici kanal/claims/gp-bulk-range` ucunda pazaryeri iadeleriyle
(harici kanal) tek havuzda çalışıyordu. Pazaryeri entegrasyonları kaldırıldığı için
yalnız SİTE iadeleri (customer_returns) için nötr bir modüle taşındı. Tekil pusula
kesimi `routes.orders.site_return_gider_pusulasi` ile AYNI mantığı kullanır.

Endpoint:
  POST /api/admin/returns/gp-bulk-range
"""
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException

from .deps import db, require_admin

router = APIRouter(prefix="/admin/returns", tags=["Returns"])


@router.post("/gp-bulk-range")
async def gp_bulk_by_range(payload: dict, current_user: dict = Depends(require_admin)):
    """İADE ONAY TARİHİ aralığındaki YALNIZ ONAYLANMIŞ ve pusulası HENÜZ OLMAYAN site
    iadeleri için (İADE ONAY tarihine göre sıralı) toplu gider pusulası keser.

    payload: {date_from, date_to, start_no:"085500", limit:50, dry_run:false}
    dry_run=true → kesmeden aday listesini döndürür (önizleme/kontrollü kesim)."""
    from .orders import _order_is_efatura, site_return_gider_pusulasi

    date_from = str(payload.get("date_from") or "").strip()
    date_to = str(payload.get("date_to") or "").strip()
    limit = max(1, min(int(payload.get("limit") or 50), 2000))
    dry = bool(payload.get("dry_run"))
    start_no = str(payload.get("start_no") or "").strip()
    try:
        base = int(start_no) if start_no else None
    except ValueError:
        base = None
    if not dry and base is None:
        raise HTTPException(status_code=400, detail="Başlangıç koçan numarası (start_no) zorunlu")

    def _in_range(v):
        s = str(v or "")[:10]
        if not s:
            return False
        if date_from and s < date_from:
            return False
        if date_to and s > date_to:
            return False
        return True

    # Pusulası zaten olanlar atlanır — ölçüt KOÇAN NUMARASI: numarası temizlenmiş
    # (clear-numbers) pusulalar havuza GERİ girer ve yeni sıralı numara alır.
    _has_no = {"$or": [{"number": {"$exists": True, "$ne": None}},
                       {"display_number": {"$exists": True, "$nin": ["", None]}}]}
    gp_returns = {str(g.get("return_id")) for g in await db.gider_pusulasi.find(
        {"return_id": {"$exists": True, "$ne": ""}, **_has_no},
        {"_id": 0, "return_id": 1}).to_list(None)}

    # TARİH ÖLÇÜTÜ = İADE ONAY TARİHİ: customer_returns.approval.at (yoksa created_at).
    cands = []
    async for r in db.customer_returns.find(
            {"status": {"$in": ["approved", "refunded", "partial_refunded"]}},
            {"_id": 0, "id": 1, "order_number": 1, "created_at": 1, "approval": 1,
             "refund_amount": 1, "refund_breakdown": 1}):
        rid = str(r.get("id") or "")
        if not rid or rid in gp_returns:
            continue
        _appr = str((r.get("approval") or {}).get("at") or r.get("created_at") or "")
        if not _in_range(_appr):
            continue
        # Onaydaki kargo kararı (deducted → kargoyu müşteriden kes) — GP hesabında baz alınır.
        _inc_cargo = bool((r.get("refund_breakdown") or {}).get("cargo", {}).get("mode") == "deducted")
        cands.append({"kaynak": "site", "key": rid, "siparis": r.get("order_number") or "",
                      "musteri": "", "tarih": _appr[:10], "_inc_cargo": _inc_cargo,
                      "tutar": round(float(r.get("refund_amount") or 0), 2)})

    # KATI KURAL: e-Fatura/kurumsal siparişler toplu kesim HAVUZUNDAN tamamen çıkarılır —
    # bu siparişlere gider pusulası KESİLMEZ, iade faturası gerekir.
    _onums = list({c.get("siparis") for c in cands if c.get("siparis")})
    _efatura_onums = set()
    _name_by_num = {}
    if _onums:
        async for _o in db.orders.find(
                {"order_number": {"$in": _onums}},
                {"_id": 0, "order_number": 1, "invoice_type": 1,
                 "billing_info": 1, "billing_address": 1, "shipping_address": 1, "customer_name": 1}):
            if _order_is_efatura(_o):
                _efatura_onums.add(str(_o.get("order_number")))
            _sh = _o.get("shipping_address") or {}
            _nm = (f"{_sh.get('first_name','')} {_sh.get('last_name','')}".strip()
                   or _sh.get("full_name") or _sh.get("name") or _o.get("customer_name") or "")
            if _nm:
                _name_by_num[str(_o.get("order_number"))] = _nm
    _elenen_efatura = len([c for c in cands if str(c.get("siparis")) in _efatura_onums])
    cands = [c for c in cands if str(c.get("siparis")) not in _efatura_onums]
    for c in cands:
        if not c.get("musteri"):
            c["musteri"] = _name_by_num.get(str(c.get("siparis")), "")

    cands.sort(key=lambda x: x["tarih"])  # İADE ONAY tarihine göre eskiden yeniye
    batch = cands[:limit]
    _dag = Counter(c["kaynak"] for c in cands)
    if dry:
        # Tutar GERÇEK gider pusulası hesabıyla (kesimle AYNI, preview=persist YOK) doldurulur —
        # raw refund_amount çoğu 0/yanlış. Kargo kararı onaydan (_inc_cargo) taşınır.
        for c in batch:
            try:
                _res = await site_return_gider_pusulasi(
                    c["key"], payload={"include_cargo": bool(c.get("_inc_cargo"))},
                    preview=True, current_user=current_user)
                _net = ((_res or {}).get("gider_pusulasi") or {}).get("totals", {}).get("net")
                if _net is not None:
                    c["tutar"] = round(float(_net), 2)
            except Exception:
                pass
        return {"dry_run": True, "toplam_aday": len(cands), "bu_partide": len(batch),
                "elenen_efatura": _elenen_efatura,
                "kaynak_dagilim": {"site": _dag.get("site", 0)},
                "adaylar": batch}

    kesilen, hatalar = [], []
    n = 0
    pusulalar = []  # YAZDIRMA için tam gider pusulası belgeleri (frontend 4'lü A4'e basar)
    for c in batch:
        tno = f"{base + n:06d}"
        try:
            res = await site_return_gider_pusulasi(
                c["key"], payload={"tracking_no": tno, "include_cargo": bool(c.get("_inc_cargo"))},
                preview=False, current_user=current_user)
            gp = (res or {}).get("gider_pusulasi") or {}
            kesilen.append({**c, "gp_no": gp.get("display_number") or tno,
                            "net": (gp.get("totals") or {}).get("net")})
            if gp:
                pusulalar.append({**gp, "assigned_no": tno})
            n += 1
        except HTTPException as he:
            hatalar.append({**c, "hata": str(he.detail)[:140]})
        except Exception as e:
            hatalar.append({**c, "hata": str(e)[:140]})
    next_no = f"{base + n:06d}"
    return {"success": True, "kesilen": len(kesilen), "hata": len(hatalar),
            "kalan_aday": max(0, len(cands) - len(batch)), "next_no": next_no,
            "detay": kesilen, "hatalar": hatalar[:20], "pusulalar": pusulalar}
