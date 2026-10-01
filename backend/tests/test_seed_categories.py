"""Garajtek kategori ağacı JSON'u + seed_categories idempotentliği.

DB katmanı olarak minimal bir bellek-içi Motor benzeri sahte kullanılır (motor/mongomock
gerektirmez). Seeder yalnızca find_one / insert_one / update_one(upsert) kullanır.
"""
import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import seed_categories as sc  # noqa: E402


# ── Minimal Motor-benzeri bellek-içi sahte ────────────────────────────────

def _match(doc, query):
    for k, v in query.items():
        if k == "$or":
            if not any(_match(doc, q) for q in v):
                return False
            continue
        val = doc.get(k)
        if isinstance(v, dict) and "$in" in v:
            if val not in v["$in"]:
                return False
        elif isinstance(val, list) and not isinstance(v, list):
            if v not in val:
                return False
        elif val != v:
            return False
    return True


class FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, query=None, projection=None):
        for d in self.docs:
            if _match(d, query or {}):
                return copy.deepcopy(d)
        return None

    async def insert_one(self, doc):
        self.docs.append(copy.deepcopy(doc))

    async def update_one(self, query, update, upsert=False):
        for d in self.docs:
            if _match(d, query):
                d.update(copy.deepcopy(update.get("$set", {})))
                return
        if upsert:
            new = {k: v for k, v in query.items() if not k.startswith("$")}
            new.update(copy.deepcopy(update.get("$set", {})))
            self.docs.append(new)

    async def delete_one(self, query):
        self.docs = [d for d in self.docs if not _match(d, query)]


class FakeDB:
    def __init__(self):
        self.categories = FakeCollection()
        self.settings = FakeCollection()


def run(coro):
    return asyncio.run(coro)


# ── JSON doğrulaması ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def nodes():
    return sc.load_tree()


def test_json_is_valid_and_reasonable(nodes):
    slugs = [n["slug"] for n in nodes]
    assert len(slugs) == len(set(slugs)), "slug'lar tekil olmalı"
    known = set()
    for n in nodes:
        if n.get("parent"):
            assert n["parent"] in known, f"{n['slug']}: ebeveyn önce tanımlı olmalı"
        known.add(n["slug"])
        assert n["slug"] == sc.tr_slugify(n["name"])
        assert n.get("meta_title") and n.get("meta_description")
    tops = [n for n in nodes if not n.get("parent")]
    assert 10 <= len(tops) <= 16
    assert all(n.get("icon") for n in tops)
    # 3 seviyeyi aşmaz
    by_slug = {n["slug"]: n for n in nodes}
    for n in nodes:
        depth, cur = 1, n
        while cur.get("parent"):
            cur, depth = by_slug[cur["parent"]], depth + 1
        assert depth <= 3


@pytest.mark.parametrize("name,expected", [
    ("Çekiç ve Keskiler", "cekic-ve-keskiler"),
    ("Yağlama Ekipmanları", "yaglama-ekipmanlari"),
    ("Işık", "isik"),
    ("İKİ SÜTUNLU LİFTLER", "iki-sutunlu-liftler"),
    ("Özel Aparatlar", "ozel-aparatlar"),
    ("Şanzıman Krikoları", "sanziman-krikolari"),
    ("Sökme & Takma", "sokme-takma"),
    ("Kaynak, Kesme ve Aydınlatma", "kaynak-kesme-ve-aydinlatma"),
])
def test_tr_slugify(name, expected):
    assert sc.tr_slugify(name) == expected


def test_validate_rejects_bad_trees():
    good = {"slug": "liftler", "name": "Liftler", "parent": None, "sort_order": 1}
    with pytest.raises(ValueError):
        sc.validate_tree([good, dict(good)])  # tekrar
    with pytest.raises(ValueError):
        sc.validate_tree([{"slug": "x", "name": "X", "parent": "yok"}])  # ebeveyn yok
    with pytest.raises(ValueError):
        sc.validate_tree([{"slug": "gi-yi-m", "name": "GİYİM"}])  # bozuk İ slug'ı


# ── Seed idempotentliği ───────────────────────────────────────────────────

