"""Panel ↔ vitrin senkron E2E bulguları (2. tur) regresyon testleri.

- #32/#40: elle durum güncellemesi onay/hazırlık/teslim tarihlerini damgalar; Hesabım
  (/my-orders) teslim tarihi boş siparişte varsayılan-teslim fallback'ini uygular
- #33: 'Ödemeli İptal Onaylandı' (cancel_refunded) stok/hediye çeki/puan iadesini tetikler
- #34/#35/#36/#40: takip ekranı — cancel_requested Türkçe etiket + iptal zaman çizelgesi,
  cancel_refunded / payment_failed iptal adımları, iade durumlarında teslim adımı tamam,
  panel müşteri etiketi override'ı ve özel durumlar
- #38: panelden şifre atama / pasifleştirme oturumu (token_version) düşürür
- #39: kapıda ödeme iadesinde IBAN zorunlu
- 1. tur kalanı: admin üye/personel listesi projeksiyonu parola geçmişi + MFA sırlarını hariç tutar
"""
import ast
import asyncio
import logging
import re
import sys
import types
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi import Body, Depends, HTTPException, Query

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from localdb import AsyncIOMotorClient  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def load(path, names, scope, assigns=()):
    """Modülden adı verilen fonksiyonları (dekoratörsüz) + modül düzeyi atamaları yükler."""
    tree = ast.parse((ROOT / path).read_text())
    nodes = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names:
            n.decorator_list = []
            nodes.append(n)
        elif isinstance(n, ast.Assign) and any(getattr(t, "id", None) in assigns for t in n.targets):
            nodes.append(n)
    assert len([n for n in nodes if not isinstance(n, ast.Assign)]) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ROOT / path), "exec"), scope)
    return scope


@pytest.fixture()
def db(tmp_path):
    d = AsyncIOMotorClient(path=str(tmp_path / "sync.db"))["shop"]
    yield d
    d.client.close()


def base_scope(db):
    return {"db": db, "re": re, "uuid": uuid, "datetime": datetime, "timezone": timezone,
            "timedelta": timedelta, "HTTPException": HTTPException, "Depends": Depends,
            "Query": Query, "Body": Body, "logger": logging.getLogger("panel-sync-test"),
            "require_auth": lambda: None, "require_admin": lambda: None,
            "require_permission": lambda key: (lambda: None)}


# ── order_statuses: sistem durumu etiketi ──────────────────────────────────────

def test_cancel_requested_has_turkish_customer_label():
    import order_statuses as OS
    assert OS.customer_label_for("cancel_requested") == "İptal Talebiniz Alındı"
    assert OS.customer_label_for_cfg("cancel_requested", {}) == "İptal Talebiniz Alındı"
    # Ayarlar'dan yönetilmez: geçerli (seçilebilir) durum kümesine girmez
    assert "cancel_requested" not in OS.valid_keys(OS.merge_config({}))


# ── update_order_status ────────────────────────────────────────────────────────

def _status_scope(db):
    s = base_scope(db)
    s.update({
        "_HAVALE_PMS": ("bank_transfer",), "_CARD_PMS": ("credit_card",), "_SETTLED_PAY": ("paid",),
        "_CANCEL_ST_FOR_STAMP": ("cancelled", "cancel_refunded"),
        "_RESTORE_MOVE_TYPES": ["order_cancelled"],
        "stamp_cancelled_at": AsyncMock(), "_log_order_event": AsyncMock(),
        "_spawn": lambda c: c.close(), "dispatch_purchase_capi": AsyncMock(),
        "_restock_order_once": AsyncMock(), "release_order_redemptions": AsyncMock(),
        "_resolve_move_level": AsyncMock(return_value="product"),
        "_reverse_stock_moves": AsyncMock(), "_consume_restore_moves": AsyncMock(return_value=1),
        # cancel_refunded yetki kontrolü `from .deps import get_effective_permissions` yapar →
        # paket bağlamı (fake_deps fikstürü routes.deps'i sağlar)
        "__package__": "routes", "__name__": "routes.orders",
    })
    load("routes/orders.py", ["update_order_status"], s)
    return s


