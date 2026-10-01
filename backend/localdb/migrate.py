"""One-off migration: copy a MongoDB database (Atlas/Railway/...) into the localdb file.

Usage (from backend/):

    python -m localdb.migrate --mongo-url "mongodb+srv://..." [--mongo-db NAME]
                              [--db PATH] [--target-db NAME] [--drop]

Copies every collection (documents as raw BSON, preserving types and _ids) and every index
definition. Needs only ``pymongo`` (already a dependency). Run it while the app is STOPPED
(single-writer rule), then start the app with DB_BACKEND=sqlite (default).
"""
from __future__ import annotations

import argparse
import os
import sys

import bson


def main(argv=None) -> int:
    from pymongo import MongoClient
    from bson.codec_options import CodecOptions
    from bson.raw_bson import RawBSONDocument

    from .storage import Storage, encode_key, DECODE_OPTS

    ap = argparse.ArgumentParser(prog="python -m localdb.migrate")
    ap.add_argument("--mongo-url", default=os.environ.get("MONGO_URL"), required=False)
    ap.add_argument("--mongo-db", default=os.environ.get("DB_NAME", "test_database"))
    ap.add_argument("--db", default=None, help="target SQLite file (default: $DB_PATH)")
    ap.add_argument("--target-db", default=None, help="logical db name (default: --mongo-db)")
    ap.add_argument("--drop", action="store_true", help="replace collections already present")
    ap.add_argument("--batch", type=int, default=2000)
    args = ap.parse_args(argv)
    if not args.mongo_url:
        print("--mongo-url (or MONGO_URL) is required", file=sys.stderr)
        return 2
    from .aio import default_db_path
    path = args.db or default_db_path()
    target = args.target_db or args.mongo_db
    st = Storage(path)
    client = MongoClient(args.mongo_url)
    src = client[args.mongo_db]
    raw = CodecOptions(document_class=RawBSONDocument)
    existing = set(st.collection_names(target))
    total = 0
    for name in sorted(src.list_collection_names()):
        if name.startswith("system."):
            continue
        if name in existing:
            if not args.drop:
                print(f"[skip] {name}: already present (use --drop to replace)")
                continue
            st.drop_collection(target, name)
        coll = src.get_collection(name, codec_options=raw)
        n = 0
        batch = []
        for doc in coll.find({}, batch_size=args.batch):
            blob = doc.raw
            _id = bson.decode(blob, DECODE_OPTS)["_id"]
            batch.append((encode_key(_id), bytes(blob)))
            if len(batch) >= args.batch:
                st.insert_new(target, name, batch)
                n += len(batch)
                batch = []
        if batch:
            st.insert_new(target, name, batch)
            n += len(batch)
        indexes = {}
        for ix in src[name].list_indexes():
            ix = dict(ix)
            ixname = ix.get("name")
            if ixname == "_id_":
                continue
            spec = {"key": [(k, v) for k, v in ix["key"].items()]}
            for opt in ("unique", "sparse", "expireAfterSeconds", "partialFilterExpression"):
                if ix.get(opt) not in (None, False):
                    spec[opt] = ix[opt]
            indexes[ixname] = spec
        st.save_indexes(target, name, indexes)
        st.mark_collection(target, name)
        total += n
        print(f"[ok] {name}: {n} docs, {len(indexes)} indexes")
    st.checkpoint()
    st.close()
    print(f"done: {total} documents -> {os.path.abspath(path)} (db={target})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
