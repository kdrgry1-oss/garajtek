"""
Garajtek kategori ağacı seed'i (idempotent).

Kaynak: backend/data/garajtek_categories.json — grayzer.net + algikitelli.com.tr menü yapısından
derlenmiş 2–3 seviyeli Türkçe ağaç (isimler/SEO metinleri özgündür).

Kurallar:
  * slug ile upsert: mevcut kategori (slug veya slug_aliases eşleşmesi) KORUNUR, id'si değişmez.
  * Asla silmez. Varsayılan modda yalnızca EKSİK alanları doldurur (panelden yapılan isim/sıra/
    açıklama düzenlemeleri ezilmez); --force ile seed alanları JSON'daki değerlere çekilir.
  * Header menüsü (settings.header_menu) yalnızca kayıt yoksa yazılır (--menu-force ile ezilir).
    Kısa Electro tarzı set: Kampanyalar + Yeni Ürünler + 5 ana kategori (tam ağaç "Tüm
    Kategoriler" dikey menüsünde). Açılışta, kayıt hâlâ ilk kurulumun otomatik UZUN menüsüyse
    (updated_by == seed etiketi, sürüm < 2) kısa menüye yükseltilir; panelden kaydedilmiş menü
    asla değişmez.

Kullanım:
  python seed_categories.py               # kategoriler + (yoksa) header menü
  python seed_categories.py --force       # seed alanlarını JSON'a göre güncelle
  python seed_categories.py --menu-force  # header menüyü ağaçtan yeniden üret
  python seed_categories.py --check       # yalnızca JSON doğrulaması (DB'ye dokunmaz)

Sunucu açılışında `seed_if_empty()` çağrılır: categories koleksiyonu BOŞSA ağacı yükler; doluysa
yalnızca `upgrade_seeded_header_menu()` çalışır (dokunulmamış otomatik menüyü kısaltır).
"""
from __future__ import annotations

import json
import logging
import random
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("seed_categories")

DATA_PATH = Path(__file__).resolve().parent / "data" / "garajtek_categories.json"
SEED_TAG = "garajtek_categories_v1"

# Seed'in yönettiği alanlar (JSON anahtarı → DB alanı)
_MANAGED = {
    "name": "name",
    "sort_order": "sort_order",
    "icon": "icon",
    "meta_title": "meta_title",
    "meta_description": "meta_description",
}

_TR_MAP = {'ı': 'i', 'İ': 'i', 'I': 'i', 'ş': 's', 'Ş': 's', 'ç': 'c', 'Ç': 'c',
           'ğ': 'g', 'Ğ': 'g', 'ö': 'o', 'Ö': 'o', 'ü': 'u', 'Ü': 'u'}


def tr_slugify(name: str) -> str:
    """Türkçe-güvenli slug — routes.categories.generate_slug ile aynı kurallar
    ("&" ayrıca boşluk sayılır: "Kaynak & Kesme" → "kaynak-kesme")."""
    s = "".join(_TR_MAP.get(ch, ch) for ch in str(name or "")).replace("&", " ")
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


# ── Ağaç yükleme / doğrulama ───────────────────────────────────────────────

def load_tree(path: Path | str = DATA_PATH) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    nodes = doc["categories"] if isinstance(doc, dict) else doc
    validate_tree(nodes)
    return nodes


