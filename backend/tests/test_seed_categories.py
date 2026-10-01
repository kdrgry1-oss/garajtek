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
    # Kısa Electro tarzı menü: Kampanyalar + Yeni Ürünler + 5 ana kategori
    assert [t["link"] for t in tabs] == ["/sale", "/en-yeniler", "/liftler", "/kompresorler",
                                         "/lastik-ekipmanlari", "/el-aletleri", "/lokma-takimlari"]
    assert tabs[0]["label"] == "Kampanyalar" and tabs[0]["style"] == "sale"
    assert len(tabs) <= 8 and all(len(t["label"]) <= 20 for t in tabs)
    assert menu["updated_by"] == sc.SEED_TAG and menu["seed_menu_version"] == sc.HEADER_MENU_VERSION
    el = next(t for t in tabs if t["link"] == "/el-aletleri")
    assert el["type"] == "mega"
    anahtar = next(c for c in el["columns"] if c["link"] == "/anahtarlar")
    assert any(i["link"] == "/yildiz-iki-agiz-anahtarlar" for i in anahtar["items"])
    # Mevcut (panelden kaydedilmiş) menü ezilmez
    menu["tabs"] = [{"id": "x", "label": "X", "type": "link", "link": "/x"}]
    run(db.settings.update_one({"id": "header_menu"}, {"$set": {"tabs": menu["tabs"]}}))
    assert run(sc.seed_header_menu(db, nodes)) is False
    assert run(db.settings.find_one({"id": "header_menu"}))["tabs"][0]["id"] == "x"


def test_header_menu_skips_missing_categories():
    nodes = [{"slug": "liftler", "name": "Liftler", "parent": None, "sort_order": 10},
             {"slug": "el-aletleri", "name": "El Aletleri", "parent": None, "sort_order": 20,
              "show_in_menu": False}]
    tabs = sc.build_header_menu(nodes)
    assert [t["link"] for t in tabs] == ["/sale", "/en-yeniler", "/liftler"]
    assert tabs[2]["type"] == "link"


def _legacy_doc(nodes, **extra):
    doc = {"id": "header_menu", "tabs": sc.build_legacy_header_menu(nodes),
           "updated_at": "2026-09-30T00:00:00+00:00", "updated_by": sc.SEED_TAG}
    doc.update(extra)
    return doc


def test_upgrade_replaces_untouched_legacy_menu(nodes):
    db = FakeDB()
    db.settings.docs.append(_legacy_doc(nodes))
    assert len(db.settings.docs[0]["tabs"]) == 15  # 14 kategori + İndirimli Ürünler
    assert run(sc.upgrade_seeded_header_menu(db, nodes)) is True
    doc = run(db.settings.find_one({"id": "header_menu"}))
    assert doc["tabs"] == sc.build_header_menu(nodes)
    assert doc["seed_menu_version"] == sc.HEADER_MENU_VERSION
    # idempotent
    assert run(sc.upgrade_seeded_header_menu(db, nodes)) is False


def test_upgrade_never_touches_admin_menu(nodes):
    # 1) Panelden kaydedilmiş (updated_by = yönetici) — içerik eski menüyle aynı olsa bile
    db = FakeDB()
    db.settings.docs.append(_legacy_doc(nodes, updated_by="owner@garajtek.com"))
    assert run(sc.upgrade_seeded_header_menu(db, nodes)) is False
    assert len(db.settings.docs[0]["tabs"]) == 15
    # 2) updated_by seed etiketi ama sekmeler değiştirilmiş (elle DB düzenlemesi)
    db = FakeDB()
    doc = _legacy_doc(nodes)
    doc["tabs"] = doc["tabs"][:3]
    db.settings.docs.append(doc)
    assert run(sc.upgrade_seeded_header_menu(db, nodes)) is False
    assert len(db.settings.docs[0]["tabs"]) == 3
    # 3) Kayıt yok → hiçbir şey yazılmaz
    db = FakeDB()
    assert run(sc.upgrade_seeded_header_menu(db, nodes)) is False
    assert db.settings.docs == []


def test_seed_if_empty_upgrades_legacy_menu_on_existing_catalog(nodes):
    db = FakeDB()
    run(sc.seed_categories(db, nodes))
    db.settings.docs.append(_legacy_doc(nodes))
    assert run(sc.seed_if_empty(db)) is None
    assert run(db.settings.find_one({"id": "header_menu"}))["tabs"][0]["label"] == "Kampanyalar"


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


# ── Vitrin görünürlüğü: gerçek "Test ..." kategorisi gizlenmemeli ─────────────

def test_storefront_filter_keeps_real_test_category_and_tree(nodes):
    from utils.category_visibility import hide_test_placeholders, is_test_placeholder

    db = FakeDB()
    run(sc.seed_categories(db, nodes))
    cats = db.categories.docs
    kept = hide_test_placeholders(cats)
    assert len(kept) == len(cats)
    ids = {c["id"] for c in kept}
    roots = [c for c in kept if not c.get("parent_id")]
    assert all(c["parent_id"] in ids for c in kept if c.get("parent_id"))  # yetim yok
    menu_roots = sorted((c for c in roots if c.get("show_in_menu") is not False),
                        key=lambda c: c["sort_order"])
    assert [c["slug"] for c in menu_roots] == [
        n["slug"] for n in nodes if not n.get("parent") and n.get("show_in_menu") is not False]
    assert len(menu_roots) == 14
    assert menu_roots[10]["slug"] == "test-ve-ariza-tespit-cihazlari"
    # Panelden açılmış (seed_source'suz) aynı isimli kategori de gizlenmez
    assert not is_test_placeholder({"id": "1", "slug": "test-ve-ariza-tespit-cihazlari",
                                    "name": "Test ve Arıza Tespit Cihazları"})
    assert not is_test_placeholder({"id": "2", "slug": "duman-kacak-test", "name": "Duman Kaçak Test"})


def test_storefront_filter_hides_placeholders_with_subtree():
    from utils.category_visibility import hide_test_placeholders

    cats = [
        {"id": "1", "slug": "liftler", "name": "Liftler", "parent_id": None},
        {"id": "HB_CAT_TEST_123", "slug": "hb-cat", "name": "HB_CAT_TEST_123", "parent_id": None},
        {"id": "3", "slug": "alt", "name": "Alt", "parent_id": "HB_CAT_TEST_123"},
        {"id": "4", "slug": "alt-alt", "name": "Alt Alt", "parent_id": "3"},
        {"id": "5", "slug": "test", "name": "Test", "parent_id": None},
        {"id": "6", "slug": "test_1", "name": "x", "parent_id": "1"},
    ]
    assert [c["id"] for c in hide_test_placeholders(cats)] == ["1"]
