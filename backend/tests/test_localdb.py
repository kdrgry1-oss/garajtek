"""Unit tests for backend/localdb — the embedded, Motor-compatible SQLite document store."""
import asyncio
import datetime
import os
import sqlite3
import sys

import pytest

pytest.importorskip("mongomock")
pytest.importorskip("pymongo")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import DeleteOne, InsertOne, ReplaceOne, ReturnDocument, UpdateMany, UpdateOne  # noqa: E402
from pymongo.errors import BulkWriteError, DuplicateKeyError  # noqa: E402

from localdb import AsyncIOMotorClient  # noqa: E402
from localdb.backup import backup as do_backup  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def dbpath(tmp_path):
    return str(tmp_path / "store.db")


def fresh(dbpath):
    """A brand-new client/engine reading the file from disk (simulates a process restart)."""
    return AsyncIOMotorClient(path=dbpath)["shop"]


def close(db):
    db.client.close()


# ----------------------------------------------------------------------------- CRUD
def test_crud_and_insert_sets_id(dbpath):
    async def go():
        db = fresh(dbpath)
        doc = {"id": "p1", "name": "Gömlek", "price": 10.5}
        res = await db.products.insert_one(doc)
        assert "_id" in doc and doc["_id"] == res.inserted_id
        many = await db.products.insert_many([{"id": f"p{i}", "price": i} for i in range(2, 6)])
        assert len(many.inserted_ids) == 4
        assert (await db.products.find_one({"id": "p1"}, {"_id": 0})) == \
            {"id": "p1", "name": "Gömlek", "price": 10.5}
        assert await db.products.find_one({"id": "nope"}) is None
        r = await db.products.delete_one({"id": "p2"})
        assert r.deleted_count == 1
        r = await db.products.delete_many({"price": {"$gte": 4, "$lt": 10}})
        assert r.deleted_count == 2
        assert await db.products.count_documents({}) == 2
        assert await db.products.estimated_document_count() == 2
        # mutating a returned document must not change the stored one
        got = await db.products.find_one({"id": "p1"})
        got["name"] = "changed"
        assert (await db.products.find_one({"id": "p1"}))["name"] == "Gömlek"
        close(db)
    run(go())


def test_update_operators_and_upsert(dbpath):
    async def go():
        db = fresh(dbpath)
        await db.c.insert_one({"id": "1", "n": 1, "tags": ["a"], "items": [{"k": 1}, {"k": 2}],
                               "gone": True})
        r = await db.c.update_one({"id": "1"}, {
            "$set": {"name": "x", "nested.v": 3}, "$inc": {"n": 2}, "$push": {"tags": "b"},
            "$addToSet": {"tags": "a"}, "$pull": {"items": {"k": 2}}, "$unset": {"gone": ""}})
        assert (r.matched_count, r.modified_count) == (1, 1)
        doc = await db.c.find_one({"id": "1"}, {"_id": 0})
        assert doc == {"id": "1", "n": 3, "tags": ["a", "b"], "items": [{"k": 1}],
                       "name": "x", "nested": {"v": 3}}
        # no-op update: matched but not modified
        r = await db.c.update_one({"id": "1"}, {"$set": {"n": 3}})
        assert (r.matched_count, r.modified_count) == (1, 0)
        # upsert with $setOnInsert
        r = await db.c.update_one({"id": "2"}, {"$set": {"a": 1}, "$setOnInsert": {"created": 1}},
                                  upsert=True)
        assert r.upserted_id is not None and r.matched_count == 0
        r = await db.c.update_one({"id": "2"}, {"$set": {"a": 2}, "$setOnInsert": {"created": 9}},
                                  upsert=True)
        assert r.upserted_id is None
        assert (await db.c.find_one({"id": "2"}, {"_id": 0})) == {"id": "2", "a": 2, "created": 1}
        r = await db.c.update_many({}, {"$inc": {"hits": 1}})
        assert (r.matched_count, r.modified_count) == (2, 2)
        # positional + array filters + all-positional
        await db.p.insert_one({"id": "p", "variants": [{"b": "x", "stock": -1}, {"b": "y", "stock": 4}]})
        await db.p.update_one({"id": "p", "variants.b": "y"}, {"$inc": {"variants.$.stock": -1}})
        await db.p.update_many({}, {"$set": {"variants.$[v].stock": 0}},
                               array_filters=[{"v.stock": {"$lt": 0}}])
        await db.p.update_one({"id": "p"}, {"$set": {"variants.$[].seen": True}})
        p = await db.p.find_one({"id": "p"}, {"_id": 0})
        assert p["variants"] == [{"b": "x", "stock": 0, "seen": True},
                                 {"b": "y", "stock": 3, "seen": True}]
        # pipeline-style update
        await db.p.update_one({"id": "p"}, [{"$set": {"stock": {"$sum": {"$map": {
            "input": "$variants", "as": "v", "in": "$$v.stock"}}}}}])
        assert (await db.p.find_one({"id": "p"}))["stock"] == 3
        r = await db.p.replace_one({"id": "p"}, {"id": "p", "replaced": True})
        assert r.modified_count == 1
        assert (await db.p.find_one({"id": "p"}, {"_id": 0})) == {"id": "p", "replaced": True}
        close(db)
    run(go())


