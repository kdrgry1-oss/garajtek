"""localdb — embedded, Motor-compatible document database stored in one SQLite file.

The store runs on a single small VDS without a MongoDB server. ``localdb`` keeps the
application's Motor code unchanged: ``client[db].collection.find_one(...)`` etc. behave like
Motor/MongoDB (query semantics by ``mongomock``, persistence by SQLite in WAL mode).

Environment:
    DB_BACKEND  ``sqlite`` (default) or ``mongo`` (legacy Motor; also needs MONGO_URL)
    DB_PATH     SQLite file path (default: backend/data/store.db)
    DB_NAME     logical database name (default: test_database)

IMPORTANT — single process: the in-memory copy of each collection is authoritative while the
process runs, so exactly ONE process may serve a given DB_PATH (uvicorn ``--workers 1``).
Separate processes may only read it through ``python -m localdb.backup`` (SQLite backup API).
"""
from __future__ import annotations

import os

from .aio import (AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorCommandCursor,
                  AsyncIOMotorCursor, AsyncIOMotorDatabase, default_db_path)

__all__ = [
    "AsyncIOMotorClient", "AsyncIOMotorDatabase", "AsyncIOMotorCollection",
    "AsyncIOMotorCursor", "AsyncIOMotorCommandCursor", "make_client", "backend_name",
    "default_db_path",
]


def backend_name() -> str:
    """'mongo' only when explicitly requested AND a MONGO_URL is configured."""
    want = (os.environ.get("DB_BACKEND") or "sqlite").strip().lower()
    if want == "mongo" and (os.environ.get("MONGO_URL") or "").strip():
        return "mongo"
    return "sqlite"


def make_client():
    """Return the application's database client according to the environment."""
    if backend_name() == "mongo":
        from motor.motor_asyncio import AsyncIOMotorClient as _MotorClient  # optional dep
        return _MotorClient(os.environ["MONGO_URL"].strip())
    return AsyncIOMotorClient(path=default_db_path())
