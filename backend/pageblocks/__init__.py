"""Sayfa Tasarımı blok şemaları — yükleyici, doğrulayıcı, varsayılan üretici, zamanlama süzgeci.

Tek doğruluk kaynağı: frontend/src/components/pageblocks/<key>/schema.json + defaults.json.
Buradaki schemas/ klasörü `scripts/sync_block_schemas.py` ile üretilen BAYT-EŞİT kopyadır
(elle düzenlenmez; backend/tests/test_block_schemas_sync.py doğrular). Bkz. docs/page-design/SPEC.md §2.

Ana API:
  load_schemas()                 → {key: schema}  (bloklar + global alanlar)
  default_settings(key, variant) → defaults.json + varyant yaması + ortak grup varsayılanları
  with_defaults(key, settings)   → eksik alanları (repeater öğeleri dahil) varsayılandan doldurur
  validate_block(block)          → (temiz_blok, hatalar, uyarılar)   — Türkçe mesajlar
  validate_global(global_)       → (temiz_global, hatalar, uyarılar)
  apply_schedule(blocks, now)    → yayında olmayan blok/öğeleri süzer (öğe düzeyinde _schedule/_hidden)
  default_home()                 → şablon v1.0 ana sayfa düzeni (SPEC §6.1)
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")
DEFAULT_TZ = "Europe/Istanbul"
SCHEMA_VERSION = 2

# Şablon v1.0 ana sayfa sırası (SPEC §6.1)
DEFAULT_HOME = [
    ("hero_slider", "v1", "Ana Slider"),
    ("ads_block", "v1", "Reklam Kutuları"),
    ("deals_tabs", "v1", "Özel Teklif ve Ürün Sekmeleri"),
    ("product_grid_212", "2_1_2", "Kategori Fırsatları (2-1-2)"),
    ("best_sellers", "", "Çok Satanlar"),
    ("full_banner", "image", "Tam Genişlik Banner"),
    ("product_slider", "", "Yeni Eklenenler"),
    ("brands_carousel", "", "Markalar"),
    ("product_columns", "", "Alt Ürün Sütunları"),
]

TOP_BAR_TYPES = {"rotating_text", "countdown_bar"}
ROOT_META_KEYS = {"_v", "_variant", "_legacy", "_migration_errors", "_demo"}
SRC_KINDS = ("manual", "category", "discounted", "newest", "best_sellers", "featured", "top_rated", "tag", "brand",
             "recently_viewed")
SRC_SORTS = ("default", "newest", "price_asc", "price_desc", "popular", "discount_desc", "name_asc", "random_daily")
LINK_KINDS = ("category", "product", "page", "brand", "search", "url", "none")
_LEGACY_SOURCE = {"popular": "best_sellers", "favorites": "best_sellers", "new": "newest", "sale": "discounted"}


class UnknownBlockType(ValueError):
    pass


# ------------------------------------------------------------------ yükleme
_CACHE: dict = {}


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schemas(force: bool = False) -> dict:
    """Tüm şemalar (bloklar + global). Süreç başına önbellekli."""
    if _CACHE.get("schemas") is not None and not force:
        return _CACHE["schemas"]
    schemas, defaults = {}, {}
    common = {"defaults": {}}
    if os.path.isdir(SCHEMA_DIR):
        for name in sorted(os.listdir(SCHEMA_DIR)):
            p = os.path.join(SCHEMA_DIR, name)
            if name == "_common.json":
                common = _read_json(p)
            elif name.endswith(".schema.json"):
                s = _read_json(p)
                schemas[s["key"]] = s
            elif name.endswith(".defaults.json"):
                defaults[name[: -len(".defaults.json")]] = _read_json(p)
    _CACHE.update(schemas=schemas, defaults=defaults, common=common)
    return schemas


def get_schema(key: str) -> dict | None:
    return load_schemas().get(key)


def block_schemas() -> dict:
    return {k: s for k, s in load_schemas().items() if s.get("scope") != "global"}


def global_schemas() -> dict:
    return {k: s for k, s in load_schemas().items() if s.get("scope") == "global"}


def raw_defaults(key: str) -> dict:
    load_schemas()
    return copy.deepcopy(_CACHE["defaults"].get(key) or {})


def common_config() -> dict:
    load_schemas()
    return _CACHE["common"]


def common_fields(schema: dict) -> list:
    cfg = common_config()
    out = []
    for g in schema.get("common") or []:
        for f in (cfg.get(g) or {}).get("fields") or []:
            out.append(dict(f, tab=f.get("tab") or (cfg.get(g) or {}).get("tab")))
    return out


def all_fields(schema: dict) -> list:
    return list(schema.get("fields") or []) + common_fields(schema)


# ------------------------------------------------------------------ yardımcılar
def deep_merge(base, over):
    """`over` kazanır; sözlükler özyinelemeli birleşir, listeler/skalerler değiştirilir.
    Anahtarları tamamen sayısal olan sözlükler (karusel `per_view` kırılım tablosu) bütün olarak değiştirilir —
    yöneticinin sildiği kırılım varsayılandan geri gelmez."""
    if isinstance(over, dict) and over and all(str(k).isdigit() for k in over):
        return copy.deepcopy(over)
    if isinstance(base, dict) and isinstance(over, dict):
        out = {k: copy.deepcopy(v) for k, v in base.items()}
        for k, v in over.items():
            out[k] = deep_merge(out.get(k), v) if k in out else copy.deepcopy(v)
        return out
    return copy.deepcopy(over)


def _common_defaults(schema: dict) -> dict:
    d = copy.deepcopy(common_config().get("defaults") or {})
    keep = {"section": "_section", "visibility": "_visibility", "reveal": "_reveal"}
    d = {v: d[v] for k, v in keep.items() if k in (schema.get("common") or []) and v in d}
    if "_section" in d:
        lay = schema.get("layout") or "container"
        d["_section"]["width"] = "container" if lay == "sidebar" else lay
    return d


def first_variant(schema: dict) -> str:
    vs = schema.get("variants") or []
    return str(vs[0]["value"]) if vs else ""


def default_settings(key: str, variant: str | None = None) -> dict:
    schema = get_schema(key)
    if not schema:
        raise UnknownBlockType(key)
    out = deep_merge(_common_defaults(schema), raw_defaults(key))
    vs = schema.get("variants") or []
    v = variant if variant is not None and any(str(x["value"]) == str(variant) for x in vs) else first_variant(schema)
    for x in vs:
        if str(x["value"]) == str(v) and x.get("defaults_patch"):
            out = deep_merge(out, x["defaults_patch"])
    if schema.get("scope") != "global":
        out["_v"] = SCHEMA_VERSION
        out["_variant"] = v
    return out


def template_default_hash(key: str, variant: str | None = None) -> str:
    raw = json.dumps(default_settings(key, variant), sort_keys=True, ensure_ascii=False)
    return "sha1-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _field_default(field):
    if "default" in field:
        return copy.deepcopy(field["default"])
    t = field.get("type")
    if t == "group":
        return {f["name"]: _field_default(f) for f in field.get("fields") or []}
    return None


def _item_default(field) -> dict:
    base = {f["name"]: _field_default(f) for f in field.get("item_fields") or []}
    base = {k: v for k, v in base.items() if v is not None}
    return deep_merge(base, field.get("item_default") or {})


def _fill(fields, value):
    """Repeater öğelerini item_default ile doldurur (özyinelemeli)."""
    if not isinstance(value, dict):
        return value
    for f in fields or []:
        n = f["name"]
        if n not in value:
            continue
        if f.get("type") == "repeater" and isinstance(value[n], list):
            dflt = _item_default(f)
            value[n] = [_fill(f.get("item_fields"), deep_merge(dflt, it)) if isinstance(it, dict) else it
                        for it in value[n]]
        elif f.get("type") == "group" and isinstance(value[n], dict):
            _fill(f.get("fields"), value[n])
    return value


def with_defaults(key: str, settings: dict | None) -> dict:
    schema = get_schema(key)
    if not schema:
        raise UnknownBlockType(key)
    st = settings if isinstance(settings, dict) else {}
    base = default_settings(key, st.get("_variant"))
    return _fill(all_fields(schema), deep_merge(base, st))


def new_id() -> str:
    return str(uuid.uuid4())


def _det_id(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "garajtek-pd:" + seed))


def assign_item_ids(fields, value, seed: str | None = None):
    """Repeater öğelerine kalıcı `_id` verir (yoksa). seed verilirse belirlenimci (idempotent geçiş)."""
    if not isinstance(value, dict):
        return value
    for f in fields or []:
        n = f["name"]
        v = value.get(n)
        if f.get("type") == "repeater" and isinstance(v, list):
            for i, it in enumerate(v):
                if isinstance(it, dict):
                    if not it.get("_id"):
                        it["_id"] = _det_id(f"{seed}:{n}:{i}") if seed else new_id()
                    assign_item_ids(f.get("item_fields"), it, f"{seed}:{n}:{i}" if seed else None)
        elif f.get("type") == "group" and isinstance(v, dict):
            assign_item_ids(f.get("fields"), v, f"{seed}:{n}" if seed else None)
        elif f.get("type") == "section_header" and isinstance(v, dict) and isinstance(v.get("pills"), list):
            for i, it in enumerate(v["pills"]):
                if isinstance(it, dict) and not it.get("_id"):
                    it["_id"] = _det_id(f"{seed}:{n}:pills:{i}") if seed else new_id()
    return value


def instantiate(key: str, variant: str | None = None, *, title: str | None = None, seed: str | None = None) -> dict:
    """Varsayılanlarla DOLU yeni blok belgesi."""
    schema = get_schema(key)
    if not schema:
        raise UnknownBlockType(key)
    st = with_defaults(key, {"_variant": variant} if variant else {})
    assign_item_ids(all_fields(schema), st, seed)
    return {"id": _det_id(f"{seed}:block") if seed else new_id(), "type": key,
            "title": title if title is not None else schema.get("title", key), "is_active": True, "settings": st,
            "template_default_hash": template_default_hash(key, st.get("_variant"))}


def default_home(seed: str | None = None) -> list:
    out = []
    for i, (key, variant, title) in enumerate(DEFAULT_HOME, start=1):
        b = instantiate(key, variant or None, title=title, seed=f"{seed}:{i}:{key}" if seed else None)
        b["sort_order"] = i
        out.append(b)
    return out


# ------------------------------------------------------------------ temizleyiciler
_SAFE_URL_RE = re.compile(r"^(https?://|mailto:|tel:|/(?!/)|#|\?)", re.I)


def safe_url(u) -> str | None:
    """Güvenli bağlantı → kendisi; tehlikeli (javascript:, data:, //host) → None."""
    s = str(u or "").strip()
    if not s:
        return ""
    if re.match(r"^\s*(javascript|data|vbscript|file):", s, re.I):
        return None
    if _SAFE_URL_RE.match(s):
        return s[:1000]
    if re.match(r"^[a-z0-9][a-z0-9\-._~%!$&'()*+,;=:@/]*$", s, re.I) and ":" not in s.split("/")[0]:
        return "/" + s.lstrip("/")  # "liftler" → "/liftler"
    return None


def safe_image_url(u) -> str | None:
    s = str(u or "").strip()
    if not s:
        return ""
    if re.match(r"^https?://", s, re.I) or (s.startswith("/") and not s.startswith("//")):
        return s[:1000]
    return None


_MARK_TAGS = {"strong": "strong", "b": "strong", "em": "em", "i": "em", "br": "br", "sup": "sup", "sub": "sub",
              "span": "span", "a": "a"}


class _Sanitizer(HTMLParser):
    def __init__(self, allowed: set, strict_html: bool = False):
        super().__init__(convert_charrefs=True)
        self.allowed = allowed
        self.strict_html = strict_html
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip = 0

    def _norm(self, tag):
        if self.strict_html:
            return tag if tag in self.allowed else None
        t = _MARK_TAGS.get(tag)
        if not t:
            return None
        if t == "span" and "span_highlight" not in self.allowed:
            return None
        if t == "a" and "link" not in self.allowed:
            return None
        if t not in ("span", "a") and t not in self.allowed:
            return None
        return t

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "iframe", "object", "template"):
            self.skip += 1
            return
        t = self._norm(tag)
        if not t:
            return
        a = dict(attrs)
        if t == "br":
            self.out.append("<br>")
            return
        if t == "img":
            src = safe_image_url(a.get("src"))
            if src:
                self.out.append(f'<img src="{escape(src)}" alt="{escape(a.get("alt") or "")}">')
            return
        attr = ""
        if t == "span":
            attr = ' class="hl"'
        elif t == "a":
            href = safe_url(a.get("href"))
            if href is None:
                href = "#"
            attr = f' href="{escape(href)}"'
            if a.get("target") == "_blank":
                attr += ' target="_blank" rel="noopener noreferrer"'
        self.out.append(f"<{t}{attr}>")
        self.stack.append(t)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        t = self._norm(tag)
        if t and t not in ("br", "img") and self.stack and self.stack[-1] == t:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "iframe", "object", "template"):
            self.skip = max(0, self.skip - 1)
            return
        t = self._norm(tag)
        if not t or t in ("br", "img"):
            return
        if t in self.stack:
            while self.stack:
                x = self.stack.pop()
                self.out.append(f"</{x}>")
                if x == t:
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(escape(data, quote=False))

    def result(self):
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitize_rich_text(html, marks=None) -> str:
    allowed = set(marks or ["strong", "em", "br", "span_highlight", "sup", "sub", "link"])
    p = _Sanitizer(allowed)
    p.feed(str(html or ""))
    p.close()
    return p.result()


