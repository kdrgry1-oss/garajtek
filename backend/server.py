"""
E-Commerce API - Main Server
Modular architecture with routes
"""
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
import logging
from pathlib import Path

# Load .env early so env-based integrations (EMERGENT_LLM_KEY etc.) are available
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except Exception:
    pass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
# httpx, istek URL'ini INFO seviyesinde komple loglar — CAPI gibi token'i query-string'de
# tasiyan cagrilarda access_token DUZ METIN olarak log'a duser (Railway log akisi vb. sizinti
# riski). Request-level INFO loglarini WARNING'e cekerek bunu engelle (hatalar yine gorunur).
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Import routes
from routes import (
    auth_router,
    products_router,
    orders_router,
    categories_router,
    banners_router,
    cms_router,
    integrations_router,
    admin_router,
    customer_router,
    variants_router,
    webhooks_router,
    attributes_router,
    upload_router,
    upload_files_router,
    settings_router,
)
from routes.vendors import router as vendors_router
from routes.pages import router as pages_router
from routes.admin_rbac import router as admin_rbac_router
from routes.seo import router as seo_router
from routes.locations import router as locations_router
from routes.attribution import router as attribution_router
from routes.members import router as members_router
from routes.consents import router as consents_router
from routes.coupons import admin_router as coupons_admin_router, public_router as coupons_public_router, campaigns_router as campaigns_router
from routes.reports import router as reports_router
from routes.report_assistant import router as report_assistant_router
from routes.extras import (
    cart_router,
    admin_cart_router,
    reviews_public_router,
    reviews_admin_router,
    seo_public_router,
    seo_admin_router,
)
from routes.catalog_extras import (
    brands_router, tags_router, member_groups_router, announcements_router, popups_router,
    storefront_extras_router,
    alerts_public_router, alerts_admin_router,
    havale_public_router, havale_admin_router,
    admin_orders_router,
    rules_router,
    extra_reports_router,
    tickets_public_router, tickets_admin_router,
    email_admin_router,
    currency_router,
)
from routes.business_rules_api import admin_router as business_rules_admin_router, public_router as business_rules_public_router
from routes.help_center import admin_router as help_center_admin_router, public_router as help_center_public_router
from routes.referrals import public_router as referrals_public_router, admin_router as referrals_admin_router
from routes.shared_carts import router as shared_carts_router
from routes.gift_cards import router as gift_cards_router, admin_router as gift_cards_admin_router
from routes.loyalty import router as loyalty_router
from routes.barcode_cards import router as barcode_cards_router
from routes.provider_settings import router as provider_settings_router
from routes.iys import router as iys_consent_router  # /iys — OTP + ticari ileti izni (iys_router ile ÇAKIŞMASIN)
from routes.automation_status import router as automation_status_router
from routes.footer_template import public_router as footer_public_router, admin_router as footer_admin_router
from routes.newsletter import public_router as newsletter_public_router, admin_router as newsletter_admin_router
from routes.rooftr_returns import router as rooftr_returns_router
from routes.bulk_ops import router as bulk_ops_router
from routes.analytics_extra import router as analytics_extra_router
from routes.notifications import router as notifications_router
from routes.capi import router as capi_router
from services.capi.orchestrator import background_retry_loop as capi_retry_bg_loop
from routes.customer_risk import router as customer_risk_router
from routes.marketing_pixels import router as marketing_pixels_router
from routes.social_auth import router as social_auth_router
from routes.security_dashboard import router as security_dashboard_router
from routes.secrets_vault import router as secrets_vault_router
from routes.system_health import router as system_health_router
from routes.mail_admin import router as mail_admin_router  # kendi mail sunucusu (deploy/mail)
from routes.reports_v2 import router as reports_v2_router, costs_router as product_costs_router
from routes.iys_integration import router as iys_router

# Database
from routes.deps import client, db

