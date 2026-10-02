"""Sayfa Tasarımı v2 uçları (SPEC §5.2): taslak (If-Match), atomik yayın, revizyon/geri yükleme, public
güvenlik (inaktif blok sızmaz), site-design, resolve-products, 410 eski uçlar."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from localdb import AsyncIOMotorClient
    import routes.cms as cms
    import routes.page_design as pd
    from routes.deps import require_admin
    from pageblocks import store, products as pbp

    db = AsyncIOMotorClient(path=str(tmp_path / "api.db"))["test"]
    monkeypatch.setattr(cms, "db", db)
    monkeypatch.setattr(pd, "db", db)
    store._ensured.clear()
    pbp.clear_cache()
    app = FastAPI()
    app.include_router(cms.router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: {"id": "a1", "email": "admin@example.com", "is_admin": True}
    c = TestClient(app)
    c.db = db
    return c


def _layout(c):
    r = c.get("/api/page-design/home")
    assert r.status_code == 200, r.text
    return r.json()


def test_initial_layout_is_template_default(client):
    d = _layout(client)
    assert d["draft"] is None and d["published"]["rev"] == 1
    assert [b["type"] for b in d["published"]["blocks"]][:3] == ["hero_slider", "ads_block", "deals_tabs"]
    assert d["published"]["global"]["site_header"]["variant"] == "v1"
    pub = client.get("/api/page-blocks?page=home").json()
    assert len(pub) == 9 and pub[0]["settings"]["slides"][0]["title"].startswith("YENİ NESİL")


def test_draft_if_match_conflict_publish_and_leak_fix(client):
    d = _layout(client)
    blocks = d["published"]["blocks"]
    blocks[1]["settings"]["items"][0]["text"] = "Taslak <strong>metni</strong>"
    blocks[2]["is_active"] = False
    r = client.put("/api/page-design/home/draft", json={"blocks": blocks, "global": d["published"]["global"]})
    assert r.status_code == 200, r.text
    rev = r.json()["rev"]
    # taslak vitrine sızmaz
    pub = client.get("/api/page-blocks?page=home").json()
    assert "Taslak" not in str(pub)
    # yanlış If-Match → 409 + güncel taslak
    r2 = client.put("/api/page-design/home/draft", json={"blocks": blocks}, headers={"If-Match": "999"})
    assert r2.status_code == 409 and r2.json()["draft"]["rev"] == rev
    r3 = client.put("/api/page-design/home/draft", json={"blocks": blocks}, headers={"If-Match": str(rev)})
    assert r3.status_code == 200 and r3.json()["rev"] == rev + 1
    # yayın
    r4 = client.post("/api/page-design/home/publish")
    assert r4.status_code == 200, r4.text
    assert r4.json()["rev"] == 2
    pub = client.get("/api/page-blocks?page=home").json()
    assert "Taslak <strong>metni</strong>" in str(pub)
    assert blocks[2]["id"] not in [b["id"] for b in pub]  # inaktif blok public'te YOK
    assert _layout(client)["draft"] is None
    # ayna
    import asyncio
    n = asyncio.run(client.db.page_blocks.count_documents({"page": "home"}))
    assert n == 9


def test_publish_validation_errors_block_publish(client):
    d = _layout(client)
    blocks = d["published"]["blocks"]
    blocks[0]["settings"]["slides"] = []
    client.put("/api/page-design/home/draft", json={"blocks": blocks})
    r = client.post("/api/page-design/home/publish")
    assert r.status_code == 422
    errs = r.json()["errors"]
    assert any("Ana Slider" in e["label"] and "En az 1" in e["message"] for e in errs)
    assert client.get("/api/page-blocks?page=home").json()[0]["settings"]["slides"]  # canlı bozulmadı


def test_unknown_type_rejected(client):
    r = client.put("/api/page-design/home/draft", json={"blocks": [{"type": "yok", "settings": {}}]})
    assert r.status_code == 422


def test_revisions_and_restore(client):
    d = _layout(client)
    blocks = d["published"]["blocks"]
    blocks[5]["settings"]["link"] = {"kind": "url", "url": "/ilk"}
    client.put("/api/page-design/home/draft", json={"blocks": blocks})
    client.post("/api/page-design/home/publish")
    blocks[5]["settings"]["link"] = {"kind": "url", "url": "/ikinci"}
    client.put("/api/page-design/home/draft", json={"blocks": blocks}, headers={"If-Match": "0"})
    r = client.get("/api/page-design/home")
    client.put("/api/page-design/home/draft", json={"blocks": blocks}, headers={"If-Match": str((r.json()["draft"] or {}).get("rev", 0))})
    client.post("/api/page-design/home/publish")
    revs = client.get("/api/page-design/home/revisions").json()["items"]
    assert [x["rev"] for x in revs][:3] == [3, 2, 0] or [x["rev"] for x in revs][:2] == [3, 2]
    assert "değişti" in revs[0]["summary"]
    one = client.get("/api/page-design/home/revisions/2").json()
    assert one["blocks"][5]["settings"]["link"]["url"] == "/ilk"
    r = client.post("/api/page-design/home/revisions/2/restore")
    assert r.status_code == 200 and r.json()["draft"]["restored_from"] == 2
    assert _layout(client)["draft"]["blocks"][5]["settings"]["link"]["url"] == "/ilk"
    assert client.delete("/api/page-design/home/draft").json()["deleted"] is True


def test_global_draft_publish_site_design(client):
    d = _layout(client)
    g = d["published"]["global"]
    g["site_theme"]["primary_color"] = "#0787ea"
    g["site_newsletter"]["title"] = "Fırsat Bülteni"
    client.put("/api/page-design/home/draft", json={"blocks": d["published"]["blocks"], "global": g})
    assert client.get("/api/site-design").json()["site_theme"]["primary_color"] == "#fed700"
    client.post("/api/page-design/home/publish")
    sd = client.get("/api/site-design").json()
    assert sd["site_theme"]["primary_color"] == "#0787ea" and sd["site_newsletter"]["title"] == "Fırsat Bülteni"


def test_schemas_validate_media_endpoints(client):
    s = client.get("/api/page-design/schemas").json()
    assert "hero_slider" in s["blocks"] and "site_theme" in s["globals"] and "section" in s["common"]
    v = client.post("/api/page-design/validate", json={"block": {"type": "full_banner", "settings": {
        "link": {"kind": "url", "url": "javascript:x"}}}}).json()
    assert v["errors"] and v["errors"][0]["path"] == "settings.link"
    assert client.get("/api/page-design/media").json() == {"items": []}


def test_old_endpoints_gone_and_install_default_to_draft(client):
    assert client.post("/api/page-blocks/seed-default-home").status_code == 410
    assert client.post("/api/page-blocks", json={}).status_code == 410
    assert client.put("/api/page-blocks/x", json={}).status_code == 410
    r = client.post("/api/page-blocks/install-default-home?replace=true")
    assert r.status_code == 200 and r.json()["created"] == 9
    assert _layout(client)["draft"] is not None


def test_resolve_products(client):
    import asyncio

    async def seed():
        for i in range(8):
            await client.db.products.insert_one({
                "id": f"p{i}", "name": f"Ürün {i}", "slug": f"urun-{i}", "price": 100 + i,
                "sale_price": 90 if i % 2 else 0, "is_active": True, "is_featured": i < 3, "stock": 0 if i == 1 else 5,
                "category_id": "c1" if i < 4 else "c2", "category_ids": ["root", "c1" if i < 4 else "c2"],
                "sales_count": i * 10, "created_at": f"2026-01-0{i + 1}T00:00:00", "cost_price": 1})
        await client.db.products.insert_one({"id": "gone", "name": "Silik", "is_active": False, "price": 1})
    asyncio.run(seed())
    r = client.post("/api/page-blocks/resolve-products", json={"sources": [
        {"kind": "featured", "limit": 6},
        {"kind": "discounted", "limit": 10, "exclude_out_of_stock": True},
        {"kind": "best_sellers", "limit": 3},
        {"kind": "newest", "limit": 2},
        {"kind": "category", "category_ids": ["c2"], "limit": 10},
        {"kind": "manual", "product_ids": ["p5", "gone", "p2"]},
        {"kind": "category", "category_ids": ["root"], "limit": 2, "include_children": True},
        {"kind": "featured", "limit": 5, "fill_with": "newest"},
        {"kind": "popular", "limit": 2},
    ]})
    assert r.status_code == 200, r.text
    res = r.json()["results"]
    ids = [[p["id"] for p in x] for x in res]
    assert set(ids[0]) == {"p0", "p1", "p2"} and ids[0][-1] == "p1"  # tükenen sona
    assert set(ids[1]) == {"p3", "p5", "p7"}  # p1 stoksuz hariç
    assert ids[2] == ["p7", "p6", "p5"]
    assert ids[3] == ["p7", "p6"]
    assert set(ids[4]) == {"p4", "p5", "p6", "p7"}
    assert ids[5] == ["p5", "p2"]
    assert len(ids[6]) == 2
    assert len(ids[7]) == 5 and set(ids[7][:2]) <= {"p0", "p2", "p1"}
    assert ids[8] == ["p7", "p6"]
    assert "cost_price" not in res[0][0]


def test_resolve_products_ratings_from_reviews(client):
    """Onaylı yorumların ortalaması kartlara `rating`/`review_count` olarak eklenir; top_rated buna göre sıralanır."""
    import asyncio

    async def seed():
        for i in range(3):
            await client.db.products.insert_one({"id": f"r{i}", "name": f"R {i}", "slug": f"r-{i}", "price": 10,
                                                 "is_active": True, "stock": 5, "created_at": f"2026-02-0{i + 1}T00:00:00"})
        for pid, rt, st in [("r1", 5, "approved"), ("r1", 4, "approved"), ("r2", 3, "approved"), ("r0", 5, "pending")]:
            await client.db.reviews.insert_one({"id": f"{pid}{rt}", "product_id": pid, "rating": rt, "status": st})
    asyncio.run(seed())
    r = client.post("/api/page-blocks/resolve-products", json={"sources": [
        {"kind": "top_rated", "limit": 3}, {"kind": "manual", "product_ids": ["r0", "r1"]}]})
    res = r.json()["results"]
    assert [p["id"] for p in res[0]][:2] == ["r1", "r2"]
    m = {p["id"]: p for p in res[1]}
    assert m["r1"]["rating"] == 4.5 and m["r1"]["review_count"] == 2
    assert "rating" not in m["r0"] or not m["r0"]["rating"]  # bekleyen yorum sayılmaz
