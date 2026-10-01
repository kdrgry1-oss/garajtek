"""services/r2_storage — yerel disk (MEDIA_DIR) fallback testleri. Ağ/boto3 gerektirmez."""
import os

import pytest

from services import r2_storage as storage

_R2_VARS = ("R2_ENDPOINT", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "R2_PUBLIC_URL")


@pytest.fixture
def local_env(monkeypatch, tmp_path):
    for v in _R2_VARS + ("MEDIA_PUBLIC_URL",):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("MEDIA_DIR", str(tmp_path / "media"))
    monkeypatch.setenv("SITE_URL", "https://garajtek.com/")
    return tmp_path / "media"


def test_disabled_without_r2_or_media_dir(monkeypatch):
    for v in _R2_VARS + ("MEDIA_DIR", "MEDIA_PUBLIC_URL"):
        monkeypatch.delenv(v, raising=False)
    assert storage.is_enabled() is False
    assert storage.backend_name() == ""
    assert storage.get_object("uploads/x.webp") == (None, None)
    with pytest.raises(RuntimeError):
        storage.put_object("uploads/x.webp", b"x")


def test_local_put_get_and_url(local_env):
    assert storage.backend_name() == "local"
    assert storage.is_enabled() is True
    url = storage.put_object("uploads/abc.webp", b"RIFFdata", "image/webp")
    assert url == "https://garajtek.com/media/uploads/abc.webp"
    path = local_env / "uploads" / "abc.webp"
    assert path.read_bytes() == b"RIFFdata"
    assert oct(os.stat(path).st_mode & 0o777) == oct(0o644)
    assert storage.get_object("/uploads/abc.webp") == (b"RIFFdata", "image/webp")
    assert storage.get_object("uploads/missing.webp") == (None, None)
    assert storage.health_check()["backend"] == "local"
    # geçici dosya kalmamalı
    assert [p.name for p in (local_env / "uploads").iterdir()] == ["abc.webp"]


def test_media_public_url_override(local_env, monkeypatch):
    monkeypatch.setenv("MEDIA_PUBLIC_URL", "https://api.garajtek.com/media/")
    url = storage.put_object("products/p1/size-table-1.jpg", b"jpg", "image/jpeg")
    assert url == "https://api.garajtek.com/media/products/p1/size-table-1.jpg"


@pytest.mark.parametrize("bad", ["../etc/passwd", "uploads/../../x", "/..", "", "a/\x00b"])
def test_path_traversal_rejected(local_env, bad):
    with pytest.raises(ValueError):
        storage.put_object(bad, b"x")
    assert storage.get_object(bad) == (None, None)


def test_r2_takes_precedence(local_env, monkeypatch):
    monkeypatch.setenv("R2_ENDPOINT", "https://acc.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "s")
    monkeypatch.setenv("R2_BUCKET", "b")
    monkeypatch.setenv("R2_PUBLIC_URL", "https://cdn.garajtek.com")
    assert storage.backend_name() == "r2"
    assert storage.public_url("uploads/a.webp") == "https://cdn.garajtek.com/uploads/a.webp"