def validate_tree(nodes: List[Dict[str, Any]], max_depth: int = 3) -> None:
    """Hata varsa ValueError. Kontroller: zorunlu alanlar, slug biçimi, tekil slug,
    ebeveyn mevcut ve kendinden ÖNCE tanımlı, derinlik ≤ max_depth, döngü yok."""
    errors: List[str] = []
    seen: Dict[str, Dict[str, Any]] = {}
    depth: Dict[str, int] = {}
    for i, n in enumerate(nodes):
        slug, name = n.get("slug"), n.get("name")
        if not slug or not name:
            errors.append(f"#{i}: slug/name zorunlu")
            continue
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            errors.append(f"{slug}: geçersiz slug biçimi")
        if slug != tr_slugify(name):
            errors.append(f"{slug}: isimden türeyen slug '{tr_slugify(name)}' ile uyuşmuyor")
        if slug in seen:
            errors.append(f"{slug}: tekrarlanan slug")
        parent = n.get("parent")
        if parent:
            if parent == slug:
                errors.append(f"{slug}: kendi kendinin ebeveyni")
            elif parent not in seen:
                errors.append(f"{slug}: ebeveyn '{parent}' yok ya da sonra tanımlı")
            else:
                depth[slug] = depth[parent] + 1
        else:
            depth[slug] = 1
        if depth.get(slug, 1) > max_depth:
            errors.append(f"{slug}: derinlik {depth[slug]} > {max_depth}")
        if not isinstance(n.get("sort_order", 0), int):
            errors.append(f"{slug}: sort_order tam sayı olmalı")
        seen[slug] = n
    if errors:
        raise ValueError("Kategori ağacı geçersiz:\n  " + "\n  ".join(errors))


# ── DB seed ────────────────────────────────────────────────────────────────

async def _new_id(db) -> str:
    """routes.deps.generate_short_id ile aynı biçim (4 haneli, çakışmasız)."""
    for _ in range(100):
        cand = str(random.randint(1000, 9999))
        if not await db.categories.find_one({"id": cand}, {"_id": 1}):
            return cand
    return uuid.uuid4().hex[:8]


async def _find_existing(db, slug: str) -> Optional[Dict[str, Any]]:
    doc = await db.categories.find_one({"slug": slug}, {"_id": 0})
    if not doc:
        doc = await db.categories.find_one({"slug_aliases": slug}, {"_id": 0})
    return doc


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


async def seed_categories(db, nodes: Optional[List[Dict[str, Any]]] = None, *, force: bool = False,
                          id_factory: Optional[Callable] = None) -> Dict[str, int]:
    """Ağacı DB'ye upsert eder. Dönüş: {"created", "updated", "unchanged"}."""
    nodes = nodes if nodes is not None else load_tree()
    validate_tree(nodes)
    now = datetime.now(timezone.utc).isoformat()
    slug_to_id: Dict[str, Any] = {}
    stats = {"created": 0, "updated": 0, "unchanged": 0}

    for n in nodes:  # ebeveynler her zaman önce gelir (validate_tree garanti eder)
        slug = n["slug"]
        parent_id = slug_to_id.get(n["parent"]) if n.get("parent") else None
        existing = await _find_existing(db, slug)

        if existing:
            slug_to_id[slug] = existing["id"]
            upd: Dict[str, Any] = {}
            for key, field in _MANAGED.items():
                if key not in n:
                    continue
                if force:
                    if existing.get(field) != n[key]:
                        upd[field] = n[key]
                elif _empty(existing.get(field)):
                    upd[field] = n[key]
            # Ebeveyn: yalnızca eksikse (veya --force) bağla; panelde taşınmış kategoriye dokunma.
            if parent_id is not None and (force or _empty(existing.get("parent_id"))):
                if str(existing.get("parent_id")) != str(parent_id):
                    upd["parent_id"] = parent_id
            if force and n.get("show_in_menu") is False and existing.get("show_in_menu") is not False:
                upd["show_in_menu"] = False
            if upd:
                upd["updated_at"] = now
                await db.categories.update_one({"id": existing["id"]}, {"$set": upd})
                stats["updated"] += 1
            else:
                stats["unchanged"] += 1
            continue

        new_id = await (id_factory() if id_factory else _new_id(db))
        doc = {
            "id": new_id,
            "name": n["name"],
            "slug": slug,
            "description": "",
            "image": "",
            "image_url": "",
            "parent_id": parent_id,
            "sort_order": n.get("sort_order", 0),
            "is_active": True,
            "members_only": False,
            "icon": n.get("icon", ""),
            "meta_title": n.get("meta_title", ""),
            "meta_description": n.get("meta_description", ""),
            "attribute_mapping": {},
            "seed_source": SEED_TAG,
            "created_at": now,
        }
        if n.get("show_in_menu") is False:
            doc["show_in_menu"] = False
        await db.categories.insert_one(dict(doc))
        slug_to_id[slug] = new_id
        stats["created"] += 1

    return stats


