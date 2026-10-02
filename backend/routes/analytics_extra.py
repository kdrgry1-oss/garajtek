"""
=============================================================================
analytics_extra.py — İleri Seviye Analitik + XML/JSON Feed Çıktıları
=============================================================================

AMAÇ:
  1) **RFM Müşteri Segmentasyonu** — Recency (son alışveriş), Frequency
     (sipariş sayısı), Monetary (toplam ciro) bazlı 1-5 puan. Klasik
     pazarlama modeli; VIP / Riskli / Kaybedilen / Yeni gibi gruplar için
     hedefli kampanya yapmayı sağlar.

  2) **Google Merchant Feed** — Google Shopping için XML feed. Ücretsiz
     listeleme ve Google Ads Shopping kampanyaları için zorunludur.

ENDPOINT'LER:
  GET /api/analytics-extra/rfm
  GET /api/feeds/google-merchant.xml   (public — token gerektirmez)
=============================================================================
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from datetime import datetime, timezone, timedelta
from typing import Optional
from xml.sax.saxutils import escape

from .deps import db, require_admin, tr_range_to_utc
from .report_dedup import effective_order_date_match, merge_match, load_dup_dep

router = APIRouter(tags=["Analytics Extra"], dependencies=[Depends(load_dup_dep)])


# ---------------------------------------------------------------------------
# RFM SEGMENTATION
# ---------------------------------------------------------------------------
def _rfm_segment(r: int, f: int, m: int) -> str:
    """
    Klasik RFM segment etiketleme. 555 en iyisi, 111 en kötüsü.
    Kaba kurallar; pazarlama içerik ekibinin ihtiyaçlarına göre
    kolayca genişletilebilir.
    """
    if r >= 4 and f >= 4 and m >= 4: return "VIP / Şampiyon"
    if r >= 4 and f >= 3: return "Sadık Müşteri"
    if r >= 4 and f <= 2: return "Yeni Müşteri"
    if r == 3 and f >= 3: return "Potansiyel Sadık"
    if r <= 2 and f >= 4 and m >= 4: return "Risk Altında (Kayıp Uyarısı)"
    if r <= 2 and f >= 3: return "Dikkat Edilmeli"
    if r <= 2 and f <= 2 and m <= 2: return "Kaybedilen"
    if r == 1: return "Hibernasyon"
    return "Standart"


@router.get("/analytics-extra/rfm")
async def rfm_analysis(
    lookback_days: int = Query(365, ge=30, le=1460),
    current_user: dict = Depends(require_admin),
):
    """
    Son lookback_days içindeki siparişleri kullanıcı e-postasına göre
    grupla, her kullanıcıya Recency/Frequency/Monetary quintile puanları
    (1-5) hesapla ve segment etiketi ata.

    Kullanım: Pazarlama ekibi "Risk Altında" segmentine özel kupon,
              "VIP" segmentine öncelikli teslimat teklifleri üretir.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).isoformat()
    # NET CİRO (kullanıcı isteği): iptal/tam iade/ödenmemiş siparişler sayılmaz; KISMİ iadeli
    # sipariş (partial_refunded vb.) sayılır ama onaylanan iade tutarı (customer_returns.refund_amount)
    # harcamadan düşülür → segment (VIP vb.) iptal-iade düştükten sonraki tutarla belirlenir.
    _RET_OK = ["approved", "return_approved", "refunded", "partial_refunded", "completed"]
    pipeline = [
        {"$match": {"created_at": {"$gte": cutoff},
                    "status": {"$nin": [
                        "cancelled", "cancel_refunded",
                        "awaiting_payment", "payment_failed", "failed", "pending", "payment_notified",
                        "return_requested", "return_approved", "return_in_transit",
                        "returned", "refunded"]},
                    "payment_status": {"$nin": ["expired", "failed", "refunded"]}}},
        {"$match": merge_match({})},  # eski altyapı ÇİFT kayıtları hariç
        {"$lookup": {"from": "customer_returns", "localField": "id", "foreignField": "order_id", "as": "_rets"}},
        {"$addFields": {"_net": {"$max": [0, {"$subtract": [
            {"$ifNull": ["$total", {"$ifNull": ["$total_amount", 0]}]},
            {"$sum": {"$map": {
                "input": {"$filter": {"input": "$_rets", "as": "r",
                                      "cond": {"$in": [{"$ifNull": ["$$r.status", ""]}, _RET_OK]}}},
                "as": "r", "in": {"$ifNull": ["$$r.refund_amount", 0]}}}}]}]}}},
        {"$group": {
            "_id": {"$ifNull": ["$customer_email",
                                {"$ifNull": ["$user_email",
                                             {"$ifNull": ["$email",
                                                          "$shipping_address.email"]}]}]},
            "last_order": {"$max": "$created_at"},
            "order_count": {"$sum": 1},
            "total_spent": {"$sum": "$_net"},
            "gross_spent": {"$sum": {"$ifNull": ["$total", {"$ifNull": ["$total_amount", 0]}]}},
            "name": {"$last": {"$ifNull": ["$customer_name",
                                           {"$ifNull": ["$shipping_address.full_name",
                                                        "$shipping_address.name"]}]}},
            "phone": {"$last": {"$ifNull": ["$customer_phone", "$shipping_address.phone"]}},
        }},
        {"$match": {"_id": {"$ne": None}}},
        {"$sort": {"total_spent": -1}},
        {"$limit": 5000},
    ]
    rows = await db.orders.aggregate(pipeline).to_list(length=5000)
    if not rows:
        return {"lookback_days": lookback_days, "total": 0, "segments": {}, "items": []}

    # Quintile hesapla (1-5)
    def _quintile(values, asc=True):
        """Değerlere 1..5 arası skor döner; asc=True ise düşük değer=1."""
        sorted_vals = sorted(values, reverse=not asc)
        n = len(sorted_vals)
        thresholds = [sorted_vals[int(n * q / 5)] for q in range(1, 5)] if n else []
        def score(v):
            s = 1
            for t in thresholds:
                if (v > t if asc else v < t): s += 1
            return min(5, s)
        return score

    now = datetime.now(timezone.utc)
    recency_days = []
    for r in rows:
        try:
            lo = datetime.fromisoformat(str(r["last_order"]).replace("Z", "+00:00"))
            if lo.tzinfo is None: lo = lo.replace(tzinfo=timezone.utc)
            r["recency_days"] = (now - lo).days
        except Exception:
            r["recency_days"] = lookback_days
        recency_days.append(r["recency_days"])

    freq_score_fn = _quintile([r["order_count"] for r in rows], asc=True)
    mon_score_fn = _quintile([r["total_spent"] or 0 for r in rows], asc=True)
    # Recency: daha az gün = daha iyi → asc=False
    rec_score_fn = _quintile(recency_days, asc=False)

    items = []
    seg_counts = {}
    for r in rows:
        R = rec_score_fn(r["recency_days"])
        F = freq_score_fn(r["order_count"])
        M = mon_score_fn(r["total_spent"] or 0)
        seg = _rfm_segment(R, F, M)
        seg_counts[seg] = seg_counts.get(seg, 0) + 1
        items.append({
            "email": r["_id"],
            "name": r.get("name"),
            "phone": r.get("phone"),
            "last_order": r["last_order"],
            "recency_days": r["recency_days"],
            "order_count": r["order_count"],
            "total_spent": round(r["total_spent"] or 0, 2),
            "gross_spent": round(r.get("gross_spent") or 0, 2),
            "returns_deducted": round((r.get("gross_spent") or 0) - (r["total_spent"] or 0), 2),
            "r": R, "f": F, "m": M,
            "rfm": f"{R}{F}{M}",
            "segment": seg,
        })
    items.sort(key=lambda x: (-x["m"], -x["f"], x["recency_days"]))
    return {
        "lookback_days": lookback_days,
        "total": len(items),
        "segments": seg_counts,
        "items": items,
        "net_basis": True,
        "note": "Tutarlar NET: iptal/tam iade/ödenmemiş siparişler sayılmaz, kısmi iade tutarı düşülür.",
    }


