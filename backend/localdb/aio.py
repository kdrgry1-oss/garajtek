"""Motor-compatible asyncio API on top of :mod:`localdb.engine`.

Operations run synchronously inside the coroutine (the data lives in memory and writes are
a single SQLite transaction), guarded by a per-engine lock so that the rare caller on another
thread cannot interleave with the event loop.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

from .engine import Engine, _normalize_sort

_ENGINES: Dict[str, Engine] = {}
_ENGINES_LOCK = threading.Lock()


def get_engine(path: str) -> Engine:
    path = os.path.abspath(path)
    with _ENGINES_LOCK:
        eng = _ENGINES.get(path)
        if eng is None or eng.closed:
            eng = _ENGINES[path] = Engine(path)
        return eng


def _release_engine(eng: Engine) -> None:
    with _ENGINES_LOCK:
        if _ENGINES.get(os.path.abspath(eng.path)) is eng:
            del _ENGINES[os.path.abspath(eng.path)]
    eng.close()


# ------------------------------------------------------------------------- cursors
class AsyncIOMotorCursor:
    """Subset of Motor's AsyncIOMotorCursor: chaining, ``to_list``, ``async for``."""

    def __init__(self, collection: "AsyncIOMotorCollection", filter=None, projection=None,
                 sort=None, skip=0, limit=0, **_ignored):
        self.collection = collection
        self._filter = filter if filter is not None else {}
        self._projection = projection
        self._sort = _normalize_sort(sort)
        self._skip = int(skip or 0)
        self._limit = int(limit or 0)
        self._results: Optional[List[dict]] = None
        self._partial = False
        self._pos = 0
        self._killed = False

    # -- chaining (pymongo semantics: sort replaces) --
    def sort(self, key_or_list, direction=None):
        if direction is not None:
            self._sort = [(key_or_list, direction)]
        else:
            self._sort = _normalize_sort(key_or_list)
        return self

    def skip(self, n):
        self._skip = int(n or 0)
        return self

    def limit(self, n):
        self._limit = int(n or 0)
        return self

    def _noop(self, *args, **kwargs):
        return self

    batch_size = max_time_ms = max_await_time_ms = hint = collation = comment = _noop
    allow_disk_use = max_scan = add_option = remove_option = _noop

    def clone(self):
        c = AsyncIOMotorCursor(self.collection, self._filter, self._projection, self._sort,
                               self._skip, self._limit)
        return c

    def rewind(self):
        self._results = None
        self._pos = 0
        return self

    @property
    def alive(self):
        return not self._killed and (self._results is None or self._pos < len(self._results)
                                     or self._partial)

    # -- execution --
    def _ensure(self, need: Optional[int]):
        if self._results is not None:
            if not self._partial:
                return
            if need is not None and self._pos + need <= len(self._results):
                return
        lim = abs(self._limit)
        partial = False
        if need is not None:
            want = self._pos + need
            if not lim or want < lim:
                lim = want
                partial = True
        self._results = self.collection._call(
            "query", self._filter, self._projection, self._sort, self._skip, lim)
        self._partial = partial and len(self._results) >= lim

    async def to_list(self, length=None):
        if length is not None and length < 0:
            raise ValueError("length must be non-negative")
        need = length if length else None
        self._ensure(need)
        if need is None:
            out = self._results[self._pos:]
        else:
            out = self._results[self._pos:self._pos + need]
        self._pos += len(out)
        return out

    def __aiter__(self):
        return self

    async def __anext__(self):
        self._ensure(None)
        if self._pos >= len(self._results):
            raise StopAsyncIteration
        doc = self._results[self._pos]
        self._pos += 1
        return doc

    async def next(self):
        try:
            return await self.__anext__()
        except StopAsyncIteration:
            raise StopAsyncIteration from None

    async def distinct(self, key):
        return self.collection._call("distinct", key, self._filter)

    async def explain(self):
        return {"queryPlanner": {"winningPlan": {"stage": "COLLSCAN"}}, "localdb": True}

    async def close(self):
        self._killed = True
        self._results = []
        self._pos = 0


