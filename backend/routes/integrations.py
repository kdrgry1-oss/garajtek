"""
Integration routes - ana toplayıcı modül.

Pazaryeri (Trendyol/Hepsiburada/Temu/Amazon) ve Ticimax aktarım uçları kaldırıldı.
Kalan genel uçlar integrations_common.py'dedir; bu modül yalnız onları toplar ve
geriye dönük uyumluluk için ortak yardımcıları yeniden dışa aktarır.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Integrations"])

from .integrations_common import router as _common_router  # noqa: E402
router.include_router(_common_router)

# Geriye dönük uyumluluk: 'from routes.integrations import X' kullanan modüller için.
from .integrations_common import (  # noqa: E402,F401
    log_integration_event,
    get_integration_logs,
    ALLOWED_MARKETPLACES,
    get_marketplace_settings,
    save_marketplace_settings,
    get_marketplace_status,
    test_marketplace_connection,
)