@pytest.fixture()
def fake_deps(monkeypatch):
    pkg = types.ModuleType("routes")
    pkg.__path__ = []
    deps = types.ModuleType("routes.deps")
    deps.get_effective_permissions = AsyncMock(return_value={"*"})
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.deps", deps)
    return pkg


def test_cancel_refunded_restocks_like_cancelled(db, fake_deps):
    s = _status_scope(db)
    run(db.orders.insert_one({"id": "o1", "order_number": "W1", "status": "confirmed",
                              "payment_status": "paid", "payment_method": "bank_transfer"}))
    run(s["update_order_status"]("o1", "cancel_refunded", {"email": "fin@x"}))
    s["_restock_order_once"].assert_awaited_once()
    assert s["_restock_order_once"].await_args.args[1] == "order_cancelled"
    s["release_order_redemptions"].assert_awaited_once()


def test_manual_status_flow_stamps_step_dates_once(db):
    s = _status_scope(db)
    run(db.orders.insert_one({"id": "o2", "status": "pending", "payment_method": "cash_on_delivery"}))
    run(s["update_order_status"]("o2", "confirmed", {"email": "a@x"}))
    o = run(db.orders.find_one({"id": "o2"}))
    assert o["confirmed_at"] and not o.get("processing_at")
    confirmed_at = o["confirmed_at"]
    run(s["update_order_status"]("o2", "preparing", {"email": "a@x"}))
    run(s["update_order_status"]("o2", "delivered", {"email": "a@x"}))
    o = run(db.orders.find_one({"id": "o2"}))
    assert o["confirmed_at"] == confirmed_at          # mevcut tarih ezilmez
    assert o["processing_at"] and o["shipped_at"] and o["delivered_at"]


def test_jump_to_delivered_fills_previous_steps(db):
    s = _status_scope(db)
    run(db.orders.insert_one({"id": "o3", "status": "pending", "payment_method": "cash_on_delivery"}))
    run(s["update_order_status"]("o3", "delivered", {"email": "a@x"}))
    o = run(db.orders.find_one({"id": "o3"}))
    for k in ("confirmed_at", "processing_at", "shipped_at", "delivered_at"):
        assert o.get(k), k


# ── /track (public_order_tracking) ─────────────────────────────────────────────

def _track(db):
    s = base_scope(db)
    load("routes/customer.py", ["_public_track_link", "public_order_tracking"], s,
         assigns=("_CARGO_NAME_MAP",))
    return s["public_order_tracking"]


def _steps(res):
    return {t["status"]: t for t in res["timeline"]}


def test_track_cancel_requested_label_and_cancel_timeline(db):
    track = _track(db)
    run(db.orders.insert_one({"id": "t1", "order_number": "W10051", "status": "cancel_requested",
                              "created_at": "2026-10-01T10:00:00+00:00",
                              "cancel_requested_at": "2026-10-01T11:00:00+00:00"}))
    res = run(track("W10051"))
    assert res["status_text"] == "İptal Talebiniz Alındı"
    st = _steps(res)
    assert "confirmed" not in st and "delivered" not in st     # normal hazırlık adımları yok
    assert st["cancel_requested"]["completed"] and st["cancel_requested"]["date"]
    assert st["cancelled"]["completed"] is False


@pytest.mark.parametrize("status,extra", [("cancel_refunded", "cancel_refunded"),
                                          ("payment_failed", "payment_failed")])
def test_track_cancel_like_statuses_use_cancel_timeline(db, status, extra):
    track = _track(db)
    run(db.orders.insert_one({"id": "t2", "order_number": "W10046", "status": status,
                              "created_at": "2026-10-01T10:00:00+00:00",
                              "cancelled_at": "2026-10-02T10:00:00+00:00",
                              "updated_at": "2026-10-02T10:00:00+00:00"}))
    st = _steps(run(track("W10046")))
    assert "confirmed" not in st and st[extra]["completed"]


