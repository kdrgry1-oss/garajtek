"""Menü Yönetimi ↔ Sayfa Tasarımı ↔ vitrin eşitliği (e2e bulguları 2. tur #27-#30).

  #27 PUT /page-blocks/header-menu 500 (datetime içe aktarılmamıştı)
  #28 Üst bar / orta menü "Varsayılana Dön" site_design'ı (vitrin kaynağı) değiştirmiyordu
  #29 Menü Yönetimi kaydı, Sayfa Tasarımı'nda gizlenen öğeyi ve Hesabım misafir yazısını siliyordu
  #30 Açık Sayfa Tasarımı'ndan "Yayınla", Menü Yönetimi değişikliğini bayat kopyayla eziyordu
"""
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
    import routes.site_menus as sm
    from routes.deps import require_admin
    from pageblocks import store, products as pbp

    db = AsyncIOMotorClient(path=str(tmp_path / "menu.db"))["test"]
    monkeypatch.setattr(cms, "db", db)
    monkeypatch.setattr(pd, "db", db)
    monkeypatch.setattr(sm, "db", db)
    store._ensured.clear()
    pbp.clear_cache()
    app = FastAPI()
    app.include_router(cms.router, prefix="/api")
    app.include_router(sm.router, prefix="/api")
    app.dependency_overrides[require_admin] = lambda: {"id": "a1", "email": "admin@example.com", "is_admin": True}
    c = TestClient(app)
    c.db = db
    return c


def _site_design(c):
    import asyncio
    doc = asyncio.run(c.db.settings.find_one({"id": "site_design"}, {"_id": 0})) or {}
    return doc.get("published") or {}


def _publish_global(c, mutate):
    """Sayfa Tasarımı'nın yaptığı gibi: global'i değiştir → taslak → yayın."""
    d = c.get("/api/page-design/home").json()
    g = d["published"]["global"]
    mutate(g)
    r = c.put("/api/page-design/home/draft", json={"blocks": d["published"]["blocks"], "global": g})
    assert r.status_code == 200, r.text
    r = c.post("/api/page-design/home/publish")
    assert r.status_code == 200, r.text


def test_header_menu_save_persists(client):
    """#27: geçerli sekmelerle kayıt 200 döner ve kalıcıdır."""
    tabs = [{"id": "t1", "label": "SYNC-SEKME", "link": "/en-yeniler"},
            {"id": "t2", "label": "Kampanya", "link": "/sale", "style": "sale", "active": False}]
    r = client.put("/api/page-blocks/header-menu", json={"tabs": tabs})
    assert r.status_code == 200, r.text
    got = client.get("/api/page-blocks/header-menu").json()["tabs"]
    assert [t["label"] for t in got] == ["SYNC-SEKME", "Kampanya"]
    assert got[1]["active"] is False and got[1]["style"] == "sale"


def test_reset_topbar_and_center_restores_storefront(client):
    """#28: Varsayılana Dön site_design'ı (vitrin) ve GET /site-menus'ü de varsayılana döndürür."""
    client.get("/api/page-design/home")  # yayın belgesi oluşsun
    r = client.put("/api/site-menus/topbar", json={"welcome": "SYNC-Hoşgeldin", "items": [
        {"id": "x1", "label": "SYNC-TopLink", "link": "/x"}]})
    assert r.status_code == 200
    r = client.put("/api/site-menus/center", json={"right_text": "SYNC-Kargo Yazısı", "right_link": "/k"})
    assert r.status_code == 200
    m = client.get("/api/site-menus").json()
    assert m["topbar"]["welcome"] == "SYNC-Hoşgeldin" and m["center"]["right_text"] == "SYNC-Kargo Yazısı"

    r = client.delete("/api/site-menus/topbar")
    assert r.status_code == 200
    assert r.json()["topbar"]["welcome"] == ""
    assert "SYNC-TopLink" not in str(r.json())
    assert client.delete("/api/site-menus/center").status_code == 200

    m = client.get("/api/site-menus").json()
    assert m["topbar"]["welcome"] == "" and m["topbar"]["customized"] is False
    assert "SYNC-TopLink" not in [it["label"] for it in m["topbar"]["items"]]
    assert "Hesabım" in [it["label"] for it in m["topbar"]["items"]]
    assert m["center"]["right_text"] == "Ücretsiz Kargo Fırsatları"
    pub = _site_design(client)
    assert pub["site_topbar"]["welcome_text"] == ""
    assert "SYNC-TopLink" not in str(pub["site_topbar"]["right_items"])
    assert all(it.get("_id") for it in pub["site_topbar"]["right_items"])
    assert pub["site_secondary_menu"]["right_text"] == "Ücretsiz Kargo Fırsatları"
    # Sayfa Tasarımı (yayın globali) da varsayılan değeri görür
    g = client.get("/api/page-design/home").json()["published"]["global"]
    assert g["site_secondary_menu"]["right_text"] == "Ücretsiz Kargo Fırsatları"


