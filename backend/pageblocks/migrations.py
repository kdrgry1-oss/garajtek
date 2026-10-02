"""Eski `page_blocks` satırları → v2 şema blokları (SPEC §6.2) ve eski menü/footer verisi → site_design.

Saf dönüştürücüler (`migrate_block`, `migrate_site_design`) belirlenimcidir: aynı girdi → aynı çıktı
(repeater `_id`'leri eski blok id'sinden türetilir). `migrate_block` zaten v2 olan bloğa dokunmaz.
`run_migration(db)` uygulama başında bir kez çalışır (`settings.migrations.page_design_v2` anahtarı):
  1. yedek: tüm page_blocks + site_menus + footer → page_layout_revisions rev 0 ("Geçiş öncesi yedek")
  2. her sayfa için dönüştür → page_layouts "<sayfa>:published" (rev 1) + revizyon
  3. page_blocks aynasını yeni biçimle yeniler; site_design belgesini yazar
Geri dönüş: POST /api/page-design/home/revisions/0/restore (rev 0 ham bloklar yeniden dönüştürülerek taslağa yüklenir).
"""
from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from html import escape

from . import (
    DEFAULT_TZ, SCHEMA_VERSION, TOP_BAR_TYPES, all_fields, assign_item_ids, deep_merge, default_global,
    default_home, default_settings, get_schema, parse_dt, template_default_hash, validate_global, validate_settings,
)

MIGRATION_KEY = "page_design_v2"
LAYOUT_TAG = "electro_home_v1"
_OLD_DEFAULT = {("hero_slider", "Ana Slider"), ("full_banner", "Tek Banner"), ("half_banners", "İki Banner"),
                ("product_slider", "Yeni Sezon"), ("instashop", "Atölyemizden")}
_SRC = {"popular": "best_sellers", "favorites": "best_sellers", "featured": "featured", "discounted": "discounted",
        "newest": "newest", "category": "category", "manual": "manual", "best_sellers": "best_sellers",
        "top_rated": "top_rated"}
_RESERVED = {"sale", "tum-urunler", "en-yeniler", "sepet", "arama", "hesabim", "sayfa", "kampanya", "urun",
             "favoriler", "karsilastir", "siparis-takip", "giris", "odeme", "iade-islemleri"}


def _pristine(block: dict) -> bool:
    """Eski home_layout._pristine tanımı: hiç düzenlenmemiş varsayılan iskelet blok."""
    if block.get("updated_at") or (block.get("images") or []):
        return False
    st = block.get("settings") or {}
    if st.get("product_ids") or st.get("text") or st.get("captions"):
        return False
    if st.get("layout") == LAYOUT_TAG:
        return True
    return (block.get("type"), block.get("title")) in _OLD_DEFAULT


def _t(v) -> str:
    return str(v or "").strip()


def _html(v) -> str:
    """Düz metni rich_text'e güvenle taşır (satır sonu → <br>)."""
    return escape(_t(v), quote=False).replace("\n", "<br>")


def to_link(url, cat_slugs=None) -> dict:
    u = _t(url)
    if not u:
        return {"kind": "none", "url": "", "new_tab": False}
    m = re.match(r"^/([a-z0-9\-]+)/?$", u)
    if m and cat_slugs and m.group(1) in cat_slugs and m.group(1) not in _RESERVED:
        return {"kind": "category", "url": u, "slug": m.group(1), "new_tab": False}
    if u.startswith("/arama?q="):
        return {"kind": "search", "url": u, "new_tab": False}
    return {"kind": "url", "url": u, "new_tab": bool(re.match(r"^https?://", u))}


def to_image(url, dims=None, alt=""):
    u = _t(url)
    if not u:
        return None
    out = {"url": u, "alt": _t(alt)}
    if isinstance(dims, (list, tuple)) and len(dims) == 2:
        try:
            w, h = int(dims[0]), int(dims[1])
            if w > 0 and h > 0:
                out["w"], out["h"] = w, h
        except (TypeError, ValueError):
            pass
    return out