# ---------------------------------------------------------------------------
# MARKETPLACE PROFIT REPORT
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# GOOGLE MERCHANT XML FEED
# ---------------------------------------------------------------------------
@router.get("/feeds/google-merchant.xml")
async def google_merchant_feed():
    """
    Google Shopping için XML feed. Google Merchant Center tarafından
    otomatik olarak çekilmek üzere PUBLIC (token'sız). Gizli ürün
    olmasın diye status='active' filtresiyle yalnızca yayındakiler dahil.
    """
    import os
    try:
        from company import get_company as _gc
        _co = await _gc(db)
    except Exception:
        _co = {}
    site_url = (_co.get("site_url") or os.environ.get("SITE_URL") or "").rstrip("/")
    _store = _co.get("store_name") or "Mağaza"
    items_xml = []
    # Yayında olan ürünler: `is_active=True` veya `status=active` veya filtre yok.
    q = {"$or": [{"is_active": True}, {"status": "active"}, {"is_active": {"$exists": False}, "status": {"$exists": False}}]}
    async for p in db.products.find(q, {"_id": 0}).limit(5000):
        if p.get("noindex"):  # demo/içe aktarılan (noindex) ürünler feed'e girmez
            continue
        pid = p.get("id", "")
        name = p.get("name", "")
        desc = p.get("description") or name
        img = (p.get("images") or [None])[0] or ""
        brand = p.get("brand") or _store
        cat = p.get("category_name") or "Giyim"
        price = p.get("sale_price") or p.get("price") or 0
        variants = p.get("variants") or []
        total_stock = sum((v.get("stock") or 0) for v in variants) if variants else (p.get("stock") or 0)
        availability = "in_stock" if total_stock > 0 else "out_of_stock"
        gtin = p.get("barcode") or ""
        mpn = p.get("stock_code") or pid
        link = f"{site_url}/urun/{pid}"
        items_xml.append(f"""
  <item>
    <g:id>{escape(str(pid))}</g:id>
    <g:title>{escape(name)}</g:title>
    <g:description>{escape(str(desc)[:5000])}</g:description>
    <g:link>{escape(link)}</g:link>
    <g:image_link>{escape(img)}</g:image_link>
    <g:availability>{availability}</g:availability>
    <g:price>{float(price):.2f} TRY</g:price>
    <g:brand>{escape(brand)}</g:brand>
    <g:condition>new</g:condition>
    <g:product_type>{escape(cat)}</g:product_type>
    {f"<g:gtin>{escape(str(gtin))}</g:gtin>" if gtin else ""}
    <g:mpn>{escape(str(mpn))}</g:mpn>
    <g:identifier_exists>{'yes' if gtin else 'no'}</g:identifier_exists>
  </item>""")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
<channel>
  <title>{escape(_store)}</title>
  <link>{site_url}</link>
  <description>{escape(_store)} Google Merchant Product Feed</description>
  {''.join(items_xml)}
</channel>
</rss>"""
    return Response(content=xml, media_type="application/xml; charset=utf-8")
