"""BirFatura Özel Entegrasyon uçları — sözleşme, güvenlik, eşleme ve geri yazım testleri.

routes paketinin __init__'i (tüm uygulama) yüklenmez: routes.deps taklit edilir, veritabanı
geçici dosyada GERÇEK localdb'dir (Motor uyumlu)."""
import importlib
import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("SECRETS_MASTER_KEY", "x1Yb5ZQkF4m3Yw3w8yqO1QZb9oS3Lr0aZ6c0eS2nHkU=")

from services import birfatura as bf  # noqa: E402

ADMIN = {"id": "u1", "email": "admin@example.com", "is_super_admin": True}


@pytest.fixture
def env(tmp_path, monkeypatch):
    from localdb import AsyncIOMotorClient
    client = AsyncIOMotorClient(path=str(tmp_path / "t.db"))
    db = client["test"]
    pkg = types.ModuleType("routes")
    pkg.__path__ = [str(ROOT / "routes")]
    deps = types.ModuleType("routes.deps")
    deps.db = db
    deps.logger = __import__("logging").getLogger("bf-test")
    state = {"perms": ["*"]}

    def require_permission(key):
        async def _checker():
            if "*" not in state["perms"] and key not in state["perms"]:
                from fastapi import HTTPException
                raise HTTPException(403, "yetki yok")
            return ADMIN
        return _checker

    deps.require_permission = require_permission
    deps.client_ip_from_request = lambda r: (r.client.host if r.client else "")
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.deps", deps)
    sys.modules.pop("routes.integrations_birfatura", None)
    mod = importlib.import_module("routes.integrations_birfatura")
    mod._failed_auth.clear()
    monkeypatch.setenv("PUBLIC_API_URL", "")
    monkeypatch.setenv("SITE_URL", "https://garajtek.com")
    app = FastAPI()
    app.include_router(mod.public_router, prefix="/api")
    app.include_router(mod.admin_router, prefix="/api")
    with TestClient(app) as c:
        yield SimpleNamespace(c=c, db=db, mod=mod, state=state, portal=c.portal)


def run(e, coro_fn, *a, **kw):
    return e.portal.call(lambda: coro_fn(*a, **kw))


def product(pid="p1", vat=10, **kw):
    return {"id": pid, "name": f"Ürün {pid}", "vat_rate": vat, "brand": "GarajTek", "stock_code": f"SKU-{pid}", **kw}


def order(num="W10001", status="confirmed", created="2026-07-10T09:00:00+00:00", **kw):
    o = {
        "id": f"id-{num}", "order_number": num, "status": status, "platform": "web",
        "payment_method": "credit_card", "payment_status": "paid", "created_at": created,
        "items": [{"product_id": "p1", "product_name": "Ceket", "quantity": 2, "price": 550.0,
                   "size": "M", "color": "Siyah", "barcode": "8680000000011", "sku": "CKT-1"}],
        "shipping_address": {"first_name": "Ayşe", "last_name": "Yılmaz", "address": "Örnek Mah. No:1",
                             "district": "Çankaya", "city": "Ankara", "phone": "+90 532 111 22 33",
                             "email": "ayse@example.com", "postal_code": "06000"},
        "billing_info": {"is_corporate": False},
        "subtotal": 1100.0, "shipping_cost": 0.0, "discount": 0.0, "total": 1100.0,
    }
    o.update(kw)
    return o


def setup(e, *, enabled=True, orders=(), products=(product(),), **settings):
    r = e.c.post("/api/integrations/birfatura/token")
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    body = {"enabled": enabled, **settings}
    r = e.c.put("/api/integrations/birfatura/settings", json=body)
    assert r.status_code == 200, r.text
    for p in products:
        run(e, e.db.products.insert_one, dict(p))
    for o in orders:
        run(e, e.db.orders.insert_one, dict(o))
    return token


def pull(e, token, sid=1, start="01.07.2026 00:00:00", end="31.07.2026 23:59:59"):
    return e.c.post("/api/birfatura/api/orders", headers={"token": token},
                    json={"orderStatusId": sid, "startDateTime": start, "endDateTime": end})


# --------------------------------------------------------------------------- güvenlik
def test_disabled_integration_is_404(env):
    token = setup(env, enabled=False, orders=[order()])
    r = env.c.post("/api/birfatura/api/orderStatus", headers={"token": token})
    assert r.status_code == 404


