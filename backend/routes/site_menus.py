"""Vitrin menü grupları (Admin › Tasarım › Menü Yönetimi).

Şablondaki her menü bölgesi ayrı bir grup olarak yönetilir:
  topbar       — Üst bar bağlantıları (en üst ince şerit: Mağazamız / Sipariş Takibi / Hesabım …)
  hamburger    — Hamburger (☰) yan menü: logonun yanındaki ikon, soldan açılan panel
  departments  — "Tüm Kategoriler" sol (dikey) menü: otomatik kategori ağacı VEYA elle menü,
                 üstte sabitlenmiş hızlı bağlantılar (Günün Fırsatları / Yeni Ürünler …)
  center       — Orta menü (ana navigasyon): sekmeler page-blocks/header-menu'de (geriye uyum),
                 burada yalnız sağdaki kampanya yazısı (ör. "Ücretsiz Kargo …")
  mobile       — Mobil menü: hamburger menüyle aynı ya da ayrı liste
(Footer sütunları Footer Tasarımı ekranında yönetilir.)

Öğe: {id, label, link, icon, style: normal|bold|sale, children: [...]} — en fazla 3 seviye.
"""
from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, Request

from .deps import db, logger, require_admin
from activity_audit import record_admin_audit

router = APIRouter(prefix="/site-menus", tags=["Menüler"])

GROUP_KEYS = ("topbar", "hamburger", "departments", "center", "mobile")

DEFAULTS = {
    "topbar": {
        "welcome": "",  # boşsa vitrin "<Mağaza adı>'e Hoş Geldiniz" yazar
        "items": [
            {"id": "tb-store", "label": "Mağazamız", "link": "/sayfa/iletisim", "icon": "ec ec-map-pointer"},
            {"id": "tb-track", "label": "Sipariş Takibi", "link": "/siparis-takip", "icon": "ec ec-transport"},
            {"id": "tb-shop", "label": "Mağaza", "link": "/tum-urunler", "icon": "ec ec-shopping-bag"},
            {"id": "tb-account", "label": "Hesabım", "link": "/hesabim", "icon": "ec ec-user", "special": "account"},
        ],
    },
    "departments": {
        "mode": "auto",   # auto: kategori ağacından | manual: aşağıdaki items
        "max_roots": 14,
        "quick": [
            {"id": "dq-deals", "label": "Günün Fırsatları", "link": "/sale", "style": "bold"},
            {"id": "dq-top", "label": "En Çok Satanlar", "link": "/tum-urunler?sort=popular&order=desc", "style": "bold"},
            {"id": "dq-new", "label": "Yeni Ürünler", "link": "/en-yeniler", "style": "bold"},
        ],
        "items": [],
    },
    "hamburger": {
        "mode": "auto",   # auto: hızlı bağlantılar + kategori ağacı | manual: items
        "quick": [
            {"id": "hq-deals", "label": "Günün Fırsatları", "link": "/sale", "style": "bold"},
            {"id": "hq-new", "label": "Yeni Ürünler", "link": "/en-yeniler", "style": "bold"},
        ],
        "items": [],
        "show_account_links": True,
    },
    "center": {
        "right_text": "Ücretsiz Kargo Fırsatları",
        "right_link": "/sayfa/kargo-ve-teslimat",
    },
    "mobile": {
        "mode": "same",   # same: hamburger menüyle aynı | manual: items
        "items": [],
    },
}

_MAX_DEPTH = 3
_MAX_ITEMS = 60
_STYLES = ("normal", "bold", "sale")


def _s(v, n=300):
    return str(v or "").strip()[:n]


def _clean_items(items, depth=1):
    out = []
    for i, it in enumerate(items or []):
        if not isinstance(it, dict) or not _s(it.get("label")):
            continue
        link = _s(it.get("link")) or "/"
        if re.match(r"^\s*javascript:", link, re.I):
            link = "/"
        node = {
            "id": _s(it.get("id"), 40) or f"m{depth}-{i}",
            "label": _s(it.get("label"), 60),
            "link": link,
            "icon": _s(it.get("icon"), 60),
            "style": it.get("style") if it.get("style") in _STYLES else "normal",
        }
        if it.get("special") == "account":
            node["special"] = "account"
        img = _s(it.get("image"), 500)
        if img and not re.match(r"^\s*javascript:", img, re.I):
            node["image"] = img   # dikey menü açılır panel arka plan görseli (şablon megamenu-2.png)
        if depth < _MAX_DEPTH:
            kids = _clean_items(it.get("children"), depth + 1)
            if kids:
                node["children"] = kids
        out.append(node)
        if len(out) >= _MAX_ITEMS:
            break
    return out