async def ensure_cod_default_once():
    from cod_rules import ensure_cod_default
    res = await ensure_cod_default(db)
    if res in ("enabled", "kept"):
        logger.info(f"[kapıda ödeme] varsayılan uygulandı: {res}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown"""
    # Startup
    logger.info("Starting E-Commerce API...")
    
    try:
        # Create admin user if not exists — e-posta YALNIZ env ADMIN_INITIAL_EMAIL'den.
        from routes.deps import bootstrap_admin_email as _bootstrap_admin_email
        _admin_email = _bootstrap_admin_email()
        admin = await db.users.find_one({"email": _admin_email}) if _admin_email else None
        if not _admin_email:
            logger.warning("Admin bootstrap atlandı: ADMIN_INITIAL_EMAIL tanımlı değil "
                           "(ilk yönetici hesabı için ADMIN_INITIAL_EMAIL + ADMIN_INITIAL_PASSWORD verin)")
        elif not admin:
            from routes.deps import hash_password, generate_id
            from datetime import datetime, timezone
            # Bootstrap parolası diske veya loga yazılmaz. Yeni ortamda yönetici
            # oluşturmak için güçlü parola deployment secret'ı olarak verilmelidir.
            _admin_pw = (os.environ.get("ADMIN_INITIAL_PASSWORD") or "").strip()
            if len(_admin_pw) < 12:
                logger.error("Admin bootstrap atlandı: ADMIN_INITIAL_PASSWORD en az 12 karakter olmalı")
            else:
                await db.users.insert_one({
                    "id": generate_id(),
                    "email": _admin_email,
                    "password": hash_password(_admin_pw),
                    "first_name": "Admin",
                    "last_name": "User",
                    "is_admin": True,
                    "is_super_admin": True,
                    "is_active": True,
                    "must_change_password": True,
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"Admin olusturuldu ({_admin_email}) — ADMIN_INITIAL_PASSWORD kullanildi.")
        # Never elevate an existing account solely because its email matches
        # the bootstrap address. Existing owners retain their explicit flag/role.

        # KURTARMA KOLU (kilitlenme önlemi): 7e50926 ile rolsüz hesaplar ve is_super_admin
        # bayrağı olmayan sahip hesabı yönetim API'sine giremez (403) ve panelden rol/bayrak
        # atayamaz (tavuk-yumurta). DB erişimi olmadan güvenli çıkış: yalnız deployment
        # secret'ı OWNER_SUPER_ADMIN_EMAILS (virgülle ayrılmış) ile listelenen MEVCUT hesaplar
        # is_super_admin=True yapılır. Env boşsa hiçbir şey yapılmaz; e-posta ile örtük yükseltme YOK.
        try:
            _owners = [e.strip().lower() for e in (os.environ.get("OWNER_SUPER_ADMIN_EMAILS") or "").split(",") if e.strip()]
            for _oe in _owners:
                _res = await db.users.update_one(
                    {"email": _oe, "is_super_admin": {"$ne": True}},
                    {"$set": {"is_super_admin": True, "is_admin": True, "is_active": True}})
                if _res.modified_count:
                    logger.warning(f"[guvenlik] OWNER_SUPER_ADMIN_EMAILS: {_oe} is_super_admin=True yapildi")
            _n_super = await db.users.count_documents({"is_super_admin": True, "is_active": {"$ne": False}})
            if _n_super == 0:
                logger.error("[guvenlik] SİSTEMDE AKTİF SÜPER-ADMİN YOK — panel yönetimi kilitli olabilir. "
                             "Railway'de OWNER_SUPER_ADMIN_EMAILS=<sahip e-postası> tanımlayıp yeniden başlatın.")
        except Exception as _oe_err:
            logger.error(f"[guvenlik] owner bootstrap hatasi: {_oe_err}")

        # GÜVENLİK: is_admin=True kalmış MÜŞTERİ hesaplarını (personel işareti taşımayan:
        # created_by/role_id/is_super_admin/varsayılan admin YOK) admin'likten düşür →
        # Üyeler listesine geçsinler, panele giremesinler. İdempotent; her başlangıçta güvenli.
        try:
            from routes.admin_rbac import demote_customer_admins
            _dc = await demote_customer_admins()
            if _dc.get("demoted"):
                logger.warning(f"[guvenlik] {_dc['demoted']} musteri hesabi admin'likten dusuruldu (Uyeler'e tasindi).")
        except Exception as _de:
            logger.error(f"[guvenlik] customer-admin temizligi hatasi: {_de}")

        # TELAFİ: bozuk/eksik XML feed yüzünden pasife alınmış ("eski altyapı") ürünleri
        # TEK SEFER geri aktif et — "bazı ürünler yok oldu" sorununu otomatik onarır (bayrakla 1 kez).
        try:
            from routes.integrations_common import restore_xml_missing_products_once
            _rx = await restore_xml_missing_products_once()
            if _rx.get("restored"):
                logger.warning(f"[urun-telafi] {_rx['restored']} pasife alinan urun geri aktiflestirildi.")
        except Exception as _re:
            logger.error(f"[urun-telafi] xml-missing restore hatasi: {_re}")

        # TELAFİ: parası HİÇ alınmadığı hâlde 'İptal Edildi' görünen (auto-cancel) kart siparişlerini
        # 'payment_failed' (Ödeme Alınamadı) yap → ekip yanlışlıkla PARA İADESİ yapmasın. İdempotent.
        try:
            from routes.orders import reclassify_auto_cancelled_unpaid_orders
            _rf = await reclassify_auto_cancelled_unpaid_orders()
            if _rf.get("reclassified"):
                logger.warning(f"[odeme-telafi] {_rf['reclassified']} odenmemis 'iptal' siparis 'payment_failed' yapildi.")
        except Exception as _rfe:
            logger.error(f"[odeme-telafi] reclassify hatasi: {_rfe}")

        # ÖZELLİK VARSAYILANLARI: koddaki mağaza sabit varsayılanlarını (brand_defaults —
        # beyaz etikette varsayılan boş) attributes.default_value alanına
        # İDEMPOTENT tohumla → Özellik Ayar Kartı'nda görünür/düzenlenebilir. DB OTORİTEDİR:
        # yalnız alan HİÇ yoksa yazar, kullanıcı silince ("") yeniden dayatmaz.
        try:
            from routes.attributes import seed_attribute_defaults
            _sd = await seed_attribute_defaults()
            if _sd.get("created") or _sd.get("seeded"):
                logger.info(f"[ozellik-seed] {_sd.get('created', 0)} yeni ozellik olusturuldu, "
                            f"{_sd.get('seeded', 0)} varsayilan deger tohumlandi.")
        except Exception as _se:
            logger.error(f"[ozellik-seed] hata: {_se}")

        # KURUMSAL / HUKUKİ SAYFALAR (KVKK, Mesafeli Satış, İade, Garanti …) + Şirket Bilgileri
        # varsayılanları: İDEMPOTENT — yalnız eksik sayfa eklenir, yalnız el değmemiş sayfa
        # yükseltilir, firma alanlarına yalnız boşsa ve bir kez yazılır (bkz. legal_pages.py).
        try:
            from legal_pages import run_startup as _legal_startup
            await _legal_startup(db, logger)
        except Exception as _lpe:
            logger.error(f"[legal-pages] hata: {_lpe}")

        # Create indexes
        await db.products.create_index("slug")
        await db.products.create_index("stock_code")
        # Performans: ürün listesi/detay sorguları için (Iter perf)
        await db.products.create_index("id")
        await db.products.create_index("category_name")
        await db.products.create_index([("is_active", 1), ("created_at", -1)])
        await db.products.create_index([("category_ids", 1), ("is_active", 1)])
        await db.orders.create_index("order_number")
        await db.orders.create_index("user_id")
        # Müşteri risk skoru (sipariş listesi) e-posta eşleşmesi — eskiden indekssiz tarama.
        for _ix in (("orders", "shipping_address.email"), ("orders", "email"),
                    ("customer_returns", "user_id"), ("customer_returns", "customer_email")):
            try:
                await db[_ix[0]].create_index(_ix[1])
            except Exception as _ixe:
                logger.warning(f"index {_ix}: {_ixe}")
        # Performans: sipariş listesi tarih/durum/platform filtreleri için
        await db.orders.create_index([("created_at", -1)])
        await db.orders.create_index([("status", 1), ("created_at", -1)])
        await db.orders.create_index([("platform", 1), ("created_at", -1)])
        await db.orders.create_index([("payment_status", 1), ("created_at", -1)])
        # RAPOR PERFORMANSI: her satış raporunun ana filtresi effective_order_date_match ->
        #   {$or: [ {marketplace_order_date: {$gte,$lte}},
        #           {marketplace_order_date: {$in:[None,""]}, created_at: {$gte,$lte}} ]}
        # marketplace_order_date HİÇ indeksli değildi → her rapor açılışı TÜM orders
        # koleksiyonunu tarıyordu (raporlar sayfası geç açılıyordu). Bu bileşik indeks
        # $or'un İKİ dalını da karşılar: 1. dal için ön-ek (aralık), 2. dal için eşitlik
        # (None/"") + created_at aralığı.
        await db.orders.create_index([("marketplace_order_date", 1), ("created_at", -1)])
        # DÖNEM MUHASEBESİ: iptaller iptal tarihine göre sayılır (cancelled_at ?? updated_at).
        await db.orders.create_index([("cancelled_at", -1)])
        # KISMİ İPTAL taraması: partial_cancel_amount indekssizdi → her rapor yüklemesinde
        # TÜM sipariş koleksiyonu taranıyordu (ay değiştirmenin yavaşlığının ana sebebi).
        # Kısmi iptal nadir olduğu için partial (sparse) indeks: koleksiyonun küçük bir
        # kısmını tutar, yazma maliyeti yok denecek kadar azdır.
        await db.orders.create_index(
            [("partial_cancel_at", -1)],
            partialFilterExpression={"partial_cancel_amount": {"$gt": 0}})
        await db.orders.create_index(
            [("updated_at", -1)],
            partialFilterExpression={"partial_cancel_amount": {"$gt": 0}},
            name="partial_cancel_updated_at")
        # İADE / GİDER PUSULASI performansı (Atlas "Scanned/Returned > 1000" uyarısı):
        # bu koleksiyonlar order_number/return_id/status ile SÜREKLİ sorgulanıyordu
        # ama index YOKTU → her sorgu tam koleksiyon taraması. Sık filtre alanlarını indeksle.
        await db.customer_returns.create_index("order_id")
        await db.customer_returns.create_index("order_number")
        await db.customer_returns.create_index([("status", 1), ("created_at", -1)])
        await db.customer_returns.create_index([("created_at", -1)])
        # DÖNEM MUHASEBESİ (raporlar): iadeler gider pusulasının KESİLDİĞİ tarihe göre
        # sayılıyor; bu sorgu indekssizdi → her rapor yüklemesinde tam tarama.
        await db.gider_pusulasi.create_index([("created_at", -1)])
        await db.gider_pusulasi.create_index("claim_id")
        await db.gider_pusulasi.create_index("return_id")
        await db.gider_pusulasi.create_index("order_number")
        await db.gider_pusulasi.create_index([("number", -1)])
        await db.order_events.create_index([("order_id", 1), ("created_at", -1)])
        await db.order_events.create_index([("created_at", -1)])
        await db.orders_deleted.create_index([("deleted_at", -1)])
        # DENETİM (DB-bütünlük): sıcak sorgular COLLSCAN'liyordu → indeks. unique DEĞİL (mevcut
        # veride olası duplikeler boot'u kırmasın; benzersizlik ayrı dedup migration ister).
        await db.orders.create_index("id")                       # ödeme callback {"id": order_id}
        await db.orders.create_index("iyzico_payment_id")        # cross-order paymentId replay kontrolü
        # DENETİM (race R1): idempotency_key partial-UNIQUE — eşzamanlı çift POST /orders'ı DB
        # seviyesinde reddeder (çift sipariş). Ayrı try: mevcut duplike varsa DİĞER indeksleri kırmasın.
        try:
            await db.orders.create_index(
                "idempotency_key", unique=True,
                partialFilterExpression={"idempotency_key": {"$type": "string"}})
        except Exception as _ie:
            logger.warning(f"idempotency_key unique index atlandı (mevcut duplike olabilir): {_ie}")
        await db.stock_movements.create_index([("order_id", 1), ("type", 1)])   # iptal/restock idempotency
        await db.stock_movements.create_index([("product_id", 1), ("created_at", -1)])
        # Per-SKU defter toplamı (stok izi / mutabakat raporu): deltalar items[]/moves[]
        # içinde durur; bu indeksler olmadan her ürün için koleksiyon taraması gerekir.
        await db.stock_movements.create_index([("items.product_id", 1), ("created_at", -1)])
        await db.stock_movements.create_index([("moves.product_id", 1), ("created_at", -1)])
        await db.stock_movements.create_index([("items.barcode", 1)])
        await db.stock_movements.create_index([("moves.barcode", 1)])
        await db.coupons.create_index("code")                    # checkout apply_coupon (public)
        await db.gift_cards.create_index("code")
        await db.products.create_index("barcode")                # barkod→ürün çözümü
        await db.products.create_index("variants.barcode")
        await db.cargo_logs.create_index([("created_at", -1)])
        await db.attribution_sessions.create_index("session_id")
        try:
            await db.users.create_index("id")  # her kimlikli istekte users.find_one({"id"}) — COLLSCAN'i önler
        except Exception as _uie:
            logger.warning(f"users.id index: {_uie}")
        await db.users.create_index("email", unique=True)
        # Üye listesi/segment hızı: is_admin+created_at (sıralama), cached_segment (segment filtresi),
        # cached_spent (VIP/harcama sıralaması). Sipariş istatistiği artık users.cached_* önbelleğinden.
        await db.users.create_index([("is_admin", 1), ("created_at", -1)])
        await db.users.create_index([("cached_segment", 1)])
        await db.users.create_index([("cached_spent", -1)])
        # Security audit indexes — fast forensic queries as the collection grows
        await db.auth_audit_logs.create_index([("created_at", -1)])
        await db.auth_audit_logs.create_index([("event", 1), ("email", 1), ("created_at", -1)])
        await db.auth_audit_logs.create_index([("ip", 1), ("created_at", -1)])
        await db.auth_audit_logs.create_index([("success", 1), ("created_at", -1)])
        await db.audit_logs.create_index([("created_at", -1)])
        await db.audit_logs.create_index([("actor.email", 1), ("created_at", -1)])
        await db.audit_logs.create_index([("action", 1), ("source", 1), ("created_at", -1)])
        # IP blocklist (Iter36 — brute force IP-level ban)
        await db.ip_blocklist.create_index([("ip", 1)], unique=True)
        await db.ip_blocklist.create_index([("blocked_until", 1)])
        # Secrets Vault & monitoring (Iter39)
        await db.vault_secrets.create_index("key", unique=True)
        await db.error_logs.create_index([("created_at", -1)])
        await db.error_logs.create_index([("level", 1), ("created_at", -1)])
        await db.error_logs.create_index([("kind", 1), ("created_at", -1)])
        await db.alerts.create_index([("created_at", -1)])
        await db.alerts.create_index([("read", 1), ("created_at", -1)])
        await db.alerts.create_index([("fingerprint", 1), ("created_at", -1)])
        # Product costs (manuel maliyet) — Iter 42
        await db.product_costs.create_index("product_id", unique=True)
        # Iter 43 indexes
        await db.iys_permissions.create_index(
            [("recipient", 1), ("recipient_type", 1), ("message_type", 1)], unique=True)
        await db.iys_permissions.create_index([("expires_at", 1)])
        
        logger.info("Database indexes created")
    except Exception as e:
        logger.warning(f"Database initialization warning (server will still start): {e}")

    # BİR KEZ — Sipariş SMS şablonlarını GÜNCEL varsayılan metinlere uygula (kullanıcı onayı).
    # Belgin metinleri: {customer_name} Ad Soyad + {order_number} + kargo için {tracking_url} LİNKİ.
    # settings.migrations.sms_templates_belgin_v2 flag'i ile YALNIZ BİR KEZ çalışır; bu uygulamadan
    # sonraki manuel düzenlemeler korunur (bir daha ezmez).
    try:
        _mig = await db.settings.find_one({"id": "migrations"},
                                          {"_id": 0, "sms_templates_belgin_v2": 1}) or {}
        if not _mig.get("sms_templates_belgin_v2"):
            from routes.notifications import _DEFAULT_TEMPLATES
            _n = 0
            for (_ev, _ch), _body in _DEFAULT_TEMPLATES.items():
                if _ch != "sms" or not _body:
                    continue
                await db.notification_templates.update_one(
                    {"event": _ev, "channel": "sms"},
                    {"$set": {"event": _ev, "channel": "sms", "body": _body, "enabled": True,
                              "manually_edited": False,
                              "updated_at": datetime.now(timezone.utc).isoformat(),
                              "updated_by": "system_migration"}},
                    upsert=True,
                )
                _n += 1
            await db.settings.update_one({"id": "migrations"},
                                         {"$set": {"sms_templates_belgin_v2": True}}, upsert=True)
            logger.info(f"[migration] sms_templates_belgin_v2 uygulandı: {_n} SMS şablonu")
    except Exception as e:
        logger.warning(f"[migration] sms_templates_belgin_v2 atlandı: {e}")

    # Start background scheduler (auto-cancel 48h unpaid havale orders)
    try:
        from scheduler import start_scheduler
        start_scheduler()
        # Olay döngüsü kilitlenme izleyicisi (teşhis: destek_q=blokaj)
        try:
            from security.monitoring import loop_lag_monitor as _llm
            import asyncio as _aio_llm
            _aio_llm.create_task(_llm())
        except Exception as _llm_e:
            logger.warning(f"loop lag monitor başlatılamadı: {_llm_e}")
    except Exception as e:
        logger.warning(f"Scheduler start warning: {e}")

    # Start CAPI (Conversions API) retry queue (30 dk'da bir)
    try:
        import asyncio as _asyncio
        _asyncio.create_task(capi_retry_bg_loop(lambda: db, interval_seconds=1800))
        logger.info("CAPI retry queue background loop started (her 30 dk)")
    except Exception as e:
        logger.warning(f"CAPI retry loop start warning: {e}")

    # Tek seferlik onarım: geçmişte iptal edilmiş siparişlerde yanan kupon hakları
    # geri açılır (hoş geldin kodu iptal sonrası tekrar kullanılamıyordu) — bayrak korumalı.
    try:
        import asyncio as _asyncio
        from routes.orders import release_cancelled_redemptions_backfill
        _asyncio.create_task(release_cancelled_redemptions_backfill())
    except Exception as e:
        logger.warning(f"Coupon cancel-release backfill start warning: {e}")

    # Tek seferlik onarım: eski İ-bug'ından bozuk kategori slug'ları (gi-yi-m → giyim)
    # düzeltilir; eski slug alias+301 ile korunur (URL kırılmaz, SEO düzelir).
    try:
        import asyncio as _asyncio
        from routes.categories import repair_category_slugs
        _asyncio.create_task(repair_category_slugs())
    except Exception as e:
        logger.warning(f"Category slug repair start warning: {e}")

    # Garajtek kategori ağacı: categories koleksiyonu BOŞSA data/garajtek_categories.json'dan
    # yüklenir (+ header mega menü kaydı yoksa yazılır). Doluysa hiçbir şeye dokunmaz.
    try:
        import asyncio as _asyncio
        from seed_categories import seed_if_empty as _seed_categories_if_empty
        _asyncio.create_task(_seed_categories_if_empty())
    except Exception as e:
        logger.warning(f"Category seed start warning: {e}")

    # Kapıda ödeme varsayılanı: yönetici hiç değiştirmediyse BİR KEZ açılır (cod_rules.ensure_cod_default).
    try:
        await ensure_cod_default_once()
    except Exception as e:
        logger.warning(f"COD default start warning: {e}")

    # Kupon ilk-sipariş istisna listesi (müşteri destek istisnası) — idempotent seed.
    try:
        import asyncio as _asyncio
        from routes.coupons import seed_coupon_exceptions, migrate_welcome_coupon_sale_policy, migrate_coupon_stacking_default
        _asyncio.create_task(seed_coupon_exceptions())
        # İşletme sahibi kararı (canlı denetim): hoş geldin kuponları indirimli ürünlerde de
        # geçsin — tek seferlik, işaretli migrasyon (bkz. coupons.migrate_welcome_coupon_sale_policy).
        _asyncio.create_task(migrate_welcome_coupon_sale_policy())
        # Kupon birleşme varsayılanı: hepsiyle birleşir, engellenenler kuponun içinden seçilir (tek seferlik).
        _asyncio.create_task(migrate_coupon_stacking_default())
        _asyncio.create_task(refit_installment_returns_once())
        _asyncio.create_task(audit_unpaid_confirmed_card_orders_once())
        _asyncio.create_task(audit_member_group_discount_once())
        _asyncio.create_task(audit_cancel_requested_visibility_once())
        _asyncio.create_task(audit_3ds_dropoff_once())
        _asyncio.create_task(audit_subset_return_overrefund_once())
        _asyncio.create_task(audit_subset_return_money_v2_once())
        _asyncio.create_task(fix_otp_email_template_once())
    except Exception as e:
        logger.warning(f"Coupon exception seed start warning: {e}")

    # Tek seferlik migrasyon: kapida odemeyi varsayilan olarak KAPAT.
    # Admin panelinden (Ayarlar > Odeme Yontemleri) tekrar acilabilir; bu blok
    # _cod_default_off_v1 isaretiyle korundugu icin SADECE BIR KEZ calisir ve
        # Eski ek katalog alanı anahtarı → catalog_fields (tek seferlik, bayraklı, veri silmez)
        from legacy_migrations import migrate_catalog_fields_once as _mig_cf
        _asyncio.create_task(_mig_cf(db))
    # admin sonradan tekrar acarsa bir daha kapatmaz.
    try:
        _cfg = await db.settings.find_one({"id": "main"}, {"_id": 0}) or {}
        if not _cfg.get("_cod_default_off_v1"):
            _pm = dict(_cfg.get("payment_methods") or {})
            _pm.setdefault("credit_card", True)
            _pm.setdefault("bank_transfer", True)
            _pm["cash_on_delivery"] = False
            await db.settings.update_one(
                {"id": "main"},
                {"$set": {"payment_methods": _pm, "_cod_default_off_v1": True},
                 "$setOnInsert": {"id": "main"}},
                upsert=True,
            )
            logger.info("[migrate] cash_on_delivery varsayilan KAPALI uygulandi (_cod_default_off_v1)")
    except Exception as e:
        logger.warning(f"[migrate] cod_default_off atlandi: {e}")

    # Tek seferlik: "Google Merchant" XML feed kaydini olustur (XML Feed'ler sayfasinda gorunur).
    # Cikti /api/products/feed/google-merchant.xml — google-merchant-feed.xml ile birebir ayni format.
    try:
        _cfgf = await db.settings.find_one({"id": "main"}, {"_id": 0, "_google_feed_seeded_v1": 1}) or {}
        if not _cfgf.get("_google_feed_seeded_v1"):
            from routes.deps import generate_id as _gid
            from datetime import datetime as _dt, timezone as _tz
            if not await db.xml_feeds.find_one({"slug": "google-merchant"}):
                await db.xml_feeds.insert_one({
                    "id": _gid(), "name": "Google Merchant", "slug": "google-merchant",
                    "target": "google", "enabled": True, "in_stock_only": False,
                    "created_at": _dt.now(_tz.utc).isoformat(),
                })
                logger.info("[migrate] Google Merchant XML feed seed edildi (/feed/google-merchant.xml)")
            await db.settings.update_one(
                {"id": "main"},
                {"$set": {"_google_feed_seeded_v1": True}, "$setOnInsert": {"id": "main"}},
                upsert=True)
    except Exception as e:
        logger.warning(f"[migrate] google feed seed atlandi: {e}")

    # Tek seferlik: LEGACY iade siparisi temizligi.
    #   (A) Import-gunu (2026-06-11) telefonsuz MUKERRER kopyalari sil — yalnizca ayni
    #       siparis numarasindan gercek ikizi (telefonlu/gercek tarihli) olanlari.
    #   (B) id'siz kalan tum siparislere id ata — satir bazli durum degistirme
    #       (/api/orders/{id}/status id alanina gore eslesir) bu kayitlarda calissin.
    # Guard: _orders_iade_cleanup_v1 → sadece BIR KEZ calisir.
    try:
        _omf = await db.settings.find_one({"id": "main"}, {"_id": 0, "_orders_iade_cleanup_v1": 1}) or {}
        if not _omf.get("_orders_iade_cleanup_v1"):
            from routes.deps import generate_id as _gidc
            removed = 0
            async for _d in db.orders.find(
                {"created_at": {"$regex": "^2026-06-11"}},
                {"_id": 1, "order_number": 1, "phone": 1, "shipping_address": 1},
            ):
                _ph = ((_d.get("shipping_address") or {}).get("phone") or _d.get("phone") or "").strip()
                if _ph:
                    continue  # telefonu olan kopyayi ASLA silme
                _onum = _d.get("order_number")
                if not _onum:
                    continue
                _twin = await db.orders.find_one(
                    {"order_number": _onum, "_id": {"$ne": _d["_id"]}}, {"_id": 1})
                if _twin:  # gercek ikizi var → bu import-gunu kopyayi sil
                    await db.orders.delete_one({"_id": _d["_id"]})
                    removed += 1
            fixed = 0
            async for _d in db.orders.find(
                {"$or": [{"id": {"$exists": False}}, {"id": None}, {"id": ""}]}, {"_id": 1}):
                await db.orders.update_one({"_id": _d["_id"]}, {"$set": {"id": _gidc()}})
                fixed += 1
            await db.settings.update_one(
                {"id": "main"},
                {"$set": {"_orders_iade_cleanup_v1": True}, "$setOnInsert": {"id": "main"}},
                upsert=True)
            logger.info(f"[migrate] iade cleanup: {removed} mukerrer silindi, {fixed} id atandi (_orders_iade_cleanup_v1)")
    except Exception as e:
        logger.warning(f"[migrate] iade cleanup atlandi: {e}")

    # Tek seferlik: iade-akisi durumlarinda SMS+mail bildirimini AC (refund-pay dahil).
    # Canli notify config'inde 'refunded' vb. kapali oldugu icin "Iade Bedeli Odendi"de
    # bildirim gitmiyordu. Guard: _return_notify_all_v1 → bir kez acar, sonra admin degistirebilir.
    try:
        _osc = await db.settings.find_one(
            {"id": "order_status_config"}, {"_id": 0, "_return_notify_all_v1": 1}) or {}
        if not _osc.get("_return_notify_all_v1"):
            _ret_keys = ["return_requested", "return_approved", "return_rejected",
                         "return_in_transit", "returned", "partial_refunded", "refunded"]
            _setn = {f"notify.{k}": {"sms": True, "email": True} for k in _ret_keys}
            _setn["_return_notify_all_v1"] = True
            await db.settings.update_one(
                {"id": "order_status_config"},
                {"$set": _setn, "$setOnInsert": {"id": "order_status_config"}},
                upsert=True)
            logger.info("[migrate] iade durumlari SMS+mail acildi (_return_notify_all_v1)")
    except Exception as e:
        logger.warning(f"[migrate] return notify enable atlandi: {e}")

    yield
    
    # Shutdown
    logger.info("Shutting down...")
    try:
        from scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    client.close()

# Create FastAPI app
# GÜVENLİK: prod'da interaktif API dokümanı (/docs, /redoc, OpenAPI şeması) kapalı —
# saldırı yüzeyini/uç envanteri ifşasını azaltır. DEV'de açmak için ENABLE_API_DOCS=1.
_docs_enabled = os.environ.get("ENABLE_API_DOCS", "").strip() == "1" or \
    os.environ.get("ENVIRONMENT", "production").strip().lower() in ("dev", "development", "local")
app = FastAPI(
    title="E-Commerce API",
    version="3.0",
    description="Modular E-Commerce API with Iyzico, MNG/Aras/PTT Kargo and e-invoice integrations",
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

# CORS — strict whitelist (no wildcard in production). Configure via CORS_ORIGINS env.
cors_origins = os.environ.get("CORS_ORIGINS", "")
_origins_list = [o.strip() for o in cors_origins.split(",") if o.strip()] if cors_origins and cors_origins != "*" else (["*"] if cors_origins == "*" else [])
if not _origins_list:
    logger.warning("CORS_ORIGINS env is missing/empty — defaulting to localhost only. "
                   "Set explicit whitelist in /app/backend/.env for production.")
    _origins_list = ["http://localhost:3000"]
# Güvenlik: wildcard origin ("*") ile allow_credentials=True BİRLİKTE kullanılamaz — Starlette
# çağıranın Origin'ini yansıtıp kimlik-bilgili (cookie/Authorization) çapraz-origin isteğe izin
# verirdi. Wildcard varsa credentials KAPATILIR (spec gereği zaten geçersiz bir eşleşme).
_allow_credentials = _origins_list != ["*"]
if not _allow_credentials:
    logger.warning("CORS_ORIGINS=* ile credentials devre dışı bırakıldı. Üretimde açık bir "
                   "origin whitelist'i tanımlayın.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins_list,
    allow_credentials=_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
    expose_headers=["Content-Disposition"],
    max_age=600,
)

# ---------------------------------------------------------------------------
# RATE LIMITING (slowapi) — protects /api/auth/* against brute force
# ---------------------------------------------------------------------------
try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from routes.deps import limiter as _limiter

    if _limiter is not None:
        app.state.limiter = _limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)
except Exception as _e:
    logger.warning(f"slowapi rate limiter not enabled: {_e}")

# ---------------------------------------------------------------------------
# SECURITY HEADERS MIDDLEWARE (CSP, HSTS, XFO, XCTO, Referrer-Policy, etc.)
# ---------------------------------------------------------------------------
from starlette.middleware.base import BaseHTTPMiddleware as _BHM


class SecurityHeadersMiddleware(_BHM):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        # Skip for static asset routes if any
        path = request.url.path
        # Frontend may inject 3rd-party pixels (GA4, Meta, TikTok). Allow https:
        # script sources broadly but block 'unsafe-eval'. 'unsafe-inline' is
        # tolerated for inline tag-manager bootstraps.
        csp = (
            "default-src 'self' https: data: blob:; "
            "script-src 'self' 'unsafe-inline' https: blob:; "
            "style-src 'self' 'unsafe-inline' https: data:; "
            "img-src 'self' data: blob: https:; "
            "font-src 'self' data: https:; "
            "connect-src 'self' https: wss:; "
            "frame-src 'self' https:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self' https:; "
            "frame-ancestors 'none'"
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(self), usb=(), interest-cohort=()",
        )
        # HSTS — only meaningful over HTTPS but harmless on HTTP previews
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        # Disable cross-origin Spectre-class leaks for API responses
        if path.startswith("/api/"):
            response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
            response.headers.setdefault("X-Robots-Tag", "noindex, nofollow")
        # DENETİM (auth-redteam #6): kimlik/PII yanıtlarına no-store — ara katman/tarayıcı
        # önbelleğe almasın (token/PII sızıntısı). Public katalog uçları hariç.
        _SENSITIVE = ("/api/auth", "/api/users", "/api/admin", "/api/my-orders",
                      "/api/orders", "/api/customer", "/api/members", "/api/iys",
                      "/api/settings", "/api/referrals", "/api/loyalty", "/api/gift")
        if any(path.startswith(p) for p in _SENSITIVE):
            response.headers.setdefault("Cache-Control", "no-store, private")
        return response


app.add_middleware(SecurityHeadersMiddleware)


class BodySizeLimitMiddleware(_BHM):
    """DoS koruması: Content-Length çok büyük olan istekleri body okunmadan 413 ile
    reddeder (devasa gövde → bellek tükenmesi). Cap 120MB — video yükleme sınırının
    (100MB) üstünde olduğu için meşru hiçbir isteği engellemez."""
    MAX_BYTES = 120 * 1024 * 1024

    async def dispatch(self, request, call_next):
        cl = request.headers.get("content-length")
        if cl:
            try:
                if int(cl) > self.MAX_BYTES:
                    from starlette.responses import JSONResponse as _JR
                    return _JR(status_code=413, content={"detail": "İstek gövdesi çok büyük"})
            except (ValueError, TypeError):
                pass
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)

# ---------------------------------------------------------------------------
# ERROR TRACKING & ALERTING — captures 5xx, slow responses, exceptions
# ---------------------------------------------------------------------------
from security.monitoring import ErrorTrackingMiddleware
app.add_middleware(ErrorTrackingMiddleware)

# Main API Router
api_router = APIRouter(prefix="/api")

from routes.admin_activity import router as admin_activity_router
api_router.include_router(admin_activity_router)

# Documentation download (public — markdown indir)
from routes.docs import router as docs_router
api_router.include_router(docs_router)

# İstemci yüklenme/hata telemetrisi (site açılmıyor teşhisi — cihaz/IP/hata)
from routes.client_log import router as client_log_router
api_router.include_router(client_log_router)

from routes.stock_notify import router as stock_notify_router
api_router.include_router(stock_notify_router)

from routes.payment import router as payment_router
api_router.include_router(payment_router)

# Çoklu kargo firması (MNG/DHL + Aras Kargo + PTT Kargo) — cargo_carriers/
from routes.cargo_carriers import router as cargo_carriers_router
api_router.include_router(cargo_carriers_router)

# Include all route modules
api_router.include_router(auth_router)
api_router.include_router(products_router)
api_router.include_router(orders_router)
api_router.include_router(categories_router)
api_router.include_router(banners_router)
api_router.include_router(cms_router)
api_router.include_router(pages_router)
# Iyzico endpoint'leri — integrations_router'ın catch-all /{provider} rotasından ÖNCE include edilmeli
from routes.integrations_iyzico import router as iyzico_router
api_router.include_router(iyzico_router, prefix="/integrations")
# BirFatura e-Fatura/e-Arşiv: BirFatura'nın çağırdığı token'lı uçlar (/api/birfatura/api/...)
# + panel ayarları (/api/integrations/birfatura/...) — catch-all /{provider}'dan ÖNCE.
from routes.integrations_birfatura import public_router as birfatura_public_router, admin_router as birfatura_admin_router
api_router.include_router(birfatura_public_router)
api_router.include_router(birfatura_admin_router)
api_router.include_router(integrations_router, prefix="/integrations")
api_router.include_router(capi_router)
api_router.include_router(admin_router)
api_router.include_router(customer_router)
# ALIAS — Checkout.jsx, üye adreslerini /api/customer/... yolundan çağırıyor; router
# ön eksiz mount edildiği için bu yol 404 dönüyordu (üye checkout'ta kayıtlı adreslerini
# göremiyor, modaldan adres kaydedemiyordu). Aynı router'ı /customer önekiyle de mount
# ederek her iki yolu da çalışır kılıyoruz (Account.jsx ön eksiz yolu kullanmaya devam eder).
api_router.include_router(customer_router, prefix="/customer")
api_router.include_router(variants_router)
api_router.include_router(webhooks_router)
api_router.include_router(attributes_router)
api_router.include_router(upload_router)
from routes.demo_content import router as demo_content_router  # demo içerik yükle/kaldır (süper yönetici)
api_router.include_router(demo_content_router)
from routes.product_sets import router as product_sets_router  # Ürün Setleri + kapıda ödeme vitrin uçları
api_router.include_router(product_sets_router)
from routes.site_menus import router as site_menus_router  # vitrin menü grupları (Menü Yönetimi)
api_router.include_router(site_menus_router)
api_router.include_router(upload_files_router)
api_router.include_router(settings_router)
api_router.include_router(vendors_router, prefix="/vendors")
api_router.include_router(admin_rbac_router)
api_router.include_router(locations_router)
api_router.include_router(attribution_router)

from routes.consent import router as consent_router  # KVKK çerez onayı kaydı
api_router.include_router(consent_router)
api_router.include_router(members_router)
api_router.include_router(consents_router)
api_router.include_router(coupons_admin_router)
api_router.include_router(coupons_public_router)
api_router.include_router(campaigns_router)
from routes.sale_menu import public_router as sale_menu_public_router, admin_router as sale_menu_admin_router
api_router.include_router(sale_menu_public_router)
api_router.include_router(sale_menu_admin_router)
api_router.include_router(reports_router)
api_router.include_router(report_assistant_router)   # Raporlar "Bana Sor" asistanı
api_router.include_router(cart_router)
api_router.include_router(admin_cart_router)
api_router.include_router(reviews_public_router)
api_router.include_router(reviews_admin_router)
api_router.include_router(seo_public_router)
api_router.include_router(seo_admin_router)
# eski altyapı P1 — catalog extras, ops, reports, communications
for _r in (
    brands_router, tags_router, member_groups_router, announcements_router, popups_router,
    storefront_extras_router,
    alerts_public_router, alerts_admin_router,
    havale_public_router, havale_admin_router,
    admin_orders_router,
    rules_router,
    extra_reports_router,
    tickets_public_router, tickets_admin_router,
    email_admin_router,
    currency_router,
):
    api_router.include_router(_r)
api_router.include_router(business_rules_admin_router)
api_router.include_router(business_rules_public_router)
api_router.include_router(help_center_admin_router)
api_router.include_router(help_center_public_router)
api_router.include_router(referrals_public_router)
api_router.include_router(referrals_admin_router)
api_router.include_router(shared_carts_router)
api_router.include_router(gift_cards_router)
api_router.include_router(gift_cards_admin_router)
api_router.include_router(loyalty_router)
# Barcode cards (products & variants) — tek tek veya toplu yazdırılabilir HTML
# kartlar. Products.jsx'deki "Barkod Yazdır" akışları buraya bağlıdır.
api_router.include_router(barcode_cards_router)
# E-Fatura ve Kargo entegratör ayarları (provider seçimi + credential formu).
# Frontend: EInvoiceSettings.jsx + CargoSettings.jsx bu endpoint'leri kullanır.
api_router.include_router(provider_settings_router)
# İYS (ticari ileti izni) + OTP doğrulama — ödeme adımında kampanya izni ve dijital İYS bildirimi.
api_router.include_router(iys_consent_router)
# Otomasyon durumu — admin için cron + log özet
api_router.include_router(automation_status_router)
# Footer şablonu (public + admin)
api_router.include_router(footer_public_router)
api_router.include_router(footer_admin_router)
api_router.include_router(newsletter_public_router)
api_router.include_router(newsletter_admin_router)
from routes.email_marketing import admin_router as email_mkt_admin_router, public_router as email_mkt_public_router
api_router.include_router(email_mkt_admin_router)
api_router.include_router(email_mkt_public_router)
api_router.include_router(rooftr_returns_router)
# Site iadeleri — toplu gider pusulası (eski /integrations/harici kanal/claims/gp-bulk-range yerine)
from routes.returns import router as returns_router
api_router.include_router(returns_router)
# Toplu fiyat/stok Excel ops + stok uyarı + yeniden sipariş önerisi
api_router.include_router(bulk_ops_router)
# RFM müşteri segmentasyonu + Google Merchant feed
api_router.include_router(analytics_extra_router)
api_router.include_router(notifications_router)
api_router.include_router(customer_risk_router)
api_router.include_router(marketing_pixels_router)
api_router.include_router(social_auth_router)
# Security dashboard — auth_audit_logs üzerinde admin görünürlüğü
api_router.include_router(security_dashboard_router)
# Secrets Vault (encrypted credentials store) + System Health monitoring
api_router.include_router(secrets_vault_router)
api_router.include_router(system_health_router)
api_router.include_router(mail_admin_router)
# Iteration 42 — Yeni rapor seti (stok değer, hızlı/yavaş satan, iade oranı, kanal kâr)
api_router.include_router(reports_v2_router)
api_router.include_router(product_costs_router)
# IYS
api_router.include_router(iys_router)

# TOTP MFA (çok faktörlü doğrulama)
from routes.mfa import router as mfa_router
api_router.include_router(mfa_router)
# Cloudflare Email Routing — gelen mail webhook'u
from routes.inbound_mail import router as inbound_mail_router
api_router.include_router(inbound_mail_router)

# Root endpoint
@api_router.get("/")
async def root():
    return {
        "message": "E-Commerce API",
        "version": "3.0",
        "status": "running"
    }

# Health check


async def refit_installment_returns_once() -> None:
    """TEK SEFERLİK: taksitli siparişlerin ONAYLI ama HENÜZ ÖDENMEMİŞ kısmi iadelerini yeni vade farkı
    dağıtımına (kargo dahil orantılı, iyzico ile birebir) göre yeniden hesaplar. Elle düzeltilmiş
    tutarlara (refund_amount ≠ otomatik hesap) DOKUNMAZ. Ödenmiş/reddedilmiş iadeler kapsam dışı.
    Sonuç settings.migrations.vade_refit_v1 → /health.vade_refit."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz
    flag_id = "migrations.vade_refit_v1"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        from routes.orders import _compute_refund_breakdown, _order_vade_farki, _round2, site_return_gider_pusulasi
        changed, skipped_manual, gp_regen, examined = [], 0, 0, 0
        cur = _db.customer_returns.find({"status": "approved", "refund_breakdown.is_partial": True,
                                         "refund_breakdown.vade_farki": {"$gt": 0.005}}, {"_id": 0})
        async for rec in cur:
            examined += 1
            order = await _db.orders.find_one({"id": rec.get("order_id")}, {"_id": 0}) or {}
            vf, _c, inst = _order_vade_farki(order)
            if vf <= 0.005 or inst <= 1:
                continue
            bd_old = rec.get("refund_breakdown") or {}
            old_amt = _round2(rec.get("refund_amount") or 0)
            if abs(old_amt - _round2(bd_old.get("auto_refund") or 0)) > 0.011:
                skipped_manual += 1      # operatör elle tutar girmiş → dokunma
                continue
            fault = rec.get("fault") or bd_old.get("fault") or "store"
            ret_net = bd_old.get("returned_products_net")
            if ret_net in (None, ""):
                continue
            cargo_ovr = bd_old.get("return_cargo_fee") if fault == "customer" else None
            bd_new = await _compute_refund_breakdown(rec, order, fault, return_cargo_fee_override=cargo_ovr,
                                                     returned_net_override=ret_net)
            if bd_old.get("cargo"):
                bd_new["cargo"] = bd_old.get("cargo")
            new_amt = _round2(bd_new.get("auto_refund") or 0)
            if abs(new_amt - old_amt) < 0.005:
                continue
            now = _dt.now(_tz.utc).isoformat()
            await _db.customer_returns.update_one({"id": rec["id"]}, {"$set": {
                "refund_breakdown": bd_new, "refund_amount": new_amt, "updated_at": now,
                "vade_refit": {"at": now, "old_amount": old_amt, "new_amount": new_amt,
                               "reason": "vade farkı kargo dahil orantılı (iyzico ile birebir)"}}})
            changed.append({"order": rec.get("order_number"), "old": old_amt, "new": new_amt})
            if await _db.gider_pusulasi.find_one({"return_id": rec["id"]}, {"_id": 0, "display_number": 1}):
                try:
                    _gp = await _db.gider_pusulasi.find_one({"return_id": rec["id"]}, {"_id": 0, "display_number": 1})
                    await site_return_gider_pusulasi(rec["id"], payload={
                        "include_cargo": fault == "customer", "tracking_no": _gp.get("display_number") or "",
                        "refund_amount": new_amt}, preview=False, current_user={"email": "sistem@vade-refit", "id": "system"})
                    gp_regen += 1
                except Exception as _ge:
                    logger.warning(f"[vade-refit] GP yenileme hatası {rec.get('order_number')}: {_ge}")
        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(), "examined": examined,
            "changed": changed[:100], "changed_count": len(changed), "skipped_manual": skipped_manual,
            "gp_regenerated": gp_regen}}, upsert=True)
        logger.warning(f"[vade-refit] incelenen={examined} değişen={len(changed)} elle={skipped_manual} gp={gp_regen}")
    except Exception as e:
        logger.error(f"[vade-refit] hata: {e}")


async def fix_otp_email_template_once() -> None:
    """TEK SEFERLİK: 'Şifre Sıfırlama Kodu' E-POSTA şablonu jenerik üretilmişti ve içinde
    {otp_code} YOKTU → mail gidiyor ama KOD görünmüyordu (17.09). Markalı, kodu büyük gösteren
    şablonla değiştirilir. Elle düzenlenmiş şablona DOKUNULMAZ."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz
    flag_id = "migrations.otp_email_tpl_v2"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        from routes.notifications import _EMAIL_HTML_TEMPLATES, _DEFAULT_TEMPLATES
        now = _dt.now(_tz.utc).isoformat()
        yazilan = []
        # Hem şifre sıfırlama hem GİRİŞ doğrulama şablonları (e-posta + SMS) kurulur.
        for ev in ("password_reset_otp", "login_verification_code"):
            rich = _EMAIL_HTML_TEMPLATES.get(ev)
            if rich:
                cur = await _db.notification_templates.find_one(
                    {"event": ev, "channel": "email"}, {"_id": 0}) or {}
                if not (cur.get("manually_edited") and "{otp_code}" in str(cur.get("body") or "")):
                    await _db.notification_templates.update_one(
                        {"event": ev, "channel": "email"},
                        {"$set": {"event": ev, "channel": "email", "subject": rich["subject"],
                                  "body": rich["body"], "enabled": True, "updated_at": now}}, upsert=True)
                    yazilan.append(f"{ev}/email")
            _sms = _DEFAULT_TEMPLATES.get((ev, "sms"))
            if _sms:
                cur2 = await _db.notification_templates.find_one(
                    {"event": ev, "channel": "sms"}, {"_id": 0}) or {}
                if not cur2.get("body"):
                    await _db.notification_templates.update_one(
                        {"event": ev, "channel": "sms"},
                        {"$set": {"event": ev, "channel": "sms", "body": _sms,
                                  "enabled": True, "updated_at": now}}, upsert=True)
                    yazilan.append(f"{ev}/sms")
        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": now, "yazilan": yazilan}}, upsert=True)
        logger.warning(f"[otp-mail] doğrulama şablonları kuruldu: {yazilan}")
    except Exception as e:
        logger.error(f"[otp-mail] hata: {e}")


async def audit_unpaid_confirmed_card_orders_once() -> None:
    """TEK SEFERLİK denetim: ödemesi ALINMAMIŞ olduğu hâlde 'onaylı/ilerlemiş' duruma çekilmiş
    KART siparişleri (ödeme alınmadan onaylanma kusuru). Yalnız RAPORLAR — hiçbir siparişi değiştirmez.
    Sonuç settings.migrations.audit_unpaid_card_v1 → /health.unpaid_card_audit."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz
    flag_id = "migrations.audit_unpaid_card_v2"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        _card = ["credit_card", "card", "kredi_karti", "kart", "iyzico", "creditcard"]
        _settled = ["paid", "completed", "success", "succeeded", "captured"]
        _live = ["confirmed", "processing", "preparing", "shipped", "delivered", "undelivered"]
        rows, imported = [], 0
        async for o in _db.orders.find(
                {"status": {"$in": _live}, "payment_method": {"$in": _card},
                 "payment_status": {"$nin": _settled},
                 "paid_with_gift_card_only": {"$ne": True}},
                {"_id": 0, "order_number": 1, "status": 1, "payment_status": 1, "total": 1,
                 "created_at": 1, "iyzico_payment_id": 1, "needs_reconciliation": 1,
                 "imported_from": 1, "platform": 1}).limit(2000):
            # AKTARILMIŞ GEÇMİŞ (eski altyapı/pazaryeri) siparişleri kusur DEĞİL: bu sistemde hiç
            # ödeme akışından geçmediler, payment_status aktarımda hiç 'paid' yazılmadı.
            if o.get("imported_from") or (o.get("platform") and o.get("platform") != "site"):
                imported += 1
                continue
            rows.append({"no": o.get("order_number"), "durum": o.get("status"),
                         "odeme": o.get("payment_status"), "tutar": o.get("total"),
                         "tarih": str(o.get("created_at") or "")[:16],
                         "iyzico_var": bool(o.get("iyzico_payment_id")),
                         "mutabakat_bekliyor": bool(o.get("needs_reconciliation"))})
        rows.sort(key=lambda r: r.get("tarih") or "", reverse=True)
        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(),
            "count": len(rows), "imported_skipped": imported, "rows": rows[:60],
            "note": "Sadece rapor — hiçbir sipariş değiştirilmedi. Aktarılmış geçmiş siparişler hariç."}},
            upsert=True)
        logger.warning(f"[denetim] ödemesi alınmamış ama onaylı KENDİ kart siparişimiz: {len(rows)} "
                       f"(aktarılmış/pazaryeri hariç: {imported})")
    except Exception as e:
        logger.error(f"[denetim] unpaid-card hata: {e}")


# Ödeme denetimi çıktısı KİŞİSEL/TİCARİ veri taşıdığından /health üzerinde yalnız bu
# anahtarla açılır (sağlık ucu herkese açıktır; sayılar herkese, detay anahtarla).
# Destek teşhis anahtarı (/api/health?diag=1&audit_key=...). YALNIZ env SUPPORT_AUDIT_KEY'den;
# boşsa ?diag=1 destek teşhisleri tamamen KAPALIDIR. Karşılaştırma sabit-zamanlı (hmac.compare_digest).
SUPPORT_AUDIT_KEY = (os.environ.get("SUPPORT_AUDIT_KEY") or "").strip()


def _audit_key_ok(audit_key: str) -> bool:
    import hmac as _hmac
    if not SUPPORT_AUDIT_KEY:
        return False
    return _hmac.compare_digest(str(audit_key or "").encode(), SUPPORT_AUDIT_KEY.encode())


async def audit_cancel_requested_visibility_once() -> None:
    """TEK SEFERLİK TEŞHİS: 'İptal Talebi Alındı' (cancel_requested) siparişler ana listede
    MOR satır olarak görünmeli. Kullanıcı: isimle arayınca görünüyor, platform=Web Sitesi
    süzgeciyle görünmüyor. Hangi alanın/süzgecin gizlediğini veriyle saptar. SALT OKUNUR."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz, timedelta as _tdl
    from collections import Counter
    flag_id = "migrations.audit_cancelreq_vis_v1"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        cutoff = (_dt.now(_tz.utc) - _tdl(days=365)).isoformat()
        rows = await _db.orders.find(
            {"status": "cancel_requested", "created_at": {"$gt": cutoff}},
            {"_id": 0, "order_number": 1, "platform": 1, "marketplace": 1, "payment_status": 1,
             "payment_method": 1, "created_at": 1, "refund_pending": 1, "total": 1}
        ).sort("created_at", -1).to_list(300)
        _settled = {"paid", "completed", "success", "succeeded", "captured"}
        _offline = {"bank_transfer", "havale", "eft", "havale_eft", "banka_havale", "transfer",
                    "cash_on_delivery", "kapida", "kapida_odeme", "cod"}
        _fulfilled = {"confirmed", "processing", "preparing", "shipped", "delivered",
                      "completed", "undelivered", "cancelled"}
        det, plat_c, gizli = [], Counter(), 0
        for r in rows:
            pf = r.get("platform")
            plat_c[str(pf)] += 1
            web = pf in ("web", None, "")
            junk = (web and str(r.get("payment_status") or "").lower() not in _settled
                    and str(r.get("payment_method") or "").lower() not in _offline
                    and "cancel_requested" not in _fulfilled)
            if junk:
                gizli += 1
            det.append({"siparis": r.get("order_number"), "tarih": str(r.get("created_at"))[:19],
                        "platform": pf, "odeme": r.get("payment_status"),
                        "yontem": r.get("payment_method"), "tutar": r.get("total"),
                        "web_suzgecinde_gorunur": pf == "web",
                        "junk_suzgeci_gizler": junk})
        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(),
            "adet": len(rows), "platform_dagilimi": dict(plat_c),
            "junk_suzgeci_gizleyen": gizli,
            "web_suzgecinde_gorunmeyen": sum(1 for d in det if not d["web_suzgecinde_gorunur"]),
            "ornekler": det[:40], "note": "Sadece rapor."}}, upsert=True)
        logger.warning(f"[teshis] cancel_requested={len(rows)} platform={dict(plat_c)} "
                       f"junk_gizler={gizli}")
    except Exception as e:
        logger.error(f"[teshis] cancel_requested gorunurluk hatasi: {e}")


