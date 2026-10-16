"""Lisans kilidi: yalnız garajtek.com (ve alt alan adları) + gerçek yerel istekler kabul edilir."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from licensing import request_allowed, is_licensed_host, LicenseMiddleware  # noqa: E402


def test_licensed_hosts():
    for h in ("garajtek.com", "www.garajtek.com", "api.garajtek.com", "GARAJTEK.COM:443", "garajtek.com."):
        assert is_licensed_host(h), h
    for h in ("garajtek.com.evil.net", "evilgarajtek.com", "example.com", "", "garajtek.co"):
        assert not is_licensed_host(h), h


def test_request_rules():
    assert request_allowed("garajtek.com", "garajtek.com", "1.2.3.4")
    assert request_allowed("127.0.0.1:8001", "", "127.0.0.1")          # sunucudaki sağlık kontrolü
    assert request_allowed("testserver", "", "testclient")             # testler
    assert not request_allowed("baskasite.com", "", "1.2.3.4")
    assert not request_allowed("baskasite.com", "baskasite.com", "127.0.0.1")
    # nginx Host'u loopback'e yazsa bile iletilen alan adı yakalanır
    assert not request_allowed("127.0.0.1", "baskasite.com", "1.2.3.4")
    assert not request_allowed("127.0.0.1", "", "1.2.3.4")              # dışarıdan gelen loopback Host
    assert not request_allowed("garajtek.com", "baskasite.com", "1.2.3.4")


def test_middleware_installed_and_blocks():
    from fastapi.testclient import TestClient
    from server import app
    assert any(m.cls is LicenseMiddleware for m in app.user_middleware)
    c = TestClient(app)
    assert c.get("/api/health").status_code == 200
    r = c.get("/api/health", headers={"host": "baskasite.com"})
    assert r.status_code == 403 and "lisansl" in r.json()["detail"]
    assert c.get("/api/health", headers={"x-forwarded-host": "baskasite.com"}).status_code == 403