def _clean_group(key, data):
    d = data if isinstance(data, dict) else {}
    base = DEFAULTS[key]
    if key == "topbar":
        return {"welcome": _s(d.get("welcome"), 120), "items": _clean_items(d.get("items"), _MAX_DEPTH)}
    if key == "departments":
        try:
            mx = int(d.get("max_roots") or base["max_roots"])
        except (TypeError, ValueError):
            mx = base["max_roots"]
        return {"mode": "manual" if d.get("mode") == "manual" else "auto", "max_roots": max(4, min(30, mx)),
                "quick": _clean_items(d.get("quick"), _MAX_DEPTH), "items": _clean_items(d.get("items"))}
    if key == "hamburger":
        return {"mode": "manual" if d.get("mode") == "manual" else "auto",
                "quick": _clean_items(d.get("quick"), _MAX_DEPTH), "items": _clean_items(d.get("items")),
                "show_account_links": d.get("show_account_links") is not False}
    if key == "center":
        return {"right_text": _s(d.get("right_text"), 80), "right_link": _s(d.get("right_link")) or "/"}
    if key == "mobile":
        return {"mode": "manual" if d.get("mode") == "manual" else "same", "items": _clean_items(d.get("items"))}
    raise HTTPException(status_code=404, detail="Bilinmeyen menü grubu")


async def _members_only_slugs():
    try:
        from .products import _members_only_cat_ids
        mo = await _members_only_cat_ids()
    except Exception:
        return set()
    slugs = set()
    if mo:
        async for c in db.categories.find({"id": {"$in": list(mo)}}, {"_id": 0, "slug": 1, "slug_aliases": 1}):
            if c.get("slug"):
                slugs.add(str(c["slug"]).lower())
            for a in (c.get("slug_aliases") or []):
                slugs.add(str(a).lower())
    return slugs


def _link_slug(link):
    m = re.search(r"[?&]kategori=([^&#]+)", str(link or ""))
    if m:
        return m.group(1).lower()
    seg = [x for x in str(link or "").split("?")[0].split("#")[0].split("/") if x]
    return (seg[-1] if seg else "").lower()


def _filter(items, blocked):
    out = []
    for it in items or []:
        if _link_slug(it.get("link")) in blocked:
            continue
        it = dict(it)
        if it.get("children"):
            it["children"] = _filter(it["children"], blocked)
        out.append(it)
    return out


def _link_url(v):
    return (v or {}).get("url") if isinstance(v, dict) else str(v or "")


async def _site_design_overlay(out: dict):
    """Sayfa Tasarımı v2: üst bar metni/bağlantıları ve orta menü sağ yazısı artık site_design'da
    (Genel Alanlar). Eski uç bir sürüm boyunca yeni belgeden okur (SPEC §6.2/6)."""
    try:
        sd = await db.settings.find_one({"id": "site_design"}, {"_id": 0}) or {}
        pub = sd.get("published") if isinstance(sd.get("published"), dict) else {}
        tb = pub.get("site_topbar")
        if isinstance(tb, dict):
            out["topbar"]["welcome"] = str(tb.get("welcome_text") or "")
            items = []
            for i, it in enumerate(tb.get("right_items") or []):
                if not isinstance(it, dict) or not it.get("label") or it.get("_hidden"):
                    continue
                node = {"id": str(it.get("_id") or f"tb-{i}"), "label": it["label"], "link": _link_url(it.get("link")) or "/",
                        "icon": ((it.get("icon") or {}).get("icon") if isinstance(it.get("icon"), dict) else "") or "", "style": "normal"}
                if it.get("special") == "account":
                    node["special"] = "account"
                items.append(node)
            out["topbar"]["items"] = items
        sm = pub.get("site_secondary_menu")
        if isinstance(sm, dict):
            out["center"]["right_text"] = str(sm.get("right_text") or "")
            out["center"]["right_link"] = _link_url(sm.get("right_link")) or "/"
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[site-menus] site_design okunamadı: {e}")


