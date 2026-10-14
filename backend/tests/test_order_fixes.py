"""Sipariş düzeltmeleri regresyon testleri (e2e bulguları #9, #10, #13, #15, #18, #30, #35).

routes/orders.py tüm uygulama grafiğini yüklemeden test edilir: ilgili fonksiyonlar AST ile
çekilip gerçek localdb + gerekli yardımcı taklitleriyle (stub) çalıştırılır."""
import ast
import asyncio
import logging
import re
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, HTTPException, Query, Request

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ORDERS = ROOT / "routes" / "orders.py"


def run(coro):
    return asyncio.run(coro)


def load(names, scope, assigns=()):
    """orders.py'den adı verilen fonksiyonları (dekoratörsüz) ve modül düzeyi atamaları yükler."""
    tree = ast.parse(ORDERS.read_text())
    nodes = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names:
            n.decorator_list = []
            nodes.append(n)
        elif isinstance(n, ast.Assign) and any(getattr(t, "id", None) in assigns for t in n.targets):
            nodes.append(n)
    assert len([n for n in nodes if not isinstance(n, ast.Assign)]) == len(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(ORDERS), "exec"), scope)
    return scope


def base_scope(db=None):
    return {"db": db, "re": re, "uuid": uuid, "datetime": datetime, "timezone": timezone,
            "timedelta": timedelta, "HTTPException": HTTPException, "Depends": Depends,
            "Query": Query, "Request": Request, "logger": logging.getLogger("order-fixes-test"),
            "get_current_user": lambda: None, "require_permission": lambda key: (lambda: None)}


@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    return AsyncIOMotorClient(path=str(tmp_path / "orders.db"))["test"]


# ── #9: sunucu tarafı adres / iletişim / fatura doğrulaması ─────────────────────

@pytest.fixture
def validator():
    s = load(["_is_valid_tckn", "_validate_checkout_payload"], base_scope(),
             assigns=("_EMAIL_RE", "_ADDR_FIELD_LABELS"))
    return s["_validate_checkout_payload"], s["_is_valid_tckn"]


GOOD_ADDR = {"first_name": "Ali", "last_name": "Yılmaz", "address": "Atatürk Mah. Cumhuriyet Cad. No:5",
             "city": "İstanbul", "district": "Kadıköy", "phone": "0532 123 45 67", "email": "ali@example.com"}


def test_validator_accepts_valid_checkout_and_cod_quick_order(validator):
    v, _ = validator
    v({"shipping_address": dict(GOOD_ADDR), "billing_info": {"is_corporate": False}})
    # Kapıda hızlı siparişte e-posta opsiyonel
    v({"shipping_address": {**GOOD_ADDR, "email": ""}, "billing_same_as_shipping": True})
    # Kurumsal: 10 haneli VKN / geçerli TCKN
    v({"shipping_address": dict(GOOD_ADDR),
       "billing_info": {"is_corporate": True, "company_name": "X Ltd", "tax_office": "Kadıköy",
                        "tax_number": "1234567890"}})
    v({"shipping_address": dict(GOOD_ADDR),
       "billing_info": {"is_corporate": True, "company_name": "X", "tax_office": "Y",
                        "tax_number": "10000000146"}})


@pytest.mark.parametrize("payload", [
    # bulgudaki yük: boş ad/adres, kısa telefon, geçersiz e-posta, hatalı vergi no
    {"shipping_address": {"first_name": "", "last_name": "", "address": "", "city": "", "district": "",
                          "phone": "12", "email": "gecersiz"},
     "billing_info": {"is_corporate": True, "company_name": "", "tax_number": "abc", "tax_office": ""}},
    {"shipping_address": None},
    {"shipping_address": {**GOOD_ADDR, "phone": "12345"}},
    {"shipping_address": {**GOOD_ADDR, "district": "  "}},
    {"shipping_address": {**GOOD_ADDR, "email": "gecersiz"}},
    {"shipping_address": dict(GOOD_ADDR), "billing_same_as_shipping": False,
     "billing_address": {**GOOD_ADDR, "address": ""}},
    {"shipping_address": dict(GOOD_ADDR),
     "billing_info": {"is_corporate": True, "company_name": "", "tax_office": "Y", "tax_number": "1234567890"}},
    {"shipping_address": dict(GOOD_ADDR),
     "billing_info": {"is_corporate": True, "company_name": "X", "tax_office": "Y", "tax_number": "abc"}},
    {"shipping_address": dict(GOOD_ADDR),
     "billing_info": {"is_corporate": True, "company_name": "X", "tax_office": "Y", "tax_number": "12345678901"}},
])
def test_validator_rejects_invalid_payload(validator, payload):
    v, _ = validator
    with pytest.raises(HTTPException) as e:
        v(payload)
    assert e.value.status_code == 400