def to_source(kind, limit, category_ids=None, product_ids=None):
    k = _SRC.get(_t(kind) or "newest", "newest")
    pids = [str(x) for x in (product_ids or []) if x]
    cids = [str(x) for x in (category_ids or []) if x]
    if k == "category" and not cids:
        k = "newest"
    if pids and k not in ("category",) and _t(kind) in ("", "manual"):
        k = "manual"
    return {"kind": k, "product_ids": pids, "category_ids": cids, "include_children": True, "tag": "",
            "brand_ids": [], "limit": int(limit or 6), "sort": "default", "exclude_out_of_stock": False,
            "exclude_ids": [], "fill_with": "none"}


def _fmt_price(p) -> str:
    if p in (None, ""):
        return ""
    if isinstance(p, str) and not re.match(r"^\s*[\d.,]+\s*$", p):
        return p.strip()
    t = str(p).strip()
    if re.match(r"^\d{1,3}(\.\d{3})+(,\d{1,2})?$", t):
        t = t.replace(".", "").replace(",", ".")
    else:
        t = t.replace(",", ".")
    try:
        v = float(t)
    except ValueError:
        return _t(p)
    whole = f"{int(v):,}".replace(",", ".")
    dec = round((v - int(v)) * 100)
    return f"₺{whole}" + (f",{dec:02d}" if dec else "")


def _sched(sc):
    """Eski {start, end, tz} (yerel duvar saati) → v2 {start, end} (tz Europe/Istanbul değilse ofsetli ISO)."""
    if not isinstance(sc, dict) or not (sc.get("start") or sc.get("end")):
        return None
    tz = _t(sc.get("tz")) or DEFAULT_TZ
    out = {}
    for k in ("start", "end"):
        v = _t(sc.get(k))
        if v and tz != DEFAULT_TZ:
            d = parse_dt(v, tz)
            v = d.isoformat(timespec="minutes") if d else v
        out[k] = v
    return out


# ------------------------------------------------------------ tip başına dönüştürücüler
def _hero(b, st, ctx):
    imgs = b.get("images") or []
    links = b.get("links") or []
    caps = st.get("captions") if isinstance(st.get("captions"), list) else []
    mob = st.get("mobile_images") if isinstance(st.get("mobile_images"), list) else []
    dims = st.get("img_dims") if isinstance(st.get("img_dims"), list) else []
    sch = st.get("slide_schedule") if isinstance(st.get("slide_schedule"), list) else []
    n = len(imgs) if imgs else len([c for c in caps if isinstance(c, dict) and any(c.values())])
    out = {}
    if st.get("style"):
        out["_variant"] = {"electro": "v1"}.get(st["style"], "v1")
    car = {}
    if "autoplay" in st:
        car["autoplay"] = bool(st["autoplay"])
    if st.get("interval_ms"):
        car["interval"] = int(st["interval_ms"])
    if car:
        out["carousel"] = car
    if not n:
        return out
    slides = []
    for i in range(n):
        c = caps[i] if i < len(caps) and isinstance(caps[i], dict) else {}
        link = _t(c.get("link")) or (_t(links[i]) if i < len(links) else "")
        bg = to_image(imgs[i] if i < len(imgs) else "", dims[i] if i < len(dims) else None, c.get("title"))
        if bg and i < len(mob) and _t(mob[i]):
            bg["mobile_url"] = _t(mob[i])
        s = {"background": bg, "layout": "price", "pretitle": "",
             "title": _html(c.get("title")), "subtitle": _t(c.get("subtitle") or c.get("eyebrow")),
             "price_prefix": _t(c.get("price_label")), "price": _fmt_price(c.get("price")),
             "button": {"text": _t(c.get("cta")), "style": "primary", "link": to_link(link, ctx.get("cat_slugs"))}}
        if not s["price_prefix"] and s["price"]:
            s["price_prefix"] = "Başlayan fiyatlarla"
        sc = _sched(sch[i] if i < len(sch) else None)
        if sc:
            s["_schedule"] = sc
        slides.append(s)
    out["slides"] = slides
    return out


