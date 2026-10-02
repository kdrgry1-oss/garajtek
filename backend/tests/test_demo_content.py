"""Demo içerik paketi (v2): görseller mevcut, kategoriler tohum ağacında, setler tutarlı ve
panelin "Demo içerik yükle" akışı hem BOŞ veritabanında hem ESKİ (v1) demo yüklü veritabanında
idempotent çalışır (eski kayıtlar kaldırılır, yenileri eklenir)."""
import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import demo_content as dc  # noqa: E402
from seed_categories import load_tree, seed_categories  # noqa: E402


def test_demo_images_exist_and_small():
    total = 0
    for row in dc.P:
        for n in range(1, row["images"] + 1):
            p = os.path.join(dc.IMG_DIR, "products", f"{row['key']}-{n}.webp")
            assert os.path.isfile(p), p
            total += os.path.getsize(p)
    for st in dc.SETS:
        for n in (1, 2):
            assert os.path.isfile(os.path.join(dc.IMG_DIR, "products", f"{st['key']}-{n}.webp"))
    for key, *_ in dc.HEROES:
        for suffix in ("", "-m"):
            p = os.path.join(dc.IMG_DIR, "banners", f"{key}{suffix}.webp")
            assert os.path.isfile(p), p
            total += os.path.getsize(p)
    for key, *_ in dc.SMALL + [dc.WIDE] + dc.ADS:
        assert os.path.isfile(os.path.join(dc.IMG_DIR, "banners", f"{key}.webp"))
    for i in range(len(dc.BRANDS)):
        assert os.path.isfile(os.path.join(dc.IMG_DIR, "brands", f"brand-{i + 1}.png"))
    assert total < 8 * 1024 * 1024


def test_catalog_shape():
    assert 20 <= len(dc.P) <= 25
    keys = [p["key"] for p in dc.P]
    assert len(keys) == len(set(keys))
    slugs = {n["slug"] for n in load_tree()}
    assert not {s for p in dc.P for s in p["cats"] if s not in slugs}
    assert "urun-setleri" in slugs
    assert any(p["stock"] == 0 for p in dc.P), "stok 0 test ürünü olmalı"
    assert any(p["sale"] for p in dc.P) and any(p["variants"] for p in dc.P)
    assert any(p["cod_disabled"] for p in dc.P)
    for p in dc.P:
        assert p["price"] > 0 and (p["sale"] is None or p["sale"] < p["price"])
        assert all(p["dims"]) and p["kg"] > 0, p["key"]
        # referans mağazaların marka adları ürün markası/adı olarak kullanılmaz
        assert "grayzer" not in (p["name"] + p["brand"]).lower()
        assert "alg" != p["brand"].lower()
    assert "Grayzer" not in dc.BRANDS


def test_sets_reference_known_products_and_one_has_out_of_stock_component():
    by_key = {p["key"]: p for p in dc.P}
    oos_sets = 0
    for st in dc.SETS:
        assert len(st["items"]) >= 2 and 0 < st["pct"] <= 20
        for key, qty, vname in st["items"]:
            assert key in by_key, key
            if vname:
                assert vname in [v for v, _ in by_key[key]["variants"] or []], (key, vname)
        if any(by_key[k]["stock"] == 0 for k, _, _ in st["items"]):
            oos_sets += 1
            # Tükenen bileşenin en alt kategorisinde stoklu yedek ürün olmalı (değiştir akışı)
            oos = next(by_key[k] for k, _, _ in st["items"] if by_key[k]["stock"] == 0)
            assert any(p is not oos and p["stock"] > 0 and oos["cats"][0] in p["cats"] for p in dc.P)
    assert oos_sets >= 1


# ── Yükleme akışı (gerçek localdb, panelin create_product taklidiyle) ──────────────

def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    return AsyncIOMotorClient(path=str(tmp_path / "demo.db"))["test"]


@pytest.fixture
def fake_store(monkeypatch):
    """routes.upload.store_image_bytes / delete_stored_file → bellek içi (dosya kaydı db.files)."""
    import types
    mod = types.ModuleType("routes.upload")
    state = {"n": 0, "db": None}

    async def store_image_bytes(data, ctype, ext, name, extra=None):
        state["n"] += 1
        rec = {"id": f"f{state['n']}", "storage_path": f"{name}", **(extra or {})}
        await state["db"].files.insert_one(rec)
        return {"url": f"/api/upload/files/{name}"}

    async def delete_stored_file(rec):
        await state["db"].files.delete_one({"id": rec["id"]})

    mod.store_image_bytes = store_image_bytes
    mod.delete_stored_file = delete_stored_file
    pkg = types.ModuleType("routes")
    pkg.__path__ = [str(ROOT / "routes")]
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.upload", mod)
    monkeypatch.setitem(sys.modules, "home_layout", types.ModuleType("home_layout"))
    return state