def test_validator_uses_session_email_fallback(validator):
    v, _ = validator
    v({"shipping_address": {**GOOD_ADDR, "email": ""}}, {"email": "uye@example.com"})
    with pytest.raises(HTTPException):
        v({"shipping_address": {**GOOD_ADDR, "email": ""}}, {"email": "bozuk"})


def test_tckn_algorithm(validator):
    _, tckn = validator
    assert tckn("10000000146") and not tckn("12345678901") and not tckn("01234567890")


# ── #10: havale indirimi yarım kuruşta yukarı (kasa ile aynı) ─────────────────

def test_bank_transfer_discount_rounds_half_up():
    pct = load(["_pct_amount_half_up"], base_scope())["_pct_amount_half_up"]
    assert pct(678.30, 5) == 33.92           # round() 33.91 veriyordu
    assert round(678.30 - pct(678.30, 5), 2) == 644.38
    assert pct(100, 5) == 5.0 and pct(0, 5) == 0.0 and pct(1000, 0) == 0.0
    assert pct(0.1 + 0.2, 50) == 0.15        # float gürültüsü tabana sızmaz


# ── #18: yalnız IP eşiği → nötr mesaj; kişi eşiği → kişiye özel mesaj ──────────

def _create_order_scope(db):
    s = base_scope(db)
    load(["create_order", "_is_valid_tckn", "_validate_checkout_payload"], s,
         assigns=("_EMAIL_RE", "_ADDR_FIELD_LABELS"))
    return s["create_order"]


def _req(ip):
    return SimpleNamespace(headers={"x-forwarded-for": ip}, client=None)


def test_ip_only_pending_limit_uses_neutral_message(db):
    create_order = _create_order_scope(db)
    now = datetime.now(timezone.utc).isoformat()
    for i in range(9):  # varsayılan eşik 3 → IP eşiği 9 (başka müşterilerin siparişleri)
        run(db.orders.insert_one({"id": f"o{i}", "status": "awaiting_payment", "created_at": now,
                                  "customer_ip": "9.9.9.9", "shipping_address": {"email": f"x{i}@e.com"}}))
    with pytest.raises(HTTPException) as e:
        run(create_order({"shipping_address": dict(GOOD_ADDR)}, _req("9.9.9.9"), None))
    assert e.value.status_code == 429
    assert "siparişleriniz var" not in e.value.detail and "bağlantı" in e.value.detail


def test_person_pending_limit_keeps_personal_message(db):
    create_order = _create_order_scope(db)
    now = datetime.now(timezone.utc).isoformat()
    for i in range(3):
        run(db.orders.insert_one({"id": f"p{i}", "status": "awaiting_payment", "created_at": now,
                                  "customer_ip": "8.8.8.8", "shipping_address": {"email": "ali@example.com"}}))
    with pytest.raises(HTTPException) as e:
        run(create_order({"shipping_address": dict(GOOD_ADDR)}, _req("7.7.7.7"), None))
    assert e.value.status_code == 429 and "siparişleriniz var" in e.value.detail


def test_invalid_payload_rejected_before_order_written(db):
    create_order = _create_order_scope(db)
    with pytest.raises(HTTPException) as e:
        run(create_order({"items": [{"product_id": "1", "quantity": 1}],
                          "shipping_address": {**GOOD_ADDR, "phone": "12"}}, _req("1.1.1.1"), None))
    assert e.value.status_code == 400
    assert run(db.orders.count_documents({})) == 0


# ── #13 / #30: durum güncelleme — teslim tarihleri ve iptalden geri dönüşte stok ─

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
    })
    load(["update_order_status"], s)
    return s


def test_manual_delivered_writes_shipped_and_delivered_at(db):
    s = _status_scope(db)
    run(db.orders.insert_one({"id": "o1", "status": "confirmed", "payment_method": "cash_on_delivery"}))
    run(s["update_order_status"]("o1", "shipped", {"email": "a@x"}))
    o = run(db.orders.find_one({"id": "o1"}))
    assert o["shipped_at"] and not o.get("delivered_at")
    shipped_at = o["shipped_at"]
    run(s["update_order_status"]("o1", "delivered", {"email": "a@x"}))
    o = run(db.orders.find_one({"id": "o1"}))
    assert o["delivered_at"] and o["shipped_at"] == shipped_at  # mevcut tarih ezilmez


