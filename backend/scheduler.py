"""
Application-level background scheduler (APScheduler).
Runs auto-cancellation of unpaid orders, etc.
"""
import os
import asyncio
import os
import time
import logging
from datetime import datetime, timezone, timedelta
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler


# Periyodik stok/fiyat senkronları için HAFİF ürün projeksiyonu: fiyat/stok/SKU mantığının
# kullanmadığı büyük alanlar hariç (görseller, açıklamalar, Ticimax ham alanları, SEO metinleri).
_LIGHT_PRODUCT_PROJ = {"_id": 0, "images": 0, "description": 0, "short_description": 0,
                       "long_description": 0, "ticimax_fields": 0, "seo_description": 0,
                       "meta_description": 0, "size_table_html": 0, "video_url": 0, "videos": 0}

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


HAVALE_METHOD_RX = {"$regex": r"^(transfer|havale|bank_transfer|eft|havale_eft|banka_havale|bank|banka|havale/eft|havale_or_eft)$",
                    "$options": "i"}


# Geçmişe dönük alt sınır (kullanıcı kararı): 1 Haziran 2026'dan itibaren tüm ödenmemiş havale
# siparişleri kural kapsamında; daha eskilere dokunulmaz.
HAVALE_SWEEP_SINCE = "2026-06-01"
# Kapsam (kullanıcı kararı): 'Ödeme Bildirimi' (payment_notified) durumundakiler de — personel
# 72 saat içinde ödemeyi ONAYLAMADIYSA — otomatik iptal edilir.
HAVALE_UNPAID_STATUSES = ["pending", "awaiting_payment", "payment_notified"]


def havale_unpaid_query(cutoff_dt):
    """Süresi dolmuş ÖDENMEMİŞ/ONAYLANMAMIŞ havale/EFT siparişleri (geçmişe dönük dahil).
    created_at hem ISO string hem datetime olarak saklanmış olabilir → ikisini de yakala;
    payment_method varyantları büyük/küçük harften bağımsız."""
    from datetime import datetime as _dt
    cutoff_iso = cutoff_dt.isoformat()
    since_dt = _dt.fromisoformat(HAVALE_SWEEP_SINCE).replace(tzinfo=timezone.utc)
    return {
        "payment_status": {"$nin": ["paid", "expired", "refunded"]},
        "status": {"$in": HAVALE_UNPAID_STATUSES},
        "payment_method": HAVALE_METHOD_RX,
        "platform": {"$nin": ["trendyol", "hepsiburada", "amazon", "n11", "etsy"]},
        "$or": [{"created_at": {"$lt": cutoff_iso, "$gte": HAVALE_SWEEP_SINCE}},
                {"created_at": {"$lt": cutoff_dt, "$gte": since_dt}}],
    }


async def auto_cancel_unpaid_havale_orders(limit: int = 0):
    """Cancel havale/transfer orders that remain unpaid after 72 hours and restock.
    Geçmişe dönük çalışır: kuralı aşan TÜM bekleyen havale siparişleri (kaç günlük olursa olsun)."""
    from routes.deps import db  # lazy import
    from routes.orders import _restock_order_once
    import business_rules as _BR

    cancelled = 0
    _started = datetime.now(timezone.utc)
    _matched = 0
    _err = ""
    try:
        # AYAR: süre admin panelinden (İşletme Kuralları) yönetilir; varsayılan 72 saat.
        _hrs = int(await _BR.get_rule(db, "order.havale_cancel_hours", 72) or 72)
        cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=_hrs)
        query = havale_unpaid_query(cutoff_dt)
        try:
            _matched = await db.orders.count_documents(query)
        except Exception:
            _matched = -1
        cur = db.orders.find(query, {"_id": 0})
        if limit:
            cur = cur.limit(limit)
        async for order in cur:
            try:
                # O16: Önce durumu güncelle, SONRA idempotent iade yap.
                # TOCTOU koruması (D1 fix): sorgu ile update arasında müşteri ödemiş/dekont
                # bildirmiş olabilir. Filtreye payment_status != paid + status re-check ekle;
                # matched_count 0 ise (arada ödendi/durum değişti) İPTAL DE STOK GERİ DE YAPMA
                # → "72. saatte ödeyen müşterinin siparişi iptal edilip stoğu geri eklenmesi" biter.
                res = await db.orders.update_one(
                    {"id": order["id"],
                     "payment_status": {"$nin": ["paid", "expired", "refunded"]},
                     "status": {"$in": HAVALE_UNPAID_STATUSES}},
                    {"$set": {
                        "status": "cancelled",
                        "payment_status": "expired",
                        "cancel_reason": (f"{_hrs} saat içinde havale ödemesi onaylanmadı (otomatik iptal)"
                                          if order.get("status") == "payment_notified"
                                          else f"{_hrs} saat içinde havale ödemesi yapılmadı (otomatik iptal)"),
                        "auto_cancelled": True,
                        "cancelled_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }}
                )
                if res.matched_count == 0:
                    continue  # arada ödendi / dekont bildirildi / durum değişti — dokunma
                await _restock_order_once(order, "havale_auto_cancel")
                cancelled += 1
                # Müşteriye bildirim: "Siparişiniz ödeme yapılmadığı için iptal edildi" (SMS+e-posta).
                # Standart 'order_cancelled' event'i (Ayarlar → Bildirimler → 'Sipariş İptal Edildi').
                try:
                    from notification_service import send_notification
                    from routes.orders import _order_notify_vars
                    _addr = order.get("shipping_address") or {}
                    _phone = _addr.get("phone") or order.get("phone")
                    _email = _addr.get("email") or order.get("email")
                    _ch = None
                    _label = "İptal Edildi"
                    try:
                        from order_statuses import get_status_config, customer_label_for
                        _cfg = await get_status_config(db)
                        _nz = (_cfg.get("notify") or {}).get("cancelled") or {}
                        _ch = [c for c in ("sms", "email") if _nz.get(c)] or None
                        _label = customer_label_for("cancelled")
                    except Exception:
                        pass
                    if _ch is None:
                        _ch = (["email"] if _email else []) + (["sms"] if _phone else [])
                    _vars = await _order_notify_vars(
                        order, status_label=_label,
                        cancel_reason="72 saat içinde havale ödemesi yapılmadı",
                    )
                    if _ch:
                        await send_notification(
                            db, "order_cancelled",
                            to_phone=_phone, to_email=_email,
                            variables=_vars, channels=_ch,
                        )
                except Exception as _e_notif:
                    logger.warning(f"[scheduler] havale-cancel notif failed for {order.get('order_number')}: {_e_notif}")
            except Exception as e_item:
                logger.error(f"Failed to cancel order {order.get('order_number')}: {e_item}")
        if cancelled:
            logger.info(f"[scheduler] Auto-cancelled {cancelled} unpaid havale orders (>{_hrs}h)")
    except Exception as e:
        _err = str(e)[:300]
        logger.exception(f"[scheduler] auto_cancel_unpaid_havale_orders failed: {e}")
    # Sağlık kaydı (teşhis): son çalışma, eşleşen aday, iptal edilen, hata → önizleme ucunda görünür.
    try:
        await db.settings.update_one(
            {"id": "havale_sweep_health"},
            {"$set": {"id": "havale_sweep_health", "last_run_at": _started.isoformat(),
                      "last_finish_at": datetime.now(timezone.utc).isoformat(),
                      "matched": _matched, "cancelled": cancelled, "error": _err}},
            upsert=True)
    except Exception:
        pass
    return cancelled


async def expire_stale_site_return_requests():
    """Süresi dolan SİTE iade taleplerini kapatır ve siparişi NORMALE döndürür.

    Sorun: müşteri siteden iade talebi açınca sipariş "return_requested"a geçiyor ve
    iade sayfasında duruyor. Müşteri ürünü hiç kargoya vermezse kayıt orada ASILI
    kalıyordu — iade hakkı süresi dolduğu hâlde satış "iade" gibi görünüyor, ciroya
    girmiyor, sipariş listesinde çıkmıyordu.
    Mevcut mekanizma yetersizdi: scheduler'daki kargo yoklaması iade KAYDINI "expired"
    yapıyor ama SİPARİŞE HİÇ DOKUNMUYOR (order.status "return_requested" kalıyor);
    üstelik yalnız MNG entegrasyonu AÇIKSA ve kayıt 45 günden yeniyse çalışıyor.

    Bu iş: kargoya HİÇ VERİLMEMİŞ ve süresi dolmuş talepleri kapatır, siparişi iade
    öncesi durumuna (prev_status, yoksa "delivered") döndürür. Böylece satış tamamlanmış
    normal sipariş olarak değerlendirilir — panelde sipariş listesinde görünür, ciroya
    girer, iade sayfasından düşer.

    PARAYA DOKUNMAZ: tahsilat, iade tutarı, stok ve fatura alanları DEĞİŞMEZ. Kargoya
    verilmiş (in_transit/received/...), onaylanmış ya da parası iade edilmiş hiçbir kayıt
    bu işten ETKİLENMEZ. Durum güncellemesi koşulludur (TOCTOU: yalnız hâlâ
    return_requested ise) ve idempotenttir."""
    from routes.deps import db  # lazy import
    import business_rules as _BR
    try:
        _days = int(await _BR.get_rule(db, "return.stale_request_days", 14) or 14)
        if _days <= 0:
            return
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=_days)).isoformat()
        now_iso = now.isoformat()
        # Kargoya verilmemiş sayılan iade kayıt durumları
        _PRE_SHIP = ["created", "expired"]
        # İlerlemiş (asla dokunulmayacak) durumlar — aynı siparişte biri varsa atlanır
        _PROGRESSED = ["in_transit", "received", "returned", "approved",
                       "refunded", "partial_refunded", "rejected"]
        # Siparişin geri döndürülebileceği durumlar. DİKKAT: "completed" çekirdek durum
        # kataloğunda YOK (order_statuses.py) — oraya döndürmek panelde tanınmayan durum
        # bırakırdı. Katalogda bulunan tamamlanmış-satış durumları kullanılır; başka her
        # şeyde iade-iptal akışının kullandığı güvenli varsayılana ("delivered") düşülür.
        _RESTORE_OK = ("delivered", "shipped", "undelivered")
        kapanan, atlanan = 0, 0
        cur = db.customer_returns.find(
            {"status": {"$in": _PRE_SHIP}, "created_at": {"$lt": cutoff}},
            {"_id": 0, "id": 1, "order_id": 1, "order_number": 1, "status": 1,
             "created_at": 1, "approval": 1, "refund_amount": 1})
        async for rec in cur:
            try:
                o = await db.orders.find_one(
                    {"id": rec.get("order_id")},
                    {"_id": 0, "id": 1, "order_number": 1, "status": 1, "payment_status": 1,
                     "return_request": 1, "refund_paid_at": 1})
                if not o or o.get("status") != "return_requested":
                    continue                      # sipariş başka duruma geçmiş → DOKUNMA
                # Para hareketi olmuş mu? (onay / iade tutarı / iade ödemesi)
                if (rec.get("approval") or rec.get("refund_amount")
                        or o.get("refund_paid_at")
                        or str(o.get("payment_status") or "") in ("refunded", "partial_refunded")):
                    atlanan += 1
                    continue
                # Aynı siparişte İLERLEMİŞ başka bir iade kaydı var mı?
                if await db.customer_returns.find_one(
                        {"order_id": rec.get("order_id"), "status": {"$in": _PROGRESSED}},
                        {"_id": 0, "id": 1}):
                    atlanan += 1
                    continue
                _prev = str((o.get("return_request") or {}).get("prev_status") or "").strip()
                if _prev not in _RESTORE_OK:
                    _prev = "delivered"
                await db.customer_returns.update_one(
                    {"id": rec["id"]},
                    {"$set": {"status": "expired", "expired_at": now_iso,
                              "expire_reason": f"İade süresi doldu ({_days} gün) — ürün kargoya verilmedi",
                              "updated_at": now_iso}})
                # TOCTOU: yalnız HÂLÂ return_requested ise geri al (arada personel dokunduysa dokunma)
                r = await db.orders.update_one(
                    {"id": o["id"], "status": "return_requested"},
                    {"$set": {"status": _prev, "return_request.status": "expired",
                              "return_request.expired_at": now_iso, "updated_at": now_iso}})
                if r.modified_count:
                    kapanan += 1
                    try:
                        from routes.orders import _log_order_event
                        await _log_order_event(
                            o["id"], "return",
                            f"İade süresi doldu ({_days} gün) — ürün kargoya verilmedi; "
                            f"sipariş '{_prev}' durumuna döndürüldü",
                            {"email": "sistem"}, {"return_id": rec.get("id")},
                            order_number=o.get("order_number", ""))
                    except Exception:
                        pass
            except Exception as _ie:
                logger.warning(f"[iade-süresi] kayıt atlandı ({rec.get('id')}): {_ie}")
        if kapanan or atlanan:
            logger.warning(f"[iade-süresi] normale döndürülen sipariş={kapanan} atlanan={atlanan} "
                           f"(sınır {_days} gün)")
    except Exception as e:
        logger.exception(f"[scheduler] expire_stale_site_return_requests failed: {e}")