def _ads(b, st, ctx):
    items = st.get("items") if isinstance(st.get("items"), list) else None
    if items is None:
        return {}
    out = []
    for it in items[:4]:
        if not isinstance(it, dict):
            continue
        pre, strong, post = _t(it.get("pre")), _t(it.get("strong")), _t(it.get("post"))
        if _t(it.get("text")) and not (pre or strong or post):
            text = _t(it.get("text"))
        else:
            line2 = " ".join(x for x in [f"<strong>{escape(strong, quote=False)}</strong>" if strong else "",
                                         escape(post, quote=False)] if x)
            text = "<br>".join(x for x in [escape(pre, quote=False), line2] if x)
        x = {"text": text, "link": to_link(it.get("link"), ctx.get("cat_slugs")),
             "image": to_image(it.get("image")) if isinstance(it.get("image"), str) else it.get("image")}
        if _t(it.get("upto")):
            x.update(action_type="upto", action_value=_t(it.get("upto")), action_prefix="%'ye varan",
                     action_suffix="indirim")
        else:
            x.update(action_type="link", action_text=_t(it.get("cta")) or "Hemen İncele")
        out.append(x)
    return {"items": out}


def _deals(b, st, ctx):
    out = {}
    sp = st.get("special") if isinstance(st.get("special"), dict) else {}
    if sp:
        d = {}
        if sp.get("mode") in ("auto", "manual"):
            d["mode"] = sp["mode"]
        if _t(sp.get("title")):
            d["title"] = _t(sp["title"])
        if _t(sp.get("product_id")):
            d["product"] = _t(sp["product_id"])
        out["deal"] = d
    if isinstance(st.get("tabs"), list):
        out["tabs"] = [{"label": _t(t.get("label")),
                        "source": to_source(t.get("source"), 6, t.get("category_ids"), t.get("product_ids"))}
                       for t in st["tabs"] if isinstance(t, dict) and _t(t.get("label"))]
    return out


def _cat_items(ids, ctx, limit, key="label"):
    names = ctx.get("cat_names") or {}
    return [{key: names.get(str(c), ""), "source": to_source("category", limit, [c])} for c in ids or [] if c]


def _p212(b, st, ctx):
    out = {}
    if "first_label" in st or "first_source" in st:
        out["nav_items"] = [{"label": _t(st.get("first_label")) or "En İyi Fırsatlar",
                             "source": to_source(st.get("first_source") or "discounted", 5)}]
    ids = [c for c in (st.get("category_ids") or []) if c]
    if ids:
        out.setdefault("nav_items", [{"label": "En İyi Fırsatlar", "source": to_source("discounted", 5)}])
        out["nav_items"] += [dict(x, link={"kind": "none", "url": "", "new_tab": False}) for x in _cat_items(ids, ctx, 5)]
        out["nav_auto_categories"] = {"enabled": False}
    if st.get("max_tabs"):
        out.setdefault("nav_auto_categories", {})["max"] = max(0, int(st["max_tabs"]) - 1)
    if _t(b.get("title")):
        out["title"] = _t(b["title"])
    return out


def _best(b, st, ctx):
    out = {}
    hdr = {}
    if _t(b.get("title")):
        hdr["title"] = _t(b["title"])
    if "first_label" in st:
        hdr["pills"] = [{"label": _t(st.get("first_label")) or "İlk 20", "active": True, "as_tab": True,
                         "link": {"kind": "none", "url": "", "new_tab": False}}]
    ids = [c for c in (st.get("category_ids") or []) if c]
    if ids:
        hdr.setdefault("pills", [{"label": "İlk 20", "active": True, "as_tab": True,
                                  "link": {"kind": "none", "url": "", "new_tab": False}}])
        hdr["pills"] += [{"label": x["label"], "active": False, "as_tab": True,
                          "link": {"kind": "none", "url": "", "new_tab": False}, "source": dict(x["source"], limit=12)}
                         for x in _cat_items(ids, ctx, 12)]
        out["pills_auto_categories"] = {"enabled": False}
    if st.get("max_tabs"):
        out.setdefault("pills_auto_categories", {})["max"] = int(st["max_tabs"])
    if hdr:
        out["header"] = hdr
    return out


def _slider(b, st, ctx):
    out = {}
    ids = st.get("product_ids") or []
    src = st.get("source") or ("manual" if ids else "newest")
    if any(k in st for k in ("source", "limit", "category_ids", "product_ids")):
        out["source"] = to_source(src, st.get("limit") or 14, st.get("category_ids"), ids)
    hdr = {}
    if _t(b.get("title")):
        hdr["title"] = _t(b["title"])
    if _t(st.get("cta_link")):
        hdr["link"] = {"label": _t(st.get("cta_label")) or "Tümünü gör", "link": to_link(st["cta_link"], ctx.get("cat_slugs"))}
    if hdr:
        out["header"] = hdr
    if _t(st.get("bg_color")):
        out["_section"] = {"background": _t(st["bg_color"])}
    return out