def test_track_return_status_marks_delivery_done_with_real_dates(db):
    track = _track(db)
    run(db.orders.insert_one({"id": "t3", "order_number": "W10036", "status": "return_approved",
                              "created_at": "2026-10-01T10:00:00+00:00",
                              "confirmed_at": "2026-10-01T12:00:00+00:00",
                              "shipped_at": "2026-10-02T10:00:00+00:00",
                              "delivered_at": "2026-10-03T10:00:00+00:00",
                              "return_approved_at": "2026-10-05T10:00:00+00:00"}))
    res = run(track("W10036"))
    st = _steps(res)
    for k in ("confirmed", "processing", "shipped", "delivered"):
        assert st[k]["completed"], k
    assert st["confirmed"]["date"] == "2026-10-01T12:00:00+00:00"
    assert st["delivered"]["date"] == "2026-10-03T10:00:00+00:00"
    assert st["return_approved"]["date"] == "2026-10-05T10:00:00+00:00"


def test_track_confirmed_date_is_not_creation_time(db):
    track = _track(db)
    run(db.orders.insert_one({"id": "t4", "order_number": "W10039", "status": "delivered",
                              "created_at": "2026-10-01T10:00:00+00:00"}))
    st = _steps(run(track("W10039")))
    assert st["confirmed"]["completed"] and st["confirmed"]["date"] != "2026-10-01T10:00:00+00:00"


def test_track_uses_panel_customer_label_override_and_custom_status(db):
    track = _track(db)
    run(db.settings.insert_one({"id": "order_status_config", "templates_seed_version": 3,
                                "labels": {"shipped": {"customer_label": "SYNC Kargo Yolda Etiketi"}},
                                "custom": [{"key": "sync_ozel", "label": "SYNC Özel Durum",
                                            "customer_label": "SYNC Özel Müşteri"}]}))
    run(db.orders.insert_one({"id": "t5", "order_number": "W1", "status": "shipped",
                              "created_at": "2026-10-01T10:00:00+00:00"}))
    run(db.orders.insert_one({"id": "t6", "order_number": "W2", "status": "sync_ozel",
                              "created_at": "2026-10-01T10:00:00+00:00"}))
    assert run(track("W1"))["status_text"] == "SYNC Kargo Yolda Etiketi"
    res = run(track("W2"))
    assert res["status_text"] == "SYNC Özel Müşteri"
    assert _steps(res)["sync_ozel"]["title"] == "SYNC Özel Müşteri"


# ── /my-orders ─────────────────────────────────────────────────────────────────

def test_my_orders_adds_status_labels_and_presumed_delivery(db, monkeypatch):
    pkg = types.ModuleType("routes")
    pkg.__path__ = []
    orders_mod = types.ModuleType("routes.orders")
    orders_mod._effective_delivered_at = AsyncMock(return_value=("2026-10-06T10:00:00+00:00", True))
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.orders", orders_mod)
    s = base_scope(db)
    load("routes/customer.py", ["_owner_or_clauses", "get_my_orders"], s)
    run(db.settings.insert_one({"id": "order_status_config", "templates_seed_version": 3,
                                "custom": [{"key": "sync_ozel", "label": "SYNC Özel",
                                            "customer_label": "SYNC Özel Müşteri"}]}))
    for i, st in enumerate(("cancel_refunded", "sync_ozel", "delivered")):
        run(db.orders.insert_one({"id": f"m{i}", "user_id": "u1", "status": st,
                                  "created_at": f"2026-10-0{i + 1}T10:00:00+00:00"}))
    res = run(s["get_my_orders"](page=1, limit=10, current_user={"id": "u1"}))
    by = {o["status"]: o for o in res["orders"]}
    assert by["cancel_refunded"]["status_label"] == "İptal Bedeliniz İade Edildi"
    assert by["sync_ozel"]["status_label"] == "SYNC Özel Müşteri" and by["sync_ozel"]["status_label_custom"]
    assert by["cancel_refunded"]["status_label_custom"] is False
    assert by["delivered"]["delivered_at"] == "2026-10-06T10:00:00+00:00"


# ── #38: panelden üye düzenleme ────────────────────────────────────────────────

def _member_update(db):
    s = base_scope(db)
    s["hash_password"] = lambda p: "hashed:" + p
    load("routes/members.py", ["update_member"], s)
    return s["update_member"]


