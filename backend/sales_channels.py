"""
sales_channels.py — Satış kanalı tanımı (tek kaynak).

Bu mağazanın tek satış kanalı web sitesidir. Siparişlerde `platform` / `marketplace`
alanları boş, "web" veya "site" ise sipariş SİTE siparişidir. Geçmişte başka bir kanaldan
içe aktarılmış (alanı başka bir değer taşıyan) kayıtlar silinmez; raporlarda ve listelerde
adı verilmeden "Diğer kanal" olarak gösterilir ve site cirosuna katılmaz.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

SITE = "site"
OTHER = "other"
SITE_LABEL = "Web Sitesi"
OTHER_LABEL = "Diğer kanal"

# Site siparişini ifade eden ham değerler (küçük harf). None/eksik alan da site sayılır.
SITE_VALUES = ("", "web", "site", "website", "online", "manual", "admin")


def _norm(v: Any) -> str:
    return str(v or "").strip().lower()


def is_site_value(v: Any) -> bool:
    return _norm(v) in SITE_VALUES


def channel_of(order: Optional[Dict[str, Any]]) -> str:
    """'site' | 'other' — sipariş belgesinden kanal."""
    o = order or {}
    if is_site_value(o.get("platform")) and is_site_value(o.get("marketplace")):
        return SITE
    return OTHER


def channel_label(value: Any) -> str:
    return SITE_LABEL if (value in (SITE, None) or is_site_value(value)) else OTHER_LABEL


def site_match() -> Dict[str, Any]:
    """Mongo süzgeci: yalnız site siparişleri (platform ve marketplace site değeri ya da yok)."""
    vals = list(SITE_VALUES) + [None]
    return {"$and": [
        {"$or": [{"platform": {"$exists": False}}, {"platform": {"$in": vals}}]},
        {"$or": [{"marketplace": {"$exists": False}}, {"marketplace": {"$in": vals}}]},
    ]}


def other_match() -> Dict[str, Any]:
    """Mongo süzgeci: site dışı (geçmişten kalan) kanal kayıtları."""
    vals = list(SITE_VALUES) + [None]
    return {"$or": [
        {"$and": [{"platform": {"$exists": True}}, {"platform": {"$nin": vals}}]},
        {"$and": [{"marketplace": {"$exists": True}}, {"marketplace": {"$nin": vals}}]},
    ]}


def channel_expr() -> Dict[str, Any]:
    """Aggregation ifadesi: 'site' | 'other'."""
    vals = list(SITE_VALUES)
    p = {"$toLower": {"$ifNull": ["$platform", ""]}}
    m = {"$toLower": {"$ifNull": ["$marketplace", ""]}}
    return {"$cond": [{"$and": [{"$in": [p, vals]}, {"$in": [m, vals]}]}, SITE, OTHER]}


def source_filter(source: Optional[str]) -> Optional[Dict[str, Any]]:
    """Rapor kaynak parametresi: None/'all' → filtre yok; 'site' → site; diğer her değer →
    site dışı kanal kayıtları."""
    s = _norm(source)
    if s in ("", "all", "tum", "tümü", "hepsi"):
        return None
    if s in (SITE, "web"):
        return site_match()
    return other_match()
