"""
product_specs.py — Ekipman ürünleri için yapılandırılmış teknik özellikler.

Ürün belgesinde:
  specs         : {alan_anahtarı: değer}   (tanımlar data/spec_templates.json → "fields")
  extra_specs   : [{"name": "...", "value": "..."}]  serbest "Ek Teknik Özellikler"
  variant_labels: {"size": "Kapasite", "color": "Model"}  varyant seçenek adları

Paket boyutları / brüt ağırlık / desi YENİ alan değildir: kargo hesabının kullandığı mevcut
width / depth / height (cm), product_weight (kg) ve cargo_weight (desi) alanları kullanılır
(bkz. cargo_carriers/packages.py).

Şablonlar (kategori → görünür alan grubu) varsayılanı data/spec_templates.json; panelden
kaydedilen sürüm settings.spec_templates kaydında tutulur ve varsayılanın yerine geçer.
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

DATA_PATH = Path(__file__).resolve().parent / "data" / "spec_templates.json"
SETTINGS_ID = "spec_templates"
MAX_TEXT = 300
MAX_TEXTAREA = 2000
MAX_EXTRA = 40

_DEFAULT_CACHE: Optional[Dict[str, Any]] = None


def default_config() -> Dict[str, Any]:
    global _DEFAULT_CACHE
    if _DEFAULT_CACHE is None:
        with open(DATA_PATH, encoding="utf-8") as f:
            _DEFAULT_CACHE = json.load(f)
    return copy.deepcopy(_DEFAULT_CACHE)


def validate_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Panelden gelen şablon yapılandırmasını doğrular (alan anahtarları tekil, tipler geçerli,
    şablonlar yalnız tanımlı alanlara başvurur). Hatalıysa ValueError."""
    if not isinstance(cfg, dict):
        raise ValueError("Yapılandırma bir nesne olmalı")
    groups = cfg.get("groups") or []
    fields = cfg.get("fields") or []
    gkeys = {g.get("key") for g in groups if isinstance(g, dict)}
    seen = set()
    for f in fields:
        k = str(f.get("key") or "")
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", k):
            raise ValueError(f"Geçersiz alan anahtarı: {k!r}")
        if k in seen:
            raise ValueError(f"Alan iki kez tanımlı: {k}")
        seen.add(k)
        if f.get("type") not in FIELD_TYPES:
            raise ValueError(f"{k}: bilinmeyen tip {f.get('type')!r}")
        if f.get("group") not in gkeys:
            raise ValueError(f"{k}: bilinmeyen grup {f.get('group')!r}")
        if not str(f.get("label") or "").strip():
            raise ValueError(f"{k}: etiket boş")
    for k in cfg.get("common_fields") or []:
        if k not in seen:
            raise ValueError(f"common_fields: tanımsız alan {k}")
    for t in cfg.get("templates") or []:
        for k in t.get("fields") or []:
            if k not in seen:
                raise ValueError(f"Şablon {t.get('key')}: tanımsız alan {k}")
    return cfg


async def get_config(db) -> Dict[str, Any]:
    try:
        doc = await db.settings.find_one({"id": SETTINGS_ID}, {"_id": 0})
    except Exception:
        doc = None
    if doc and isinstance(doc.get("config"), dict):
        try:
            return validate_config(doc["config"])
        except ValueError:
            pass
    return default_config()