def test_unique_index_duplicate_key(dbpath):
    async def go():
        db = fresh(dbpath)
        await db.users.create_index("email", unique=True)
        await db.users.insert_one({"email": "a@x.com"})
        with pytest.raises(DuplicateKeyError):
            await db.users.insert_one({"email": "a@x.com"})
        await db.users.insert_one({"email": "b@x.com"})
        with pytest.raises(DuplicateKeyError):
            await db.users.update_one({"email": "b@x.com"}, {"$set": {"email": "a@x.com"}})
        assert await db.users.count_documents({"email": "a@x.com"}) == 1
        # partial unique index: only string keys participate
        await db.orders.create_index("k", unique=True,
                                     partialFilterExpression={"k": {"$type": "string"}})
        await db.orders.insert_one({"k": None})
        await db.orders.insert_one({"k": None})
        await db.orders.insert_one({"k": "abc"})
        with pytest.raises(DuplicateKeyError):
            await db.orders.insert_one({"k": "abc"})
        # duplicate _id on an unloaded (append-only fast path) collection
        await db.logs.insert_one({"_id": 1})
        with pytest.raises(DuplicateKeyError):
            await db.logs.insert_one({"_id": 1})
        close(db)
        # unique index survives restart
        db = fresh(dbpath)
        with pytest.raises(DuplicateKeyError):
            await db.users.insert_one({"email": "b@x.com"})
        info = await db.users.index_information()
        assert info["email_1"]["unique"] is True
        # re-creating the identical index at boot is a no-op
        assert await db.users.create_index("email", unique=True) == "email_1"
        close(db)
    run(go())


