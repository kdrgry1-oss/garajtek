"""Üye hesabı E2E bulgularının regresyon testleri (gerçek route gövdeleri + gömülü localdb).

- /auth/me (get_current_user) parola geçmişi / MFA / kilit alanlarını sızdırmaz
- 20 adres sınırı + sıralı, eksiksiz adres listesi
- şifre sıfırlama hatalı-giriş kilidini kaldırır
- profil telefonu normalize + doğrulanır, başka hesabın numarası alınamaz
- sipariş takibi küçük harfli sipariş numarasını bulur
- zaten 'cancel_requested' olan siparişe tekrar iptal → idempotent bilgi (409 değil)
"""
import ast
import asyncio
import os
import re
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import Body, Depends, HTTPException

pytest.importorskip("mongomock")

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from localdb import AsyncIOMotorClient  # noqa: E402


def load(path, names, scope):
    """Modülden yalnız istenen fonksiyon/sabitleri (dekoratörsüz) scope'a yükle."""
    tree = ast.parse((ROOT / path).read_text())
    nodes = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names:
            n.decorator_list = []
            nodes.append(n)
        elif isinstance(n, ast.Assign) and any(getattr(t, "id", None) in names for t in n.targets):
            nodes.append(n)
    assert len(nodes) == len(names), [getattr(n, "name", None) for n in nodes]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / path), "exec"), scope)
    return scope


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def db(tmp_path):
    d = AsyncIOMotorClient(path=str(tmp_path / "store.db"))["shop"]
    yield d
    d.client.close()


def base_scope(db):
    return {"db": db, "HTTPException": HTTPException, "Depends": Depends, "Body": Body,
            "datetime": datetime, "timezone": timezone, "re": re,
            "require_auth": lambda: None, "get_current_user": lambda: None}


# --------------------------------------------------------------------------- /auth/me sızıntısı
def test_session_user_hides_password_history_and_security_fields(db):
    run(db.users.insert_one({
        "id": "u1", "email": "a@example.invalid", "first_name": "Ada", "phone": "905441112233",
        "password": "$2b$12$current", "password_history": ["$2b$12$old"], "token_version": 2,
        "password_changed_at": "2026-01-01T00:00:00+00:00",
        "failed_attempts": 3, "first_failed_at": "x", "locked_until": "y",
        "mfa_secret_enc": "enc", "mfa_pending_secret_enc": "enc2", "mfa_phone_enc": "enc3",
        "mfa_fail_count": 1, "mfa_fail_window": "z", "is_active": True,
    }))
    scope = base_scope(db)
    scope["_decode_jwt_strict"] = lambda tok: {"user_id": "u1", "tv": 2}
    scope["security"] = None
    scope["HTTPAuthorizationCredentials"] = object
    load("routes/deps.py", ["_USER_SESSION_PROJECTION", "_USER_SESSION_STRIP",
                            "_strip_session_user", "_token_revoked", "get_current_user"], scope)
    user = run(scope["get_current_user"](SimpleNamespace(credentials="t")))
    assert user["id"] == "u1" and user["first_name"] == "Ada" and user["phone"] == "905441112233"
    for k in ("password", "password_history", "token_version", "failed_attempts", "first_failed_at",
              "locked_until", "mfa_secret_enc", "mfa_pending_secret_enc", "mfa_phone_enc",
              "mfa_fail_count", "mfa_fail_window"):
        assert k not in user, k
    # token iptal kontrolü hâlâ çalışır (eski tv → oturum yok)
    scope["_decode_jwt_strict"] = lambda tok: {"user_id": "u1", "tv": 1}
    assert run(scope["get_current_user"](SimpleNamespace(credentials="t"))) is None


# --------------------------------------------------------------------------- customer.py yardımcıları
@pytest.fixture()
def customer(db, monkeypatch):
    # update_my_profile içindeki `from .auth import _phone_exact_regex` için sahte paket
    auth_scope = load("routes/auth.py", ["_phone_exact_regex"], {})
    pkg, auth_mod = types.ModuleType("routes"), types.ModuleType("routes.auth")
    pkg.__path__ = []
    auth_mod._phone_exact_regex = auth_scope["_phone_exact_regex"]
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.auth", auth_mod)
    scope = base_scope(db)
    scope["__package__"] = "routes"
    scope["generate_id"] = lambda: os.urandom(8).hex()
    return load("routes/customer.py", [
        "MAX_ADDRESSES_PER_USER", "_MAX_LIST_ADDRESSES", "get_my_addresses", "create_address",
        "update_my_profile", "public_order_tracking", "_public_track_link", "_CARGO_NAME_MAP",
        "_CUSTOMER_CANCELLABLE", "_owner_or_clauses", "valid_tr_iban", "cancel_my_order",
    ], scope)


