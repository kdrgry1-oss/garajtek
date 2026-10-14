"""Ürün paketi (bundle) kampanyası — panel okuma/yazma eşlemesi paket fiyatını korumalı.

Hata: GET /campaigns bundle_price döndürmüyordu → liste "Paket: 0 TL", düzenleme formu 0 ve
aktif/pasif geçişi ({...c} PUT) paket fiyatını None'a ezip indirimi sıfırlıyordu."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

SRC = Path(__file__).parents[1] / "routes" / "coupons.py"
NAMES = {"_coupon_to_campaign", "_campaign_to_coupon_fields", "_check_bundle_price", "update_campaign"}


class FakeCoupons:
    def __init__(self, docs):
        self.docs = {d["id"]: dict(d) for d in docs}

    async def find_one(self, q, proj=None):
        d = self.docs.get(q.get("id"))
        return dict(d) if d else None

    async def update_one(self, q, upd):
        d = self.docs.get(q.get("id"))
        if d is not None:
            d.update(upd["$set"])
        return SimpleNamespace(matched_count=1 if d is not None else 0)


def load(docs):
    tree = ast.parse(SRC.read_text())
    nodes = []
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in NAMES:
            n.decorator_list = []
            nodes.append(n)
    assert len(nodes) == len(NAMES)
    coupons = FakeCoupons(docs)

    async def _no_excluded(payload):
        return None
    scope = {"db": SimpleNamespace(coupons=coupons), "HTTPException": HTTPException,
             "Depends": lambda *a, **k: None, "require_admin": None,
             "_window_from_payload": lambda *a, **k: None, "_utcnow": lambda: "now",
             "_excluded_fields_from_payload": _no_excluded}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(SRC), "exec"), scope)
    return scope, coupons


BUNDLE = {"id": "b1", "code": "AUTO-B1", "title": "Paket", "type": "bundle", "bundle_price": 2000.0,
          "auto_apply": True, "is_active": True, "products": ["A", "B"]}


def test_list_returns_bundle_price_and_toggle_keeps_it():
    s, coupons = load([BUNDLE])
    c = s["_coupon_to_campaign"](coupons.docs["b1"])
    assert c["type"] == "bundle" and c["bundle_price"] == 2000.0
    # Panel handleToggle: {...c, is_active: !c.is_active} → iki kez PUT
    asyncio.run(s["update_campaign"]("b1", {**c, "is_active": False}))
    c2 = s["_coupon_to_campaign"](coupons.docs["b1"])
    asyncio.run(s["update_campaign"]("b1", {**c2, "is_active": True}))
    assert coupons.docs["b1"]["bundle_price"] == 2000.0 and coupons.docs["b1"]["is_active"] is True


def test_partial_payload_without_bundle_price_does_not_erase():
    s, coupons = load([BUNDLE])
    c = s["_coupon_to_campaign"](coupons.docs["b1"])
    c.pop("bundle_price")
    asyncio.run(s["update_campaign"]("b1", {**c, "is_active": False}))
    assert coupons.docs["b1"]["bundle_price"] == 2000.0


def test_bundle_without_price_rejected():
    s, coupons = load([BUNDLE])
    c = s["_coupon_to_campaign"](coupons.docs["b1"])
    with pytest.raises(HTTPException) as e:
        asyncio.run(s["update_campaign"]("b1", {**c, "bundle_price": 0}))
    assert e.value.status_code == 400
    assert coupons.docs["b1"]["bundle_price"] == 2000.0
    with pytest.raises(HTTPException):
        s["_check_bundle_price"](s["_campaign_to_coupon_fields"]({"type": "bundle", "name": "x"}))
    s["_check_bundle_price"](s["_campaign_to_coupon_fields"]({"type": "percentage", "value": 10}))
