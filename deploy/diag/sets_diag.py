"""Salt okunur tanı: ürün setleri nerede? (canlı store.db'yi ?mode=ro ile açar, hiçbir şey yazmaz)."""
import sqlite3, sys
import bson
from bson.codec_options import CodecOptions

path = sys.argv[1] if len(sys.argv) > 1 else "/opt/garajtek/data/store.db"
con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
opts = CodecOptions(tz_aware=True)
def docs(coll):
    for (blob,) in con.execute("SELECT doc FROM docs WHERE coll=?", (coll,)):
        try:
            yield bson.decode(blob, opts)
        except Exception:
            continue
sets, by_name = [], []
for d in docs("products"):
    n = str(d.get("name") or "")
    if d.get("product_type") == "set" or d.get("set_items") or d.get("set_seed"):
        sets.append(d)
    elif any(k in n for k in ("Başlangıç Seti", "Servis Seti", "Paketi", "Açılış Seti")):
        by_name.append(d)
print("SET belgeleri:", len(sets))
for d in sets[:40]:
    print("  ", d.get("id"), "|", str(d.get("name"))[:50], "| type", d.get("product_type"), "| active", d.get("is_active"),
          "| deleted", d.get("is_deleted"), "| items", len(d.get("set_items") or []), "| stock", d.get("stock"),
          "| deact", d.get("deactivated_reason"))
print("Adı set gibi ama türü set olmayan:", len(by_name))
for d in by_name[:20]:
    print("  ", d.get("id"), "|", str(d.get("name"))[:50], "| type", d.get("product_type"), "| active", d.get("is_active"))
for coll in ("settings",):
    for d in docs(coll):
        if "set" in str(d.get("id", "")).lower() and ("site_sets" in str(d.get("id")) or "sets" in d):
            print("MARKER", d.get("id"), "| sets:", [(s.get("name"), s.get("items")) for s in (d.get("sets") or [])][:12])
n = 0
for d in docs("audit_logs"):
    a = str(d.get("action") or "")
    if ("delete" in a or "trash" in a) and d.get("entity_type") in ("product", "product_set"):
        nm = str(((d.get("before") or {}).get("name")) or d.get("entity_name") or "")
        if "Set" in nm or "Paket" in nm:
            n += 1
            if n <= 20:
                print("SİLME", d.get("created_at") or d.get("timestamp"), a, d.get("entity_id"), nm[:50],
                      (d.get("actor") or {}).get("email") if isinstance(d.get("actor"), dict) else d.get("user_email"))
print("set silme denetim kaydı:", n)