def test_topbar_save_keeps_hidden_items_guest_text_and_new_tab(client):
    """#29: Menü Yönetimi kaydı gizli öğeyi, misafir yazısını ve yeni sekme ayarını korur."""
    def mutate(g):
        items = g["site_topbar"]["right_items"]
        for it in items:
            if it["label"] == "Teknik Destek":
                it["_hidden"] = True
            if it.get("special") == "account":
                it["guest_text"] = "SYNC-Giriş"
            if it["label"] == "Mağaza":
                it["link"]["new_tab"] = True
        g["site_topbar"]["welcome_link"] = {"kind": "url", "url": "/sayfa/SYNC-wl", "new_tab": False}
    _publish_global(client, mutate)

    m = client.get("/api/site-menus").json()
    labels = [it["label"] for it in m["topbar"]["items"]]
    assert "Teknik Destek" not in labels  # panelde gizli öğe listelenmez
    r = client.put("/api/site-menus/topbar", json={"welcome": "SYNC-Hosgeldin", "items": m["topbar"]["items"]})
    assert r.status_code == 200

    pub = _site_design(client)["site_topbar"]
    by = {it["label"]: it for it in pub["right_items"]}
    assert pub["welcome_text"] == "SYNC-Hosgeldin"
    assert pub["welcome_link"]["url"] == "/sayfa/SYNC-wl"
    assert "Teknik Destek" in by and by["Teknik Destek"]["_hidden"] is True
    assert [it["label"] for it in pub["right_items"]][0] == "Teknik Destek"  # eski konumunda
    assert by["Hesabım"]["guest_text"] == "SYNC-Giriş"
    assert by["Mağaza"]["link"]["new_tab"] is True
    # Sayfa Tasarımı yayın globali de aynı
    g = client.get("/api/page-design/home").json()["published"]["global"]["site_topbar"]
    assert "Teknik Destek" in [it["label"] for it in g["right_items"]]


def test_stale_page_design_publish_keeps_menu_change(client):
    """#30: Sayfa Tasarımı açıkken Menü Yönetimi'nden yapılan değişiklik, düzenleyicinin bayat kopyasıyla
    yayınlanınca geri alınmaz (yalnız değiştirilen global anahtarlar gönderilir)."""
    d = client.get("/api/page-design/home").json()  # sekme A: yüklendi (taslak yok)
    stale_global = d["published"]["global"]
    r = client.put("/api/site-menus/topbar", json={"welcome": "SYNC-Menüden hoşgeldin",
                                                    "items": client.get("/api/site-menus").json()["topbar"]["items"]})
    assert r.status_code == 200  # sekme B
    # sekme A: yalnız tema rengini değiştirip yayınlar
    stale_global["site_theme"]["primary_color"] = "#123456"
    r = client.put("/api/page-design/home/draft", json={"blocks": d["published"]["blocks"], "global": stale_global,
                                                         "global_keys": ["site_theme"]})
    assert r.status_code == 200, r.text
    assert client.post("/api/page-design/home/publish").status_code == 200
    pub = _site_design(client)
    assert pub["site_topbar"]["welcome_text"] == "SYNC-Menüden hoşgeldin"
    assert pub["site_theme"]["primary_color"] == "#123456"
    assert client.get("/api/site-menus").json()["topbar"]["welcome"] == "SYNC-Menüden hoşgeldin"


def test_stale_page_design_with_existing_draft_keeps_menu_change(client):
    """#30 (taslak varken): Menü Yönetimi taslak globaline de yazar; düzenleyici sonraki kayıtta onu ezmez."""
    d = client.get("/api/page-design/home").json()
    g = d["published"]["global"]
    r = client.put("/api/page-design/home/draft", json={"blocks": d["published"]["blocks"], "global": g,
                                                         "global_keys": []})
    rev = r.json()["rev"]
    client.put("/api/site-menus/center", json={"right_text": "SYNC-Kargo", "right_link": "/k"})
    r = client.put("/api/page-design/home/draft", json={"blocks": d["published"]["blocks"], "global": g,
                                                         "global_keys": []}, headers={"If-Match": str(rev)})
    assert r.status_code == 200, r.text
    assert client.post("/api/page-design/home/publish").status_code == 200
    assert _site_design(client)["site_secondary_menu"]["right_text"] == "SYNC-Kargo"