def test_find_one_and_update_variants(dbpath):
    async def go():
        db = fresh(dbpath)
        await db.counters.insert_many([{"_id": "a", "seq": 1, "p": 2}, {"_id": "b", "seq": 5, "p": 1}])
        after = await db.counters.find_one_and_update(
            {}, {"$inc": {"seq": 1}}, sort=[("p", 1)], projection={"_id": 0, "seq": 1},
            return_document=ReturnDocument.AFTER)
        assert after == {"seq": 6}  # sorted target "b", even with _id projected out
        before = await db.counters.find_one_and_update({"_id": "a"}, {"$inc": {"seq": 1}})
        assert before["seq"] == 1
        up = await db.counters.find_one_and_update(
            {"_id": "new"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
        assert up == {"_id": "new", "seq": 1}
        assert await db.counters.find_one_and_update({"_id": "zz"}, {"$set": {"a": 1}}) is None
        rep = await db.counters.find_one_and_replace({"_id": "a"}, {"seq": 100},
                                                     return_document=ReturnDocument.AFTER)
        assert rep == {"_id": "a", "seq": 100}
        gone = await db.counters.find_one_and_delete({"_id": "b"})
        assert gone["seq"] == 6
        assert await db.counters.count_documents({}) == 2
        close(db)
    run(go())


def test_bulk_write(dbpath):
    async def go():
        db = fresh(dbpath)
        await db.s.insert_many([{"id": i, "v": 0} for i in range(3)])
        res = await db.s.bulk_write([
            UpdateOne({"id": 0}, {"$set": {"v": 1}}),
            UpdateOne({"id": 99}, {"$set": {"v": 9}}, upsert=True),
            UpdateMany({"id": {"$in": [1, 2]}}, {"$inc": {"v": 5}}),
            InsertOne({"id": 7}),
            ReplaceOne({"id": 2}, {"id": 2, "r": True}),
            DeleteOne({"id": 1}),
        ], ordered=False)
        assert res.matched_count == 4 and res.modified_count == 4
        assert res.upserted_count == 1 and res.inserted_count == 1 and res.deleted_count == 1
        assert sorted(await db.s.distinct("id")) == [0, 2, 7, 99]
        await db.s.create_index("id", unique=True)
        with pytest.raises(BulkWriteError) as ei:
            await db.s.bulk_write([InsertOne({"id": 0}), UpdateOne({"id": 2}, {"$set": {"x": 1}})])
        assert ei.value.details["writeErrors"][0]["index"] == 0
        assert (await db.s.find_one({"id": 2})).get("x") is None  # ordered: stopped at error
        close(db)
    run(go())


def test_cursor_sort_skip_limit_projection(dbpath):
    async def go():
        db = fresh(dbpath)
        await db.p.insert_many([{"i": i, "g": i % 3, "name": f"n{i}", "x": {"y": i}}
                                for i in range(10)])
        rows = await db.p.find({"g": {"$ne": 0}}, {"_id": 0, "i": 1}).sort("i", -1) \
            .skip(1).limit(3).to_list(None)
        assert rows == [{"i": 7}, {"i": 5}, {"i": 4}]
        rows = await db.p.find({}, {"x.y": 1, "_id": 0}, sort=[("g", 1), ("i", -1)], limit=2) \
            .to_list(length=10)
        assert rows == [{"x": {"y": 9}}, {"x": {"y": 6}}]
        rows = await db.p.find({}).sort([("i", 1)]).to_list(4)
        assert [r["i"] for r in rows] == [0, 1, 2, 3]
        out = []
        async for d in db.p.find({"name": {"$regex": "^N[12]$", "$options": "i"}}).sort("i", 1):
            out.append(d["i"])
        assert out == [1, 2]
        assert await db.p.count_documents({"g": 1}) == 3
        assert await db.p.count_documents({"g": 1}, limit=2) == 2
        assert sorted(await db.p.distinct("g")) == [0, 1, 2]
        assert sorted(await db.p.distinct("i", {"g": 2})) == [2, 5, 8]
        c = db.p.find({}, batch_size=2).sort("i", 1)
        assert (await c.to_list(2))[1]["i"] == 1
        assert (await c.to_list(2))[0]["i"] == 2  # continues where it left off
        close(db)
    run(go())


def test_aggregate(dbpath):
    async def go():
        db = fresh(dbpath)
        await db.products.insert_many([{"id": "a", "cat": "x", "cost": 2},
                                       {"id": "b", "cat": "y", "cost": 3}])
        await db.orders.insert_many([
            {"n": 1, "status": "paid", "items": [{"pid": "a", "q": 2}, {"pid": "b", "q": 1}],
             "total": 10.0, "created_at": datetime.datetime(2026, 1, 5, 10)},
            {"n": 2, "status": "paid", "items": [{"pid": "a", "q": 1}], "total": 4.0,
             "created_at": datetime.datetime(2026, 1, 6, 23, 30)},
            {"n": 3, "status": "cancelled", "items": [{"pid": "b", "q": 5}], "total": 50.0,
             "created_at": datetime.datetime(2026, 1, 6)},
        ])
        rows = await db.orders.aggregate([
            {"$match": {"status": "paid"}},
            {"$unwind": "$items"},
            {"$lookup": {"from": "products", "localField": "items.pid", "foreignField": "id",
                         "as": "p"}},
            {"$unwind": {"path": "$p", "preserveNullAndEmptyArrays": True}},
            {"$group": {"_id": "$p.cat", "qty": {"$sum": "$items.q"},
                        "cogs": {"$sum": {"$multiply": ["$items.q", "$p.cost"]}},
                        "orders": {"$addToSet": "$n"}}},
            {"$sort": {"_id": 1}},
        ]).to_list(None)
        assert rows == [{"_id": "x", "qty": 3, "cogs": 6, "orders": [1, 2]},
                        {"_id": "y", "qty": 1, "cogs": 3, "orders": [1]}]
        daily = await db.orders.aggregate([
            {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at",
                                                  "timezone": "Europe/Istanbul"}},
                        "rev": {"$sum": "$total"}, "c": {"$count": {}}}},
            {"$sort": {"_id": 1}},
        ]).to_list(None)
        assert daily == [{"_id": "2026-01-05", "rev": 10.0, "c": 1},
                         {"_id": "2026-01-06", "rev": 50.0, "c": 1},
                         {"_id": "2026-01-07", "rev": 4.0, "c": 1}]
        facet = await db.orders.aggregate([
            {"$facet": {"n": [{"$count": "c"}],
                        "big": [{"$match": {"total": {"$gt": 5}}}, {"$project": {"_id": 0, "n": 1}}]}}
        ]).to_list(None)
        assert facet == [{"n": [{"c": 3}], "big": [{"n": 1}, {"n": 3}]}]
        # correlated $lookup (let + pipeline) and conversion operators
        rows = await db.orders.aggregate([
            {"$match": {"n": 1}}, {"$unwind": "$items"},
            {"$lookup": {"from": "products", "let": {"pid": "$items.pid"}, "pipeline": [
                {"$match": {"$expr": {"$eq": ["$id", "$$pid"]}}},
                {"$project": {"_id": 0, "cost": 1}}], "as": "p"}},
            {"$project": {"_id": 0, "pid": "$items.pid", "cost": {"$first": "$p.cost"},
                          "s": {"$toString": "$n"}, "d": {"$toDouble": "$items.q"},
                          "k": {"$convert": {"input": "12x", "to": "int", "onError": -1}}}},
        ]).to_list(None)
        assert rows == [{"pid": "a", "cost": 2, "s": "1", "d": 2.0, "k": -1},
                        {"pid": "b", "cost": 3, "s": "1", "d": 1.0, "k": -1}]
        assert await db.orders.aggregate([{"$match": {"n": 99}}]).to_list(None) == []
        close(db)
    run(go())


