"""Consistent online backup of the localdb SQLite file.

Usage (from the backend/ directory):

    python -m localdb.backup DEST [--db PATH] [--gzip] [--keep N]

* DEST may be a file path or an existing directory; for a directory a timestamped name
  ``store-YYYYmmdd-HHMMSS.db`` (``.db.gz`` with --gzip) is created inside it.
* --db defaults to $DB_PATH (or backend/data/store.db).
* --keep N (directory DEST only) deletes all but the newest N backups made by this tool.

Uses the SQLite online-backup API, so it is safe while the app is running (WAL mode) and
the copy is a single self-contained .db file (no -wal/-shm needed). Prints the path written
and exits non-zero on failure. The result is verified with ``PRAGMA integrity_check``.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import gzip
import os
import shutil
import sqlite3
import sys
import tempfile


def _default_db() -> str:
    env = (os.environ.get("DB_PATH") or "").strip()
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "data", "store.db")


def backup(src: str, dest: str, compress: bool = False) -> str:
    if not os.path.exists(src):
        raise FileNotFoundError(f"database file not found: {src}")
    if os.path.isdir(dest):
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(dest, f"store-{stamp}.db" + (".gz" if compress else ""))
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".backup-", suffix=".db",
                               dir=os.path.dirname(os.path.abspath(dest)))
    os.close(fd)
    try:
        s = sqlite3.connect(f"file:{os.path.abspath(src)}?mode=ro", uri=True, timeout=60)
        d = sqlite3.connect(tmp)
        try:
            s.backup(d, pages=4096)
            ok = d.execute("PRAGMA integrity_check").fetchone()[0]
            if ok != "ok":
                raise RuntimeError(f"integrity_check failed on backup: {ok}")
            d.execute("PRAGMA journal_mode=DELETE")
        finally:
            d.close()
            s.close()
        if compress:
            gz_tmp = tmp + ".gz"
            with open(tmp, "rb") as fi, gzip.open(gz_tmp, "wb", compresslevel=6) as fo:
                shutil.copyfileobj(fi, fo, 1024 * 1024)
            os.unlink(tmp)
            os.chmod(gz_tmp, 0o600)  # same private mode as the plain .db (mkstemp)
            tmp = gz_tmp
        os.replace(tmp, dest)
        return dest
    except BaseException:
        for p in (tmp, tmp + ".gz"):
            if os.path.exists(p):
                os.unlink(p)
        raise


def prune(directory: str, keep: int) -> list:
    files = sorted(glob.glob(os.path.join(directory, "store-*.db")) +
                   glob.glob(os.path.join(directory, "store-*.db.gz")))
    removed = files[:-keep] if keep > 0 else []
    for p in removed:
        os.unlink(p)
    return removed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m localdb.backup", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dest", help="destination file or directory")
    ap.add_argument("--db", default=_default_db(), help="source database (default: $DB_PATH)")
    ap.add_argument("--gzip", action="store_true", help="gzip the backup")
    ap.add_argument("--keep", type=int, default=0,
                    help="when DEST is a directory, keep only the newest N backups")
    args = ap.parse_args(argv)
    try:
        out = backup(args.db, args.dest, args.gzip)
    except Exception as e:  # noqa: BLE001
        print(f"backup FAILED: {e}", file=sys.stderr)
        return 1
    print(out)
    if args.keep and os.path.isdir(args.dest):
        for p in prune(args.dest, args.keep):
            print(f"pruned {p}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
