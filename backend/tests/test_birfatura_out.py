"""BirFatura OutEBelgeV2 — panelden DOĞRUDAN fatura kesimi testleri.

HTTP çağrıları httpx.MockTransport ile taklit edilir (gerçek BirFatura/E-Dönüştür'e istek ATILMAZ).
Gönderdiğimiz gövdeler resmî dokümandan alınmış şemaya (fixtures/birfatura_outebelgev2.json)
alan adı / zorunluluk / tip açısından birebir doğrulanır."""
import json
import re
from pathlib import Path

import httpx
import pytest

from test_birfatura import env, order, product, run  # noqa: F401  (env = fixture)
from services import birfatura_out as bfo

KEYS = {"api_key": "API-KEY-1234567890abcd", "secret_key": "SECRET-abcdefghijkl9876",
        "integration_key": "INTEG-zzzzyyyyxxxx5555"}
SPEC = json.loads((Path(__file__).parent / "fixtures" / "birfatura_outebelgev2.json").read_text("utf-8"))
ALIAS = "urn:mail:defaultpk@ornek.com.tr"


class FakeBF:
    """BirFatura OutEBelgeV2 taklidi: çağrıları kaydeder, uç başına yanıt üretir."""

    def __init__(self):
        self.calls = []
        self.user_pk = []             # GetUserPK Result
        self.send = None              # None → başarı; callable(body) → httpx.Response ya da istisna
        self.pdf_link = "https://uygulama.edonustur.com/dosyagetir?tur=1&guid=fatura.pdf"
        self.credits = "1500"

    def ok(self, result, code="200"):
        return httpx.Response(200, json={"Success": True, "Message": "OK", "Code": code, "Result": result})

    def __call__(self, request: httpx.Request):
        op = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content or b"{}")
        self.calls.append({"op": op, "body": body, "headers": dict(request.headers), "url": str(request.url)})
        if op == "GetUserPK":
            return self.ok(self.user_pk)
        if op == "GetNumberOfCredits":
            return self.ok(self.credits)
        if op == "SendBasicInvoiceFromModel":
            if self.send:
                return self.send(body)
            return self.ok({"invoiceNo": "GRJ2026000000001", "zipped": None, "htmlString": "",
                            "pdfLink": "https://uygulama.edonustur.com/ilk-link.pdf"})
        if op == "GetPDFLinkByUUID":
            return self.ok([{"uuid": body["uuids"][0], "pdfLink": self.pdf_link, "success": "true", "message": ""}])
        return httpx.Response(404, json={"Success": False, "Message": "yok"})

    def ops(self, name):
        return [c for c in self.calls if c["op"] == name]


@pytest.fixture
def bfx(env):  # noqa: F811
    fake = FakeBF()
    env.mod.OUT_TRANSPORT = httpx.MockTransport(fake)
    env.fake = fake
    yield env
    env.mod.OUT_TRANSPORT = None


def configure(e, enabled=True, **extra):
    r = e.c.put("/api/integrations/birfatura/out/settings",
                json={**KEYS, "enabled": enabled, "company_vkn": "9990001112", **extra})
    assert r.status_code == 200, r.text
    return r.json()["out"]


def add(e, *orders, products=(product(),)):
    for p in products:
        run(e, e.db.products.insert_one, dict(p))
    for o in orders:
        run(e, e.db.orders.insert_one, dict(o))


def issue(e, oid="id-W10001"):
    return e.c.post(f"/api/integrations/birfatura/invoices/{oid}")


def get_order(e, oid="id-W10001"):
    return run(e, e.db.orders.find_one, {"id": oid})


CORP = {"is_corporate": True, "company_name": "Örnek A.Ş.", "tax_office": "Çankaya", "tax_number": "1234567801"}


# --------------------------------------------------------------------------- ayarlar / sırlar
def test_secrets_encrypted_and_never_returned(bfx):
    out = configure(bfx)
    assert out["configured"] and out["api_key_hint"] == "abcd" and out["secret_key_hint"] == "9876"
    doc = run(bfx, bfx.db.settings.find_one, {"id": "birfatura"})
    view = bfx.c.get("/api/integrations/birfatura/settings").json()
    audits = run(bfx, lambda: bfx.db.audit_logs.find({}, {"_id": 0}).to_list(50))
    for secret in KEYS.values():
        assert secret not in str(doc)
        assert secret not in json.dumps(view, ensure_ascii=False)
        assert secret not in str(audits)
    assert doc["out_api_key_enc"].startswith("v1:")
    assert view["out"]["has_integration_key"] and view["out"]["base_url"] == "https://uygulama.edonustur.com"
    # boş alan gönderilirse mevcut anahtar korunur
    r = bfx.c.put("/api/integrations/birfatura/out/settings", json={"api_key": "", "secret_key": None})
    assert r.status_code == 200 and r.json()["out"]["api_key_hint"] == "abcd"
    assert any(a["action"] == "integration.birfatura.out_settings" for a in audits)