def test_delivered_keeps_existing_carrier_dates(db):
    s = _status_scope(db)
    run(db.orders.insert_one({"id": "o2", "status": "shipped", "shipped_at": "2026-01-01T00:00:00+00:00",
                              "delivered_at": "2026-01-02T00:00:00+00:00"}))
    run(s["update_order_status"]("o2", "delivered", {"email": "a@x"}))
    o = run(db.orders.find_one({"id": "o2"}))
    assert o["delivered_at"] == "2026-01-02T00:00:00+00:00"
    assert o["shipped_at"] == "2026-01-01T00:00:00+00:00"


@pytest.mark.parametrize("status", ["pending", "awaiting_payment", "payment_notified"])
def test_reactivating_cancelled_to_open_status_redecrements_stock(db, status):
    s = _status_scope(db)
    run(db.orders.insert_one({"id": "o3", "order_number": "W1", "status": "cancelled"}))
    run(db.stock_movements.insert_one({"id": "m1", "type": "order_cancelled", "order_id": "o3",
                                       "items": [{"product_id": "P", "delta": 1}]}))
    run(s["update_order_status"]("o3", status, {"email": "a@x"}))
    s["_reverse_stock_moves"].assert_awaited_once()
    s["_consume_restore_moves"].assert_awaited_once()
    assert run(db.stock_movements.count_documents({"type": "reactivate_decrement"})) == 1


# ── #15: herkese açık sipariş-no sorgusu açık adresi maskeler ─────────────────

def _by_number_scope(db):
    s = base_scope(db)
    s["_effective_delivered_at"] = AsyncMock(return_value=(None, False))
    load(["get_order_by_number"], s)
    return s["get_order_by_number"]


def test_public_order_lookup_masks_street_address(db):
    get = _by_number_scope(db)
    run(db.orders.insert_one({"id": "o4", "order_number": "W10023", "user_id": "u1",
                              "idempotency_key": "k1",
                              "shipping_address": {"first_name": "Ayşe", "last_name": "Y",
                                                   "address": "Bağdat Cad. No:10 D:3", "city": "İstanbul",
                                                   "district": "Kadıköy", "phone": "05321234501"}}))
    anon = run(get("W10023", None, None))
    assert "No:10" not in anon["shipping_address"]["address"]
    assert anon["shipping_address"]["city"] == "İstanbul" and anon["shipping_address"]["district"] == "Kadıköy"
    assert "idempotency_key" not in anon and "user_id" not in anon
    other = run(get("W10023", None, {"id": "u2"}))
    assert "No:10" not in other["shipping_address"]["address"]
    owner = run(get("W10023", None, {"id": "u1"}))
    assert owner["shipping_address"]["address"] == "Bağdat Cad. No:10 D:3" and "user_id" not in owner


# ── #35: gider pusulası KDV'si kalem oranlarından ─────────────────────────────

@pytest.fixture
def gp_vat():
    s = base_scope()
    load(["_round2", "_gp_vat_totals"], s)
    return s["_gp_vat_totals"]


def test_gider_pusulasi_vat_uses_item_rate(gp_vat):
    # bulgu: ürün %20, ayar %10, net 725 (10 TL satır dışı fark) → KDV 120,83
    rate, vat, matrah, br = gp_vat([(20.0, 715.0)], 725.0, 10.0, 1)
    assert rate == 20.0 and vat == 120.83 and matrah == 604.17
    assert br == {"20": {"gross": 725.0, "vat": 120.83, "matrah": 604.17}}


def test_gider_pusulasi_vat_mixed_rates(gp_vat):
    rate, vat, matrah, br = gp_vat([(10.0, 110.0), (20.0, 240.0), (20.0, 60.0)], 410.0, 10.0, 2)
    assert set(br) == {"10", "20"} and br["10"]["vat"] == 10.0 and br["20"]["vat"] == 50.0
    assert vat == 60.0 and matrah == 350.0 and rate == 20.0


def test_gider_pusulasi_vat_falls_back_to_default_without_lines(gp_vat):
    rate, vat, matrah, br = gp_vat([], 110.0, 10.0, 0)
    assert rate == 10.0 and vat == 10.0 and matrah == 100.0