_STRICT_HTML = {"p", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "strong", "b", "em", "i", "br", "a", "img",
                "span", "div", "sup", "sub", "blockquote", "hr", "table", "thead", "tbody", "tr", "td", "th"}


def sanitize_html(html) -> str:
    p = _Sanitizer(_STRICT_HTML, strict_html=True)
    p.feed(str(html or ""))
    p.close()
    return p.result()


# ------------------------------------------------------------------ zaman
def _tz(name=None):
    if not ZoneInfo:
        return timezone.utc
    try:
        return ZoneInfo(str(name or DEFAULT_TZ))
    except Exception:
        return ZoneInfo(DEFAULT_TZ)


def parse_dt(s, tz=None):
    """ISO-8601 (saat dilimli veya yerel duvar saati) → aware datetime. Bozuksa None."""
    t = str(s or "").strip()
    if not t:
        return None
    t = t.replace(" ", "T")
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(t)
    except ValueError:
        try:
            d = datetime.strptime(t[:16], "%Y-%m-%dT%H:%M")
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=_tz(tz))
    return d


def schedule_active(sched, now=None) -> bool:
    """{start, end, tz?} — kural yoksa / bozuksa yayında sayılır. Bitiş dakikası dahildir."""
    if not isinstance(sched, dict):
        return True
    now = now or datetime.now(timezone.utc)
    s = parse_dt(sched.get("start"), sched.get("tz"))
    e = parse_dt(sched.get("end"), sched.get("tz"))
    if s and now < s:
        return False
    if e:
        if len(str(sched.get("end") or "").strip()) <= 16:
            e = e.replace(second=59, microsecond=999999)
        if now > e:
            return False
    return True