def test_seed_is_idempotent_and_preserves_ids(nodes):
    db = FakeDB()
    s1 = run(sc.seed_categories(db, nodes))
    assert s1["created"] == len(nodes) and s1["updated"] == 0
    ids_before = {d["slug"]: d["id"] for d in db.categories.docs}
    assert len(set(ids_before.values())) == len(nodes)

    s2 = run(sc.seed_categories(db, nodes))
    assert s2 == {"created": 0, "updated": 0, "unchanged": len(nodes)}
    assert len(db.categories.docs) == len(nodes)
    assert {d["slug"]: d["id"] for d in db.categories.docs} == ids_before

    # ebeveyn bağları doğru
    by_slug = {d["slug"]: d for d in db.categories.docs}
    for n in nodes:
        pid = by_slug[n["slug"]]["parent_id"]
        assert pid == (by_slug[n["parent"]]["id"] if n.get("parent") else None)


def test_seed_keeps_admin_edits_and_never_deletes(nodes):
    db = FakeDB()
    # Panelde önceden oluşturulmuş, adı özelleştirilmiş kategori + ağaçta olmayan kategori
    run(db.categories.insert_one({"id": "42", "slug": "liftler", "name": "Araç Liftleri",
                                  "parent_id": None, "sort_order": 5}))
    run(db.categories.insert_one({"id": "77", "slug": "eski-kategori", "name": "Eski"}))
    run(sc.seed_categories(db, nodes))
    lift = run(db.categories.find_one({"slug": "liftler"}))
    assert lift["id"] == "42" and lift["name"] == "Araç Liftleri"  # isim ezilmedi
    assert lift["meta_title"]  # eksik alan dolduruldu
    assert run(db.categories.find_one({"id": "77"}))  # silinmedi
    child = run(db.categories.find_one({"slug": "makasli-liftler"}))
    assert child["parent_id"] == "42"

    # --force: seed alanları JSON'a çekilir, id yine korunur
    run(sc.seed_categories(db, nodes, force=True))
    lift = run(db.categories.find_one({"slug": "liftler"}))
    assert lift["id"] == "42" and lift["name"] == "Liftler"


def test_seed_matches_slug_aliases(nodes):
    db = FakeDB()
    run(db.categories.insert_one({"id": "9", "slug": "kompresor", "slug_aliases": ["kompresorler"],
                                  "name": "Kompresör"}))
    run(sc.seed_categories(db, nodes))
    assert not any(d["slug"] == "kompresorler" for d in db.categories.docs)
    child = run(db.categories.find_one({"slug": "pistonlu-kompresorler"}))
    assert child["parent_id"] == "9"


def test_header_menu_seed(nodes):
    db = FakeDB()
    assert run(sc.seed_header_menu(db, nodes)) is True
    menu = run(db.settings.find_one({"id": "header_menu"}))
    tabs = menu["tabs"]
    tops = [n for n in nodes if not n.get("parent") and n.get("show_in_menu") is not False]
    assert [t["link"] for t in tabs[:-1]] == [f"/{n['slug']}" for n in tops]
    assert tabs[-1]["link"] == "/sale"
    el = next(t for t in tabs if t["link"] == "/el-aletleri")
    assert el["type"] == "mega"
    anahtar = next(c for c in el["columns"] if c["link"] == "/anahtarlar")
    assert any(i["link"] == "/yildiz-iki-agiz-anahtarlar" for i in anahtar["items"])
    # Mevcut (panelden kaydedilmiş) menü ezilmez
    menu["tabs"] = [{"id": "x", "label": "X", "type": "link", "link": "/x"}]
    run(db.settings.update_one({"id": "header_menu"}, {"$set": {"tabs": menu["tabs"]}}))
    assert run(sc.seed_header_menu(db, nodes)) is False
    assert run(db.settings.find_one({"id": "header_menu"}))["tabs"][0]["id"] == "x"


def test_seed_if_empty_only_on_empty_collection():
    db = FakeDB()
    stats = run(sc.seed_if_empty(db))
    assert stats and stats["created"] > 0
    assert run(db.settings.find_one({"id": "header_menu"}))
    assert run(sc.seed_if_empty(db)) is None  # dolu → dokunmaz


def test_json_file_is_utf8_turkish():
    raw = json.loads((BACKEND / "data" / "garajtek_categories.json").read_text(encoding="utf-8"))
    names = {c["name"] for c in raw["categories"]}
    assert "Takım Arabaları ve Tezgahlar" in names and "Özel Aparatlar" in names
