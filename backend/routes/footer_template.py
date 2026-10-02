"""
=============================================================================
footer_template.py — Admin'in özelleştirebileceği HTML footer şablonu
=============================================================================
Footer tasarımını admin'in değiştirebilmesi için settings collection'ında
`id=footer` döküman tutulur. İki mod desteklenir:

  • HTML mode (basit):   custom_html alanına yazılan HTML render edilir.
  • Structured mode:     columns array'i ile sütun + link listesi yönetilir.

ENDPOINTS:
  GET  /api/footer-template            — Public (frontend Footer.jsx render için)
  PUT  /api/admin/footer-template      — Admin (HTML / columns güncelleme)
=============================================================================
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, timezone

from .deps import db, require_admin

public_router = APIRouter(prefix="/footer-template", tags=["footer-public"])
admin_router = APIRouter(prefix="/admin/footer-template", tags=["footer-admin"])


_DEFAULT = {
    "id": "footer",
    "mode": "structured",  # "html" | "structured"
    "custom_html": "",
    "columns": [
        {
            "title": "Alışveriş",
            "links": [
                {"to": "/en-yeniler", "label": "Yeni Ürünler"},
                {"to": "/sale", "label": "İndirimli Ürünler"},
                {"to": "/tum-urunler?sort=popular&order=desc", "label": "Çok Satanlar"},
                {"to": "/tum-urunler", "label": "Tüm Ürünler"},
                {"to": "/karsilastir", "label": "Ürün Karşılaştır"},
            ],
        },
        {
            "title": "Yardım",
            "links": [
                {"to": "/siparis-takip", "label": "Sipariş Takibi"},
                {"to": "/sayfa/uyelik-islemleri", "label": "Üyelik İşlemleri"},
                {"to": "/iade-islemleri", "label": "İade Talebi"},
                {"to": "/sayfa/iade-kosullari", "label": "İade İşlemleri"},
                {"to": "/sikca-sorulan-sorular", "label": "Sıkça Sorulan Sorular"},
                {"to": "/sayfa/iletisim", "label": "İletişim"},
            ],
        },
        {
            "title": "Kurumsal",
            "links": [
                {"to": "/sayfa/hakkimizda", "label": "Hakkımızda"},
                {"to": "/sayfa/mesafeli-satis", "label": "Mesafeli Satış Sözleşmesi"},
                {"to": "/sayfa/uyelik-sozlesmesi", "label": "Üyelik Sözleşmesi"},
                {"to": "/sayfa/kvkk", "label": "KVKK Aydınlatma Metni"},
                {"to": "/sayfa/gizlilik", "label": "Gizlilik Politikası"},
            ],
        },
        {
            "title": "İletişim",
            "static": [
                "{store_email}",
                "{store_phone}",
                "Pazartesi-Cumartesi 09:00 - 18:00",
            ],
        },
    ],
    "newsletter": {
        "title": "E-Bültene Kaydolun",
        "description": "Yeni ürünler, kampanyalar ve atölye fırsatlarından ilk siz haberdar olun.",
        "placeholder": "E-posta adresiniz",
    },
    "social": {
        "instagram": "{store_instagram}",
        "facebook": "",
        "twitter": "",
    },
    "copyright": "© {year} {store_name}. Tüm hakları saklıdır.",
    "slogan": "",
}


async def _default_footer() -> dict:
    """Varsayılan footer — firma değerleri (e-posta/telefon/Instagram/ad) Firma Bilgileri'nden
    doldurulur; koda gömülü firma verisi YOK. Boş kalan iletişim satırları atlanır."""
    import copy as _copy
    try:
        from company import get_company
        co = await get_company(db)
    except Exception:
        co = {}
    vals = {
        "{store_email}": co.get("contact_email") or "",
        "{store_phone}": co.get("contact_phone") or "",
        "{store_instagram}": co.get("instagram") or "",
        "{store_name}": co.get("store_name") or "Mağaza",
        "{year}": str(datetime.now(timezone.utc).year),
    }

    def _f(v):
        if isinstance(v, str):
            for k, r in vals.items():
                v = v.replace(k, r)
            return v
        if isinstance(v, list):
            return [x for x in (_f(i) for i in v) if x != ""]
        if isinstance(v, dict):
            return {k: _f(i) for k, i in v.items()}
        return v
    return _f(_copy.deepcopy(_DEFAULT))


@public_router.get("")
async def get_footer_template():
    """Frontend Footer.jsx için public endpoint."""
    doc = await db.settings.find_one({"id": "footer"}, {"_id": 0})
    return doc or await _default_footer()


@admin_router.get("")
async def admin_get_footer_template(current_user: dict = Depends(require_admin)):
    """Admin (yönetim için)."""
    doc = await db.settings.find_one({"id": "footer"}, {"_id": 0})
    return doc or await _default_footer()


@admin_router.put("")
async def admin_update_footer_template(
    payload: dict,
    current_user: dict = Depends(require_admin)
):
    """Footer şablonunu güncelle (whitelist)."""
    allowed = {"mode", "custom_html", "columns", "newsletter", "social", "copyright", "slogan"}
    update = {k: v for k, v in (payload or {}).items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one(
        {"id": "footer"},
        {"$set": update, "$setOnInsert": {"id": "footer"}},
        upsert=True,
    )
    return {"success": True, "message": "Footer şablonu güncellendi"}


@admin_router.post("/reset-default")
async def reset_footer_default(current_user: dict = Depends(require_admin)):
    """Footer'ı varsayılan değerlere döndür."""
    await db.settings.update_one(
        {"id": "footer"},
        {"$set": {**(await _default_footer()), "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True,
    )
    return {"success": True, "message": "Footer varsayılana sıfırlandı"}
