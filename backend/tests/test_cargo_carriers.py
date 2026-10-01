"""Kargo taşıyıcı kayıt defteri + sipariş akışı (Aras/PTT) — gerçek localdb (geçici dosya),
SOAP katmanı sahte. routes.orders yerine küçük bir stub modül kullanılır (ağır import yok).
"""
import asyncio
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("pymongo")

from localdb import AsyncIOMotorClient  # noqa: E402

import aras_kargo_client as ac  # noqa: E402
import ptt_kargo_client as pc  # noqa: E402
from cargo_carriers import registry, normalize_code, get_carrier  # noqa: E402
from cargo_carriers import service  # noqa: E402
from cargo_carriers.packages import compute_package  # noqa: E402


def run(coro):
    return asyncio.run(coro)


@pytest.fixture()
def db(tmp_path, monkeypatch):
    # routes.orders / routes.provider_settings stub'ları (gönderici bilgisi, olay günlüğü, şifre çözme)
    events = []
    orders_stub = types.ModuleType("routes.orders")

    async def _get_sender_info():
        return {"name": "Garaj Tekstil", "phone": "2241112233", "address": "Sanayi 1", "city": "Bursa",
                "district": "Osmangazi"}

    async def _log_order_event(order_id, event_type, description, current_user=None, meta=None, order_number=None):
        events.append(description)

    async def _order_notify_vars(order, **extra):
        return dict(extra)

    async def _get_mng_settings():
        return {"username": "mnguser", "password": "x", "env": "test", "is_active": True}

    orders_stub._get_sender_info = _get_sender_info
    orders_stub._log_order_event = _log_order_event
    orders_stub._order_notify_vars = _order_notify_vars
    orders_stub._get_mng_settings = _get_mng_settings
    ps_stub = types.ModuleType("routes.provider_settings")
    ps_stub.decrypt_provider_doc = lambda kind, doc: doc
    routes_pkg = sys.modules.get("routes") or types.ModuleType("routes")
    monkeypatch.setitem(sys.modules, "routes", routes_pkg)
    monkeypatch.setitem(sys.modules, "routes.orders", orders_stub)
    monkeypatch.setitem(sys.modules, "routes.provider_settings", ps_stub)
    d = AsyncIOMotorClient(path=str(tmp_path / "store.db"))["shop"]
    d._events = events
    yield d
    d.client.close()


def _order(**kw):
    o = {"id": "o1", "order_number": "W10063", "status": "confirmed", "payment_method": "credit_card",
         "payment_status": "paid", "total": 1249.9, "created_at": "2026-10-01T10:00:00+00:00",
         "items": [{"product_id": "p1", "product_name": "Tişört", "quantity": 2}],
         "shipping_address": {"first_name": "Ayşe", "last_name": "Yılmaz", "phone": "0532 111 22 33",
                              "city": "34", "district": "Kadıköy", "address": "Çiçek Sok. No:5"}}
    o.update(kw)
    return o


async def _seed(db, order, providers):
    await db.orders.insert_one(dict(order))
    await db.products.insert_one({"id": "p1", "width": 30, "depth": 20, "height": 10, "weight": 0.4})
    await db.providers_config.insert_one({"kind": "cargo", "active_provider": "aras", "providers": providers})


ARAS_CFG = {"aras": {"username": "neodyum", "password": "nd2580", "customer_code": "1932448851342", "env": "test"}}
PTT_CFG = {"ptt": {"customer_number": "900000001", "password": "s", "env": "test",
                   "barcode_range_start": "275036560000", "barcode_range_end": "275036560002",
                   "odeme_sekli": "MH", "ek_hizmet": "SB"}}


# --------------------------------------------------------------------------- registry
def test_normalize_and_lookup():
    assert normalize_code("aras") == "ARAS" and normalize_code("Aras Kargo") == "ARAS"
    assert normalize_code("ptt") == "PTT" and normalize_code("DHL") == "MNG"
    assert get_carrier("ptt").name == "PTT Kargo"
    assert get_carrier("yurtici") is None


