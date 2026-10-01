"""Demo içerik paketi: tüm görsel dosyaları mevcut ve kategoriler tohum ağacında var."""
import os

import demo_content as dc
from seed_categories import load_tree


def _names(tree, out):
    for node in tree:
        out.append(node.get("name", ""))
        _names(node.get("children") or [], out)
    return out


def test_demo_images_exist_and_small():
    total = 0
    for row in dc.P:
        for n in (1, 2, 3):
            p = os.path.join(dc.IMG_DIR, "products", f"{row[0]}-{n}.webp")
            assert os.path.isfile(p), p
            total += os.path.getsize(p)
    for key, *_ in dc.HEROES:
        for suffix in ("", "-m"):
            p = os.path.join(dc.IMG_DIR, "banners", f"{key}{suffix}.webp")
            assert os.path.isfile(p), p
            total += os.path.getsize(p)
    for key, *_ in dc.SMALL + [dc.WIDE]:
        assert os.path.isfile(os.path.join(dc.IMG_DIR, "banners", f"{key}.webp"))
    assert total < 8 * 1024 * 1024


def test_demo_categories_exist_in_seed_tree():
    slugs = {__import__("seed_categories").tr_slugify(n) for n in _names(load_tree(), [])}
    if not slugs:
        return
    missing = {s for row in dc.P for s in row[3] if s not in slugs}
    assert not missing, missing
