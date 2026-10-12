"""Aktarılan ürünlerden hazır ürün setleri (sahip talebi 12.10.2026) — BİR KEZ oluşturulur.

Referans mağazalardaki "servis paketleri" yalnız görseldi; burada her set gerçek bileşen ürünlerden
oluşur ve tek tıkla (tek sepet işlemiyle) sepete eklenir. Sözleşme 7.2: 100 ürünlük set de var.
Bileşenler stokta ve yayında olan, toplu aktarılmış (site_import_v1) ürünlerden seçilir; seçim sabit
tohumlu rastgele (her kurulumda aynı). Setler panelde Katalog › Ürün Setleri'nden düzenlenir/silinir;
silinen set tekrar oluşturulmaz (işaret: settings.id=MARKER).
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Dict, List

logger = logging.getLogger("site_sets")

MARKER = "site_sets_2026_10_12_v1"
SEED_SOURCE = "site_import_v1"

# (ad, açıklama, indirim %, [(kategori slug'ı, adet)], öne çıkar)
SETS = [
    ("Oto Servis Başlangıç Seti",
     "Yeni açılan oto servisler için temel ekipman: kriko, mengene, takım arabası, lokma ve anahtar takımları, "
     "pense, çekiç ve aydınlatma. Tek tıkla sepete ekleyin; set indirimi otomatik uygulanır.",
     6, [("yer-krikolari", 1), ("mengeneler", 1), ("takim-arabalari", 1), ("lokma-setleri", 1),
         ("anahtar-takimlari", 1), ("penseler", 2), ("tornavidalar", 1), ("cekic-ve-keskiler", 1),
         ("led-lambalar-ve-calisma-isiklari", 1), ("yatma-tahtalari-ve-tamirci-koltuklari", 1)], True),
    ("Lastikçi Açılış Seti",
     "Lastik servisi kurulumu için sökme-takma ve balans makinesi, havalı somun sökme, lastik şişirme ve "
     "tamir malzemeleri tek pakette.",
     5, [("lastik-sokme-takma-makineleri", 1), ("lastik-balans-makineleri", 1), ("havali-somun-sokme-makineleri", 1),
         ("lastik-sisirme-cihazlari", 1), ("lastik-tamir-malzemeleri", 2), ("hava-hortumlari-ve-makaralari", 1),
         ("darbeli-lokmalar", 1)], True),
    ("Bakım Kimyasalları Paketi",
     "Motor, fren, yakıt sistemi ve radyatör bakımı için temizleyici spreyler, katkılar ve sıvı conta.",
     8, [("temizleme-ve-bakim-spreyleri", 4), ("yakit-motor-ve-radyator-katkilari", 3),
         ("sivi-conta-ve-yapistiricilar", 1)], False),
    ("Arıza Tespit ve Test Seti",
     "Akü test, oto test kitleri, kontrol kalemleri, steteskop ve ölçüm cihazlarından oluşan teşhis paketi.",
     6, [("aku-test-ve-takviye-cihazlari", 1), ("oto-test-kitleri", 2), ("kontrol-kalemleri-ve-olcum-cihazlari", 3),
         ("antifriz-ve-sivi-olcerler", 1), ("olcum-aletleri", 1)], False),
]
BIG_SET = ("Atölye Kurulum Seti — 100 Ürün",
           "Bir atölyeyi baştan donatan 100 farklı ürün: el aletleri, lokma ve anahtar takımları, test cihazları, "
           "atölye ekipmanları ve sarf malzemeleri. Tamamı tek tıkla sepete eklenir; stokta olmayan bir ürünü "
           "sepette aynı kategoriden başka bir ürünle değiştirebilirsiniz.",
           10, 100)
BIG_ROOTS = ["el-aletleri", "lokma-takimlari", "test-ve-ariza-tespit-cihazlari", "atolye-ekipmanlari-ve-sarf",
             "bakim-kimyasallari-ve-spreyler", "yaglama-ekipmanlari", "ozel-aparatlar", "havali-aletler",
             "kaynak-kesme-ve-aydinlatma", "oto-aksesuar-ve-arac-koruma"]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _pool(db, cat_ids) -> List[dict]:
    ids = [cat_ids] if isinstance(cat_ids, str) else list(cat_ids)
    q = {"seed_source": SEED_SOURCE, "is_active": True, "stock": {"$gt": 0}, "product_type": {"$ne": "set"},
         "is_deleted": {"$ne": True}, "price": {"$gt": 0},
         "$or": [{"category_ids": {"$in": ids}}, {"category_id": {"$in": ids}}]}
    rows = await db.products.find(q, {"_id": 0, "id": 1, "name": 1, "variants": 1}).to_list(5000)
    return [r for r in rows if not (r.get("variants") or [])]  # varyantlı ürün sette seçim gerektirir


async def build_plan(db, rng: random.Random) -> List[dict]:
    rows = await db.categories.find({}, {"_id": 0, "id": 1, "slug": 1, "parent_id": 1}).to_list(5000)
    cats = {c.get("slug"): str(c.get("id")) for c in rows if c.get("slug")}
    kids: Dict[str, List[str]] = {}
    for c in rows:
        if c.get("parent_id"):
            kids.setdefault(str(c["parent_id"]), []).append(str(c["id"]))

    def subtree(cid: str) -> List[str]:
        out, todo = [], [cid]
        while todo:
            x = todo.pop()
            if x not in out:
                out.append(x)
                todo += kids.get(x, [])
        return out

    plans = []
    used_big: set = set()
    for name, desc, pct, parts, featured in SETS:
        picked: List[str] = []
        for slug, n in parts:
            if slug not in cats:
                continue
            pool = [p["id"] for p in await _pool(db, subtree(cats[slug])) if p["id"] not in picked]
            rng.shuffle(pool)
            picked += pool[:n]
        if len(picked) >= 3:
            plans.append({"name": name, "description": desc, "pct": pct, "ids": picked, "featured": featured})
    name, desc, pct, size = BIG_SET
    pool_ids: List[str] = []
    for slug in BIG_ROOTS:
        if slug in cats:
            for p in await _pool(db, subtree(cats[slug])):
                if p["id"] not in used_big:
                    used_big.add(p["id"])
                    pool_ids.append(p["id"])
    rng.shuffle(pool_ids)
    if len(pool_ids) >= size:
        plans.append({"name": name, "description": desc, "pct": pct, "ids": pool_ids[:size], "featured": True})
    return plans


async def create_sets_once(db, *, create_set) -> Dict:
    """create_set(data) → set belgesi (routes.product_sets.create_set_product sarmalayıcısı)."""
    if await db.settings.find_one({"id": MARKER}, {"_id": 1}):
        return {"skipped": "done"}
    plans = await build_plan(db, random.Random(20261012))
    if not any(len(p["ids"]) >= 100 for p in plans):
        return {"skipped": "not_enough_products", "plans": len(plans)}  # aktarım bitmemiş → sonraki açılış
    made = []
    for p in plans:
        doc = await create_set({
            "name": p["name"], "description": f"<p>{p['description']}</p>", "short_description": p["description"][:300],
            "set_items": [{"product_id": pid, "quantity": 1} for pid in p["ids"]],
            "set_discount_pct": p["pct"], "is_active": True, "is_featured": p["featured"],
            "meta_title": f"{p['name']} | GarajTek", "meta_description": p["description"][:155],
        })
        await db.products.update_one({"id": doc["id"]}, {"$set": {"set_seed": MARKER}})
        made.append({"id": doc["id"], "name": p["name"], "items": len(p["ids"])})
    await db.settings.update_one({"id": MARKER}, {"$set": {"id": MARKER, "sets": made, "applied_at": _now()}},
                                 upsert=True)
    return {"created": made}
