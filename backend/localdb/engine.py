"""Synchronous core of localdb: mongomock collections backed by SQLite.

* Query/update/aggregation semantics come from ``mongomock`` (pure Python).
* Every collection is loaded lazily from SQLite into mongomock's in-memory store on first
  real access; every mutation is written through to SQLite before the call returns.
* Changed documents are tracked by hooking the store (``__setitem__``/``__delitem__``) and
  the document iterator that update/delete operations mutate in place, so the set of ids to
  persist is exact for every operation (including upserts and rollbacks).
* A small hash-index accelerator (``_id``, ``id`` and the first field of every declared
  index) narrows equality / ``$in`` lookups so that ``find_one({"id": ...})`` does not scan
  the whole collection. It is only a candidate pre-filter: mongomock still evaluates the full
  filter on each candidate, so results are identical to a full scan.

Single-process assumption: the in-memory copy is the source of truth while the process
runs, so exactly ONE process may open a given database file for writing (run uvicorn with a
single worker). Other processes may only take backups (``python -m localdb.backup``).
"""
from __future__ import annotations

import collections
import copy
import datetime
import itertools
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Optional

import bson
from bson import ObjectId

import mongomock
from mongomock import filtering, helpers
from sentinels import NOTHING
from mongomock import store as mm_store
from mongomock.collection import Collection as _MMCollection
from mongomock.collection import (validate_is_mapping, validate_is_mutable_mapping,
                                  validate_ok_for_replace, validate_ok_for_update)
from mongomock.command_cursor import CommandCursor
from mongomock.database import Database as _MMDatabase
from pymongo.errors import BulkWriteError, DuplicateKeyError, OperationFailure, WriteError
from pymongo.operations import DeleteMany, DeleteOne, InsertOne, ReplaceOne, UpdateMany, UpdateOne
from pymongo.results import (BulkWriteResult, DeleteResult, InsertManyResult, InsertOneResult,
                             UpdateResult)

from . import shims
from .matcher import compile_filter, install_fast_sort
from .storage import DECODE_OPTS, Storage, decode_doc, encode_key

logger = logging.getLogger("localdb")

shims.apply()
install_fast_sort()

_SCALARS = (str, int, float, type(None), ObjectId, datetime.datetime, bytes, uuid.UUID)


def _roundtrip(doc: dict) -> dict:
    """Normalise a document exactly like a MongoDB round-trip would (BSON types, naive-UTC
    datetimes truncated to milliseconds, tuples -> lists ...). Raises bson InvalidDocument for
    values MongoDB would also reject."""
    return bson.decode(bson.encode(doc), DECODE_OPTS)


def _roundtrip_value(value):
    return bson.decode(bson.encode({"v": value}), DECODE_OPTS)["v"]


def _store_key(_id):
    return helpers.hashdict(_id) if isinstance(_id, dict) else _id


def _plain_id(key):
    return dict(key) if isinstance(key, helpers.hashdict) else key


def _norm_scalar(v):
    if isinstance(v, datetime.datetime):
        return helpers.patch_datetime_awareness_in_document(v)
    return v


def _eq_values(v):
    """Values a filter clause requires equality with (superset semantics), or None."""
    if isinstance(v, dict):
        if len(v) == 1:
            (op, arg), = v.items()
            if op == "$eq" and isinstance(arg, _SCALARS):
                return [_norm_scalar(arg)]
            if op == "$in" and isinstance(arg, (list, tuple)) and \
                    all(isinstance(a, _SCALARS) for a in arg):
                return [_norm_scalar(a) for a in arg]
        return None
    if isinstance(v, _SCALARS):
        return [_norm_scalar(v)]
    return None


def _doc_index_keys(doc, field):
    """(hashable keys, always_flag) under which ``doc`` must be found for ``field``."""
    v = doc.get(field) if isinstance(doc, dict) else None
    if isinstance(v, list):
        keys, always = [], False
        for e in v:
            if isinstance(e, _SCALARS):
                keys.append(e)
            elif not isinstance(e, (dict, list)):
                always = True
        return keys, always
    if isinstance(v, _SCALARS):
        return [v], False
    if isinstance(v, dict):
        return [], False
    return [], True


