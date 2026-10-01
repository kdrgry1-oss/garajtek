"""Gelen webhook uçları için ortak router.

Trendyol sipariş webhook'u pazaryeri entegrasyonlarıyla birlikte kaldırıldı; router
geriye dönük uyumluluk (routes/__init__.py → server.py) için boş olarak durur.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Webhooks"])
