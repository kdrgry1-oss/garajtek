"""
CMS routes — sayfa blokları (vitrin okuma), header menüsü.

Sayfa Tasarımı v2 (docs/page-design/SPEC.md): bloklar `page_layouts` yayın belgesinde tutulur, düzenleme
/api/page-design/* taslak-yayın akışıyla yapılır (routes/page_design.py). `page_blocks` koleksiyonu
eski uçlar/modüller için yayın AYNASIDIR. Bu dosyadaki eski tekil blok yazma uçları (POST/PUT/DELETE/
reorder/seed-default-home) 410 döner; install-default-home şablon düzenini TASLAĞA yükler.
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Request

from .deps import db, logger, require_admin
from activity_audit import record_admin_audit
from pageblocks import store as pd_store

blocks_router = APIRouter(prefix="/page-blocks", tags=["CMS"])
router = blocks_router  # aşağıdaki dekoratörler için (en altta toplayıcı `router` yeniden tanımlanır)

_GONE = ("Bu eski uç kaldırıldı. Sayfa Tasarımı artık taslak/yayın akışını kullanır: "
         "/api/page-design/{sayfa}/draft ve /publish.")


def _request_is_member(request) -> bool:
    try:
        from .products import request_is_member
        return bool(request_is_member(request))
    except Exception:  # noqa: BLE001
        return False


@router.get("")
async def get_page_blocks(request: Request, page: str = Query("home")):
    """Sayfanın YAYINDAKİ blokları (public). Yalnız aktif, zamanı gelmiş ve ziyaretçiye uygun
    (hedef kitle) bloklar döner; taslak ve `is_active=false` bloklar ASLA dönmez. Repeater öğelerinin
    zamanlaması (slayt başına yayın aralığı) öğe düzeyinde sunucuda süzülür. Sınırsız (eski 50 sınırı yok)."""
    if not pd_store.valid_page(page):
        return []
    try:
        return await pd_store.public_blocks(db, page, is_member=_request_is_member(request))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[page-blocks] yayın okunamadı: {e}")
        return []

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
    """Yayındaki tek blok (public)."""
    for page in ("home",):
        for b in await pd_store.public_blocks(db, page):
            if b.get("id") == block_id:
                return b
    raise HTTPException(status_code=404, detail="Blok bulunamadı")


@router.post("")
async def create_page_block(current_user: dict = Depends(require_admin)):
    raise HTTPException(status_code=410, detail=_GONE)


@router.put("/{block_id}")
async def update_page_block(block_id: str, current_user: dict = Depends(require_admin)):
    raise HTTPException(status_code=410, detail=_GONE)


@router.delete("/{block_id}")
async def delete_page_block(block_id: str, current_user: dict = Depends(require_admin)):
    raise HTTPException(status_code=410, detail=_GONE)


@router.post("/reorder")
async def reorder_page_blocks(current_user: dict = Depends(require_admin)):
    raise HTTPException(status_code=410, detail=_GONE)


@router.post("/install-default-home")
async def install_default_home_layout(
    request: Request,
    replace: bool = Query(False, description="True: üst barlar dışındaki blokları şablon düzeniyle değiştirir"),
    current_user: dict = Depends(require_admin),
):
    """Şablonun v1.0 ana sayfa düzenini (defaults.json'lardan üretilir) TASLAĞA yükler; yayın için
    Sayfa Tasarımı'nda "Yayınla" gerekir."""
    doc = await pd_store.default_layout_draft(db, "home", replace=replace,
                                              user=str(current_user.get("email") or current_user.get("id")))
    await record_admin_audit(
        db, action="page_block.install_default_home", entity_type="page_layout", entity_id="home",
        before={}, after={"draft_rev": doc["rev"], "blocks": len(doc["blocks"])}, current_user=current_user,
        request=request, source="content.blocks",
    )
    return {"success": True, "created": len(doc["blocks"]), "draft_rev": doc["rev"],
            "message": "Şablon düzeni taslağa yüklendi — yayınlamak için Sayfa Tasarımı'nda “Yayınla”ya basın."}


@router.post("/seed-default-home")
async def seed_default_home_blocks(current_user: dict = Depends(require_admin)):
    """Eski 5 bloklu iskelet kaldırıldı (SPEC §6.2/9)."""
    raise HTTPException(status_code=410, detail="Bu uç kaldırıldı. Şablon düzeni için "
                                                "/api/page-design/home/install-default kullanın.")


# ── Toplayıcı: eski /page-blocks + yeni /page-design, /site-design, /page-blocks/resolve-products
from .page_design import router as _page_design_router, site_router as _site_router, resolve_router as _resolve_router  # noqa: E402

router = APIRouter()
router.include_router(_resolve_router)   # /page-blocks/resolve-products (/{block_id}'den önce)
router.include_router(blocks_router)
router.include_router(_page_design_router)
router.include_router(_site_router)