def test_settings_validation(bfx):
    r = bfx.c.put("/api/integrations/birfatura/out/settings", json={"enabled": True})
    assert r.status_code == 400                                         # anahtarsız açılamaz
    for bad in ("http://uygulama.edonustur.com", "https://evil.example.com", "https://uygulama.edonustur.com.evil.io",
                "https://uygulama.edonustur.com/api", "https://user:pw@uygulama.birfatura.com"):
        r = bfx.c.put("/api/integrations/birfatura/out/settings", json={"base_url": bad})
        assert r.status_code == 400, bad
    r = bfx.c.put("/api/integrations/birfatura/out/settings", json={"base_url": "https://uygulama.birfatura.com/"})
    assert r.status_code == 200 and r.json()["out"]["base_url"] == "https://uygulama.birfatura.com"
    assert bfx.c.put("/api/integrations/birfatura/out/settings", json={"api_key": "a b"}).status_code == 400
    configure(bfx)
    r = bfx.c.put("/api/integrations/birfatura/out/settings", json={"clear_keys": True})
    o = r.json()["out"]
    assert not o["has_api_key"] and not o["enabled"] and not o["configured"]


def test_settings_require_integration_permission(bfx):
    bfx.state["perms"] = ["orders.view", "orders.invoice"]
    assert bfx.c.put("/api/integrations/birfatura/out/settings", json=KEYS).status_code == 403
    assert bfx.c.post("/api/integrations/birfatura/out/test").status_code == 403


def test_connection_test_reports_credits(bfx):
    assert bfx.c.post("/api/integrations/birfatura/out/test").json()["ok"] is False   # anahtar yok
    configure(bfx, enabled=False)
    r = bfx.c.post("/api/integrations/birfatura/out/test").json()
    assert r == {**r, "ok": True, "credits": "1500", "base_url": "https://uygulama.edonustur.com"}
    call = bfx.fake.ops("GetNumberOfCredits")[0]
    assert call["url"] == "https://uygulama.edonustur.com/api/OutEBelgeV2/GetNumberOfCredits"
    assert call["headers"]["x-api-key"] == KEYS["api_key"]
    assert call["headers"]["x-secret-key"] == KEYS["secret_key"]
    assert call["headers"]["x-integration-key"] == KEYS["integration_key"]
    assert call["body"] == {"kn": "9990001112"}
    assert bfx.c.get("/api/integrations/birfatura/settings").json()["out"]["last_credits"] == "1500"


def test_connection_test_error_is_turkish_and_hides_secrets(bfx):
    configure(bfx)
    bfx.mod.OUT_TRANSPORT = httpx.MockTransport(lambda req: httpx.Response(
        401, json={"Success": False, "Message": f"Invalid key {KEYS['secret_key']}", "Result": None}))
    r = bfx.c.post("/api/integrations/birfatura/out/test").json()
    assert r["ok"] is False and "anahtarları reddedildi" in r["detail"]
    assert KEYS["secret_key"] not in r["detail"]
    logs = bfx.c.get("/api/integrations/birfatura/logs").json()["logs"]
    assert all(s not in str(logs) for s in KEYS.values())


def test_status_endpoint(bfx):
    assert bfx.c.get("/api/integrations/birfatura/out/status").json()["configured"] is False
    configure(bfx, enabled=False)
    assert bfx.c.get("/api/integrations/birfatura/out/status").json()["configured"] is False
    configure(bfx)
    bfx.state["perms"] = ["orders.view"]
    assert bfx.c.get("/api/integrations/birfatura/out/status").json() == {
        "configured": True, "provider": "birfatura_outebelgev2"}


# --------------------------------------------------------------------------- kesim
def test_not_configured_is_400(bfx):
    add(bfx, order())
    r = issue(bfx)
    assert r.status_code == 400 and "yapılandırılmamış" in r.json()["detail"]
    assert not bfx.fake.calls