def test_default_carrier_resolution(db):
    async def go():
        assert await registry.resolve_default_code(db) == "MNG"          # hiçbir ayar yok
        await db.providers_config.insert_one({"kind": "cargo", "active_provider": "ptt", "providers": {}})
        assert await registry.resolve_default_code(db) == "PTT"          # provider ayarlarında aktif
        await db.settings.insert_one({"id": registry.CARRIER_SETTINGS_ID, "default_carrier": "ARAS"})
        assert await registry.resolve_default_code(db) == "ARAS"         # açık seçim önceliklidir
    run(go())


def test_tracking_urls():
    assert get_carrier("ARAS").tracking_url("123").endswith("code=123")
    assert get_carrier("PTT").tracking_url("2750365698456").endswith("q=2750365698456")
    assert "dhlecommerce" in get_carrier("MNG").tracking_url("1")


def test_compute_package_from_products_and_defaults():
    o = _order()
    pkg = compute_package(o, {"p1": {"width": 30, "depth": 20, "height": 10, "weight": 0.4}})
    assert pkg["desi"] == 4.0 and pkg["kg"] == 0.8 and pkg["source"] == "products"
    pkg2 = compute_package(o, {}, default_desi=2, default_kg=3)
    assert pkg2["desi"] == 2 and pkg2["kg"] == 3 and pkg2["source"] == "defaults"
    pkg3 = compute_package({**o, "cargo_package": {"desi": 7, "kg": 5, "pieces": 2}}, {})
    assert pkg3 == {"pieces": 2, "desi": 7.0, "kg": 5.0, "source": "order"}


# --------------------------------------------------------------------------- Aras akışı
def test_aras_create_refresh_cancel_flow(db, monkeypatch):
    calls = []
    set_ok = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><SetOrderResponse '
              'xmlns="http://tempuri.org/"><SetOrderResult><OrderResultInfo><ResultCode>0</ResultCode>'
              '<ResultMessage>Başarılı</ResultMessage></OrderResultInfo></SetOrderResult></SetOrderResponse>'
              '</soap:Body></soap:Envelope>')
    import json
    q = json.dumps({"QueryResult": {"Cargo": [{"MUSTERI_OZEL_KODU": "W10063", "KARGO_TAKIP_NO": "3513773163316",
                                                 "DURUM_KODU": "1", "DURUMU": "ÇIKIŞ ŞUBESİNDE"}]}})
    q_resp = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><GetQueryJSONResponse '
              f'xmlns="http://tempuri.org/"><GetQueryJSONResult>{q}</GetQueryJSONResult></GetQueryJSONResponse>'
              '</s:Body></s:Envelope>')
    cancel_ok = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body>'
                 '<CancelDispatchResponse xmlns="http://tempuri.org/"><CancelDispatchResult><ResultCode>0</ResultCode>'
                 '<ResultMessage>OK</ResultMessage></CancelDispatchResult></CancelDispatchResponse></soap:Body></soap:Envelope>')

    def fake(url, body, headers, timeout=25):
        act = headers.get("SOAPAction", "")
        calls.append((act, body))
        if "SetOrder" in act:
            return set_ok
        if "GetQueryJSON" in act:
            return q_resp
        if "CancelDispatch" in act:
            return cancel_ok
        raise AssertionError(act)

    monkeypatch.setattr(ac, "soap_post", fake)

    async def go():
        await _seed(db, _order(payment_method="cash_on_delivery"), ARAS_CFG)
        order = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        res = await service.create_shipment_for_order(db, order, "ARAS", {"email": "admin@x"})
        assert res["success"] and res["barcode"] == "W1006301" and res["cargo_provider_code"] == "ARAS"
        body = calls[0][1]
        assert "<IsCod>1</IsCod>" in body and "<CodAmount>1249.9</CodAmount>" in body
        assert "<ReceiverCityName>İSTANBUL</ReceiverCityName>" in body   # plaka kodu 34 → il adı
        assert "<VolumetricWeight>4</VolumetricWeight>" in body           # 30x20x10/3000 x2
        o = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        assert o["status"] == "preparing" and o["cargo_barcode_number"] == "W1006301"
        assert o["cargo_tracking_number"] == "" and o["cargo"]["tracking_number"] == "W1006301"
        assert o["cargo_company"] == "Aras"

        r = await service.refresh_order_tracking(db, o)
        assert r["tracking_number"] == "3513773163316" and r["new_status"] == "shipped"
        o = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        assert o["status"] == "shipped" and o["cargo_tracking_link"].endswith("code=3513773163316")

        # Kargoya verilmiş gönderi iptal edilemez
        with pytest.raises(Exception) as ei:
            await service.cancel_order_shipment(db, o, None)
        assert "iptal edilemez" in str(ei.value.detail)
        await db.orders.update_one({"id": "o1"}, {"$set": {"status": "preparing"}})
        o = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        r = await service.cancel_order_shipment(db, o, None)
        assert r["success"]
        o = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        assert o["status"] == "confirmed" and not o.get("cargo_barcode_number") and o["cargo_barcode_created"] is False
        assert any("iptal" in e for e in db._events)
        logs = [x async for x in db.cargo_logs.find({}, {"_id": 0})]
        assert {x["action"] for x in logs} == {"create_shipment", "cancel_shipment"}
    run(go())