def _images_items(b, st, ctx, item_key="image", extra=None):
    imgs = b.get("images") or []
    links = b.get("links") or []
    dims = st.get("img_dims") if isinstance(st.get("img_dims"), list) else []
    out = []
    for i, u in enumerate(imgs):
        if not _t(u):
            continue
        it = {item_key: to_image(u, dims[i] if i < len(dims) else None, b.get("title")),
              "link": to_link(links[i] if i < len(links) else "", ctx.get("cat_slugs"))}
        if extra:
            it.update(extra)
        out.append(it)
    return out


def _full(b, st, ctx):
    imgs = b.get("images") or []
    if not imgs:
        return {}
    dims = st.get("img_dims") if isinstance(st.get("img_dims"), list) else []
    links = b.get("links") or []
    return {"image": to_image(imgs[0], dims[0] if dims else None, b.get("title")),
            "link": to_link(links[0] if links else "", ctx.get("cat_slugs"))}


def _half(b, st, ctx):
    items = _images_items(b, st, ctx, extra={"alt": _t(b.get("title"))})
    return {"items": items} if items else {}


def _insta(b, st, ctx):
    out = {}
    if _t(b.get("title")):
        out["title"] = _t(b["title"])
    items = _images_items(b, st, ctx, extra={"alt": ""})
    if items:
        out["items"] = items
    return out


def _brands(b, st, ctx):
    items = _images_items(b, st, ctx, item_key="logo", extra={"name": ""})
    for it in items:
        q = re.match(r"^/arama\?q=(.+)$", it["link"].get("url") or "")
        if q:
            from urllib.parse import unquote_plus
            it["name"] = unquote_plus(q.group(1))
    return {"source": "manual", "brands": items} if items else {}


def _columns(b, st, ctx):
    cols = st.get("columns") if isinstance(st.get("columns"), list) else None
    if cols is None:
        return {}
    return {"columns": [{"title": _t(c.get("title")),
                         "source": to_source(c.get("source") or "featured", 3, c.get("category_ids"), c.get("product_ids"))}
                        for c in cols if isinstance(c, dict)]}


def _text(b, st, ctx):
    out = {}
    if _t(b.get("title")):
        out["title"] = _t(b["title"])
    if _t(st.get("text")):
        out["body"] = _html(st["text"])
    if _t(st.get("html")):
        out["legacy_html"] = st["html"]
    imgs, links = b.get("images") or [], b.get("links") or []
    if imgs and _t(imgs[0]):
        out["image"] = to_image(imgs[0], None, b.get("title"))
    if links and _t(links[0]):
        out["link"] = to_link(links[0], ctx.get("cat_slugs"))
    return out


def _video(b, st, ctx):
    out = {}
    if _t(st.get("video_url")):
        out["video"] = {"url": _t(st["video_url"]), "alt": ""}
    imgs, links = b.get("images") or [], b.get("links") or []
    if imgs and _t(imgs[0]):
        out["poster"] = to_image(imgs[0], None, b.get("title"))
    if links and _t(links[0]):
        out["button"] = {"link": to_link(links[0], ctx.get("cat_slugs"))}
    if _t(b.get("title")):
        out["title"] = _t(b["title"])
    return out


def _rotating(b, st, ctx):
    out = {}
    if isinstance(st.get("texts"), list):
        out["messages"] = [{"text": _t(x), "link": {"kind": "none", "url": "", "new_tab": False}}
                           for x in st["texts"] if _t(x)]
    if st.get("interval"):
        try:
            out["interval"] = int(float(st["interval"]) * 1000)
        except (TypeError, ValueError):
            pass
    if _t(st.get("bg_color")):
        out["background"] = _t(st["bg_color"])
    if _t(st.get("text_color")):
        out["text_color"] = _t(st["text_color"])
    return out