class AsyncIOMotorCommandCursor:
    """Lazily-evaluated result of ``aggregate()`` / ``list_indexes()``."""

    def __init__(self, producer):
        self._producer = producer
        self._results: Optional[List[dict]] = None
        self._pos = 0

    def _noop(self, *args, **kwargs):
        return self

    batch_size = max_time_ms = _noop

    def _ensure(self):
        if self._results is None:
            self._results = self._producer()

    async def to_list(self, length=None):
        self._ensure()
        if length:
            out = self._results[self._pos:self._pos + length]
        else:
            out = self._results[self._pos:]
        self._pos += len(out)
        return out

    def __aiter__(self):
        return self

    async def __anext__(self):
        self._ensure()
        if self._pos >= len(self._results):
            raise StopAsyncIteration
        doc = self._results[self._pos]
        self._pos += 1
        return doc

    async def next(self):
        return await self.__anext__()

    async def close(self):
        self._results = []
        self._pos = 0

    @property
    def alive(self):
        return self._results is None or self._pos < len(self._results)


# ---------------------------------------------------------------------- collection
def _async_method(method_name):
    async def method(self, *args, **kwargs):
        return self._call(method_name, *args, **kwargs)
    method.__name__ = method_name
    return method


class AsyncIOMotorCollection:
    def __init__(self, database: "AsyncIOMotorDatabase", name: str):
        self.database = database
        self._name = name

    def __repr__(self):
        return f"AsyncIOMotorCollection(localdb, {self.full_name!r})"

    @property
    def name(self):
        return self._name

    @property
    def full_name(self):
        return f"{self.database.name}.{self._name}"

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self.database[f"{self._name}.{name}"]

    def __getitem__(self, name):
        return self.database[f"{self._name}.{name}"]

    def __eq__(self, other):
        return isinstance(other, AsyncIOMotorCollection) and other.full_name == self.full_name

    def __hash__(self):
        return hash(self.full_name)

    def _sync(self):
        return self.database._sync().get_collection(self._name)

    def _call(self, _method, /, *args, **kwargs):
        engine = self.database.client._engine()
        with engine.lock:
            return getattr(engine.database(self.database.name).get_collection(self._name),
                           _method)(*args, **kwargs)

    def with_options(self, *args, **kwargs):
        return self

    # -- cursors --
    def find(self, filter=None, projection=None, *args, **kwargs):
        skip = kwargs.pop("skip", args[0] if len(args) > 0 else 0)
        limit = kwargs.pop("limit", args[1] if len(args) > 1 else 0)
        sort = kwargs.pop("sort", None)
        projection = kwargs.pop("fields", projection)
        return AsyncIOMotorCursor(self, filter, projection, sort, skip, limit)

    def aggregate(self, pipeline, *args, **kwargs):
        pipeline = list(pipeline)
        return AsyncIOMotorCommandCursor(lambda: self._call("aggregate_list", pipeline))

    def list_indexes(self, *args, **kwargs):
        def produce():
            info = self._call("index_information")
            return [dict(v, name=k, key=dict(v.get("key", [])), v=2) for k, v in info.items()]
        return AsyncIOMotorCommandCursor(produce)

    async def find_one(self, filter=None, *args, **kwargs):
        return self._call("find_one", filter, *args, **kwargs)

    insert_one = _async_method("insert_one")
    insert_many = _async_method("insert_many")
    update_one = _async_method("update_one")
    update_many = _async_method("update_many")
    replace_one = _async_method("replace_one")
    delete_one = _async_method("delete_one")
    delete_many = _async_method("delete_many")
    find_one_and_update = _async_method("find_one_and_update")
    find_one_and_replace = _async_method("find_one_and_replace")
    find_one_and_delete = _async_method("find_one_and_delete")
    count_documents = _async_method("count_documents")
    estimated_document_count = _async_method("estimated_document_count")
    distinct = _async_method("distinct")
    bulk_write = _async_method("bulk_write")
    create_index = _async_method("create_index")
    create_indexes = _async_method("create_indexes")
    drop_index = _async_method("drop_index")
    drop_indexes = _async_method("drop_indexes")
    index_information = _async_method("index_information")
    drop = _async_method("drop")
    rename = _async_method("rename")

    async def options(self):
        return {}

    def watch(self, *args, **kwargs):
        raise NotImplementedError("Change streams are not supported by localdb")


