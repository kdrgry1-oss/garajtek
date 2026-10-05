"""Gerçek alış faturasından katalog tohumu (Al Nalburiye, 25-09-2026).

İşletme sahibi bu ürünleri stokladı ve canlı mağazada 3 katı fiyatla (KDV dahil) satışa açılmasını
istedi; panelden tek tek girmek yerine açılışta İDEMPOTENT olarak oluşturulur.

Kurallar
  * Veri: data/catalog_seed_al_2026_09.json (ürün adı, marka, kategori slug'ı, stok kodu, adet, satır
    tutarı, teknik özellikler, özgün açıklama, üretici sayfa adresleri).
  * Fiyat: satış = 3 × (satır tutarı / adet) × 1,20, 2 haneye yuvarlanır (KDV dahil). Alış (net,
    KDV hariç) `purchase_price` alanına yazılır → kâr/maliyet raporları.
  * Varyantlı ürün: ürün fiyatı = en ucuz ölçü; diğer ölçüler `price_adjustment` (fark) taşır —
    sepet/kasa (orders._eff_unit_price, /products/cart-pricing, CartContext) bu farkı uygular.
  * Bir kez: settings {"id": MARKER} kaydı varsa oluşturma adımı atlanır. Yoksa her ürün YALNIZ aynı
    stok kodu / barkod / varyant SKU'su taşıyan ürün yoksa oluşturulur → panelde sonradan yapılan
    düzenlemeler ASLA ezilmez. Demo etiketi / noindex YOK; aktif; stok = fatura adedi.
  * Kategoriler (seed_categories arka plan görevi) hazır değilse beklenir; yine yoksa işaret
    yazılmaz, sonraki açılışta tekrar denenir.
  * Görseller: oluşturma sonrası arka planda, YALNIZ görseli hâlâ boş olan tohum ürünlerine üretici /
    yetkili satıcı sayfalarından (url_import'un SSRF korumalı Fetcher'ı + ayrıştırıcısı) indirilir,
    WebP'ye çevrilip medya deposuna yazılır. Yönetici görsel yüklediyse dokunulmaz. Başarısızlıkta
    birkaç kez yeniden denenir; ürün başına `images_fetched_at` / `images_fetch_attempts` tutulur.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from html import escape
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlsplit

logger = logging.getLogger("catalog_seed")

SEED_ID = "catalog_seed_al_2026_09"
MARKER = f"{SEED_ID}_applied"
DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"{SEED_ID}.json")
MAX_IMAGES = 4
MAX_IMAGE_ATTEMPTS = 12         # tüm açılışlar boyunca ürün başına üst sınır
RETRY_DELAYS = (0, 60, 300)     # aynı açılış içinde deneme aralıkları (sn)

CreateProduct = Callable[[dict], Awaitable[dict]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_seed(path: str = DATA_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _d(x) -> Decimal:
    return Decimal(str(x))


def net_unit_cost(line_total, qty) -> float:
    """KDV hariç net birim alış = satır tutarı / adet (2 hane)."""
    return float((_d(line_total) / int(qty)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def sale_price(line_total, qty, markup=3, vat_rate=20) -> float:
    """Satış (KDV dahil) = markup × (satır/adet) × (1 + KDV). Ara yuvarlama yok, sonuç 2 hane."""
    v = _d(line_total) / int(qty) * _d(markup) * (1 + _d(vat_rate) / 100)
    return float(v.quantize(Decimal("0.01"), ROUND_HALF_UP))


def _desc_html(p: dict) -> str:
    rows = "".join(f"<tr><th>{escape(k)}</th><td>{escape(v)}</td></tr>" for k, v in p.get("table") or [])
    lis = "".join(f"<li>{escape(b)}</li>" for b in p.get("bullets") or [])
    box = (p.get("specs") or {}).get("box_contents")
    out = f"<p>{escape(p['intro'])}</p>"
    if lis:
        out += f"<h3>Öne Çıkan Özellikler</h3><ul>{lis}</ul>"
    if rows:
        out += f"<h3>Teknik Özellikler</h3><table><tbody>{rows}</tbody></table>"
    if box:
        out += f"<h3>Kutu İçeriği</h3><p>{escape(box)}</p>"
    return out


def build_product(p: dict, seed: dict, cat: dict) -> tuple[dict, dict]:
    """(create_product verisi, create sonrası $set edilecek ek alanlar)."""
    markup, vat = seed.get("markup", 3), seed.get("vat_rate", 20)
    w, dep, h = p.get("dims") or (0, 0, 0)
    kg = float(p.get("kg") or 0)
    desi = round(w * dep * h / 3000.0, 2) if (w and dep and h) else 0
    data: Dict[str, Any] = {
        "name": p["name"],
        "brand": p["brand"],
        "manufacturer": p["brand"],
        "categories": [cat["id"]],
        "category_id": cat["id"],
        "category_name": cat.get("name") or "",
        "images": [],
        "description": _desc_html(p),
        "short_description": p["intro"],
        "attributes": [{"name": k, "value": v} for k, v in p.get("table") or []],
        "stock_code": p["stock_code"],
        "supplier": seed.get("supplier", ""),
        "is_active": True,
        "is_new": True,
        "vat_rate": vat,
        "specs": p.get("specs") or {},
        "extra_specs": p.get("extra_specs") or [],
        "width": w, "depth": dep, "height": h,
        "product_weight": kg,
        # kargo firması ağırlık ile desiden büyüğünü faturalar
        "cargo_weight": round(max(desi, kg), 2),
    }
    if p.get("barcode"):
        data["barcode"] = p["barcode"]
    vs = p.get("variants") or []
    if vs:
        prices = [sale_price(v["line_total"], v["qty"], markup, vat) for v in vs]
        base = min(prices)
        variants = []
        tot_cost = Decimal(0)
        tot_qty = 0
        for v, price in zip(vs, prices):
            cost = net_unit_cost(v["line_total"], v["qty"])
            tot_cost += _d(v["line_total"])
            tot_qty += int(v["qty"])
            variants.append({
                "size": v["size"], "stock": int(v["qty"]), "sku": v["sku"],
                "stock_code": v["sku"], "mpn": v.get("mpn", ""),
                "price_adjustment": round(price - base, 2),
                "purchase_price": cost,
            })
        data["price"] = base
        data["variants"] = variants
        data["variant_labels"] = {"size": p.get("variant_label") or "Ölçü"}
        data["purchase_price"] = float((tot_cost / tot_qty).quantize(Decimal("0.01"), ROUND_HALF_UP))
        data["stock"] = tot_qty
    else:
        data["price"] = sale_price(p["line_total"], p["qty"], markup, vat)
        data["purchase_price"] = net_unit_cost(p["line_total"], p["qty"])
        data["stock"] = int(p["qty"])
    extra = {
        "vat_included": True,
        "meta_title": (p.get("meta_title") or p["name"])[:70],
        "meta_description": (p.get("meta_description") or p["intro"])[:160],
        "mpn": (p.get("specs") or {}).get("mpn", ""),
        "catalog_seed": SEED_ID,
        "catalog_seed_key": p["key"],
        "source_page_urls": list(p.get("source_page_urls") or []),
        "source_image_urls": list(p.get("image_urls") or []),
        "purchase_invoice": {"supplier": seed.get("supplier", ""), "date": seed.get("invoice_date", "")},
    }
    return data, extra


def _codes(p: dict) -> List[str]:
    codes = [p["stock_code"]] + [v["sku"] for v in p.get("variants") or []]
    if p.get("barcode"):
        codes.append(p["barcode"])
    return [c for c in codes if c]


async def _exists(db, p: dict) -> bool:
    for c in _codes(p):
        for q in ({"stock_code": c}, {"barcode": c}, {"sku": c}, {"variants.sku": c},
                  {"variants.barcode": c}, {"variants.stock_code": c}):
            if await db.products.find_one(q, {"_id": 0, "id": 1}):
                return True
    return False


async def _wait_categories(db, slugs: List[str], timeout: float, poll: float = 2.0) -> Dict[str, dict]:
    loop = asyncio.get_event_loop()
    end = loop.time() + timeout
    while True:
        cats = {c["slug"]: c for c in await db.categories.find(
            {"slug": {"$in": slugs}}, {"_id": 0, "id": 1, "slug": 1, "name": 1}).to_list(100)}
        if all(s in cats for s in slugs) or loop.time() >= end:
            return cats
        await asyncio.sleep(poll)


async def apply_seed(db, create_product: CreateProduct, *, seed: Optional[dict] = None,
                     category_timeout: float = 60.0) -> dict:
    """Ürünleri (bir kez) oluşturur. Döner: {created, skipped, missing_categories, marker}."""
    seed = seed or load_seed()
    if await db.settings.find_one({"id": MARKER}, {"_id": 0, "id": 1}):
        return {"created": [], "skipped": [], "missing_categories": [], "marker": "already"}
    slugs = sorted({p["category_slug"] for p in seed["products"]})
    cats = await _wait_categories(db, slugs, category_timeout)
    missing = [s for s in slugs if s not in cats]
    created, skipped = [], []
    for p in seed["products"]:
        if p["category_slug"] not in cats:
            continue
        if await _exists(db, p):
            skipped.append(p["stock_code"])
            continue
        data, extra = build_product(p, seed, cats[p["category_slug"]])
        res = await create_product(data)
        pid = (res or {}).get("id")
        if not pid:
            raise RuntimeError(f"ürün oluşturulamadı: {p['stock_code']}")
        await db.products.update_one({"id": pid}, {"$set": {**extra, "catalog_seeded_at": _now()}})
        created.append(p["stock_code"])
    if missing:
        logger.warning(f"[{SEED_ID}] kategori bulunamadı {missing} — işaret yazılmadı, sonraki açılışta denenecek")
        return {"created": created, "skipped": skipped, "missing_categories": missing, "marker": None}
    await db.settings.update_one(
        {"id": MARKER},
        {"$set": {"id": MARKER, "done": True, "applied_at": _now(), "created": created, "skipped": skipped}},
        upsert=True)
    return {"created": created, "skipped": skipped, "missing_categories": [], "marker": "written"}


# ── görseller ───────────────────────────────────────────────────────────────

def _no_images(doc: dict) -> bool:
    return not [x for x in (doc.get("images") or []) if x]


def _og_images(body: bytes, url: str, charset: Optional[str]) -> List[str]:
    import re
    from urllib.parse import urljoin
    from url_import.parser import soup_of

    soup = soup_of(body, charset)
    pat = re.compile(r"^og:image(:url|:secure_url)?$")
    return [urljoin(url, m.get("content").strip()) for m in soup.find_all("meta", attrs={"property": pat})
            if m.get("content")]


async def _page_images(fetcher, page: str) -> List[str]:
    """Bir kaynak sayfadaki ürün görselleri (JSON-LD/microdata/platform galerisi; aksi hâlde og:image önde)."""
    from url_import.fetcher import BlockedURL, FetchError
    from url_import.parser import parse_product

    try:
        r = await fetcher.fetch(page, kind="html")
        pd = parse_product(r.body, r.url, r.charset)
    except (FetchError, BlockedURL) as e:
        logger.info(f"[{SEED_ID}] sayfa alınamadı {page}: {e}")
        return []
    except Exception as e:  # noqa: BLE001 — ayrıştırma hatası diğer kaynakları engellemesin
        logger.info(f"[{SEED_ID}] sayfa ayrıştırılamadı {page}: {e}")
        return []
    imgs = [u for u in pd.images if u]
    if pd.sources.get("images") not in ("jsonld", "microdata", "platform"):
        # genel galeri seçicisi kurumsal sayfalarda logo/banner yakalayabilir → og:image önce
        imgs = _og_images(r.body, r.url, r.charset) + imgs
    out: List[str] = []
    for u in imgs:
        if u not in out:
            out.append(u)
    return out


async def _download(fetcher, img_url: str, referer: str) -> bytes:
    from url_import.job import convert_image

    headers = {"Referer": referer} if referer else None
    r = await fetcher.fetch(img_url, kind="image", headers=headers)
    return await asyncio.to_thread(convert_image, r.body, r.content_type)


async def fetch_images_for_product(db, doc: dict, *, fetcher, store_image) -> int:
    """Tek ürün: kaynakları sırayla dener (doğrudan görsel adresleri → üretici sayfası → yetkili
    satıcı sayfaları); görsel İNDİRİLEBİLEN ilk kaynağın görsellerini (en çok MAX_IMAGES) ürün hâlâ
    görselsizse yazar. Döner: yazılan görsel sayısı."""
    from url_import.fetcher import BlockedURL, FetchError

    pid = doc["id"]
    saved: List[dict] = []
    errs: List[str] = []
    sources = []
    if doc.get("source_image_urls"):
        sources.append(("", list(doc["source_image_urls"])))
    sources += [(pg, None) for pg in doc.get("source_page_urls") or []]
    try:
        for page, imgs in sources:
            if imgs is None:
                imgs = await _page_images(fetcher, page)
                if not imgs:
                    errs.append(f"{urlsplit(page).hostname}: görsel yok/erişilemedi")
                    continue
            for img_url in imgs:
                if len(saved) >= MAX_IMAGES:
                    break
                try:
                    webp = await _download(fetcher, img_url, page)
                except (FetchError, BlockedURL, ValueError) as e:
                    errs.append(f"{img_url.rsplit('/', 1)[-1][:60]}: {e}")
                    continue
                host = (urlsplit(page or img_url).hostname or "").lower()
                res = await store_image(
                    webp, "image/webp", "webp", f"{doc.get('catalog_seed_key') or pid}-{len(saved) + 1}.webp",
                    extra={"catalog_seed": SEED_ID, "product_id": pid, "source_page": page,
                           "source_image": img_url, "source_host": host})
                if res and res.get("url"):
                    saved.append({"url": res["url"], "page": page})
            if saved:
                break
    except Exception as e:  # noqa: BLE001
        errs.append(str(e)[:200])
    err = "; ".join(errs)[-400:]
    cur = await db.products.find_one({"id": pid}, {"_id": 0, "images": 1}) or {}
    if saved and _no_images(cur):
        await db.products.update_one({"id": pid}, {"$set": {
            "images": [s["url"] for s in saved],
            "images_fetched_at": _now(),
            "images_source_page": saved[0]["page"],
            "images_fetch_error": "",
        }, "$inc": {"images_fetch_attempts": 1}})
        return len(saved)
    if saved:  # bu arada yönetici görsel yükledi → indirilenler kullanılmaz (dosyalar zararsız kalır)
        await db.products.update_one({"id": pid}, {"$set": {"images_fetched_at": _now(),
                                                            "images_fetch_error": "yönetici görseli mevcut"}})
        return 0
    await db.products.update_one({"id": pid}, {"$set": {"images_fetch_error": err or "görsel indirilemedi",
                                                        "images_last_attempt_at": _now()},
                                               "$inc": {"images_fetch_attempts": 1}})
    return 0


async def pending_image_products(db) -> List[dict]:
    rows = await db.products.find({"catalog_seed": SEED_ID}, {"_id": 0}).to_list(100)
    return [d for d in rows if _no_images(d) and not d.get("images_fetched_at")
            and int(d.get("images_fetch_attempts") or 0) < MAX_IMAGE_ATTEMPTS]


async def fetch_missing_images(db, *, store_image, fetcher=None) -> dict:
    """Görselsiz tohum ürünleri için bir tur indirme. Döner: {key: görsel sayısı}."""
    from url_import.fetcher import Fetcher

    rows = await pending_image_products(db)
    if not rows:
        return {}
    own = fetcher is None
    fetcher = fetcher or Fetcher()
    out = {}
    try:
        for d in rows:
            out[d.get("catalog_seed_key") or d["id"]] = await fetch_images_for_product(
                db, d, fetcher=fetcher, store_image=store_image)
    finally:
        if own:
            await fetcher.close()
    return out


# ── açılış kancası ──────────────────────────────────────────────────────────

FEATURED_MARKER = f"{SEED_ID}_featured_v1"


async def mark_featured_once(db) -> int:
    """Fatura ürünlerini BİR KEZ "Öne Çıkan" yapar (ana sayfa Öne Çıkanlar sekmesi/sütunu).
    Sonradan yönetici öne çıkarmayı kaldırırsa tekrar açılmaz (bayraklı)."""
    if await db.settings.find_one({"id": FEATURED_MARKER}, {"_id": 0, "id": 1}):
        return 0
    if not await db.products.count_documents({"catalog_seed": SEED_ID}):
        return 0  # ürünler henüz oluşmadı → bayrak yazılmaz, sonraki açılışta tekrar denenir
    r = await db.products.update_many({"catalog_seed": SEED_ID}, {"$set": {"is_featured": True}})
    await db.settings.update_one(
        {"id": FEATURED_MARKER},
        {"$set": {"id": FEATURED_MARKER, "done": True, "applied_at": _now()}}, upsert=True)
    return getattr(r, "modified_count", 0)


async def run_startup(db=None, *, delays=RETRY_DELAYS) -> None:
    """server.py lifespan'inden arka plan görevi olarak çağrılır; açılışı asla düşürmez.
    CATALOG_SEED_DISABLED=1 → hiçbir şey yapmaz (yerel test/izole ortam)."""
    if (os.environ.get("CATALOG_SEED_DISABLED") or "").strip().lower() in ("1", "true", "yes"):
        return
    try:
        if db is None:
            from routes.deps import db as _db
            db = _db
        from starlette.requests import Request
        from routes.products import create_product
        req = Request({"type": "http", "method": "POST", "path": f"/startup/{SEED_ID}", "headers": [],
                       "client": ("127.0.0.1", 0)})
        user = {"id": "system", "email": "system@localhost", "is_admin": True, "role": "system",
                "first_name": "Sistem", "last_name": "(fatura tohumu)"}
        res = await apply_seed(db, lambda d: create_product(d, req, user))
        if res.get("created") or res.get("missing_categories"):
            logger.warning(f"[{SEED_ID}] {res}")
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{SEED_ID}] ürün tohumu hatası: {e}")
        return
    try:
        await mark_featured_once(db)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{SEED_ID}] öne çıkarma hatası: {e}")
    try:
        from routes.upload import store_image_bytes
    except Exception as e:  # noqa: BLE001
        logger.error(f"[{SEED_ID}] görsel deposu yüklenemedi: {e}")
        return
    for delay in delays:
        if delay:
            await asyncio.sleep(delay)
        try:
            got = await fetch_missing_images(db, store_image=store_image_bytes)
        except Exception as e:  # noqa: BLE001
            logger.error(f"[{SEED_ID}] görsel indirme hatası: {e}")
            continue
        if got:
            logger.warning(f"[{SEED_ID}] üretici görselleri: {got}")
        if not await pending_image_products(db):
            return