def _filter_items(fields, value, now):
    if not isinstance(value, dict):
        return value
    for f in fields or []:
        n = f["name"]
        v = value.get(n)
        if f.get("type") == "repeater" and isinstance(v, list):
            value[n] = [_filter_items(f.get("item_fields"), it, now) for it in v
                        if isinstance(it, dict) and not it.get("_hidden") and schedule_active(it.get("_schedule"), now)]
        elif f.get("type") == "group" and isinstance(v, dict):
            _filter_items(f.get("fields"), v, now)
    return value


# Görselsiz anlamını yitiren tipler: tüm slaytları/öğeleri zamanı geçmişse blok gizlenir.
_EMPTY_HIDES = {"hero_slider": "slides", "half_banners": "items", "instashop": "items"}


def apply_schedule(blocks: list, now=None, *, keep_inactive: bool = False) -> list:
    now = now or datetime.now(timezone.utc)
    out = []
    for b in blocks or []:
        if not isinstance(b, dict):
            continue
        if not keep_inactive and b.get("is_active") is False:
            continue
        st = b.get("settings") if isinstance(b.get("settings"), dict) else {}
        if st.get("_legacy"):
            continue
        if not schedule_active((st.get("_visibility") or {}).get("schedule"), now):
            continue
        schema = get_schema(b.get("type"))
        if not schema:
            continue
        had = {k: len(st.get(k) or []) for k in [_EMPTY_HIDES.get(b.get("type"))] if k}
        st2 = _filter_items(all_fields(schema), copy.deepcopy(st), now)
        for k, n in had.items():
            if n and not (st2.get(k) or []):
                st2 = None
                break
        if st2 is None:
            continue
        out.append({**b, "settings": st2})
    return out