# ------------------------------------------------------------------------ database
class AsyncIOMotorDatabase:
    def __init__(self, client: "AsyncIOMotorClient", name: str):
        self.client = client
        self.name = name
        self._colls: Dict[str, AsyncIOMotorCollection] = {}

    def __repr__(self):
        return f"AsyncIOMotorDatabase(localdb, {self.name!r})"

    def __getitem__(self, name) -> AsyncIOMotorCollection:
        c = self._colls.get(name)
        if c is None:
            c = self._colls[name] = AsyncIOMotorCollection(self, name)
        return c

    def __getattr__(self, name) -> AsyncIOMotorCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __eq__(self, other):
        return isinstance(other, AsyncIOMotorDatabase) and other.name == self.name and \
            other.client is self.client

    def __hash__(self):
        return hash(("localdb", self.name))

    def get_collection(self, name, *args, **kwargs) -> AsyncIOMotorCollection:
        return self[name]

    def with_options(self, *args, **kwargs):
        return self

    def _sync(self):
        return self.client._engine().database(self.name)

    def _call(self, _method, /, *args, **kwargs):
        engine = self.client._engine()
        with engine.lock:
            return getattr(engine.database(self.name), _method)(*args, **kwargs)

    async def command(self, command, value=1, *args, **kwargs):
        return self._call("command", command, value)

    async def list_collection_names(self, *args, **kwargs):
        return self._call("list_collection_names", *args, **kwargs)

    async def list_collections(self, *args, **kwargs):
        names = self._call("list_collection_names")
        return AsyncIOMotorCommandCursor(lambda: [{"name": n, "type": "collection"}
                                                  for n in names])

    async def create_collection(self, name, *args, **kwargs):
        self._call("create_collection", name)
        return self[name]

    async def drop_collection(self, name_or_collection, *args, **kwargs):
        name = getattr(name_or_collection, "name", name_or_collection)
        self._call("drop_collection", name)
        return {"ok": 1.0}

    def aggregate(self, *args, **kwargs):
        raise NotImplementedError("Database-level aggregate is not supported by localdb")


# -------------------------------------------------------------------------- client
def default_db_path() -> str:
    env = (os.environ.get("DB_PATH") or "").strip()
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "store.db")


class AsyncIOMotorClient:
    """Drop-in replacement for ``motor.motor_asyncio.AsyncIOMotorClient``.

    ``host`` is ignored unless it is a filesystem path / ``sqlite:///path`` URL; otherwise the
    database file comes from ``path=`` or the ``DB_PATH`` environment variable.
    """

    def __init__(self, host: Any = None, *args, path: Optional[str] = None, **kwargs):
        if path is None and isinstance(host, str):
            if host.startswith("sqlite:///"):
                path = host[len("sqlite:///") - 1:] if host.startswith("sqlite:////") \
                    else host[len("sqlite:///"):]
            elif host.endswith(".db") and "://" not in host:
                path = host
        self._path = os.path.abspath(path or default_db_path())
        self._eng: Optional[Engine] = get_engine(self._path)
        self._dbs: Dict[str, AsyncIOMotorDatabase] = {}
        self._default_db = kwargs.get("default_db")

    @property
    def path(self) -> str:
        return self._path

    def _engine(self) -> Engine:
        eng = self._eng
        if eng is None or eng.closed:
            eng = self._eng = get_engine(self._path)
        return eng

    def __getitem__(self, name) -> AsyncIOMotorDatabase:
        d = self._dbs.get(name)
        if d is None:
            d = self._dbs[name] = AsyncIOMotorDatabase(self, name)
        return d

    def __getattr__(self, name) -> AsyncIOMotorDatabase:
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def get_database(self, name=None, *args, **kwargs) -> AsyncIOMotorDatabase:
        return self[name or self._default_db or os.environ.get("DB_NAME", "test_database")]

    def get_default_database(self, default=None, *args, **kwargs) -> AsyncIOMotorDatabase:
        return self.get_database(default)

    async def server_info(self):
        import mongomock
        return {"version": mongomock.SERVER_VERSION, "ok": 1.0, "localdb": True,
                "path": self._path}

    async def list_database_names(self, *args, **kwargs):
        eng = self._engine()
        with eng.lock:
            return eng.database_names()

    async def drop_database(self, name_or_db):
        name = getattr(name_or_db, "name", name_or_db)
        db = self[name]
        for coll in await db.list_collection_names():
            await db.drop_collection(coll)

    def close(self):
        """Release the database file (data is already on disk). A later operation through
        this client transparently re-opens it, like Motor reconnects."""
        eng = self._eng
        self._eng = None
        if eng is not None and not eng.closed:
            _release_engine(eng)

    def backup(self, dest_path: str) -> None:
        eng = self._engine()
        eng.storage.backup_to(dest_path)

    @property
    def address(self):
        return ("localdb", 0)