def _countdown_bar(b, st, ctx):
    out = {}
    if _t(st.get("left_text")):
        out["text"] = "\n".join(x.strip() for x in re.split(r"\n|\|", st["left_text"]) if x.strip())
    cd = {}
    if _t(st.get("timer_label")):
        cd["heading"] = _t(st["timer_label"])
    if _t(st.get("end_at")):
        cd["end"] = _t(st["end_at"])
    if _t(st.get("fallback_text")):
        cd["expired_text"] = _t(st["fallback_text"])
        cd["on_expire"] = "show_text"
    if cd:
        out["countdown"] = cd
    if _t(st.get("start_at")) and not _t(st.get("fallback_text")):
        out["_visibility"] = {"schedule": {"start": _t(st["start_at"]), "end": ""}}
    if _t(st.get("bg_color")):
        out["background"] = _t(st["bg_color"])
    if _t(st.get("text_color")):
        out["text_color"] = _t(st["text_color"])
    return out


CONVERTERS = {
    "hero_slider": _hero, "ads_block": _ads, "deals_tabs": _deals, "product_grid_212": _p212, "best_sellers": _best,
    "product_slider": _slider, "full_banner": _full, "half_banners": _half, "instashop": _insta,
    "brands_carousel": _brands, "product_columns": _columns, "text_block": _text, "video_banner": _video,
    "rotating_text": _rotating, "countdown_bar": _countdown_bar,
}


def migrate_block(old: dict, ctx: dict | None = None) -> dict:
    """Eski page_blocks satırı → v2 blok. Zaten v2 ise (settings._v == 2) olduğu gibi döner."""
    ctx = ctx or {}
    b = {k: v for k, v in (old or {}).items() if k != "_id"}
    st = b.get("settings") if isinstance(b.get("settings"), dict) else {}
    bid = str(b.get("id") or "")
    base = {"id": bid, "type": str(b.get("type") or ""), "title": _t(b.get("title")),
            "is_active": b.get("is_active") is not False, "page": b.get("page") or "home"}
    for k in ("created_at", "updated_at", "updated_by"):
        if b.get(k):
            base[k] = b[k]
    if st.get("_v") == SCHEMA_VERSION or st.get("_legacy"):
        return {**base, "settings": st, **({"template_default_hash": b["template_default_hash"]}
                                            if b.get("template_default_hash") else {})}
    key = base["type"]
    schema = get_schema(key)
    if not schema or schema.get("scope") == "global":
        legacy = copy.deepcopy(b)
        return {**base, "settings": {"_legacy": True, "_legacy_source": legacy}}
    conv = {} if _pristine(b) else (CONVERTERS.get(key) or (lambda *_: {}))(b, st, ctx)
    variant = conv.pop("_variant", None)
    vis = {}
    sd, sm = b.get("show_desktop"), b.get("show_mobile")
    if sd is not None or sm is not None:
        vis.update(desktop=sd is not False, tablet=sd is not False, mobile=sm is not False)
    sc = _sched(st.get("schedule"))
    if sc:
        vis["schedule"] = sc
    if vis:
        conv["_visibility"] = deep_merge(conv.get("_visibility") or {}, vis)
    settings = deep_merge(default_settings(key, variant), conv)
    if st.get("demo_filled"):
        settings["_demo"] = True
    assign_item_ids(all_fields(schema), settings, seed=f"mig:{bid}")
    clean, errors, _w = validate_settings(key, settings, block_label=base["title"] or schema.get("title", key))
    if errors:
        clean["_migration_errors"] = [f"{e['label']}: {e['message']}" for e in errors][:50]
    if st.get("demo_filled"):
        clean["_demo"] = True
    return {**base, "settings": clean, "template_default_hash": template_default_hash(key, clean.get("_variant"))}


# ------------------------------------------------------------ global alanlar
def _menu_items(items):
    out = []
    for it in items or []:
        if not isinstance(it, dict) or not _t(it.get("label")):
            continue
        out.append({"label": _t(it["label"]), "icon": {"icon": _t(it.get("icon"))},
                    "link": to_link(it.get("link") or "/"), "special": "account" if it.get("special") == "account" else "",
                    "guest_text": "Üye Ol veya Giriş Yap" if it.get("special") == "account" else ""})
    return out


