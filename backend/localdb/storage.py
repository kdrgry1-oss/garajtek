"""SQLite persistence for localdb.

Layout (one file, WAL mode):

    docs(rowid, db, coll, key, doc)   -- one row per document; key = BSON of {"_id": ...},
                                         doc = full BSON document; rowid keeps natural order
    idx(db, coll, name, spec)         -- index definitions (BSON), recreated on load
    colls(db, coll)                   -- collections created explicitly (may be empty)
    meta(k, v)                        -- schema version

Documents are stored as BSON exactly like MongoDB would store them, so datetimes,
ObjectIds, Int64, Decimal128, binary etc. round-trip losslessly (datetimes come back
naive-UTC, millisecond precision -- the same as Motor's default ``tz_aware=False``).
"""
from __future__ import annotations

import os
import sqlite3
try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX
    fcntl = None
import sys
import threading
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import bson
from bson.codec_options import CodecOptions

SCHEMA_VERSION = "1"

# Default codec options mirror pymongo/Motor defaults: dict documents, naive UTC datetimes.
DECODE_OPTS = CodecOptions(tz_aware=False)


def encode_key(_id) -> bytes:
    return bson.encode({"_id": _id})


_intern = sys.intern


def compact(obj):
    """Intern dict keys and short strings. Every document repeats the same field names (and
    status/platform/city values); sharing them cuts the in-memory size of a collection by
    ~50-60% (measured: 30k orders 393 MB -> 161 MB)."""
    t = type(obj)
    if t is dict:
        return {_intern(k): compact(v) for k, v in obj.items()}
    if t is list:
        return [compact(v) for v in obj]
    if t is str and len(obj) <= 24:
        return _intern(obj)
    return obj


def decode_doc(blob: bytes) -> dict:
    return compact(bson.decode(blob, DECODE_OPTS))


class DatabaseInUseError(RuntimeError):
    """Another process already serves this database file."""