# ------------------------------------------------------------------ doğrulama
class _Ctx:
    def __init__(self, strict: bool):
        self.strict = strict
        self.errors: list[dict] = []
        self.warnings: list[dict] = []
        self.block_label = ""

    def err(self, path, labels, msg):
        self.errors.append({"path": path, "label": " › ".join([x for x in [self.block_label, *labels] if x]),
                            "message": msg})

    def warn(self, path, labels, msg):
        self.warnings.append({"path": path, "label": " › ".join([x for x in [self.block_label, *labels] if x]),
                              "message": msg})


def _is_empty(v):
    return v is None or v == "" or v == [] or v == {} or (isinstance(v, dict) and not (v.get("url") or v.get("id")) and set(v) <= {"url", "alt", "w", "h", "focal", "kind", "new_tab", "label", "slug", "id"})


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    try:
        s = str(v).strip().replace(",", ".")
        return float(s) if "." in s else int(s)
    except (TypeError, ValueError):
        return None


def _clean_link(v, field, path, labels, ctx):
    if v is None or v == "":
        return {"kind": "none", "url": "", "new_tab": False} if v == "" else None
    if isinstance(v, str):
        v = {"kind": "url", "url": v}
    if not isinstance(v, dict):
        ctx.err(path, labels, "Bağlantı biçimi geçersiz.")
        return None
    kind = str(v.get("kind") or "url")
    kinds = field.get("kinds") or LINK_KINDS
    if kind not in LINK_KINDS:
        kind = "url"
    if kind not in kinds and kind not in ("url", "none"):
        ctx.warn(path, labels, f"Bu alanda “{kind}” bağlantı türü desteklenmiyor; özel adres olarak saklandı.")
        kind = "url"
    url = safe_url(v.get("url"))
    if url is None:
        ctx.err(path, labels, "Bağlantı geçersiz (javascript:, data: gibi adresler kabul edilmez).")
        url = ""
    out = {"kind": kind, "url": url, "new_tab": bool(v.get("new_tab"))}
    for k in ("id", "slug", "label"):
        if v.get(k) not in (None, ""):
            out[k] = str(v[k])[:300]
    return out