async def audit_3ds_dropoff_once() -> None:
    """TEK SEFERLİK ÖLÇÜM (müşteri şikâyeti): banka 3DS onayından sonra tarayıcı dönüşü
    kırılan siparişler ("Safari: adres geçersiz"). Son 21 günde kaç kart siparişi 3DS
    başlattı, kaçı tamamlandı, tamamlanmayanların parası GERÇEKTEN çekilmiş mi?
    SALT OKUNUR. Sonuç /health (audit_key ile) → threeds_audit."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz, timedelta as _tdl
    import asyncio as _aio
    flag_id = "migrations.audit_3ds_dropoff_v1"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        cutoff = (_dt.now(_tz.utc) - _tdl(days=21)).isoformat()
        _card = ["credit_card", "card", "kredi_karti", "kart", "iyzico", "creditcard"]
        _proj = {"_id": 0, "id": 1, "order_number": 1, "created_at": 1, "total": 1,
                 "status": 1, "payment_status": 1, "payment_flow": 1,
                 "iyzico_conversation_id": 1, "iyzico_payment_id": 1, "payment_id": 1,
                 "reconcile_payment_id": 1}
        toplam = basladi = odendi = 0
        yarim = []
        async for o in _db.orders.find(
                {"created_at": {"$gt": cutoff}, "payment_method": {"$in": _card},
                 "order_number": {"$regex": "^W"}}, _proj):
            toplam += 1
            _3ds = bool(o.get("payment_flow") == "3ds" or o.get("iyzico_conversation_id"))
            if not _3ds:
                continue
            basladi += 1
            if str(o.get("payment_status") or "").lower() == "paid":
                odendi += 1
            else:
                yarim.append(o)
        yarim.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)

        # Tamamlanmayanların parası çekilmiş mi? (iyzico'ya canlı sor — en fazla 40 tanesi)
        cekilmis, sorgulanan, ornekler = [], 0, []
        try:
            import json as _json, httpx as _httpx
            from routes.payment import (_get_iyzico_settings as _gs, _v2_headers as _vh,
                                        PAYMENT_DETAIL_PATH as _pd)
            st = await _gs()
            async with _httpx.AsyncClient(timeout=25) as c:
                for o in yarim[:40]:
                    pid = str(o.get("iyzico_payment_id") or o.get("payment_id")
                              or o.get("reconcile_payment_id") or "").strip()
                    kayit = {"siparis": o.get("order_number"),
                             "tarih": str(o.get("created_at") or "")[:19],
                             "tutar": o.get("total"), "durum": o.get("status"),
                             "odeme": o.get("payment_status"),
                             "paymentId": pid or None, "iyzico": None}
                    if pid:
                        sorgulanan += 1
                        try:
                            body = {"locale": "tr", "conversationId": str(o.get("id")), "paymentId": pid}
                            bs = _json.dumps(body, separators=(",", ":"), ensure_ascii=False)
                            r = await c.post(f"{st['base_url']}{_pd}", content=bs.encode("utf-8"),
                                             headers=_vh(st["api_key"], st["api_secret"], _pd, bs))
                            d = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
                            kayit["iyzico"] = str(d.get("paymentStatus") or d.get("status") or "?")
                            if str(d.get("paymentStatus") or "").upper() == "SUCCESS":
                                cekilmis.append(kayit)
                        except Exception as _pe:
                            kayit["iyzico"] = f"hata: {str(_pe)[:60]}"
                        await _aio.sleep(0.25)
                    ornekler.append(kayit)
        except Exception as _ie:
            ornekler.append({"hata": str(_ie)[:120]})

        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(),
            "gun": 21, "kart_siparisi": toplam, "3ds_baslatan": basladi,
            "3ds_tamamlanan": odendi, "yarim_kalan": len(yarim),
            "tamamlanma_orani": (round(odendi / basladi * 100, 1) if basladi else None),
            "paymentId_ile_sorgulanan": sorgulanan,
            "PARASI_CEKILMIS_AMA_KAYITSIZ": len(cekilmis),
            "cekilmis_liste": cekilmis[:10], "son_yarim_kalanlar": ornekler[:15],
            "note": "Salt okunur. 'Parası çekilmiş ama kayıtsız' > 0 ise elle finalize gerekir."}},
            upsert=True)
        logger.warning(f"[denetim] 3DS: baslatan={basladi} tamamlanan={odendi} "
                       f"yarim={len(yarim)} cekilmis-kayitsiz={len(cekilmis)}")
    except Exception as e:
        logger.error(f"[denetim] 3ds dropoff hata: {e}")


async def audit_member_group_discount_once() -> None:
    """TEK SEFERLİK denetim: üye-grubu indirimi (users.group_id → member_groups.discount_percent)
    kasada GÖSTERİLİYOR ama sipariş kaydında HESAPLANMIYORDU. Onay-tutarı denetimi devrede
    olduğu için indirimli gruptaki üye sipariş veremiyor, 409 "Sepet tutarı güncellendi"
    hatası alıyordu. İndirim artık kampanya motorunun içinde (önizleme = sipariş).

    Bu görev yalnız RAPORLAR + düzeltmeyi doğrular: kaç grubun indirimi var, kaç üye etkileniyor
    ve örnek bir üye için motor gerçekten indirimi üretiyor mu. Hiçbir kayıt değiştirilmez.
    Sonuç settings.migrations.audit_member_discount_v1 → /health.member_discount_audit."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz
    flag_id = "migrations.audit_member_discount_v1"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        groups = await _db.member_groups.find(
            {}, {"_id": 0, "id": 1, "name": 1, "discount_percent": 1}).to_list(200)
        rows, sample_uid, etkilenen = [], None, 0
        for g in groups:
            try:
                pct = float(g.get("discount_percent") or 0)
            except Exception:
                pct = 0.0
            if pct <= 0:
                continue
            n = await _db.users.count_documents({"group_id": g.get("id")})
            etkilenen += n
            rows.append({"grup": g.get("name") or "", "yuzde": pct, "uye": n})
            if n and not sample_uid:
                u = await _db.users.find_one({"group_id": g.get("id")}, {"_id": 0, "id": 1}) or {}
                sample_uid = u.get("id")
        # Doğrulama: örnek üye için motor 1000 TL'lik sepette indirimi üretiyor mu?
        dogrulama = None
        if sample_uid:
            try:
                from routes.coupons import evaluate_cart_promotions as _ev_fn
                _ev = await _ev_fn(cart_total=1000.0, items=[], user_id=sample_uid,
                                   email="", entered_code="", payment_method="")
                dogrulama = {"taban": 1000.0,
                             "uye_indirimi": _ev.get("member_discount"),
                             "yuzde": _ev.get("member_discount_pct"),
                             "toplam_indirim": _ev.get("total_discount")}
            except Exception as _ve:
                dogrulama = {"hata": str(_ve)[:200]}
        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(),
            "indirimli_grup": len(rows), "etkilenen_uye": etkilenen,
            "gruplar": rows, "dogrulama": dogrulama,
            "note": "Sadece rapor. Üye indirimi artık kampanya motorunda hesaplanıyor "
                    "(kasa önizlemesi = sipariş kaydı)."}},
            upsert=True)
        logger.warning(f"[denetim] uye-grubu indirimi: indirimli grup={len(rows)} "
                       f"etkilenen uye={etkilenen} dogrulama={dogrulama}")
    except Exception as e:
        logger.error(f"[denetim] uye-grubu indirimi denetimi hata: {e}")