def _acquire_process_lock(path: str):
    """Exclusive, non-blocking advisory lock on ``<db>.lock`` for the life of the process.

    The in-memory copy is authoritative while the app runs, so a second writer (a second
    uvicorn worker, or reset_admin.py / import_data.py run while the service is up) would
    silently diverge and lose writes. Refuse to open instead. The kernel drops the lock when
    the process exits (also on SIGKILL). Online backups (``python -m localdb.backup``) do not
    take this lock."""
    if fcntl is None:
        return None
    fd = os.open(path + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as e:
        os.close(fd)
        raise DatabaseInUseError(
            f"localdb: {path} başka bir süreç tarafından kullanılıyor (uygulama çalışıyor "
            f"olabilir). Bu işlem için önce servisi durdurun: systemctl stop garajtek-api. "
            f"(another process holds {path}.lock; localdb is single-process)") from e
    return fd


class Storage:
    """Thin, thread-safe wrapper around a single SQLite connection."""

    def __init__(self, path: str):
        self.path = path
        d = os.path.dirname(os.path.abspath(path))
        os.makedirs(d, exist_ok=True)
        self._lockfd = _acquire_process_lock(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False,
                                     timeout=30)
        c = self._conn
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA synchronous=NORMAL")
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA temp_store=MEMORY")
        # Modest page cache: the working set lives in Python memory anyway.
        c.execute("PRAGMA cache_size=-16000")
        c.execute("""CREATE TABLE IF NOT EXISTS docs (
                        rowid INTEGER PRIMARY KEY,
                        db   TEXT NOT NULL,
                        coll TEXT NOT NULL,
                        key  BLOB NOT NULL,
                        doc  BLOB NOT NULL,
                        UNIQUE(db, coll, key))""")
        c.execute("CREATE INDEX IF NOT EXISTS docs_by_coll ON docs(db, coll, rowid)")
        c.execute("""CREATE TABLE IF NOT EXISTS idx (
                        db TEXT NOT NULL, coll TEXT NOT NULL, name TEXT NOT NULL,
                        spec BLOB NOT NULL, PRIMARY KEY(db, coll, name))""")
        c.execute("""CREATE TABLE IF NOT EXISTS colls (
                        db TEXT NOT NULL, coll TEXT NOT NULL, PRIMARY KEY(db, coll))""")
        c.execute("CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)")
        c.execute("INSERT OR IGNORE INTO meta(k, v) VALUES('schema', ?)", (SCHEMA_VERSION,))

    # ------------------------------------------------------------------ reads
    def iter_docs(self, db: str, coll: str) -> Iterator[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT doc FROM docs WHERE db=? AND coll=? ORDER BY rowid", (db, coll)).fetchall()
        for (blob,) in rows:
            yield decode_doc(blob)

    def count(self, db: str, coll: str) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM docs WHERE db=? AND coll=?", (db, coll)).fetchone()[0]

    def has_key(self, db: str, coll: str, key: bytes) -> bool:
        with self._lock:
            return self._conn.execute(
                "SELECT 1 FROM docs WHERE db=? AND coll=? AND key=?", (db, coll, key)
            ).fetchone() is not None

    def collection_names(self, db: str) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT coll FROM docs WHERE db=? "
                "UNION SELECT coll FROM idx WHERE db=? "
                "UNION SELECT coll FROM colls WHERE db=?", (db, db, db)).fetchall()
        return sorted(r[0] for r in rows)

    def database_names(self) -> List[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT DISTINCT db FROM docs UNION SELECT db FROM idx "
                "UNION SELECT db FROM colls").fetchall()
        return sorted(r[0] for r in rows)

    def load_indexes(self, db: str, coll: str) -> dict:
        with self._lock:
            rows = self._conn.execute(
                "SELECT name, spec FROM idx WHERE db=? AND coll=?", (db, coll)).fetchall()
        out = {}
        for name, blob in rows:
            spec = decode_doc(blob)["s"]
            # BSON has no tuples: restore mongomock's [(field, direction), ...] shape so that
            # re-creating an identical index on boot is a no-op instead of a conflict.
            spec["key"] = [tuple(k) for k in spec.get("key", [])]
            out[name] = spec
        return out

    # ----------------------------------------------------------------- writes
    def write(self, db: str, coll: str, upserts: Sequence[Tuple[bytes, bytes]],
              deletes: Sequence[bytes]) -> None:
        if not upserts and not deletes:
            return
        with self._lock:
            c = self._conn
            c.execute("BEGIN IMMEDIATE")
            try:
                if deletes:
                    c.executemany("DELETE FROM docs WHERE db=? AND coll=? AND key=?",
                                  [(db, coll, k) for k in deletes])
                if upserts:
                    c.executemany(
                        "INSERT INTO docs(db, coll, key, doc) VALUES(?,?,?,?) "
                        "ON CONFLICT(db, coll, key) DO UPDATE SET doc=excluded.doc",
                        [(db, coll, k, d) for k, d in upserts])
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    def insert_new(self, db: str, coll: str, rows: Sequence[Tuple[bytes, bytes]]) -> None:
        """Plain INSERT (raises sqlite3.IntegrityError on duplicate _id); all-or-nothing."""
        with self._lock:
            c = self._conn
            c.execute("BEGIN IMMEDIATE")
            try:
                c.executemany("INSERT INTO docs(db, coll, key, doc) VALUES(?,?,?,?)",
                              [(db, coll, k, d) for k, d in rows])
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    def save_indexes(self, db: str, coll: str, indexes: dict) -> None:
        with self._lock:
            c = self._conn
            c.execute("BEGIN IMMEDIATE")
            try:
                c.execute("DELETE FROM idx WHERE db=? AND coll=?", (db, coll))
                c.executemany("INSERT INTO idx(db, coll, name, spec) VALUES(?,?,?,?)",
                              [(db, coll, name, bson.encode({"s": spec}))
                               for name, spec in indexes.items()])
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    def mark_collection(self, db: str, coll: str) -> None:
        with self._lock:
            self._conn.execute("INSERT OR IGNORE INTO colls(db, coll) VALUES(?,?)", (db, coll))

    def drop_collection(self, db: str, coll: str) -> None:
        with self._lock:
            c = self._conn
            c.execute("BEGIN IMMEDIATE")
            try:
                c.execute("DELETE FROM docs WHERE db=? AND coll=?", (db, coll))
                c.execute("DELETE FROM idx WHERE db=? AND coll=?", (db, coll))
                c.execute("DELETE FROM colls WHERE db=? AND coll=?", (db, coll))
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    def rename_collection(self, db: str, old: str, new: str) -> None:
        with self._lock:
            c = self._conn
            c.execute("BEGIN IMMEDIATE")
            try:
                for t in ("docs", "idx", "colls"):
                    c.execute(f"DELETE FROM {t} WHERE db=? AND coll=?", (db, new))
                    c.execute(f"UPDATE {t} SET coll=? WHERE db=? AND coll=?", (new, db, old))
                c.execute("COMMIT")
            except BaseException:
                c.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------- utilities
    def backup_to(self, dest_path: str) -> None:
        """Consistent online copy via the SQLite backup API (safe while the app runs)."""
        dest = sqlite3.connect(dest_path)
        try:
            with self._lock:
                self._conn.backup(dest)
        finally:
            dest.close()

    def checkpoint(self) -> None:
        with self._lock:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except Exception:
                pass
            self._conn.close()
            if self._lockfd is not None:
                try:
                    os.close(self._lockfd)  # releases the flock
                except OSError:
                    pass
                self._lockfd = None


def iter_rows(path: str) -> Iterable[Tuple[str, str, Optional[dict]]]:  # pragma: no cover
    """Debug helper: yields (db, coll, doc) for every stored document."""
    conn = sqlite3.connect(path)
    try:
        for db, coll, blob in conn.execute("SELECT db, coll, doc FROM docs ORDER BY rowid"):
            yield db, coll, decode_doc(blob)
    finally:
        conn.close()