# Header yatay menüsü: Electro home-v1 gibi KISA (≈7 sekme). Tam ağaç zaten "Tüm Kategoriler"
# dikey menüsünden erişilebilir. Sürüm, otomatik üretilmiş eski menünün güvenle
# yükseltilebilmesi için kayda yazılır (bkz. upgrade_seeded_header_menu).
HEADER_MENU_VERSION = 2
HEADER_MENU_CATEGORIES = [
    "liftler", "kompresorler", "lastik-ekipmanlari", "el-aletleri", "lokma-takimlari",
]


def _children_map(nodes: List[Dict[str, Any]]) -> Dict[Optional[str], List[Dict[str, Any]]]:
    children: Dict[Optional[str], List[Dict[str, Any]]] = {}
    for n in nodes:
        children.setdefault(n.get("parent"), []).append(n)
    for lst in children.values():
        lst.sort(key=lambda x: x.get("sort_order", 0))
    return children


def _category_tab(top: Dict[str, Any], children: Dict[Optional[str], List[Dict[str, Any]]]) -> Dict[str, Any]:
    subs = children.get(top["slug"], [])
    tab = {
        "id": f"cat-{top['slug']}",
        "label": top["name"][:60],
        "type": "mega" if subs else "link",
        "link": f"/{top['slug']}",
        "style": "normal",
        "active": True,
    }
    if subs:
        tab["columns"] = [
            {"title": s["name"][:60], "link": f"/{s['slug']}",
             "items": [{"name": g["name"][:60], "link": f"/{g['slug']}"}
                       for g in children.get(s["slug"], [])]}
            for s in subs
        ]
    return tab