def test_aras_error_is_502_and_logged(db, monkeypatch):
    err = ('<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><SetOrderResponse '
           'xmlns="http://tempuri.org/"><SetOrderResult><OrderResultInfo><ResultCode>1000</ResultCode>'
           '</OrderResultInfo></SetOrderResult></SetOrderResponse></soap:Body></soap:Envelope>')
    monkeypatch.setattr(ac, "soap_post", lambda *a, **k: err)

    async def go():
        await _seed(db, _order(), ARAS_CFG)
        order = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        with pytest.raises(Exception) as ei:
            await service.create_shipment_for_order(db, order, "ARAS")
        assert ei.value.status_code == 502 and "şifre" in ei.value.detail.lower()
        o = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        assert o["status"] == "confirmed" and not o.get("cargo_barcode_created")
        assert await db.cargo_logs.count_documents({"status": "error"}) == 1
    run(go())


def test_missing_config_and_address_validation(db):
    async def go():
        await _seed(db, _order(), {})
        order = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        with pytest.raises(Exception) as ei:
            await service.create_shipment_for_order(db, order, "ARAS")
        assert ei.value.status_code == 400 and "eksik" in ei.value.detail
        await db.providers_config.update_one({"kind": "cargo"}, {"$set": {"providers": ARAS_CFG}})
        bad = {**order, "shipping_address": {**order["shipping_address"], "district": ""}}
        with pytest.raises(Exception) as ei:
            await service.create_shipment_for_order(db, bad, "ARAS")
        assert "ilçe" in ei.value.detail
    run(go())


# --------------------------------------------------------------------------- PTT akışı
def test_ptt_barcode_allocation_sequence_and_exhaustion(db):
    async def go():
        cfg = PTT_CFG["ptt"]
        b1 = await service.allocate_ptt_barcode(db, cfg)
        b2 = await service.allocate_ptt_barcode(db, cfg)
        b3 = await service.allocate_ptt_barcode(db, cfg)
        assert [b[:12] for b in (b1, b2, b3)] == ["275036560000", "275036560001", "275036560002"]
        assert all(pc.is_valid_barcode(b) for b in (b1, b2, b3))
        with pytest.raises(Exception) as ei:
            await service.allocate_ptt_barcode(db, cfg)
        assert "tükendi" in ei.value.detail
        # yeni aralık → sayaç sıfırlanır
        b = await service.allocate_ptt_barcode(db, {**cfg, "barcode_range_start": "275036570000",
                                                    "barcode_range_end": "275036579999"})
        assert b[:12] == "275036570000"
    run(go())