def test_address_limit_and_full_sorted_listing(customer, db):
    me = {"id": "m1"}
    for i in range(20):
        run(customer["create_address"]({"title": f"Adres {i + 1}", "address": "x", "city": "c"}, me))
    with pytest.raises(HTTPException) as e:
        run(customer["create_address"]({"title": "Adres 21"}, me))
    assert e.value.status_code == 400 and "En fazla 20" in e.value.detail
    # Sınırdan önce birikmiş (eski) fazladan adresler de listelenir
    run(db.addresses.insert_one({"id": "legacy", "user_id": "m1", "title": "Eski 21",
                                 "is_default": False, "created_at": "2000-01-01T00:00:00+00:00"}))
    run(db.addresses.insert_one({"id": "def", "user_id": "m1", "title": "Varsayılan",
                                 "is_default": True, "created_at": "1999-01-01T00:00:00+00:00"}))
    out = run(customer["get_my_addresses"](me))["addresses"]
    assert len(out) == 22
    assert out[0]["id"] == "def"           # varsayılan başta
    assert out[-1]["id"] == "legacy"       # en eski sonda
    assert out[1]["title"] == "Adres 20"   # en yeni (varsayılan dışı) üstte


def test_profile_phone_normalized_validated_and_unique(customer, db):
    run(db.users.insert_one({"id": "a", "phone": "905447778899"}))
    run(db.users.insert_one({"id": "b", "phone": ""}))
    upd = customer["update_my_profile"]
    for bad in ("abc<script>", "12345", "+44 7700 900123"):
        with pytest.raises(HTTPException) as e:
            run(upd({"phone": bad}, {"id": "b"}))
        assert e.value.detail == "Geçerli bir cep telefonu girin"
    with pytest.raises(HTTPException) as e:
        run(upd({"phone": "0544 777 88 99"}, {"id": "b"}))
    assert e.value.detail == "Bu telefon numarası zaten kayıtlı"
    run(upd({"phone": "0 (532) 111 22 33"}, {"id": "b"}))
    assert run(db.users.find_one({"id": "b"}))["phone"] == "905321112233"
    # Kendi numarasını tekrar göndermek (ad değişikliği) engellenmez; boş → temizlenir
    run(upd({"phone": "05447778899", "first_name": "Ali"}, {"id": "a", "phone": "905447778899"}))
    run(upd({"phone": ""}, {"id": "b"}))
    assert run(db.users.find_one({"id": "b"}))["phone"] == ""


def test_tracking_finds_lowercase_order_number(customer, db):
    run(db.orders.insert_one({"id": "o1", "order_number": "W10001", "status": "confirmed",
                              "created_at": "2026-01-01T00:00:00+00:00"}))
    run(db.orders.insert_one({"id": "o2", "order_number": "W10002", "status": "shipped",
                              "cargo_tracking_number": "abC123", "created_at": "2026-01-01T00:00:00+00:00"}))
    assert run(customer["public_order_tracking"]("  w10001 "))["order_number"] == "W10001"
    assert run(customer["public_order_tracking"]("abC123"))["order_number"] == "W10002"
    with pytest.raises(HTTPException):
        run(customer["public_order_tracking"]("ABC123"))  # kargo no harf duyarlı kalır


def test_repeat_cancel_on_cancel_requested_is_idempotent(customer, db):
    info = {"iban": "TR330006100519786457841326", "name": "Ada"}
    run(db.orders.insert_one({"id": "o9", "order_number": "W10023", "user_id": "m1",
                              "status": "cancel_requested", "payment_status": "paid",
                              "refund_bank_info": info, "cancel_requested_at": "t0"}))
    res = run(customer["cancel_my_order"]("o9", {}, {"id": "m1"}))
    assert res["success"] is True and res["status"] == "cancel_requested"
    assert "zaten alındı" in res["message"] and "iade" in res["message"]
    o = run(db.orders.find_one({"id": "o9"}))
    assert o["refund_bank_info"] == info and o["cancel_requested_at"] == "t0"  # ezilmedi
    # Gerçekten hazırlanan siparişte 409 korunur
    run(db.orders.insert_one({"id": "o10", "user_id": "m1", "status": "preparing"}))
    with pytest.raises(HTTPException) as e:
        run(customer["cancel_my_order"]("o10", {}, {"id": "m1"}))
    assert e.value.status_code == 409


# --------------------------------------------------------------------------- şifre sıfırlama kilidi
def test_password_reset_clears_login_lockout(db):
    now_ts = datetime.now(timezone.utc).timestamp()
    run(db.users.insert_one({"id": "u5", "email": "l@example.invalid", "password": "old",
                             "failed_attempts": 5, "first_failed_at": "t", "locked_until": "2999-01-01"}))
    run(db.password_reset_otps.insert_one({"user_id": "u5", "reset_token": "rt",
                                           "reset_token_expires": now_ts + 600}))
    scope = base_scope(db)
    scope.update({"OTPResetReq": object, "hash_password": lambda p: "h:" + p,
                  "_enforce_pw_history": lambda u, p: None, "_PW_HISTORY_KEEP": 10})
    load("routes/auth.py", ["forgot_password_reset", "_next_pw_history"], scope)
    res = run(scope["forgot_password_reset"](SimpleNamespace(new_password="NewPass456!", reset_token="rt")))
    assert res["success"] is True
    u = run(db.users.find_one({"id": "u5"}))
    assert u["password"] == "h:NewPass456!" and u["token_version"] == 1
    for k in ("failed_attempts", "first_failed_at", "locked_until"):
        assert k not in u, k