def build_header_menu(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """settings.header_menu 'tabs' yapısı (routes/cms.py save_header_menu şeması), KISA set:
    Kampanyalar (SALE) + Yeni Ürünler + en önemli 5 ana kategori (mega: alt kategori → kolon,
    3. seviye → kolon öğeleri). Ağaçta olmayan/menüden gizli kategori atlanır."""
    children = _children_map(nodes)
    by_slug = {n["slug"]: n for n in nodes}
    # Sanal slug'lar: "/sale" indirimli ürünleri, "/en-yeniler" en yeni ürünleri listeler.
    tabs: List[Dict[str, Any]] = [
        {"id": "sale", "label": "Kampanyalar", "type": "link", "link": "/sale",
         "style": "sale", "active": True},
        {"id": "yeni", "label": "Yeni Ürünler", "type": "link", "link": "/en-yeniler",
         "style": "normal", "active": True},
    ]
    for slug in HEADER_MENU_CATEGORIES:
        top = by_slug.get(slug)
        if not top or top.get("parent") or top.get("show_in_menu") is False:
            continue
        tabs.append(_category_tab(top, children))
    return tabs


def build_legacy_header_menu(nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """v1 (ilk canlı kurulum) otomatik menüsü: HER üst kategori bir sekme + "İndirimli Ürünler".
    Yalnız upgrade_seeded_header_menu'nün eski kaydı tanıması için tutulur."""
    children = _children_map(nodes)
    tabs = [_category_tab(top, children) for top in children.get(None, [])
            if top.get("show_in_menu") is not False]
    tabs.append({"id": "sale", "label": "İndirimli Ürünler", "type": "link", "link": "/sale",
                 "style": "sale", "active": True})
    return tabs


async def seed_header_menu(db, nodes: Optional[List[Dict[str, Any]]] = None, *,
                           force: bool = False) -> bool:
    """Header menü kaydı yoksa (veya force) ağaçtan üretir. Yazıldıysa True."""
    nodes = nodes if nodes is not None else load_tree()
    existing = await db.settings.find_one({"id": "header_menu"}, {"_id": 0})
    if existing and existing.get("tabs") and not force:
        return False
    await db.settings.update_one(
        {"id": "header_menu"},
        {"$set": {"tabs": build_header_menu(nodes),
                  "updated_at": datetime.now(timezone.utc).isoformat(),
                  "updated_by": SEED_TAG,
                  "seed_menu_version": HEADER_MENU_VERSION}},
        upsert=True,
    )
    return True


def _is_untouched_seed_menu(doc: Optional[Dict[str, Any]], nodes: List[Dict[str, Any]]) -> bool:
    """Kayıt hâlâ seeder'ın yazdığı ESKİ menü mü? Panelden kaydedilen menüde updated_by yönetici
    e-postası/id'sidir → asla eşleşmez. Ek güvenlik: sekme bağlantıları v1 menüsüyle birebir aynı
    olmalı (elle DB'de oynanmış bir kayıt da korunur)."""
    if not doc or doc.get("updated_by") != SEED_TAG:
        return False
    if int(doc.get("seed_menu_version") or 1) >= HEADER_MENU_VERSION:
        return False
    tabs = doc.get("tabs") or []
    legacy = build_legacy_header_menu(nodes)
    return [(t.get("id"), t.get("link")) for t in tabs if isinstance(t, dict)] == \
        [(t["id"], t["link"]) for t in legacy]


async def upgrade_seeded_header_menu(db=None, nodes: Optional[List[Dict[str, Any]]] = None) -> bool:
    """Açılış kancası (idempotent): header menü hâlâ ilk kurulumda otomatik üretilen UZUN v1
    menüsüyse kısa v2 menüyle değiştirir. Yönetici tarafından kaydedilmiş menüye DOKUNMAZ."""
    try:
        if db is None:
            from routes.deps import db as _db
            db = _db
        nodes = nodes if nodes is not None else load_tree()
        doc = await db.settings.find_one({"id": "header_menu"}, {"_id": 0})
        if not _is_untouched_seed_menu(doc, nodes):
            return False
        await db.settings.update_one(
            {"id": "header_menu", "updated_by": SEED_TAG},
            {"$set": {"tabs": build_header_menu(nodes),
                      "updated_at": datetime.now(timezone.utc).isoformat(),
                      "updated_by": SEED_TAG,
                      "seed_menu_version": HEADER_MENU_VERSION}},
        )
        logger.info("[kategori seed] otomatik header menü kısa v2 menüye yükseltildi")
        return True
    except Exception as e:  # açılışı asla düşürme
        logger.error(f"[kategori seed] header menü yükseltme hatası: {e}")
        return False


async def seed_if_empty(db=None) -> Optional[Dict[str, int]]:
    """Açılış kancası: categories koleksiyonu BOŞSA ağacı + header menüyü yükler."""
    try:
        if db is None:
            from routes.deps import db as _db
            db = _db
        if await db.categories.find_one({}, {"_id": 1}):
            await upgrade_seeded_header_menu(db)
            return None
        nodes = load_tree()
        stats = await seed_categories(db, nodes)
        menu = await seed_header_menu(db, nodes)
        logger.info(f"[kategori seed] boş katalog → {stats}, header menü: {'yazıldı' if menu else 'mevcut'}")
        return stats
    except Exception as e:  # açılışı asla düşürme
        logger.error(f"[kategori seed] hata: {e}")
        return None


def _main() -> None:
    import argparse
    import asyncio
    import sys

    ap = argparse.ArgumentParser(description="Garajtek kategori ağacını seed eder (idempotent).")
    ap.add_argument("--force", action="store_true", help="seed alanlarını JSON değerlerine çek")
    ap.add_argument("--menu-force", action="store_true", help="header menüyü ağaçtan yeniden üret")
    ap.add_argument("--no-menu", action="store_true", help="header menüye dokunma")
    ap.add_argument("--check", action="store_true", help="yalnızca JSON'u doğrula")
    args = ap.parse_args()

    nodes = load_tree()
    if args.check:
        tops = sum(1 for n in nodes if not n.get("parent"))
        print(f"OK: {len(nodes)} kategori, {tops} üst seviye")
        return

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parent / ".env")
    except Exception:
        pass
    from routes.deps import db

    async def run():
        stats = await seed_categories(db, nodes, force=args.force)
        print(f"Kategoriler: {stats}")
        if not args.no_menu:
            wrote = await seed_header_menu(db, nodes, force=args.menu_force)
            print("Header menü: " + ("yazıldı" if wrote else "mevcut kayıt korundu (--menu-force ile ez)"))

    asyncio.run(run())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _main()
