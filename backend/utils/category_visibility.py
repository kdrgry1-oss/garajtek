"""Vitrin kategori görünürlüğü — saf yardımcılar (DB'siz; routes.categories kullanır)."""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Set

# Sızan test/placeholder kategorileri (HB_CAT_TEST_123, cat_test, test_1, "Test") — yalnız
# alt çizgili / numaralı / tek kelimelik yer tutucular. Gerçek kategoriler de "test" ile
# başlayabilir: "Test ve Arıza Tespit Cihazları" → "test-ve-ariza-tespit-cihazlari". Eski desen
# (`^test[_-]`) bu kök kategoriyi gizliyor, çocukları kök seviyeye düşüp "Tüm Kategoriler"
# menüsünü bozuyordu. Seed ağacından gelen kategoriler (seed_source) hiçbir zaman eşleşmez.
_TEST_PLACEHOLDER = re.compile(
    r"hb_cat_test|cat_test|_test_|test_\d|^test_|_test$|^test[\s_-]*\d*$", re.I)


def is_test_placeholder(c: Dict[str, Any]) -> bool:
    if c.get("seed_source"):
        return False
    return any(_TEST_PLACEHOLDER.search(str(c.get(f) or "").strip()) for f in ("id", "slug", "name"))


def hide_test_placeholders(categories: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Yer tutucuları VE alt ağaçlarını çıkarır (çocuklar kökte "yetim" görünmesin)."""
    cats = list(categories)
    hidden: Set[str] = {str(c.get("id")) for c in cats if is_test_placeholder(c)}
    if not hidden:
        return cats
    by_parent: Dict[str, List[str]] = {}
    for c in cats:
        if c.get("parent_id"):
            by_parent.setdefault(str(c["parent_id"]), []).append(str(c.get("id")))
    stack = list(hidden)
    while stack:
        for kid in by_parent.get(stack.pop(), []):
            if kid not in hidden:
                hidden.add(kid)
                stack.append(kid)
    return [c for c in cats if str(c.get("id")) not in hidden]