def _creator(db):
    counter = {"n": 0}

    async def create(data):
        counter["n"] += 1
        pid = f"p{counter['n']}"
        doc = {k: data.get(k) for k in ("name", "price", "sale_price", "images", "stock", "brand", "is_active",
                                         "description", "short_description", "stock_code")}
        cats = data.get("categories") or []
        variants = [{**v, "id": f"{pid}-v{i}"} for i, v in enumerate(data.get("variants") or [])]
        doc.update(id=pid, slug=f"s-{pid}", category_id=cats[0] if cats else "", category_ids=cats,
                   categories=cats, variants=variants)
        if variants:
            doc["stock"] = sum(v["stock"] for v in variants)
        await db.products.insert_one(doc)
        return {"id": pid}
    return create


def test_load_on_fresh_db_then_upgrade_from_v1(db, fake_store):
    fake_store["db"] = db
    _run(seed_categories(db, load_tree()))
    # Eski (v1) demo + yöneticinin kendi ürünü
    _run(db.products.insert_one({"id": "old1", "name": "Eski demo", "demo": True, "seed_source": "garajtek_demo_v1"}))
    _run(db.banners.insert_one({"id": "demo-hero-1", "demo": True, "seed_source": "garajtek_demo_v1"}))
    _run(db.products.insert_one({"id": "real1", "name": "Gerçek ürün"}))
    st0 = _run(dc.demo_status(db))
    assert st0["outdated"] is True

    res = _run(dc.load_demo(db, _creator(db)))
    assert res["created_products"] == len(dc.P) and res["created_sets"] == len(dc.SETS)
    assert res["replaced"]["removed_products"] == 1
    assert not _run(db.products.find_one({"id": "old1"}))
    assert _run(db.products.find_one({"id": "real1"}))
    st = _run(dc.demo_status(db))
    assert st["products"] == len(dc.P) and st["sets"] == len(dc.SETS) and st["outdated"] is False

    sets = _run(db.products.find({"product_type": "set"}, {"_id": 0}).to_list(10))
    cat = _run(db.categories.find_one({"slug": "urun-setleri"}))
    for s in sets:
        assert s["category_id"] == cat["id"] and s["seed_source"] == dc.DEMO_TAG
        assert s["price"] > 0 and s["sale_price"] < s["price"]
        assert len(s["set_items"]) >= 2
    lift = _run(db.products.find_one({"name": {"$regex": "^4 Ton"}}))
    assert lift["cod_disabled"] is True and lift["width"] == 300 and lift["cargo_weight"] > 0
    # teknik özellikler ekipman şablonunun kanonik anahtarlarıyla (product_specs) yazılır
    assert lift["specs"].get("lifting_capacity_kg") == 4000 or lift["specs"].get("kapasite_ton") == 4
    assert lift["variant_labels"] == {"size": "Elektrik Bağlantısı"}

    # Sayfa Tasarımı v2: boş görsel alanları demo görselleriyle dolar (yeni alan yolları)
    pub = _run(db.page_layouts.find_one({"id": "home:published"}, {"_id": 0}))
    by = {b["type"]: b["settings"] for b in pub["blocks"]}
    assert all(s["background"]["url"].startswith("/api/upload/files/") for s in by["hero_slider"]["slides"])
    assert by["ads_block"]["items"][0]["image"]["url"].startswith("/api/upload/files/")
    assert by["full_banner"]["image"]["url"] and by["brands_carousel"]["source"] == "manual"
    assert _run(db.page_blocks.count_documents({"type": "hero_slider"})) == 1  # yayın aynası

    # İkinci yükleme idempotent: sayılar aynı kalır
    _run(dc.load_demo(db, _creator(db)))
    st2 = _run(dc.demo_status(db))
    assert (st2["products"], st2["sets"]) == (len(dc.P), len(dc.SETS))
    assert _run(db.banners.count_documents({"id": "demo-hero-1"})) == 1

    rm = _run(dc.remove_demo(db))
    assert rm["removed_products"] == len(dc.P) + len(dc.SETS)
    assert _run(db.products.count_documents({})) == 1  # yalnız gerçek ürün kaldı
    assert _run(db.files.count_documents({})) == 0
    pub = _run(db.page_layouts.find_one({"id": "home:published"}, {"_id": 0}))
    by = {b["type"]: b["settings"] for b in pub["blocks"]}
    assert not any(s.get("background") for s in by["hero_slider"]["slides"])  # demo slaytları kaldırıldı
    assert by["full_banner"]["image"] is None and by["brands_carousel"]["source"] == "catalog"
