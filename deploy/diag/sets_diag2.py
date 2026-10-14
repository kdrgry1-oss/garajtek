"""Salt okunur: set işaretlerindeki set id'leri şu an neyi gösteriyor + bu id'lerle ilgili denetim kayıtları."""
import sqlite3, sys
import bson
from bson.codec_options import CodecOptions
con = sqlite3.connect("file:/opt/garajtek/data/store.db?mode=ro", uri=True)
opts = CodecOptions(tz_aware=True)
def docs(coll):
    for (blob,) in con.execute("SELECT doc FROM docs WHERE coll=?", (coll,)):
        try: yield bson.decode(blob, opts)
        except Exception: continue
ids = {}
for d in docs("settings"):
    if str(d.get("id", "")).startswith("site_sets"):
        print("MARKER", d.get("id"), d.get("applied_at"), d.get("skipped"), d.get("retired"))
        for s in d.get("sets") or []:
            ids[str(s.get("id"))] = s.get("name")
print("set id'leri:", ids)
for d in docs("products"):
    if str(d.get("id")) in ids:
        print("ŞU AN", d.get("id"), "| ad:", str(d.get("name"))[:60], "| type", d.get("product_type"), "| seed", d.get("seed_source"),
              "| created", d.get("created_at"), "| updated", d.get("updated_at"), "| set_seed", d.get("set_seed"))
for coll in ("audit_logs", "stock_audit", "stock_movements", "activity_logs"):
    n = 0
    for d in docs(coll):
        eid = str(d.get("entity_id") or d.get("product_id") or "")
        if eid in ids:
            n += 1
            if n <= 15:
                print(coll, d.get("created_at") or d.get("timestamp") or d.get("at"), d.get("action") or d.get("source"),
                      eid, str(d.get("product_name") or d.get("entity_name") or "")[:40],
                      d.get("user_email") or (d.get("actor") or {}).get("email") if isinstance(d.get("actor"), dict) else d.get("user_email"))
    print(coll, "kayıt:", n)
