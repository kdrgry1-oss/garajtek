"""
Category routes - CRUD
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import Optional
from datetime import datetime, timezone
import re
from utils.category_visibility import hide_test_placeholders

from .deps import db, logger, require_admin, generate_id, generate_short_id, require_permission

router = APIRouter(prefix="/categories", tags=["Categories"])


def _req_is_member(request) -> bool:
    """İstek geçerli bir kullanıcı JWT'si taşıyor mu (üye)? Misafir = token yok/geçersiz."""
    try:
        _auth = (request.headers.get("authorization") or "") if request else ""
        if _auth.lower().startswith("bearer "):
            from .deps import _decode_jwt_strict
            if (_decode_jwt_strict(_auth.split(" ", 1)[1]) or {}).get("user_id"):
                return True
    except Exception:
        pass
    return False

def generate_slug(name: str) -> str:
    # DENETİM (kategori slug): "İ".lower() → "i" + U+0307 (birleşik nokta) ürettiğinden naif
    # slug "GİYİM" → "gi-yi-m" gibi BOZUK çıkıyordu. Türkçe harfleri ÖNCE ASCII'ye çevir, sonra
    # kalan birleşik işaretleri (Mn) temizle → frontend lib/slug.js ile birebir aynı.
    import unicodedata
    tr_map = {'ı': 'i', 'İ': 'i', 'I': 'i', 'ş': 's', 'Ş': 's', 'ç': 'c', 'Ç': 'c',
              'ğ': 'g', 'Ğ': 'g', 'ö': 'o', 'Ö': 'o', 'ü': 'u', 'Ü': 'u'}
    s = "".join(tr_map.get(ch, ch) for ch in str(name or ""))
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")  # birleşik işaretleri at
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'[\s_]+', '-', s)
    s = re.sub(r'-+', '-', s).strip('-')
    return s