def test_individual_gets_e_arsiv_and_order_fields(bfx):
    configure(bfx)
    add(bfx, order())
    r = issue(bfx)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["success"] and j["invoice"]["invoice_type"] == "e-arsiv"
    assert not bfx.fake.ops("GetUserPK")                    # 11111111111 → sorgu yok
    sent = bfx.fake.ops("SendBasicInvoiceFromModel")[0]["body"]["invoice"]
    assert "receiverTag" not in sent and sent["taxNo"] == "11111111111"
    assert sent["totalPaidTaxIncluding"] == 1100 and sent["isDocumentNoAuto"] is True
    pdf_call = bfx.fake.ops("GetPDFLinkByUUID")[0]["body"]
    assert pdf_call == {"uuids": [sent["ettn"]], "systemType": "EARSIV"}
    o = get_order(bfx)
    assert o["invoice_issued"] is True and o["invoice_provider"] == "birfatura_outebelgev2"
    assert o["invoice_uuid"] == sent["ettn"] and o["invoice_number"] == "GRJ2026000000001"
    assert o["invoice_pdf_url"] == bfx.fake.pdf_link and o["invoice_type"] == "e-arsiv"
    assert o["invoice_issued_at"] and not o.get("birfatura_out_lock")
    ev = run(bfx, lambda: bfx.db.order_events.find({"order_id": "id-W10001"}, {"_id": 0}).to_list(10))
    assert any(x["event_type"] == "invoice" and "e-Arşiv" in x["description"] for x in ev)
    audits = run(bfx, lambda: bfx.db.audit_logs.find({}, {"_id": 0}).to_list(50))
    assert any(a["action"] == "order.invoice.birfatura_out" and a["success"] for a in audits)


def test_corporate_e_invoice_user_gets_e_fatura_with_receiver_tag(bfx):
    configure(bfx)
    bfx.fake.user_pk = [
        {"identifier": "1234567801", "title": "ÖRNEK A.Ş.", "type2": "", "name": "urn:mail:defaultgb@ornek.com.tr",
         "pkGbTurKod": "GB", "firstCreationTime": "2020-01-01T00:00:00Z"},
        {"identifier": "1234567801", "title": "ÖRNEK A.Ş.", "type2": "", "name": ALIAS,
         "pkGbTurKod": "PK", "firstCreationTime": "2020-01-01T00:00:00Z"},
    ]
    add(bfx, order(billing_info=CORP))
    r = issue(bfx)
    assert r.status_code == 200, r.text
    assert bfx.fake.ops("GetUserPK")[0]["body"] == {"kn": "1234567801"}
    sent = bfx.fake.ops("SendBasicInvoiceFromModel")[0]["body"]["invoice"]
    assert sent["receiverTag"] == ALIAS and sent["taxNo"] == "1234567801"
    assert sent["billingName"] == "Örnek A.Ş." and sent["taxOffice"] == "Çankaya"
    assert bfx.fake.ops("GetPDFLinkByUUID")[0]["body"]["systemType"] == "EFATURA"
    assert get_order(bfx)["invoice_type"] == "e-fatura"


def test_corporate_not_registered_gets_e_arsiv(bfx):
    configure(bfx)
    bfx.fake.user_pk = []
    add(bfx, order(billing_info=CORP))
    assert issue(bfx).status_code == 200
    sent = bfx.fake.ops("SendBasicInvoiceFromModel")[0]["body"]["invoice"]
    assert "receiverTag" not in sent
    assert get_order(bfx)["invoice_type"] == "e-arsiv"


def test_user_lookup_failure_aborts(bfx):
    configure(bfx)
    add(bfx, order(billing_info=CORP))
    fake = bfx.fake

    def handler(req):
        if req.url.path.endswith("GetUserPK"):
            return httpx.Response(500, json={"Success": False, "Message": "GİB servisi yanıt vermiyor"})
        return fake(req)
    bfx.mod.OUT_TRANSPORT = httpx.MockTransport(handler)
    r = issue(bfx)
    assert r.status_code == 502 and "mükellefiyeti sorgulanamadı" in r.json()["detail"]
    assert "GİB servisi yanıt vermiyor" in r.json()["detail"]
    assert not fake.ops("SendBasicInvoiceFromModel")
    o = get_order(bfx)
    assert not o.get("invoice_issued") and not o.get("birfatura_out_lock") and o["invoice_last_error"]