def _clean_image(v, field, path, labels, ctx):
    if v in (None, "", {}):
        return None
    if isinstance(v, str):
        v = {"url": v}
    if not isinstance(v, dict):
        ctx.err(path, labels, "Görsel biçimi geçersiz.")
        return None
    url = safe_image_url(v.get("url"))
    if url is None:
        ctx.err(path, labels, "Görsel adresi geçersiz (yalnız yüklenen dosyalar veya https adresleri).")
        url = ""
    out = {"url": url, "alt": str(v.get("alt") or "")[:300]}
    for k in ("w", "h"):
        n = _num(v.get(k))
        if n:
            out[k] = int(n)

    def _focal(f):
        if not isinstance(f, dict):
            return None
        x, y = _num(f.get("x")), _num(f.get("y"))
        if x is None or y is None:
            return None
        return {"x": max(0.0, min(1.0, float(x))), "y": max(0.0, min(1.0, float(y)))}

    if _focal(v.get("focal")):
        out["focal"] = _focal(v.get("focal"))
    mu = safe_image_url(v.get("mobile_url"))
    if v.get("mobile_url") and mu is None:
        ctx.err(path + ".mobile_url", labels + ["Mobil görsel"], "Mobil görsel adresi geçersiz.")
    if mu:
        out["mobile_url"] = mu
        if _focal(v.get("mobile_focal")):
            out["mobile_focal"] = _focal(v.get("mobile_focal"))
    if isinstance(v.get("crop"), dict):
        c = {k: _num(v["crop"].get(k)) for k in ("x", "y", "w", "h")}
        if all(x is not None for x in c.values()):
            out["crop"] = c
    if not out["url"] and not out.get("mobile_url"):
        return None
    return out


_COLOR_RE = re.compile(r"^(#[0-9a-f]{3,4}|#[0-9a-f]{6}|#[0-9a-f]{8}|var\(--[a-z0-9-]+\)|transparent|"
                       r"rgba?\(\s*[\d.]+\s*,\s*[\d.]+\s*,\s*[\d.]+\s*(,\s*[\d.]+\s*)?\))$", re.I)


def _clean_source(v, field, path, labels, ctx):
    if isinstance(v, str):
        v = {"kind": v}
    if not isinstance(v, dict):
        ctx.err(path, labels, "Ürün kaynağı geçersiz.")
        v = {}
    kind = _LEGACY_SOURCE.get(str(v.get("kind") or ""), str(v.get("kind") or "featured"))
    allowed = field.get("allowed_kinds") or SRC_KINDS
    if kind not in SRC_KINDS or kind not in allowed:
        ctx.err(path, labels, f"Ürün kaynağı türü geçersiz: {kind}")
        kind = "featured"
    mx = int(field.get("max_limit") or 48)
    lim = _num(v.get("limit"))
    lim = int(lim) if lim else int(field.get("default_limit") or 6)
    lim = max(1, min(mx, lim))

    def _ids(x):
        return [str(i)[:80] for i in (x or []) if str(i or "").strip()] if isinstance(x, list) else []

    out = {"kind": kind, "product_ids": _ids(v.get("product_ids")), "category_ids": _ids(v.get("category_ids")),
           "include_children": v.get("include_children") is not False, "tag": str(v.get("tag") or "")[:80],
           "brand_ids": _ids(v.get("brand_ids")), "limit": lim,
           "sort": v.get("sort") if v.get("sort") in SRC_SORTS else "default",
           "exclude_out_of_stock": bool(v.get("exclude_out_of_stock")), "exclude_ids": _ids(v.get("exclude_ids")),
           "fill_with": v.get("fill_with") if v.get("fill_with") in ("none", "newest", "featured") else "none"}
    if kind == "manual" and not out["product_ids"] and ctx.strict:
        ctx.warn(path, labels, "Elle seçim için ürün eklenmedi.")
    return out


_CAROUSEL_BOOL = ("autoplay", "pause_on_hover", "loop", "rewind", "dots", "drag", "last_active_divider")


def _clean_carousel(v, field, path, labels, ctx):
    v = v if isinstance(v, dict) else {}
    out = {}
    pv = v.get("per_view")
    if isinstance(pv, dict):
        out["per_view"] = {}
        for k, n in pv.items():
            kk, nn = _num(k), _num(n)
            if kk is not None and nn is not None:
                out["per_view"][str(int(kk))] = max(1, min(12, int(nn)))
    for k, lo, hi in (("slides_to_scroll", 1, 12), ("rows", 1, 4), ("gutter", 0, 100), ("interval", 500, 60000),
                      ("speed", 0, 5000)):
        n = _num(v.get(k))
        if n is not None:
            out[k] = max(lo, min(hi, int(n)))
    for k in _CAROUSEL_BOOL:
        if k in v:
            out[k] = bool(v[k])
    if v.get("transition") in ("slide", "fade"):
        out["transition"] = v["transition"]
    if v.get("arrows") in ("none", "header", "side", "outer"):
        out["arrows"] = v["arrows"]
    if v.get("dots") == "mobile":
        out["dots"] = "mobile"
    return out


_UNITS = ("days", "hours", "minutes", "seconds")


def _clean_countdown(v, field, path, labels, ctx):
    v = v if isinstance(v, dict) else {}
    out = {"enabled": v.get("enabled") is not False}
    end = str(v.get("end") or "").strip()
    if end and not parse_dt(end):
        ctx.err(path + ".end", labels + ["Bitiş"], "Geri sayım bitiş tarihi geçersiz.")
        end = ""
    out["end"] = end
    rd = _num(v.get("rolling_days"))
    out["rolling_days"] = max(0, min(365, int(rd))) if rd is not None else 0
    units = [u for u in (v.get("units") or []) if u in _UNITS] if isinstance(v.get("units"), list) else list(_UNITS)
    out["units"] = units or list(_UNITS)
    out["hide_zero_days"] = v.get("hide_zero_days") is not False
    lb = v.get("labels") if isinstance(v.get("labels"), dict) else {}
    out["labels"] = {u: str(lb.get(u) or "")[:20] for u in _UNITS}
    out["heading"] = str(v.get("heading") or "")[:200]
    out["on_expire"] = v.get("on_expire") if v.get("on_expire") in ("hide_block", "hide_timer", "show_text", "zero") else "hide_timer"
    out["expired_text"] = str(v.get("expired_text") or "")[:200]
    out["pad"] = v.get("pad") is not False
    return out


