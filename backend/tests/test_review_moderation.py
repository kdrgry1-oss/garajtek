"""Panel yorum düzenleme: ilk metin saklanır, vitrine 'düzenlendi' bilgisi gider ama ilk metin gitmez."""
import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(c):
    return asyncio.run(c)


@pytest.fixture
def E(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    import routes.extras as extras
    tdb = AsyncIOMotorClient(path=str(tmp_path / "rv.db"))["test"]
    monkeypatch.setattr(extras, "db", tdb)
    run(tdb.reviews.insert_one({"id": "r1", "product_id": "p1", "rating": 5, "title": "Süper",
                                "comment": "argo kelime içeren yorum", "status": "pending",
                                "user_id": "u1", "created_at": "2026-10-01"}))
    return extras, tdb


ADMIN = {"email": "admin@x", "role": "admin"}


def test_edit_keeps_original_and_hides_it_publicly(E):
    extras, tdb = E
    run(extras.update_review("r1", {"comment": "*** içeren yorum", "status": "approved"}, current_user=ADMIN))
    run(extras.update_review("r1", {"comment": "temiz yorum"}, current_user=ADMIN))
    r = run(tdb.reviews.find_one({"id": "r1"}, {"_id": 0}))
    assert r["comment"] == "temiz yorum" and r["is_edited"] is True
    assert r["original_comment"] == "argo kelime içeren yorum"   # ilk metin, ikinci düzenlemede ezilmez
    assert r["original_title"] == "Süper" and r["edited_by"] == "admin@x"
    pub = run(extras.list_approved_reviews("p1", limit=10))["items"][0]
    assert pub["comment"] == "temiz yorum" and pub["is_edited"] is True
    assert "original_comment" not in pub and "edited_by" not in pub


def test_empty_comment_rejected_and_reply(E):
    extras, tdb = E
    with pytest.raises(HTTPException):
        run(extras.update_review("r1", {"comment": "  "}, current_user=ADMIN))
    run(extras.update_review("r1", {"admin_reply": " Teşekkürler "}, current_user=ADMIN))
    r = run(tdb.reviews.find_one({"id": "r1"}, {"_id": 0}))
    assert r["admin_reply"] == "Teşekkürler" and "is_edited" not in r