def test_missing_and_invalid_token_401(env):
    setup(env, orders=[order()])
    assert env.c.post("/api/birfatura/api/orderStatus").status_code == 401
    r = env.c.post("/api/birfatura/api/orders", headers={"token": "yanlis"}, json={})
    assert r.status_code == 401 and r.json()["Success"] is False
    logs = env.c.get("/api/integrations/birfatura/logs").json()["logs"]
    assert any(l["status"] == 401 for l in logs)
    assert all("yanlis" not in str(l) for l in logs)


def test_brute_force_lockout_429(env):
    token = setup(env)
    for _ in range(10):
        env.c.post("/api/birfatura/api/orderStatus", headers={"token": "x"})
    r = env.c.post("/api/birfatura/api/orderStatus", headers={"token": token})
    assert r.status_code == 429 and r.headers.get("Retry-After")


def test_token_stored_encrypted_and_never_returned(env):
    token = setup(env)
    doc = run(env, env.db.settings.find_one, {"id": "birfatura"})
    assert token not in str(doc) and doc["token_enc"].startswith("v1:")
    view = env.c.get("/api/integrations/birfatura/settings").json()
    assert token not in str(view) and view["has_token"] and view["token_hint"] == token[-4:]
    assert view["urls"]["orders"].endswith("/api/birfatura/api/orders")


def test_regenerate_invalidates_old_token(env):
    old = setup(env)
    new = env.c.post("/api/integrations/birfatura/token").json()["token"]
    assert env.c.post("/api/birfatura/api/orderStatus", headers={"token": old}).status_code == 401
    assert env.c.post("/api/birfatura/api/orderStatus", headers={"token": new}).status_code == 200


def test_enable_requires_token_and_permission(env):
    r = env.c.put("/api/integrations/birfatura/settings", json={"enabled": True})
    assert r.status_code == 400
    env.state["perms"] = ["orders.view"]
    assert env.c.get("/api/integrations/birfatura/settings").status_code == 403


# --------------------------------------------------------------------------- sözlükler
def test_dictionaries(env):
    token = setup(env)
    r = env.c.post("/api/birfatura/api/orderStatus", headers={"token": token})
    assert r.status_code == 200
    assert r.json()["OrderStatus"][0] == {"Id": 1, "Value": "Onaylandı (faturalanabilir)"}
    r = env.c.post("/api/birfatura/api/paymentMethods", headers={"token": token})
    assert [m["Id"] for m in r.json()["PaymentMethods"]] == [1, 2, 3]


# --------------------------------------------------------------------------- sipariş çekimi
def test_date_filter_and_validation(env):
    token = setup(env, orders=[
        order("W10001", created="2026-07-10T09:00:00+00:00"),
        # 31.07 23:59:59 TR = 31.07 20:59:59 UTC → 21:30 UTC aralık DIŞI
        order("W10002", created="2026-07-31T21:30:00+00:00"),
        order("W10003", created="2026-06-30T20:59:00+00:00"),   # 30.06 23:59 TR → dışarıda
        order("W10004", created="2026-06-30T21:00:00+00:00"),   # 01.07 00:00 TR → içeride
    ])
    r = pull(env, token)
    assert r.status_code == 200, r.text
    assert sorted(o["OrderCode"] for o in r.json()["Orders"]) == ["W10001", "W10004"]
    assert pull(env, token, start="2026-07-01").status_code == 422
    assert pull(env, token, start="31.02.2026 00:00:00").status_code == 422
    assert pull(env, token, start="10.07.2026 00:00:00", end="01.07.2026 00:00:00").status_code == 422
    assert pull(env, token, start="01.01.2026 00:00:00", end="31.07.2026 00:00:00").status_code == 422


def test_status_filtering_and_unknown_group(env):
    token = setup(env, orders=[
        order("W10001", status="confirmed"), order("W10002", status="shipped"),
        order("W10003", status="awaiting_payment"), order("W10004", status="cancelled"),
        order("W10005", status="delivered"),
    ])
    codes = lambda sid: sorted(o["OrderCode"] for o in pull(env, token, sid).json()["Orders"])  # noqa
    assert codes(1) == ["W10001", "W10002", "W10005"]
    assert codes(2) == ["W10002"]
    assert codes(3) == ["W10005"]
    assert codes(99) == []
    assert pull(env, token, sid="abc").status_code == 422