def _clean_section_header(v, field, path, labels, ctx):
    v = v if isinstance(v, dict) else {}
    out = {"title": str(v.get("title") or "")[:200],
           "tag": v.get("tag") if v.get("tag") in ("h2", "h3", "sr-only") else "h2",
           "align": v.get("align") if v.get("align") in ("left", "center") else "left",
           "right": v.get("right") if v.get("right") in ("none", "arrows", "pills", "link", "countdown") else "none",
           "underline": v.get("underline") is not False}
    pills = []
    for i, p in enumerate(v.get("pills") or []):
        if not isinstance(p, dict):
            continue
        item = {"label": str(p.get("label") or "")[:80],
                "link": _clean_link(p.get("link"), {}, f"{path}.pills[{i}].link", labels + [f"Hap {i + 1}"], ctx)
                or {"kind": "none", "url": "", "new_tab": False},
                "active": bool(p.get("active")), "as_tab": bool(p.get("as_tab"))}
        if p.get("_id"):
            item["_id"] = str(p["_id"])[:64]
        if isinstance(p.get("source"), dict):
            item["source"] = _clean_source(p["source"], {}, f"{path}.pills[{i}].source", labels + [f"Hap {i + 1}"], ctx)
        pills.append(item)
    out["pills"] = pills[:12]
    lk = v.get("link") if isinstance(v.get("link"), dict) else {}
    out["link"] = {"label": str(lk.get("label") or "")[:80],
                   "link": _clean_link(lk.get("link"), {}, f"{path}.link.link", labels + ["Bağlantı"], ctx)
                   or {"kind": "none", "url": "", "new_tab": False}}
    return out


def _clean_spacing(v):
    v = v if isinstance(v, dict) else {}
    out = {}
    for k in ("top", "bottom"):
        n = _num(v.get(k))
        out[k] = max(0, min(400, int(n))) if n is not None else 0
    return out


def _responsive(field, v, fn, default=None):
    """Responsive değer {desktop, tablet, mobile} ya da tek değer. fn(değer, cihaz_varsayılanı)."""
    is_dev = isinstance(default, dict) and set(default) & {"desktop", "tablet", "mobile"}
    if field.get("responsive") and isinstance(v, dict) and set(v) & {"desktop", "tablet", "mobile"}:
        return {d: fn(v.get(d), default.get(d) if is_dev else default) for d in ("desktop", "tablet", "mobile") if d in v}
    return fn(v, default.get("desktop") if is_dev else default)


