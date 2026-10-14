"""Panelde ürün kaydetme stoğu sıfırlamamalı (varyantsız ürün variants=[] gönderir)."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Req:
    headers = {}
    client = None
    url = type("U", (), {"path": "/api/products/x"})()


@pytest.fixture
def P(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.products as products
    tdb = AsyncIOMotorClient(path=str(tmp_path / "p.db"))["test"]
    monkeypatch.setattr(products, "db", tdb)
    return products, tdb


def test_simple_product_save_keeps_stock(P):
    products, tdb = P

    async def run():
        await tdb.products.insert_one({"id": "2000", "name": "Basit", "slug": "basit-2000", "price": 100.0,
                                       "stock": 7, "variants": [], "brand": "", "is_active": True,
                                       "urun_karti_id": "2000"})
        doc = await tdb.products.find_one({"id": "2000"}, {"_id": 0})
        doc["description"] = "güncellendi"
        await products.update_product("2000", doc, _Req(), {"email": "a@b", "role": "admin"})
        return await tdb.products.find_one({"id": "2000"}, {"_id": 0})

    out = asyncio.run(run())
    assert out["stock"] == 7
    assert out["brand"] == ""


def test_variant_product_save_keeps_stock(P):
    products, tdb = P

    async def run():
        vs = [{"id": str(13 + i), "urun_id": str(13 + i), "size": f"{i}", "stock": 6,
               "barcode": f"868385100045{i}"} for i in range(3)]
        await tdb.products.insert_one({"id": "1685", "name": "V", "slug": "v-1685", "price": 500.0, "stock": 18,
                                       "variants": vs, "is_active": True, "urun_karti_id": "1685"})
        doc = await tdb.products.find_one({"id": "1685"}, {"_id": 0})
        doc["variants"] = [{**v, "_stock0": v["stock"]} for v in doc["variants"]]
        await products.update_product("1685", doc, _Req(), {"email": "a@b", "role": "admin"})
        return await tdb.products.find_one({"id": "1685"}, {"_id": 0})

    out = asyncio.run(run())
    assert out["stock"] == 18
    assert [v["stock"] for v in out["variants"]] == [6, 6, 6]