def test_custom_status_groups(env):
    token = setup(env, orders=[order("W10001", status="preparing"), order("W10002", status="confirmed")],
                  status_groups=[{"id": 7, "name": "Hazırlanıyor", "statuses": ["preparing"]}])
    r = env.c.post("/api/birfatura/api/orderStatus", headers={"token": token})
    assert r.json()["OrderStatus"] == [{"Id": 7, "Value": "Hazırlanıyor"}]
    assert [o["OrderCode"] for o in pull(env, token, 7).json()["Orders"]] == ["W10001"]
    bad = env.c.put("/api/integrations/birfatura/settings",
                    json={"status_groups": [{"id": 1, "name": "x", "statuses": ["yok_boyle"]}]})
    assert bad.status_code == 400


def test_skips_marketplace_zero_total_and_invoiced_elsewhere(env):
    token = setup(env, orders=[
        order("W10001"),
        order("W10002", platform="other"),
        order("W10003", total=0.0),
        order("W10004", invoice_issued=True, invoice_provider="manual", invoice_number="MANUEL-1"),
        order("W10005", invoice_issued=True, invoice_provider="birfatura", invoice_number="ARS1"),
    ])
    assert sorted(o["OrderCode"] for o in pull(env, token).json()["Orders"]) == ["W10001", "W10005"]
    logs = env.c.get("/api/integrations/birfatura/logs").json()["logs"]
    assert "W10002 (site dışı kanal kaydı)" in logs[0]["message"]


def test_field_mapping_individual(env):
    token = setup(env, orders=[order()])
    o = pull(env, token).json()["Orders"][0]
    assert o["OrderId"] == 10001 and o["OrderCode"] == "W10001"
    assert o["OrderDate"] == "10.07.2026 12:00:00"           # UTC 09:00 → TR 12:00
    assert o["BillingName"] == "Ayşe Yılmaz" and o["BillingTown"] == "Çankaya" and o["BillingCity"] == "Ankara"
    assert o["BillingMobilePhone"] == "05321112233" and o["SSNTCNo"] == "11111111111"
    assert "TaxNo" not in o and o["Email"] == "ayse@example.com"
    assert o["ShippingName"] == "Ayşe Yılmaz" and o["ShippingZipCode"] == "06000"
    assert o["PaymentTypeId"] == 1 and o["Currency"] == "TRY"
    line = o["OrderDetails"][0]
    assert line["ProductCode"] == "CKT-1" and line["Barcode"] == "8680000000011"
    assert line["ProductQuantity"] == 2 and line["VatRate"] == 10
    assert line["ProductUnitPriceTaxIncluding"] == 550 and line["ProductUnitPriceTaxExcluding"] == 500
    assert {"Type": "Beden", "Value": "M"} in line["Variants"]
    assert isinstance(line["ProductId"], int)
    assert o["ProductsTotalTaxIncluding"] == 1100 and o["ProductsTotalTaxExcluding"] == 1000
    assert o["TotalPaidTaxIncluding"] == 1100 and o["TotalPaidTaxExcluding"] == 1000
    for f in bf.REQUIRED_ORDER_FIELDS:
        assert o.get(f) not in (None, "", []), f


def test_kdv_split_discount_shipping_cod_giftwrap(env):
    o = order(
        "W10010", payment_method="cash_on_delivery",
        items=[
            {"product_id": "p1", "product_name": "Ceket", "quantity": 1, "price": 1100.0},   # %10
            {"product_id": "p2", "product_name": "Kemer", "quantity": 1, "price": 240.0},    # %20
        ],
        subtotal=1340.0, discount=134.0, shipping_cost=60.0, cod_fee=30.0,
        gift_wrap=True, gift_wrap_price=24.0,
        total=1340.0 - 134.0 + 60.0 + 30.0 + 24.0,
    )
    token = setup(env, orders=[o], products=[product("p1", 10), product("p2", 20)])
    m = pull(env, token).json()["Orders"][0]
    d = {x["ProductName"]: x for x in m["OrderDetails"]}
    # %10 indirim oransal: Ceket 1100→990, Kemer 240→216
    assert d["Ceket"]["VatRate"] == 10 and d["Ceket"]["ProductUnitPriceTaxIncluding"] == 990
    assert d["Ceket"]["ProductUnitPriceTaxExcluding"] == 900
    assert d["Kemer"]["VatRate"] == 20 and d["Kemer"]["ProductUnitPriceTaxIncluding"] == 216
    assert d["Kemer"]["ProductUnitPriceTaxExcluding"] == 180
    assert d["Hediye Paketi"]["VatRate"] == 20 and d["Hediye Paketi"]["ProductUnitPriceTaxIncluding"] == 24
    assert m["DiscountTotalTaxIncluding"] == 0
    assert m["ShippingChargeTotalTaxIncluding"] == 60 and m["ShippingChargeTotalTaxExcluding"] == 50
    assert m["PayingAtTheDoorChargeTotalTaxIncluding"] == 30 and m["PayingAtTheDoorChargeTotalTaxExcluding"] == 25
    assert m["PaymentTypeId"] == 3
    assert m["TotalPaidTaxIncluding"] == o["total"]                        # 1320
    assert m["TotalPaidTaxExcluding"] == 900 + 180 + 20 + 50 + 25          # 1175


