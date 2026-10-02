#!/usr/bin/env python3
"""Blok şemalarının §2 formatına uyduğunu ve defaults.json'ın şemadan geçtiğini doğrular (SPEC §8.1).

Kontroller:
  * Zorunlu üst alanlar (key = klasör adı, version, title, category, layout, fields …)
  * Her alan: name, desteklenen type, Türkçe label; tipe özel zorunlu özellikler (options, item_fields, fields)
  * show_if anahtarları var olan alanlara / _variant'a / $parent.* başvurur
  * defaults.json: şemada olmayan anahtar içermez, backend doğrulayıcısından HATASIZ geçer
  * Alanın `default` değeri varsa defaults.json'daki değerle aynıdır
  * Varyant değerleri tekildir; defaults_patch yalnız şema alanlarına dokunur
Kullanım: python scripts/validate_block_schemas.py   (hata varsa 1 ile çıkar)
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE = os.path.join(ROOT, "frontend", "src", "components", "pageblocks")
sys.path.insert(0, os.path.join(ROOT, "backend"))

FIELD_TYPES = {"text", "textarea", "rich_text", "image", "link", "color", "number", "bool", "select", "icon",
               "date_time", "product_source", "product_picker", "category_picker", "brand_picker", "repeater", "group",
               "carousel", "spacing", "countdown", "section_header", "html"}
CATEGORIES = {"slider", "banner", "urun", "firsat", "kategori", "marka", "icerik", "kenar", "ust_bar", "genel"}
LAYOUTS = {"full_bleed", "container", "sidebar", "wide"}
STATUSES = {"ready", "stub", "beta"}
TOP_KEYS = {"key", "version", "title", "description", "category", "group", "status", "template_refs", "layout",
            "singleton", "allowed_pages", "variants", "tabs", "fields", "common", "legacy", "scope"}


def _fields_errors(fields, where, names_ctx=None):
    errs = []
    names = set()
    for i, f in enumerate(fields or []):
        w = f"{where}.fields[{i}]"
        if not isinstance(f, dict):
            errs.append(f"{w}: alan nesne olmalı")
            continue
        n, t = f.get("name"), f.get("type")
        if not n or not isinstance(n, str):
            errs.append(f"{w}: name eksik")
        elif n in names:
            errs.append(f"{w}: '{n}' iki kez tanımlı")
        names.add(n)
        if t not in FIELD_TYPES:
            errs.append(f"{w} ({n}): bilinmeyen tip {t!r}")
        if not f.get("label"):
            errs.append(f"{w} ({n}): label (Türkçe etiket) eksik")
        if t == "select" and not f.get("options"):
            errs.append(f"{w} ({n}): select için options gerekli")
        if t == "repeater":
            if not f.get("item_fields"):
                errs.append(f"{w} ({n}): repeater için item_fields gerekli")
            errs += _fields_errors(f.get("item_fields"), f"{w}.item", None)
        if t == "group":
            if not f.get("fields"):
                errs.append(f"{w} ({n}): group için fields gerekli")
            errs += _fields_errors(f.get("fields"), f"{w}.group", None)
        if f.get("width") not in (None, "full", "half", "third"):
            errs.append(f"{w} ({n}): width full|half|third olmalı")
    for i, f in enumerate(fields or []):
        for k in (f.get("show_if") or {}) if isinstance(f, dict) else {}:
            if k == "_variant" or k.startswith("$parent.") or k.startswith("$root."):
                continue
            if k not in names:
                errs.append(f"{where}.fields[{i}] ({f.get('name')}): show_if bilinmeyen alana bakıyor: {k}")
    return errs


def _default_lookup(fields, defaults, where):
    errs = []
    for f in fields or []:
        n = f.get("name")
        if "default" in f and isinstance(defaults, dict) and n in defaults and defaults[n] != f["default"]:
            errs.append(f"{where}.{n}: field.default ({f['default']!r}) defaults.json ile farklı ({defaults[n]!r})")
        if f.get("type") == "group" and isinstance(defaults, dict) and isinstance(defaults.get(n), dict):
            errs += _default_lookup(f.get("fields"), defaults[n], f"{where}.{n}")
    return errs


def _unknown_keys(fields, defaults, where, allow=()):
    errs = []
    if not isinstance(defaults, dict):
        return errs
    names = {f.get("name"): f for f in fields or []}
    for k, v in defaults.items():
        if k in allow:
            continue
        if k not in names:
            errs.append(f"{where}: defaults.json'da şemada olmayan anahtar: {k}")
            continue
        f = names[k]
        if f.get("type") == "group":
            errs += _unknown_keys(f.get("fields"), v, f"{where}.{k}")
        if f.get("type") == "repeater" and isinstance(v, list):
            for i, it in enumerate(v):
                errs += _unknown_keys(f.get("item_fields"), it, f"{where}.{k}[{i}]", allow=("_id", "_hidden", "_schedule"))
    return errs


def check_one(key, sdir, is_global, pb):
    errs = []
    try:
        with open(os.path.join(sdir, "schema.json"), encoding="utf-8") as f:
            s = json.load(f)
        with open(os.path.join(sdir, "defaults.json"), encoding="utf-8") as f:
            d = json.load(f)
    except Exception as e:  # noqa: BLE001
        return [f"{key}: JSON okunamadı: {e}"]
    w = key
    if s.get("key") != key:
        errs.append(f"{w}: schema.key ({s.get('key')!r}) klasör adıyla aynı olmalı")
    for k in ("version", "title", "category", "fields"):
        if k not in s:
            errs.append(f"{w}: '{k}' eksik")
    for k in s:
        if k not in TOP_KEYS:
            errs.append(f"{w}: bilinmeyen üst alan: {k}")
    if s.get("category") not in CATEGORIES:
        errs.append(f"{w}: category geçersiz: {s.get('category')!r}")
    if not is_global and s.get("layout") not in LAYOUTS:
        errs.append(f"{w}: layout geçersiz: {s.get('layout')!r}")
    if s.get("status", "ready") not in STATUSES:
        errs.append(f"{w}: status geçersiz")
    vals = [v.get("value") for v in s.get("variants") or []]
    if len(vals) != len(set(vals)):
        errs.append(f"{w}: varyant değerleri tekil olmalı")
    for v in s.get("variants") or []:
        if not v.get("label"):
            errs.append(f"{w}: varyant {v.get('value')!r} label eksik")
    errs += _fields_errors(s.get("fields"), w)
    common = pb.common_fields(s) if not is_global else []
    allow = ("_v", "_variant") + tuple(f["name"] for f in common)
    errs += _unknown_keys(s.get("fields"), d, f"{w}/defaults", allow=allow)
    errs += _default_lookup(s.get("fields"), d, f"{w}/defaults")
    for v in s.get("variants") or []:
        errs += _unknown_keys(s.get("fields"), v.get("defaults_patch") or {}, f"{w}/variant:{v.get('value')}", allow=allow)
    if not errs:
        try:
            _c, e, _w = pb.validate_settings(key, pb.default_settings(key), strict=True)
            errs += [f"{w}/defaults: {x['path']}: {x['message']}" for x in e]
            for v in s.get("variants") or []:
                _c, e, _w = pb.validate_settings(key, pb.default_settings(key, v["value"]), strict=True)
                errs += [f"{w}/variant:{v['value']}: {x['path']}: {x['message']}" for x in e]
        except Exception as e:  # noqa: BLE001
            errs.append(f"{w}: doğrulayıcı çöktü: {e!r}")
    return errs


def main():
    import pageblocks as pb  # noqa: E402  (backend kopyası senkron olmalı)
    pb.load_schemas(force=True)
    errs = []
    n = 0
    for name in sorted(os.listdir(FE)):
        p = os.path.join(FE, name)
        if os.path.isdir(p) and not name.startswith(("_", ".")) and os.path.isfile(os.path.join(p, "schema.json")):
            errs += check_one(name, p, False, pb)
            n += 1
    gdir = os.path.join(FE, "_global")
    for name in sorted(os.listdir(gdir)):
        p = os.path.join(gdir, name)
        if os.path.isfile(os.path.join(p, "schema.json")):
            errs += check_one(name, p, True, pb)
            n += 1
    if errs:
        print("\n".join(errs))
        print(f"\n{len(errs)} hata ({n} şema).")
        return 1
    print(f"Tamam — {n} şema geçerli.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