def migrate_site_design(site_menus: dict | None, footer: dict | None) -> dict:
    """Eski Menü Yönetimi metin alanları + Footer Tasarımı → site_design global (yönetici değeri kazanır)."""
    g = default_global()
    sm = site_menus if isinstance(site_menus, dict) else {}
    tb = sm.get("topbar") if isinstance(sm.get("topbar"), dict) else None
    if tb:
        if _t(tb.get("welcome")):
            g["site_topbar"]["welcome_text"] = _t(tb["welcome"])
        if isinstance(tb.get("items"), list):
            g["site_topbar"]["right_items"] = _menu_items(tb["items"])
    ce = sm.get("center") if isinstance(sm.get("center"), dict) else None
    if ce:
        if "right_text" in ce:
            g["site_secondary_menu"]["right_text"] = _t(ce.get("right_text"))
        if _t(ce.get("right_link")):
            g["site_secondary_menu"]["right_link"] = to_link(ce["right_link"])
    ft = footer if isinstance(footer, dict) else None
    if ft:
        cols = []
        for c in ft.get("columns") or []:
            if not isinstance(c, dict):
                continue
            links = [{"label": _t(x.get("label")), "link": to_link(x.get("to") or x.get("link") or "/")}
                     for x in (c.get("links") or []) if isinstance(x, dict) and _t(x.get("label"))]
            links += [{"label": _t(x), "link": {"kind": "none", "url": "", "new_tab": False}}
                      for x in (c.get("static") or []) if _t(x) and "{" not in _t(x)]
            if links or _t(c.get("title")):
                cols.append({"title": _t(c.get("title")), "links": links})
        if cols:
            g["site_footer_links"]["columns"] = cols[:4]
        if ft.get("mode") == "html" and _t(ft.get("custom_html")):
            g["site_footer_links"]["mode"] = "html"
            g["site_footer_links"]["custom_html"] = ft["custom_html"]
        nl = ft.get("newsletter") if isinstance(ft.get("newsletter"), dict) else {}
        if _t(nl.get("title")):
            g["site_newsletter"]["title"] = _t(nl["title"])
        if _t(nl.get("description")):
            g["site_newsletter"]["marketing_text"] = _html(nl["description"])
        if _t(nl.get("placeholder")):
            g["site_newsletter"]["placeholder"] = _t(nl["placeholder"])
        soc = ft.get("social") if isinstance(ft.get("social"), dict) else {}
        social = [{"network": k, "url": _t(v)} for k, v in soc.items()
                  if _t(v) and "{" not in _t(v) and k in ("facebook", "instagram", "twitter", "youtube", "tiktok", "linkedin", "pinterest")]
        if social:
            g["site_footer_contact"]["social"] = social
        if _t(ft.get("slogan")):
            g["site_footer_contact"]["slogan"] = _t(ft["slogan"])
        if _t(ft.get("copyright")):
            g["site_footer_bottom"]["copyright"] = _html(ft["copyright"]).replace("{year}", "{yıl}").replace("{store_name}", "{mağaza}")
        if _t(ft.get("payment_band_url")):
            g["site_footer_bottom"]["payment_mode"] = "band_image"
            g["site_footer_bottom"]["payment_band_image"] = {"url": _t(ft["payment_band_url"]), "alt": "Ödeme yöntemleri"}
    for k, v in g.items():
        assign_item_ids(all_fields(get_schema(k)), v, seed=f"mig:global:{k}")
    clean, _e, _w = validate_global(g)
    for k, v in clean.items():
        assign_item_ids(all_fields(get_schema(k)), v, seed=f"mig:global:{k}")
    return clean


# ------------------------------------------------------------ çalışma
async def _category_ctx(db) -> dict:
    names, slugs = {}, set()
    try:
        async for c in db.categories.find({}, {"_id": 0, "id": 1, "name": 1, "slug": 1}):
            if c.get("id"):
                names[str(c["id"])] = c.get("name") or ""
            if c.get("slug"):
                slugs.add(str(c["slug"]))
    except Exception:  # noqa: BLE001
        pass
    return {"cat_names": names, "cat_slugs": slugs}


def migrate_page(rows: list, ctx: dict, page: str = "home") -> list:
    rows = sorted([r for r in rows if isinstance(r, dict)], key=lambda r: (r.get("sort_order") or 0))
    blocks = [migrate_block(r, ctx) for r in rows]
    if page == "home" and not [b for b in blocks if b["type"] not in TOP_BAR_TYPES]:
        top = [b for b in blocks if b["type"] in TOP_BAR_TYPES]
        blocks = top + default_home(seed="mig:default-home")
    for i, b in enumerate(blocks, start=1):
        b["sort_order"] = i
        b["page"] = page
    return blocks


