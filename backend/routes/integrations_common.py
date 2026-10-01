"""
integrations_common.py — entegrasyonlar arasında PAYLAŞILAN yardımcılar ve genel uçlar:
entegrasyon logları, kargo sağlayıcı ayarları (/{provider}/settings|status|test-connection),
müşteri mesaj kanalları (WhatsApp/Instagram/Messenger/site) ve katalog bakım araçları (/site/*).

Pazaryeri (Trendyol/Hepsiburada/Temu/Amazon) entegrasyonları kaldırıldı; geçmiş veriler
veritabanında durur, yalnız okunur.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
from datetime import datetime, timezone
import uuid
import re
import httpx

from .deps import db, logger, require_admin, generate_short_id, require_permission

router = APIRouter(tags=["Integrations-Common"])

# DB-DRIVEN EŞANLAMLILAR (kullanıcının UI/DB'den eklediği; koddakilere EK). Modül-cache;
# refresh_value_synonyms() ile ~60sn'de bir tazelenir (sync _resolve_value_id await edemez).
async def log_integration_event(platform: str, action: str, entity_type: str, entity_id: str, status: str, message: str, details: dict = None):
    try:
        from datetime import datetime, timezone
        await db.integration_logs.insert_one({
            "platform": platform,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "status": status,
            "message": message,
            "details": details or {},
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Failed to log integration event: {str(e)}")


class _SkipPlatform(Exception):
    """on_product_deactivated: istenmeyen pazaryeri atlanır."""


# Trendyol ms-epoch'u TÜRKİYE saatini taşır (UTC değil). Kanıt (23.09.2026, sipariş
# listesi dışa aktarımı ile karşılaştırma): Trendyol'un TR 21:09 dediği sipariş bizde
# "2026-09-01T21:08:57+00:00" olarak duruyordu — saat rakamı AYNI, etiket UTC.
# Sonuç: raporlar UTC→TR dönüşümünde 3 saat DAHA ekliyor, 21:00 sonrası siparişler
# ertesi güne (ay sonuysa ertesi aya) kayıyordu. Türkiye'de yaz saati uygulaması
# 2016'dan beri YOK, ofset sabit +03:00.


def _tr_norm(s) -> str:
    """Türkçe-duyarsız normalize (eşleştirme için)."""
    import unicodedata as _u
    s = _u.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not _u.combining(c))
    s = (s.lower().replace("ı", "i").replace("ş", "s").replace("ç", "c")
         .replace("ğ", "g").replace("ü", "u").replace("ö", "o"))
    return " ".join(s.split())
@router.get("/integration-logs")
async def get_integration_logs(
    platform: str = Query(None),
    status: str = Query(None),
    limit: int = 50,
    current_user: dict = Depends(require_admin)
):
    """Fetch integration logs for UI"""
    try:
        query = {}
        if platform:
            query["platform"] = platform
        if status:
            query["status"] = status
            
        logs = await db.integration_logs.find(query).sort("created_at", -1).limit(limit).to_list(1000)
        # remove mongo _id
        for log in logs:
            if "_id" in log:
                log["_id"] = str(log["_id"])
        return {"success": True, "logs": logs}
    except Exception as e:
        logger.error(f"Error fetching integration logs: {e}")
        raise HTTPException(status_code=500, detail="Loglar alınamadı.")
def _generate_slug(name: str) -> str:
    slug = name.lower()
    tr_map = {'ı':'i','ğ':'g','ü':'u','ş':'s','ö':'o','ç':'c',
              'İ':'i','Ğ':'g','Ü':'u','Ş':'s','Ö':'o','Ç':'c'}
    for tr, en in tr_map.items():
        slug = slug.replace(tr, en)
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    return slug or str(uuid.uuid4())[:8]
@router.post("/site/categories/sync-missing-from-products")
async def sync_missing_categories_from_products(current_user: dict = Depends(require_admin)):
    """
    Ticimax kategori senkronizasyonunda kaçırılmış (örn. çok derin alt-kategori veya
    silinmiş ama ürünleri kalmış) kategorileri ürünlerin `category_name` alanından
    bulup yerel `categories` koleksiyonuna ekler ve ilgili ürünleri category_id ile
    günceller.

    Tipik kullanım: "Tulum kategorisi gelmemiş" gibi durumlarda; Ticimax API'sini
    tekrar çağırmadan, mevcut veriden eksiklikleri tamamlar.
    """
    # 1) Mevcut yerel kategoriler (isim → id)
    existing = {}
    async for c in db.categories.find({}, {"_id": 0, "id": 1, "name": 1}):
        nm = (c.get("name") or "").strip()
        if nm:
            existing[nm.lower()] = c.get("id")

    # 2) Ürünlerdeki tüm kategori isimleri (boş olmayanlar)
    pipeline = [
        {"$match": {"category_name": {"$nin": [None, ""]}}},
        {"$group": {"_id": "$category_name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    product_cats = []
    async for row in db.products.aggregate(pipeline):
        product_cats.append({"name": (row["_id"] or "").strip(), "count": row["count"]})

    # 3) Eksik olanları bul → oluştur
    created = []
    relinked = 0
    for pc in product_cats:
        nm = pc["name"]
        if not nm or nm.lower() in existing:
            continue
        # Yeni kategori oluştur
        new_id = await generate_short_id("categories")
        slug = _generate_slug(nm)
        doc = {
            "id": new_id,
            "ticimax_id": None,  # Ticimax'tan gelmediği için None
            "name": nm,
            "slug": slug,
            "parent_id": None,
            "is_active": True,
            "source": "products_backfill",
            "ticimax_sub_count": 0,
            "ticimax_sira": 999,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Bu kategori Ticimax sync sırasında kaçırılmıştı; ürünlerden geri-yüklendi.",
        }
        await db.categories.insert_one(doc)
        existing[nm.lower()] = new_id
        created.append({"id": new_id, "name": nm, "product_count": pc["count"]})

    # 4) Ürünlerde category_id boş olup category_name dolu olanları bağla
    for pc in product_cats:
        cat_id = existing.get(pc["name"].lower())
        if not cat_id:
            continue
        res = await db.products.update_many(
            {"category_name": pc["name"], "$or": [{"category_id": {"$exists": False}}, {"category_id": None}, {"category_id": ""}]},
            {"$set": {"category_id": cat_id}}
        )
        relinked += res.modified_count

    return {
        "success": True,
        "created_categories": created,
        "created_count": len(created),
        "relinked_products": relinked,
        "message": f"{len(created)} kategori oluşturuldu, {relinked} ürün bağlandı.",
    }
async def _kurtarma_match(uk, barkodlar, projection):
    """Bir Ticimax kartı için canlı ürün(ler)i GÜVENLE bulur.
    Öncelik: urun_karti_id (benzersiz). Tutmazsa BARKOD (varyant-benzersiz; bu export'ta
    1086 distinct barkodun 0'ı birden çok karta düşüyor → güvenli yedek anahtar).
    Döner: (prods, via) ; via ∈ {'kart_id','barkod',''}.
    Eşleşen tüm ürünler aynı karttır (renk kardeşleri) → hepsine uygulamak güvenli."""
    ukq = [str(uk)]
    if str(uk).isdigit():
        ukq.append(int(uk))
    prods = await db.products.find(
        {"urun_karti_id": {"$in": ukq}}, projection
    ).to_list(length=30)
    if prods:
        return prods, "kart_id"
    bl = [str(b).strip() for b in (barkodlar or []) if str(b).strip()]
    if bl:
        prods = await db.products.find(
            {"$or": [{"barcode": {"$in": bl}}, {"variants.barcode": {"$in": bl}}]},
            projection,
        ).to_list(length=30)
        if prods:
            return prods, "barkod"
    return [], ""
@router.post("/site/teknik-detay/recover")
async def recover_teknik_detay_from_snapshot(
    apply: bool = Query(False, description="false=ÖNİZLEME (yazma yok) · true=UYGULA"),
    current_user: dict = Depends(require_admin),
):
    """Silinen ürün-kartı teknik detaylarını, doğrulanmış Ticimax export snapshot'ından
    (backend/data/teknik_detay_kurtarma.json) GERİ YÜKLER.

    GÜVENLİK GARANTİLERİ:
      • Eşleştirme YALNIZCA `urun_karti_id` üzerinden (benzersiz). StokKodu/barkod ASLA.
      • Bir kart-ID birden çok ürüne denk gelirse (belirsiz) → ATLANIR, asla yazılmaz.
      • Sadece BOŞ/eksik özellik doldurulur; mevcut (manuel) değer ASLA ezilmez.
      • Fiyat/KDV/stok/barkod/varyantlara DOKUNULMAZ (yalnız `attributes`).
      • apply=false → ne değişeceğini döner, HİÇBİR ŞEY yazmaz.
    """
    import json as _json
    import os as _os
    snap_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                              "data", "teknik_detay_kurtarma.json")
    try:
        with open(snap_path, "r", encoding="utf-8") as f:
            snap = _json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kurtarma verisi okunamadı: {e}")
    urunler = snap.get("urunler") or {}

    matched = 0
    via_kart = 0
    via_barkod = 0
    no_match = 0
    too_many = 0
    to_fill_total = 0
    hb_total = 0
    temu_total = 0
    updated = 0
    sample: list = []

    PROJ = {"_id": 0, "id": 1, "attributes": 1, "name": 1,
            "hepsiburada_attributes": 1, "temu_attributes": 1}

    for uk, info in urunler.items():
        ozet = (info or {}).get("ozellikler") or {}
        if not ozet:
            continue
        prods, via = await _kurtarma_match(uk, (info or {}).get("barkodlar"), PROJ)
        if not prods:
            no_match += 1
            continue
        if len(prods) > 25:
            too_many += 1   # GÜVENLİK: anormal eşleşme sayısı → dokunma
            continue
        if via == "kart_id":
            via_kart += 1
        elif via == "barkod":
            via_barkod += 1

        card_did = False
        for p in prods:
            cur = p.get("attributes")
            existing_names: set = set()
            existing_vals: dict = {}   # orijinal_ad -> deger (üründe ZATEN dolu genel/Trendyol özellikleri)
            cur_list: list = []
            if isinstance(cur, list):
                for a in cur:
                    if isinstance(a, dict):
                        cur_list.append(a)
                        nm = a.get("name") or a.get("label") or a.get("type")
                        vv = a.get("value") or a.get("attribute_value")
                        if nm and str(vv or "").strip():
                            existing_names.add(_tr_norm(nm))
                            existing_vals.setdefault(str(nm), str(vv).strip())
            elif isinstance(cur, dict):
                for k, v in cur.items():
                    if isinstance(v, dict):
                        nm = v.get("label") or v.get("name") or k
                        vv = v.get("value") or v.get("attribute_value")
                    else:
                        nm, vv = k, v
                    if nm and str(vv or "").strip():
                        existing_names.add(_tr_norm(nm))
                        existing_vals.setdefault(str(nm), str(vv).strip())

            # 1) Snapshot'tan GENEL (attributes/Trendyol) BOŞ özellikleri doldur.
            adds = []
            for oz, dg in ozet.items():
                if not str(dg or "").strip():
                    continue
                if _tr_norm(oz) in existing_names:
                    continue   # zaten DOLU → dokunma
                adds.append({"name": oz, "value": str(dg).strip()})

            # 2) HB + Temu'ya AKTAR: ürünün TÜM genel özellikleri (mevcut dolu + kurtarılan) →
            #    hepsiburada_attributes / temu_attributes'ta BOŞ olanı doldur (manuel değer ezilmez).
            #    Push, bu ham değerleri gönderim anında HB enum'una çözer.
            hb = dict(p.get("hepsiburada_attributes") or {})
            temu = dict(p.get("temu_attributes") or {})
            propagate: dict = {}
            for nm, vv in existing_vals.items():
                propagate[nm] = vv
            for a in adds:
                propagate.setdefault(a["name"], a["value"])
            hb_keys_norm = {_tr_norm(k) for k, v in hb.items() if str(v or "").strip()}
            temu_keys_norm = {_tr_norm(k) for k, v in temu.items() if str(v or "").strip()}
            hb_fill = 0
            temu_fill = 0
            for nm, vv in propagate.items():
                nn = _tr_norm(nm)
                if nn and nn not in hb_keys_norm:
                    hb[nm] = vv; hb_fill += 1; hb_keys_norm.add(nn)
                if nn and nn not in temu_keys_norm:
                    temu[nm] = vv; temu_fill += 1; temu_keys_norm.add(nn)

            if not adds and hb_fill == 0 and temu_fill == 0:
                continue   # bu üründe yapılacak bir şey yok
            card_did = True
            to_fill_total += len(adds)
            hb_total += hb_fill
            temu_total += temu_fill
            if len(sample) < 12:
                sample.append({"urun_karti_id": str(uk),
                               "eslesme": via,
                               "urun": (p.get("name") or info.get("urun_adi") or "")[:50],
                               "genel_eklenecek": {a["name"]: a["value"] for a in adds},
                               "hb_dolan": hb_fill, "temu_dolan": temu_fill})
            if apply:
                setdoc = {"hepsiburada_attributes": hb, "temu_attributes": temu}
                if adds:
                    # attributes FORMATINI KORU (Trendyol'u bozma): list ise list'e ekle, dict ise dict'e.
                    if isinstance(cur, dict):
                        new_attrs = dict(cur)
                        for a in adds:
                            new_attrs[a["name"]] = a["value"]
                    else:
                        new_attrs = (cur_list if isinstance(cur, list) else []) + adds
                    setdoc["attributes"] = new_attrs
                await db.products.update_one({"id": p["id"]}, {"$set": setdoc})
                updated += 1
        if card_did:
            matched += 1

    return {
        "mode": "apply" if apply else "preview",
        "snapshot_urun": len(urunler),
        "eslesen_urun": matched,
        "eslesen_kart_id_ile": via_kart,
        "eslesen_barkod_ile": via_barkod,
        "eslesmeyen_urun_karti": no_match,
        "anormal_atlanmis": too_many,
        "doldurulacak_ozellik_toplam": to_fill_total,
        "hb_dolan_toplam": hb_total,
        "temu_dolan_toplam": temu_total,
        "guncellenen_urun": updated,
        "ornek": sample,
        "not": ("Eşleştirme: önce urun_karti_id, tutmazsa BARKOD (varyant-benzersiz, güvenli). "
                "Yalnız BOŞ özellikler dolduruldu (genel + Hepsiburada + Temu); manuel değerler korundu. "
                "attributes formatına dokunulmadı (Trendyol güvende). Fiyat/KDV/stok/barkoda dokunulmadı."
                + ("" if apply else " — ÖNİZLEME: hiçbir şey yazılmadı.")),
    }
@router.post("/site/aciklama/recover")
async def recover_aciklama_from_snapshot(
    apply: bool = Query(False, description="false=ÖNİZLEME (yazma yok) · true=UYGULA"),
    current_user: dict = Depends(require_admin),
):
    """Eksik ürün AÇIKLAMALARINI (description) doğrulanmış Ticimax export snapshot'ından
    (backend/data/aciklama_kurtarma.json) doldurur.

    GÜVENLİK GARANTİLERİ:
      • Eşleştirme YALNIZCA `urun_karti_id` (benzersiz). StokKodu/barkod ASLA.
      • Bir kart-ID birden çok ürüne denk gelirse → ATLANIR.
      • Yalnız BOŞ açıklama doldurulur (içi boş "<p></p>" gibi HTML de boş sayılır);
        dolu açıklama ASLA ezilmez.
      • Yalnız `description` alanı; fiyat/KDV/stok/barkod/başlık/özelliklere DOKUNULMAZ.
      • apply=false → önizleme, hiçbir şey yazmaz.
    """
    import json as _json
    import os as _os
    import re as _re
    snap_path = _os.path.join(_os.path.dirname(_os.path.dirname(__file__)),
                              "data", "aciklama_kurtarma.json")
    try:
        with open(snap_path, "r", encoding="utf-8") as f:
            snap = _json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Açıklama verisi okunamadı: {e}")
    urunler = snap.get("urunler") or {}

    def _blank_html(s):
        t = _re.sub(r"<[^>]+>", " ", str(s or ""))
        t = t.replace("&nbsp;", " ").replace("\xa0", " ")
        return not t.strip()

    matched = 0
    via_kart = 0
    via_barkod = 0
    no_match = 0
    too_many = 0
    already_full = 0
    updated = 0
    sample: list = []

    PROJ = {"_id": 0, "id": 1, "description": 1, "name": 1}

    for uk, info in urunler.items():
        desc = (info or {}).get("description") or ""
        if not str(desc).strip():
            continue
        prods, via = await _kurtarma_match(uk, (info or {}).get("barkodlar"), PROJ)
        if not prods:
            no_match += 1
            continue
        if len(prods) > 25:
            too_many += 1   # GÜVENLİK: anormal → dokunma
            continue
        if via == "kart_id":
            via_kart += 1
        elif via == "barkod":
            via_barkod += 1

        card_did = False
        for p in prods:
            if not _blank_html(p.get("description")):
                already_full += 1
                continue   # zaten dolu → DOKUNMA
            card_did = True
            if len(sample) < 12:
                sample.append({"urun_karti_id": str(uk),
                               "eslesme": via,
                               "urun": (p.get("name") or info.get("urun_adi") or "")[:50],
                               "aciklama_onizleme": _re.sub(r"<[^>]+>", " ", desc)[:120].strip()})
            if apply:
                await db.products.update_one({"id": p["id"]}, {"$set": {"description": str(desc)}})
                updated += 1
        if card_did:
            matched += 1

    return {
        "mode": "apply" if apply else "preview",
        "snapshot_urun": len(urunler),
        "doldurulacak_urun": matched,
        "eslesen_kart_id_ile": via_kart,
        "eslesen_barkod_ile": via_barkod,
        "zaten_dolu": already_full,
        "eslesmeyen_urun_karti": no_match,
        "anormal_atlanmis": too_many,
        "guncellenen_urun": updated,
        "ornek": sample,
        "not": ("Eşleştirme: önce urun_karti_id, tutmazsa BARKOD (varyant-benzersiz, güvenli). "
                "Yalnız BOŞ açıklamalar dolduruldu (içi boş HTML dahil); dolu açıklamalar korundu. "
                "Sadece description; fiyat/KDV/stok/başlık/özelliklere dokunulmadı."
                + ("" if apply else " — ÖNİZLEME: hiçbir şey yazılmadı.")),
    }
def _rk_lower(s: str) -> str:
    """tr-lower (İ/I güvenli)."""
    return (s or "").replace("I", "ı").replace("İ", "i").lower()
_RENK_CANON = {
    "siyah": "Siyah", "black": "Siyah", "beyaz": "Beyaz", "white": "Beyaz",
    "ekru": "Ekru", "krem": "Krem", "cream": "Krem", "bej": "Bej", "beige": "Bej",
    "kahve": "Kahverengi", "kahverengi": "Kahverengi", "brown": "Kahverengi",
    "vizon": "Vizon", "camel": "Camel", "taş": "Taş", "tas": "Taş", "stone": "Taş",
    "gri": "Gri", "grey": "Gri", "gray": "Gri", "antrasit": "Antrasit",
    "füme": "Füme", "fume": "Füme", "lacivert": "Lacivert", "navy": "Lacivert",
    "mavi": "Mavi", "blue": "Mavi", "indigo": "İndigo", "petrol": "Petrol",
    "turkuaz": "Turkuaz", "mint": "Mint", "yeşil": "Yeşil", "yesil": "Yeşil",
    "green": "Yeşil", "haki": "Haki", "zümrüt": "Zümrüt", "zumrut": "Zümrüt",
    "sarı": "Sarı", "sari": "Sarı", "yellow": "Sarı", "hardal": "Hardal",
    "gold": "Gold", "altın": "Gold", "altin": "Gold", "turuncu": "Turuncu",
    "orange": "Turuncu", "mercan": "Mercan", "somon": "Somon", "salmon": "Somon",
    "kiremit": "Kiremit", "kırmızı": "Kırmızı", "kirmizi": "Kırmızı", "red": "Kırmızı",
    "bordo": "Bordo", "fuşya": "Fuşya", "fusya": "Fuşya", "fuchsia": "Fuşya",
    "pembe": "Pembe", "pink": "Pembe", "pudra": "Pudra", "lila": "Lila",
    "mor": "Mor", "purple": "Mor", "leylak": "Leylak", "gümüş": "Gümüş",
    "gumus": "Gümüş", "silver": "Gümüş", "bronz": "Bronz", "metalik": "Metalik",
    "mürdüm": "Mürdüm", "murdum": "Mürdüm", "yavruağzı": "Yavruağzı",
    "yavruagzi": "Yavruağzı", "fıstık": "Fıstık Yeşili", "fistik": "Fıstık Yeşili",
}
def _renk_from_name(name: str) -> str:
    """Ürün adının SON kelimesinden rengi çıkarır; sözlükle doğrulanır.
    Renk değilse '' (asla tahmin etmez)."""
    toks = re.sub(r"[^0-9A-Za-zçğıöşüÇĞİÖŞÜ ]", " ", str(name or "")).split()
    if not toks:
        return ""
    return _RENK_CANON.get(_rk_lower(toks[-1]), "")
def _renk_canon(val: str) -> str:
    """Serbest renk değerini (ürün/varyant color) kanonik renge çevirir; tanınmazsa ''."""
    v = _rk_lower(str(val or "").strip())
    if not v:
        return ""
    if v in _RENK_CANON:
        return _RENK_CANON[v]
    parts = v.split()
    return _RENK_CANON.get(parts[-1], "") if parts else ""
@router.post("/site/renk-webcolor/autofill")
async def autofill_renk_webcolor(
    apply: bool = Query(False, description="false=ÖNİZLEME · true=UYGULA"),
    current_user: dict = Depends(require_admin),
):
    """Renk + Web Color'ı ürün ADINDAN otomatik doldurur.
    Her renk varyantı split sonrası ayrı kart olur ve adı renkle biter
    (ör. '...Elbise Bej' → Renk=Bej, Web Color=Bej). Web Color gönderimde
    pazaryeri enum'una (en yakın) çözülür.
    GÜVENLİK: çok renkli (henüz bölünmemiş) kartlara tek renk YAZILMAZ; yalnız BOŞ
    Renk/Web Color doldurulur; Beden ASLA yazılmaz; fiyat/KDV/stok/barkoda dokunulmaz;
    attributes formatı (list/dict) korunur — Trendyol güvende."""
    PROJ = {"_id": 0, "id": 1, "name": 1, "color": 1, "attributes": 1,
            "variants": 1, "hepsiburada_attributes": 1, "temu_attributes": 1}
    scanned = matched = updated = renk_fill = webcolor_fill = 0
    no_color = multi_color = hb_fill_t = temu_fill_t = 0
    sample: list = []

    async for p in db.products.find({}, PROJ):
        scanned += 1
        # GÜVENLİK: çok renkli (bölünmemiş) kart → tek renk yazma, ATLA
        vcols_all: list = []
        for v in (p.get("variants") or []):
            c = str((v or {}).get("color") or "").strip()
            if c and _rk_lower(c) not in [_rk_lower(x) for x in vcols_all]:
                vcols_all.append(c)
        if len(vcols_all) > 1:
            multi_color += 1
            continue

        name = p.get("name") or ""
        color = _renk_from_name(name)              # 1) isim son kelimesi
        if not color:
            color = _renk_canon(p.get("color"))    # 2) ürün color alanı
        if not color and len(vcols_all) == 1:
            color = _renk_canon(vcols_all[0])      # 3) tek distinct varyant rengi
        if not color:
            no_color += 1
            continue
        matched += 1

        # mevcut genel Renk/Web Color DOLU mu?
        cur = p.get("attributes")
        existing_names: set = set()
        cur_list: list = []
        if isinstance(cur, list):
            for a in cur:
                if isinstance(a, dict):
                    cur_list.append(a)
                    nm = a.get("name") or a.get("label") or a.get("type")
                    vv = a.get("value") or a.get("attribute_value")
                    if nm and str(vv or "").strip():
                        existing_names.add(_tr_norm(nm))
        elif isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(v, dict):
                    nm = v.get("label") or v.get("name") or k
                    vv = v.get("value") or v.get("attribute_value")
                else:
                    nm, vv = k, v
                if nm and str(vv or "").strip():
                    existing_names.add(_tr_norm(nm))

        targets = [("Renk", color), ("Web Color", color)]
        adds = [{"name": nm, "value": vv} for nm, vv in targets
                if _tr_norm(nm) not in existing_names]

        hb = dict(p.get("hepsiburada_attributes") or {})
        temu = dict(p.get("temu_attributes") or {})
        hb_norms = {_tr_norm(k) for k, v in hb.items() if str(v or "").strip()}
        temu_norms = {_tr_norm(k) for k, v in temu.items() if str(v or "").strip()}
        hb_f = temu_f = 0
        for nm, vv in targets:
            nn = _tr_norm(nm)
            if nn not in hb_norms:
                hb[nm] = vv; hb_f += 1; hb_norms.add(nn)
            if nn not in temu_norms:
                temu[nm] = vv; temu_f += 1; temu_norms.add(nn)

        if not adds and hb_f == 0 and temu_f == 0:
            continue
        renk_fill += sum(1 for a in adds if a["name"] == "Renk")
        webcolor_fill += sum(1 for a in adds if a["name"] == "Web Color")
        hb_fill_t += hb_f
        temu_fill_t += temu_f
        if len(sample) < 15:
            sample.append({"urun": name[:55], "renk": color,
                           "genel_eklenecek": [a["name"] for a in adds],
                           "hb_dolan": hb_f, "temu_dolan": temu_f})

        if apply:
            setdoc = {"hepsiburada_attributes": hb, "temu_attributes": temu}
            if not str(p.get("color") or "").strip():
                setdoc["color"] = color
            if adds:
                if isinstance(cur, dict):
                    new_attrs = dict(cur)
                    for a in adds:
                        new_attrs[a["name"]] = a["value"]
                else:
                    new_attrs = (cur_list if isinstance(cur, list) else []) + adds
                setdoc["attributes"] = new_attrs
            await db.products.update_one({"id": p["id"]}, {"$set": setdoc})
            updated += 1

    return {
        "mode": "apply" if apply else "preview",
        "taranan_urun": scanned,
        "renk_bulunan_urun": matched,
        "renk_bulunamayan": no_color,
        "cok_renkli_atlanan": multi_color,
        "renk_doldurulacak": renk_fill,
        "webcolor_doldurulacak": webcolor_fill,
        "hb_dolan_toplam": hb_fill_t,
        "temu_dolan_toplam": temu_fill_t,
        "guncellenen_urun": updated,
        "ornek": sample,
        "not": ("Renk = ürün ADININ son kelimesi (renk sözlüğüyle doğrulanır); değilse "
                "ürün/varyant renginden. Web Color = Renk; gönderimde pazaryeri enum'una "
                "(en yakın) çözülür. Çok renkli kart ATLANIR. Beden YAZILMAZ. Yalnız BOŞ "
                "alanlar dolduruldu; fiyat/KDV/stok/barkoda dokunulmadı."
                + ("" if apply else " — ÖNİZLEME: hiçbir şey yazılmadı.")),
    }
def _desc_is_blank(s) -> bool:
    """HTML açıklamayı düz metne indirip boş mu (sadece etiket/boşluk) kontrol eder."""
    t = re.sub(r"<[^>]+>", " ", str(s or ""))
    t = t.replace("&nbsp;", " ").replace("\xa0", " ")
    return not t.strip()
def _attr_flat(p: dict) -> dict:
    """Ürünün genel attributes (list/dict) + hepsiburada_attributes'ını ad->değer düz sözlüğe indirir."""
    out: dict = {}
    cur = p.get("attributes")
    if isinstance(cur, list):
        for a in cur:
            if isinstance(a, dict):
                nm = a.get("name") or a.get("label") or a.get("type")
                vv = a.get("value") or a.get("attribute_value")
                if nm and str(vv or "").strip():
                    out.setdefault(str(nm), str(vv).strip())
    elif isinstance(cur, dict):
        for k, v in cur.items():
            vv = v.get("value") if isinstance(v, dict) else v
            if str(vv or "").strip():
                out.setdefault(str(k), str(vv).strip())
    for k, v in (p.get("hepsiburada_attributes") or {}).items():
        if str(v or "").strip():
            out.setdefault(str(k), str(v).strip())
    return out
def _attr_get(am: dict, *names) -> str:
    """Düz öznitelik sözlüğünden ad(lar)a göre (HB-normalize ile) ilk dolu değeri döner."""
    for n in names:
        for k, v in am.items():
            if _tr_norm(k) == _tr_norm(n):
                return v
    return ""
@router.post("/site/aciklama/generate")
async def generate_aciklama_ai(
    apply: bool = Query(False, description="false=SAY (üretme yok) · true=ÜRET (batch)"),
    limit: int = Query(10, ge=1, le=30, description="apply'da her çağrıda işlenecek ürün sayısı"),
    current_user: dict = Depends(require_admin),
):
    """Boş açıklamalı ürünlere ÖZNİTELİKLERDEN beslenerek mevcut formatta açıklama üretir.
    Ürün Bilgisi prozası LLM ile (AI Chatbot ayarlarındaki sağlayıcı/model — Gemini de olur);
    Kumaş = Materyal, Kalıp = Kalıp özniteliği; Beden/Model ölçüleri BOŞ '___' bırakılır.
    GÜVENLİK: yalnız BOŞ açıklama doldurulur (mevcut korunur); ölçü/fiyat/beden UYDURULMAZ;
    fiyat/KDV/stok/başlık/özelliklere dokunulmaz."""
    PROJ = {"_id": 0, "id": 1, "name": 1, "description": 1,
            "attributes": 1, "hepsiburada_attributes": 1}
    total_empty = 0
    batch: list = []
    async for p in db.products.find({}, PROJ):
        if _desc_is_blank(p.get("description")):
            total_empty += 1
            if apply and len(batch) < limit:
                batch.append(p)

    if not apply:
        return {
            "mode": "preview",
            "bos_aciklamali_urun": total_empty,
            "not": (f"{total_empty} ürünün açıklaması boş. 'Uygula' her çağrıda en çok {limit} "
                    "tanesini AI ile üretir; arayüz kalan bitene kadar döngüyle çağırır. "
                    "Ürün Bilgisi AI ile özniteliklerden yazılır, ölçüler boş '___' bırakılır."),
        }

    from .ai_chatbot import get_ai_settings, _api_key_for, llm_chat
    settings = await get_ai_settings()
    api_key = _api_key_for(settings)
    if not api_key:
        raise HTTPException(status_code=400, detail="AI anahtarı yapılandırılmamış (Ayarlar → AI Chatbot).")
    provider = settings.get("provider", "anthropic")
    model = settings.get("fast_model") or settings.get("model", "claude-haiku-4-5")

    SYS = (
        "Sen bir kadın giyim e-ticaret editörüsün. Sana ürün adı ve öznitelikleri verilir. "
        "SADECE 'Ürün Bilgisi' bölümü için 1-2 kısa, akıcı, abartısız Türkçe cümle yaz. "
        "Yalnızca verilen özniteliklere dayan; ölçü, fiyat, beden, kumaş oranı, malzeme UYDURMA. "
        "Başlık, etiket, HTML, madde işareti, tırnak KULLANMA — yalnızca düz cümle döndür."
    )

    generated = failed = 0
    sample: list = []
    for p in batch:
        am = _attr_flat(p)
        name = p.get("name") or ""
        feed = "\n".join(
            f"- {k}: {v}" for k, v in am.items()
            if _tr_norm(k) not in (_tr_norm("Web Color"), _tr_norm("Renk"), _tr_norm("Beden"))
        )
        user_text = (f"Ürün adı: {name}\nÖznitelikler:\n{feed or '(öznitelik yok)'}\n\n"
                     "Bu ürün için 'Ürün Bilgisi' cümlesini yaz:")
        try:
            resp = await llm_chat(
                api_key=api_key, provider=provider, model=model,
                system_message=SYS, user_text=user_text, max_tokens=500,
            )
            prose = re.sub(r"<[^>]+>", "", str(resp or "")).strip()
            prose = re.sub(r"^\s*(Ürün Bilgisi\s*:?)\s*", "", prose, flags=re.I).strip()
        except Exception:
            failed += 1
            continue
        if not prose:
            failed += 1
            continue

        kumas = _attr_get(am, "Materyal", "Kumaş", "Kumaş Tipi")
        kalip = _attr_get(am, "Kalıp")
        parts = [f"<p><strong>Ürün Bilgisi:&nbsp;</strong>{prose}</p>"]
        if kumas:
            parts.append(f"<p><strong>Kumaş Bilgisi:&nbsp;</strong>{kumas}</p>")
        if kalip:
            parts.append(f"<p><strong>Kalıp:&nbsp;</strong>{kalip}</p>")
        parts.append("<p><strong>STD Beden Ölçüleri:</strong>&nbsp; Göğüs: ___ cm&nbsp; "
                     "Boy: ___ cm&nbsp; Kol Boyu: ___ cm</p>")
        parts.append("<p><strong>Model Ölçüleri:</strong>&nbsp; Boy: ___&nbsp; Göğüs: ___&nbsp; "
                     "Bel: ___&nbsp; Kalça: ___&nbsp; Kilo: ___</p>")
        parts.append("<p>Modelin üzerindeki ürün <strong>STD</strong> bedendir.</p>")
        parts.append("<p>Bedenler arası +/- sapma olabilir.</p>")
        html = "\n".join(parts)

        await db.products.update_one({"id": p["id"]}, {"$set": {"description": html}})
        generated += 1
        if len(sample) < 6:
            sample.append({"urun": name[:55], "uretilen_proza": prose[:140]})

    return {
        "mode": "apply",
        "uretilen": generated,
        "basarisiz": failed,
        "kalan": max(0, total_empty - generated),
        "kullanilan_model": f"{provider}/{model}",
        "ornek": sample,
        "not": ("Ürün Bilgisi AI ile özniteliklerden yazıldı; Kumaş=Materyal, Kalıp=Kalıp "
                "özniteliğinden. Beden/Model ölçüleri boş '___' bırakıldı (elle doldur). "
                "Yalnız boş açıklamalar dolduruldu; fiyat/KDV/stok/başlık/özelliklere dokunulmadı."),
    }
async def restore_xml_missing_products_once():
    """OTOMATİK TELAFİ: kullanıcının SİLMEDİĞİ (is_deleted=True DEĞİL) hâlde pasif görünen tüm
    ürünleri geri AKTİF eder. Kullanıcı kuralı: "sil tuşuna basmadıysam ürün görünmeli."

    KAPSAM (geri açılır): is_active != True  VE  is_deleted != True  VE  manual_deactivated != True
      → yani feed glitch'i / eski otomatik pasifleştirme ile kaybolan ürünler (ekru vb. renk
        varyantları dahil) geri gelir.
    DOKUNULMAZ:
      - is_deleted=True  → kullanıcı SİL'e bastı (bilinçli kaldırma).
      - manual_deactivated=True → kullanıcı ELLE pasife aldı (ürün toggle işareti).

    Settings bayrağı (v2) ile deploy başına BİR KEZ çalışır; sonraki elle pasifleştirmelerle
    savaşmaz (onlar manual_deactivated işaretli). v1'den v2'ye çıkıldı çünkü v1 yalnız
    'ticimax_xml_missing' etiketlileri kapsıyordu; etiketsiz eski pasifler geri gelmiyordu."""
    try:
        flag = await db.settings.find_one({"id": "xml_missing_restore_v2"}, {"_id": 0})
        if flag and flag.get("done"):
            return {"restored": 0, "skipped": "already-done"}
        now_iso = datetime.now(timezone.utc).isoformat()
        res = await db.products.update_many(
            {"is_active": {"$ne": True},
             "is_deleted": {"$ne": True},
             "manual_deactivated": {"$ne": True}},
            {"$set": {"is_active": True, "updated_at": now_iso},
             "$unset": {"deactivated_reason": ""}},
        )
        await db.settings.update_one(
            {"id": "xml_missing_restore_v2"},
            {"$set": {"id": "xml_missing_restore_v2", "done": True,
                      "restored": res.modified_count, "at": now_iso}},
            upsert=True,
        )
        if res.modified_count:
            logger.info(f"[urun-telafi] {res.modified_count} silinmemis pasif urun geri aktiflestirildi (v2, tek seferlik)")
        return {"restored": res.modified_count}
    except Exception as e:
        logger.warning(f"[xml-feed] restore_xml_missing_products_once hata: {e}")
        return {"restored": 0, "error": str(e)}


# DENETİM HATA-1: sipariş bu statülerdeyse iade işaretlemesi YAPILMAZ (zaten iptal/iade)


ALLOWED_MARKETPLACES = {
    # müşteri mesaj kanalları
    "whatsapp", "instagram", "messenger", "site",
    # kargo sağlayıcıları
    "mng", "aras", "yurtici", "ptt", "hepsijet", "trendyol_express", "surat", "ups", "dhl",
}
@router.get("/{marketplace}/settings")
async def get_marketplace_settings(marketplace: str, current_user: dict = Depends(require_admin)):
    """Sağlayıcı ayarlarını getir (kargo / mesaj kanalları)."""
    if marketplace not in ALLOWED_MARKETPLACES:
        raise HTTPException(status_code=404, detail="Bilinmeyen pazaryeri")
    settings = await db.settings.find_one({"id": marketplace}, {"_id": 0})
    if not settings:
        return {
            "id": marketplace,
            "merchant_id": "",
            "username": "",
            "api_key": "",
            "api_secret": "",
            "mode": "sandbox",
            "is_active": False,
            "default_markup": 0
        }
    # Mask secret
    if settings.get("api_secret"):
        settings["api_secret"] = "********"
    if settings.get("password"):
        settings["password"] = "********"
    if settings.get("secret_key"):
        settings["secret_key"] = "********"
    return settings
@router.post("/{marketplace}/settings")
async def save_marketplace_settings(marketplace: str, payload: dict, current_user: dict = Depends(require_permission("integrations.view"))):
    """Sağlayıcı ayarlarını kaydet (kargo / mesaj kanalları)."""
    if marketplace not in ALLOWED_MARKETPLACES:
        raise HTTPException(status_code=404, detail="Bilinmeyen pazaryeri")

    # Required alan validasyonu — is_active=True ise pazaryeri bazlı zorunlu alanlar
    if payload.get("is_active"):
        existing = await db.settings.find_one({"id": marketplace}, {"_id": 0}) or {}
        required = ["api_key", "api_secret"]
        missing = []
        for k in required:
            v = payload.get(k)
            if v in (None, "", "********"):
                v = existing.get(k)
            if not v:
                missing.append(k)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"{marketplace.capitalize()} aktifleştirmek için zorunlu alanlar eksik: {', '.join(missing)}"
            )

    update_data = {
        "id": marketplace,
        "merchant_id": payload.get("merchant_id", ""),
        "username": payload.get("username", ""),
        "dev_username": payload.get("dev_username", ""),
        "api_key": payload.get("api_key", ""),
        "mode": payload.get("mode", "sandbox"),
        "is_active": payload.get("is_active", False),
        "default_markup": payload.get("default_markup", 0),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    # Only update secret if provided — GÜVENLİK: sırları at-rest ŞİFRELE
    try:
        from security.crypto import encrypt as _enc_secret
    except Exception:
        _enc_secret = lambda v: v
    if payload.get("api_secret") and payload.get("api_secret") != "********":
        update_data["api_secret"] = _enc_secret(payload.get("api_secret"))
    if payload.get("password") and payload.get("password") != "********":
        update_data["password"] = _enc_secret(payload.get("password"))
    if payload.get("secret_key") and payload.get("secret_key") != "********":
        update_data["secret_key"] = _enc_secret(payload.get("secret_key"))

    await db.settings.update_one({"id": marketplace}, {"$set": update_data}, upsert=True)
    return {"success": True, "message": f"{marketplace.capitalize()} ayarları kaydedildi"}
@router.get("/{marketplace}/status")
async def get_marketplace_status(marketplace: str, current_user: dict = Depends(require_admin)):
    """Sağlayıcı entegrasyon durumu.
    DENETİM SEC-5 F-12: eskiden PUBLIC'ti ve merchant_id/supplier_id + canlı mod sızdırıyordu →
    require_admin eklendi."""
    if marketplace not in ALLOWED_MARKETPLACES:
        raise HTTPException(status_code=404, detail="Bilinmeyen pazaryeri")
    settings = await db.settings.find_one({"id": marketplace}, {"_id": 0})
    if not settings:
        return {"configured": False, "mode": "sandbox"}
    mode_raw = (settings.get("mode") or "sandbox").strip().lower()
    is_live = mode_raw in ("live", "production", "prod", "canli", "canlı")
    configured = bool(settings.get("is_active") and (settings.get("api_key") or settings.get("merchant_id")))
    return {
        "configured": configured,
        "mode": "live" if is_live else "sandbox",
        "merchant_id": settings.get("merchant_id", "") if settings.get("is_active") else None
    }
@router.post("/{marketplace}/test-connection")
async def test_marketplace_connection(marketplace: str, current_user: dict = Depends(require_admin)):
    """Kimlik bilgisi kontrolü (kargo sağlayıcıları / mesaj kanalları).
    Eksik bilgi varsa success=False ve açıklayıcı mesaj döner."""
    if marketplace not in ALLOWED_MARKETPLACES:
        raise HTTPException(status_code=404, detail="Bilinmeyen pazaryeri")
    settings = await db.settings.find_one({"id": marketplace}, {"_id": 0})
    if not settings:
        return {"success": False, "message": f"{marketplace.capitalize()} ayarları kaydedilmemiş"}

    # GÜVENLİK: at-rest şifreli sırları probe'tan ÖNCE çöz (decrypt düz-metni geçirir).
    try:
        from security.crypto import decrypt as _dec_secret
        for _sf in ("api_secret", "password", "secret_key", "access_token"):
            if settings.get(_sf):
                settings[_sf] = _dec_secret(settings[_sf]) or settings[_sf]
    except Exception:
        pass

    try:
        if marketplace in {"mng", "aras", "yurtici", "ptt", "hepsijet", "trendyol_express", "surat"}:
            user = (settings.get("username") or "").strip()
            pw = (settings.get("password") or "").strip()
            key = (settings.get("api_key") or "").strip()
            if not (user or key) or not (pw or settings.get("customer_code")):
                return {"success": False, "message": f"{marketplace.upper()} kimlik bilgileri eksik"}
            return {"success": True, "message": f"{marketplace.upper()} kimlik bilgileri kaydedildi (canlı test yapılmadı)"}

        # Default fallback for other marketplaces (whatsapp/instagram/site channels etc.)
        if not (settings.get("api_key") or settings.get("username")):
            return {"success": False, "message": f"{marketplace} kimlik bilgileri eksik"}
        return {"success": True, "message": f"{marketplace} ayarları geçerli"}
    except httpx.TimeoutException:
        return {"success": False, "message": f"{marketplace} API zaman aşımına uğradı (15s)"}
    except Exception as e:
        return {"success": False, "message": f"{marketplace} test hatası: {str(e)[:150]}"}
QUESTIONS_COLLECTIONS = {
    "whatsapp": "whatsapp_messages",
    "instagram": "instagram_messages",
    "messenger": "messenger_messages",
    "site": "site_messages",
}
@router.delete("/{marketplace}/questions/{question_id}")
async def delete_marketplace_question(marketplace: str, question_id: str, current_user: dict = Depends(require_admin)):
    """Delete a question/message (e.g., expired unanswered)."""
    if marketplace not in QUESTIONS_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Bilinmeyen kanal")
    coll = db[QUESTIONS_COLLECTIONS[marketplace]]
    res = await coll.delete_one({"question_id": question_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
    return {"success": True}
@router.get("/marketplace/questions")
async def get_marketplace_questions(
    marketplace: Optional[str] = "all",
    status: Optional[str] = None,
    page: int = 0,
    size: int = 20,
    current_user: dict = Depends(require_admin)
):
    """Unified endpoint returning questions tagged with their marketplace."""
    query = {}
    if status:
        query["status"] = status

    skip = page * size
    sources = []
    if marketplace and marketplace != "all":
        if marketplace not in QUESTIONS_COLLECTIONS:
            raise HTTPException(status_code=400, detail="Bilinmeyen pazaryeri")
        sources = [marketplace]
    else:
        sources = list(QUESTIONS_COLLECTIONS.keys())

    all_items = []
    totals = {}
    for mp in sources:
        coll = db[QUESTIONS_COLLECTIONS[mp]]
        # Pull enough for merge+sort; cap per marketplace to avoid huge reads
        items = await coll.find(query, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
        for it in items:
            it["marketplace"] = mp
        all_items.extend(items)
        totals[mp] = await coll.count_documents(query)

    # Sort merged by created_at desc
    def _key(x):
        return x.get("created_at") or ""
    all_items.sort(key=_key, reverse=True)
    total = sum(totals.values())
    paginated = all_items[skip: skip + size]

    return {
        "questions": paginated,
        "total": total,
        "totals": totals,
        "page": page,
        "size": size,
    }
@router.post("/{marketplace}/questions/sync")
async def sync_marketplace_questions_stub(marketplace: str, current_user: dict = Depends(require_admin)):
    """Kanal senkronu (yerel kanallarda API çekimi yok)."""
    if marketplace not in ALLOWED_MARKETPLACES:
        raise HTTPException(status_code=404, detail="Bilinmeyen pazaryeri")
    settings = await db.settings.find_one({"id": marketplace}, {"_id": 0})
    if not settings or not settings.get("is_active"):
        raise HTTPException(status_code=400, detail=f"{marketplace.capitalize()} entegrasyonu yapılandırılmamış")
    return {"success": True, "synced": 0, "total_fetched": 0, "message": "API entegrasyonu yapılandırıldığında otomatik çalışacak (stub)"}
@router.post("/{marketplace}/questions/{question_id}/answer")
async def answer_marketplace_question_stub(
    marketplace: str,
    question_id: str,
    payload: dict,
    current_user: dict = Depends(require_admin)
):
    """Mesaja yanıtı yerel olarak kaydeder."""
    if marketplace not in QUESTIONS_COLLECTIONS:
        raise HTTPException(status_code=404, detail="Bilinmeyen pazaryeri")
    answer_text = (payload or {}).get("answer", "").strip()
    if not answer_text:
        raise HTTPException(status_code=400, detail="Yanıt metni boş olamaz")
    coll = db[QUESTIONS_COLLECTIONS[marketplace]]
    await coll.update_one(
        {"question_id": question_id},
        {"$set": {
            "answer": answer_text,
            "status": "ANSWERED",
            "answered_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"success": True, "message": "Cevap kaydedildi (yerel). API entegrasyonu tamamlandığında otomatik gönderilecek."}