def test_idempotent_409(bfx):
    configure(bfx)
    add(bfx, order(), order("W10002", invoice_issued=True, invoice_provider="manual", invoice_number="MANUEL-1"))
    assert issue(bfx).status_code == 200
    r = issue(bfx)
    assert r.status_code == 409 and r.json()["invoice"]["invoice_number"] == "GRJ2026000000001"
    assert len(bfx.fake.ops("SendBasicInvoiceFromModel")) == 1
    r = issue(bfx, "id-W10002")
    assert r.status_code == 409 and r.json()["invoice"]["invoice_provider"] == "manual"
    assert len(bfx.fake.ops("SendBasicInvoiceFromModel")) == 1


def test_concurrent_lock_409(bfx):
    configure(bfx)
    from datetime import datetime, timezone
    add(bfx, order(birfatura_out_lock=datetime.now(timezone.utc).isoformat()),
        order("W10002", birfatura_out_lock="2020-01-01T00:00:00+00:00"))   # bayat kilit → geçer
    r = issue(bfx)
    assert r.status_code == 409 and "sürüyor" in r.json()["detail"]
    assert issue(bfx, "id-W10002").status_code == 200


@pytest.mark.parametrize("status", ["cancelled", "cancel_refunded", "cancel_requested", "returned", "refunded",
                                    "return_requested", "partial_refunded", "payment_failed", "pending"])
def test_cancelled_returned_and_unconfirmed_rejected(bfx, status):
    configure(bfx)
    add(bfx, order(status=status))
    r = issue(bfx)
    assert r.status_code == 400 and r.json()["detail"]
    assert not bfx.fake.calls and not get_order(bfx).get("invoice_issued")


def test_unpaid_bank_transfer_rejected(bfx):
    configure(bfx)
    add(bfx, order(payment_method="bank_transfer", payment_status="pending"))
    r = issue(bfx)
    assert r.status_code == 400 and "Havale" in r.json()["detail"]


def test_total_mismatch_rejected(bfx):
    configure(bfx)
    add(bfx, order(total=5000.0))           # kalemler 1100 TL → fatura toplamı sipariş toplamını tutmaz
    r = issue(bfx)
    assert r.status_code == 422 and "uyuşmuyor" in r.json()["detail"]
    assert not bfx.fake.ops("SendBasicInvoiceFromModel")
    assert not get_order(bfx).get("birfatura_out_lock")


def test_birfatura_error_is_turkish_and_retry_reuses_ettn(bfx):
    configure(bfx)
    add(bfx, order())
    bfx.fake.send = lambda body: httpx.Response(400, json={
        "Success": False, "Message": "Fatura tarihi hatalı", "Code": "400", "Result": "invoiceDate geçersiz"})
    r = issue(bfx)
    assert r.status_code == 502
    d = r.json()["detail"]
    assert "BirFatura isteği reddetti" in d and "Fatura tarihi hatalı" in d and "invoiceDate geçersiz" in d
    o = get_order(bfx)
    assert not o.get("invoice_issued") and not o.get("birfatura_out_lock")
    assert o["invoice_last_error"] == d
    first = bfx.fake.ops("SendBasicInvoiceFromModel")[0]["body"]["invoice"]["ettn"]
    assert o["birfatura_out_ettn"] == first
    bfx.fake.send = None
    assert issue(bfx).status_code == 200
    assert bfx.fake.ops("SendBasicInvoiceFromModel")[1]["body"]["invoice"]["ettn"] == first
    o = get_order(bfx)
    assert o["invoice_uuid"] == first and not o.get("birfatura_out_ettn")


def test_success_false_with_http_200(bfx):
    configure(bfx)
    add(bfx, order())
    bfx.fake.send = lambda body: httpx.Response(200, json={"Success": False, "Message": "Yetersiz kontör",
                                                           "Code": "K01", "Result": None})
    r = issue(bfx)
    assert r.status_code == 502 and "Yetersiz kontör" in r.json()["detail"]