async def run_migration(db, *, force: bool = False) -> dict | None:
    """Tek seferlik canlı veritabanı geçişi (idempotent). Yapıldıysa özet, zaten yapılmışsa None."""
    mig = await db.settings.find_one({"id": "migrations"}, {"_id": 0}) or {}
    if mig.get(MIGRATION_KEY) and not force:
        return None
    now = datetime.now(timezone.utc).isoformat()
    # kilit (aynı anda iki işçi): yalnız kilidi alan devam eder
    held = mig.get(f"{MIGRATION_KEY}_lock")
    stale = bool(held) and (datetime.now(timezone.utc) - (parse_dt(held) or datetime.now(timezone.utc))).total_seconds() > 600
    if not mig:
        await db.settings.insert_one({"id": "migrations", f"{MIGRATION_KEY}_lock": now})
    else:
        q = {"id": "migrations"} if (stale or force) else {"id": "migrations", f"{MIGRATION_KEY}_lock": {"$exists": False}}
        lock = await db.settings.update_one(q, {"$set": {f"{MIGRATION_KEY}_lock": now}})
        if not lock.matched_count:
            return None
    try:
        rows = await db.page_blocks.find({}, {"_id": 0}).to_list(None)
        site_menus = await db.settings.find_one({"id": "site_menus"}, {"_id": 0})
        footer = await db.settings.find_one({"id": "footer"}, {"_id": 0})
        ctx = await _category_ctx(db)
        pages = sorted({(r.get("page") or "home") for r in rows} | {"home"})
        summary = {"at": now, "pages": {}, "legacy": 0, "errors": 0}
        global_ = migrate_site_design(site_menus, footer)
        for page in pages:
            prow = [r for r in rows if (r.get("page") or "home") == page]
            if not await db.page_layout_revisions.find_one({"id": f"{page}:rev:0"}):
                await db.page_layout_revisions.insert_one({
                    "id": f"{page}:rev:0", "page": page, "rev": 0, "raw": True, "blocks": copy.deepcopy(prow),
                    "global": {"site_menus": site_menus, "footer": footer} if page == "home" else {},
                    "published_at": now, "published_by": "geçiş", "summary": "Geçiş öncesi yedek"})
            if await db.page_layouts.find_one({"id": f"{page}:published"}) and not force:
                continue
            blocks = migrate_page(prow, ctx, page)
            summary["pages"][page] = len(blocks)
            summary["legacy"] += sum(1 for b in blocks if b["settings"].get("_legacy"))
            summary["errors"] += sum(1 for b in blocks if b["settings"].get("_migration_errors"))
            doc = {"id": f"{page}:published", "page": page, "rev": 1, "blocks": blocks,
                   "global": global_ if page == "home" else {}, "updated_at": now, "updated_by": "geçiş",
                   "published_at": now, "published_by": "geçiş"}
            await db.page_layouts.replace_one({"id": doc["id"]}, doc, upsert=True)
            await db.page_layout_revisions.replace_one({"id": f"{page}:rev:1"}, {
                "id": f"{page}:rev:1", "page": page, "rev": 1, "blocks": blocks, "global": doc["global"],
                "published_at": now, "published_by": "geçiş", "summary": "Yeni sayfa tasarımına geçiş"}, upsert=True)
            await db.page_blocks.delete_many({"page": page} if page != "home" else {"$or": [{"page": "home"}, {"page": None}, {"page": {"$exists": False}}]})
            for b in blocks:
                await db.page_blocks.insert_one({**copy.deepcopy(b), "page": page})
        if not await db.settings.find_one({"id": "site_design"}):
            await db.settings.insert_one({"id": "site_design", "rev": 1, "published": global_, "updated_at": now})
        await db.settings.update_one({"id": "migrations"}, {"$set": {MIGRATION_KEY: summary},
                                                            "$unset": {f"{MIGRATION_KEY}_lock": ""}}, upsert=True)
        return summary
    except Exception:
        await db.settings.update_one({"id": "migrations"}, {"$unset": {f"{MIGRATION_KEY}_lock": ""}})
        raise