# --------------------------------------------------------------------------- stores
class LazyCollectionStore(mm_store.CollectionStore):
    """mongomock CollectionStore that loads from SQLite on first access and records every
    document id written/deleted while a write operation is active."""

    def __init__(self, name, engine: "Engine", dbname: str):
        self._engine = engine
        self._dbname = dbname
        self._loaded = False
        self._docs_raw = collections.OrderedDict()
        self._touched = None
        self._pending = set()
        self._seq: Dict[Any, int] = {}
        self._next_seq = 0
        self._hidx: Dict[str, Dict[Any, set]] = {}
        self._hrev: Dict[str, Dict[Any, tuple]] = {}
        self._halways: Dict[str, set] = {}
        # Match cache: repr(filter) -> ordered store keys of the matching documents. A
        # paginated endpoint typically runs count_documents(q) and find(q)/aggregate($match q)
        # back to back; the second evaluation is served from here. Cleared on ANY change.
        self._mcache: "collections.OrderedDict[str, list]" = collections.OrderedDict()
        self._version = 0
        super().__init__(name)
        self.indexes = engine.storage.load_indexes(dbname, name)
        self._ttl_indexes = {k: v for k, v in self.indexes.items()
                             if v.get("expireAfterSeconds") is not None}

    # -- lazy document dict ------------------------------------------------
    @property
    def _documents(self):
        if not self._loaded:
            self._load()
        return self._docs_raw

    @_documents.setter
    def _documents(self, value):
        self._docs_raw = value

    def bump(self):
        self._version += 1
        if self._mcache:
            self._mcache.clear()

    def _load(self):
        self.bump()
        self._loaded = True
        docs = collections.OrderedDict()
        seq = {}
        try:
            for i, doc in enumerate(self._engine.storage.iter_docs(self._dbname, self.name)):
                k = _store_key(doc["_id"])
                docs[k] = doc
                seq[k] = i
        except BaseException:
            self._loaded = False
            raise
        self._docs_raw = docs
        self._seq = seq
        self._next_seq = len(seq)
        self._hidx.clear()
        self._hrev.clear()
        self._halways.clear()
        self._pending = set()

    @property
    def loaded(self):
        return self._loaded

    @property
    def is_created(self):
        if not self._loaded:
            return bool(self.indexes) or self._is_force_created or \
                self._engine.storage.count(self._dbname, self.name) > 0
        return super().is_created

    def drop(self):
        self.bump()
        super().drop()
        self._loaded = True
        self._pending = set()
        self._seq = {}
        self._next_seq = 0
        self._hidx.clear()
        self._hrev.clear()
        self._halways.clear()

    def _remove_expired_documents(self):
        if not self._ttl_indexes:
            return
        own = self._touched is None
        if own:
            self._touched = set()
        try:
            super()._remove_expired_documents()
        finally:
            if own:
                touched, self._touched = self._touched, None
                if touched:
                    self._engine.flush(self._dbname, self, touched)

    def __setitem__(self, key, val):
        docs = self._documents
        if key not in docs:
            self._seq[key] = self._next_seq
            self._next_seq += 1
        self.bump()
        super().__setitem__(key, val)
        if self._hidx:
            self.reindex((key,))
        if self._touched is not None:
            self._touched.add(key)

    def __delitem__(self, key):
        self.bump()
        super().__delitem__(key)
        self._seq.pop(key, None)
        if self._hidx:
            self.reindex((key,))
        if self._touched is not None:
            self._touched.add(key)

    # -- hash index accelerator --------------------------------------------
    def _indexable_fields(self):
        fields = {"id"}
        for spec in self.indexes.values():
            key = spec.get("key") or []
            if key:
                f = key[0][0]
                if "." not in f and not f.startswith("$") and f != "_id":
                    fields.add(f)
        return fields

    def _build(self, field):
        idx: Dict[Any, set] = {}
        rev: Dict[Any, tuple] = {}
        always = set()
        for k, doc in self._documents.items():
            keys, alw = _doc_index_keys(doc, field)
            for x in keys:
                try:
                    idx.setdefault(x, set()).add(k)
                except TypeError:
                    alw = True
            rev[k] = (tuple(keys), alw)
            if alw:
                always.add(k)
        self._hidx[field] = idx
        self._hrev[field] = rev
        self._halways[field] = always

    def _lookup(self, field, values):
        if field not in self._hidx:
            self._build(field)
        idx = self._hidx[field]
        out = set(self._halways[field])
        for v in values:
            try:
                s = idx.get(v)
            except TypeError:
                return None
            if s:
                out |= s
        return out

    def reindex(self, keys):
        if not self._hidx:
            return
        docs = self._docs_raw
        for field, idx in self._hidx.items():
            rev = self._hrev[field]
            always = self._halways[field]
            for k in keys:
                old = rev.pop(k, None)
                if old is not None:
                    for x in old[0]:
                        try:
                            s = idx.get(x)
                        except TypeError:
                            continue
                        if s is not None:
                            s.discard(k)
                            if not s:
                                del idx[x]
                    always.discard(k)
                doc = docs.get(k)
                if doc is None:
                    continue
                nkeys, alw = _doc_index_keys(doc, field)
                for x in nkeys:
                    try:
                        idx.setdefault(x, set()).add(k)
                    except TypeError:
                        alw = True
                rev[k] = (tuple(nkeys), alw)
                if alw:
                    always.add(k)

    def candidates(self, spec, _fields=None):
        """A superset of the keys of documents matching ``spec``; None = unknown (scan)."""
        if not isinstance(spec, dict) or not spec:
            return None
        if _fields is None:
            _fields = self._indexable_fields()
        best = None
        for k, v in spec.items():
            c = None
            if k == "$and" and isinstance(v, list):
                for sub in v:
                    cc = self.candidates(sub, _fields)
                    if cc is not None and (c is None or len(cc) < len(c)):
                        c = cc
            elif k == "$or" and isinstance(v, list) and v:
                acc = set()
                for sub in v:
                    cc = self.candidates(sub, _fields)
                    if cc is None:
                        acc = None
                        break
                    acc |= cc
                c = acc
            elif k == "_id":
                vals = _eq_values(v)
                if vals is not None:
                    docs = self._documents
                    c = set()
                    for x in vals:
                        try:
                            if x in docs:
                                c.add(x)
                        except TypeError:
                            c = None
                            break
            elif k in _fields:
                vals = _eq_values(v)
                if vals is not None:
                    c = self._lookup(k, vals)
            if c is not None and (best is None or len(c) < len(best)):
                best = c
                if not best:
                    return best
        return best


class LDatabaseStore(mm_store.DatabaseStore):
    def __init__(self, engine: "Engine", dbname: str):
        super().__init__()
        self._engine = engine
        self._dbname = dbname

    def __getitem__(self, col_name):
        try:
            return self._collections[col_name]
        except KeyError:
            col = self._collections[col_name] = LazyCollectionStore(
                col_name, self._engine, self._dbname)
            return col

    def list_created_collection_names(self):
        names = set(self._engine.storage.collection_names(self._dbname))
        for name, col in self._collections.items():
            if col._is_force_created or col.indexes or (col.loaded and col._docs_raw):
                names.add(name)
        return sorted(names)

    def create_collection(self, name):
        col = super().create_collection(name)
        self._engine.storage.mark_collection(self._dbname, name)
        return col

    @property
    def is_created(self):
        return bool(self.list_created_collection_names())