def test_timeout_marks_maybe_sent_and_pull_skips(bfx):
    configure(bfx)
    token = bfx.c.post("/api/integrations/birfatura/token").json()["token"]
    bfx.c.put("/api/integrations/birfatura/settings", json={"enabled": True})
    add(bfx, order())

    def boom(body):
        raise httpx.ReadTimeout("zaman aşımı")
    bfx.fake.send = boom
    r = issue(bfx)
    assert r.status_code == 502 and r.json()["maybe_sent"] is True
    assert "kesilmiş olabilir" in r.json()["detail"]
    o = get_order(bfx)
    assert o["birfatura_out_maybe_sent"] is True and not o.get("birfatura_out_lock")
    pulled = bfx.c.post("/api/birfatura/api/orders", headers={"token": token}, json={
        "orderStatusId": 1, "startDateTime": "01.07.2026 00:00:00", "endDateTime": "31.07.2026 23:59:59"}).json()
    assert pulled["Orders"] == []                           # çekme entegrasyonu ikinci fatura kesmesin
    prev = bfx.c.get("/api/integrations/birfatura/invoices/id-W10001/preview").json()
    assert prev["maybe_sent"] is True


def test_pull_integration_skips_direct_invoiced(bfx):
    configure(bfx)
    token = bfx.c.post("/api/integrations/birfatura/token").json()["token"]
    bfx.c.put("/api/integrations/birfatura/settings", json={"enabled": True, "skip_invoiced_elsewhere": False})
    add(bfx, order())
    assert issue(bfx).status_code == 200
    pulled = bfx.c.post("/api/birfatura/api/orders", headers={"token": token}, json={
        "orderStatusId": 1, "startDateTime": "01.07.2026 00:00:00", "endDateTime": "31.07.2026 23:59:59"}).json()
    assert pulled["Orders"] == []


def test_invoice_requires_orders_invoice_permission(bfx):
    configure(bfx)
    add(bfx, order())
    bfx.state["perms"] = ["orders.view"]
    assert issue(bfx).status_code == 403
    assert bfx.c.get("/api/integrations/birfatura/invoices/id-W10001/preview").status_code == 403
    bfx.state["perms"] = ["orders.view", "orders.invoice"]
    assert issue(bfx).status_code == 200


def test_preview_does_not_issue(bfx):
    configure(bfx)
    bfx.fake.user_pk = [{"identifier": "1234567801", "name": ALIAS, "pkGbTurKod": "PK"}]
    add(bfx, order(billing_info=CORP, shipping_cost=60.0, total=1160.0))
    p = bfx.c.get("/api/integrations/birfatura/invoices/id-W10001/preview").json()
    assert p["configured"] and p["invoice_type"] == "e-fatura" and p["type_source"] == "gib"
    assert p["total_incl"] == 1160 and p["order_total"] == 1160 and p["problems"] == []
    assert p["receiver"]["name"] == "Örnek A.Ş." and p["receiver_tag"] == ALIAS
    assert p["vat"] == round(1160 - p["total_excl"], 2)
    assert not bfx.fake.ops("SendBasicInvoiceFromModel")
    assert not get_order(bfx).get("invoice_issued")


def test_preview_lookup_error_is_tolerated(bfx):
    configure(bfx)
    bfx.mod.OUT_TRANSPORT = httpx.MockTransport(lambda req: httpx.Response(503, text="bakım"))
    add(bfx, order(billing_info=CORP))
    p = bfx.c.get("/api/integrations/birfatura/invoices/id-W10001/preview").json()
    assert p["type_source"] == "bilinmiyor" and p["invoice_type"] == "" and "sunucu hatası" in p["lookup_error"]


def test_pdf_pending_then_refresh(bfx):
    configure(bfx)
    add(bfx, order())
    bfx.fake.pdf_link = ""
    bfx.fake.send = lambda body: bfx.fake.ok({"invoiceNo": "GRJ1", "pdfLink": ""})
    j = issue(bfx).json()
    assert j["invoice"]["invoice_pdf_url"] == "" and "PDF" in j["message"]
    r = bfx.c.post("/api/integrations/birfatura/invoices/id-W10001/pdf").json()
    assert r["success"] is False
    bfx.fake.pdf_link = "https://uygulama.edonustur.com/hazir.pdf"
    r = bfx.c.post("/api/integrations/birfatura/invoices/id-W10001/pdf").json()
    assert r == {"success": True, "invoice_pdf_url": "https://uygulama.edonustur.com/hazir.pdf"}
    o = get_order(bfx)
    assert o["invoice_pdf_url"] == r["invoice_pdf_url"] and o["birfatura_out"]["pdf_pending"] is False