async def repair_category_slugs():
    """BOZUK kategori slug'larını (eski İ→i̇ bug'ından 'gi-yi-m', 'en-yeni-ler' gibi) TEK
    SEFERDE onarır: doğru slug'ı kanonik yapar, eskisini slug_aliases + 301 redirect ile korur
    → mevcut URL'ler kırılmaz, SEO düzelir. settings.category_slug_repair_v1 ile idempotent."""
    try:
        flag = await db.settings.find_one({"id": "category_slug_repair_v1"}, {"_id": 0})
        if flag and flag.get("done"):
            return
        cats = await db.categories.find({}, {"_id": 0}).to_list(length=None)
        used = {str(c.get("slug") or "").lower() for c in cats if c.get("slug")}
        fixed = 0
        for c in cats:
            old = str(c.get("slug") or "")
            correct = generate_slug(c.get("name") or "")
            if not correct or correct == old.lower():
                continue
            if correct in used and correct != old.lower():
                continue  # çakışma → dokunma (veri güvenliği)
            aliases = list(c.get("slug_aliases") or [])
            if old and old not in aliases:
                aliases.append(old)
            await db.categories.update_one({"id": c["id"]},
                                           {"$set": {"slug": correct, "slug_aliases": aliases}})
            used.discard(old.lower())
            used.add(correct)
            if old and old != correct:
                try:
                    await db.seo_redirects.update_one(
                        {"from_path": f"/{old}"},
                        {"$setOnInsert": {"id": generate_id(), "from_path": f"/{old}",
                                          "to_path": f"/{correct}", "status_code": 301, "hits": 0,
                                          "is_active": True,
                                          "created_at": datetime.now(timezone.utc).isoformat()}},
                        upsert=True)
                except Exception:
                    pass
            fixed += 1
        await db.settings.update_one({"id": "category_slug_repair_v1"},
                                     {"$set": {"done": True, "fixed": fixed,
                                               "at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        if fixed:
            logger.info(f"[kategori-slug onarım] {fixed} kategori düzeltildi (alias+301 korundu)")
    except Exception as e:
        logger.error(f"[kategori-slug onarım] hata: {e}")


def _sort_key(v) -> float:
    """Kategori sıra değeri: boş/geçersiz → 999 (sona), 0 dahil sayılar olduğu gibi."""
    if v is None or v == "" or isinstance(v, bool):
        return 999
    try:
        return float(v)
    except (TypeError, ValueError):
        return 999


@router.get("")
async def get_categories(
    request: Request,
    parent_id: Optional[str] = None,
    is_active: Optional[bool] = None,
    visible_only: bool = False
):
    """Get categories.

    visible_only=True (storefront): pasif ve test/placeholder kategorileri gizler.
    Varsayılan False (admin): tüm kategoriler döner — mevcut davranış korunur.
    ÜYELERE ÖZEL: visible_only=True + MİSAFİR (geçerli JWT yok) ise members_only kategoriler gizlenir.
    """
    query = {}
    if parent_id is not None:
        query["parent_id"] = parent_id
    if is_active is not None:
        query["is_active"] = is_active
    if visible_only and "is_active" not in query:
        query["is_active"] = {"$ne": False}

    categories = await db.categories.find(query, {"_id": 0}).to_list(5000)

    # Misafir + storefront görünümü: üyelere-özel kategorileri menü/nav'dan çıkar.
    if not _req_is_member(request):
        # Üyelere özel kategori VE tüm alt kategorileri misafirden gizlenir (visible_only olsun
        # olmasın — panel her zaman oturumlu çağırdığından yönetici etkilenmez).
        from .products import _members_only_cat_ids
        _mo = await _members_only_cat_ids()
        categories = [c for c in categories
                      if not c.get("members_only") and str(c.get("id")) not in _mo]

    if visible_only:
        # PASİF kategorinin TÜM ALT AĞACI da gizlenir: yalnız belge bazında is_active'e
        # bakılınca pasif üstün aktif alt kategorisi menüde KÖK gibi çıkıyordu.
        from .products import _inactive_cat_ids
        _ina = await _inactive_cat_ids()
        if _ina:
            categories = [c for c in categories if str(c.get("id")) not in _ina]
        # Sızan test/placeholder kategorileri (ör. HB_CAT_TEST_123) + alt ağaçları gizlenir.
        # ("Test ve Arıza Tespit Cihazları" gibi gerçek kategoriler artık gizlenmez.)
        categories = hide_test_placeholders(categories)

    # Build hierarchical full_name
    cat_dict = {c["id"]: c for c in categories}
    for c in categories:
        path = []
        curr = c
        while curr:
            path.append(curr.get("name", ""))
            parent_id = curr.get("parent_id")
            if parent_id and parent_id in cat_dict and parent_id != curr.get("id"):
                curr = cat_dict[parent_id]
            else:
                curr = None
        c["full_name"] = " > ".join(reversed(path))

    # Sort: by sort_order if available, else by full_name.
    # Sıra 0 GEÇERLİDİR (panel listesi gibi en önde): eskiden `or 999` 0'ı da sona atıyordu →
    # varsayılanı 0 olan yeni kategori menünün kök sınırı dışına düşüp hiç görünmüyordu.
    categories.sort(key=lambda c: (_sort_key(c.get("sort_order")), c.get("full_name", "")))
    return categories

@router.get("/{category_id}")
async def get_category(category_id: str):
    """Get single category"""
    category = await db.categories.find_one(
        {"$or": [{"id": category_id}, {"slug": category_id}, {"slug_aliases": category_id}]},
        {"_id": 0}
    )
    if not category:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    # Etkin üyelere-özel durumu (kendisi VEYA üst kategorisi işaretli) — vitrin yönlendirmesi için.
    # members_only alanı DEĞİŞTİRİLMEZ (admin formu kendi işaretini görür/kaydeder).
    try:
        from .products import _members_only_cat_ids
        category["members_only_effective"] = str(category.get("id")) in (await _members_only_cat_ids())
    except Exception:
        category["members_only_effective"] = bool(category.get("members_only"))
    return category

def _client_slug(sent, name: str) -> str:
    """İstemcinin gönderdiği slug'ı normalize eder. Eski panel kopyası 'İ'yi 'i-' + birleşik
    nokta → '-' yaparak "sync-i-zmir-gi-ris" üretiyordu; gelen değer addan bu BOZUK yolla
    üretilmiş slug'a eşitse doğru slug (generate_slug(ad)) kullanılır."""
    s = generate_slug(sent or "")
    if s and name:
        naive = str(name).lower()
        for a, b in (("ğ", "g"), ("ü", "u"), ("ş", "s"), ("ı", "i"), ("ö", "o"), ("ç", "c")):
            naive = naive.replace(a, b)
        naive = re.sub(r"[^a-z0-9]+", "-", naive).strip("-")
        if s == naive:
            return generate_slug(name)
    return s


async def _slug_taken(slug: str, exclude_id=None) -> bool:
    """Slug başka bir kategoride (slug veya slug_aliases) kullanılıyor mu?"""
    if not slug:
        return False
    q = {"$or": [{"slug": slug}, {"slug_aliases": slug}]}
    async for c in db.categories.find(q, {"_id": 0, "id": 1}):
        if exclude_id is None or str(c.get("id")) != str(exclude_id):
            return True
    return False


async def _unique_slug(base: str, exclude_id=None) -> str:
    """Çakışan slug'a -2, -3 … eki verir (aynı adlı iki alt kategori aynı URL'yi paylaşmasın)."""
    slug, n = base, 2
    while await _slug_taken(slug, exclude_id) and n < 500:
        slug = f"{base}-{n}"
        n += 1
    return slug


async def _redirect_category_slug(old: str, new: str) -> None:
    """Eski kategori adresini (/{eski} ve /kategori/{eski}) 301 ile yenisine bağlar.
    Yeni adres önceden başka yere yönleniyorsa o kayıt kapatılır (döngü olmasın); eski
    adrese işaret eden zincirler doğrudan yeni adrese çevrilir."""
    now = datetime.now(timezone.utc).isoformat()
    for pre in ("/", "/kategori/"):
        frm, to = f"{pre}{old}", f"{pre}{new}"
        try:
            await db.seo_redirects.update_many({"from_path": to}, {"$set": {"is_active": False}})
            await db.seo_redirects.update_many({"to_path": frm, "is_active": True}, {"$set": {"to_path": to}})
            await db.seo_redirects.update_one(
                {"from_path": frm},
                {"$set": {"to_path": to, "status_code": 301, "is_active": True, "updated_at": now},
                 "$setOnInsert": {"id": generate_id(), "from_path": frm, "hits": 0, "created_at": now}},
                upsert=True)
        except Exception as e:  # yönlendirme yazılamazsa kategori kaydı yine de geçerli
            logger.warning(f"[kategori-slug] 301 yazılamadı {frm} → {to}: {e}")


@router.post("")
async def create_category(
    category_data: dict,
    current_user: dict = Depends(require_admin)
):
    """Create category (admin only)"""
    # Slug SUNUCUDA normalize edilir (istemcinin gönderdiği bozuk 'gi-ris' gibi değerler
    # kaydedilmez) ve başka kategoriyle çakışırsa ek alır.
    _slug = _client_slug(category_data.get("slug"), category_data.get("name", "")) or generate_slug(category_data.get("name", ""))
    category = {
        "id": await generate_short_id("categories"),
        "name": category_data.get("name", ""),
        "slug": await _unique_slug(_slug),
        "description": category_data.get("description", ""),
        "image": category_data.get("image", ""),
        "image_url": category_data.get("image_url", ""),
        "parent_id": category_data.get("parent_id"),
        "attribute_mapping": category_data.get("attribute_mapping", {}),
        "sort_order": category_data.get("sort_order", 0),
        "is_active": category_data.get("is_active", True),
        # ÜYELERE ÖZEL: True ise giriş yapmayan (misafir) bu kategoriyi/ürünlerini göremez.
        "members_only": bool(category_data.get("members_only", False)),
        # Vitrin menüsünde (dikey "Tüm Kategoriler") gösterilsin mi — panelden yönetilir.
        "show_in_menu": category_data.get("show_in_menu", True) is not False,
        "cod_disabled": bool(category_data.get("cod_disabled", False)),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.categories.insert_one(category)
    from .products import invalidate_members_only_cache as _imo
    _imo()   # üyelere-özel kapsamı anında tazelensin
    return {"id": category["id"], "message": "Kategori oluşturuldu"}

@router.put("/{category_id}")
async def update_category(
    category_id: str,
    category_data: dict,
    current_user: dict = Depends(require_admin)
):
    """Update category (admin only)"""
    existing = await db.categories.find_one({"id": category_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    category_data.pop("_id", None)
    category_data.pop("id", None)

    # SLUG: panelin gönderdiği slug KORUNUR (eskiden her kayıtta addan yeniden üretilip ezildi).
    # Slug gönderilmediyse ve ad değiştiyse addan üretilir; ikisi de yoksa mevcut kalır.
    old_slug = str(existing.get("slug") or "")
    old_name = existing.get("name") or ""
    new_name = (category_data.get("name") or "").strip() or old_name
    if "name" in category_data:
        category_data["name"] = new_name
    _sent = _client_slug(category_data.get("slug"), new_name)
    if _sent:
        new_slug = _sent
        if new_slug != old_slug and await _slug_taken(new_slug, existing.get("id")):
            raise HTTPException(status_code=409, detail=f"'{new_slug}' adresi başka bir kategoride kullanılıyor")
    elif new_name != old_name or not old_slug:
        new_slug = await _unique_slug(generate_slug(new_name), existing.get("id"))
    else:
        new_slug = old_slug
    category_data["slug"] = new_slug
    if old_slug and new_slug != old_slug:
        # Eski adres kırılmasın: slug_aliases + 301 (ürün slug değişimiyle aynı davranış).
        aliases = [a for a in (existing.get("slug_aliases") or []) if a and a != new_slug]
        if old_slug not in aliases:
            aliases.append(old_slug)
        category_data["slug_aliases"] = aliases

    if "members_only" in category_data:   # ÜYELERE ÖZEL bayrağı — bool'a normalize et
        category_data["members_only"] = bool(category_data["members_only"])
    if "show_in_menu" in category_data:   # Menüde göster — bool'a normalize et
        category_data["show_in_menu"] = category_data["show_in_menu"] is not False

    category_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.categories.update_one({"id": existing["id"]}, {"$set": category_data})

    if old_slug and new_slug != old_slug:
        await _redirect_category_slug(old_slug, new_slug)
    if new_name != old_name or new_slug != old_slug:
        await _sync_products_after_category_change(existing, new_name, new_slug)

    from .products import invalidate_members_only_cache as _imo
    _imo()   # üyelere-özel / pasif kapsamı anında tazelensin
    return {"message": "Kategori güncellendi", "slug": new_slug}


async def _sync_products_after_category_change(existing: dict, new_name: str, new_slug: str) -> None:
    """Kategori adı/slug'ı değişince üründeki KOPYA alanları tazeler: birincil kategorisi bu
    olan ürünlerde category_name/category_slug; bu kategoriyi (veya bir alt kategorisini)
    içeren ürünlerde breadcrumb. Aksi halde kartta eski ad kalıyor, yeni adla arama sonuç
    vermiyor, JSON-LD/feed ölü adrese işaret ediyordu."""
    cid = existing.get("id")
    try:
        await db.products.update_many(
            {"category_id": {"$in": _id_variants(cid)}},
            {"$set": {"category_name": new_name, "category_slug": new_slug}})
        # Breadcrumb (kök→yaprak adlar, ">" ile) — ağaç yeni adla yeniden kurulur.
        cmap = {}
        async for c in db.categories.find({}, {"_id": 0, "id": 1, "name": 1, "parent_id": 1}):
            if c.get("id") is not None:
                cmap[str(c["id"])] = c

        def _crumb(pid) -> str:
            names, cur, g = [], str(pid) if pid is not None else "", 0
            while cur and cur in cmap and g < 50:
                names.append(cmap[cur].get("name") or "")
                p = cmap[cur].get("parent_id")
                cur = str(p) if p not in (None, "") else ""
                g += 1
            return ">".join([n for n in reversed(names) if n])

        async for p in db.products.find({"category_ids": {"$in": _id_variants(cid)}},
                                        {"_id": 0, "id": 1, "category_id": 1, "breadcrumb": 1}):
            if p.get("category_id") in (None, ""):
                continue
            bc = _crumb(p.get("category_id"))
            if bc and bc != p.get("breadcrumb"):
                await db.products.update_one({"id": p["id"]}, {"$set": {"breadcrumb": bc}})
    except Exception as e:
        logger.warning(f"[kategori-güncelle] ürün kopya alanları tazelenemedi ({cid}): {e}")

def _id_variants(v):
    """Kategori id'si DB'de int VEYA string olabilir — ikisini de eşlemek için liste döndürür."""
    out = [v]
    s = str(v)
    out.append(s)
    try:
        out.append(int(s))
    except (TypeError, ValueError):
        pass
    # tekilleştir (sırayı koru)
    seen, uniq = set(), []
    for x in out:
        k = (type(x).__name__, str(x))
        if k not in seen:
            seen.add(k); uniq.append(x)
    return uniq


@router.post("/merge")
async def merge_categories(payload: dict, current_user: dict = Depends(require_admin)):
    """İki kategoriyi GÜVENLİ birleştirir (mükerrer/çift yapıyı temizlemek için).
    source kategorisi altındaki ALT KATEGORİLER ve ürün referansları target'a taşınır,
    sonra source silinir. Ürünler asla yetim kalmaz.

    payload: {"source_id": <id>, "target_id": <id>}
    Reassign edilenler: alt kategori parent_id; ürün category_ids[] / category_id /
    category_slug / category_name (yalnız source'a EŞİT olanlar).
    """
    src_id = payload.get("source_id")
    tgt_id = payload.get("target_id")
    if src_id is None or tgt_id is None:
        raise HTTPException(status_code=400, detail="source_id ve target_id gerekli")
    if str(src_id) == str(tgt_id):
        raise HTTPException(status_code=400, detail="source ve target aynı olamaz")

    src = await db.categories.find_one({"id": {"$in": _id_variants(src_id)}}, {"_id": 0})
    tgt = await db.categories.find_one({"id": {"$in": _id_variants(tgt_id)}}, {"_id": 0})
    if not src:
        raise HTTPException(status_code=404, detail="Kaynak kategori bulunamadı")
    if not tgt:
        raise HTTPException(status_code=404, detail="Hedef kategori bulunamadı")

    src_real = src["id"]; tgt_real = tgt["id"]
    src_vars = _id_variants(src_real)
    report = {"source": {"id": src_real, "name": src.get("name")},
              "target": {"id": tgt_real, "name": tgt.get("name")}}

    # 1) Alt kategorileri target'a taşı
    r_children = await db.categories.update_many(
        {"parent_id": {"$in": src_vars}}, {"$set": {"parent_id": tgt_real}})
    report["children_moved"] = r_children.modified_count

    # 2) Ürün category_ids[] dizisinde source → target
    #    Önce target'ı ekle (source içerenlere), sonra source'u çıkar.
    await db.products.update_many(
        {"category_ids": {"$in": src_vars}}, {"$addToSet": {"category_ids": tgt_real}})
    r_arr = await db.products.update_many(
        {"category_ids": {"$in": src_vars}}, {"$pull": {"category_ids": {"$in": src_vars}}})
    report["products_category_ids"] = r_arr.modified_count

    # 3) Skaler category_id source → target
    r_scalar = await db.products.update_many(
        {"category_id": {"$in": src_vars}}, {"$set": {"category_id": tgt_real}})
    report["products_category_id"] = r_scalar.modified_count

    # 4) category_slug source.slug → target.slug (yalnız tam eşleşen)
    if src.get("slug"):
        r_slug = await db.products.update_many(
            {"category_slug": src["slug"]}, {"$set": {"category_slug": tgt.get("slug") or src["slug"]}})
        report["products_category_slug"] = r_slug.modified_count

    # 5) category_name source.name → target.name (yalnız tam eşleşen)
    if src.get("name"):
        r_name = await db.products.update_many(
            {"category_name": src["name"]}, {"$set": {"category_name": tgt.get("name") or src["name"]}})
        report["products_category_name"] = r_name.modified_count

    # 6) ÜRÜN DIŞI referanslar (uç eskiden bunları atlıyordu → kampanya kapsamı, manuel
    #    ürün sırası, feed etiket kuralları ve pazaryeri eşlemeleri sessizce öksüz kalıyordu).
    try:
        await db.coupons.update_many({"categories": {"$in": src_vars}},
                                     {"$addToSet": {"categories": tgt_real}})
        r_cpn = await db.coupons.update_many({"categories": {"$in": src_vars}},
                                             {"$pull": {"categories": {"$in": src_vars}}})
        report["coupons_rescoped"] = r_cpn.modified_count
    except Exception as e:
        report["coupons_error"] = str(e)[:120]
    try:
        # Manuel ürün sırası: hedefin kendi sırası VARSA o kazanır, yoksa kaynağınki taşınır.
        _src_ord = await db.category_product_order.find_one({"id": str(src_real)}, {"_id": 0, "ids": 1})
        if _src_ord:
            _tgt_ord = await db.category_product_order.find_one({"id": str(tgt_real)}, {"_id": 0, "ids": 1})
            if not _tgt_ord:
                await db.category_product_order.update_one(
                    {"id": str(tgt_real)},
                    {"$set": {"id": str(tgt_real), "ids": _src_ord.get("ids") or []}}, upsert=True)
                report["manual_order_moved"] = True
            await db.category_product_order.delete_one({"id": str(src_real)})
    except Exception as e:
        report["manual_order_error"] = str(e)[:120]
    try:
        _feeds = 0
        async for _f in db.xml_feeds.find({}, {"_id": 0, "id": 1, "custom_labels": 1}):
            _rules = _f.get("custom_labels") or []
            _chg = False
            for _r in _rules:
                if not isinstance(_r, dict):
                    continue
                _cids = [str(x) for x in (_r.get("category_ids") or [])]
                if any(c in [str(v) for v in src_vars] for c in _cids):
                    _r["category_ids"] = sorted({(str(tgt_real) if c in [str(v) for v in src_vars] else c)
                                                 for c in _cids})
                    _chg = True
            if _chg:
                await db.xml_feeds.update_one({"id": _f["id"]}, {"$set": {"custom_labels": _rules}})
                _feeds += 1
        report["feeds_updated"] = _feeds
    except Exception as e:
        report["feeds_error"] = str(e)[:120]
    try:
        _mp = 0
        for _coll in ("category_mappings",):
            _r = await db[_coll].update_many({"category_id": {"$in": src_vars}},
                                             {"$set": {"category_id": tgt_real}})
            _mp += _r.modified_count
        report["category_maps_moved"] = _mp
    except Exception as e:
        report["category_maps_error"] = str(e)[:120]

    # 7) source kategorisini sil — ÖNCE öksüz ürün kalmadığını doğrula
    _left = await db.products.count_documents(
        {"$or": [{"category_id": {"$in": src_vars}}, {"category_ids": {"$in": src_vars}}]})
    report["products_left_on_source"] = _left
    if _left:
        report["source_deleted"] = False
        report["warning"] = (f"Kaynak kategoride hâlâ {_left} ürün görünüyor; SİLİNMEDİ. "
                             f"Ürünler taşındıktan sonra tekrar deneyin.")
        logger.warning(f"[category-merge] {src_real} silinmedi: {_left} ürün kaldı")
        return {"message": "Birleştirme kısmi: kaynak kategori silinmedi", "report": report}
    await db.categories.delete_one({"id": src_real})
    report["source_deleted"] = True
    logger.info(f"[category-merge] {src_real}({src.get('name')}) → {tgt_real}({tgt.get('name')}) {report}")
    return {"message": "Kategoriler birleştirildi", "report": report}


@router.delete("/{category_id}")
async def delete_category(
    category_id: str,
    current_user: dict = Depends(require_permission("products.categories"))
):
    """Delete category (admin only)"""
    result = await db.categories.delete_one({"id": {"$in": _id_variants(category_id)}})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Kategori bulunamadı")
    from .products import invalidate_members_only_cache as _imo
    _imo()   # üyelere-özel kapsamı anında tazelensin
    return {"message": "Kategori silindi"}