# ---------------------------------------------------------------------- array filters
def _expand_path(node, parts, idents):
    if not parts:
        yield []
        return
    head, rest = parts[0], parts[1:]
    if head.startswith("$[") and head.endswith("]"):
        ident = head[2:-1]
        if not isinstance(node, list):
            return
        for i, el in enumerate(node):
            if ident:
                flt = idents.get(ident)
                if flt is None:
                    raise WriteError("No array filter found for identifier '%s'" % ident, 2)
                if not filtering.filter_applies(flt, {ident: el}):
                    continue
            for tail in _expand_path(el, rest, idents):
                yield [str(i)] + tail
        return
    if not any(p.startswith("$[") for p in rest):
        yield [head] + list(rest)
        return
    child = None
    if isinstance(node, dict):
        child = node.get(head)
    elif isinstance(node, list) and head.isdigit():
        i = int(head)
        child = node[i] if i < len(node) else None
    for tail in _expand_path(child, rest, idents):
        yield [head] + tail


def _expand_update(doc, update, idents):
    out = {}
    for op, fields in update.items():
        if not isinstance(fields, dict):
            out[op] = fields
            continue
        nf = {}
        for path, val in fields.items():
            if "$[" not in path:
                nf[path] = val
                continue
            for segs in _expand_path(doc, path.split("."), idents):
                nf[".".join(segs)] = val
        if nf:
            out[op] = nf
    return out


def _uses_all_positional(update) -> bool:
    if not isinstance(update, dict):
        return False
    for fields in update.values():
        if isinstance(fields, dict) and any("$[" in p for p in fields):
            return True
    return False


def _normalize_sort(sort):
    if not sort:
        return None
    if isinstance(sort, str):
        return [(sort, 1)]
    if isinstance(sort, dict):
        return list(sort.items())
    out = []
    for item in sort:
        if isinstance(item, str):
            out.append((item, 1))
        else:
            out.append((item[0], item[1]))
    return out


class _NeedAll(Exception):
    pass