def _clean_value(field, v, path, labels, ctx, default=None):
    t = field.get("type")
    label = field.get("label") or field.get("name")
    labels = labels + [label]
    if t in ("text", "textarea"):
        if v is None:
            return default if default is not None else ""
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            v = str(v)
        if not isinstance(v, str):
            ctx.err(path, labels, "Metin bekleniyordu.")
            return default if isinstance(default, str) else ""
        mx = int(field.get("max_length") or (2000 if t == "textarea" else 200))
        if len(v) > mx:
            ctx.warn(path, labels, f"En fazla {mx} karakter; fazlası kesildi.")
            v = v[:mx]
        if field.get("required") and not v.strip():
            ctx.err(path, labels, "Bu alan zorunlu.")
        return v
    if t == "rich_text":
        s = sanitize_rich_text(v if isinstance(v, str) else "", field.get("marks"))
        mx = int(field.get("max_length") or 1000)
        if len(s) > mx:
            ctx.warn(path, labels, f"En fazla {mx} karakter; fazlası kesildi.")
            s = sanitize_rich_text(s[:mx], field.get("marks"))
        if field.get("required") and not re.sub(r"<[^>]+>", "", s).strip():
            ctx.err(path, labels, "Bu alan zorunlu.")
        return s
    if t == "html":
        return sanitize_html(v if isinstance(v, str) else "")
    if t == "image":
        out = _clean_image(v, field, path, labels, ctx)
        if field.get("required") and not out:
            ctx.err(path, labels, "Görsel zorunlu.")
        return out
    if t == "link":
        out = _clean_link(v, field, path, labels, ctx)
        if field.get("required") and not (out and out.get("url")):
            ctx.err(path, labels, "Bağlantı boş.")
        return out if out is not None else {"kind": "none", "url": "", "new_tab": False}
    if t == "color":
        s = str(v or "").strip()
        if s and not _COLOR_RE.match(s):
            ctx.err(path, labels, "Renk değeri geçersiz.")
            return default if isinstance(default, str) else ""
        return s

    if t == "number":
        def _n(x, d=None):
            n = _num(x)
            if n is None:
                if x not in (None, ""):
                    ctx.err(path, labels, "Sayı bekleniyordu.")
                return d if isinstance(d, (int, float)) else (field.get("min") or 0)
            if field.get("min") is not None and n < field["min"]:
                n = field["min"]
            if field.get("max") is not None and n > field["max"]:
                n = field["max"]
            return n
        return _responsive(field, v, _n, default)
    if t == "bool":
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "evet", "on")
        return bool(v) if v is not None else bool(default)
    if t == "select":
        opts = field.get("options") or []
        for o in opts:
            if str(o["value"]) == str(v if v is not None else ""):
                return o["value"]
        if v not in (None, ""):
            ctx.err(path, labels, f"Geçersiz seçim: {v}")
        if default is not None and any(str(o["value"]) == str(default) for o in opts):
            return default
        return opts[0]["value"] if opts else ""
    if t == "icon":
        if isinstance(v, str):
            v = {"icon": v}
        v = v if isinstance(v, dict) else {}
        out = {"icon": re.sub(r"[^a-zA-Z0-9 _\-]", "", str(v.get("icon") or ""))[:80]}
        img = _clean_image(v.get("image"), {}, path + ".image", labels, ctx)
        if img:
            out["image"] = img
        return out
    if t == "date_time":
        s = str(v or "").strip()
        if s and not parse_dt(s):
            ctx.err(path, labels, "Tarih geçersiz.")
            return ""
        return s
    if t == "product_source":
        return _clean_source(v, field, path, labels, ctx)
    if t in ("product_picker", "category_picker", "brand_picker"):
        if field.get("multiple", t != "product_picker"):
            if isinstance(v, str):
                v = [v] if v else []
            ids = [str(x)[:80] for x in (v or []) if str(x or "").strip()] if isinstance(v, list) else []
            mx = field.get("max")
            return ids[: int(mx)] if mx else ids
        if isinstance(v, list):
            v = v[0] if v else ""
        return str(v or "")[:80]
    if t == "group":
        v = v if isinstance(v, dict) else {}
        d = default if isinstance(default, dict) else {}
        return _clean_object(field.get("fields") or [], v, path, labels, ctx, d)
    if t == "repeater":
        if not isinstance(v, list):
            if v not in (None, ""):
                ctx.err(path, labels, "Liste bekleniyordu.")
            v = []
        mx = field.get("max")
        if mx and len(v) > int(mx):
            ctx.warn(path, labels, f"En fazla {mx} öğe; fazlası atıldı.")
            v = v[: int(mx)]
        mn = field.get("min")
        if mn and len(v) < int(mn):
            ctx.err(path, labels, f"En az {mn} öğe gerekli.")
        idef = _item_default(field)
        out = []
        for i, it in enumerate(v):
            if not isinstance(it, dict):
                ctx.err(f"{path}[{i}]", labels + [f"{i + 1}. öğe"], "Öğe biçimi geçersiz.")
                continue
            ilabel = f"{field.get('item_noun') or 'Öğe'} {i + 1}"
            c = _clean_object(field.get("item_fields") or [], it, f"{path}[{i}]", labels[:-1] + [label, ilabel], ctx, idef)
            if it.get("_id"):
                c["_id"] = str(it["_id"])[:64]
            if it.get("_hidden"):
                c["_hidden"] = True
            if field.get("item_schedule") or isinstance(it.get("_schedule"), dict):
                sc = it.get("_schedule")
                if isinstance(sc, dict) and (sc.get("start") or sc.get("end")):
                    c["_schedule"] = {"start": str(sc.get("start") or "")[:40], "end": str(sc.get("end") or "")[:40]}
                    if sc.get("tz"):
                        c["_schedule"]["tz"] = str(sc["tz"])[:64]
            out.append(c)
        return out
    if t == "carousel":
        return deep_merge(default if isinstance(default, dict) else {}, _clean_carousel(v, field, path, labels, ctx))
    if t == "spacing":
        return _responsive(field, v, lambda x, _d=None: _clean_spacing(x), default)
    if t == "countdown":
        return _clean_countdown(deep_merge(default or {}, v) if isinstance(v, dict) else default, field, path, labels, ctx)
    if t == "section_header":
        return _clean_section_header(deep_merge(default or {}, v) if isinstance(v, dict) else default, field, path, labels, ctx)
    ctx.warn(path, labels, f"Bilinmeyen alan tipi: {t}")
    return v


def _clean_object(fields, value, path, labels, ctx, defaults=None):
    defaults = defaults if isinstance(defaults, dict) else {}
    out = {}
    known = set()
    for f in fields:
        n = f["name"]
        known.add(n)
        p = f"{path}.{n}" if path else n
        if n in value:
            out[n] = _clean_value(f, value[n], p, labels, ctx, defaults.get(n, f.get("default")))
        elif n in defaults:
            out[n] = copy.deepcopy(defaults[n])
            if f.get("required") and _is_empty(out[n]):
                ctx.err(p, labels + [f.get("label") or n], "Bu alan zorunlu.")
        elif f.get("required"):
            ctx.err(p, labels + [f.get("label") or n], "Bu alan zorunlu.")
    for k in value:
        if k not in known and k not in ("_id", "_hidden", "_schedule") and k not in ROOT_META_KEYS:
            ctx.warn(f"{path}.{k}" if path else k, labels, f"Bilinmeyen alan atıldı: {k}")
    return out