# --------------------------------------------------------------------------- resmî şema uyumu
def _props(name):
    s = SPEC["schemas"][name]
    return {p["name"]: p for p in s["properties"]}, set(s.get("required") or [])


def _check(obj, name, path, errors):
    props, req = _props(name)
    if not isinstance(obj, dict):
        errors.append(f"{path}: nesne bekleniyor")
        return
    for k in req:
        v = obj.get(k)
        if v is None or v == "" or v == []:
            errors.append(f"{path}.{k}: zorunlu alan boş/eksik")
    for k, v in obj.items():
        if k not in props:
            errors.append(f"{path}.{k}: resmî şemada yok")
            continue
        p = props[k]
        t = p["type"]
        if v is None:
            continue
        if p.get("enum") and v not in p["enum"]:
            errors.append(f"{path}.{k}: {v!r} izinli değerlerden değil {p['enum']}")
        if p.get("ref") and p["ref"] in SPEC["schemas"]:
            sub = SPEC["schemas"][p["ref"]]
            if sub.get("enum"):
                if v not in sub["enum"]:
                    errors.append(f"{path}.{k}: {v!r} {p['ref']} enum'unda yok")
            else:
                _check(v, p["ref"], f"{path}.{k}", errors)
            continue
        if t.startswith("array"):
            if not isinstance(v, list):
                errors.append(f"{path}.{k}: dizi bekleniyor")
                continue
            item_ref = p.get("itemsRef")
            for i, it in enumerate(v):
                if item_ref:
                    _check(it, item_ref, f"{path}.{k}[{i}]", errors)
                elif "string" in t and not isinstance(it, str):
                    errors.append(f"{path}.{k}[{i}]: string bekleniyor")
            continue
        if t.startswith("integer") and not (isinstance(v, int) and not isinstance(v, bool)):
            errors.append(f"{path}.{k}: integer bekleniyor, {type(v).__name__}")
        elif t.startswith("number") and not (isinstance(v, (int, float)) and not isinstance(v, bool)):
            errors.append(f"{path}.{k}: number bekleniyor, {type(v).__name__}")
        elif t.startswith("boolean") and not isinstance(v, bool):
            errors.append(f"{path}.{k}: boolean bekleniyor, {type(v).__name__}")
        elif t.startswith("string") and not isinstance(v, str):
            errors.append(f"{path}.{k}: string bekleniyor, {type(v).__name__}")
        if t == "string (date)" and isinstance(v, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            errors.append(f"{path}.{k}: tarih biçimi yyyy-MM-dd değil: {v}")


def _endpoint(op):
    return next(e for e in SPEC["endpoints"] if e["path"].endswith("/" + op))


def test_fixture_is_official_contract():
    """Fikstür resmî dokümanın ilgili kısmı; kullandığımız alan listeleri onunla birebir aynı."""
    inv, inv_req = _props("Invoice")
    det, det_req = _props("OrderDetail")
    assert list(inv) == list(bfo.INVOICE_FIELDS) and inv_req == set(bfo.INVOICE_REQUIRED)
    assert list(det) == list(bfo.DETAIL_FIELDS) and det_req == set(bfo.DETAIL_REQUIRED)
    assert set(SPEC["schemas"]["SystemTypeCodes"]["enum"]) >= {bfo.SYSTEM_EFATURA, bfo.SYSTEM_EARSIV}
    assert SPEC["baseUrl"] == bfo.DEFAULT_BASE_URL
    for op in ("SendBasicInvoiceFromModel", "GetUserPK", "GetPDFLinkByUUID", "GetNumberOfCredits"):
        e = _endpoint(op)
        assert e["method"] == "POST" and e["path"] == f"{bfo.API_PREFIX}/{op}"
        assert {p["name"] for p in e["parameters"] if p["in"] == "header" and p["required"]} == {
            "X-Api-Key", "X-Secret-Key", "X-Integration-Key"}


def test_request_bodies_match_official_schema(bfx):
    """Çeşitli siparişler için BirFatura'ya giden TÜM gövdeler resmî istek şemalarına uymalı."""
    configure(bfx)
    bfx.fake.user_pk = [{"identifier": "1234567801", "name": ALIAS, "pkGbTurKod": "PK"}]
    orders = [
        order("W20001"),
        order("W20002", payment_method="cash_on_delivery", cod_fee=30.0, shipping_cost=60.0, discount=50.0,
              total=1100.0 + 30 + 60 - 50),
        order("W20003", payment_method="bank_transfer", billing_info=CORP),
        order("W20004", iyzico_retrieve_response={"installment": 3, "paidPrice": "1155.00"}),
        order("W20005", gift_wrap=True, gift_wrap_price=24.0, total=1124.0,
              items=[{"product_id": "p1", "product_name": "Ceket", "quantity": 1, "price": 600.0},
                     {"product_id": "p2", "product_name": "Kemer", "quantity": 1, "price": 500.0, "size": "L"}]),
    ]
    add(bfx, *orders, products=(product("p1", 10), product("p2", 20)))
    for o in orders:
        r = issue(bfx, o["id"])
        assert r.status_code == 200, (o["order_number"], r.text)
    # satır iskontosu modu da şemaya uymalı
    bfx.c.put("/api/integrations/birfatura/settings", json={"discount_mode": "line"})
    add(bfx, order("W20006", discount=100.0, total=1000.0), products=())
    assert issue(bfx, "id-W20006").status_code == 200

    errors = []
    schema_for = {"SendBasicInvoiceFromModel": "SendBasicInvoiceFromModelRequestData",
                  "GetUserPK": "GetUserPKRequestData", "GetPDFLinkByUUID": "GetPDFLinkByUUIDRequestData",
                  "GetNumberOfCredits": "GetUserPKRequestData"}
    bfx.c.post("/api/integrations/birfatura/out/test")
    seen = set()
    for c in bfx.fake.calls:
        assert _endpoint(c["op"])["request"]["schemaName"] == schema_for[c["op"]]
        _check(c["body"], schema_for[c["op"]], c["op"], errors)
        seen.add(c["op"])
    assert seen == set(schema_for)
    assert not errors, "\n".join(errors)

    sends = [c["body"]["invoice"] for c in bfx.fake.ops("SendBasicInvoiceFromModel")]
    by_code = {s["orderCode"]: s for s in sends}
    assert by_code["W20002"]["payingAtTheDoorChargeTotalTaxIncluding"] == 30
    assert by_code["W20002"]["shippingChargeTotalTaxIncluding"] == 60
    assert by_code["W20002"]["totalPaidTaxIncluding"] == 1140
    assert by_code["W20004"]["installmentChargeTotalTaxIncluding"] == 55
    assert by_code["W20004"]["totalPaidTaxIncluding"] == 1155
    w5 = {d["productName"]: d for d in by_code["W20005"]["orderDetails"]}
    assert w5["Hediye Paketi"]["productUnitPriceTaxIncluding"] == 24 and w5["Kemer"]["vatRate"] == 20
    assert w5["Kemer"]["productNote"] == "Beden: L"
    w6 = by_code["W20006"]["orderDetails"][0]
    assert w6["discountUnitTaxIncluding"] == 50 and w6["discountIsPercentUnit"] == 0
    assert by_code["W20006"]["totalPaidTaxIncluding"] == 1000
    assert by_code["W20001"]["orderDate"] == "2026-07-10"
    for s in sends:
        assert re.fullmatch(r"[0-9a-f-]{36}", s["ettn"])


# --------------------------------------------------------------------------- saf yardımcılar
def test_pure_helpers():
    assert bfo.normalize_base_url("https://uygulama.edonustur.com/") == "https://uygulama.edonustur.com"
    assert bfo.normalize_base_url("https://UYGULAMA.birfatura.com") == "https://uygulama.birfatura.com"
    assert bfo.normalize_base_url("https://uygulama.edonustur.com:8443") is None
    assert bfo.normalize_base_url("") is None
    assert bfo.pick_receiver([]) == (False, None)
    assert bfo.pick_receiver([{"name": "urn:mail:x@y", "pkGbTurKod": "GB"}]) == (False, None)
    assert bfo.pick_receiver([{"identifier": "1", "title": "A", "name": ALIAS}]) == (True, ALIAS)
    assert bfo.pick_receiver([{"identifier": "1", "title": "A"}]) == (True, None)
    assert not bfo.should_query_user("11111111111", {"default_tckn": "11111111111"})
    assert bfo.should_query_user("1234567801", {})
    assert not bfo.should_query_user("", {})
    msg = bfo.api_error_text(400, {"Message": "<b>Hata</b> SECRETX", "Result": "detay"}, "Op", ("SECRETX",))
    assert msg == "BirFatura isteği reddetti (Op): Hata *** — detay."