def test_line_discount_mode(env):
    o = order(items=[{"product_id": "p1", "product_name": "Ceket", "quantity": 2, "price": 500.0}],
              subtotal=1000.0, discount=100.0, total=900.0)
    token = setup(env, orders=[o], discount_mode="line")
    m = pull(env, token).json()["Orders"][0]
    line = m["OrderDetails"][0]
    assert line["ProductUnitPriceTaxIncluding"] == 500
    assert line["DiscountUnitTaxIncluding"] == 50
    assert m["ProductsTotalTaxIncluding"] == 1000 and m["TotalPaidTaxIncluding"] == 900  # brüt; iskonto satırda
    assert m["DiscountTotalTaxIncluding"] == 0


def test_frozen_item_discount_is_respected(env):
    o = order(items=[
        {"product_id": "p1", "product_name": "A", "quantity": 1, "price": 600.0, "discount_amount": 120.0},
        {"product_id": "p1", "product_name": "B", "quantity": 1, "price": 400.0, "discount_amount": 0.0},
    ], subtotal=1000.0, discount=120.0, total=880.0)
    token = setup(env, orders=[o])
    d = {x["ProductName"]: x for x in pull(env, token).json()["Orders"][0]["OrderDetails"]}
    assert d["A"]["ProductUnitPriceTaxIncluding"] == 480 and d["B"]["ProductUnitPriceTaxIncluding"] == 400


def test_corporate_billing(env):
    o = order(billing_info={"is_corporate": True, "company_name": "Örnek A.Ş.", "tax_office": "Çankaya",
                            "tax_number": "1234567890"})
    o2 = order("W10002", billing_info={"is_corporate": True, "company_name": "Ali Veli Ticaret",
                                       "tax_office": "Kadıköy", "tax_number": "12345678901"})
    token = setup(env, orders=[o, o2])
    res = {x["OrderCode"]: x for x in pull(env, token).json()["Orders"]}
    a = res["W10001"]
    assert a["BillingName"] == "Örnek A.Ş." and a["TaxOffice"] == "Çankaya" and a["TaxNo"] == "1234567890"
    assert "SSNTCNo" not in a
    b = res["W10002"]
    assert b["SSNTCNo"] == "12345678901" and b["TaxOffice"] == "Kadıköy" and "TaxNo" not in b


def test_installment_charge(env):
    o = order(iyzico_retrieve_response={"installment": 3, "paidPrice": "1155.00"})
    token = setup(env, orders=[o])
    m = pull(env, token).json()["Orders"][0]
    assert m["InstallmentChargeTotalTaxIncluding"] == 55 and m["InstallmentChargeTotalTaxExcluding"] == 50
    assert m["TotalPaidTaxIncluding"] == 1155
    assert "3 taksit" in m["InvoiceExplanation"]


def test_non_w_order_number_gets_stable_numeric_id(env):
    token = setup(env, orders=[order("TY-ABC", platform="web")])
    first = pull(env, token).json()["Orders"][0]["OrderId"]
    assert first >= 900000001
    assert pull(env, token).json()["Orders"][0]["OrderId"] == first


# --------------------------------------------------------------------------- geri yazım
def _postback(e, token, **body):
    base = {"orderId": 10001, "faturaUrl": "https://uygulama.birfatura.com/dosyagetir?tur=1&guid=a.pdf",
            "faturaNo": "ARS2026000000001", "faturaTarihi": "16.07.2026 14:27:09"}
    base.update(body)
    return e.c.post("/api/birfatura/api/invoiceLinkUpdate", headers={"token": token}, json=base)


def test_invoice_postback_stores_and_is_idempotent(env):
    token = setup(env, orders=[order()])
    r = _postback(env, token)
    assert r.status_code == 200 and r.json() == {"Success": True, "Message": "Fatura bağlantısı güncellendi."}
    o = run(env, env.db.orders.find_one, {"id": "id-W10001"})
    assert o["invoice_issued"] is True and o["invoice_provider"] == "birfatura"
    assert o["invoice_number"] == "ARS2026000000001"
    assert o["invoice_pdf_url"].startswith("https://uygulama.birfatura.com/")
    assert o["invoice_issued_at"].startswith("2026-07-16T11:27:09")
    n_events = run(env, env.db.order_events.count_documents, {"order_id": "id-W10001"})
    assert _postback(env, token).status_code == 200                     # tekrar
    assert run(env, env.db.order_events.count_documents, {"order_id": "id-W10001"}) == n_events
    o = run(env, env.db.orders.find_one, {"id": "id-W10001"})
    assert not o.get("invoice_history")


