"""
legacy_migrations.py — eski veri alan adlarını güncel adlara taşıyan tek seferlik işler.

Kural: veri SİLİNMEZ; değerler yeni alana kopyalanır, eski anahtar kaldırılır. Her iş
settings'te bayrakla korunur ve açılışta arka planda bir kez çalışır.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Ürün ek katalog alanlarının ESKİ anahtarı (yalnız veri taşıma için burada geçer).
_OLD_CATALOG_KEY = "ticimax_fields"
_NEW_CATALOG_KEY = "catalog_fields"
_FLAG = "migrations.catalog_fields_v1"


async def migrate_catalog_fields_once(db) -> dict:
    """products.<eski anahtar> → products.catalog_fields (mevcut catalog_fields değerleri
    önceliklidir). İdempotent; bayrak varsa hiçbir şey yapmaz."""
    try:
        if await db.settings.find_one({"id": _FLAG, "done": True}):
            return {"skipped": True}
        moved = 0
        async for p in db.products.find({_OLD_CATALOG_KEY: {"$exists": True}},
                                        {"_id": 0, "id": 1, _OLD_CATALOG_KEY: 1, _NEW_CATALOG_KEY: 1}):
            old = p.get(_OLD_CATALOG_KEY) if isinstance(p.get(_OLD_CATALOG_KEY), dict) else {}
            new = p.get(_NEW_CATALOG_KEY) if isinstance(p.get(_NEW_CATALOG_KEY), dict) else {}
            await db.products.update_one(
                {"id": p.get("id")},
                {"$set": {_NEW_CATALOG_KEY: {**old, **new}}, "$unset": {_OLD_CATALOG_KEY: ""}})
            moved += 1
        await db.settings.update_one(
            {"id": _FLAG},
            {"$set": {"id": _FLAG, "done": True, "moved": moved,
                      "at": datetime.now(timezone.utc).isoformat()}},
            upsert=True)
        if moved:
            logger.warning(f"[migrasyon] ek katalog alanları taşındı: {moved} ürün")
        return {"moved": moved}
    except Exception as e:  # açılışı asla düşürmez
        logger.error(f"[migrasyon] katalog alanları taşınamadı: {e}")
        return {"error": str(e)}
