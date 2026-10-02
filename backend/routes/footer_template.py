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
        # Vitrin footer'ı (kategori menüsü varken) ilk İKİ sütunu gösterir → hukuki sayfalar önde.
        {
            "title": "Müşteri Hizmetleri",
            "links": [
                {"to": "/siparis-takip", "label": "Sipariş Takibi"},
                {"to": "/iade-islemleri", "label": "İade Talebi"},
                {"to": "/sayfa/iade-kosullari", "label": "İade ve Değişim Koşulları"},
                {"to": "/sayfa/kargo-ve-teslimat", "label": "Teslimat ve Kargo"},
                {"to": "/sayfa/garanti-kosullari", "label": "Garanti ve Teknik Servis"},
                {"to": "/sikca-sorulan-sorular", "label": "Sıkça Sorulan Sorular"},
                {"to": "/sayfa/iletisim", "label": "İletişim"},
            ],
        },
        {
            "title": "Kurumsal",
            "links": [
                {"to": "/sayfa/hakkimizda", "label": "Hakkımızda"},
                {"to": "/sayfa/mesafeli-satis", "label": "Mesafeli Satış Sözleşmesi"},
                {"to": "/sayfa/on-bilgilendirme", "label": "Ön Bilgilendirme Formu"},
                {"to": "/sayfa/uyelik-sozlesmesi", "label": "Üyelik Sözleşmesi"},
                {"to": "/sayfa/kullanim-kosullari", "label": "Kullanım Koşulları"},
                {"to": "/sayfa/kvkk", "label": "KVKK Aydınlatma Metni"},
                {"to": "/sayfa/gizlilik", "label": "Gizlilik Politikası"},
                {"to": "/sayfa/cerez-politikasi", "label": "Çerez Politikası"},
                {"to": "/sayfa/acik-riza-metni", "label": "Açık Rıza Metni"},
            ],
        },
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
    allowed = {"mode", "custom_html", "columns", "newsletter", "social", "copyright", "slogan", "payment_band_url"}
    update = {k: v for k, v in (payload or {}).items() if k in allowed}
    if "payment_band_url" in update:
        u = str(update["payment_band_url"] or "").strip()[:500]
        # yalnız http(s) veya site-içi yol (javascript:/data: vb. reddedilir)
        update["payment_band_url"] = u if (u.startswith("/") or u.lower().startswith(("https://", "http://"))) else ""
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