def test_invoice_postback_rejects_untrusted_and_unknown(env):
    token = setup(env, orders=[order()])
    assert _postback(env, token, faturaUrl="https://evilbirfatura.com/x.pdf").status_code == 422
    assert _postback(env, token, faturaUrl="http://uygulama.birfatura.com/x.pdf").status_code == 422
    assert _postback(env, token, faturaUrl="https://uygulama.birfatura.com.evil.test/x").status_code == 422
    assert _postback(env, token, orderId="99999").status_code == 404
    assert _postback(env, token, faturaTarihi="2026-07-16").status_code == 422
    assert _postback(env, token, orderId="a b").status_code == 422
    o = run(env, env.db.orders.find_one, {"id": "id-W10001"})
    assert not o.get("invoice_issued")


def test_invoice_postback_by_order_number_and_history(env):
    token = setup(env, orders=[order(invoice_issued=True, invoice_provider="manual", invoice_number="MANUEL-1")])
    assert _postback(env, token, orderId="W10001", faturaNo="ARS2").status_code == 200
    o = run(env, env.db.orders.find_one, {"id": "id-W10001"})
    assert o["invoice_number"] == "ARS2" and o["invoice_history"][0]["number"] == "MANUEL-1"


def test_cargo_update(env):
    token = setup(env, orders=[order(), order("W10002", cargo_tracking_number="MNG123")])
    body = {"orderId": 10001, "orderStatusId": 2, "cargoTrackingCode": "AT27NN805",
            "cargoTrackingCodeUrl": "https://kargotakip.example/AT27NN805", "cargoCompany": "Aras",
            "updateDateTime": "16.07.2026 14:27:09"}
    r = env.c.post("/api/birfatura/api/orderCargoUpdate", headers={"token": token}, json=body)
    assert r.status_code == 200 and r.json()["Success"] is True
    o = run(env, env.db.orders.find_one, {"id": "id-W10001"})
    assert o["cargo_tracking_number"] == "AT27NN805" and o["cargo_provider_name"] == "Aras"
    assert o["status"] == "confirmed"                                    # durum değişmez
    body["orderId"] = 10002
    env.c.post("/api/birfatura/api/orderCargoUpdate", headers={"token": token}, json=body)
    o2 = run(env, env.db.orders.find_one, {"id": "id-W10002"})
    assert o2["cargo_tracking_number"] == "MNG123" and o2["birfatura_cargo"]["tracking_code"] == "AT27NN805"


def test_admin_test_endpoint_and_audit(env):
    setup(env, orders=[order(created="2099-01-01T00:00:00+00:00")])
    r = env.c.post("/api/integrations/birfatura/test", json={"days": 7})
    assert r.status_code == 200
    j = r.json()
    assert j["has_token"] and j["checks"][0]["ok"] and "sample" in j
    audits = run(env, lambda: env.db.audit_logs.find({}, {"_id": 0}).to_list(50))
    assert any(a["action"] == "integration.birfatura.settings" for a in audits)
    assert any(a["action"] == "integration.birfatura.token_regenerate" for a in audits)


# --------------------------------------------------------------------------- saf yardımcılar
def test_pure_helpers():
    assert bf.parse_bf_date("01.07.2026 00:00:00").isoformat() == "2026-06-30T21:00:00+00:00"
    assert bf.parse_bf_date("1.7.2026 00:00:00") is None
    assert bf.host_allowed("https://a.birfatura.com/x", ["*.birfatura.com"])
    assert not bf.host_allowed("https://birfatura.com/x", ["*.birfatura.com"])
    assert bf.host_allowed("https://birfatura.com/x", ["birfatura.com"])
    assert not bf.host_allowed("https://user:pw@a.birfatura.com/x", ["*.birfatura.com"])
    assert bf.numeric_order_id({"order_number": "W10500"}) == 10500
    assert bf.numeric_product_id({"product_id": "abc"}) == bf.numeric_product_id({"product_id": "abc"})
    assert bf.numeric_product_id({"product_id": "abc"}) < 2 ** 53
