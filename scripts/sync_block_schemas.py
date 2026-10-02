#!/usr/bin/env python3
"""Sayfa Tasarımı blok şemalarını senkronlar (SPEC §2.1).

Kanonik kaynak: frontend/src/components/pageblocks/<key>/{schema.json,defaults.json[,thumb.png]}
                frontend/src/components/pageblocks/_global/<key>/{schema.json,defaults.json}
                frontend/src/components/pageblocks/_common.json
Üretilenler (elle düzenlenmez):
  backend/pageblocks/schemas/<key>.schema.json, <key>.defaults.json, _common.json   (bayt-eşit kopya)
  frontend/src/components/pageblocks/index.generated.js                               (registry import listesi)
  frontend/public/pageblocks/thumbs/<key>.png                                         (galeri küçük resmi)

Kullanım:
  python scripts/sync_block_schemas.py          # yazar
  python scripts/sync_block_schemas.py --check  # fark varsa 1 ile çıkar (CI / test)
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FE = os.path.join(ROOT, "frontend", "src", "components", "pageblocks")
BE = os.path.join(ROOT, "backend", "pageblocks", "schemas")
THUMBS = os.path.join(ROOT, "frontend", "public", "pageblocks", "thumbs")
INDEX = os.path.join(FE, "index.generated.js")


def block_dirs():
    out = []
    for name in sorted(os.listdir(FE)):
        p = os.path.join(FE, name)
        if os.path.isdir(p) and not name.startswith(("_", ".")) and os.path.isfile(os.path.join(p, "schema.json")):
            out.append((name, p, False))
    gdir = os.path.join(FE, "_global")
    if os.path.isdir(gdir):
        for name in sorted(os.listdir(gdir)):
            p = os.path.join(gdir, name)
            if os.path.isdir(p) and os.path.isfile(os.path.join(p, "schema.json")):
                out.append((name, p, True))
    return out


def _ident(key):
    return "".join(x.capitalize() for x in key.split("_"))


def render_index(dirs) -> str:
    lines = [
        "// OTOMATİK ÜRETİLDİ — elle düzenlemeyin. Üretmek için: python scripts/sync_block_schemas.py",
        "// Her blok klasörü (schema.json + defaults.json + Render.jsx) ve global alan şemaları.",
        "/* eslint-disable */",
    ]
    blocks, globs = [], []
    for key, path, is_global in dirs:
        rel = f"./_global/{key}" if is_global else f"./{key}"
        ident = _ident(key)
        lines.append(f'import {ident}Schema from "{rel}/schema.json";')
        lines.append(f'import {ident}Defaults from "{rel}/defaults.json";')
        if is_global:
            globs.append(f"  {key}: {{ schema: {ident}Schema, defaults: {ident}Defaults }},")
        else:
            has_render = os.path.isfile(os.path.join(path, "Render.jsx"))
            if has_render:
                lines.append(f'import {ident}Render from "{rel}/Render";')
            thumb = os.path.isfile(os.path.join(path, "thumb.png"))
            blocks.append(f"  {key}: {{ schema: {ident}Schema, defaults: {ident}Defaults, "
                          f"Render: {ident + 'Render' if has_render else 'null'}, "
                          f"thumb: {json.dumps('/pageblocks/thumbs/' + key + '.png' if thumb else '')} }},")
    lines.append("")
    lines.append("export const BLOCKS = {")
    lines += blocks
    lines.append("};")
    lines.append("")
    lines.append("export const GLOBALS = {")
    lines += globs
    lines.append("};")
    return "\n".join(lines) + "\n"


def plan():
    """{hedef_yol: bayt} — üretilecek tüm dosyalar."""
    files = {}
    dirs = block_dirs()
    for key, path, _g in dirs:
        for kind in ("schema", "defaults"):
            src = os.path.join(path, f"{kind}.json")
            if os.path.isfile(src):
                with open(src, "rb") as f:
                    files[os.path.join(BE, f"{key}.{kind}.json")] = f.read()
        thumb = os.path.join(path, "thumb.png")
        if os.path.isfile(thumb):
            with open(thumb, "rb") as f:
                files[os.path.join(THUMBS, f"{key}.png")] = f.read()
    with open(os.path.join(FE, "_common.json"), "rb") as f:
        files[os.path.join(BE, "_common.json")] = f.read()
    files[INDEX] = render_index(dirs).encode("utf-8")
    return files


def stale(files):
    """Kaynağı silinmiş üretilmiş kopyalar."""
    out = []
    for d, ext in ((BE, ".json"), (THUMBS, ".png")):
        if os.path.isdir(d):
            for name in os.listdir(d):
                p = os.path.join(d, name)
                if name.endswith(ext) and p not in files:
                    out.append(p)
    return out


def main(argv):
    check = "--check" in argv
    files = plan()
    diff = []
    for path, data in files.items():
        cur = None
        if os.path.isfile(path):
            with open(path, "rb") as f:
                cur = f.read()
        if cur != data:
            diff.append(path)
            if not check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "wb") as f:
                    f.write(data)
    old = stale(files)
    for p in old:
        diff.append(p + " (fazlalık)")
        if not check:
            os.remove(p)
    if check:
        if diff:
            print("Senkron dışı dosyalar:\n  " + "\n  ".join(os.path.relpath(p, ROOT) for p in diff))
            print("Düzeltmek için: python scripts/sync_block_schemas.py")
            return 1
        print(f"Tamam — {len(files)} dosya senkron.")
        return 0
    print(f"{len(diff)} dosya güncellendi ({len(files)} toplam).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