async def audit_subset_return_overrefund_once() -> None:
    """DENETİM (SALT OKUNUR): geçmişte "alt küme iade talebi → TÜM SİPARİŞ iadesi" hatasından
    kaç siparişte FAZLA para iade edilmiş, toplamı ne kadar?

    Hata: müşteri çok kalemli siparişin BİR kalemi için iade talebi açtığında
    customer_returns.items siparişin alt kümesi oluyordu; onay akışı kısmiliği yalnız
    "seçim < KAYITTAKİ kalem" ile ölçtüğünden kısmi saymıyor, iade hesabı tam iade dalına
    düşüp order.total'ı iade ediyordu. Kod düzeltildi (_return_covers_whole_order);
    bu görev YALNIZ geçmiş hasarı raporlar, hiçbir kaydı değiştirmez.

    Sonuç settings.migrations.audit_subset_refund_v1 → /health?diag=1&audit_key=..."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz
    flag_id = "migrations.audit_subset_refund_v1"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return

        def _r2(v):
            try:
                return round(float(v or 0), 2)
            except Exception:
                return 0.0

        def _q(it):
            try:
                return max(1, int((it or {}).get("quantity", 1) or 1))
            except Exception:
                return 1

        supheli, toplam_fazla, taranan = [], 0.0, 0
        cur = _db.customer_returns.find(
            {"status": {"$in": ["approved", "refunded", "returned", "partial_refunded"]}},
            {"_id": 0, "id": 1, "order_id": 1, "order_number": 1, "items": 1,
             "refund_amount": 1, "status": 1, "created_at": 1, "approval": 1})
        async for rec in cur:
            taranan += 1
            _ri = rec.get("items") or []
            if not _ri:
                continue
            o = await _db.orders.find_one(
                {"id": rec.get("order_id")},
                {"_id": 0, "order_number": 1, "items": 1, "total": 1, "subtotal": 1}) or {}
            _oi = o.get("items") or []
            if not _oi:
                continue
            # Alt küme mi? (kalem sayısı VEYA toplam adet eksik)
            if len(_ri) >= len(_oi) and sum(_q(i) for i in _ri) >= sum(_q(i) for i in _oi):
                continue
            _ref = _r2(rec.get("refund_amount"))
            _tot = _r2(o.get("total"))
            if _ref <= 0.01 or _tot <= 0.01:
                continue
            # İade edilen kalemlerin brüt karşılığı (üst sınır) — bunun ÜSTÜ fazla ödemedir.
            _sel_gross = _r2(sum(_r2((i or {}).get("price")) * _q(i) for i in _ri))
            if _ref <= _sel_gross + 0.02:
                continue          # seçili kalemler kadar ya da altında → sorun yok
            _fazla = _r2(_ref - _sel_gross)
            toplam_fazla = _r2(toplam_fazla + _fazla)
            supheli.append({
                "iade_id": rec.get("id"), "siparis": o.get("order_number") or rec.get("order_number"),
                "durum": rec.get("status"), "tarih": str(rec.get("created_at") or "")[:19],
                "iade_edilen": _ref, "siparis_toplami": _tot,
                "iade_kalem": len(_ri), "siparis_kalem": len(_oi),
                "secili_brut": _sel_gross, "fazla": _fazla,
                "elle_mi": bool((rec.get("approval") or {}).get("manual_override")),
            })
        supheli.sort(key=lambda x: -x["fazla"])
        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(),
            "taranan_iade": taranan, "supheli_adet": len(supheli),
            "toplam_fazla_tl": toplam_fazla, "ornekler": supheli[:40],
            "note": "Salt okunur. 'fazla' = iade edilen tutar − iade talebindeki kalemlerin "
                    "brüt toplamı. Kök sebep kodda kapatıldı (_return_covers_whole_order); "
                    "elle_mi=True olanlarda tutarı personel bilerek girmiş olabilir."}},
            upsert=True)
        logger.warning(f"[denetim] alt-kume iade fazla odeme: supheli={len(supheli)} "
                       f"toplam_fazla={toplam_fazla} taranan={taranan}")
    except Exception as e:
        logger.error(f"[denetim] alt-kume iade denetimi hata: {e}")


class _NullCtx:
    """httpx yoksa denetimin çökmemesi için boş bağlam (iyzico sorgusu atlanır)."""
    async def __aenter__(self):
        return None
    async def __aexit__(self, *a):
        return False


async def audit_subset_return_money_v2_once() -> None:
    """DENETİM v2 (SALT OKUNUR): v1'in işaretlediği "fazla iade" vakalarında para GERÇEKTEN
    çıkmış mı? Sipariş üzerindeki iade kayıtları + iyzico ödeme detayı (itemTransactions
    içindeki iade satırları) okunur; kuruş hareket ettirilmez.

    Sonuç settings.migrations.audit_subset_refund_v2 → /health?diag=1&audit_key=..."""
    from routes.deps import db as _db
    from datetime import datetime as _dt, timezone as _tz
    import asyncio as _aio
    import json
    flag_id = "migrations.audit_subset_refund_v2"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        # v1 aynı açılışta paralel koşuyor olabilir — bitmesini bekle (bitmezse bu açılışta
        # HİÇ done yazma ki sonraki açılışta tekrar denensin).
        v1 = {}
        for _w in range(40):
            v1 = await _db.settings.find_one({"id": "migrations.audit_subset_refund_v1"}, {"_id": 0}) or {}
            if v1.get("done"):
                break
            await _aio.sleep(3)
        if not v1.get("done"):
            return
        vakalar = v1.get("ornekler") or []
        if not vakalar:
            await _db.settings.update_one({"id": flag_id}, {"$set": {
                "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(),
                "sonuc": "v1 şüpheli vaka bulmadı"}}, upsert=True)
            return
        try:
            from routes.payment import (_get_iyzico_settings as _gs, _v2_headers as _vh,
                                        PAYMENT_DETAIL_PATH as _pd)
            import httpx as _httpx
            st = await _gs()
        except Exception:
            st, _httpx = None, None
        rapor = []
        _cm = _httpx.AsyncClient(timeout=25) if _httpx else _NullCtx()
        async with _cm as c:
            for v in vakalar[:20]:
                o = await _db.orders.find_one({"order_number": v.get("siparis")}, {"_id": 0}) or {}
                pid = str(o.get("iyzico_payment_id") or o.get("payment_id") or "").strip()
                _iade_alanlari = {k: o.get(k) for k in o.keys()
                                  if any(x in k.lower() for x in ("refund", "iade")) }
                iyz = {"paymentId": pid or None}
                if st and pid:
                    try:
                        body = {"locale": "tr", "conversationId": str(o.get("id")), "paymentId": pid}
                        bs = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
                        resp = await c.post(f"{st['base_url']}{_pd}", content=bs.encode("utf-8"),
                                            headers=_vh(st["api_key"], st["api_secret"], _pd, bs))
                        d = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                        _its = d.get("itemTransactions") or []
                        _iade_toplam = 0.0
                        for _t in _its:
                            try:
                                _iade_toplam += float(_t.get("paidPrice") or 0) - float(
                                    _t.get("convertedPayout", {}).get("paidPrice") or _t.get("paidPrice") or 0)
                            except Exception:
                                pass
                        iyz.update({
                            "durum": str(d.get("paymentStatus") or ""),
                            "cekilen": d.get("paidPrice"),
                            "kalem_sayisi": len(_its),
                            "kalem_durumlari": [str(_t.get("transactionStatus")) for _t in _its][:10],
                            "iade_satirlari": [{"tutar": _t.get("paidPrice"),
                                                "durum": str(_t.get("transactionStatus"))}
                                               for _t in _its if str(_t.get("transactionStatus")) in ("3", "-1")][:10],
                        })
                    except Exception as _pe:
                        iyz["hata"] = str(_pe)[:120]
                    await _aio.sleep(0.2)
                rapor.append({
                    "siparis": v.get("siparis"), "iade_id": v.get("iade_id"),
                    "onaylanan_iade": v.get("iade_edilen"), "olmasi_gereken": v.get("secili_brut"),
                    "fazla": v.get("fazla"), "iade_durumu": v.get("durum"),
                    "siparis_durumu": o.get("status"), "odeme_durumu": o.get("payment_status"),
                    "siparis_iade_alanlari": {k: str(x)[:120] for k, x in _iade_alanlari.items()},
                    "iyzico": iyz,
                })
        await _db.settings.update_one({"id": flag_id}, {"$set": {
            "id": flag_id, "done": True, "at": _dt.now(_tz.utc).isoformat(),
            "vaka": len(rapor), "rapor": rapor,
            "note": "Salt okunur. 'onaylanan_iade' panelde onaylanan tutar; paranın fiilen "
                    "çıkıp çıkmadığı iyzico kalem durumlarından ve siparişin iade "
                    "alanlarından okunur."}}, upsert=True)
        logger.warning(f"[denetim] alt-kume iade v2: vaka={len(rapor)}")
    except Exception as e:
        logger.error(f"[denetim] alt-kume iade v2 hata: {e}")


async def scrub_phone_once(raw_phone: str, reason: str = "") -> None:
    """Bir telefon numarasını TÜM kayıtlardan siler (üye, adres, sipariş, İYS izni, OTP, influencer)
    ve SMS kara listesine alır. Tek seferlik (bayraklı); sonuç sayaçları settings.phone_scrub_<tail>."""
    import re as _re
    from datetime import datetime as _dt, timezone as _tz
    from notification_service import normalize_phone_tr as _norm
    from routes.deps import db as _db
    norm = _norm(raw_phone)
    tail = norm[-10:] if len(norm) >= 10 else norm
    if not tail:
        return
    flag_id = f"phone_scrub_{tail}"
    try:
        if await _db.settings.find_one({"id": flag_id, "done": True}):
            return
        rx = {"$regex": _re.escape(tail) + r"\s*$"}
        now = _dt.now(_tz.utc).isoformat()
        counts = {}
        r = await _db.users.update_many({"phone": rx}, {"$set": {"phone": "", "phone_verified": False, "phone_scrubbed_at": now}})
        counts["users"] = r.modified_count
        r = await _db.addresses.update_many({"phone": rx}, {"$set": {"phone": "", "phone_scrubbed_at": now}})
        counts["addresses"] = r.modified_count
        for fld in ("shipping_address.phone", "billing_address.phone", "phone", "customer_phone"):
            r = await _db.orders.update_many({fld: rx}, {"$set": {fld: "", "phone_scrubbed_at": now}})
            counts[f"orders.{fld}"] = r.modified_count
        r = await _db.iys_consents.update_many({"phone": rx}, {"$set": {"phone": "", "phone_scrubbed_at": now}, "$pull": {"channels": "MESAJ"}})
        counts["iys_consents"] = r.modified_count
        r = await _db.otp_verifications.delete_many({"phone": rx})
        counts["otp_verifications"] = r.deleted_count
        for coll, fld in (("influencers", "phone"), ("influencers", "shipping_address.phone"), ("influencer_pr", "phone")):
            try:
                r = await getattr(_db, coll).update_many({fld: rx}, {"$set": {fld: "", "phone_scrubbed_at": now}})
                counts[f"{coll}.{fld}"] = r.modified_count
            except Exception:
                pass
        await _db.sms_suppressions.update_one({"phone": norm}, {"$set": {"phone": norm, "reason": reason, "created_at": now}}, upsert=True)
        await _db.settings.update_one({"id": flag_id}, {"$set": {"id": flag_id, "done": True, "at": now, "counts": counts}}, upsert=True)
        logger.warning(f"[phone-scrub] tamamlandı: {counts}")
    except Exception as e:
        logger.error(f"[phone-scrub] hata: {e}")
        try:
            await _db.settings.update_one({"id": flag_id}, {"$set": {"id": flag_id, "done": False, "error": str(e)[:200]}}, upsert=True)
        except Exception:
            pass


async def _stock_trace_block(q: str = "") -> dict:
    """SALT OKUNUR stok izi: bir ürünün stoğu BUGÜNKÜ değerine NASIL geldi?

    `q` = ürün adı parçası / stok kodu / barkod. Eşleşen ürünler için:
      • şu anki stok (ürün + varyant kırılımı)
      • db.stock_movements'taki TÜM hareketler (en eski→en yeni), delta ve aktörüyle
      • defter toplamı ile canlı stoğun karşılaştırması → AÇIKLANAMAYAN fark
      • bu ürünün barkodlarını içeren siparişlerin durum dağılımı
    HİÇBİR YAZMA YAPMAZ. Ticari veri taşıdığı için çağıran yer audit_key ister.
    """
    try:
        import re as _re_st
        if not q or len(str(q).strip()) < 2:
            return {"hata": "stock_q gerekli (ürün adı parçası / stok kodu / barkod)"}
        qs = str(q).strip()
        rx = {"$regex": _re_st.escape(qs), "$options": "i"}
        prods = await db.products.find(
            {"$or": [{"name": rx}, {"stock_code": rx}, {"barcode": qs},
                     {"variants.barcode": qs}, {"variants.stock_code": rx}]},
            {"_id": 0, "id": 1, "name": 1, "stock_code": 1, "barcode": 1, "stock": 1,
             "variants": 1, "is_active": 1, "created_at": 1, "updated_at": 1},
        ).limit(4).to_list(4)
        if not prods:
            return {"hata": f"'{qs}' ile ürün bulunamadı"}

        out = []
        for p in prods:
            pid = str(p.get("id") or "")
            variants = p.get("variants") or []
            bcs = [str(v.get("barcode")) for v in variants if v.get("barcode")]
            if p.get("barcode"):
                bcs.append(str(p["barcode"]))
            vnow = [{"barkod": v.get("barcode"), "beden": v.get("size"),
                     "renk": v.get("color"), "stok": v.get("stock")} for v in variants]
            canli_toplam = sum(int(v.get("stock") or 0) for v in variants) if variants \
                else int(p.get("stock") or 0)

            # ── Hareket defteri (tüm şemalar: items / moves / v2) ──────────────
            movs = await db.stock_movements.find(
                {"$or": [{"items.product_id": pid}, {"moves.product_id": pid},
                         {"product_id": pid}, {"items.barcode": {"$in": bcs[:50]}},
                         {"moves.barcode": {"$in": bcs[:50]}}]},
                {"_id": 0},
            ).sort("created_at", 1).limit(4000).to_list(4000)

            satirlar, defter_delta, tip_ozet, tip_qty = [], 0, {}, {}
            for m in movs:
                rows = (m.get("items") or []) + (m.get("moves") or [])
                d, detay = 0, []
                for it in rows:
                    if not isinstance(it, dict):
                        continue
                    _bc = str(it.get("barcode") or "")
                    if it.get("product_id") and str(it["product_id"]) != pid and _bc not in bcs:
                        continue
                    if not it.get("product_id") and _bc and _bc not in bcs:
                        continue
                    _dl = it.get("delta")
                    # BAZI YAZICILAR 'qty' KULLANIYOR: pazaryeri iade (claim) geri-stok
                    # satırları delta yerine qty yazıyor (integrations_common.py:2198,
                    # (kaldırılan entegrasyon)). $inc GERÇEKTEN çalışmış ama defter
                    # satırı 'delta' okuyan her yere 0 görünüyor. Burada doğru okunur;
                    # kaynaktaki alan adı ayrıca düzeltilmelidir.
                    if _dl is None and it.get("qty") is not None:
                        _dl = it.get("qty")
                    if _dl is None and it.get("old") is not None and it.get("new") is not None:
                        _dl = int(it["new"]) - int(it["old"])
                    try:
                        _dl = int(_dl or 0)
                    except Exception:
                        _dl = 0
                    d += _dl
                    detay.append({"barkod": _bc or None, "beden": it.get("size"),
                                  "delta": _dl, "once": it.get("old"), "sonra": it.get("new")})
                if any(isinstance(x, dict) and x.get("delta") is None
                       and x.get("qty") is not None for x in rows):
                    tip_qty[str(m.get("type") or "?")] = tip_qty.get(
                        str(m.get("type") or "?"), 0) + 1
                defter_delta += d
                _t = str(m.get("type") or m.get("action") or "?")
                _o = tip_ozet.setdefault(_t, {"adet": 0, "delta": 0})
                _o["adet"] += 1
                _o["delta"] += d
                satirlar.append({
                    "tarih": m.get("created_at"), "tip": _t,
                    "kaynak": m.get("source") or (m.get("sync_result") or {}).get("platform"),
                    "siparis": m.get("order_number") or m.get("order_id"),
                    "kim": (m.get("actor") or {}).get("email") or m.get("created_by") or "",
                    "toplam_delta": d, "kalemler": detay[:12],
                })

            # ── Bu ürünün barkodlarını içeren siparişler ───────────────────────
            sip_durum, sip_adet = {}, 0
            try:
                async for r in db.orders.aggregate([
                    {"$match": {"items.barcode": {"$in": bcs[:50]}}},
                    {"$group": {"_id": "$status", "n": {"$sum": 1}}},
                ], allowDiskUse=True):
                    sip_durum[str(r.get("_id") or "?")] = int(r.get("n") or 0)
                    sip_adet += int(r.get("n") or 0)
            except Exception as _oe:
                sip_durum = {"hata": str(_oe)[:120]}

            # ── SİPARİŞ-SİPARİŞ MUTABAKAT: hangi sipariş stoğu DÜŞÜRMEDİ? ─────
            # "Stok neden düşmedi?" sorusunun tek kesin cevabı burada: bu ürünü
            # içeren HER siparişi stok defteriyle eşleştirir, düşüm hareketi
            # OLMAYANLARI ay/kanal/statü kırılımıyla ve ADETİYLE gösterir.
            DUS = ["order_created", "order_imported", "manual_decrement",
                   "backfill_decrement", "influencer_seeding"]
            # Stoğu meşru şekilde DÜŞÜRMEMESİ gereken statüler (hiç rezerve edilmedi).
            YOK = {"cancelled", "cancel_refunded", "pending", "awaiting_payment",
                   "payment_failed", "payment_notified"}
            eksik = {"adet_siparis": 0, "adet_urun": 0, "ay": {}, "kanal": {},
                     "statu": {}, "ornekler": []}
            dusen = {"siparis": 0, "urun": 0}
            try:
                _oids = []
                async for o in db.orders.find(
                        {"items.barcode": {"$in": bcs[:50]}},
                        {"_id": 0, "id": 1, "order_number": 1, "status": 1,
                         "platform": 1, "marketplace": 1, "created_at": 1,
                         "marketplace_order_date": 1, "items.barcode": 1,
                         "items.quantity": 1}):
                    _oids.append(o)
                _ids = [str(o.get("id")) for o in _oids if o.get("id")]
                _has = set()
                for i in range(0, len(_ids), 4000):
                    async for mv in db.stock_movements.find(
                            {"order_id": {"$in": _ids[i:i + 4000]},
                             "type": {"$in": DUS}}, {"_id": 0, "order_id": 1}):
                        _has.add(str(mv.get("order_id")))
                for o in _oids:
                    _q = 0
                    for it in (o.get("items") or []):
                        if str((it or {}).get("barcode") or "") in bcs:
                            try:
                                _q += max(1, int(it.get("quantity") or 1))
                            except Exception:
                                _q += 1
                    if str(o.get("id")) in _has:
                        dusen["siparis"] += 1
                        dusen["urun"] += _q
                        continue
                    _st = str(o.get("status") or "?")
                    if _st in YOK:
                        continue          # zaten düşmemesi gerekiyordu
                    _ay = str(o.get("marketplace_order_date")
                              or o.get("created_at") or "")[:7] or "?"
                    _ch = (str(o.get("platform") or "").lower()
                           or str(o.get("marketplace") or "").lower() or "site")
                    eksik["adet_siparis"] += 1
                    eksik["adet_urun"] += _q
                    eksik["ay"][_ay] = eksik["ay"].get(_ay, 0) + _q
                    eksik["kanal"][_ch] = eksik["kanal"].get(_ch, 0) + _q
                    eksik["statu"][_st] = eksik["statu"].get(_st, 0) + _q
                    if len(eksik["ornekler"]) < 15:
                        eksik["ornekler"].append(
                            {"siparis": o.get("order_number"), "statu": _st,
                             "kanal": _ch, "tarih": _ay, "adet": _q})
            except Exception as _re2:
                eksik = {"hata": str(_re2)[:200]}

            out.append({
                "urun": {"id": pid, "ad": p.get("name"), "stok_kodu": p.get("stock_code"),
                         "aktif": p.get("is_active"), "olusturma": p.get("created_at"),
                         "son_guncelleme": p.get("updated_at")},
                "canli_stok": {"urun_alani": p.get("stock"), "varyant_toplami": canli_toplam,
                               "varyantlar": vnow},
                "defter": {"hareket_adedi": len(movs), "toplam_delta": defter_delta,
                           "alan_adi_qty_olan_hareketler": tip_qty,
                           "tip_ozeti": tip_ozet,
                           "aciklanamayan_fark": canli_toplam - defter_delta,
                           "not": ("Defter toplamı ile canlı stok arasındaki fark, DEFTERE "
                                   "YAZILMADAN yapılmış stok değişikliğidir (ör. eski manuel "
                                   "düzenleme, import, doğrudan DB yazımı).")},
                "siparisler": {"toplam": sip_adet, "durum_dagilimi": sip_durum,
                               "stogu_dusen": dusen,
                               "STOGU_DUSMEYEN": eksik},
                "hareketler": satirlar,
            })
        return {"sorgu": qs, "urun_sayisi": len(out), "sonuc": out}
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}


async def _order_lookup(nos: str = "") -> dict:
    """SALT OKUNUR: verilen sipariş numaralarını bizim kayıtlarımızla eşleştir.

    "Pazaryeri listesindeki her sipariş bizde var mı?" sorusunun sipariş-sipariş
    cevabı. Her numara için: bizde var mı, statüsü ne, hangi tarihle kayıtlı.
    Saat kayması teşhisi için kayıtlı ham tarih de döner (dönüştürülmeden).
    """
    try:
        _l = [x.strip() for x in str(nos or "").replace(";", ",").split(",") if x.strip()]
        if not _l:
            return {"hata": "orders_q gerekli (virgülle sipariş numaraları)"}
        _l = _l[:600]
        bulunan = {}
        async for o in db.orders.find(
                {"order_number": {"$in": _l}},
                {"_id": 0, "order_number": 1, "status": 1, "total": 1, "platform": 1,
                 "marketplace_order_date": 1, "created_at": 1, "cancelled_at": 1,
                 "items.quantity": 1}):
            _q = 0
            for it in (o.get("items") or []):
                try:
                    _q += max(1, int((it or {}).get("quantity") or 1))
                except Exception:
                    _q += 1
            bulunan[str(o.get("order_number"))] = {
                "statu": o.get("status"), "tutar": o.get("total"), "adet": _q,
                "kayitli_siparis_tarihi": o.get("marketplace_order_date"),
                "olusturma": o.get("created_at"), "iptal_tarihi": o.get("cancelled_at"),
                "platform": o.get("platform"),
            }
        eksik = [n for n in _l if n not in bulunan]
        _st = {}
        _adet = 0
        _tut = 0.0
        for v in bulunan.values():
            _st[str(v.get("statu"))] = _st.get(str(v.get("statu")), 0) + 1
            _adet += int(v.get("adet") or 0)
            try:
                _tut += float(v.get("tutar") or 0)
            except Exception:
                pass
        return {
            "sorgulanan": len(_l), "bulunan": len(bulunan), "EKSIK": len(eksik),
            "eksik_liste": eksik[:60],
            "statu_dagilimi": _st,
            "toplam_urun_adedi": _adet,
            "toplam_tutar": round(_tut, 2),
            "ornek_kayitlar": dict(list(bulunan.items())[:8]),
        }
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}


async def _iade_listesi(start_date: str = "", end_date: str = "") -> dict:
    """SALT OKUNUR: dönemdeki iade belgelerimizin KOMPAKT dökümü.

    harici kanal "İadeleriniz" Excel'iyle iade iade kıyas için iki kaynak:
      • gider_pusulasi — raporun İADE saydığı otantik belge (numaralı = kesinleşmiş)
      • harici kanal — harici kanal senkronlanan iade talepleri ve kalem statüleri
    Aralık, pusulanın kesildiği / talebin açıldığı / onaylandığı tarihlerden HERHANGİ
    biri aralıktaysa kaydı içerir (haziran talebinin pusulası temmuzda kesilmiş olabilir).
    Müşteri kişisel verisi DÖNMEZ; yalnız sipariş no, tarih, tutar, barkod, adet.
    """
    try:
        from routes.reports import _iso_range
        s, e = _iso_range(start_date or None, end_date or None)
        gp = []
        async for g in db.gider_pusulasi.find(
                {"created_at": {"$gte": s, "$lte": e}},
                {"_id": 0, "order_number": 1, "number": 1, "display_number": 1,
                 "created_at": 1, "totals.net": 1, "items.barcode": 1,
                 "items.quantity": 1, "source": 1}):
            gp.append([str(g.get("order_number") or ""),
                       g.get("number") or g.get("display_number") or "",
                       str(g.get("created_at") or "")[:19],
                       (g.get("totals") or {}).get("net"),
                       [[str((i or {}).get("barcode") or ""), (i or {}).get("quantity")]
                        for i in (g.get("items") or [])],
                       g.get("source") or ""])
        cl = []   # site dışı kanal iade talepleri bu mağazada tutulmaz
        return {"aralik": [s, e],
                "pusula_alanlar": ["siparis", "kocan_no", "tarih", "net", "kalemler", "kaynak"],
                "pusulalar": gp,
                "talep_alanlar": ["siparis", "claim_id", "statu", "tip", "acilis",
                                  "onay", "iade_tutari", "kalemler(barkod,adet,statu)"],
                "talepler": cl}
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}


async def _pusula_lookup(nos: str) -> dict:
    """SALT OKUNUR: verilen sipariş numaralarına kesilmiş gider pusulalarını döker.

    "Aynı siparişe üç pusula" mükerrer mi, yoksa üç ayrı kısmi iade mi? Bu ancak
    belgelerin KENDİLERİNE bakılarak anlaşılır: koçan numaraları farklı mı, aynı gün
    mü kesilmiş, kalemleri aynı mı. Rapordan iade düşmeden önce bu görülmeli.
    """
    try:
        _nos = [x.strip() for x in str(nos or "").replace(";", ",").split(",") if x.strip()]
        if not _nos:
            return {"hata": "pusula_q gerekli (virgülle sipariş numaraları)"}
        out: dict = {}
        for _n in _nos[:25]:
            _belgeler = []
            async for g in db.gider_pusulasi.find(
                    {"order_number": _n},
                    {"_id": 0, "number": 1, "display_number": 1, "created_at": 1,
                     "source": 1, "totals": 1, "items": 1, "order_number": 1}):
                _it = []
                for i in (g.get("items") or []):
                    _it.append({"barkod": (i or {}).get("barcode"),
                                "ad": str((i or {}).get("name") or "")[:40],
                                "adet": (i or {}).get("quantity")})
                _belgeler.append({
                    "kocan_no": g.get("number") or g.get("display_number"),
                    "tarih": str(g.get("created_at") or "")[:19],
                    "kaynak": g.get("source"),
                    "net": (g.get("totals") or {}).get("net"),
                    "kalemler": _it,
                })
            _belgeler.sort(key=lambda x: str(x.get("tarih") or ""))
            _o = await db.orders.find_one(
                {"order_number": _n},
                {"_id": 0, "order_number": 1, "status": 1, "platform": 1, "total": 1,
                 "created_at": 1, "marketplace_order_date": 1, "items": 1})
            out[_n] = {
                "pusula_sayisi": len(_belgeler),
                "pusulalar": _belgeler,
                "siparis_BULUNDU": bool(_o),
                "siparis": ({"statu": _o.get("status"), "platform": _o.get("platform"),
                             "tutar": _o.get("total"),
                             "tarih": str(_o.get("marketplace_order_date")
                                          or _o.get("created_at") or "")[:19],
                             "kalem_sayisi": len(_o.get("items") or [])} if _o else None),
            }
        return out
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}


async def _bozuk_tutar_block() -> dict:
    """SALT OKUNUR: tutarı GEÇERSİZ SAYI (NaN/Infinity) olan siparişleri bulur.

    MongoDB bu değerleri saklayabilir; toplandıklarında sonucun tamamı NaN olur.
    Haziran denetimi böyle çöküyordu (iptal toplamı → net → ortalama sepet → yanıt
    JSON'a yazılamıyor → 500). Raporlar artık bozuk değeri 0 sayıyor, ama KAYIT
    hâlâ bozuk; asıl tutarın ne olması gerektiğine yalnız işletme karar verebilir,
    bu yüzden burada sadece LİSTELENİR, değiştirilmez.
    """
    try:
        _nan = float("nan")
        _inf = float("inf")
        out: dict = {"alanlar": {}, "siparisler": []}
        _gorulen = set()
        for _alan in ("total", "subtotal", "shipping_cost", "discount_amount",
                      "partial_cancel_amount"):
            _q = {"$or": [{_alan: _nan}, {_alan: _inf}, {_alan: -_inf}]}
            _n = await db.orders.count_documents(_q)
            if not _n:
                continue
            out["alanlar"][_alan] = _n
            async for o in db.orders.find(_q, {
                    "_id": 0, "order_number": 1, "status": 1, "platform": 1,
                    "created_at": 1, "marketplace_order_date": 1, "cancelled_at": 1,
                    "total": 1, "items": 1}).limit(25):
                _on = str(o.get("order_number") or "")
                if _on in _gorulen:
                    continue
                _gorulen.add(_on)
                # Kalemlerden hesaplanan tutar — düzeltme için REFERANS (uygulanmaz).
                _hesap = 0.0
                for _it in (o.get("items") or []):
                    try:
                        _q2 = max(1, int((_it or {}).get("quantity") or 1))
                        _pr = float((_it or {}).get("price")
                                    or (_it or {}).get("unit_price") or 0)
                        if _pr == _pr and abs(_pr) != float("inf"):
                            _hesap += _q2 * _pr
                    except Exception:
                        pass
                out["siparisler"].append({
                    "siparis_no": _on, "bozuk_alan": _alan,
                    "statu": o.get("status"), "platform": o.get("platform"),
                    "siparis_tarihi": str(o.get("marketplace_order_date")
                                          or o.get("created_at") or "")[:19],
                    "iptal_tarihi": str(o.get("cancelled_at") or "")[:19],
                    "kalem_sayisi": len(o.get("items") or []),
                    "kalemlerden_hesaplanan_tutar": round(_hesap, 2),
                })
        out["toplam_bozuk_kayit"] = sum(out["alanlar"].values())
        out["not"] = ("Bu kayıtlar DEĞİŞTİRİLMEDİ. Raporlar bozuk değeri 0 sayarak "
                      "devam eder; doğru tutarın ne olacağına işletme karar vermeli. "
                      "'kalemlerden_hesaplanan_tutar' yalnız referanstır.")
        return out
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}


def _json_safe(obj, bad: list, path: str = ""):
    """NaN / Infinity değerlerini temizler ve NEREDE bulunduklarını kaydeder.

    Starlette'in JSONResponse'u json.dumps(..., allow_nan=False) kullanır: yanıtta
    tek bir NaN/Infinity varsa serileştirme ANDA patlar ve TÜM /health yanıtı 500
    olur. Bu, endpoint çalıştıktan SONRA olduğu için blok içindeki try/except
    yakalayamaz — haziran denetimi tam olarak böyle düşüyordu (8 sn'de 500, zaman
    aşımı değil). Bozuk sayı None'a çevrilir, yolu 'bozuk_sayilar'da raporlanır.
    """
    import math
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            if len(bad) < 40:
                bad.append(path or "(kök)")
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _json_safe(v, bad, f"{path}.{k}" if path else str(k))
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v, bad, f"{path}[{i}]") for i, v in enumerate(obj)]
    return obj


_RAPOR_Q_YASAK = {"/products/export-xlsx", "/gated/stock-restock-audit", "/profitability-config"}


async def _rapor_sorgu(q: str, start_date: str = "", end_date: str = "", source: str = "") -> dict:
    """rapor_q: Raporlar sayfasının GÖSTERDİĞİ rakamları, sayfanın çağırdığı AYNI uç
    fonksiyonlarıyla üretir (denetim/kıyas için). SALT OKUNUR: yalnız GET rapor uçları;
    yazma bayrağı taşıyan ('apply') ve dosya üreten uçlar hariç. Müşteri kişisel verisi
    rapor asistanının temizleyicisinden geçirilir.
    Biçim: rapor_q=sales-breakdown,sales?group_by=month,by-location?group=city&limit=20"""
    import inspect
    from routes import reports as _R
    from routes import reports_v2 as _R2
    from routes.report_assistant import _cagir, _temizle
    from routes.report_dedup import load_dup_order_numbers as _ldc_rq
    from fastapi.routing import APIRoute
    # Uçlar router bağımlılığı (load_dup_dep) OLMADAN doğrudan çağrılıyor: eski altyapı kopya
    # elemesi yüklenmezse soğuk süreçte ay rakamları şişik çıkıyordu. Önce yükle.
    try:
        await _ldc_rq()
    except Exception:
        pass
    uclar = {r.path.replace(_R.router.prefix, "", 1): r.endpoint for r in _R.router.routes
             if isinstance(r, APIRoute) and "GET" in r.methods}
    # Kâr & Stok Değer sayfasının uçları (/admin/reports2/*) "v2/<uç>" adıyla (salt GET).
    uclar.update({"/v2" + r.path.replace(_R2.router.prefix, "", 1): r.endpoint
                  for r in _R2.router.routes if isinstance(r, APIRoute) and "GET" in r.methods})
    ortak = {"start_date": start_date or None, "end_date": end_date or None,
             "source": source or None}
    out: dict = {"aralik": {"start": start_date, "end": end_date, "source": source or "all"}}
    for parca in [p.strip() for p in (q or "").split(",") if p.strip()][:12]:
        yol, _, qs = parca.partition("?")
        yol = "/" + yol.strip("/")
        fn = uclar.get(yol)
        if not fn or yol in _RAPOR_Q_YASAK:
            out[yol] = {"hata": "bilinmeyen/izinsiz uç", "izinli": sorted(set(uclar) - _RAPOR_Q_YASAK)}
            continue
        imza = inspect.signature(fn).parameters
        kw = {k: v for k, v in ortak.items() if k in imza and v is not None}
        for kv in qs.split("&"):
            k, _, v = kv.partition("=")
            if k and k in imza and k not in ("apply", "current_user"):
                if k in ("limit", "days", "window_days", "min_sold", "top", "velocity_days",
                         "horizon_days", "target_cover_days", "min_orders", "min_stock") and v.isdigit():
                    kw[k] = int(v)
                elif k in ("threshold", "min_velocity"):
                    try:
                        kw[k] = float(v)
                    except ValueError:
                        kw[k] = v
                else:
                    kw[k] = v
        try:
            out[yol] = _temizle(await _cagir(fn, {"id": "diag", "role": "super_admin",
                                                   "email": "diag@local"}, **kw))
        except Exception as _e:
            out[yol] = {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}
    return out


async def _asistan_log_block() -> dict:
    """Rapor asistanının son 15 cevabı: hangi sağlayıcı cevapladı, başarısız denemeler
    (ör. Gemini hata metni), süre. Soru/cevap METNİ döndürülmez. Salt okuma."""
    rows = await db.report_assistant_logs.find(
        {}, {"_id": 0, "at": 1, "saglayici": 1, "denemeler": 1, "ms": 1, "araclar": 1}
    ).sort("at", -1).limit(15).to_list(15)
    from routes.report_assistant import _anahtar
    return {"son": rows,
            "anahtar_var": {"gemini": bool(await _anahtar("GEMINI_API_KEY", "gemini|google")),
                            "openai": bool(await _anahtar("OPENAI_API_KEY", "openai"))}}


async def _destek_teshis(mod: str = "", eposta: str = "") -> dict:
    """SALT OKUNUR destek teşhisi. PII DÖNMEZ (e-posta yalnız eşleme için kullanılır).
    mod=kargo  : son 14 günde eşik altında ücretsiz kargoyla açılan site siparişleri
    mod=uyelik : hoş geldin kodu/maili zinciri (kural, şablon, sağlayıcı, loglar, popup)
    mod=yavas  : >3 sn yanıtlar (error_logs.slow_response) uç bazında"""
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    now = _dt.now(_tz.utc)
    out = {"mod": mod}
    if mod == "kargo":
        bas = (now - _td(days=14)).isoformat()
        q = {"created_at": {"$gte": bas}, "free_shipping_applied": True}
        rows = []
        async for o in db.orders.find(q, {"_id": 0, "order_number": 1, "created_at": 1, "status": 1,
                                          "payment_status": 1, "source": 1, "channel": 1,
                                          "shipping_eligibility_basis": 1, "subtotal": 1,
                                          "free_shipping_waived_fee": 1, "free_shipping_threshold": 1,
                                          "applied_promotions": 1}).sort("created_at", 1):
            basis = o.get("shipping_eligibility_basis")
            if basis is None:
                basis = o.get("subtotal")
            rows.append({"no": o.get("order_number"), "at": o.get("created_at"), "status": o.get("status"),
                         "pay": o.get("payment_status"), "kaynak": o.get("source") or o.get("channel"),
                         "basis": basis, "esik": o.get("free_shipping_threshold"),
                         "feragat": o.get("free_shipping_waived_fee"),
                         "promo_fs": [a.get("code") for a in (o.get("applied_promotions") or [])
                                      if isinstance(a, dict) and a.get("free_shipping")]})
        out["siparisler"] = rows
        out["esik_alti"] = [r for r in rows
                            if r["esik"] not in (None, "") and (r["basis"] or 0) < float(r["esik"] or 0)]
        return out
    if mod == "uyelik":
        from business_rules import get_rule as _gr
        out["kural"] = {k: await _gr(db, k, None) for k in
                        ("welcome.enabled", "welcome.reward_type", "welcome.reward_value")}
        out["sablon"] = []
        async for t in db.notification_templates.find({"event": "welcome"}, {"_id": 0, "body": 0}):
            out["sablon"].append({k: (str(v)[:120] if isinstance(v, str) else v) for k, v in t.items()
                                  if k in ("event", "channel", "enabled", "is_active", "subject", "updated_at")})
        prov = await db.settings.find_one({"id": "notification_providers"}, {"_id": 0, "email_active": 1}) or {}
        out["saglayici_email_active"] = prov.get("email_active", True)
        st = await db.settings.find_one({"id": "main"}, {"_id": 0, "email_smtp": 1}) or {}
        es = st.get("email_smtp") or {}
        out["email_ayar"] = {"enabled": es.get("enabled"), "username_var": bool(es.get("username")),
                             "password_var": bool(es.get("password")), "host": es.get("host")}
        since = (now - _td(days=14)).isoformat()
        agg = {}
        async for r in db.notification_logs.find({"created_at": {"$gte": since}},
                                                  {"_id": 0, "event": 1, "channel": 1, "status": 1}):
            k = f"{r.get('event')}/{r.get('channel')}/{r.get('status')}"
            agg[k] = agg.get(k, 0) + 1
        out["bildirim_log_14g"] = dict(sorted(agg.items()))
        son_hata = []
        async for r in db.notification_logs.find({"channel": "email", "status": {"$nin": ["sent", "success", "ok"]},
                                                   "created_at": {"$gte": since}},
                                                  {"_id": 0, "event": 1, "status": 1, "response": 1,
                                                   "created_at": 1}).sort("created_at", -1).limit(8):
            son_hata.append({"event": r.get("event"), "status": r.get("status"),
                             "resp": (r.get("response") or "")[:200], "at": r.get("created_at")})
        out["email_son_hatalar"] = son_hata
        out["yeni_uye_7g"] = {}
        async for u in db.users.find({"created_at": {"$gte": (now - _td(days=7)).isoformat()}},
                                     {"_id": 0, "auth_provider": 1, "role": 1}):
            if u.get("role") not in (None, "", "customer", "user"):
                continue
            k = u.get("auth_provider") or "email"
            out["yeni_uye_7g"][k] = out["yeni_uye_7g"].get(k, 0) + 1
        out["bulten_7g"] = {}
        async for n in db.newsletter_subscribers.find({"created_at": {"$gte": (now - _td(days=7)).isoformat()}},
                                                      {"_id": 0, "source": 1}):
            k = n.get("source") or "?"
            out["bulten_7g"][k] = out["bulten_7g"].get(k, 0) + 1
        out["hg_kupon_7g"] = await db.coupons.count_documents(
            {"source": "welcome", "created_at": {"$gte": (now - _td(days=7)).isoformat()}})
        pops = []
        async for pp in db.popups.find({}, {"_id": 0, "name": 1, "title": 1, "is_active": 1, "type": 1,
                                            "popup_type": 1, "button_text": 1, "content": 1}):
            pops.append({k: (str(v)[:160] if isinstance(v, str) else v) for k, v in pp.items()})
        out["popuplar"] = pops
        fo = await db.coupons.find({"is_active": True, "first_order_only": True},
                                   {"_id": 0, "code": 1, "value": 1, "type": 1, "start_at": 1, "end_at": 1,
                                    "auto_apply": 1}).to_list(10)
        out["ilk_siparis_kuponlari"] = fo
        e = (eposta or "").strip().lower()
        if e:
            u = await db.users.find_one({"email": e}, {"_id": 0, "auth_provider": 1, "created_at": 1,
                                                      "email_verified": 1})
            nb = await db.newsletter_subscribers.find_one({"email": e}, {"_id": 0, "source": 1, "created_at": 1})
            hg = await db.coupons.count_documents({"source": "welcome", "email": e})
            out["musteri"] = {"uye": bool(u), "uye_provider": (u or {}).get("auth_provider") or ("email" if u else None),
                              "uye_at": (u or {}).get("created_at"), "dogrulandi": (u or {}).get("email_verified"),
                              "bulten": bool(nb), "bulten_kaynak": (nb or {}).get("source"),
                              "bulten_at": (nb or {}).get("created_at"), "hg_kupon": hg}
        return out
    if mod == "yavas":
        res = {}
        for gun in (0.125, 1, 7):  # 0.125 gün = son 3 saat (düzeltme sonrası durumu ayrı görmek için)
            since = (now - _td(days=gun)).isoformat()
            agg = {}
            async for r in db.error_logs.find({"kind": "slow_response", "created_at": {"$gte": since}},
                                              {"_id": 0, "path": 1, "meta": 1}):
                p = r.get("path") or "?"
                a = agg.setdefault(p, [0, 0])
                a[0] += 1
                a[1] = max(a[1], int((r.get("meta") or {}).get("duration_ms") or 0))
            res["3s" if gun == 0.125 else f"{gun}g"] = sorted(([p, n, mx] for p, (n, mx) in agg.items()), key=lambda x: -x[1])[:30]
        out["yavas"] = res
        return out
    if mod == "meta":
        feeds = await db.xml_feeds.find({}, {"_id": 0, "slug": 1, "target": 1, "in_stock_only": 1,
                                             "group_variants": 1, "name": 1}).to_list(50)
        out["feeds"] = feeds
        ids = [x.strip() for x in (eposta or "").split(",") if x.strip()][:200]
        res = {}
        for cid in ids:
            hits = []
            async for pr in db.products.find({"$or": [{"variants.id": cid}, {"id": cid}]},
                                             {"_id": 0, "id": 1, "is_active": 1, "is_deleted": 1,
                                              "variants": 1, "stock_code": 1}).limit(5):
                v = next((v for v in (pr.get("variants") or []) if str(v.get("id")) == cid), None)
                hits.append({"pid": pr.get("id"), "aktif": pr.get("is_active"), "silik": pr.get("is_deleted"),
                             "sk": pr.get("stock_code"), "vstok": (v or {}).get("stock") if v else None,
                             "urun_id_mi": pr.get("id") == cid})
            res[cid] = hits
        out["idler"] = res
        # Aktif ürünler arasında AYNI varyant id'si birden fazla üründe mi? (katalogda çakışır)
        dup = {}
        tot = 0
        async for pr in db.products.find({"is_active": True, "is_deleted": {"$ne": True}},
                                         {"_id": 0, "id": 1, "variants.id": 1}):
            for v in (pr.get("variants") or []):
                vid = str(v.get("id") or "")
                if not vid:
                    continue
                tot += 1
                dup.setdefault(vid, set()).add(pr.get("id"))
        cak = {k: len(v) for k, v in dup.items() if len(v) > 1}
        out["aktif_varyant_toplam"] = tot
        out["cakisan_varyant_id_sayisi"] = len(cak)
        out["cakisan_ornek"] = sorted(cak.items(), key=lambda x: -x[1])[:15]
        out["bos_varyant_id"] = None
        return out
    if mod == "siparis":
        # Tek sipariş PARA teşhisi (PII YOK): kalemler, tutar alanları, fatura alanları.
        q = (eposta or "").strip()
        ors = [{"order_number": q}, {"marketplace_order_id": q}, {"package_number": q}, {"id": q}]
        docs = []
        _money_keys = ("order_number", "platform", "status", "payment_status", "created_at",
                       "marketplace_order_date", "subtotal", "discount", "discount_total", "total",
                       "total_amount", "shipping_cost", "marketplace_total", "package_number",
                       "invoice_issued", "invoice_number", "invoice_type", "invoice_total",
                       "invoice_amount", "invoice_created_at", "invoice_lines_total",
                       "invoice_payable", "invoice_items_count",
                       "merged_from", "split_from", "cancelled_items",
                       "partial_cancel", "updated_at")
        async for o in db.orders.find({"$or": ors}, {"_id": 0}).limit(10):
            its = []
            for it in (o.get("items") or []):
                its.append({k: it.get(k) for k in (
                    "name", "sku", "barcode", "stock_code", "quantity", "price", "unit_price",
                    "list_price", "sale_price", "discount_amount", "discount",
                    "merchant_discount", "total", "line_total", "kdv_rate", "vat_rate", "status",
                    "line_status", "package_number", "cancelled", "is_cancelled")
                    if it.get(k) not in (None, "")})
            d = {k: o.get(k) for k in _money_keys if o.get(k) not in (None, "")}
            d["kalem_sayisi"] = len(its)
            d["kalemler"] = its
            try:
                d["kalem_brut_toplam"] = round(sum(float(i.get("price") or 0) * int(i.get("quantity") or 1)
                                                   for i in (o.get("items") or [])), 2)
            except Exception:
                pass
            # Fatura ile ilgili TÜM alan adları (değer türüyle) — nereden okunduğunu görmek için
            d["fatura_alanlari"] = {k: (v if isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) < 80) else type(v).__name__)
                                    for k, v in o.items() if "invoice" in k or "fatura" in k or "einvoice" in k}
            docs.append(d)
        out["siparisler"] = docs
        try:
            import re as _re_fk
            _fl2 = await db.settings.find({"id": {"$regex": "^fatura_yeniden_kesim:.*" + _re_fk.escape(q)}},
                                          {"_id": 0}).to_list(5)
            if _fl2:
                out["iptal_sonrasi_kesim"] = _fl2
        except Exception:
            pass
        # Doğan/e-fatura gönderim kaydı varsa (koleksiyon adları sistemden bağımsız denenir)
        for col in ("invoice_logs", "einvoice_logs", "dogan_invoice_logs", "invoices"):
            try:
                rows = []
                async for r in db[col].find({"$or": [{"order_number": q}, {"order_id": {"$in": [x.get("id") for x in []]}}]},
                                            {"_id": 0}).limit(5):
                    rows.append({k: (v if isinstance(v, (int, float, bool)) or (isinstance(v, str) and len(v) < 120) else type(v).__name__)
                                 for k, v in r.items() if k not in ("customer", "buyer", "address", "email", "phone", "tckn")})
                if rows:
                    out[col] = rows
            except Exception:
                pass
        return out
    if mod == "iys":
        # İYS bildirim durumu (salt okunur; e-posta/telefon MASKELİ).
        import re as _re
        from routes.iys import _iys_config
        cfg = await _iys_config()
        _mask = lambda t: _re.sub(r"\+?\d{7,}", "<tel>", _re.sub(r"[\w.+-]+@[\w.-]+", "<eposta>", str(t or "")))
        tot = await db.iys_consents.count_documents({})
        rep = await db.iys_consents.count_documents({"reported": True})
        codes, resp = {}, {}
        async for r in db.iys_consents.find({"reported": {"$ne": True}},
                                            {"_id": 0, "report_status_code": 1, "report_response": 1,
                                             "created_at": 1, "channels": 1, "source": 1}).sort("created_at", -1).limit(3000):
            k = str(r.get("report_status_code"))
            codes[k] = codes.get(k, 0) + 1
            rr = _mask(r.get("report_response"))[:220] or "(yanıt yok — hiç denenmemiş)"
            resp[rr] = resp.get(rr, 0) + 1
        last_ok = await db.iys_consents.find_one({"reported": True}, {"_id": 0, "reported_at": 1, "created_at": 1},
                                                 sort=[("reported_at", -1)])
        oldest_pending = await db.iys_consents.find_one({"reported": {"$ne": True}}, {"_id": 0, "created_at": 1},
                                                        sort=[("created_at", 1)])
        return {"config": {"username": bool(cfg.get("username")), "password": bool(cfg.get("password")),
                           "appkey": bool(cfg.get("appkey")),
                           "brand_code": bool(cfg.get("brand_code") or cfg.get("iys_code"))},
                "toplam": tot, "bildirilen": rep, "bekleyen": tot - rep, "http_kodlari": codes,
                "yanitlar": sorted(resp.items(), key=lambda x: -x[1])[:8],
                "son_basarili": last_ok, "en_eski_bekleyen": oldest_pending,
                "gunluk_toplu": await db.settings.find_one({"id": "iys_daily_batch"}, {"_id": 0}),
                "url": os.environ.get("NETGSM_IYS_URL") or "https://api.netgsm.com.tr/iys/add"}
    if mod == "blokaj":
        # Olay döngüsü kilitlenmeleri (son 24 sa): o an çalışan işler/istekler — salt okunur.
        since = (now - _td(hours=24)).isoformat()
        rows = await db.error_logs.find({"kind": "loop_block", "created_at": {"$gte": since}},
                                        {"_id": 0, "created_at": 1, "meta": 1}).sort("created_at", -1).to_list(500)
        jf, rf = {}, {}
        for r in rows:
            m = r.get("meta") or {}
            for j in (m.get("jobs") or []):
                jf[j[0]] = jf.get(j[0], 0) + 1
            for sname in (m.get("syncs") or []):
                jf["sync:" + sname] = jf.get("sync:" + sname, 0) + 1
            for q in (m.get("requests") or [])[:3]:
                rf[q[0]] = rf.get(q[0], 0) + 1
        try:
            from scheduler import JOB_STATS
            slow_jobs = sorted(([k, v] for k, v in JOB_STATS.items()), key=lambda x: -x[1]["max_s"])[:15]
        except Exception:
            slow_jobs = []
        return {"adet": len(rows), "max_lag_ms": max([(r.get("meta") or {}).get("lag_ms", 0) for r in rows] or [0]),
                "is_sikligi": sorted(jf.items(), key=lambda x: -x[1])[:15],
                "istek_sikligi": sorted(rf.items(), key=lambda x: -x[1])[:15],
                "son": rows[:10], "is_sureleri": slow_jobs}
    if mod == "tarama":
        # GENEL SAĞLIK/GÜVENLİK TARAMASI (salt okunur; e-posta/IP MASKELİ).
        import hashlib as _hl
        def _m_ip(ip):
            ip = str(ip or "")
            return (".".join(ip.split(".")[:2]) + ".x.x") if "." in ip else (ip[:6] + "…" if ip else "")
        def _h(x):
            return _hl.sha256(str(x or "").encode()).hexdigest()[:8] if x else ""
        d1 = (now - _td(days=1)).isoformat(); d7 = (now - _td(days=7)).isoformat()
        out = {}
        # 1) BÜYÜK SEPETLER (terk edilmiş sepet takibi)
        big = []
        async for c in db.cart_sessions.find({"$expr": {"$gte": [{"$size": {"$ifNull": ["$items", []]}}, 15]}},
                                             {"_id": 0}).sort("updated_at", -1).limit(200):
            its = c.get("items") or []
            pids = [str(i.get("product_id") or "") for i in its]
            qty = sum(int(i.get("qty") or 1) for i in its if isinstance(i, dict))
            big.append({"sid": _h(c.get("session_id")), "kalem": len(its), "adet": qty,
                        "farkli_urun": len(set(pids)), "bos_urun_id": sum(1 for x in pids if not x),
                        "tutar": round(float(c.get("total") or 0)),
                        "uye": bool(c.get("user_id")), "eposta_var": bool(c.get("email")),
                        "olusturma": str(c.get("created_at") or "")[:16], "guncelleme": str(c.get("updated_at") or "")[:16],
                        "isimler_bos": sum(1 for i in its if not (i.get("name") or "").strip())})
        out["buyuk_sepet"] = {"adet": len(big), "ornek": big[:40]}
        dist = {}
        async for c in db.cart_sessions.aggregate([
                {"$project": {"n": {"$size": {"$ifNull": ["$items", []]}}}},
                {"$bucket": {"groupBy": "$n", "boundaries": [0, 1, 3, 6, 10, 15, 20, 30, 50, 101], "default": "101+",
                             "output": {"c": {"$sum": 1}}}}]):
            dist[str(c["_id"])] = c["c"]
        out["sepet_kalem_dagilimi"] = dist
        out["sepet_toplam"] = await db.cart_sessions.count_documents({})
        # büyük sepetlerde en çok geçen ürünler (id → ad)
        pc = {}
        async for c in db.cart_sessions.find({"$expr": {"$gte": [{"$size": {"$ifNull": ["$items", []]}}, 15]}},
                                             {"_id": 0, "items.product_id": 1}).limit(500):
            for i in c.get("items") or []:
                k = str(i.get("product_id") or "")
                pc[k] = pc.get(k, 0) + 1
        top = sorted(pc.items(), key=lambda x: -x[1])[:10]
        names = {}
        if top:
            async for pr in db.products.find({"id": {"$in": [k for k, _ in top]}}, {"_id": 0, "id": 1, "name": 1}):
                names[pr["id"]] = pr.get("name")
        out["buyuk_sepet_urunleri"] = [[names.get(k, k), n] for k, n in top]
        # büyük sepetten siparişe dönen (üye) var mı
        # 2) HATALAR
        agg = {}
        async for r in db.error_logs.aggregate([{"$match": {"created_at": {"$gte": d1}}},
                                                {"$group": {"_id": {"k": "$kind", "l": "$level"}, "c": {"$sum": 1}}}]):
            agg[f"{r['_id'].get('k')}/{r['_id'].get('l')}"] = r["c"]
        out["hata_24s"] = agg
        top5 = {}
        async for r in db.error_logs.find({"created_at": {"$gte": d1}, "kind": {"$in": ["http_5xx", "exception"]}},
                                          {"_id": 0, "path": 1, "message": 1}).limit(3000):
            k = f"{r.get('path')} | {str(r.get('message') or '')[:120]}"
            top5[k] = top5.get(k, 0) + 1
        out["hata_24s_en_sik"] = sorted(top5.items(), key=lambda x: -x[1])[:15]
        # 3) GÜVENLİK: giriş denemeleri, IP engelleri, uyarılar
        ev = {}
        async for r in db.auth_audit_logs.aggregate([{"$match": {"created_at": {"$gte": d7}}},
                                                     {"$group": {"_id": {"e": "$event", "s": "$success"}, "c": {"$sum": 1}}}]):
            ev[f"{r['_id'].get('e')}/{'ok' if r['_id'].get('s') else 'fail'}"] = r["c"]
        out["auth_7g"] = ev
        ipf = {}
        async for r in db.auth_audit_logs.find({"created_at": {"$gte": d7}, "success": False},
                                               {"_id": 0, "ip": 1, "email": 1, "event": 1}).limit(20000):
            k = _m_ip(r.get("ip"))
            a = ipf.setdefault(k, {"n": 0, "hesap": set()})
            a["n"] += 1
            a["hesap"].add(_h(r.get("email")))
        out["basarisiz_giris_ip_7g"] = sorted(([k, v["n"], len(v["hesap"])] for k, v in ipf.items()), key=lambda x: -x[1])[:15]
        out["ip_engel_aktif"] = await db.ip_blocklist.count_documents({"blocked_until": {"$gte": now.isoformat()}})
        al = {}
        async for r in db.alerts.find({"created_at": {"$gte": d7}}, {"_id": 0, "kind": 1, "level": 1, "title": 1}).limit(2000):
            k = f"{r.get('kind')}/{r.get('level')}: {str(r.get('title') or '')[:80]}"
            al[k] = al.get(k, 0) + 1
        out["uyarilar_7g"] = sorted(al.items(), key=lambda x: -x[1])[:20]
        return out
    if mod == "paylasim":
        # Paylaşılan sepetler (salt okunur): boyut, oluşturma, kaynak; büyük sepet eşleşmesi.
        rows = []
        async for c in db.shared_carts.find({}, {"_id": 0, "id": 1, "items": 1, "created_at": 1, "source": 1,
                                                  "opened_at": 1}).sort("created_at", -1).limit(400):
            its = c.get("items") or []
            rows.append({"id": str(c.get("id"))[:4] + "…", "kalem": len(its), "adet": sum(int(i.get("quantity") or 1) for i in its),
                         "olusturma": str(c.get("created_at") or "")[:16], "kaynak": c.get("source") or "",
                         "_set": sorted({str(i.get("product_id")) for i in its})})
        big = [r for r in rows if r["kalem"] >= 15]
        # büyük sepet oturumlarının ürün kümesi ile eşleşme
        sess = []
        async for c in db.cart_sessions.find({"$expr": {"$gte": [{"$size": {"$ifNull": ["$items", []]}}, 15]}},
                                             {"_id": 0, "items.product_id": 1}).limit(200):
            sess.append(sorted({str(i.get("product_id")) for i in (c.get("items") or [])}))
        for r in big:
            r["ayni_urunlu_oturum"] = sum(1 for sset in sess if sset == r["_set"])
            r["kapsanan_oturum"] = sum(1 for sset in sess if set(r["_set"]) <= set(sset))
        for r in rows:
            r.pop("_set", None)
        return {"toplam": len(rows), "buyuk": big[:30],
                "boyut_dagilimi": {k: sum(1 for r in rows if lo <= r["kalem"] < hi) for k, lo, hi in
                                   (("1", 1, 2), ("2-5", 2, 6), ("6-14", 6, 15), ("15+", 15, 10**6))}}
    if mod == "sepet_mail":
        # Terkedilmiş sepet e-postası: kuru çalıştırma sayımı + son gönderimler (PII yok).
        import abandoned_cart_mail as _acm
        dry = await _acm.run(db, dry_run=True)
        last = await db.abandoned_cart_emails.find({}, {"_id": 0, "status": 1, "items": 1, "provider": 1,
                                                        "created_at": 1, "error": 1}).sort("created_at", -1).to_list(20)
        tracked = await db.cart_sessions.count_documents({"user_id": {"$nin": [None, ""]}, "total": {"$gt": 0}})
        return {"kuru_calistirma": dry, "uye_bagli_sepet": tracked, "son_gonderimler": last}
    return {"detay": "mod=kargo|uyelik|yavas|meta|siparis|iys|blokaj|tarama|paylasim|sepet_mail"}


async def _kupon_teshis(kod: str = "") -> dict:
    """SALT OKUNUR: kupon/kampanya kaydı + ŞU AN geçerli mi (ödeme ile aynı değerlendirme)
    + bu kodla verilen siparişlerin TR gününe göre dağılımı ve son kullanım anı. PII yok."""
    import re as _re
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    kod = (kod or "").strip()
    c = await db.coupons.find_one({"code": {"$regex": f"^{_re.escape(kod)}$", "$options": "i"}}, {"_id": 0})
    if not c:
        return {"bulunamadi": kod}
    alan = {k: c.get(k) for k in ("id", "code", "title", "type", "value", "free_shipping", "auto_apply",
                                  "is_active", "start_at", "end_at", "usage_limit", "redeemed_count",
                                  "min_cart_total", "payment_methods", "created_at", "updated_at")}
    try:
        from routes.coupons import _evaluate_single
        ev = await _evaluate_single(c, 5000.0, [], None, "", "credit_card")
    except TypeError:
        ev = {"not": "imza farklı — değerlendirme atlandı"}
    except Exception as e:
        ev = {"hata": f"{type(e).__name__}: {str(e)[:200]}"}
    gun, son = {}, ""
    async for o in db.orders.find({"coupon_code": {"$regex": f"^{_re.escape(kod)}$", "$options": "i"}},
                                  {"_id": 0, "created_at": 1, "status": 1, "payment_status": 1}):
        ca = str(o.get("created_at") or "")
        try:
            d = (_dt.fromisoformat(ca.replace("Z", "+00:00")) + _td(hours=3)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            d = ca[:16]
        g = d[:10]
        gun[g] = gun.get(g, 0) + 1
        if d > son:
            son = d
    # Otomatik kampanyalar siparişe applied_promotions.coupon_id ile, ödenenler coupon_redemptions'a yazılır.
    def _trg(ca):
        try:
            return (_dt.fromisoformat(str(ca).replace("Z", "+00:00")) + _td(hours=3)).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return str(ca)[:16]
    end = str(c.get("end_at") or "")
    ap_gun, ap_sonra, ap_son = {}, [], ""
    async for o in db.orders.find({"applied_promotions.coupon_id": c.get("id")},
                                  {"_id": 0, "order_number": 1, "created_at": 1, "status": 1, "payment_status": 1}):
        d = _trg(o.get("created_at"))
        ap_gun[d[:10]] = ap_gun.get(d[:10], 0) + 1
        ap_son = max(ap_son, d)
        if end and str(o.get("created_at") or "") > end:
            ap_sonra.append({"no": o.get("order_number"), "tarih_TR": d, "statu": o.get("status"),
                             "odeme": o.get("payment_status")})
    rd_gun, rd_sonra = {}, 0
    async for r in db.coupon_redemptions.find({"coupon_id": c.get("id")}, {"_id": 0, "created_at": 1}):
        d = _trg(r.get("created_at"))
        rd_gun[d[:10]] = rd_gun.get(d[:10], 0) + 1
        if end and str(r.get("created_at") or "") > end:
            rd_sonra += 1
    return {"kupon": alan, "simdi_degerlendirme": ev, "simdi_utc": _dt.now(_tz.utc).isoformat(),
            "siparis_gun_TR": dict(sorted(gun.items())), "son_kullanim_TR": son,
            "otomatik_siparis_gun_TR": dict(sorted(ap_gun.items())), "otomatik_son_TR": ap_son,
            "BITISTEN_SONRA_siparis": ap_sonra[:50], "kullanim_kaydi_gun_TR": dict(sorted(rd_gun.items())),
            "BITISTEN_SONRA_kullanim_kaydi": rd_sonra}


async def _safe_block(coro):
    """Bir teşhis bloğunun hatası TÜM /health yanıtını düşürmesin.

    Teşhis blokları tek bir sözlük içinde yan yana kuruluyor; birinde hata çıkınca
    yanıtın tamamı 500 oluyor ve geri kalan bloklar da okunamıyordu. Salt okuma.
    Ayrıca sonuç JSON'a yazılabilir hâle getirilir (NaN/Infinity temizliği).
    """
    try:
        res = await coro
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}
    try:
        bad: list = []
        res = _json_safe(res, bad)
        if bad and isinstance(res, dict):
            res["bozuk_sayilar"] = {
                "adet": len(bad), "alanlar": bad,
                "not": ("NaN/Infinity JSON'a yazılamaz; bu alanlar None yapıldı. "
                        "Kaynak genellikle sıfıra bölme (boş dönemde ortalama)."),
            }
        return res
    except Exception as _se:
        return {"hata": f"temizleme: {type(_se).__name__}: {str(_se)[:200]}"}


async def _stock_drift_block(limit: int = 50) -> dict:
    """SALT OKUNUR · KATALOG GENELİ: hangi üründe ne kadar HAYALET stok var?

    Hayalet stok = düşüm hareketi HİÇ OLMAYAN bir siparişe yapılmış geri-ekleme.
    (Sipariş stoktan hiç düşmemiş, ama iptal/iade edilince stoğa geri eklenmiş.)

    Yöntem:
      1) Tüm geri-ekleme hareketleri taranır (adet ve bağlı sipariş toplanır)
      2) Bu siparişlerin düşüm hareketi olup olmadığına TEK seferde bakılır
      3) Düşümü olmayanların geri-eklemeleri ürün bazında toplanır

    HİÇBİR YAZMA YAPMAZ. Rakam bir ÖNERİDİR — fiziksel sayımla karşılaştırılmalı,
    otomatik düşülmemelidir.
    """
    try:
        RESTORE = ["order_cancelled", "auto_cancel_expired", "havale_auto_cancel",
                   "return_restock", "order_returned", "manual_increment",
                   "backfill_increment", "order_deleted_restock",
                   "influencer_seeding_restock"]
        DEDUCT = ["order_created", "order_imported", "manual_decrement",
                  "backfill_decrement", "influencer_seeding"]

        rows, oids = [], set()
        async for m in db.stock_movements.find(
                {"type": {"$in": RESTORE}},
                {"_id": 0, "order_id": 1, "type": 1, "items": 1, "moves": 1}):
            oid = str(m.get("order_id") or "")
            for it in ((m.get("items") or []) + (m.get("moves") or [])):
                if not isinstance(it, dict):
                    continue
                d = it.get("delta")
                if d is None:
                    d = it.get("qty")          # eski pazaryeri iade satırları
                if d is None and it.get("old") is not None and it.get("new") is not None:
                    try:
                        d = int(it["new"]) - int(it["old"])
                    except Exception:
                        d = None
                try:
                    d = int(d or 0)
                except Exception:
                    d = 0
                if d <= 0:
                    continue
                key = str(it.get("product_id") or "") or ("bc:" + str(it.get("barcode") or ""))
                if not key or key == "bc:":
                    continue
                rows.append((oid, key, d, str(m.get("type") or "?")))
                if oid:
                    oids.add(oid)

        dusenler = set()
        _ol = list(oids)
        for i in range(0, len(_ol), 4000):
            async for m in db.stock_movements.find(
                    {"order_id": {"$in": _ol[i:i + 4000]}, "type": {"$in": DEDUCT}},
                    {"_id": 0, "order_id": 1}):
                dusenler.add(str(m.get("order_id")))

        per: dict = {}
        toplam_h = toplam_g = 0
        for oid, key, d, tip in rows:
            p = per.setdefault(key, {"hayalet": 0, "gercek": 0, "tipler": {}})
            if oid and oid in dusenler:
                p["gercek"] += d
                toplam_g += d
            else:
                p["hayalet"] += d
                p["tipler"][tip] = p["tipler"].get(tip, 0) + d
                toplam_h += d

        en_kotu = sorted(per.items(), key=lambda kv: -kv[1]["hayalet"])[:max(1, min(limit, 300))]
        _pids = [k for k, _ in en_kotu if not k.startswith("bc:")]
        _bcs = [k[3:] for k, _ in en_kotu if k.startswith("bc:")]
        _info: dict = {}
        async for p in db.products.find(
                {"$or": [{"id": {"$in": _pids}}, {"variants.barcode": {"$in": _bcs}}]},
                {"_id": 0, "id": 1, "name": 1, "stock_code": 1, "stock": 1,
                 "is_active": 1, "variants": 1}):
            _tot = sum(int(v.get("stock") or 0) for v in (p.get("variants") or [])) \
                if p.get("variants") else int(p.get("stock") or 0)
            _rec = {"ad": p.get("name"), "stok_kodu": p.get("stock_code"),
                    "aktif": p.get("is_active"), "canli_stok": _tot}
            _info[str(p.get("id"))] = _rec
            for v in (p.get("variants") or []):
                if v.get("barcode"):
                    _info.setdefault("bc:" + str(v["barcode"]), _rec)

        liste = []
        for k, v in en_kotu:
            if v["hayalet"] <= 0:
                continue
            d = dict(_info.get(k) or {"ad": "(ürün bulunamadı)", "canli_stok": None})
            d.update({"anahtar": k, "hayalet_adet": v["hayalet"],
                      "gercek_iade_adet": v["gercek"], "kaynak_tipler": v["tipler"]})
            if d.get("canli_stok") is not None:
                d["duzeltilmis_tahmin"] = d["canli_stok"] - v["hayalet"]
            liste.append(d)

        return {
            "ozet": {"etkilenen_urun": sum(1 for v in per.values() if v["hayalet"] > 0),
                     "toplam_hayalet_adet": toplam_h,
                     "dusumu_olan_siparise_yapilan_gercek_iade": toplam_g,
                     "taranan_geri_ekleme_satiri": len(rows)},
            "not": ("hayalet_adet = stoktan HİÇ DÜŞMEMİŞ bir siparişe yapılan geri-ekleme. "
                    "duzeltilmis_tahmin bir ÖNERİDİR; fiziksel sayımla doğrulanmadan "
                    "stoktan düşülmemelidir."),
            "en_kotu": liste,
        }
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}


async def _sales_audit_block(start_date: str = "", end_date: str = "",
                             source: str = "") -> dict:
    """Bağımsız satış denetimi (routes.reports.sales_audit_summary). Tarih verilmezse
    içinde bulunulan TÜRKİYE ayının 1'inden bugüne. Hata sağlık ucunu BOZMAZ.

    `source` verilirse (harici kanal/site/harici kanal) denetim o kanala daraltılır —
    "pazaryeri panelindeki rakam bizimkiyle tutuyor mu" sorusu ancak kanal kanal
    ölçülerek cevaplanabilir."""
    try:
        from datetime import datetime as _dt2, timezone as _tz2, timedelta as _td2
        from routes.reports import sales_audit_summary as _sas
        from routes.report_dedup import load_dup_order_numbers as _ldc_sa
        try:
            await _ldc_sa()        # kopya elemesi soğuk süreçte de yüklü olsun
        except Exception:
            pass
        _tr_now = _dt2.now(_tz2.utc) + _td2(hours=3)
        _s = start_date or _tr_now.replace(day=1).date().isoformat()
        _e = end_date or _tr_now.date().isoformat()
        return await _sas(_s, _e, (source or None))
    except Exception as _e:
        return {"hata": f"{type(_e).__name__}: {str(_e)[:300]}"}


@api_router.get("/health")
async def health(diag: str = "", audit_key: str = "",
                 audit_start: str = "", audit_end: str = "", stock_q: str = "",
                 drift: str = "", orders_q: str = "",
                 audit_source: str = "", pusula_q: str = "", iade_list: str = "",
                 rapor_q: str = "", asistan_log: str = "", kupon_q: str = "",
                 destek_q: str = "", destek_email: str = ""):
    # Deploy teşhisi: hangi commit çalışıyor (Railway RAILWAY_GIT_COMMIT_SHA sağlar).
    _sha = (os.environ.get("RAILWAY_GIT_COMMIT_SHA") or os.environ.get("GIT_SHA") or "")[:12]
    # HAFİF MOD (varsayılan): yalnız sürüm + tek bir hızlı DB ping (5 sn zaman aşımı). Ağır teşhis
    # blokları (log aggregation'ları, koleksiyon taramaları) YALNIZ ?diag=1 ile çalışır — sağlık
    # ucu izleme araçlarınca sık çağrıldığından veritabanını yormamalı.
    if not diag:
        import asyncio as _aio_h
        _db_ok, _db_err = True, ""
        try:
            await _aio_h.wait_for(db.command("ping"), timeout=5)
        except Exception as _pe:
            _db_ok, _db_err = False, str(_pe)[:120]
        return {"status": "healthy" if _db_ok else "degraded", "version": _sha, "db": "ok" if _db_ok else f"hata: {_db_err}"}
    # Destek teşhisleri YALNIZ SUPPORT_AUDIT_KEY tanımlıysa açılır (beyaz etiket: koda gömülü anahtar YOK).
    if not SUPPORT_AUDIT_KEY:
        return {"status": "healthy", "version": _sha or None,
                "diag": "kapalı (SUPPORT_AUDIT_KEY tanımlı değil)"}
    _audit_ok = _audit_key_ok(audit_key)
    # Havale 72s taraması sağlığı (PII yok: yalnız zaman/sayaç/hata) — teşhis.
    _hv = {}
    try:
        _hv = await db.settings.find_one({"id": "havale_sweep_health"}, {"_id": 0, "id": 0}) or {}
    except Exception as _e:
        _hv = {"error": f"okunamadı: {str(_e)[:80]}"}
    # Zamanlayıcı canlı mı? (job listesi — yalnız id'ler)
    _jobs = None
    try:
        from scheduler import _scheduler as _sched
        _jobs = sorted(j.id for j in _sched.get_jobs())[:60] if _sched else []
    except Exception as _e:
        _jobs = [f"okunamadı: {str(_e)[:60]}"]
    _rp = None   # iade sondası KALDIRILDI (indeks-siz tarama)
    # TEŞHİS (yalnız ?diag=1, DB'ye DOKUNMAZ): kargo etiketi barkodu sunucuda üretilebiliyor mu?
    # python-barcode/Pillow eksikse etiket web-font yedeğine düşer → kurye okuyamayabilir.
    _op = None   # tekil sipariş sondası kaldırıldı (indekssiz telefon taraması)
    _lbc = {}
    try:
        from routes.orders import _render_label_barcode_png_b64 as _lb
        for _c in ("TEST000001", "INF00000001"):
            _png = _lb(_c)
            _lbc[_c] = {"ok": bool(_png), "png_bytes": (len(_png) * 3 // 4) if _png else 0}
    except Exception as _e:
        _lbc = {"error": str(_e)[:120]}
    _inst = None   # süreç-etiketi teşhisi KALDIRILDI: indeks-siz log aggregation'ları DB'yi kilitliyordu
    return {"status": "healthy", "version": _sha or None, "havale_sweep": _hv or None,
            "scheduler_jobs": _jobs,
            "instances": _inst,
            "otp_mail_fix": (await db.settings.find_one({"id": "migrations.otp_email_tpl_v2"}, {"_id": 0, "id": 0})),
            "vade_refit": (await db.settings.find_one({"id": "migrations.vade_refit_v1"}, {"_id": 0, "id": 0})),
            "label_barcode": _lbc,
            "unpaid_card_audit": (await db.settings.find_one({"id": "migrations.audit_unpaid_card_v2"}, {"_id": 0, "id": 0})),
            "member_discount_audit": (await db.settings.find_one({"id": "migrations.audit_member_discount_v1"}, {"_id": 0, "id": 0})),
            "threeds_audit": ((await db.settings.find_one({"id": "migrations.audit_3ds_dropoff_v1"}, {"_id": 0, "id": 0}))
                              if _audit_ok else {"detay": "audit_key gerekli"}),
            "cancelreq_audit": (await db.settings.find_one({"id": "migrations.audit_cancelreq_vis_v1"}, {"_id": 0, "id": 0})),
            "report_perf": (lambda: __import__("routes.reports", fromlist=["REPORT_PERF"]).REPORT_PERF[-10:])(),
            # BAĞIMSIZ satış denetimi — panelin rakamına güvenilmediğinde kıyas için.
            # Ham db.orders üzerinden ayrı aritmetik; panelin sonucu da yanında döner.
            # Ticari veri taşıdığı için audit_key ZORUNLU. Salt-okunur.
            "sales_audit": (await _safe_block(_sales_audit_block(audit_start, audit_end,
                                                                 audit_source))
                            if (_audit_ok and not iade_list and not rapor_q
                                and not kupon_q and not destek_q)
                            else {"detay": "audit_key gerekli"}),
            # SALT OKUNUR stok izi: "bu ürünün stoğu neden bu değerde?" — hareket
            # defteri + canlı stok karşılaştırması. audit_key ZORUNLU, yazma YOK.
            "stock_trace": ((await _stock_trace_block(stock_q))
                            if (_audit_ok and stock_q)
                            else {"detay": "audit_key + stock_q gerekli"}),
            # KATALOG GENELİ hayalet stok raporu (salt okunur, öneri niteliğinde).
            # Ağır olduğu için yalnız &drift=1 ile çalışır.
            # Tek seferlik göçlerin çalışıp çalışmadığı (görünürlük; salt okuma).
            "gocler": {d.get("id"): {k: v for k, v in d.items() if k != "id"}
                       for d in [await db.settings.find_one({"id": _i}, {"_id": 0})
                                 for _i in ("ty_date_utc_fix_v1",
                                            "restock_delta_backfill_v1",
                                            "cancelled_at_backfill_v1",
                                            "consignment_removed_v1")]
                       if d},
            # Sipariş-sipariş eşleştirme (salt okuma).
            "siparis_eslestir": ((await _order_lookup(orders_q))
                                 if (_audit_ok and orders_q)
                                 else {"detay": "audit_key + orders_q gerekli"}),
            # Dönemin iade belgeleri + talepleri (Excel ile iade iade kıyas; salt okuma).
            "iade_listesi": ((await _safe_block(_iade_listesi(audit_start, audit_end)))
                             if (_audit_ok and iade_list)
                             else {"detay": "audit_key + iade_list=1 gerekli"}),
            # Raporlar sayfasının gösterdiği rakamlar, aynı uçlardan (kıyas; salt okuma).
            "rapor_sorgu": ((await _safe_block(_rapor_sorgu(rapor_q, audit_start, audit_end,
                                                            audit_source)))
                            if (_audit_ok and rapor_q)
                            else {"detay": "audit_key + rapor_q gerekli"}),
            "destek": ((await _safe_block(_destek_teshis(destek_q, destek_email)))
                       if (_audit_ok and destek_q)
                       else {"detay": "audit_key + destek_q=kargo|uyelik|yavas gerekli"}),
            "kupon": ((await _safe_block(_kupon_teshis(kupon_q)))
                      if (_audit_ok and kupon_q)
                      else {"detay": "audit_key + kupon_q=<KOD> gerekli"}),
            "asistan_log": ((await _safe_block(_asistan_log_block()))
                            if (_audit_ok and asistan_log)
                            else {"detay": "audit_key + asistan_log=1 gerekli"}),
            # Bir siparişe kesilmiş gider pusulalarının TAMAMI (mükerrer teşhisi).
            "pusula_dokum": ((await _pusula_lookup(pusula_q))
                             if (_audit_ok and pusula_q)
                             else {"detay": "audit_key + pusula_q gerekli"}),
            # Tutarı GEÇERSİZ SAYI olan siparişler (bir kayıt tüm ayı zehirliyordu).
            "bozuk_tutar": (await _safe_block(_bozuk_tutar_block())
                            if _audit_ok
                            else {"detay": "audit_key gerekli"}),
            "stock_drift": ((await _stock_drift_block())
                            if (_audit_ok and drift)
                            else {"detay": "audit_key + drift=1 gerekli"}),
            "subset_refund_money": ((await db.settings.find_one({"id": "migrations.audit_subset_refund_v2"}, {"_id": 0, "id": 0}))
                                    if _audit_ok else {"detay": "audit_key gerekli"}),
            "subset_refund_audit": ((await db.settings.find_one({"id": "migrations.audit_subset_refund_v1"}, {"_id": 0, "id": 0}))
                                    if _audit_ok else
                                    {"detay": "audit_key gerekli",
                                     "supheli_adet": ((await db.settings.find_one({"id": "migrations.audit_subset_refund_v1"}, {"_id": 0, "supheli_adet": 1, "toplam_fazla_tl": 1})) or {})}),
            "return_probe": _rp}

# Include API router
app.include_router(api_router)

# SEO: /sitemap.xml ve /robots.txt — KÖK seviye (api_router'a DEĞİL, /api prefix'siz)
app.include_router(seo_router)

# Static files (if needed)
static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