def validate_settings(key: str, settings: dict, *, strict: bool = False, block_label: str = "", path="settings"):
    schema = get_schema(key)
    if not schema:
        raise UnknownBlockType(key)
    ctx = _Ctx(strict)
    ctx.block_label = block_label or schema.get("title", key)
    st = settings if isinstance(settings, dict) else {}
    base = with_defaults(key, st) if schema.get("scope") != "global" else deep_merge(default_settings(key), st)
    clean = _clean_object(all_fields(schema), base, path, [], ctx, default_settings(key, st.get("_variant")))
    # _clean_object ön ekleri "settings." ile — iç yolları sadeleştir
    if schema.get("scope") != "global":
        vs = [str(v["value"]) for v in schema.get("variants") or []]
        var = str(st.get("_variant") or "")
        clean["_variant"] = var if var in vs else (vs[0] if vs else "")
        clean["_v"] = SCHEMA_VERSION
        if isinstance(st.get("_migration_errors"), list) and st["_migration_errors"]:
            clean["_migration_errors"] = [str(x)[:300] for x in st["_migration_errors"][:50]]
        if st.get("_demo"):
            clean["_demo"] = True
    assign_item_ids(all_fields(schema), clean)
    return clean, ctx.errors, ctx.warnings


def validate_block(block: dict, *, strict: bool = False):
    """(temiz_blok, hatalar, uyarılar). Bilinmeyen tip → UnknownBlockType. `_legacy` bloklar olduğu gibi döner."""
    if not isinstance(block, dict):
        raise ValueError("Blok nesne olmalı")
    key = str(block.get("type") or "")
    st = block.get("settings") if isinstance(block.get("settings"), dict) else {}
    base = {"id": str(block.get("id") or new_id())[:64], "type": key,
            "title": str(block.get("title") or "")[:120], "is_active": block.get("is_active") is not False}
    for k in ("created_at", "updated_at", "updated_by", "template_default_hash"):
        if block.get(k):
            base[k] = block[k]
    if st.get("_legacy"):
        return {**base, "settings": st}, [], [{"path": "settings", "label": base["title"] or key,
                                               "message": "Desteklenmeyen eski blok — vitrinde gösterilmez."}]
    schema = get_schema(key)
    if not schema or schema.get("scope") == "global":
        raise UnknownBlockType(key)
    clean, errors, warnings = validate_settings(key, st, strict=strict,
                                                block_label=base["title"] or schema.get("title", key))
    for e in errors + warnings:
        e["block_id"] = base["id"]
    base["settings"] = clean
    base["template_default_hash"] = template_default_hash(key, clean.get("_variant"))
    return base, errors, warnings


def validate_global(global_: dict, *, strict: bool = False):
    out, errors, warnings = {}, [], []
    gs = global_schemas()
    src = global_ if isinstance(global_, dict) else {}
    for key in gs:
        clean, e, w = validate_settings(key, src.get(key) or {}, strict=strict, block_label=gs[key].get("title", key),
                                        path=key)
        for x in e + w:
            x["global_key"] = key
        out[key] = clean
        errors += e
        warnings += w
    return out, errors, warnings


def default_global() -> dict:
    return {k: default_settings(k) for k in global_schemas()}


def validate_layout(blocks: list, global_: dict | None, *, strict: bool = False):
    """Tüm düzen: (temiz_bloklar, temiz_global, hatalar, uyarılar). Bilinmeyen tip → UnknownBlockType."""
    clean_blocks, errors, warnings = [], [], []
    seen = set()
    for i, b in enumerate(blocks or []):
        c, e, w = validate_block(b, strict=strict)
        if c["id"] in seen:
            c["id"] = new_id()
        seen.add(c["id"])
        c["sort_order"] = i + 1
        clean_blocks.append(c)
        errors += e
        warnings += w
    single = {}
    for c in clean_blocks:
        s = get_schema(c["type"])
        if s and s.get("singleton"):
            single[c["type"]] = single.get(c["type"], 0) + 1
    for k, n in single.items():
        if n > 1:
            errors.append({"path": "blocks", "label": get_schema(k).get("title", k),
                           "message": "Bu bloktan sayfada yalnız bir tane olabilir."})
    g, ge, gw = validate_global(global_ or {}, strict=strict)
    return clean_blocks, g, errors + ge, warnings + gw


def public_block(b: dict) -> dict:
    """Vitrine giden blok (eski uçla uyumlu alanlar)."""
    return {"id": b.get("id"), "type": b.get("type"), "title": b.get("title", ""), "is_active": True,
            "settings": b.get("settings") or {}, "sort_order": b.get("sort_order", 0), "page": b.get("page", "home")}