def field_map(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {f["key"]: f for f in cfg.get("fields") or []}


# ── Değer temizleme / doğrulama ─────────────────────────────────────────────

FIELD_TYPES = {"text", "textarea", "number", "int", "select", "multiselect", "bool", "dimensions"}


def _num(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    # Türkçe ondalık: "1.250,5" → 1250.5 ; "2,2" → 2.2
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        raise ValueError("sayı olmalı")


def _clean_value(f: Dict[str, Any], v: Any) -> Any:
    t = f.get("type")
    if t in ("text", "textarea"):
        s = str(v if v is not None else "").strip()
        return s[: (MAX_TEXTAREA if t == "textarea" else MAX_TEXT)] or None
    if t in ("number", "int"):
        n = _num(v)
        if n is None:
            return None
        lo, hi = f.get("min"), f.get("max")
        if lo is not None and n < lo:
            raise ValueError(f"en az {lo} olmalı")
        if hi is not None and n > hi:
            raise ValueError(f"en çok {hi} olmalı")
        if t == "int":
            if n != int(n):
                raise ValueError("tam sayı olmalı")
            return int(n)
        return int(n) if n == int(n) else round(n, 3)
    if t == "bool":
        if v in (None, ""):
            return None
        if isinstance(v, str):
            return v.strip().lower() in ("1", "true", "evet", "var", "on")
        return bool(v)
    if t == "select":
        s = str(v if v is not None else "").strip()[:MAX_TEXT]
        if not s:
            return None
        opts = f.get("options") or []
        if opts and not f.get("free"):
            m = next((o for o in opts if o.casefold() == s.casefold()), None)
            if m is None:
                raise ValueError("listedeki seçeneklerden biri olmalı")
            return m
        m = next((o for o in opts if o.casefold() == s.casefold()), None)
        return m or s
    if t == "multiselect":
        items = v if isinstance(v, list) else [x for x in re.split(r"[,;]", str(v or ""))]
        out: List[str] = []
        opts = f.get("options") or []
        for it in items:
            s = str(it or "").strip()[:80]
            if not s:
                continue
            m = next((o for o in opts if o.casefold() == s.casefold()), None)
            if m is None and opts and not f.get("free"):
                raise ValueError(f"'{s}' geçerli bir seçenek değil")
            s = m or s
            if s not in out:
                out.append(s)
        return out[:20] or None
    if t == "dimensions":
        if not isinstance(v, dict):
            return None
        out = {}
        for k in ("w", "d", "h"):
            n = _num(v.get(k))
            if n is not None:
                if n < 0 or n > 100000:
                    raise ValueError("boyut 0–100000 cm arası olmalı")
                out[k] = int(n) if n == int(n) else round(n, 2)
        return out or None
    return None


def clean_specs(raw: Any, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Gelen specs nesnesini tanımlara göre doğrular. Bilinmeyen anahtarlar atılır, boş değerler
    kaydedilmez. Geçersiz değerde ValueError('Etiket: neden')."""
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Teknik özellikler bir nesne olmalı")
    fm = field_map(cfg)
    out: Dict[str, Any] = {}
    for k, v in raw.items():
        f = fm.get(k)
        if not f:
            continue
        try:
            cv = _clean_value(f, v)
        except ValueError as e:
            raise ValueError(f"{f.get('label')}: {e}")
        if cv is not None and cv != [] and cv != {}:
            out[k] = cv
    return out


def clean_extra_specs(raw: Any) -> List[Dict[str, str]]:
    if not raw:
        return []
    if not isinstance(raw, list):
        raise ValueError("Ek teknik özellikler bir liste olmalı")
    out = []
    for r in raw:
        if not isinstance(r, dict):
            continue
        n = str(r.get("name") or "").strip()[:80]
        v = str(r.get("value") or "").strip()[:MAX_TEXT]
        if n and v:
            out.append({"name": n, "value": v})
    return out[:MAX_EXTRA]


def clean_variant_labels(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k in ("size", "color"):
        s = str(raw.get(k) or "").strip()[:40]
        if s:
            out[k] = s
    return out


# ── Görüntüleme ─────────────────────────────────────────────────────────────

def _fmt_num(n: Any) -> str:
    try:
        x = float(n)
    except (TypeError, ValueError):
        return str(n)
    if x == int(x):
        return f"{int(x):,}".replace(",", ".")
    return f"{x:,.2f}".rstrip("0").rstrip(",").replace(",", "X").replace(".", ",").replace("X", ".")


def format_value(f: Dict[str, Any], v: Any) -> str:
    t = f.get("type")
    unit = f.get("unit") or ""
    if t in ("number", "int"):
        s = _fmt_num(v)
        if f.get("key") == "lifting_capacity_kg":
            try:
                if float(v) >= 1000:
                    return f"{s} kg ({_fmt_num(float(v) / 1000)} ton)"
            except (TypeError, ValueError):
                pass
        return f"{s} {unit}".strip()
    if t == "bool":
        return "Evet" if v else "Hayır"
    if t == "multiselect":
        return ", ".join(str(x) for x in (v or []))
    if t == "dimensions":
        parts = [_fmt_num(v.get(k)) if v.get(k) not in (None, "") else "—" for k in ("w", "d", "h")]
        return " × ".join(parts) + (f" {unit}" if unit else "")
    s = str(v)
    return f"{s} {unit}".strip() if unit and t == "text" and re.fullmatch(r"[\d\s.,–-]+", s) else s


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def spec_table(product: Dict[str, Any], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Vitrin 'Teknik Özellikler' tablosu: [{group, label, rows: [{label, value}]}]."""
    fm = field_map(cfg)
    specs = product.get("specs") if isinstance(product.get("specs"), dict) else {}
    by_group: Dict[str, List[Dict[str, str]]] = {}

    def add(gkey: str, label: str, value: str):
        if value not in (None, ""):
            by_group.setdefault(gkey, []).append({"label": label, "value": value})

    if str(product.get("brand") or "").strip():
        add("genel", "Marka", str(product["brand"]).strip())
    for f in cfg.get("fields") or []:
        k = f["key"]
        if k in specs and specs[k] not in (None, "", [], {}):
            add(f.get("group") or "genel", f.get("label") or k, format_value(f, specs[k]))
    gtin = str(product.get("barcode") or "").strip()
    if gtin:
        add("genel", "Barkod / GTIN", gtin)
    # Paket / kargo bilgileri (mevcut kargo alanları)
    w, d, h = _f(product.get("width")), _f(product.get("depth")), _f(product.get("height"))
    if w and d and h:
        add("boyut", "Paket Boyutları (En × Boy × Yükseklik)", f"{_fmt_num(w)} × {_fmt_num(d)} × {_fmt_num(h)} cm")
    if _f(product.get("product_weight")):
        add("boyut", "Brüt (Paketli) Ağırlık", f"{_fmt_num(product.get('product_weight'))} kg")
    desi = (w * d * h / 3000.0) if (w and d and h) else _f(product.get("cargo_weight"))
    if desi:
        add("boyut", "Desi", _fmt_num(round(desi, 2)))
    for r in product.get("extra_specs") or []:
        if isinstance(r, dict) and r.get("name") and r.get("value"):
            add("ek", str(r["name"]), str(r["value"]))
    labels = {g["key"]: g["label"] for g in cfg.get("groups") or []}
    labels["ek"] = "Ek Teknik Özellikler"
    order = [g["key"] for g in cfg.get("groups") or []] + ["ek"]
    return [{"group": labels.get(g, g), "key": g, "rows": by_group[g]} for g in order if by_group.get(g)]


def template_for(cfg: Dict[str, Any], category_slugs: Iterable[str]) -> Optional[Dict[str, Any]]:
    slugs = [s for s in category_slugs if s]
    for t in cfg.get("templates") or []:
        if any(s in (t.get("category_slugs") or []) for s in slugs):
            return t
    return None


def filterable_fields(cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [f for f in cfg.get("fields") or [] if f.get("filter")]


def spec_query(params: Dict[str, str], cfg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Kategori listesi süzgeci: ?spec_<anahtar>=a,b → specs.<anahtar> ∈ {a,b} ($and koşulları)."""
    fm = field_map(cfg)
    conds = []
    for pk, pv in params.items():
        if not pk.startswith("spec_"):
            continue
        k = pk[5:]
        f = fm.get(k)
        if not f or not f.get("filter"):
            continue
        vals = [x.strip() for x in str(pv or "").split(",") if x.strip()][:20]
        if not vals:
            continue
        if f.get("type") in ("number", "int"):
            nums = []
            for x in vals:
                try:
                    n = _num(x)
                except ValueError:
                    continue
                if n is not None:
                    nums.append(int(n) if n == int(n) else n)
            if nums:
                conds.append({f"specs.{k}": {"$in": nums}})
        else:
            conds.append({f"specs.{k}": {"$in": vals}})
    return conds