def test_admin_password_change_revokes_member_sessions(db):
    upd = _member_update(db)
    run(db.users.insert_one({"id": "u1", "email": "m@x", "is_admin": False, "token_version": 3}))
    run(upd("u1", {"password": "YeniSifre123"}, current_user={}))
    u = run(db.users.find_one({"id": "u1"}))
    assert u["password"] == "hashed:YeniSifre123" and u["token_version"] == 4
    assert u["password_changed_at"] and u["must_change_password"] is True
    with pytest.raises(HTTPException):
        run(upd("u1", {"password": "kisa"}, current_user={}))


def test_deactivation_revokes_but_profile_edit_does_not(db):
    upd = _member_update(db)
    run(db.users.insert_one({"id": "u2", "email": "m2@x", "is_admin": False, "token_version": 1,
                             "is_active": True}))
    run(upd("u2", {"first_name": "Ada"}, current_user={}))
    assert run(db.users.find_one({"id": "u2"}))["token_version"] == 1
    run(upd("u2", {"is_active": False}, current_user={}))
    u = run(db.users.find_one({"id": "u2"}))
    assert u["is_active"] is False and u["token_version"] == 2


# ── #39: kapıda ödeme iadesinde IBAN ──────────────────────────────────────────

@pytest.mark.parametrize("pm", ["cash_on_delivery", "kapida", "cod"])
def test_cod_return_requires_iban(db, monkeypatch, pm):
    s = base_scope(db)
    load("routes/customer.py", ["valid_tr_iban"], s, assigns=("BANK_REFUND_PMS",))
    pkg = types.ModuleType("routes")
    pkg.__path__ = []
    cust = types.ModuleType("routes.customer")
    cust.BANK_REFUND_PMS = s["BANK_REFUND_PMS"]
    cust.valid_tr_iban = s["valid_tr_iban"]
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.customer", cust)
    o = base_scope(db)
    o["_effective_delivered_at"] = AsyncMock(
        return_value=(datetime.now(timezone.utc).isoformat(), False))
    load("routes/orders.py", ["_build_return_for_order"], o)
    order = {"id": "r1", "order_number": "W10036", "payment_method": pm,
             "items": [{"name": "Ürün", "quantity": 1, "price": 715}]}
    with pytest.raises(HTTPException) as e:
        run(o["_build_return_for_order"](order, {"reason": "Beden uymadı"}, {"email": "m@x"}))
    assert e.value.status_code == 400 and "IBAN" in e.value.detail


# ── 1. tur kalanı: admin üye listesi projeksiyonu ─────────────────────────────

@pytest.mark.parametrize("path", ["routes/admin.py", "routes/members.py", "routes/admin_rbac.py"])
def test_admin_member_projection_hides_security_fields(db, path):
    s = {}
    load("routes/deps.py", [], s, assigns=("_USER_SESSION_PROJECTION",))
    load(path, [], s, assigns=("_USER_ADMIN_PROJECTION",))
    src = (ROOT / path).read_text()
    assert '{"_id": 0, "password": 0}' not in src
    run(db.users.insert_one({"id": "u1", "email": "a@x", "password": "h", "password_history": ["o"],
                             "mfa_secret_enc": "e", "mfa_phone_enc": "p", "failed_attempts": 2,
                             "locked_until": "l", "token_version": 3, "is_active": True}))
    u = run(db.users.find_one({"id": "u1"}, s["_USER_ADMIN_PROJECTION"]))
    assert u["email"] == "a@x" and u["is_active"] is True
    for k in ("password", "password_history", "mfa_secret_enc", "mfa_phone_enc",
              "failed_attempts", "locked_until", "token_version"):
        assert k not in u, k


# ── 1. tur kalanı: sipariş sonrası otomatik adres kaydı adres sınırına uyar ───

def test_order_address_autosave_respects_address_limit():
    src = (ROOT / "routes" / "orders.py").read_text()
    blk = src[src.index("# Üye adres defteri"):src.index("Profil telefonu boşsa")]
    assert "MAX_ADDRESSES_PER_USER" in blk and "count_documents" in blk
    assert "if not _dup and not _full:" in blk