async def _site_design_write(group: str, clean: dict):
    """Menü Yönetimi'nden üst bar / orta menü kaydı → site_design yayın + varsa taslak (aynı anda)."""
    if group == "topbar":
        key, val = "site_topbar", {"welcome_text": clean.get("welcome", ""), "right_items": [
            {"_id": it.get("id"), "label": it.get("label"), "icon": {"icon": it.get("icon") or ""},
             "link": {"kind": "url", "url": it.get("link") or "/", "new_tab": False},
             "special": it.get("special") or "", "guest_text": "Üye Ol veya Giriş Yap" if it.get("special") == "account" else ""}
            for it in clean.get("items") or []]}
    elif group == "center":
        key, val = "site_secondary_menu", {"right_text": clean.get("right_text", ""),
                                           "right_link": {"kind": "url", "url": clean.get("right_link") or "/", "new_tab": False}}
    else:
        return
    try:
        sd = await db.settings.find_one({"id": "site_design"}, {"_id": 0}) or {}
        pub = sd.get("published") if isinstance(sd.get("published"), dict) else {}
        pub[key] = {**(pub.get(key) or {}), **val}
        await db.settings.update_one({"id": "site_design"}, {"$set": {"published": pub}}, upsert=True)
        for lid in ("home:published", "home:draft"):
            doc = await db.page_layouts.find_one({"id": lid}, {"_id": 0, "global": 1})
            if doc is not None:
                g = doc.get("global") or {}
                g[key] = {**(g.get(key) or {}), **val}
                await db.page_layouts.update_one({"id": lid}, {"$set": {"global": g}})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[site-menus] site_design yazılamadı: {e}")


@router.get("")
async def get_site_menus(request: Request):
    """Tüm menü grupları (public). Kayıtsız grup varsayılanla döner. Misafire üyelere özel
    kategori bağlantıları gösterilmez."""
    doc = await db.settings.find_one({"id": "site_menus"}, {"_id": 0}) or {}
    out = {}
    for k in GROUP_KEYS:
        g = doc.get(k)
        out[k] = _clean_group(k, g) if isinstance(g, dict) else _clean_group(k, DEFAULTS[k])
        out[k]["customized"] = isinstance(g, dict)
    await _site_design_overlay(out)
    try:
        from .products import request_is_member
        if not request_is_member(request):
            blocked = await _members_only_slugs()
            if blocked:
                for k in GROUP_KEYS:
                    for f in ("items", "quick"):
                        if f in out[k]:
                            out[k][f] = _filter(out[k][f], blocked)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[site-menus] üyelere özel süzgeç: {e}")
    return out


@router.put("/{group}")
async def save_site_menu(group: str, payload: dict, request: Request,
                         current_user: dict = Depends(require_admin)):
    if group not in GROUP_KEYS:
        raise HTTPException(status_code=404, detail="Bilinmeyen menü grubu")
    clean = _clean_group(group, payload)
    before = await db.settings.find_one({"id": "site_menus"}, {"_id": 0}) or {}
    await db.settings.update_one(
        {"id": "site_menus"},
        {"$set": {group: clean, "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": current_user.get("email") or current_user.get("id")}},
        upsert=True,
    )
    await _site_design_write(group, clean)
    await record_admin_audit(db, action="site_menu.update", entity_type="content", entity_id=f"site_menus.{group}",
                             before={group: before.get(group)}, after={group: clean},
                             current_user=current_user, request=request, source="content.menu")
    return {"success": True, group: clean}


@router.delete("/{group}")
async def reset_site_menu(group: str, request: Request, current_user: dict = Depends(require_admin)):
    """Grubu varsayılana döndürür."""
    if group not in GROUP_KEYS:
        raise HTTPException(status_code=404, detail="Bilinmeyen menü grubu")
    await db.settings.update_one({"id": "site_menus"}, {"$unset": {group: ""}}, upsert=True)
    await record_admin_audit(db, action="site_menu.reset", entity_type="content", entity_id=f"site_menus.{group}",
                             before={}, after={}, current_user=current_user, request=request, source="content.menu")
    return {"success": True, group: _clean_group(group, DEFAULTS[group])}