def test_ptt_create_retry_reuses_barcode_then_poll_delivers(db, monkeypatch):
    state = {"fail": True}
    kabul_ok = ('<soapenv:Envelope xmlns:soapenv="http://www.w3.org/2003/05/soap-envelope"><soapenv:Body>'
                '<ns:kabulEkle2Response xmlns:ns="http://kabul.ptt.gov.tr"><ns:return><ax:aciklama xmlns:ax="x">BASARILI'
                '</ax:aciklama><ax:dongu xmlns:ax="x"><ax:barkod>{bc}</ax:barkod><ax:donguHataKodu>1</ax:donguHataKodu>'
                '</ax:dongu><ax:hataKodu xmlns:ax="x">1</ax:hataKodu></ns:return></ns:kabulEkle2Response>'
                '</soapenv:Body></soapenv:Envelope>')
    takip = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body><ns:r '
             'xmlns:ns="t"><ax:BARNO xmlns:ax="x">{bc}</ax:BARNO><ax:dongu xmlns:ax="x"><ax:IKODU>100</ax:IKODU>'
             '<ax:ISLEM>Teslim Edildi</ax:ISLEM><ax:ITARIH>03/10/2026</ax:ITARIH><ax:ISAAT>11:30:00</ax:ISAAT>'
             '<ax:siraNo>1</ax:siraNo></ax:dongu></ns:r></soapenv:Body></soapenv:Envelope>')
    sent = []

    def fake(url, body, headers, timeout=25):
        import re
        bc = (re.search(r"<xsd:barkodNo>(\d+)</xsd:barkodNo>", body) or re.search(r"<xsd:barkod>(\d+)<", body)).group(1)
        sent.append((url, bc, body))
        if "kabulEkle2" in headers.get("Content-Type", ""):
            if state["fail"]:
                state["fail"] = False
                from cargo_carriers.common import CarrierError
                raise CarrierError("Kargo servisine bağlanılamadı: ReadTimeout")
            return kabul_ok.format(bc=bc)
        return takip.format(bc=bc)

    monkeypatch.setattr(pc, "soap_post", fake)

    async def go():
        await _seed(db, _order(payment_method="cash_on_delivery"), PTT_CFG)
        order = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        with pytest.raises(Exception) as ei:
            await service.create_shipment_for_order(db, order, "PTT")
        assert ei.value.status_code == 502
        order = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        res = await service.create_shipment_for_order(db, order, "PTT")
        assert sent[0][1] == sent[1][1] == res["barcode"]          # aynı barkod tekrar kullanıldı
        body = sent[1][2]
        assert "<xsd:ekhizmet>SBOS</xsd:ekhizmet>" in body and "<xsd:odeme_sart_ucreti>1249.90<" in body
        assert "<xsd:agirlik>800</xsd:agirlik>" in body                 # 0.4kg x2 = 800 g
        o = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        assert o["cargo_tracking_number"] == res["barcode"] and "cargo_pending" not in o
        stats = await service.poll_tick(db)
        assert stats["processed"] == 1 and stats["delivered"] == 1
        o = await db.orders.find_one({"id": "o1"}, {"_id": 0})
        assert o["status"] == "delivered" and o["cargo"]["status"] == "delivered"
    run(go())


def test_mng_poll_query_excludes_aras_ptt(db):
    """scheduler._dhl_cargo_poll_tick sorgusundaki $nin filtresi: alanı olmayan (eski MNG) siparişler
    eşleşmeye devam eder, ARAS/PTT siparişleri dışarıda kalır."""
    async def go():
        await db.orders.insert_many([{"id": "a", "cargo_provider_code": "MNG"}, {"id": "b"},
                                     {"id": "c", "cargo_provider_code": "ARAS"}, {"id": "d", "cargo_provider_code": "PTT"}])
        ids = sorted([o["id"] async for o in db.orders.find({"cargo_provider_code": {"$nin": ["ARAS", "PTT"]}})])
        assert ids == ["a", "b"]
    run(go())
