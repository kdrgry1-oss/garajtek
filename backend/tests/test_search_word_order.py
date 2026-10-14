"""Regresyon: kelimeleri karışık sırayla yazılan aramalar da sonuç döndürmeli."""
import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _Req:
    def __init__(self, auth=""):
        self.headers = {"authorization": auth} if auth else {}
    client = None
    cookies = {}
    query_params = {}
    url = type("U", (), {"path": "/api/products"})()
    method = "GET"


def run(c):
    return asyncio.run(c)


@pytest.fixture
def E(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.products as products
    import routes.deps as deps
    tdb = AsyncIOMotorClient(path=str(tmp_path / "sw.db"))["test"]
    for m in (products, deps):
        monkeypatch.setattr(m, "db", tdb)
    products.invalidate_members_only_cache()

    async def ins():
        for d in [
            {"id": "a", "name": "Çift Kolonlu Lift 4 Ton", "brand": "Usta", "price": 10, "stock": 5,
             "is_active": True, "images": ["x.jpg"], "created_at": "1"},
            {"id": "b", "name": "Makaslı Lift 3 Ton", "category_name": "Lift", "price": 20, "stock": 5,
             "is_active": True, "images": ["x.jpg"], "created_at": "2"},
            {"id": "c", "name": "Hidrolik Kriko", "brand": "Usta", "price": 30, "stock": 5,
             "is_active": True, "images": ["x.jpg"], "created_at": "3"},
        ]:
            await tdb.products.insert_one(dict(d))
    run(ins())
    yield products, tdb
    products.invalidate_members_only_cache()


def _ids(products, term):
    r = run(products.get_products(_Req(), page=1, limit=20, search=term))
    return [p["id"] for p in r["products"]]


def test_reordered_words_match(E):
    products, _ = E
    assert _ids(products, "Lift Çift Kolonlu") == ["a"]
    assert _ids(products, "4 ton lift kolonlu") == ["a"]
    assert _ids(products, "lift makasli") == ["b"]          # Türkçe harf duyarsız + ters sıra


def test_words_across_fields(E):
    products, _ = E
    assert _ids(products, "kriko usta") == ["c"]             # isim + marka


def test_all_words_required(E):
    products, _ = E
    assert _ids(products, "lift kriko") == []                # her kelime aynı üründe geçmeli


def test_phrase_ranked_first(E):
    products, _ = E
    # "lift" her iki liftte de geçer; "makaslı lift" ifadesi isimde birebir olan önce gelir
    assert _ids(products, "makaslı lift")[0] == "b"
    assert set(_ids(products, "ton lift")) == {"a", "b"}