def _needed_fields(pipeline) -> Optional[set]:
    """Conservative superset of the top-level input fields an aggregation pipeline can read,
    or None when it may read the whole document ($$ROOT, $graphLookup, ...). Used to copy only
    those fields out of the store instead of whole documents (much less memory and CPU for
    reports over large collections)."""
    fields = set()

    def add_path(path):
        if not isinstance(path, str) or not path:
            return
        top = path.split(".", 1)[0]
        if top:
            fields.add(top)

    def scan_expr(node):
        if isinstance(node, str):
            if node.startswith("$$"):
                name = node[2:].split(".", 1)[0]
                if name in ("ROOT", "CURRENT"):
                    raise _NeedAll()
            elif node.startswith("$"):
                add_path(node[1:])
        elif isinstance(node, dict):
            for k, v in node.items():
                if k in ("$getField", "$setField", "$unsetField", "$function", "$accumulator",
                         "$where"):
                    raise _NeedAll()
                scan_expr(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                scan_expr(v)

    def scan_query(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$expr":
                    scan_expr(v)
                elif k == "$where" or k == "$text":
                    raise _NeedAll()
                elif k.startswith("$"):
                    scan_query(v)
                else:
                    add_path(k)
                    scan_query(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                scan_query(v)

    def scan_pipeline(stages) -> bool:
        """Scan stages; True when the pipeline output no longer contains the input documents
        as such (a $group/$project-inclusion/... reshaped them), i.e. unread fields of the input
        can never reach the output."""
        for stage in stages:
            if not isinstance(stage, dict) or len(stage) != 1:
                raise _NeedAll()
            (op, arg), = stage.items()
            if op == "$match":
                scan_query(arg)
            elif op == "$project":
                if not isinstance(arg, dict):
                    raise _NeedAll()
                exclusion = any((v is False or (type(v) in (int, float) and v == 0))
                                for k, v in arg.items() if k != "_id")
                for k, v in arg.items():
                    add_path(k)
                    scan_expr(v)
                if not exclusion:
                    return True  # inclusion projection reshapes the document
            elif op in ("$addFields", "$set", "$sort"):
                if not isinstance(arg, dict):
                    raise _NeedAll()
                for k, v in arg.items():
                    add_path(k)
                    scan_expr(v)
            elif op in ("$unset", "$limit", "$skip", "$sample"):
                pass
            elif op == "$unwind":
                scan_expr(arg)
            elif op == "$lookup":
                if not isinstance(arg, dict):
                    raise _NeedAll()
                add_path(arg.get("localField"))
                scan_expr(arg.get("let") or {})
            elif op in ("$group", "$bucket", "$bucketAuto", "$sortByCount", "$replaceRoot",
                        "$replaceWith", "$count"):
                scan_expr(arg)
                return True
            elif op == "$facet":
                if not isinstance(arg, dict):
                    raise _NeedAll()
                for sub in arg.values():
                    if not scan_pipeline(sub):
                        raise _NeedAll()
                return True
            else:
                raise _NeedAll()
        return False

    try:
        if not scan_pipeline(pipeline):
            return None
    except _NeedAll:
        return None
    return fields


def _nondeterministic(node) -> bool:
    """True when an expression tree uses $rand / $$NOW / $$CLUSTER_TIME / $function."""
    if isinstance(node, str):
        return node.startswith("$$NOW") or node.startswith("$$CLUSTER_TIME")
    if isinstance(node, dict):
        return any(k in ("$rand", "$function", "$sample") or _nondeterministic(v)
                   for k, v in node.items())
    if isinstance(node, (list, tuple)):
        return any(_nondeterministic(v) for v in node)
    return False


def _has_unique(indexes: dict) -> bool:
    return any(spec.get("unique") for spec in indexes.values())


# ------------------------------------------------------------------------ collection
class LCollection(_MMCollection):

    def __init__(self, database, name, _db_store, engine: "Engine", **kwargs):
        super().__init__(database, name, _db_store, **kwargs)
        self._engine = engine

    def with_options(self, *args, **kwargs):
        return self

    @property
    def _dbname(self):
        return self.database.name

    # -- write tracking ----------------------------------------------------
    @contextmanager
    def _writing(self):
        st = self._store
        outer = st._touched is None
        if outer:
            st._touched = set()
        try:
            yield st
        finally:
            if outer:
                touched = st._touched
                st._touched = None
                if touched:
                    self._engine.flush(self._dbname, st, touched)

    def _iter_documents(self, filter):
        st = self._store
        if filter is None:
            filter = {}
        if st._pending:
            # Documents yielded earlier in this write operation may have been modified in
            # place since: refresh their hash-index entries before using the index.
            pending, st._pending = st._pending, set()
            st.reindex(pending)
        ck = None
        if filter and st._touched is None and not st._ttl_indexes and st.loaded:
            try:
                ck = repr(filter)
            except Exception:  # noqa: BLE001
                ck = None
            if ck is not None:
                hit = st._mcache.get(ck)
                if hit is not None:
                    st._mcache.move_to_end(ck)
                    raw = st._docs_raw
                    return iter([raw[k] for k in hit])
        cand = st.candidates(filter) if filter else None
        if cand is None:
            if st.is_empty:
                filtering.filter_applies(filter, {})
                return iter(())
            docs = list(st.documents)
        else:
            seq = st._seq
            raw = st._documents
            docs = [raw[k] for k in sorted(cand, key=lambda k: seq.get(k, 0)) if k in raw]
        if ck is not None:
            return self._yield_and_cache(st, filter, docs, ck)
        return self._yield_matching(st, filter, docs)

    _MCACHE_SIZE = 16

    @staticmethod
    def _yield_and_cache(st, filter, docs, ck):
        """Like _yield_matching (read-only use); remembers the result once the caller has
        consumed it completely and nothing changed meanwhile."""
        version = st._version
        match = compile_filter(filter)
        keys = []
        for doc in docs:
            if match(doc):
                keys.append(_store_key(doc.get("_id")))
                yield doc
        if st._version == version and st._touched is None:
            st._mcache[ck] = keys
            while len(st._mcache) > LCollection._MCACHE_SIZE:
                st._mcache.popitem(last=False)

    @staticmethod
    def _yield_matching(st, filter, docs):
        match = compile_filter(filter)
        for doc in docs:
            if match(doc):
                touched = st._touched
                if touched is not None:
                    k = _store_key(doc.get("_id"))
                    touched.add(k)
                    st._pending.add(k)
                yield doc

    def _ensure_uniques(self, new_data):
        """Unique-index check (``new_data`` is already stored). Unlike mongomock, documents
        outside a partial index's filter are skipped up front (as MongoDB does), and the
        candidate lookup stops at the first duplicate."""
        for index in self._store.indexes.values():
            if not index.get("unique"):
                continue
            pfe = index.get("partialFilterExpression")
            if pfe is not None and not filtering.filter_applies(pfe, new_data):
                continue
            values = {}
            for key, _ in index.get("key") or []:
                try:
                    values[key] = helpers.get_value_by_dot(new_data, key)
                except KeyError:
                    values[key] = None
            if index.get("sparse") and all(v is None for v in values.values()):
                continue
            spec = {"$and": [pfe, values]} if pfe is not None else values
            count = 0
            for _ in self._iter_documents(spec):
                count += 1
                if count > 1:
                    raise DuplicateKeyError(
                        "E11000 duplicate key error collection: %s index: %s dup key: %r"
                        % (self.full_name, "_".join(f"{k}_{d}" for k, d in index["key"]),
                           values), 11000)

    # -- reads ---------------------------------------------------------------
    def _select(self, spec, sort=None):
        if spec is None:
            spec = {}
        if not isinstance(spec, dict):
            spec = {"_id": spec}
        validate_is_mapping("filter", spec)
        spec = helpers.patch_datetime_awareness_in_document(spec)
        it = self._iter_documents(spec)
        sort = _normalize_sort(sort)
        if sort:
            for key, direction in reversed(sort):
                if key == "$natural":
                    if direction < 0:
                        it = iter(reversed(list(it)))
                    continue
                if key.startswith("$"):
                    raise NotImplementedError("Sorting by %s is not supported" % key)
                it = iter(sorted(it, key=lambda x, k=key: filtering.resolve_sort_key(k, x),
                                 reverse=direction < 0))
        return it

    def query(self, spec=None, projection=None, sort=None, skip=0, limit=0) -> List[dict]:
        it = self._select(spec, sort)
        skip = int(skip or 0)
        limit = abs(int(limit or 0))
        if skip or limit:
            it = itertools.islice(it, skip, skip + limit if limit else None)
        if isinstance(projection, dict):
            projection = dict(projection)
        return [self._copy_only_fields(d, projection, dict) for d in it]

    def find_one(self, filter=None, *args, **kwargs):
        projection = kwargs.pop("projection", args[0] if args else None)
        res = self.query(filter, projection, kwargs.get("sort"), kwargs.get("skip", 0), 1)
        return res[0] if res else None

    def find(self, filter=None, projection=None, *args, **kwargs):
        # mongomock internals call find(); accept and ignore driver-only options.
        for k in ("hint", "comment", "batch_size", "no_cursor_timeout", "allow_disk_use",
                  "max_time_ms", "collation", "cursor_type", "allow_partial_results"):
            kwargs.pop(k, None)
        return super().find(filter, projection, *args, **kwargs)

    def count_documents(self, filter, **kwargs):
        for k in ("collation", "hint", "maxTimeMS", "comment", "session"):
            kwargs.pop(k, None)
        st = self._store
        if not filter and not st.loaded and not kwargs:
            return self._engine.storage.count(self._dbname, self.name)
        return super().count_documents(filter or {}, **kwargs)

    def estimated_document_count(self, **kwargs):
        st = self._store
        if not st.loaded:
            return self._engine.storage.count(self._dbname, self.name)
        return len(st._documents)

    def distinct(self, key, filter=None, session=None, **kwargs):
        if not isinstance(key, str):
            raise TypeError("distinct key must be a string")
        unique = []
        seen = set()
        for x in self._select(filter):
            for values in filtering.iter_key_candidates(key, x):
                if values is NOTHING:
                    continue
                if not isinstance(values, (tuple, list)):
                    values = [values]
                for value in values:
                    h = helpers.hashdict(value) if isinstance(value, dict) else value
                    try:
                        if h in seen:
                            continue
                        seen.add(h)
                    except TypeError:
                        if value in unique:
                            continue
                    unique.append(copy.deepcopy(value))
        return unique

    def aggregate_list(self, pipeline, **kwargs) -> List[dict]:
        pipeline = list(pipeline or [])
        spec, sort, skip, limit = {}, None, 0, 0
        i = 0
        if i < len(pipeline) and list(pipeline[i].keys()) == ["$match"]:
            spec = pipeline[i]["$match"]
            i += 1
        if i < len(pipeline) and list(pipeline[i].keys()) == ["$sort"]:
            sort = list(pipeline[i]["$sort"].items())
            i += 1
            while i < len(pipeline) and len(pipeline[i]) == 1:
                (op, val), = pipeline[i].items()
                if op == "$skip" and not limit:
                    skip += int(val)
                elif op == "$limit":
                    limit = int(val) if not limit else min(limit, int(val))
                else:
                    break
                i += 1
        rest = pipeline[i:]
        if rest and not sort:
            out = self._aggregate_topk(spec, rest)
            if out is not None:
                return out
        projection = None
        if rest:
            needed = _needed_fields(rest)
            if needed is not None:
                projection = {f: 1 for f in needed if f != "_id"} or {"_id": 1}
        docs = self.query(spec, projection, sort, skip, limit)
        if not rest:
            return docs
        return list(mongomock.aggregate.process_pipeline(docs, self.database, rest, None))

    def _aggregate_topk(self, spec, rest) -> Optional[List[dict]]:
        """``[$addFields|$set ..., $sort, ($skip), $limit, tail...]`` after the leading
        $match (storefront product lists, admin order list): run the computed fields and the
        sort on copies holding only the fields they read, keep the selected window, then
        build only those documents in full. Same result as the plain pipeline (stable sort,
        identical input order); None when the shape does not qualify."""
        n_add = 0
        while n_add < len(rest) and len(rest[n_add]) == 1 and \
                next(iter(rest[n_add])) in ("$addFields", "$set"):
            n_add += 1
        if not n_add or n_add >= len(rest) or list(rest[n_add]) != ["$sort"]:
            return None
        j = n_add + 1
        skip, limit = 0, None
        while j < len(rest) and len(rest[j]) == 1:
            (op, val), = rest[j].items()
            if op == "$skip" and limit is None and isinstance(val, int) and val >= 0:
                skip += val
            elif op == "$limit" and isinstance(val, int) and val > 0:
                limit = val if limit is None else min(limit, val)
            else:
                break
            j += 1
        if limit is None:
            return None
        head, tail = rest[:n_add + 1], rest[j:]
        if _nondeterministic(head):
            return None
        needed = _needed_fields(head + [{"$count": "n"}])
        if needed is None:
            return None
        light = self.query(spec, {f: 1 for f in needed if f != "_id"} or {"_id": 1})
        if len(light) <= skip + limit:
            return None  # small input: nothing to gain
        window = head + ([{"$skip": skip}] if skip else []) + [{"$limit": limit}]
        picked = list(mongomock.aggregate.process_pipeline(light, self.database, window, None))
        order = [_store_key(d["_id"]) for d in picked]
        raw = self._store._documents
        full = [self._copy_only_fields(raw[k], None, dict) for k in order]
        return list(mongomock.aggregate.process_pipeline(full, self.database,
                                                         rest[:n_add] + tail, None))

    def aggregate(self, pipeline, session=None, **kwargs):
        return CommandCursor(self.aggregate_list(pipeline))

    # -- inserts -------------------------------------------------------------
    def insert_one(self, document, bypass_document_validation=False, session=None, **kwargs):
        validate_is_mutable_mapping("document", document)
        if "_id" not in document:
            document["_id"] = ObjectId()
        blob = bson.encode(document)
        clean = decode_doc(blob)
        st = self._store
        if not st.loaded and not _has_unique(st.indexes):
            # Append-only fast path: no need to load the collection into memory.
            try:
                self._engine.storage.insert_new(self._dbname, self.name,
                                                [(encode_key(clean["_id"]), blob)])
            except sqlite3.IntegrityError as e:
                raise DuplicateKeyError("E11000 duplicate key error collection: %s index: _id_ "
                                        "dup key: { _id: %r }" % (self.full_name, clean["_id"]),
                                        11000) from e
            return InsertOneResult(clean["_id"], True)
        with self._writing():
            _id = self._insert(clean)
        return InsertOneResult(_id, True)

    def insert_many(self, documents, ordered=True, bypass_document_validation=False,
                    session=None, **kwargs):
        documents = list(documents) if documents is not None else []
        if not documents:
            raise TypeError("documents must be a non-empty list")
        cleans, blobs = [], []
        for d in documents:
            validate_is_mutable_mapping("document", d)
            if "_id" not in d:
                d["_id"] = ObjectId()
            b = bson.encode(d)
            blobs.append(b)
            cleans.append(decode_doc(b))
        st = self._store
        if not st.loaded and not _has_unique(st.indexes):
            try:
                self._engine.storage.insert_new(
                    self._dbname, self.name,
                    [(encode_key(c["_id"]), b) for c, b in zip(cleans, blobs)])
                return InsertManyResult([c["_id"] for c in cleans], True)
            except sqlite3.IntegrityError:
                pass  # fall back to the in-memory path for exact per-document semantics
        with self._writing():
            ids = self._insert(cleans, ordered=ordered)
        return InsertManyResult(ids, True)

    # -- updates -------------------------------------------------------------
    def _do_update(self, filter, update, upsert, multi, array_filters=None, replace=False):
        if filter is None:
            filter = {}
        validate_is_mapping("filter", filter)
        update = _roundtrip_value(update)
        with self._writing():
            if not replace and (array_filters or _uses_all_positional(update)):
                raw = self._update_with_array_filters(filter, update, upsert, multi,
                                                      array_filters)
            else:
                raw = self._update(filter, update, upsert=upsert, multi=multi)
        return UpdateResult(raw, True)

    def _update_with_array_filters(self, filter, update, upsert, multi, array_filters):
        if isinstance(update, list):
            raise OperationFailure("arrayFilters may not be specified for pipeline-style updates")
        filter = helpers.patch_datetime_awareness_in_document(filter)
        idents: Dict[str, dict] = {}
        for f in _roundtrip_value(list(array_filters or [])):
            for k, v in f.items():
                idents.setdefault(k.split(".", 1)[0], {})[k] = v
        gen = self._iter_documents(filter)
        if multi:
            targets = list(gen)
        else:
            first = next(gen, None)
            targets = [first] if first is not None else []
        matched = modified = 0
        for doc in targets:
            matched += 1
            concrete = _expand_update(doc, update, idents)
            if not concrete:
                continue
            raw = self._update({"_id": doc["_id"]}, concrete, upsert=False, multi=False)
            modified += raw.get("nModified", 0) or 0
        upserted = None
        if not targets and upsert:
            stripped = {}
            for op, fields in update.items():
                if isinstance(fields, dict):
                    keep = {p: v for p, v in fields.items() if "$[" not in p}
                    if keep:
                        stripped[op] = keep
            raw = self._update(filter, stripped or {"$set": {}}, upsert=True)
            upserted = raw.get("upserted")
            matched = 1
        return {"n": matched, "nModified": modified, "upserted": upserted, "ok": 1.0,
                "updatedExisting": bool(targets)}

    def update_one(self, filter, update, upsert=False, bypass_document_validation=False,
                   collation=None, array_filters=None, hint=None, session=None, let=None,
                   comment=None):
        validate_ok_for_update(update)
        return self._do_update(filter, update, upsert, False, array_filters)

    def update_many(self, filter, update, upsert=False, array_filters=None,
                    bypass_document_validation=False, collation=None, hint=None, session=None,
                    let=None, comment=None):
        validate_ok_for_update(update)
        return self._do_update(filter, update, upsert, True, array_filters)

    def replace_one(self, filter, replacement, upsert=False, bypass_document_validation=False,
                    collation=None, hint=None, session=None, let=None, comment=None):
        validate_ok_for_replace(replacement)
        return self._do_update(filter, replacement, upsert, False, replace=True)

    # -- find-and-modify -----------------------------------------------------
    def _target_spec(self, filter, _id):
        if "_id" not in filter:
            spec = dict(filter)
            spec["_id"] = _id
            return spec
        return {"$and": [filter, {"_id": _id}]}

    def _find_and_modify_impl(self, filter, projection, sort, return_after, op):
        if filter is None:
            filter = {}
        validate_is_mapping("filter", filter)
        with self._writing() as st:
            target = next(self._select(filter, sort), None)
            if target is None:
                return op(None)
            _id = target["_id"]
            before = None if return_after else self._copy_only_fields(
                target, dict(projection) if isinstance(projection, dict) else projection, dict)
            op(self._target_spec(filter, _id))
            if not return_after:
                return before
            doc = st._documents.get(_store_key(_id))
            if doc is None:
                return None
            return self._copy_only_fields(
                doc, dict(projection) if isinstance(projection, dict) else projection, dict)

    def find_one_and_update(self, filter, update, projection=None, sort=None, upsert=False,
                            return_document=False, array_filters=None, hint=None,
                            session=None, let=None, comment=None, **kwargs):
        validate_ok_for_update(update)
        return_after = bool(return_document)

        def op(spec):
            if spec is None:
                if not upsert:
                    return None
                res = self._do_update(filter or {}, update, True, False, array_filters)
                if return_after and res.upserted_id is not None:
                    return self.find_one({"_id": res.upserted_id}, projection)
                return None
            return self._do_update(spec, update, False, False, array_filters)

        return self._find_and_modify_impl(filter, projection, sort, return_after, op)

    def find_one_and_replace(self, filter, replacement, projection=None, sort=None,
                             upsert=False, return_document=False, hint=None, session=None,
                             let=None, comment=None, **kwargs):
        validate_ok_for_replace(replacement)
        return_after = bool(return_document)

        def op(spec):
            if spec is None:
                if not upsert:
                    return None
                res = self._do_update(filter or {}, replacement, True, False, replace=True)
                if return_after and res.upserted_id is not None:
                    return self.find_one({"_id": res.upserted_id}, projection)
                return None
            return self._do_update(spec, replacement, False, False, replace=True)

        return self._find_and_modify_impl(filter, projection, sort, return_after, op)

    def find_one_and_delete(self, filter, projection=None, sort=None, hint=None, session=None,
                            let=None, comment=None, **kwargs):
        def op(spec):
            if spec is None:
                return None
            return self._delete(spec, multi=False)

        return self._find_and_modify_impl(filter, projection, sort, False, op)

    # -- deletes -------------------------------------------------------------
    def _delete(self, filter, collation=None, hint=None, multi=False, session=None):
        if filter is None:
            filter = {}
        if not isinstance(filter, dict):
            filter = {"_id": filter}
        filter = helpers.patch_datetime_awareness_in_document(filter)
        with self._writing() as st:
            keys = []
            for d in self._iter_documents(filter):
                keys.append(_store_key(d["_id"]))
                if not multi:
                    break
            for k in keys:
                del st[k]
        return {"n": len(keys), "ok": 1.0}

    def delete_one(self, filter, collation=None, hint=None, session=None, let=None,
                   comment=None):
        validate_is_mapping("filter", filter)
        return DeleteResult(self._delete(filter, multi=False), True)

    def delete_many(self, filter, collation=None, hint=None, session=None, let=None,
                    comment=None):
        validate_is_mapping("filter", filter)
        return DeleteResult(self._delete(filter, multi=True), True)

    # -- bulk ----------------------------------------------------------------
    def bulk_write(self, requests, ordered=True, bypass_document_validation=False,
                   session=None, comment=None, let=None):
        res = {"writeErrors": [], "writeConcernErrors": [], "nInserted": 0, "nUpserted": 0,
               "nMatched": 0, "nModified": 0, "nRemoved": 0, "upserted": []}
        requests = list(requests)
        if not requests:
            raise mongomock.InvalidOperation("No operations to execute")
        with self._writing():
            for i, op in enumerate(requests):
                try:
                    if isinstance(op, InsertOne):
                        self.insert_one(op._doc)
                        res["nInserted"] += 1
                        continue
                    if isinstance(op, (DeleteOne, DeleteMany)):
                        r = self._delete(op._filter, multi=isinstance(op, DeleteMany))
                        res["nRemoved"] += r["n"]
                        continue
                    if isinstance(op, ReplaceOne):
                        validate_ok_for_replace(op._doc)
                        r = self._do_update(op._filter, op._doc, op._upsert, False,
                                            replace=True)
                    elif isinstance(op, (UpdateOne, UpdateMany)):
                        validate_ok_for_update(op._doc)
                        r = self._do_update(op._filter, op._doc, op._upsert,
                                            isinstance(op, UpdateMany),
                                            getattr(op, "_array_filters", None))
                    else:
                        raise TypeError("%r is not a valid request" % (op,))
                    if r.upserted_id is not None:
                        res["nUpserted"] += 1
                        res["upserted"].append({"index": i, "_id": r.upserted_id})
                    else:
                        res["nMatched"] += r.matched_count
                        res["nModified"] += r.modified_count or 0
                except (DuplicateKeyError, WriteError) as e:
                    res["writeErrors"].append({"index": i, "code": getattr(e, "code", None),
                                               "errmsg": str(e), "op": op})
                    if ordered:
                        break
        if res["writeErrors"]:
            raise BulkWriteError(res)
        return BulkWriteResult(res, True)

    # -- indexes / admin -------------------------------------------------------
    def _save_indexes(self):
        self._engine.storage.save_indexes(self._dbname, self.name, self._store.indexes)

    def create_index(self, key_or_list, cache_for=300, session=None, **kwargs):
        for k in ("background", "comment", "collation", "default_language", "weights",
                  "language_override", "textIndexVersion", "hidden", "commitQuorum"):
            kwargs.pop(k, None)
        index_list = helpers.create_index_list(key_or_list)
        name = kwargs.get("name") or helpers.gen_index_name(index_list)
        expected = {"key": index_list}
        if kwargs.get("sparse"):
            expected["sparse"] = True
        if kwargs.get("unique"):
            expected["unique"] = True
        if kwargs.get("expireAfterSeconds") is not None:
            expected["expireAfterSeconds"] = kwargs["expireAfterSeconds"]
        if kwargs.get("partialFilterExpression") is not None:
            expected["partialFilterExpression"] = _roundtrip_value(
                kwargs["partialFilterExpression"])
        existing = self._store.indexes.get(name)
        if existing is not None and existing == expected:
            return name  # identical index already present: no-op, no collection load
        if "partialFilterExpression" in kwargs and kwargs["partialFilterExpression"] is not None:
            kwargs["partialFilterExpression"] = expected["partialFilterExpression"]
        with self._writing():
            name = super().create_index(key_or_list, cache_for, **kwargs)
        self._save_indexes()
        return name

    def create_indexes(self, indexes, session=None, **kwargs):
        names = []
        for index in indexes:
            doc = dict(index.document)
            key = list(doc.pop("key").items())
            names.append(self.create_index(key, **doc))
        return names

    def drop_index(self, index_or_name, session=None, **kwargs):
        super().drop_index(index_or_name)
        self._save_indexes()

    def drop_indexes(self, session=None, **kwargs):
        super().drop_indexes()
        self._save_indexes()

    def drop(self, session=None, **kwargs):
        self.database.drop_collection(self.name)

    def rename(self, new_name, session=None, **kwargs):
        return self.database.rename_collection(self.name, new_name, **kwargs)


# -------------------------------------------------------------------------- database
class LDatabase(_MMDatabase):

    def __init__(self, client, name, _store, engine: "Engine"):
        super().__init__(client, name, _store)
        self._engine = engine

    def get_collection(self, name, codec_options=None, read_preference=None,
                       write_concern=None, read_concern=None):
        try:
            return self._collection_accesses[name]
        except KeyError:
            self._ensure_valid_collection_name(name)
            col = self._collection_accesses[name] = LCollection(
                self, name, _db_store=self._store, engine=self._engine)
            return col

    def with_options(self, *args, **kwargs):
        return self

    def list_collection_names(self, filter=None, session=None, **kwargs):
        names = [n for n in self._store.list_created_collection_names()
                 if not n.startswith("system.")]
        if filter and filter.get("name") is not None:
            names = [n for n in names if filtering.filter_applies({"name": filter["name"]},
                                                                    {"name": n})]
        return names

    def create_collection(self, name, **kwargs):
        self._ensure_valid_collection_name(name)
        if name in self.list_collection_names():
            raise mongomock.CollectionInvalid("collection %s already exists" % name)
        self._store.create_collection(name)
        return self[name]

    def drop_collection(self, name_or_collection, session=None, **kwargs):
        name = name_or_collection.name if hasattr(name_or_collection, "name") \
            else name_or_collection
        with self._engine.lock:
            self._engine.storage.drop_collection(self.name, name)
            self._store[name].drop()
            self._store[name].indexes = {}

    def rename_collection(self, name, new_name, dropTarget=False, **kwargs):
        with self._engine.lock:
            if name not in self.list_collection_names():
                raise OperationFailure('The collection "%s" does not exist.' % name, 10026)
            if new_name in self.list_collection_names() and not dropTarget:
                raise OperationFailure('The target collection "%s" already exists' % new_name,
                                       10027)
            self._engine.storage.rename_collection(self.name, name, new_name)
            self._store._collections.pop(name, None)
            self._store._collections.pop(new_name, None)
            self._collection_accesses.pop(name, None)
            self._collection_accesses.pop(new_name, None)
        return {"ok": 1}

    def command(self, command, value=1, **kwargs):
        if isinstance(command, str):
            command = {command: value}
        name = next(iter(command))
        if name in ("ping", "ismaster", "isMaster", "hello"):
            return {"ok": 1.0}
        if name == "buildInfo" or name == "buildinfo":
            return {"version": mongomock.SERVER_VERSION, "ok": 1.0, "localdb": True}
        if name == "serverStatus":
            return {"ok": 1.0, "host": "localdb", "version": mongomock.SERVER_VERSION,
                    "process": "localdb", "uptime": 0}
        if name == "dbStats":
            names = self.list_collection_names()
            return {"db": self.name, "collections": len(names),
                    "objects": sum(self[n].estimated_document_count() for n in names),
                    "ok": 1.0}
        if name == "collStats":
            coll = command[name]
            return {"ns": f"{self.name}.{coll}", "count": self[coll].estimated_document_count(),
                    "ok": 1.0}
        if name == "listCollections":
            return {"cursor": {"firstBatch": [{"name": n, "type": "collection"}
                                              for n in self.list_collection_names()]},
                    "ok": 1.0}
        raise OperationFailure("localdb: command %r is not supported" % name)


# ---------------------------------------------------------------------------- engine
class Engine:
    """Owns the SQLite file and the in-memory mongomock databases."""

    def __init__(self, path: str):
        self.path = path
        self.storage = Storage(path)
        self.lock = threading.RLock()
        self._mm_client = mongomock.MongoClient()
        self._dbs: Dict[str, LDatabase] = {}
        self.closed = False

    def database(self, name: str) -> LDatabase:
        with self.lock:
            db = self._dbs.get(name)
            if db is None:
                db = self._dbs[name] = LDatabase(self._mm_client, name,
                                                 LDatabaseStore(self, name), self)
            return db

    def flush(self, dbname: str, st: LazyCollectionStore, touched: Iterable) -> None:
        ups, dels = [], []
        docs = st._docs_raw
        try:
            for k in touched:
                key = encode_key(_plain_id(k))
                doc = docs.get(k)
                if doc is None:
                    dels.append(key)
                else:
                    blob = bson.encode(doc)
                    ups.append((key, blob))
                    # Keep memory byte-identical to disk (ms datetimes, Int64, lists...).
                    docs[k] = decode_doc(blob)
            self.storage.write(dbname, st.name, ups, dels)
        except Exception:
            logger.critical("localdb: failed to persist %d change(s) in %s.%s — in-memory "
                            "state is ahead of disk until restart", len(ups) + len(dels),
                            dbname, st.name, exc_info=True)
            raise
        finally:
            st.bump()
            st._pending.clear()
            st.reindex(touched)

    def database_names(self) -> List[str]:
        names = set(self.storage.database_names())
        names.update(n for n, d in self._dbs.items() if d.list_collection_names())
        return sorted(names)

    def close(self):
        with self.lock:
            if not self.closed:
                self.closed = True
                self.storage.close()