async def auto_cancel_unpaid_card_orders():
    """Başarısız/ödenmemiş KART siparişlerini 24 saat sonra iptal edip stoğu geri ekler.

    KRİTİK: Bu iş zamanlanmamıştı → başarısız kart ödemeleri (iyzico 3DS reddi, yarıda kalan
    ödeme) create_order'da düşürülen stoğu KALICI sızdırıyordu (ürünler yanlışlıkla tükeniyordu).
    COD/havale HARİÇ (meşru şekilde bekler + kendi akışları var). Restock idempotenttir
    (_restock_order_once — 'auto_cancel_expired' hareketi bir kez eklenir)."""
    from routes.deps import db  # lazy import
    from routes.orders import _restock_order_once
    import business_rules as _BR
    try:
        # AYAR (varsayılan 3 saat): 3DS başlatılıp ödenmeyen kart siparişleri fazla beklemesin.
        # Güvenli: webhook (saniyeler) + reconcile (her 15dk) gerçekten çekilen ödemeyi bu süreden
        # ÇOK önce 'paid' yapar. Süre admin panelinden (İşletme Kuralları) yönetilir.
        # SÜRE (kullanıcı isteği): yarıda kalan kart siparişi stoğu UZUN SÜRE TUTMASIN.
        # Dakika bazlı kural birincil; 0/boş ise eski saat bazlı ayar kullanılır.
        _ucm = int(await _BR.get_rule(db, "order.unpaid_card_cancel_minutes", 45) or 0)
        if _ucm <= 0:
            _ucm = int(await _BR.get_rule(db, "order.unpaid_card_cancel_hours", 3) or 3) * 60
        # Hiç ödeme denemesi OLMAYAN (iyzico kaydı oluşmamış) siparişler daha kısa sürede
        # kapanır: doğrulanacak bir tahsilat yok, stoğu boşuna tutmanın anlamı yok.
        _abm = int(await _BR.get_rule(db, "order.abandoned_card_cancel_minutes", 15) or 0)
        if _abm <= 0 or _abm > _ucm:
            _abm = _ucm
        _now_dt = datetime.now(timezone.utc)
        cutoff = (_now_dt - timedelta(minutes=_ucm)).isoformat()
        cutoff_abandoned = (_now_dt - timedelta(minutes=_abm)).isoformat()
        _cod_bank = ["cash_on_delivery", "kapida", "kapida_odeme", "cod",
                     "bank_transfer", "havale", "eft", "havale_eft", "banka_havale", "transfer"]
        # İki grup: (a) ödeme denemesi VAR (iyzico kaydı oluşmuş) → tam süre beklenir,
        # (b) hiç deneme YOK → kısa süre. (b)'de doğrulanacak tahsilat olmadığından stok
        # erken serbest bırakılır (kullanıcı isteği: yarıda kalan sipariş stoğu tutmasın).
        _no_attempt = {
            "$and": [
                {"$or": [{"iyzico_payment_id": {"$in": [None, ""]}}, {"iyzico_payment_id": {"$exists": False}}]},
                {"$or": [{"payment_id": {"$in": [None, ""]}}, {"payment_id": {"$exists": False}}]},
                {"$or": [{"reconcile_payment_id": {"$in": [None, ""]}}, {"reconcile_payment_id": {"$exists": False}}]},
                {"needs_reconciliation": {"$ne": True}},
            ]
        }
        query = {
            "payment_status": {"$in": ["pending", "failed"]},
            "status": {"$in": ["pending", "awaiting_payment"]},
            # DENETİM (2026-09-29): pazaryeri siparişi (Amazon 'Pending', HB bilinmeyen statü →
            # pending/pending) iyzico kaydı olmadığından bu süpürgeye takılıp iptal + stok iadesi
            # alıyordu (oversell). Yalnız SİTE kart siparişleri süpürülür.
            "payment_method": {"$nin": _cod_bank + ["marketplace"]},
            "platform": {"$nin": ["trendyol", "hepsiburada", "amazon", "temu", "n11"]},
            "$or": [
                {"created_at": {"$lt": cutoff}},
                {"$and": [{"created_at": {"$lt": cutoff_abandoned}}, _no_attempt]},
            ],
        }
        cancelled = 0
        async for order in db.orders.find(query, {"_id": 0}):
            try:
                # TOCTOU koruması: sorgu ile update arasında ödeme onaylanmış olabilir.
                # Filtreye payment_status != paid ekle → ödenmiş sipariş iptal/geri stok
                # EDİLMESİN. matched_count 0 ise (ödenmiş) restock da yapılmaz.
                # DENETİM (2026-09-29, Y3): iyzico'da ödeme kaydı belirsiz (needs_reconciliation)
                # olan sipariş kapatılır ve stok serbest kalır; ANCAK mutabakat bayrağı SİLİNMEZ ve
                # "para alınmadı" denmez — para çekilmiş olabilir, reconcile cron'u 7 gün boyunca
                # doğrulamaya devam eder (çekildiyse sipariş paid olur, stok yeniden düşer).
                _unsure = bool(order.get("needs_reconciliation"))
                _upd_extra = {"$unset": {"needs_reconciliation": ""}} if not _unsure else {}
                res = await db.orders.update_one(
                    {"id": order["id"], "payment_status": {"$nin": ["paid", "refunded"]},
                     "status": {"$in": ["pending", "awaiting_payment"]}},
                    {**_upd_extra, "$set": {
                        # status="cancelled" DEĞİL "payment_failed": bu siparişin parası HİÇ alınmadı.
                        # "İptal Edildi" yazılırsa ekip "ödeme alınmıştı" sanıp yanlışlıkla PARA İADESİ
                        # yapıyordu. "payment_failed" = Ödeme Alınamadı → iade GEREKMEZ, ana listede
                        # görünmez. (Gerçekten para çekilmiş olsaydı reconcile job 24s dolmadan
                        # 'paid' yapardı; bu guard paid'i zaten atlıyor.)
                        "status": "payment_failed",
                        "payment_status": "expired",
                        # Kapatılan siparişi mutabakat havuzundan çıkar: ödeme gerçekten
                        # çekilmediği (birkaç mutabakat turu boyunca SUCCESS gelmediği) için
                        # 7 gün boyunca 15 dakikada bir iyzico'ya sormanın anlamı yok.
                        # Geç ortaya çıkan gerçek tahsilat webhook ile yine yakalanır.
                        "reconcile_stopped_at": datetime.now(timezone.utc).isoformat(),
                        "cancel_reason": ("Ödeme doğrulanamadı — iyzico kaydı belirsiz, sistem 7 gün kontrol "
                                          "etmeye devam ediyor. İade yapmadan önce iyzico panelinden kontrol edin."
                                          if _unsure else
                                          "Ödeme süresinde tamamlanmadı — para HİÇ alınmadı (iade gerekmez)"),
                        "auto_cancelled": True,
                        # Denetim #2: bu sipariş restock edildi. Geç reconcile (iyzico'dan para
                        # çekildiği ortaya çıkarsa) tekrar paid+confirmed olursa stok TEKRAR
                        # düşülmeli (oversell önle) — payment._mark_order_from_payment bu işareti okur.
                        "_restocked_by_autocancel": True,
                        "cancelled_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }}
                )
                if res.matched_count == 0:
                    continue  # arada ödendi/durumu değişti — dokunma
                await _restock_order_once(order, "auto_cancel_expired")
                cancelled += 1
            except Exception as e_item:
                logger.error(f"Failed to cancel card order {order.get('order_number')}: {e_item}")
        if cancelled:
            logger.info(f"[scheduler] Auto-cancelled {cancelled} unpaid/failed card orders (>3h)")
    except Exception as e:
        logger.exception(f"[scheduler] auto_cancel_unpaid_card_orders failed: {e}")


async def reconcile_charged_but_unrecorded_orders():
    """OTOMATİK KURTARMA: iyzico'dan para ÇEKİLMİŞ ama 'ödendi' işaretlenmemiş kart siparişlerini
    (needs_reconciliation bayraklı VEYA pending/failed) iyzico'dan paymentId ile doğrulayıp
    finalize eder — kimsenin elle 'recover-charged' çalıştırmasına gerek kalmaz.
    _finalize_by_payment_id belirsiz cevapta siparişe DOKUNMAZ (yanlış paid yazmaz).
    Kapsam: son 7 gün, kart (COD/havale hariç), tur başına en çok 50 sipariş."""
    from routes.deps import db  # lazy import
    try:
        from routes.payment import _finalize_by_payment_id
    except Exception as e:
        logger.warning(f"[scheduler] reconcile import atlandı: {e}")
        return
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        _cod_bank = ["cash_on_delivery", "kapida", "kapida_odeme", "cod",
                     "bank_transfer", "havale", "eft", "havale_eft", "banka_havale", "transfer"]
        query = {
            "created_at": {"$gt": cutoff},
            "payment_method": {"$nin": _cod_bank},
            "payment_status": {"$ne": "paid"},
            "$or": [
                {"needs_reconciliation": True},
                {"payment_status": {"$in": ["pending", "failed"]}},
            ],
        }
        recovered = 0
        candidates = await db.orders.find(
            query, {"_id": 0, "id": 1, "reconcile_payment_id": 1,
                    "iyzico_payment_id": 1, "payment_id": 1, "order_number": 1,
                    "iyzico_retrieve_response": 1}
        ).sort("created_at", -1).to_list(50)
        for order in candidates:
            # KÖK NEDEN #1: eski 'failed' siparişlerde paymentId ÜST DÜZEYDE yok, yalnızca
            # iyzico_retrieve_response.paymentId içinde saklı. O yüzden nested alanı da OKU →
            # bayrağı olmayan mevcut takılı siparişler de otomatik kurtarılabilsin.
            _nested_pid = ""
            try:
                _nested_pid = str((order.get("iyzico_retrieve_response") or {}).get("paymentId") or "").strip()
            except Exception:
                _nested_pid = ""
            pid = str(order.get("reconcile_payment_id") or order.get("iyzico_payment_id")
                      or order.get("payment_id") or _nested_pid or "").strip()
            if not pid:
                continue  # paymentId yok → otomatik doğrulanamaz (webhook/callback bekler)
            try:
                paid = await _finalize_by_payment_id(order["id"], pid)
            except Exception as _e:
                logger.warning(f"[scheduler] reconcile finalize hata {order.get('order_number')}: {_e}")
                continue
            if paid:
                await db.orders.update_one(
                    {"id": order["id"]},
                    {"$unset": {"needs_reconciliation": "", "reconcile_payment_id": ""}})
                recovered += 1
        if recovered:
            logger.info(f"[scheduler] iyzico reconcile: {recovered} çekilmiş sipariş otomatik finalize edildi")
    except Exception as e:
        logger.exception(f"[scheduler] reconcile_charged_but_unrecorded_orders failed: {e}")


async def retry_pending_iys_consents():
    """İYS GÜNLÜK TOPLU BİLDİRİM (işletme isteği: "günlük bildir tüm izinleri, izin
    kalkarsa da bildir"). Saatte bir tetiklenir; gün içinde (TR saati) bir kez TÜM bekleyen
    izin (ONAY) ve iptal (RET) kayıtlarını NetGSM'e toplu gönderir. 'Sinir asimi' veya hata
    olursa o günün turu tamamlanmış sayılmaz → bir saat sonra kaldığı yerden devam eder.

    ESKİ HATA: NetGSM'in başarılı yanıtı ({"code":"0","error":"false"}) başarısız sayılıyordu;
    her kayıt 30 dk'da bir tek tek yeniden gönderiliyor ve NetGSM 103 'Sinir asimi' veriyordu."""
    from routes.deps import db  # lazy import
    try:
        from routes.iys import report_pending_batch
    except Exception as e:
        logger.warning(f"[scheduler] iys batch import atlandı: {e}")
        return
    try:
        tr_today = (datetime.now(timezone.utc) + timedelta(hours=3)).date().isoformat()
        st = await db.settings.find_one({"id": "iys_daily_batch"}, {"_id": 0}) or {}
        if st.get("completed_date") == tr_today:
            return
        res = await report_pending_batch()
        upd = {"id": "iys_daily_batch", "last_run_at": datetime.now(timezone.utc).isoformat(), "last_result": res}
        if not res.get("stopped") and not res.get("error"):
            upd["completed_date"] = tr_today
        await db.settings.update_one({"id": "iys_daily_batch"}, {"$set": upd}, upsert=True)
        logger.info(f"[scheduler] İYS günlük toplu bildirim: {res}")
    except Exception as e:
        logger.exception(f"[scheduler] retry_pending_iys_consents failed: {e}")


async def send_havale_payment_reminders():
    """Havale/EFT siparişinde ödeme N saat içinde gelmediyse müşteriye 'Siparişiniz Alındı ·
    Ödeme Bekleniyor' (order_awaiting_payment) bildirimini OTOMATİK bir kez daha gönderir.
    Süre: İşletme Kuralları → order.havale_reminder_hours (varsayılan 24; 0 = kapalı).
    Kapsam: awaiting_payment + ödenmemiş + dekont bildirilmemiş (payment_notified değil) +
    daha önce hatırlatılmamış. Otomatik iptal süresine (havale_cancel_hours) girmiş siparişe
    hatırlatma GİTMEZ (iptal işi onu süpürür). Kanal: Sipariş Durumları ayarı; boşsa e-posta (+SMS).
    Yalnız en az bir kanal başarılıysa 'hatırlatıldı' damgalanır (SMTP hatasında tekrar denenir)."""
    from routes.deps import db  # lazy import
    import business_rules as _BR
    try:
        _hrs = int(await _BR.get_rule(db, "order.havale_reminder_hours", 24) or 0)
        if _hrs <= 0:
            return
        _cancel_hrs = int(await _BR.get_rule(db, "order.havale_cancel_hours", 72) or 72)
        now = datetime.now(timezone.utc)
        due_before = (now - timedelta(hours=_hrs)).isoformat()
        alive_after = (now - timedelta(hours=max(_cancel_hrs, _hrs + 1))).isoformat()
        query = {
            "payment_status": {"$nin": ["paid", "expired", "refunded"]},
            "status": "awaiting_payment",
            "payment_method": {"$in": ["transfer", "havale", "bank_transfer", "eft", "havale_eft", "banka_havale"]},
            "payment_notified": {"$ne": True},
            "havale_reminder_sent_at": {"$in": [None, ""]},
            "created_at": {"$lt": due_before, "$gt": alive_after},
        }
        try:
            from notification_service import send_notification
            from routes.orders import _order_notify_vars
            from order_statuses import get_status_config
        except Exception as e:
            logger.warning(f"[scheduler][havale-reminder] import skip: {e}")
            return
        try:
            _cfg = await get_status_config(db)
            _nz = (_cfg.get("notify") or {}).get("awaiting_payment") or {}
        except Exception:
            _nz = {}
        sent = failed = 0
        async for order in db.orders.find(query, {"_id": 0}).limit(200):
            ship = order.get("shipping_address") or {}
            phone = ship.get("phone") or order.get("phone")
            email = ship.get("email") or order.get("email") or order.get("customer_email")
            if not (phone or email):
                await db.orders.update_one({"id": order["id"]},
                                           {"$set": {"havale_reminder_sent_at": now.isoformat(),
                                                     "havale_reminder_result": "alıcı yok (telefon/e-posta boş)"}})
                continue
            channels = [c for c in ("sms", "email") if _nz.get(c)]
            if not channels:
                channels = ["email"] + (["sms"] if phone else [])
            try:
                variables = await _order_notify_vars(order)
                res = await send_notification(db, "order_awaiting_payment", to_phone=phone,
                                              to_email=email, variables=variables, channels=channels)
                results = (res or {}).get("results") or {}
                ok = any((v or {}).get("success") for v in results.values())
                if ok:
                    sent += 1
                    await db.orders.update_one(
                        {"id": order["id"]},
                        {"$set": {"havale_reminder_sent_at": now.isoformat(),
                                  "havale_reminder_result": ",".join(k for k, v in results.items() if (v or {}).get("success"))}})
                else:
                    failed += 1
                    logger.warning(f"[scheduler][havale-reminder] gönderilemedi order={order.get('order_number')} res={results}")
            except Exception as e:
                failed += 1
                logger.warning(f"[scheduler][havale-reminder] hata order={order.get('order_number')}: {e}")
            await asyncio.sleep(0.2)
        if sent or failed:
            logger.info(f"[scheduler][havale-reminder] {_hrs}s hatırlatma: gönderilen={sent} başarısız={failed}")
    except Exception as e:
        logger.exception(f"[scheduler] send_havale_payment_reminders failed: {e}")


async def _run_varyant_id_normalize():
    """Beden kimliği kuralını TÜM ürünlere uygular (6 saatte bir, idempotent):
    her beden id = kendi 4 haneli urun_id; urun_id ürünler arası tekil (önce oluşturulan ürün
    korur, kopyalayan ürüne yeni numara). Panelden/imalattan açılan 'var-…' bedenler ve
    kopyalanan ürünlerin çakışan ID'leri böylece Meta katalog/pikselde 4 haneli ve tekil olur.
    Barkodsuz bedenin id'sine dokunulmaz (eski siparişlerin iadesi id ile çözülür)."""
    from routes.deps import db, build_used_urun_id_set, normalize_variant_ids
    try:
        used = await build_used_urun_id_set()
        claimed = {}
        changed_products, changed_vars, barkodsuz = 0, 0, 0
        ornek = []
        async for p in db.products.find({}, {"_id": 0, "id": 1, "name": 1, "variants": 1}).sort("created_at", 1):
            vs = p.get("variants") or []
            if not vs:
                continue
            before = [(str(v.get("id") or ""), str(v.get("urun_id") or "")) for v in vs]
            n = normalize_variant_ids(vs, used, claimed)
            for v in vs:
                u = str(v.get("urun_id") or "").strip()
                if u:
                    claimed.setdefault(u, p["id"])
                if not str(v.get("barcode") or "").strip() and not str(v.get("id") or "").isdigit():
                    barkodsuz += 1
            if n:
                after = [(str(v.get("id") or ""), str(v.get("urun_id") or "")) for v in vs]
                if after != before:
                    await db.products.update_one({"id": p["id"]}, {"$set": {
                        "variants": vs, "updated_at": datetime.now(timezone.utc).isoformat()}})
                    # Bekleyen "stoğa gelince haber ver" kayıtları yeni beden id'sine taşınır.
                    for (oid, _ou), (nid, _nu) in zip(before, after):
                        if oid and nid and oid != nid:
                            try:
                                await db.stock_alerts.update_many(
                                    {"product_id": p["id"], "variant_id": oid, "notified": False},
                                    {"$set": {"variant_id": nid}})
                            except Exception:
                                pass
                    changed_products += 1
                    changed_vars += sum(1 for a, b in zip(before, after) if a != b)
                    if len(ornek) < 15:
                        ornek.append({"urun": (p.get("name") or "")[:40],
                                      "degisen": [f"{a[0]}→{b[0]}" for a, b in zip(before, after) if a != b][:4]})
        await db.settings.update_one({"id": "varyant_id_normalize"}, {"$set": {
            "id": "varyant_id_normalize", "at": datetime.now(timezone.utc).isoformat(),
            "degisen_urun": changed_products, "degisen_beden": changed_vars,
            "barkodsuz_4hanesiz": barkodsuz, "ornek": ornek}}, upsert=True)
        if changed_products:
            logger.info(f"[scheduler] varyant id normalize: {changed_products} ürün / {changed_vars} beden")
        # DOĞRULAMA + UYARI (kullanıcı görsün, söze güvenmek zorunda kalmasın):
        # düzeltme sonrası hâlâ 4 haneli olmayan / çakışan beden id'si var mı?
        import re as _re_v
        _seen, _bad, _dup = {}, [], []
        async for p in db.products.find({"is_deleted": {"$ne": True}},
                                        {"_id": 0, "id": 1, "name": 1, "variants.id": 1}):
            for v in (p.get("variants") or []):
                _vid = str(v.get("id") or "").strip()
                if not _re_v.fullmatch(r"\d{4,}", _vid):
                    _bad.append(f"{(p.get('name') or '')[:30]}: {_vid[:24]}")
                elif _vid in _seen and _seen[_vid] != p["id"]:
                    _dup.append(f"{_vid} ({(p.get('name') or '')[:30]})")
                _seen.setdefault(_vid, p["id"])
        try:
            from security.alerts import send_alert
            if _bad or _dup:
                await send_alert(
                    "variant_id_rule", "Beden ID kuralı BOZUK — Meta katalog eşleşmesi etkilenir",
                    f"4 haneli olmayan: {len(_bad)} · çakışan: {len(_dup)} · örnek: {(_bad + _dup)[:6]}",
                    level="critical", fingerprint="variant_id_rule_broken",
                    meta={"bad": _bad[:30], "dup": _dup[:30]})
            elif changed_products:
                await send_alert(
                    "variant_id_rule", f"Beden ID'si kurala uymayan {changed_products} ürün otomatik düzeltildi",
                    f"Bir yoldan 4 haneli olmayan/çakışan beden ID'si girdi ve düzeltildi. Örnek: {ornek[:5]}",
                    level="warning", fingerprint="variant_id_rule_fixed", meta={"ornek": ornek[:15]})
        except Exception as _ae:
            logger.warning(f"[scheduler] varyant id uyarısı gönderilemedi: {_ae}")
    except Exception as e:
        logger.warning(f"[scheduler] _run_varyant_id_normalize failed: {e}")


async def _ensure_cancelled_at_backfill():
    """TEK SEFERLİK: geçmiş iptallerin tarihini KANITTAN çıkar ve DONDUR.

    Sorun: rapor iptali "iptalin kesinleştiği ay"a yazıyor; tarih `cancelled_at`
    yoksa `updated_at`'ten okunuyordu. `updated_at` sipariş her senkronlandığında
    (2 dk) ileri kaydığı için GEÇMİŞ AYLARIN iptal rakamı her gün değişiyordu.

    Tarih şu sırayla, EN GÜVENİLİR KANITTAN seçilir:
      1) status_history içindeki 'cancelled' kaydının 'at' değeri (en eskisi)
      2) siparişin iptal/stok-iade hareketinin created_at'i (sistem o an işledi)
      3) refund_paid_at / expired_at gibi ilgili damgalar
      4) son çare: updated_at (kaynağı 'updated_at_fallback' diye İŞARETLENİR —
         hangi kayıtların tahmini olduğu sonradan görülebilsin)
    Hangi yoldan geldiği cancelled_at_source alanına yazılır.

    Sipariş STATÜSÜNE, tutarına veya stoğuna DOKUNMAZ — yalnız tarih alanı ekler.
    """
    from routes.deps import db  # lazy import
    _flag = "cancelled_at_backfill_v1"
    try:
        _cur = await db.settings.find_one({"id": _flag}, {"_id": 0, "done": 1})
        if (_cur or {}).get("done"):
            return
        _ST = ["cancelled", "cancel_refunded"]
        kaynak = {}
        yazildi = 0
        _batch = []
        async for o in db.orders.find(
                {"status": {"$in": _ST}, "cancelled_at": {"$exists": False}},
                {"_id": 0, "id": 1, "order_number": 1, "status_history": 1,
                 "refund_paid_at": 1, "expired_at": 1, "updated_at": 1}):
            _batch.append(o)
        # Hareket defterinden kanıt (tek seferde, sipariş sipariş sorgu atmadan)
        _ids = [str(o.get("id")) for o in _batch if o.get("id")]
        _mv = {}
        _RT = ["order_cancelled", "auto_cancel_expired", "havale_auto_cancel"]
        for i in range(0, len(_ids), 4000):
            async for m in db.stock_movements.find(
                    {"order_id": {"$in": _ids[i:i + 4000]}, "type": {"$in": _RT}},
                    {"_id": 0, "order_id": 1, "created_at": 1}):
                _k = str(m.get("order_id"))
                _c = str(m.get("created_at") or "")
                if _c and (_k not in _mv or _c < _mv[_k]):
                    _mv[_k] = _c        # en ERKEN hareket = iptalin işlendiği an
        for o in _batch:
            _when, _src = "", ""
            for h in (o.get("status_history") or []):
                if str((h or {}).get("status") or "") in _ST:
                    _at = str((h or {}).get("at") or "")
                    if _at and (not _when or _at < _when):
                        _when, _src = _at, "status_history"
            if not _when:
                _c = _mv.get(str(o.get("id")))
                if _c:
                    _when, _src = _c, "stock_movement"
            if not _when:
                for _f in ("refund_paid_at", "expired_at"):
                    if o.get(_f):
                        _when, _src = str(o[_f]), _f
                        break
            if not _when:
                _when, _src = str(o.get("updated_at") or ""), "updated_at_fallback"
            if not _when:
                continue
            try:
                r = await db.orders.update_one(
                    {"id": o.get("id"), "cancelled_at": {"$exists": False}},
                    {"$set": {"cancelled_at": _when, "cancelled_at_source": _src}})
                if r.modified_count:
                    yazildi += 1
                    kaynak[_src] = kaynak.get(_src, 0) + 1
            except Exception:
                pass
        # Kısmi iptaller: partial_cancel_at yoksa mevcut updated_at ile DONDUR
        # (daha iyi kanıt yok; en azından bir daha kaymaz).
        _kismi = 0
        try:
            async for o in db.orders.find(
                    {"partial_cancel_amount": {"$gt": 0},
                     "partial_cancel_at": {"$exists": False}},
                    {"_id": 0, "id": 1, "updated_at": 1}):
                r = await db.orders.update_one(
                    {"id": o.get("id"), "partial_cancel_at": {"$exists": False}},
                    {"$set": {"partial_cancel_at": str(o.get("updated_at") or ""),
                              "partial_cancel_at_source": "updated_at_fallback"}})
                _kismi += 1 if r.modified_count else 0
        except Exception as _ke:
            logger.warning(f"[iptal-tarihi] kısmi iptal dondurma: {_ke}")
        await db.settings.update_one(
            {"id": _flag},
            {"$set": {"id": _flag, "done": True, "tam_iptal": yazildi,
                      "kismi_iptal": _kismi, "kaynak_dagilimi": kaynak,
                      "applied_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        logger.info(f"[scheduler] iptal tarihi donduruldu: {yazildi} tam + {_kismi} kısmi "
                    f"({kaynak}) — statü/tutar/stok DEĞİŞMEDİ")
    except Exception as e:
        try:
            await db.settings.update_one(
                {"id": _flag}, {"$set": {"id": _flag, "done": False,
                                         "hata": f"{type(e).__name__}: {str(e)[:300]}"}},
                upsert=True)
        except Exception:
            pass
        logger.warning(f"[scheduler] _ensure_cancelled_at_backfill failed: {e}")


async def _ensure_restock_delta_backfill():
    """TEK SEFERLİK · YALNIZ DEFTER: eski pazaryeri iade satırlarına 'delta' yaz.

    Pazaryeri iade (claim) geri-stok hareketleri deftere 'qty' alan adıyla yazılmıştı;
    sistemdeki tüm okuyucular ise 'delta' okur (_restock_authoritative, reaktivasyon
    yeniden-düşümü, iade-reddi geri alma, raporlar). Bu yüzden o satırlar "0 adet"
    görünüyor, aynı sipariş İKİNCİ kez geri stoklanabiliyordu.

    HİÇBİR STOK SAYISINI DEĞİŞTİRMEZ — yalnız hareket kaydına delta=qty ekler (qty
    korunur). Yalnız type='return_restock' satırlarına dokunur.

    DAYANIKLILIK: önce tek aggregation-pipeline güncellemesi denenir; sunucu sürümü
    desteklemez ya da başka bir nedenle hata verirse belge belge Python tarafında
    yapılır. Sonuç (başarı VEYA hata) settings'e YAZILIR — aksi halde hata yutulup
    "çalıştı mı?" sorusu cevapsız kalıyordu. Yalnız done=True ise tekrar çalışmaz.
    """
    from routes.deps import db  # lazy import
    _flag = "restock_delta_backfill_v1"
    try:
        _cur = await db.settings.find_one({"id": _flag}, {"_id": 0, "done": 1})
        if (_cur or {}).get("done"):
            return
        Q = {"type": "return_restock", "items.qty": {"$exists": True},
             "items.delta": {"$exists": False}}
        n, yol, hata = 0, "", ""
        try:
            res = await db.stock_movements.update_many(Q, [{"$set": {"items": {"$map": {
                "input": {"$ifNull": ["$items", []]}, "as": "it",
                "in": {"$cond": [
                    {"$and": [
                        {"$ne": [{"$ifNull": ["$$it.qty", None]}, None]},
                        {"$eq": [{"$ifNull": ["$$it.delta", None]}, None]},
                    ]},
                    {"$mergeObjects": ["$$it", {"delta": "$$it.qty"}]},
                    "$$it",
                ]}}}}}])
            n, yol = res.modified_count, "pipeline"
        except Exception as _pe:
            hata = f"pipeline: {type(_pe).__name__}: {str(_pe)[:200]}"
            yol = "python"
            async for mv in db.stock_movements.find(Q, {"_id": 1, "items": 1}):
                yeni, degisti = [], False
                for it in (mv.get("items") or []):
                    if isinstance(it, dict) and it.get("delta") is None and it.get("qty") is not None:
                        it = {**it, "delta": it["qty"]}
                        degisti = True
                    yeni.append(it)
                if degisti:
                    await db.stock_movements.update_one(
                        {"_id": mv["_id"]}, {"$set": {"items": yeni}})
                    n += 1
        await db.settings.update_one(
            {"id": _flag},
            {"$set": {"id": _flag, "done": True, "yol": yol, "hareket": n,
                      "pipeline_hatasi": hata,
                      "applied_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        logger.info(f"[scheduler] iade hareketlerine delta yazıldı: {n} kayıt ({yol}) "
                    f"— stok DEĞİŞMEDİ, yalnız defter")
    except Exception as e:
        # Hata da KAYDEDİLİR (done=False) ki bir sonraki açılışta tekrar denensin
        # ve "neden çalışmadı" sorusu görünür olsun.
        try:
            await db.settings.update_one(
                {"id": _flag},
                {"$set": {"id": _flag, "done": False,
                          "hata": f"{type(e).__name__}: {str(e)[:300]}",
                          "denendi_at": datetime.now(timezone.utc).isoformat()}},
                upsert=True)
        except Exception:
            pass
        logger.warning(f"[scheduler] _ensure_restock_delta_backfill failed: {e}")


async def _ensure_consignment_removed():
    """Tek seferlik: KONSİNYE STOK alanını veritabanından da tamamen kaldır.

    Kullanıcı kararı ("konsinye stoğu tamamen sil sistemden"). Alan Ticimax Excel'inden
    gelmişti, HİÇBİR hesaplamada kullanılmıyordu (ölü alan) — koddan çıkarıldı, burada
    ürün belgelerinden de silinir. Bayrak (settings.consignment_removed_v1) bir kez uygular.
    Yalnız bu iki alanı $unset eder; başka hiçbir veriye dokunmaz.
    """
    from routes.deps import db  # lazy import
    try:
        if await db.settings.find_one({"id": "consignment_removed_v1"}):
            return
        r1 = await db.products.update_many(
            {"consignment_stock": {"$exists": True}}, {"$unset": {"consignment_stock": ""}})
        r2 = await db.products.update_many(
            {"ticimax_fields.KONSINYESTOKADEDI": {"$exists": True}},
            {"$unset": {"ticimax_fields.KONSINYESTOKADEDI": ""}})
        await db.settings.update_one(
            {"id": "consignment_removed_v1"},
            {"$set": {"id": "consignment_removed_v1",
                      "applied_at": datetime.now(timezone.utc).isoformat(),
                      "products": r1.modified_count, "ticimax_fields": r2.modified_count}},
            upsert=True)
        logger.info(f"[scheduler] Konsinye stok alanı silindi "
                    f"(ürün: {r1.modified_count}, ticimax_fields: {r2.modified_count})")
    except Exception as e:
        logger.warning(f"[scheduler] _ensure_consignment_removed failed: {e}")


# Eski pazaryeri senkron kilit havuzu (security/monitoring okur; artık boş kalır).
_RUNNING_SYNCS: set = set()
_SYNC_TASKS: set = set()


async def _send_abandoned_cart_reminders():
    """Terkedilmiş sepet e-postası — yalnız e-posta ticari ileti izni olan ÜYELERE, sepet
    12 saat (İşletme Kuralları) önce güncellenmiş ve o saatten beri sipariş yoksa.
    Tüm kurallar abandoned_cart_mail.run içinde (izin / üye / sipariş / tekrar aralığı).

    ESKİ DAVRANIŞ KALDIRILDI: günde bir, izin kontrolü YAPMADAN istemcinin yazdığı her sepet
    e-postasına jenerik mail gidiyordu (İYS/KVKK açısından ticari ileti izni şart)."""
    from routes.deps import db
    try:
        import abandoned_cart_mail
        stats = await abandoned_cart_mail.run(db)
        if stats.get("candidates"):
            logger.info(f"[scheduler] Abandoned cart e-mail: {stats}")
    except Exception as e:
        logger.exception(f"[scheduler] abandoned cart e-mail failed: {e}")


async def _stock_alert_recipients(db) -> list:
    """Stok uyarılarının gideceği adres(ler). Beyaz etiket: firma-özel değer koddan gelmez.

    Öncelik: İşletme Kuralları `stock.alert_email` → firma iletişim e-postası
    (company.contact_email) → admin kullanıcılar. Virgülle birden çok adres yazılabilir.
    """
    try:
        from business_rules import get_rule as _gr
        raw = str(await _gr(db, "stock.alert_email", "") or "").strip()
    except Exception:
        raw = ""
    if not raw:
        try:
            from company import get_company
            raw = str((await get_company(db)).get("contact_email") or "").strip()
        except Exception:
            raw = ""
    if raw:
        return [x.strip() for x in raw.replace(";", ",").split(",") if x.strip()]
    try:
        admins = await db.users.find(
            {"is_admin": True, "is_active": {"$ne": False}}, {"_id": 0, "email": 1}
        ).to_list(50)
        return list({a.get("email") for a in admins if a.get("email")})
    except Exception:
        return []


async def _send_daily_stock_alert(threshold: int = None):
    """Her gün, stoğu `threshold` veya altına düşmüş ürün-varyant kombinasyonlarını
    bulup admin kullanıcılara (is_admin=True) özet e-posta gönderir. Eşik verilmezse
    İşletme Kuralları'ndan okunur (stock.low_stock_alert_threshold, varsayılan 3).

    2026-07-02: notification_service.py'de 'stock_alert' bildirim tipi tanımlıydı
    ('Stok Uyarısı (Admin)') ama hiçbir yerde tetiklenmiyordu. Sorgu mantığı
    routes/bulk_ops.py:GET /stock-alerts ile aynı (kopyalandı, davranış korunuyor).
    """
    from routes.deps import db
    if threshold is None:
        try:
            from business_rules import get_rule as _get_rule
            threshold = int(await _get_rule(db, "stock.low_stock_alert_threshold", 3))
        except Exception:
            threshold = 3
    try:
        from routes.catalog_extras import _send_email_via_resend  # lazy
    except Exception as e:
        logger.warning(f"[scheduler] stock alert mail skip (import): {e}")
        return
    from email_smtp import get_smtp_config, is_configured
    if not is_configured(await get_smtp_config(db)):
        return  # E-posta (SMTP/Zoho) yapılandırılmamış → sessizce atla
    try:
        alerts = []
        async for p in db.products.find(
            {"status": {"$ne": "archived"}},
            {"_id": 0, "id": 1, "name": 1, "stock_code": 1, "variants": 1, "stock": 1},
        ):
            variants = p.get("variants") or []
            if variants:
                for v in variants:
                    s = v.get("stock")
                    if s is not None and s <= threshold:
                        alerts.append({
                            "name": p.get("name", ""),
                            "variant": f"{v.get('size','')} {v.get('color','')}".strip(),
                            "stock_code": v.get("stock_code") or p.get("stock_code"),
                            "stock": s,
                        })
            else:
                s = p.get("stock")
                if s is not None and s <= threshold:
                    alerts.append({
                        "name": p.get("name", ""), "variant": "—",
                        "stock_code": p.get("stock_code"), "stock": s,
                    })
        if not alerts:
            return
        # ALICI (beyaz etiket): İşletme Kuralları'ndaki stock.alert_email → boşsa firma
        # iletişim e-postası (company/tenant ayarı) → o da yoksa admin kullanıcılar.
        # Firma-özel adres KODDA DEĞİL, ayarda durur.
        recipients = await _stock_alert_recipients(db)
        if not recipients:
            return
        rows = "".join(
            f"<tr><td>{a['name']}</td><td>{a['variant']}</td>"
            f"<td>{a['stock_code'] or ''}</td><td>{a['stock']}</td></tr>"
            for a in alerts[:200]  # e-posta boyutu için sınırla
        )
        subject = f"Stok Uyarısı: {len(alerts)} ürün-varyant eşik altında (≤{threshold})"
        html = (
            f"<h2>Düşük Stok Uyarısı</h2>"
            f"<p>{len(alerts)} ürün-varyant kombinasyonu {threshold} veya altında stoğa sahip.</p>"
            f"<table border='1' cellpadding='6' style='border-collapse:collapse'>"
            f"<tr><th>Ürün</th><th>Varyant</th><th>Stok Kodu</th><th>Stok</th></tr>{rows}</table>"
            f"<p style='font-size:12px;color:#888;margin-top:24px'>Bu e-posta otomatik gönderilmiştir.</p>"
        )
        ok, failed, errs = await _send_email_via_resend(recipients, subject, html)
        logger.info(f"[scheduler] Stock alert: {len(alerts)} items, sent={ok} failed={failed} errs={errs[:1]}")
    except Exception as e:
        logger.exception(f"[scheduler] stock alert failed: {e}")


# ── §7 GÜVENLİK / AUDIT LOG RETENTION ─────────────────────────
# TANIMLI POLİTİKA: PII'siz denetim logları MİNİMUM 12 AY (365 gün) saklanır; bu süreyi AŞAN
# kayıtlar temizlenir (bounded retention). TABAN KİLİDİ: env ile UZATILABİLİR ama 365'in ALTINA
# İNEMEZ → hiçbir log 12 aydan erken silinemez. Silme YALNIZ bu sistem işinde yapılır; admin-facing
# log-silme ucu YOKTUR (silme yetkisi sistemle sınırlı).
# (koleksiyon, zaman_alanı) — hepsi ISO string zaman tutar → string "<" karşılaştırması güvenli.
_RETENTION_LOG_COLLECTIONS = [
    ("capi_event_logs", "created_at"),  # CAPI server-event logları
    ("audit_logs", "created_at"),       # genel compliance/audit
    ("auth_audit_logs", "created_at"),  # giriş/kimlik denetim
    ("integration_logs", "created_at"),  # pazaryeri entegrasyon logları
]


async def _security_log_retention_purge():
    """§7 — Güvenlik/audit/SP-API loglarını ≥12 AY (365 gün) saklar, aşan kayıtları temizler.
    TABAN KİLİDİ 365 gün → hiçbir log 12 aydan erken silinmez (yanlış config'e karşı korumalı)."""
    import os as _os
    from routes.deps import db
    try:
        days = max(365, int(_os.environ.get("SECURITY_LOG_RETENTION_DAYS") or 365))
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        total = 0
        for coll, tfield in _RETENTION_LOG_COLLECTIONS:
            try:
                res = await db[coll].delete_many({tfield: {"$lt": cutoff}})
                total += int(getattr(res, "deleted_count", 0) or 0)
            except Exception as _ce:
                logger.warning(f"[scheduler][retention] {coll} temizlenemedi: {_ce}")
        if total:
            logger.info(f"[scheduler][retention] {total} eski log temizlendi (>{days} gün saklama)")
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "action": "security_log_retention_purge",
                "category": "compliance",
                "details": {"deleted": total, "retention_days": days},
                "actor": "system_scheduler",
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
    except Exception as e:
        logger.exception(f"[scheduler] security_log_retention_purge failed: {e}")


def _parse_tr_dt(s: str):
    """MNG teslim tarihini ISO'ya cevirir; basarisizsa None."""
    s = (s or "").strip()
    if not s:
        return None
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M",
              "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, f).replace(tzinfo=timezone.utc).isoformat()
        except Exception:
            continue
    return None


async def _dhl_cargo_poll_tick():
    """Her 5 dk: site (web) siparislerini MNG/DHL e-Commerce API'sinden sorgula.
      - GONDERI_NO / takip linki olustuysa -> 'shipped' (Kargoya Verildi) + bildirim
      - Teslim edildiyse -> 'delivered' (Teslim Edildi) + delivered_at + bildirim
    Bildirimler Ayarlar > Siparis Durumlari (sms/email) secimine gore gonderilir.
    SOAP cagrilari thread executor'da calisir (event loop bloklanmaz).
    """
    from routes.deps import db  # lazy
    try:
        from routes.orders import _get_mng_settings
        from order_statuses import get_status_config, customer_label_for
        from notification_service import send_notification
        from mng_kargo_client import get_mng_shipment_status
    except Exception as e:
        logger.warning(f"[scheduler][dhl] import skip: {e}")
        return

    # DENETİM FIX (#10): İzleme paneli 'dhl_poll_health' dokümanını okuyor ama hiç yazılmıyordu.
    # Başlangıç/bitiş + sayaçlar (matched/processed/shipped/delivered/errors/duration) yazılır.
    _run_started = datetime.now(timezone.utc)

    async def _write_health(status: str, **extra):
        try:
            doc = {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
            doc.update(extra)
            await db.settings.update_one({"id": "dhl_poll_health"}, {"$set": doc}, upsert=True)
        except Exception as _he:
            logger.warning(f"[scheduler][dhl] health write err: {_he}")

    s = await _get_mng_settings()
    if not s.get("is_active") or not s.get("username"):
        logger.info("[scheduler][dhl] atlandi: MNG/DHL ayarlari aktif degil ya da kullanici adi yok")
        await _write_health("inactive", last_run_at=_run_started.isoformat(),
                            last_finish_at=datetime.now(timezone.utc).isoformat(),
                            matched=0, processed=0, shipped=0, delivered=0, errors=0,
                            duration_ms=0, interval_min=5,
                            note="MNG/DHL ayarları aktif değil ya da kullanıcı adı yok")
        return
    user, pw = s["username"], s["password"]

    cutoff = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
    q = {
        "platform": {"$in": ["web", "site", None]},
        "status": {"$in": ["confirmed", "processing", "preparing", "ready_to_ship",
                            "shipped", "in_transit", "out_for_delivery"]},
        "$or": [
            {"cargo_tracking_number": {"$nin": [None, ""]}},
            {"cargo_provider_name": {"$nin": [None, ""]}},
            {"cargo_barcode_created": True},
        ],
        "created_at": {"$gt": cutoff},
    }
    try:
        cfg = await get_status_config(db)
    except Exception:
        cfg = {"notify": {}}
    notify = cfg.get("notify") or {}

    try:
        matched = await db.orders.count_documents(q)
    except Exception:
        matched = 0
    await _write_health("running", last_run_at=_run_started.isoformat(),
                        matched=matched, interval_min=5)

    processed = 0
    n_shipped = 0
    n_delivered = 0
    n_errors = 0
    try:
        async for order in db.orders.find(q, {"_id": 0}).limit(120):
            siparis_no = str(order.get("order_number") or order.get("id") or "").strip()
            if not siparis_no:
                continue
            try:
                info = await asyncio.to_thread(
                    get_mng_shipment_status, username=user, password=pw, siparis_no=siparis_no
                )
            except Exception as e:
                logger.warning(f"[scheduler][dhl] status err {siparis_no}: {e}")
                n_errors += 1
                await asyncio.sleep(0.2)
                continue
            if not info or not info.get("ok"):
                await asyncio.sleep(0.2)
                continue

            gonderi = (info.get("gonderi_no") or "").strip()
            url = (info.get("kargo_takip_url") or "").strip()
            # DHL eCommerce: takip no varsa müşteri direkt takip deep-link'i (genel /gonderitakip yerine)
            _track_no = gonderi or order.get("cargo_tracking_number", "")
            track_link = f"https://kargotakip.dhlecommerce.com.tr/?takipNo={_track_no}" if _track_no else url
            teslim = (info.get("teslim_tarihi") or "").strip()
            statu = (info.get("kargo_statu") or "0").strip()
            aciklama = (info.get("kargo_statu_aciklama") or "")
            cur = order.get("status")

            # Y20: "teslim alın(dı)" / "şubeden teslim" = ŞUBE/KABUL hareketi, TESLİMAT DEĞİL.
            # "teslim" substring'i bunları da eşleyip siparişi ilk taramada yanlış 'delivered'
            # yapıyor, müşteriye erken "Teslim Edildi" bildirimi gidiyordu.
            _dl_aç = aciklama.lower()
            _pickup = any(k in _dl_aç for k in ("teslim alın", "teslim alin", "şubeden teslim",
                                                "subeden teslim", "şubede teslim", "subede teslim"))
            delivered = (not _pickup) and (bool(teslim) or ("teslim" in _dl_aç and "edilemedi" not in _dl_aç))
            # İLK OKUTMA tespiti — sadece kargocu/şube siparişi fiilen okuttuğunda "Kargoya Verildi".
            # Barkod oluşturulurken gönderi_no/takip url'i dolabildiği için onlar TEK BAŞINA tetik DEĞİL;
            # yalnızca MNG/DHL bir HAREKET statüsü (kargo_statu ≠ 0) ya da kabul/şube/okutma açıklaması
            # döndürdüğünde durumu çeviriyoruz. (kargo_statu: 0=İşlem Yok, 1+/100+=şubeye girdi/işleniyor)
            _alow = aciklama.lower()
            _acc_kw = ("kabul", "şube", "sube", "okut", "teslim alın", "teslim alin",
                       "işleme", "isleme", "çıkış", "cikis", "girdi", "transfer",
                       "dağıt", "dagit", "yola")
            shipped = (statu not in ("", "0")) or any(k in _alow for k in _acc_kw)
            now_iso = datetime.now(timezone.utc).isoformat()

            new_status = None
            upd = {}
            if delivered and cur != "delivered":
                new_status = "delivered"
                upd["delivered_at"] = _parse_tr_dt(teslim) or now_iso
            elif shipped and _track_no and cur in ("confirmed", "processing", "preparing", "ready_to_ship"):
                # Takip no oluşmadan "Kargoya Verildi" YAPMA — yoksa müşteriye giden SMS'teki
                # {tracking_url} no'suz genel /gonderitakip sayfasını açar. No gelene kadar bekle;
                # sonraki taramada gönderi no dolunca durum çevrilir + deep-link'li SMS gider.
                new_status = "shipped"
                upd["shipped_at"] = now_iso

            if gonderi:
                upd["cargo_gonderi_no"] = gonderi
                upd["cargo_tracking_number"] = gonderi
            if track_link:
                upd["cargo_tracking_url"] = track_link
                upd["cargo_tracking_link"] = track_link
            if aciklama:
                upd["cargo_status_text"] = aciklama
            if new_status:
                upd["status"] = new_status
            if upd:
                upd["updated_at"] = now_iso
                await db.orders.update_one({"id": order["id"]}, {"$set": upd})

            if new_status == "shipped":
                n_shipped += 1
            elif new_status == "delivered":
                n_delivered += 1

            if new_status in ("shipped", "delivered"):
                ev = "order_shipped" if new_status == "shipped" else "order_delivered"
                nz = notify.get(new_status) or {}
                ch = [c for c in ("sms", "email") if nz.get(c)]
                if ch:
                    addr = order.get("shipping_address") or {}
                    try:
                        await send_notification(
                            db, ev,
                            to_phone=addr.get("phone") or order.get("phone"),
                            to_email=addr.get("email") or order.get("email"),
                            variables={
                                "customer_name": (f"{addr.get('first_name','')} {addr.get('last_name','')}".strip()
                                                  or addr.get("full_name") or addr.get("name") or "Müşterimiz"),
                                "order_number": siparis_no,
                                "amount": f"{order.get('total', 0):.2f} TL",
                                "tracking_number": gonderi or order.get("cargo_tracking_number", ""),
                                "tracking_url": track_link or order.get("cargo_tracking_url", ""),
                                "tracking_link": track_link or order.get("cargo_tracking_url", ""),
                                "status_label": customer_label_for(new_status),
                            },
                            channels=ch,
                        )
                    except Exception as e:
                        logger.warning(f"[scheduler][dhl] notif {siparis_no}: {e}")
                logger.info(f"[scheduler][dhl] {siparis_no} -> {new_status}")

            processed += 1
            await asyncio.sleep(0.25)

        _final_status = "ok"
    except Exception as e:
        logger.exception(f"[scheduler][dhl] poll tick failed: {e}")
        n_errors += 1
        _final_status = "error"
    _fin = datetime.now(timezone.utc)
    _dur_ms = int((_fin - _run_started).total_seconds() * 1000)
    await _write_health(
        _final_status,
        last_run_at=_run_started.isoformat(),
        last_finish_at=_fin.isoformat(),
        matched=matched, processed=processed,
        shipped=n_shipped, delivered=n_delivered, errors=n_errors,
        duration_ms=_dur_ms, interval_min=5,
    )
    logger.info(f"[scheduler][dhl] tick bitti — {processed} site siparisi sorgulandi "
                f"(shipped={n_shipped} delivered={n_delivered} err={n_errors})")


async def _return_cargo_poll_tick():
    """Her 5 dk: müşteriden depoya gelen İADE kargolarını MNG'den sorgula.
      - Kargo hareketi (ilk okutma) -> 'return_in_transit' (İade Kargoda) + bildirim
      - Depoya teslim -> 'returned' (Teslim Alındı; Aksiyon'a düşer) + returned_at + bildirim
      - Barkod 3 gün geçerli: süre dolmuş + hâlâ kargoya verilmemiş -> 'expired'
    customer_returns.status: created -> in_transit -> received | expired
    orders.status:           return_requested -> return_in_transit -> returned
    SOAP çağrıları thread executor'da çalışır (event loop bloklanmaz).
    """
    from routes.deps import db  # lazy
    try:
        from routes.orders import _get_mng_settings
        from order_statuses import get_status_config
        from notification_service import send_notification
        from mng_kargo_client import get_mng_shipment_status
    except Exception as e:
        logger.warning(f"[scheduler][return] import skip: {e}")
        return

    s = await _get_mng_settings()
    if not s.get("is_active") or not s.get("username"):
        return
    user, pw = s["username"], s["password"]

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    cutoff = (now - timedelta(days=45)).isoformat()
    q = {
        "status": {"$in": ["created", "in_transit"]},
        "created_at": {"$gt": cutoff},
        "$or": [
            {"mng_ref": {"$nin": [None, ""]}},
            {"return_code": {"$nin": [None, ""]}},
        ],
    }
    try:
        cfg = await get_status_config(db)
    except Exception:
        cfg = {"notify": {}}
    notify = cfg.get("notify") or {}

    def _expired(vu):
        if not vu:
            return False
        try:
            d = datetime.fromisoformat(str(vu).replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
        except Exception:
            return False
        return now > d

    processed = 0
    try:
        async for rec in db.customer_returns.find(q, {"_id": 0, "barcode_png_b64": 0}).limit(120):
            ref = str(rec.get("mng_ref") or rec.get("return_code") or "").strip()
            if not ref:
                continue
            cur = rec.get("status")  # created | in_transit

            try:
                info = await asyncio.to_thread(
                    get_mng_shipment_status, username=user, password=pw, siparis_no=ref
                )
            except Exception as e:
                logger.warning(f"[scheduler][return] status err {ref}: {e}")
                await asyncio.sleep(0.2)
                continue

            moved = delivered = False
            teslim = aciklama = ""
            if info and info.get("ok"):
                teslim = (info.get("teslim_tarihi") or "").strip()
                statu = (info.get("kargo_statu") or "0").strip()
                aciklama = (info.get("kargo_statu_aciklama") or "")
                _alow = aciklama.lower()
                # Y20: şube/kabul "teslim alındı" hareketini teslimat sayma (iade akışını erken tetikler).
                _pickup2 = any(k in _alow for k in ("teslim alın", "teslim alin", "şubeden teslim",
                                                    "subeden teslim", "şubede teslim", "subede teslim"))
                delivered = (not _pickup2) and (bool(teslim) or ("teslim" in _alow and "edilemedi" not in _alow))
                _acc_kw = ("kabul", "şube", "sube", "okut", "teslim alın", "teslim alin",
                           "işleme", "isleme", "çıkış", "cikis", "girdi", "transfer",
                           "dağıt", "dagit", "yola")
                moved = (statu not in ("", "0")) or any(k in _alow for k in _acc_kw)

            new_ret = new_order = ev = None
            ostamp = {}
            if delivered:
                # B1 fix: iade kargosu depoya ULAŞTI → durum içeride 'returned' (aksiyon/inceleme)
                # olur AMA müşteriye "İadeniz Tamamlandı" SMS'i GÖNDERİLMEZ — para henüz iade
                # edilmedi (erken/yanlış bildirim olurdu). Müşteri, iade bedeli ödenince
                # 'order_refunded' ("İade Bedeliniz Ödendi") bildirimini alır (refund_pay adımı).
                new_ret, new_order, ev = "received", "returned", None
                ostamp["returned_at"] = _parse_tr_dt(teslim) or now_iso
            elif moved and cur == "created":
                new_ret, new_order, ev = "in_transit", "return_in_transit", "order_return_in_transit"
                ostamp["return_shipped_at"] = now_iso

            # Hareket yok / hâlâ created ve 3 günlük barkod süresi dolmuş -> expired
            if new_ret is None:
                if cur == "created" and _expired(rec.get("valid_until")):
                    await db.customer_returns.update_one({"id": rec["id"]},
                        {"$set": {"status": "expired", "updated_at": now_iso}})
                    logger.info(f"[scheduler][return] {ref} -> expired (barkod 3g doldu)")
                await asyncio.sleep(0.2)
                continue

            if new_ret == cur:  # idempotent
                await asyncio.sleep(0.2)
                continue

            await db.customer_returns.update_one({"id": rec["id"]},
                {"$set": {"status": new_ret, "cargo_status_text": aciklama, "updated_at": now_iso}})
            order = await db.orders.find_one(
                {"id": rec.get("order_id")},
                {"_id": 0, "shipping_address": 1, "phone": 1, "email": 1, "total": 1}) or {}
            await db.orders.update_one({"id": rec.get("order_id")}, {"$set": {
                "status": new_order, "return_request.status": new_ret,
                "updated_at": now_iso, **ostamp,
            }})

            nz = notify.get(new_order) or notify.get(new_ret) or {}
            ch = [c for c in ("sms", "email") if nz.get(c)]
            if ch and ev:
                addr = order.get("shipping_address") or {}
                try:
                    await send_notification(
                        db, ev,
                        to_phone=addr.get("phone") or order.get("phone"),
                        to_email=addr.get("email") or order.get("email"),
                        variables={
                            "customer_name": addr.get("full_name") or addr.get("first_name") or "Müşterimiz",
                            "order_number": rec.get("order_number", ""),
                            "tracking_number": ref,
                        },
                        channels=ch,
                    )
                except Exception as e:
                    logger.warning(f"[scheduler][return] notif {ref}: {e}")

            logger.info(f"[scheduler][return] {ref} {cur} -> {new_ret}")
            processed += 1
            await asyncio.sleep(0.25)
    except Exception as e:
        logger.exception(f"[scheduler][return] poll tick failed: {e}")
    if processed:
        logger.info(f"[scheduler][return] polled {processed} return cargo(s)")


async def _notify_back_in_stock():
    """Favorilenen ürünlerden stoğu 'yok' → 'var' geçenleri tespit edip, o ürünü
    favorileyen kullanıcılara 'tekrar stokta' e-postası gönderir.

    db.product_stock_flags ile her favorilenen ürünün stok durumu izlenir; bildirim
    YALNIZCA 0→var geçişinde (ve restok döngüsü başına bir kez) atılır. İlk görülmede
    (flag yok → prev=None) bildirim ATILMAZ; bu deploy sonrası toplu spam'i önler.
    Stok master'ı bu sistem olduğundan (sipariş/iptal/iade/admin/pazaryeri fark etmez)
    bu periyodik kontrol tüm stok-giriş yollarını tek noktadan yakalar.
    """
    import os
    from routes.deps import db
    try:
        from notification_service import send_notification
    except Exception as e:
        logger.warning(f"[scheduler] back-in-stock skip (import): {e}")
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        from company import get_site_url
        site = (await get_site_url(db)) or os.environ.get("SITE_URL", "").rstrip("/")
    except Exception:
        site = os.environ.get("SITE_URL", "").rstrip("/")
    try:
        fav_pids = await db.favorites.distinct("product_id")
        if not fav_pids:
            return
        notified = 0
        for pid in fav_pids:
            if not pid:
                continue
            prod = await db.products.find_one(
                {"id": pid},
                {"_id": 0, "id": 1, "name": 1, "slug": 1, "stock": 1, "variants": 1, "is_active": 1},
            )
            if not prod:
                continue
            variants = prod.get("variants") or []
            if variants:
                total = sum(int(v.get("stock") or 0) for v in variants if isinstance(v, dict))
            else:
                total = int(prod.get("stock") or 0)
            in_stock = (total > 0) and (prod.get("is_active", True) is not False)
            flag = await db.product_stock_flags.find_one({"product_id": pid}, {"_id": 0, "in_stock": 1})
            prev = flag.get("in_stock") if flag else None
            await db.product_stock_flags.update_one(
                {"product_id": pid},
                {"$set": {"product_id": pid, "in_stock": in_stock, "updated_at": now_iso}},
                upsert=True,
            )
            # Sadece 'yok' → 'var' geçişinde bildir (ilk görülmede prev=None → atla)
            if prev is False and in_stock:
                favs = await db.favorites.find(
                    {"product_id": pid}, {"_id": 0, "user_id": 1}
                ).to_list(10000)
                uids = list({f.get("user_id") for f in favs if f.get("user_id")})
                if not uids:
                    continue
                users = await db.users.find(
                    {"id": {"$in": uids}}, {"_id": 0, "email": 1, "first_name": 1}
                ).to_list(10000)
                link = f"{site}/urun/{prod.get('slug') or prod.get('id')}"
                for u in users:
                    email = (u.get("email") or "").strip()
                    if not email or "@" not in email:
                        continue
                    try:
                        await send_notification(
                            db, "wishlist_back_in_stock",
                            to_email=email,
                            variables={
                                "customer_name": (u.get("first_name") or "").strip() or "değerli müşterimiz",
                                "product_name": prod.get("name") or "Favori ürünün",
                                "product_link": link,
                            },
                            channels=["email"],
                        )
                        notified += 1
                    except Exception as ie:
                        logger.warning(f"[scheduler] back-in-stock send failed ({email}): {ie}")

        # DENETİM FIX (#23): "Gelince Haber Ver" (db.stock_notifications) talepleri hiç
        # bildirilmiyordu (orphaned collection). notified=False kayıtları taranır; ürün+beden
        # stoğa girmişse e-posta gönderilir ve notified=True + notified_at yazılır (beden bazlı
        # eşleşme: varyant 'size' ile). Aynı ürün+beden için stok cache'lenir (tek DB okuması).
        try:
            pending = await db.stock_notifications.find(
                {"notified": {"$ne": True}}, {"_id": 0}
            ).to_list(5000)
        except Exception:
            pending = []
        _prod_cache: dict = {}
        for req in pending:
            pid = req.get("product_id")
            size = (req.get("size") or "").strip()
            email = (req.get("email") or "").strip()
            if not pid or not email or "@" not in email:
                continue
            prod = _prod_cache.get(pid)
            if prod is None:
                prod = await db.products.find_one(
                    {"id": pid}, {"_id": 0, "id": 1, "name": 1, "slug": 1, "stock": 1,
                                  "variants": 1, "is_active": 1})
                _prod_cache[pid] = prod or {}
            if not prod:
                continue
            if prod.get("is_active", True) is False:
                continue
            variants = prod.get("variants") or []
            if size and variants:
                # Beden bazlı: yalnız o bedene ait varyant(lar)ın stoğuna bak
                sz_stock = 0
                for v in variants:
                    if not isinstance(v, dict):
                        continue
                    vsize = (v.get("size") or v.get("name") or "").strip()
                    if vsize.lower() == size.lower():
                        sz_stock += int(v.get("stock") or 0)
                available = sz_stock > 0
            elif variants:
                available = sum(int(v.get("stock") or 0) for v in variants if isinstance(v, dict)) > 0
            else:
                available = int(prod.get("stock") or 0) > 0
            if not available:
                continue
            link = f"{site}/urun/{prod.get('slug') or prod.get('id')}"
            _pname = prod.get("name") or "Ürün"
            if size:
                _pname = f"{_pname} ({size} beden)"
            try:
                await send_notification(
                    db, "wishlist_back_in_stock",
                    to_email=email,
                    variables={
                        "customer_name": "değerli müşterimiz",
                        "product_name": _pname,
                        "product_link": link,
                    },
                    channels=["email"],
                )
                await db.stock_notifications.update_one(
                    {"id": req.get("id")},
                    {"$set": {"notified": True, "notified_at": now_iso}},
                )
                notified += 1
            except Exception as ie:
                logger.warning(f"[scheduler] stock-notify send failed ({email}): {ie}")

        if notified:
            logger.info(f"[scheduler] back-in-stock notified={notified}")
    except Exception as e:
        logger.exception(f"[scheduler] back_in_stock failed: {e}")


async def _run_award_referrals():
    """Bölüm C: davet edilenin ilk siparişi oluştuysa referans ödüllerini ver (idempotent)."""
    try:
        from routes.referrals import award_pending_referrals
        await award_pending_referrals()
    except Exception as e:
        logger.exception(f"[scheduler] referans ödül job hata: {e}")


async def _run_award_loyalty():
    """C3: ödemesi onaylanmış üye siparişlerine sadakat puanı yaz + iptal/iadede geri al (idempotent)."""
    try:
        from routes.loyalty import award_loyalty_points
        await award_loyalty_points()
    except Exception as e:
        logger.exception(f"[scheduler] sadakat puanı job hata: {e}")


async def _run_birthday_coupons():
    """Bölüm C: bugün doğum günü olan müşterilere kupon gönder (yıl-başına idempotent)."""
    try:
        from routes.referrals import send_birthday_coupons
        await send_birthday_coupons()
    except Exception as e:
        logger.exception(f"[scheduler] doğum günü job hata: {e}")


# ==================== A2.8: TEK-LİDER (distributed leader lease) ====================
# APScheduler her PROCESS'te çalışır; Railway yatay ölçeklenirse (>1 instance) tüm zamanlı
# işler HER instance'ta tekrar koşar → çift iptal / çift reconcile / çift bildirim. Mongo
# tabanlı kısa süreli lease ile aynı anda YALNIZ bir instance "lider" olur ve işleri o koşar.
# Tek-instance dağıtımda (varsayılan) davranış değişmez. Lease okunamazsa (Mongo hatası)
# tek-instance varsayımıyla iş yine koşar (regresyon yok).
def _instance_label() -> str:
    try:
        from routes.deps import instance_tag
        return instance_tag()
    except Exception:
        return "unknown"


_INSTANCE_ID = str(uuid.uuid4())
_LEASE_TTL_SEC = 120


async def _acquire_or_renew_leadership() -> bool:
    from routes.deps import db  # lazy
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    exp_iso = (now + timedelta(seconds=_LEASE_TTL_SEC)).isoformat()
    # 1) Bize aitse yenile, süresi dolmuşsa devral — tek-döküman atomik koşullu update.
    _prev = await db.scheduler_leader.find_one({"_id": "scheduler_leader"}, {"_id": 0, "holder": 1, "holder_label": 1})
    res = await db.scheduler_leader.update_one(
        {"_id": "scheduler_leader",
         "$or": [{"holder": _INSTANCE_ID}, {"expires_at": {"$lt": now_iso}}]},
        {"$set": {"holder": _INSTANCE_ID, "holder_label": _instance_label(), "expires_at": exp_iso, "renewed_at": now_iso}},
    )
    if res.matched_count > 0:
        # LİDERLİK EL DEĞİŞTİRDİ → kayıt (hangi deployment/replica devraldı). İkinci bir senkron
        # süreci varsa burada farklı etiketler dönüşümlü görünür.
        if _prev and _prev.get("holder") != _INSTANCE_ID:
            try:
                await db.scheduler_leader_log.insert_one({
                    "at": now_iso, "from": _prev.get("holder_label") or (_prev.get("holder") or "")[:8],
                    "to": _instance_label(), "to_id": _INSTANCE_ID[:8]})
            except Exception:
                pass
        return True
    # 2) Henüz kayıt yok → atomik oluştur (benzersiz _id iki liderliği engeller).
    try:
        await db.scheduler_leader.insert_one(
            {"_id": "scheduler_leader", "holder": _INSTANCE_ID,
             "expires_at": exp_iso, "renewed_at": now_iso})
        return True
    except Exception:
        return False  # başka instance kaydı oluşturdu/tutuyor


# Kilitlenme teşhisi: şu an çalışan zamanlayıcı işleri {ad: başlangıç} + süre istatistiği.
RUNNING_JOBS: dict = {}
JOB_STATS: dict = {}


def _lead(fn):
    """İşi yalnız lider instance koşsun diye sarmalar. Lease hatasında tek-instance
    varsayımıyla koşar (regresyon önleme).

    KÖK NEDEN DÜZELTMESİ (havale 72s / influencer takip "hiç çalışmıyor"): deploy sırasında yeni
    instance ilk _LEASE_TTL_SEC (120 sn) boyunca lider olamaz; açılışta +30 sn / +2 dk'ya kurulan
    ilk çalışmalar SESSİZCE atlanıyor ve 30 dk / 1 saatlik işler bir sonraki periyoda kalıyordu
    (art arda deploy'larda hiç sıra alamıyordu). Artık lider olunamayan çalışma, lease süresi
    dolduktan sonra (TTL+30 sn) BİR KEZ yeniden denenir; o da lider değilse gerçekten başka
    instance liderdir → bırakılır."""
    async def _w(*a, _lead_retry=False, **k):
        try:
            if not await _acquire_or_renew_leadership():
                if not _lead_retry and _scheduler is not None:
                    try:
                        _scheduler.add_job(
                            _w, "date",
                            run_date=datetime.now(timezone.utc) + timedelta(seconds=_LEASE_TTL_SEC + 30),
                            id=f"{_w.__name__}__lead_retry", replace_existing=True,
                            kwargs={"_lead_retry": True}, misfire_grace_time=300)
                        logger.info(f"[scheduler] {_w.__name__}: lider değil — {_LEASE_TTL_SEC + 30} sn sonra yeniden denenecek")
                    except Exception as _re:
                        logger.warning(f"[scheduler] {_w.__name__}: lider-retry kurulamadı: {_re}")
                return None
        except Exception as _e:
            logger.warning(f"[scheduler] liderlik kontrolü atlandı ({_e}) — iş yine koşuyor")
        _nm = getattr(fn, "__name__", "job")
        RUNNING_JOBS[_nm] = time.monotonic()
        try:
            return await fn(*a, **k)
        finally:
            _st = RUNNING_JOBS.pop(_nm, None)
            if _st is not None:
                _d = time.monotonic() - _st
                _prev = JOB_STATS.get(_nm) or {"n": 0, "max_s": 0.0}
                JOB_STATS[_nm] = {"n": _prev["n"] + 1, "max_s": round(max(_prev["max_s"], _d), 1),
                                  "last_s": round(_d, 1)}
    _w.__name__ = getattr(fn, "__name__", "job")
    _w.__qualname__ = _w.__name__
    return _w


async def _refresh_instagram_token():
    """SINIRSIZ Instagram feed: 60 günlük kullanıcı token'ı ~45 günde bir otomatik yeniden
    exchange edilir (fb_exchange_token → taze 60 gün). Kullanıcı bir daha dokunmaz.
    token_obtained_at 45 günden yeniyse hiçbir şey yapmaz; app_id sayısal değilse (bozuk kayıt) atlar.
    Ödeme/sipariş akışıyla ilgisi yoktur — tamamen bağımsız görev."""
    from routes.deps import db
    try:
        from security.crypto import encrypt, decrypt
    except Exception:
        def encrypt(x): return x
        def decrypt(x): return x
    try:
        s = await db.settings.find_one({"id": "instagram"}, {"_id": 0}) or {}
        tok_enc = s.get("access_token")
        app_id = str(s.get("app_id") or "").strip()
        app_secret_enc = s.get("app_secret")
        obtained = s.get("token_obtained_at")
        if not (tok_enc and app_id and app_secret_enc and obtained) or not app_id.isdigit():
            return
        try:
            _dt = datetime.fromisoformat(obtained)
            if _dt.tzinfo is None:
                _dt = _dt.replace(tzinfo=timezone.utc)
        except Exception:
            return
        if (datetime.now(timezone.utc) - _dt).days < 45:
            return  # henüz erken
        cur_token = decrypt(tok_enc)
        app_secret = decrypt(app_secret_enc)
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get("https://graph.facebook.com/v23.0/oauth/access_token", params={
                "grant_type": "fb_exchange_token", "client_id": app_id,
                "client_secret": app_secret, "fb_exchange_token": cur_token})
        if r.status_code == 200 and (r.json() or {}).get("access_token"):
            new_tok = r.json()["access_token"]
            await db.settings.update_one({"id": "instagram"}, {"$set": {
                "access_token": encrypt(new_tok),
                "token_obtained_at": datetime.now(timezone.utc).isoformat(),
                "token_refreshed_at": datetime.now(timezone.utc).isoformat(),
                "last_error": ""}})
            logger.info("[instagram] uzun ömürlü token otomatik yenilendi (+60 gün)")
        else:
            _t = r.text[:200] if hasattr(r, "text") else str(r.status_code)
            logger.warning(f"[instagram] token yenilenemedi: {_t}")
    except Exception as e:
        logger.warning(f"[instagram] token refresh hata: {e}")


async def _run_visual_index_refresh():
    """WhatsApp görselden-ürün-tanıma hafızasını OTOMATİK doldurur/günceller.
    Yalnız EKSİK (indekslenmemiş) aktif ürünleri işler → ilk çalışmada tümünü kurar,
    sonraki çalışmalarda yeni eklenenleri tamamlar (token/manuel tetik gerekmez)."""
    try:
        from routes.whatsapp_webhook import _run_visual_index_build
        await _run_visual_index_build(force=False)
    except Exception as e:
        logger.error(f"[cron] görsel indeks yenileme hatası: {e}")


async def _run_member_stats_refresh():
    """Üye sipariş istatistiklerini (users.cached_*) yeniden hesapla — üye listesi/segment/stats
    sayfaları bu önbellekten okur (per-üye aggregation kaldırıldı → sayfalar anında açılır)."""
    try:
        from routes.members import _refresh_member_stats
        res = await _refresh_member_stats()
        logger.info(f"[cron] Üye istatistik önbelleği güncellendi: {res}")
    except Exception as e:
        logger.warning(f"[cron] Üye istatistik refresh hata: {e}")


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    # DENETİM (2026-09-29): varsayılan misfire_grace_time 1 sn → tetik anında döngü 1 sn meşgulse
    # günlük işler (doğum günü kuponu, stok uyarıları) o gün SESSİZCE atlanıyordu. İş tanımında
    # açıkça verilen değerler geçerliliğini korur.
    _scheduler = AsyncIOScheduler(timezone="UTC", job_defaults={"misfire_grace_time": 3600, "coalesce": True})

    def _add(fn, *a, **k):
        # A2.8: her iş lider-sarmalıyla eklenir (çok-instance'ta çift çalışmayı önler).
        return _scheduler.add_job(_lead(fn), *a, **k)
    # Üye sipariş istatistiği önbelleği (users.cached_*): boot+60s'de ilk dolum, sonra 15 dk'da bir.
    # Üye listesi/segment/stats sayfalarının hızı için — canlı per-üye aggregation kaldırıldı.
    _add(
        _run_member_stats_refresh,
        "interval",
        minutes=15,
        id="member_stats_refresh",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=60),
        max_instances=1,
        coalesce=True,
    )
    # SINIRSIZ Instagram feed: token'ı günde bir kontrol et, 45 günü geçince otomatik yenile.
    _add(
        _refresh_instagram_token,
        "interval",
        hours=24,
        id="instagram_token_refresh",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=120),
        max_instances=1,
        coalesce=True,
    )
    # WhatsApp görsel hafızası (görselden ürün tanıma) — OTOMATİK doldur/güncelle.
    # İlk çalışma boot+3dk'da tüm eksikleri kurar; 12 saatte bir yeni ürünleri tamamlar
    # (yalnız indekslenmemişleri işler → tekrar tarama yapmaz, maliyet düşük).
    _add(
        _run_visual_index_refresh,
        "interval",
        hours=12,
        id="wa_visual_index_refresh",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=180),
        max_instances=1,
        coalesce=True,
    )
    # Run every 30 minutes; catches orders promptly as they cross the 48h mark
    _add(
        auto_cancel_unpaid_havale_orders,
        "interval",
        minutes=30,
        id="auto_cancel_havale_48h",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=30),
        max_instances=1,
        coalesce=True,
    )
    # Havale/EFT ödeme HATIRLATMA — her 30 dk; süre İşletme Kuralları'ndan (varsayılan 24 saat)
    _add(
        send_havale_payment_reminders,
        "interval",
        minutes=30,
        id="havale_payment_reminder",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=90),
        max_instances=1,
        coalesce=True,
    )
    # SÜRESİ DOLAN SİTE İADE TALEPLERİ: kargoya verilmeyen talepler sonsuza kadar
    # "iade" görünmesin; sipariş normale dönsün (ciroya girsin, listede çıksın).
    _add(
        expire_stale_site_return_requests,
        "interval",
        hours=6,
        id="expire_stale_return_requests",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=90),
        max_instances=1,
        coalesce=True,
    )
    # KRİTİK: başarısız/ödenmemiş KART siparişleri — 3 saat sonra iptal + stok iadesi.
    # Önceden HİÇ zamanlanmamıştı → başarısız kart ödemeleri stoğu kalıcı sızdırıyordu.
    _add(
        auto_cancel_unpaid_card_orders,
        "interval",
        minutes=30,
        id="auto_cancel_card_24h",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=45),
        max_instances=1,
        coalesce=True,
    )
    # iyzico OTOMATİK reconcile: para çekilmiş ama 'ödendi' işaretlenmemiş kart siparişlerini
    # her 15 dk'da iyzico'dan doğrulayıp finalize eder (elle recover-charged gerekmez).
    _add(
        reconcile_charged_but_unrecorded_orders,
        "interval",
        minutes=15,
        id="iyzico_reconcile_charged",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=90),
        max_instances=1,
        coalesce=True,
    )
    # İYS: bildirilmemiş izinleri her 30 dk'da NetGSM'e yeniden gönder. NetGSM modülü
    # aktif olur olmaz (yansıma/aktivasyon gecikmesi sonrası) bekleyenler otomatik geçer.
    _add(
        retry_pending_iys_consents,
        "interval",
        minutes=60,
        id="iys_retry_pending",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=60),
        max_instances=1,
        coalesce=True,
    )
    # Instagram akışı — auto_sync açık + token varsa her 30 dk mağazanın Instagram gönderilerini tazeler.
    try:
        from routes.instagram import auto_sync_instagram
        # İşletme isteği: Instagram feed'i 2 GÜNDE BİR arka planda otomatik tara (elle "şimdi çek" dışında).
        # Boot'tan 2 dk sonra bir kez, sonra her 48 saatte bir. (Önceden 30 dk idi — IG API'ye
        # gereksiz yüktü ve etkili çalışmıyordu; istenen kadans 2 gün.)
        _add(
            auto_sync_instagram,
            "interval",
            days=2,
            id="instagram_auto_sync",
            next_run_time=datetime.now(timezone.utc) + timedelta(seconds=120),
            max_instances=1,
            coalesce=True,
        )
    except Exception as _e:
        logging.getLogger("scheduler").warning("[scheduler] instagram job eklenemedi: %s", _e)
    # Tek seferlik: konsinye stok alanını veritabanından da kaldır (ölü alan).
    _add(
        _ensure_consignment_removed,
        "date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=30),
        id="ensure_consignment_removed_once",
        # Açılış yavaşsa iş düşmesin: APScheduler varsayılan gecikme
        # toleransı 1 sn ve "date" tetikleyicisi bir daha çalışmaz.
        misfire_grace_time=3600,
    )
    # Tek seferlik: geçmiş iptallerin tarihini kanıttan çıkar ve DONDUR.
    # SIRA ÖNEMLİ: iptal damgası basabilen TÜM işlerden (Trendyol iptal taraması +30 sn,
    # pazaryeri senkron tick'i +45 sn) ÖNCE çalışmalı; aksi halde onların "şimdi"
    # damgası kanıta dayalı tarihin yerini kapar (2026-09-23 olayı). Bayrak 'done'
    # olduğunda no-op; bu sıralama yeni kurulumlar içindir.
    _add(
        _ensure_cancelled_at_backfill,
        "date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=10),
        id="ensure_cancelled_at_backfill_once",
        misfire_grace_time=3600,
    )
    _add(
        _ensure_restock_delta_backfill,
        "date",
        run_date=datetime.now(timezone.utc) + timedelta(seconds=35),
        id="ensure_restock_delta_backfill_once",
        # Açılış yavaşsa iş düşmesin: APScheduler varsayılan gecikme
        # toleransı 1 sn ve "date" tetikleyicisi bir daha çalışmaz.
        misfire_grace_time=3600,
    )
    # Beden kimliği kuralı (id = 4 haneli urun_id, tekil) — 6 saatte bir + açılıştan 150 sn sonra.
    _add(
        _run_varyant_id_normalize,
        "interval",
        hours=6,
        id="varyant_id_normalize",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=150),
        max_instances=1,
        coalesce=True,
    )
    # O12: "Günde bir" işleri SABİT SAATLİ cron ile çalıştır (07:00 UTC ≈ 10:00 İstanbul).
    # Önceki `interval hours=24 + next_run_time=now+2dk` her PROCESS RESTART'ında çalışıyor ve
    # düşük-stok e-postası sent-flag'i olmadığından her deploy'da MÜKERRER mail gidiyordu; ayrıca
    # "günlük" saat her restart'ta kayıyordu. cron ile gün içinde tam olarak bir kez tetiklenir.
    # Terkedilmiş sepet e-postası: 30 dk'da bir tarar (12 saatlik gecikme dakika hassasiyetinde
    # tutulsun diye). Gönderim bayrağı sepet + üye bazında → restart/deploy mükerrer mail üretmez.
    _add(
        _send_abandoned_cart_reminders,
        "interval",
        minutes=30,
        id="abandoned_cart_reminders",
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=5),
        max_instances=1,
        coalesce=True,
    )
    _add(
        _send_daily_stock_alert,
        "cron",
        hour=7, minute=10,
        id="daily_stock_alert",
        max_instances=1,
        coalesce=True,
    )
    # Favori ürün tekrar stokta — her 30 dk favorilenen ürünlerin stoğunu kontrol eder;
    # 'yok'→'var' geçişinde o ürünü favorileyenlere markalı e-posta atar (döngü başına 1 kez).
    _add(
        _notify_back_in_stock,
        "interval",
        minutes=30,
        id="wishlist_back_in_stock",
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=2),
        max_instances=1,
        coalesce=True,
    )
    # Iter 43 — Günlük stok tükenme uyarısı (her gün sabah 9:00 UTC, ~12:00 TR)
    async def _daily_stockout_alert():
        try:
            from routes.reports_v2 import send_stockout_alert_email
            class _SystemAdmin:
                def get(self, k, *a): return "system@localhost" if k == "email" else None
            await send_stockout_alert_email(admin=_SystemAdmin())
            logger.info("[scheduler] daily stockout alert sent")
        except Exception as e:
            logger.warning(f"[scheduler] stockout alert failed: {e}")
    from apscheduler.triggers.cron import CronTrigger
    _add(
        _daily_stockout_alert,
        CronTrigger(hour=9, minute=0),
        id="daily_stockout_alert",
        max_instances=1, coalesce=True,
    )
    # §7 — Güvenlik/audit/SP-API log retention: ≥12 ay sakla, aşanı temizle. Haftalık (Pzt 04:00 UTC).
    _add(
        _security_log_retention_purge,
        CronTrigger(day_of_week="mon", hour=4, minute=0),
        id="security_log_retention_purge",
        next_run_time=datetime.now(timezone.utc) + timedelta(minutes=5),
        max_instances=1, coalesce=True,
    )
    # DHL/MNG kargo durum taramasi — her 30 dk (site siparisleri; takip linki -> Kargoya Verildi, teslim -> Teslim Edildi)
    _add(
        _dhl_cargo_poll_tick,
        "interval",
        minutes=30,
        id="dhl_cargo_poll",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=60),
        max_instances=1,
        coalesce=True,
    )
    _add(
        _return_cargo_poll_tick,
        "interval",
        minutes=5,
        id="return_cargo_poll",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=90),
        max_instances=1,
        coalesce=True,
    )
    # Bölüm C — Referans ödülleri (davet edilenin ilk siparişi geldiyse) her 20 dk.
    _add(
        _run_award_referrals,
        "interval",
        minutes=20,
        id="referral_award",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=120),
        max_instances=1,
        coalesce=True,
    )
    # C3 — Sadakat puanları: ödenmiş siparişlere puan + iptalde geri alma, her 30 dk.
    _add(
        _run_award_loyalty,
        "interval",
        minutes=30,
        id="loyalty_award",
        next_run_time=datetime.now(timezone.utc) + timedelta(seconds=180),
        max_instances=1,
        coalesce=True,
    )
    # Bölüm C — Doğum günü kuponları: her gün 07:00 UTC (~10:00 TR).
    _add(
        _run_birthday_coupons,
        "cron",
        hour=7,
        minute=0,
        id="birthday_coupons",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("[scheduler] Background scheduler started (auto-cancel every 30 min + abandoned cart e-mail every 30 min)")
    return _scheduler


def shutdown_scheduler():
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None