def test_datetime_roundtrip_and_naive_utc(dbpath):
    async def go():
        db = fresh(dbpath)
        aware = datetime.datetime(2026, 3, 1, 15, 30, 45, 123456,
                                  tzinfo=datetime.timezone(datetime.timedelta(hours=3)))
        await db.e.insert_one({"id": 1, "at": aware, "iso": aware.isoformat()})
        expect = datetime.datetime(2026, 3, 1, 12, 30, 45, 123000)  # naive UTC, ms precision
        assert (await db.e.find_one({"id": 1}))["at"] == expect
        # aware datetimes in filters are converted like MongoDB does
        assert await db.e.count_documents({"at": {"$gte": aware - datetime.timedelta(seconds=1)}}) == 1
        await db.e.update_one({"id": 1}, {"$set": {"upd": aware}})
        close(db)
        db = fresh(dbpath)
        d = await db.e.find_one({"id": 1})
        assert d["at"] == expect and d["upd"] == expect and d["at"].tzinfo is None
        assert d["iso"] == aware.isoformat()
        close(db)
    run(go())


def test_persistence_across_restart(dbpath):
    async def go():
        db = fresh(dbpath)
        await db.items.create_index([("sku", 1)])
        await db.items.insert_many([{"sku": f"s{i}", "q": i} for i in range(50)])
        await db.items.update_many({"q": {"$lt": 10}}, {"$set": {"low": True}})
        await db.items.delete_many({"q": {"$gte": 40}})
        await db.items.find_one_and_update({"sku": "s20"}, {"$inc": {"q": 100}})
        await db.logs.insert_one({"msg": "fast path"})
        snapshot = await db.items.find({}, {"_id": 0}).to_list(None)
        ids = [d["_id"] for d in await db.items.find({}).to_list(None)]
        close(db)

        db = fresh(dbpath)
        assert await db.items.find({}, {"_id": 0}).to_list(None) == snapshot  # same order too
        assert [d["_id"] for d in await db.items.find({}).to_list(None)] == ids
        assert await db.items.count_documents({"low": True}) == 10
        assert (await db.items.find_one({"sku": "s20"}))["q"] == 120
        assert (await db.logs.find_one({}))["msg"] == "fast path"
        assert sorted(await db.list_collection_names()) == ["items", "logs"]
        assert "sku_1" in await db.items.index_information()
        await db.drop_collection("logs")
        close(db)

        db = fresh(dbpath)
        assert await db.list_collection_names() == ["items"]
        close(db)
    run(go())


def test_hash_index_consistency(dbpath):
    """Index-accelerated lookups must return exactly what a full scan returns."""
    async def go():
        db = fresh(dbpath)
        await db.u.create_index("email")
        await db.u.insert_many([{"id": str(i), "email": f"u{i % 7}@x", "tags": [i % 2, "t"]}
                                for i in range(40)])
        await db.u.update_many({"email": "u3@x"}, {"$set": {"email": "moved@x"}})
        await db.u.delete_one({"id": "5"})
        await db.u.insert_one({"id": "new", "email": ["u1@x", "alias@x"]})
        all_docs = await db.u.find({}).to_list(None)
        for q in [{"email": "u1@x"}, {"email": "u3@x"}, {"email": "moved@x"},
                  {"email": {"$in": ["u2@x", "alias@x"]}}, {"id": "5"}, {"id": "new"},
                  {"$or": [{"id": "1"}, {"email": "u4@x"}]}, {"email": None}]:
            got = [d["id"] for d in await db.u.find(q).to_list(None)]
            from mongomock.filtering import filter_applies
            want = [d["id"] for d in all_docs if filter_applies(q, d)]
            assert got == want, q
        close(db)
    run(go())


def test_command_ping_and_backup(dbpath, tmp_path):
    async def go():
        db = fresh(dbpath)
        assert (await db.command("ping"))["ok"] == 1.0
        assert (await db.client.admin.command("ping"))["ok"] == 1.0
        await db.k.insert_one({"a": 1})
        out = do_backup(dbpath, str(tmp_path / "bk.db"))
        conn = sqlite3.connect(out)
        assert conn.execute("SELECT COUNT(*) FROM docs WHERE coll='k'").fetchone()[0] == 1
        conn.close()
        close(db)
        restored = AsyncIOMotorClient(path=out)["shop"]
        assert (await restored.k.find_one({}, {"_id": 0})) == {"a": 1}
        restored.client.close()
    run(go())
