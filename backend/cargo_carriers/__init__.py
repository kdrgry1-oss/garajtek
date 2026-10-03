"""Çoklu kargo firması (taşıyıcı) altyapısı: Aras Kargo, PTT Kargo.

Bkz. registry.py (arayüz + kayıt defteri), service.py (sipariş akışı), docs/KARGO.md.
"""
from .registry import (  # noqa: F401
    CARRIERS, get_carrier, normalize_code, resolve_default_code, load_carrier_config,
    get_carrier_settings, CARRIER_SETTINGS_ID,
)
