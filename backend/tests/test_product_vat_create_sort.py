"""Regresyon: KDV varsayılanı/doğrulaması, yeni üründe form alanlarının korunması,
vitrin fiyat sıralaması (efektif fiyat) ve boş havale indirimi ayarı."""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Req:
    headers = {}
    client = None
    cookies = {}
    query_params = {}
    url = type("U", (), {"path": "/api/products"})()


_ADMIN = {"email": "a@b", "role": "admin"}


@pytest.fixture
def P(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.products as products
    import routes.deps as deps
    tdb = AsyncIOMotorClient(path=str(tmp_path / "p.db"))["test"]
    monkeypatch.setattr(products, "db", tdb)
    monkeypatch.setattr(deps, "db", tdb)
    return products, tdb


def _create(products, data):
    return products.create_product(data, _Req(), _ADMIN)


def test_new_product_default_vat_is_20_without_settings(P):
    products, tdb = P

    async def run():
        r = await _create(products, {"name": "X", "price": 100, "stock": 5})
        return await tdb.products.find_one({"id": r["id"]}, {"_id": 0})

    assert asyncio.run(run())["vat_rate"] == 20


def test_new_product_uses_settings_default_vat(P):
    products, tdb = P

    async def run():
        await tdb.settings.insert_one({"id": "main", "default_vat_rate": 10})
        r = await _create(products, {"name": "X", "price": 100, "stock": 5})
        return await tdb.products.find_one({"id": r["id"]}, {"_id": 0})

    assert asyncio.run(run())["vat_rate"] == 10


@pytest.mark.parametrize("bad", ["abc", -5, 250, ""])
def test_vat_validation_rejects_bad_values(P, bad):
    products, tdb = P

    async def run():
        await tdb.products.insert_one({"id": "2000", "name": "B", "slug": "b-2000", "price": 100.0,
                                       "stock": 1, "variants": [], "vat_rate": 20, "urun_karti_id": "2000"})
        with pytest.raises(HTTPException) as e:
            await products.update_product("2000", {"vat_rate": bad}, _Req(), _ADMIN)
        assert e.value.status_code == 400
        with pytest.raises(HTTPException):
            await _create(products, {"name": "Y", "price": 1, "vat_rate": bad})
        with pytest.raises(HTTPException):
            await products.bulk_update_vat({"vat_rate": bad}, _ADMIN)
        return await tdb.products.find_one({"id": "2000"}, {"_id": 0})

    assert asyncio.run(run())["vat_rate"] == 20


def test_bulk_vat_skips_trash_and_persists_default(P):
    products, tdb = P

    async def run():
        await tdb.settings.insert_one({"id": "main", "default_vat_rate": 10})
        await tdb.products.insert_one({"id": "1", "vat_rate": 10})
        await tdb.products.insert_one({"id": "2", "vat_rate": 10, "is_deleted": True})
        await products.bulk_update_vat({"vat_rate": "20"}, _ADMIN)
        a = await tdb.products.find_one({"id": "1"}, {"_id": 0})
        b = await tdb.products.find_one({"id": "2"}, {"_id": 0})
        s = await tdb.settings.find_one({"id": "main"}, {"_id": 0})
        return a, b, s

    a, b, s = asyncio.run(run())
    assert a["vat_rate"] == 20
    assert b["vat_rate"] == 10
    assert s["default_vat_rate"] == 20


def test_create_keeps_form_fields(P):
    products, tdb = P

    async def run():
        r = await _create(products, {
            "name": "E2E", "price": 1234.5, "stock": 7, "variants": [],
            "meta_title": "E2E Meta Başlık", "meta_description": "açıklama",
            "member_price_1": "1200", "min_order_qty": 2, "max_order_qty": 5,
            "estimated_delivery": "2-3", "market_price": 1500, "vat_included": True,
            "keywords": "pense", "unit": "Adet", "gtip_code": "8203", "max_installment": 6,
        })
        return await tdb.products.find_one({"id": r["id"]}, {"_id": 0})

    p = asyncio.run(run())
    assert p["meta_title"] == "E2E Meta Başlık"
    assert p["meta_description"] == "açıklama"
    assert p["member_price_1"] == 1200.0
    assert p["min_order_qty"] == 2 and p["max_order_qty"] == 5
    assert p["max_installment"] == 6
    assert p["market_price"] == 1500.0
    assert p["vat_included"] is True
    assert (p["keywords"], p["unit"], p["gtip_code"], p["estimated_delivery"]) == ("pense", "Adet", "8203", "2-3")


def test_create_rejects_bad_numeric_form_field(P):
    products, _ = P
    with pytest.raises(HTTPException):
        asyncio.run(_create(products, {"name": "X", "price": 1, "member_price_1": "abc"}))


def test_eff_price_sort_stages(P):
    """Vitrin fiyat sıralaması indirimli satış fiyatını dikkate alır."""
    products, tdb = P

    async def run():
        docs = [
            {"id": "a", "name": "Allen", "price": 462.0, "sale_price": 429},
            {"id": "t", "name": "Torx", "price": 462.0, "sale_price": 385.0},
            {"id": "w", "name": "Wossen", "price": 847.87, "sale_price": None},
            {"id": "l", "name": "Lokma", "price": 869.0, "sale_price": 715.0},
            {"id": "x", "name": "Yuksek", "price": 300.0, "sale_price": 900.0},  # geçersiz indirim
            {"id": "z", "name": "Bozuk", "price": 500.0, "sale_price": "abc"},
        ]
        for d in docs:
            await tdb.products.insert_one(d)
        pipe = [*products._EFF_PRICE_STAGES, {"$sort": {"_eff_price": 1, "_id": 1}},
                {"$project": {"_id": 0, "id": 1}}]
        return [d["id"] for d in await tdb.products.aggregate(pipe).to_list(100)]

    assert asyncio.run(run()) == ["x", "t", "a", "z", "l", "w"]


def test_settings_empty_bank_discount_normalized(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.settings as settings_mod
    tdb = AsyncIOMotorClient(path=str(tmp_path / "s.db"))["test"]
    monkeypatch.setattr(settings_mod, "db", tdb)

    data = {"bank_transfer_discount_pct": "", "edu_discount_pct": None}
    settings_mod._normalize_pct_settings(data)
    assert data == {"bank_transfer_discount_pct": 5, "edu_discount_pct": 5}
    ok = {"bank_transfer_discount_pct": "7,5"}
    settings_mod._normalize_pct_settings(ok)
    assert ok["bank_transfer_discount_pct"] == 7.5
    for bad in ("abc", -1, 95):
        with pytest.raises(HTTPException):
            settings_mod._normalize_pct_settings({"bank_transfer_discount_pct": bad})

    # Eski sürümün kaydettiği "" okuma sırasında onarılır (kasa ve sipariş aynı değeri görür).
    async def run():
        await tdb.settings.insert_one({"id": "main", "cod_default_applied": True,
                                       "bank_transfer_discount_pct": ""})
        try:
            await settings_mod.get_settings()
        except Exception:
            pass  # tenant_config/kargo çözümleyicileri bu testin konusu değil
        return await tdb.settings.find_one({"id": "main"}, {"_id": 0})

    assert asyncio.run(run())["bank_transfer_discount_pct"] == 5
