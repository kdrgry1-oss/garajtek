"""
CMS routes - Page blocks, homepage content management
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import Optional
from datetime import datetime, timezone

from .deps import db, logger, require_admin, generate_id
from activity_audit import record_admin_audit

try:
    from zoneinfo import ZoneInfo
except Exception:                      # py<3.9 (olmamalı, güvenlik ağı)
    ZoneInfo = None

router = APIRouter(prefix="/page-blocks", tags=["CMS"])

# ── ZAMANLI YAYIN (banner/slayt zaman aralığı) ──────────────────────────────
# Panelden her slayta (ve istenirse tüm bloğa) "şu tarih-saat aralığında yayında
# olsun" kuralı girilebilir. Saatler YEREL duvar saati olarak saklanır + saat
# dilimi adı; UTC'ye çevirme YAPILMAZ ki panelde girilen saat neyse vitrinde de o
# olsun (yaz saati değişse bile). Süzme SUNUCUDA yapılır: süresi dolan slayt
# vitrine hiç gitmez, kaynak koda/derlemeye dokunmadan kaybolur.
DEFAULT_TZ = "Europe/Istanbul"
# Görseli olmayınca anlamını yitiren blok tipleri — tüm slaytları zamanı geçmişse
# blok komple gizlenir. (text_block hariç: metni yayında kalmalı.)
_MEDIA_ONLY_TYPES = {"hero_slider", "full_banner", "half_banners", "instashop"}


def _tz(name):
    if not ZoneInfo:
        return timezone.utc
    try:
        return ZoneInfo(str(name or DEFAULT_TZ))
    except Exception:
        try:
            return ZoneInfo(DEFAULT_TZ)
        except Exception:
            return timezone.utc


def _clean_schedule(v):
    """Panelden gelen zaman aralığını doğrular: {start, end, tz} ya da None.
    start/end: 'YYYY-MM-DDTHH:MM' (yerel duvar saati). İkisi de boşsa kural yok."""
    if not isinstance(v, dict):
        return None

    def _dt(x):
        t = str(x or "").strip().replace(" ", "T")[:16]
        if not t:
            return ""
        try:
            datetime.strptime(t, "%Y-%m-%dT%H:%M")
        except Exception:
            return ""
        return t

    start, end = _dt(v.get("start")), _dt(v.get("end"))
    if not start and not end:
        return None
    tzname = str(v.get("tz") or DEFAULT_TZ).strip()[:64]
    if ZoneInfo:
        try:
            ZoneInfo(tzname)
        except Exception:
            tzname = DEFAULT_TZ
    out = {"start": start, "end": end, "tz": tzname}
    if start and end and end < start:      # ters aralık → uyarı yerine düzelt
        out["start"], out["end"] = end, start
    return out


def _schedule_active(sched, now_utc=None) -> bool:
    """Kural yoksa/bozuksa YAYINDA sayılır (mevcut bannerlar etkilenmez)."""
    if not isinstance(sched, dict):
        return True
    start, end = str(sched.get("start") or ""), str(sched.get("end") or "")
    if not start and not end:
        return True
    z = _tz(sched.get("tz"))
    now = (now_utc or datetime.now(timezone.utc)).astimezone(z)

    def _p(x):
        try:
            return datetime.strptime(str(x)[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=z)
        except Exception:
            return None

    s, e = _p(start), _p(end)
    if s and now < s:
        return False
    if e and now > e.replace(second=59, microsecond=999999):   # bitiş dakikası DAHİL
        return False
    return True


def _apply_block_schedule(block: dict, now_utc=None):
    """Zamanı gelmemiş/geçmiş slaytları bloktan çıkarır. Blok komple gizlenecekse
    None döner. images/links/img_dims/slide_schedule PARALEL süzülür."""
    st = block.get("settings") if isinstance(block.get("settings"), dict) else {}
    if not _schedule_active(st.get("schedule"), now_utc):
        return None
    sl = st.get("slide_schedule")
    imgs = block.get("images") or []
    if not (isinstance(sl, list) and imgs and any(isinstance(x, dict) for x in sl)):
        return block
    keep = [i for i in range(len(imgs))
            if _schedule_active(sl[i] if i < len(sl) else None, now_utc)]
    if len(keep) == len(imgs):
        return block
    links = block.get("links") or []
    dims = st.get("img_dims") if isinstance(st.get("img_dims"), list) else None
    out = dict(block)
    out["images"] = [imgs[i] for i in keep]
    out["links"] = [(links[i] if i < len(links) else "/") for i in keep]
    ns = dict(st)
    ns["slide_schedule"] = [(sl[i] if i < len(sl) else None) for i in keep]
    if dims is not None:
        ns["img_dims"] = [(dims[i] if i < len(dims) else None) for i in keep]
    out["settings"] = ns
    if not out["images"] and str(block.get("type") or "") in _MEDIA_ONLY_TYPES:
        return None
    return out


def _sanitize_schedule_settings(settings, images):
    """settings.schedule (blok) + settings.slide_schedule (slayt başı) doğrulanır."""
    if not isinstance(settings, dict):
        return settings
    out = dict(settings)
    _b = _clean_schedule(out.get("schedule"))
    if _b:
        out["schedule"] = _b
    else:
        out.pop("schedule", None)
    raw = out.get("slide_schedule")
    if isinstance(raw, list):
        n = len(images or [])
        cleaned = [_clean_schedule(raw[i]) if i < len(raw) else None for i in range(n)] \
            if n else [_clean_schedule(x) for x in raw]
        if any(cleaned):
            out["slide_schedule"] = cleaned
        else:
            out.pop("slide_schedule", None)
    elif "slide_schedule" in out:
        out.pop("slide_schedule", None)
    return out


def _requester_is_admin(request) -> bool:
    """Panel mi istiyor? (?all=1 ile zamanı gelmemiş slaytları da görmek için).
    Yalnız token'daki is_admin iddiası doğrulanır — burada sır değil, yayına
    girmemiş banner görselinin rakibe sızmaması amaçlanır."""
    try:
        auth = (request.headers.get("authorization") or "").strip()
        if not auth.lower().startswith("bearer "):
            return False
        from .deps import _decode_jwt_strict
        return bool(_decode_jwt_strict(auth.split(" ", 1)[1].strip()).get("is_admin"))
    except Exception:
        return False

_home_layout_checked = False


async def _ensure_home_layout_once():
    """Ana sayfa varsayılan (şablon v1.0) düzeni — süreç başına bir kez kontrol edilir; boş ya da
    el değmemiş eski iskelet varsa kurar, düzenlenmiş tasarıma dokunmaz (bkz. home_layout.py)."""
    global _home_layout_checked
    if _home_layout_checked:
        return
    _home_layout_checked = True
    try:
        from home_layout import ensure_default_home
        res = await ensure_default_home(db)
        if res:
            logger.info(f"[page-blocks] varsayılan ana sayfa düzeni kuruldu: {res}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[page-blocks] varsayılan ana sayfa düzeni kurulamadı: {e}")


@router.get("")
async def get_page_blocks(
    request: Request,
    page: str = Query("home"),
    is_active: Optional[bool] = None,
    all: bool = Query(False, description="Panel: zaman kuralı süzmeden TÜM slaytlar"),
):
    """Sayfanın bloklarını döner.

    ZAMANLI YAYIN: slayt/blok bazlı zaman aralığı kuralları SUNUCUDA uygulanır —
    zamanı gelmemiş ya da süresi dolmuş slayt vitrine hiç gitmez. Panel (admin
    token + ?all=1) hepsini görür, yoksa düzenleme ekranında slaytlar kaybolurdu."""
    if page == "home":
        await _ensure_home_layout_once()
    query = {"page": page}
    if is_active is not None:
        query["is_active"] = is_active

    blocks = await db.page_blocks.find(query, {"_id": 0}).sort("sort_order", 1).to_list(50)
    if all and _requester_is_admin(request):
        return blocks
    now = datetime.now(timezone.utc)
    out = []
    for b in blocks:
        try:
            b2 = _apply_block_schedule(b, now)
        except Exception as e:
            logger.warning(f"[page-blocks] zaman suzme hatasi ({b.get('id')}): {e}")
            b2 = b
        if b2 is not None:
            out.append(b2)
    return out

# ── HEADER MENÜ (Menü Yönetimi) ─────────────────────────────────────────────
# ÖNEMLİ: /{block_id} rotasından ÖNCE tanımlı olmalı, yoksa "header-menu"
# block_id olarak yakalanır.

@router.get("/header-menu")
async def get_header_menu(request: Request):
    """Vitrin header menüsü (public). Kayıt yoksa boş döner — frontend
    kendi varsayılanını (mevcut sabit menü) kullanır, görünüm bozulmaz.
    ÜYELERE ÖZEL: misafire, üyelere özel kategoriye (veya alt kategorisine) giden sekme /
    sütun / link gösterilmez."""
    doc = await db.settings.find_one({"id": "header_menu"}, {"_id": 0})
    tabs = (doc or {}).get("tabs") or []
    try:
        from .products import request_is_member, _members_only_cat_ids
        if tabs and not request_is_member(request):
            mo = await _members_only_cat_ids()
            if mo:
                slugs = set()
                async for c in db.categories.find({"id": {"$in": list(mo)}},
                                                  {"_id": 0, "slug": 1, "slug_aliases": 1}):
                    if c.get("slug"):
                        slugs.add(str(c["slug"]).lower())
                    for a in (c.get("slug_aliases") or []):
                        slugs.add(str(a).lower())

                def _slug(link):
                    import re as _re
                    l = str(link or "")
                    m = _re.search(r"[?&]kategori=([^&#]+)", l)
                    if m:
                        return m.group(1).lower()
                    seg = [x for x in l.split("?")[0].split("#")[0].split("/") if x]
                    return (seg[-1] if seg else "").lower()

                def _blocked(link):
                    return bool(link) and _slug(link) in slugs

                out = []
                for t in tabs:
                    if not isinstance(t, dict) or _blocked(t.get("link")):
                        continue
                    t = dict(t)
                    cols = []
                    for col in (t.get("columns") or []):
                        if not isinstance(col, dict) or _blocked(col.get("link")):
                            continue
                        col = dict(col)
                        col["items"] = [it for it in (col.get("items") or [])
                                        if isinstance(it, dict) and not _blocked(it.get("link"))]
                        cols.append(col)
                    if "columns" in t:
                        t["columns"] = cols
                    out.append(t)
                tabs = out
    except Exception as _e:
        logger.warning(f"[header-menu] üyelere özel süzgeç: {_e}")
    return {"tabs": tabs}


@router.put("/header-menu")
async def save_header_menu(payload: dict, request: Request,
                           current_user: dict = Depends(require_admin)):
    """Header menüsünü kaydeder. tabs: [{id,label,type,link,style,active,columns:[{title,link,items:[{name,link}]}]}]"""
    tabs = payload.get("tabs")
    if not isinstance(tabs, list) or not tabs:
        raise HTTPException(status_code=400, detail="tabs boş olamaz")

    def _s(v, maxlen=300):
        return str(v or "").strip()[:maxlen]

    clean = []
    for i, t in enumerate(tabs):
        if not isinstance(t, dict) or not _s(t.get("label")):
            continue
        tab = {
            "id": _s(t.get("id")) or f"tab{i}",
            "label": _s(t.get("label"), 60),
            "type": "mega" if t.get("type") == "mega" else "link",
            "link": _s(t.get("link")) or "/",
            "style": t.get("style") if t.get("style") in ("accent", "sale") else "normal",
            "active": t.get("active") is not False,
        }
        if tab["type"] == "mega":
            cols = []
            for c in (t.get("columns") or []):
                if not isinstance(c, dict):
                    continue
                items = [{"name": _s(it.get("name"), 60), "link": _s(it.get("link")) or "/"}
                         for it in (c.get("items") or [])
                         if isinstance(it, dict) and _s(it.get("name"))]
                cols.append({"title": _s(c.get("title"), 60), "link": _s(c.get("link")) or "/", "items": items})
            tab["columns"] = cols
        clean.append(tab)
    if not clean:
        raise HTTPException(status_code=400, detail="Geçerli sekme yok")

    before = await db.settings.find_one({"id": "header_menu"}, {"_id": 0}) or {}
    await db.settings.update_one(
        {"id": "header_menu"},
        {"$set": {"tabs": clean, "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": current_user.get("email") or current_user.get("id")}},
        upsert=True,
    )
    await record_admin_audit(
        db, action="header_menu.update", entity_type="content", entity_id="header_menu",
        before=before, after={"id": "header_menu", "tabs": clean},
        current_user=current_user, request=request, source="content.menu",
    )
    return {"success": True, "tabs": clean}


@router.get("/{block_id}")
async def get_page_block(block_id: str):
    """Get single page block"""
    block = await db.page_blocks.find_one({"id": block_id}, {"_id": 0})
    if not block:
        raise HTTPException(status_code=404, detail="Blok bulunamadı")
    return block

@router.post("")
async def create_page_block(
    block_data: dict,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Create page block (admin only)"""
    block = {
        "id": generate_id(),
        "type": block_data.get("type", "hero_slider"),
        "title": block_data.get("title", ""),
        "images": block_data.get("images", []),
        "links": block_data.get("links", []),
        "settings": _sanitize_schedule_settings(block_data.get("settings", {}),
                                                block_data.get("images", [])),
        "page": block_data.get("page", "home"),
        "sort_order": block_data.get("sort_order", 0),
        "is_active": block_data.get("is_active", True),
        "show_desktop": block_data.get("show_desktop", True),
        "show_mobile": block_data.get("show_mobile", True),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.page_blocks.insert_one(block)
    await record_admin_audit(
        db, action="page_block.create", entity_type="page_block", entity_id=block["id"],
        before={}, after=block, current_user=current_user, request=request, source="content.blocks",
    )
    return {"id": block["id"], "message": "Blok oluşturuldu"}

@router.put("/{block_id}")
async def update_page_block(
    block_id: str,
    block_data: dict,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Update page block (admin only).
    Whitelist'li güncelleme: id, created_at gibi sistem alanları override edilemez.
    """
    existing = await db.page_blocks.find_one({"id": block_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Blok bulunamadı")

    allowed = {"type", "title", "images", "links", "settings", "page", "sort_order", "is_active", "show_desktop", "show_mobile"}
    update_set = {k: v for k, v in block_data.items() if k in allowed}
    if "settings" in update_set:
        update_set["settings"] = _sanitize_schedule_settings(
            update_set["settings"],
            update_set.get("images", existing.get("images") or []))
    update_set["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.page_blocks.update_one({"id": block_id}, {"$set": update_set})
    await record_admin_audit(
        db, action="page_block.update", entity_type="page_block", entity_id=block_id,
        before=existing, after={**existing, **update_set}, current_user=current_user,
        request=request, source="content.blocks",
    )
    return {"message": "Blok güncellendi"}

@router.delete("/{block_id}")
async def delete_page_block(
    block_id: str,
    request: Request,
    current_user: dict = Depends(require_admin)
):
    """Delete page block (admin only)"""
    existing = await db.page_blocks.find_one({"id": block_id}, {"_id": 0})
    result = await db.page_blocks.delete_one({"id": block_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Blok bulunamadı")
    await record_admin_audit(
        db, action="page_block.delete", entity_type="page_block", entity_id=block_id,
        before=existing or {}, after={}, current_user=current_user, request=request,
        source="content.blocks",
    )
    return {"message": "Blok silindi"}


@router.post("/reorder")
async def reorder_page_blocks(
    payload: dict,
    current_user: dict = Depends(require_admin)
):
    """Toplu sıralama güncellemesi.
    Body: { "ids": ["id1", "id2", "id3", ...] } — listedeki sıraya göre sort_order=1,2,3,... atanır.
    Tek tek PUT'a gerek kalmadan hızlı sürükle-bırak kaydetmeyi sağlar.
    """
    ids = payload.get("ids") or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="ids listesi gerekli")
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    for idx, bid in enumerate(ids, start=1):
        r = await db.page_blocks.update_one(
            {"id": bid}, {"$set": {"sort_order": idx, "updated_at": now}}
        )
        updated += r.modified_count
    return {"success": True, "updated": updated, "total": len(ids)}


@router.post("/install-default-home")
async def install_default_home_layout(
    request: Request,
    replace: bool = Query(False, description="True: üst barlar dışındaki mevcut ana sayfa bloklarını siler"),
    current_user: dict = Depends(require_admin),
):
    """Şablonun v1.0 ana sayfa düzenini (slider, reklam bannerları, fırsat+sekmeler, 2-1-2 ızgara,
    çok satanlar, tam banner, son eklenenler, markalar, ürün sütunları) blok olarak ekler."""
    from home_layout import install_default_home
    before = await db.page_blocks.find({"page": "home"}, {"_id": 0}).to_list(200)
    res = await install_default_home(db, replace=replace)
    await record_admin_audit(
        db, action="page_block.install_default_home", entity_type="page_block", entity_id="home",
        before={"blocks": len(before)}, after=res, current_user=current_user, request=request,
        source="content.blocks",
    )
    return {"success": True, **res}


@router.post("/seed-default-home")
async def seed_default_home_blocks(
    overwrite: bool = Query(False),
    current_user: dict = Depends(require_admin)
):
    """Mevcut Home.jsx default tasarımını DB bloklarına aktarır (admin'den
    yönetilebilir hale getirir). overwrite=True ise mevcut home blokları silinir.
    """
    if overwrite:
        await db.page_blocks.delete_many({"page": "home"})

    existing_count = await db.page_blocks.count_documents({"page": "home"})
    if existing_count > 0 and not overwrite:
        return {
            "success": False,
            "message": f"Anasayfada zaten {existing_count} blok var. overwrite=true ile çağırın.",
            "existing_count": existing_count,
        }

    now = datetime.now(timezone.utc).isoformat()
    # BEYAZ ETİKET: varsayılan bloklar GÖRSELSİZ iskelettir — görseller/linkler Sayfa
    # Tasarımı ekranından mağazanın kendi içeriğiyle doldurulur (koda gömülü firma görseli YOK).
    default_blocks = [
        {
            "type": "hero_slider",
            "title": "Ana Slider",
            "images": [],
            "links": [],
            "settings": {"autoplay": True, "interval_ms": 5000},
            "sort_order": 1,
        },
        {
            "type": "full_banner",
            "title": "Tek Banner",
            "images": [],
            "links": [],
            "sort_order": 2,
        },
        {
            "type": "half_banners",
            "title": "İki Banner",
            "images": [],
            "links": [],
            "sort_order": 3,
        },
        {
            "type": "product_slider",
            "title": "Yeni Sezon",
            "images": [],
            "links": [],
            "settings": {"category_slug": "en-yeniler", "limit": 8},
            "sort_order": 4,
        },
        {
            "type": "instashop",
            "title": "Atölyemizden",
            "images": [],
            "links": [],
            "sort_order": 5,
        },
    ]

    inserted = []
    for b in default_blocks:
        b.update({
            "id": generate_id(),
            "page": "home",
            "is_active": True,
            "created_at": now,
        })
        b.setdefault("settings", {})
        await db.page_blocks.insert_one(b)
        inserted.append({"id": b["id"], "type": b["type"], "title": b["title"]})

    return {
        "success": True,
        "message": f"{len(inserted)} default blok eklendi",
        "blocks": inserted,
    }
