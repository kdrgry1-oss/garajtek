"""Toplu site aktarımı — sahibin talebiyle iki tedarik sitesindeki TÜM ürünler.

Sahip (Salih Sezgin / USTAELLER) bu sitelerdeki ürünlerin aynılarını sattığını ve içerik
sorumluluğunu üstlendiğini belirterek tamamının yayına alınmasını istedi (12.10.2026).

Akış (sunucuda, uygulama sürecinde arka plan görevi — localdb tek-süreç kuralı):
  1. Keşif (site başına bir kez): robots.txt → Sitemap satırları, yoksa /sitemap.xml ve
     /sitemap_index.xml; sitemap index'leri açılır. Ürün sitemap'i varsa yalnız o kullanılır.
     Hiç sitemap yoksa ana sayfadan başlayan sınırlı tarama (liste sayfalarındaki ürün linkleri).
  2. Bulunan adresler db.site_import_queue'ya yazılır (status: pending/done/skipped/failed).
  3. Her site için ayrı işçi kuyruğu sırayla işler (host başına ≤1 istek/sn). Her ürün
     url_import.job.ImportJob._handle_product ile yazılır: fiyat = kaynak × 1,10, yayında,
     demo DEĞİL, indekslenir, en çok 4 görsel WebP olarak kendi depomuza indirilir.
  4. Servis yeniden başlarsa (her deploy) kalan 'pending' adreslerden devam eder; aynı
     adres ikinci kez ürün açmaz (source_url ile güncellenir).

Kapatma: SITE_IMPORT_DISABLED=1. Durum: db.site_import_state (id=SEED_SOURCE).
"""
from __future__ import annotations

import asyncio
import gzip
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlsplit

from .fetcher import BlockedURL, FetchError, Fetcher
from .parser import NON_PRODUCT_PATH, PRODUCT_PATH, clean_url, parse_listing

logger = logging.getLogger("site_bulk")

SEED_SOURCE = "site_import_v1"
SITES = ["https://www.algikitelli.com.tr", "https://www.grayzer.net"]
PRICE_MULTIPLIER = 1.10
MAX_IMAGES = 4
MAX_ATTEMPTS = 3
MAX_SITEMAPS = 60
MAX_URLS_PER_SITE = 20000
MAX_CRAWL_PAGES = 400
START_DELAY = 90  # açılıştaki diğer tohumlar (kategori, fatura ürünleri) önce bitsin

LOC_RE = re.compile(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^<\]\s]+)\s*(?:\]\]>)?\s*</loc>", re.I)
PRODUCT_SITEMAP_RE = re.compile(r"(product|urun|item)", re.I)
SKIP_SITEMAP_RE = re.compile(r"(categor|kategori|brand|marka|blog|page|sayfa|post|tag|image|video|news)", re.I)
# etiket / arama / SEO açılış sayfaları (ör. grayzer.net/meta-etiket/duz-keski-fiyat) ürün değildir
TAG_PATH_RE = re.compile(r"/(?:[^/]*-)?(etiket|etiketler|tag|tags|arama|search|filtre|filter|marka|markalar|"
                         r"brand|brands)(?:-[^/]*)?/", re.I)
PRODUCT_PATH_MIN = 20  # sitede bu kadar /urun/ biçimli adres varsa yalnız onlar ürün sayılır
ASSET_RE = re.compile(r"\.(jpe?g|png|gif|webp|svg|pdf|css|js|xml|zip)(\?|$)", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _same_host(url: str, base: str) -> bool:
    return _host(url) == _host(base)


def _body_text(body: bytes) -> str:
    if body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except OSError:
            return ""
    return body.decode("utf-8", "replace")


def parse_sitemap(text: str) -> Tuple[List[str], bool]:
    """(loc listesi, index mi)."""
    locs = [x.replace("&amp;", "&") for x in LOC_RE.findall(text)]
    return locs, "<sitemapindex" in text[:2000].lower()


def is_candidate(url: str, base: str) -> bool:
    if not _same_host(url, base) or ASSET_RE.search(url):
        return False
    path = urlsplit(url).path or "/"
    if TAG_PATH_RE.search(path.rsplit("/", 1)[0] + "/"):  # yalnız klasör kısmı (son parça ürün adı olabilir)
        return False
    if PRODUCT_PATH.search(url):
        return True
    return path not in ("", "/") and not NON_PRODUCT_PATH.search(path)


async def discover_sitemap(fetcher: Fetcher, base: str) -> List[str]:
    roots: List[str] = []
    try:
        r = await fetcher.fetch(urljoin(base, "/robots.txt"), kind="xml")
        for line in _body_text(r.body).splitlines():
            k, _, v = line.partition(":")
            if k.strip().lower() == "sitemap" and v.strip():
                roots.append(v.strip())
    except (FetchError, BlockedURL) as e:
        logger.info("robots.txt alınamadı (%s): %s", base, e)
    if not roots:
        roots = [urljoin(base, "/sitemap.xml"), urljoin(base, "/sitemap_index.xml")]

    product_urls: List[str] = []
    other_urls: List[str] = []
    seen_maps: set = set()
    todo: List[Tuple[str, bool]] = [(u, False) for u in roots]  # (adres, ürün sitemap'i mi)
    while todo and len(seen_maps) < MAX_SITEMAPS:
        sm, is_prod = todo.pop(0)
        if sm in seen_maps:
            continue
        seen_maps.add(sm)
        try:
            r = await fetcher.fetch(sm, kind="xml", max_bytes=40 * 1024 * 1024)
        except (FetchError, BlockedURL) as e:
            logger.info("sitemap alınamadı %s: %s", sm, e)
            continue
        locs, is_index = parse_sitemap(_body_text(r.body))
        if is_index:
            prods = [u for u in locs if PRODUCT_SITEMAP_RE.search(u.rsplit("/", 1)[-1])]
            for u in (prods or [u for u in locs if not SKIP_SITEMAP_RE.search(u.rsplit("/", 1)[-1])] or locs):
                todo.append((u, bool(prods)))
            continue
        name_is_prod = is_prod or bool(PRODUCT_SITEMAP_RE.search(sm.rsplit("/", 1)[-1]))
        bucket = product_urls if name_is_prod else other_urls
        bucket.extend(u for u in locs if is_candidate(u, base))
    urls = product_urls or other_urls
    strict = [u for u in urls if PRODUCT_PATH.search(u)]
    if len(strict) >= PRODUCT_PATH_MIN:
        urls = strict
    out, seen = [], set()
    for u in urls:
        k = clean_url(u)
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out[:MAX_URLS_PER_SITE]


async def discover_crawl(fetcher: Fetcher, base: str) -> List[str]:
    """Sitemap yoksa: ana sayfadan liste sayfalarını gez, ürün linklerini topla."""
    from bs4 import BeautifulSoup

    found: List[str] = []
    seen_found: set = set()
    queue: List[str] = [base.rstrip("/") + "/"]
    visited: set = set()
    while queue and len(visited) < MAX_CRAWL_PAGES:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        try:
            r = await fetcher.fetch(url)
        except (FetchError, BlockedURL):
            continue
        listing = parse_listing(r.body, r.url, r.charset)
        for u in listing.product_links:
            k = clean_url(u)
            if k not in seen_found:
                seen_found.add(k)
                found.append(k)
        if listing.next_page and listing.next_page not in visited:
            queue.insert(0, listing.next_page)
        soup = BeautifulSoup(r.body, "html.parser")
        for a in soup.find_all("a", href=True):
            u = clean_url(urljoin(r.url, a["href"]))
            if not _same_host(u, base) or ASSET_RE.search(u) or u in visited or u in seen_found:
                continue
            path = urlsplit(u).path
            if PRODUCT_PATH.search(u):
                seen_found.add(u)
                found.append(u)
            elif re.search(r"/(kategori|category|urunler|collections?)(/|$)", path, re.I) or path.count("/") <= 2:
                if u not in queue:
                    queue.append(u)
    return found[:MAX_URLS_PER_SITE]


async def _enqueue(db, host: str, urls: List[str]) -> int:
    n = 0
    for u in urls:
        if await db.site_import_queue.find_one({"url": u}, {"_id": 1}):
            continue
        await db.site_import_queue.insert_one({"url": u, "host": host, "status": "pending", "attempts": 0,
                                               "created_at": _now()})
        n += 1
    return n


async def _state(db) -> dict:
    return await db.site_import_state.find_one({"id": SEED_SOURCE}, {"_id": 0}) or {"id": SEED_SOURCE}


async def _set_state(db, **kw):
    await db.site_import_state.update_one({"id": SEED_SOURCE}, {"$set": {"id": SEED_SOURCE, **kw,
                                                                          "updated_at": _now()}}, upsert=True)


def make_job(db, *, create_product, store_image, delete_file, fetcher: Fetcher):
    from .job import ImportJob

    opts = {"urls": [], "category_mode": "auto", "category_id": "", "max_per_category": 1,
            "import_images": True, "price_multiplier": PRICE_MULTIPLIER, "fixed_price": None,
            "publish": True, "demo": False, "seed_source": SEED_SOURCE, "max_images": MAX_IMAGES}
    return ImportJob(db, "site-" + uuid.uuid4().hex[:8], opts, create_product=create_product,
                     store_image=store_image, delete_file=delete_file, fetcher=fetcher)


async def _prepare_job(db, job):
    from .catmap import CategoryMapper

    cats = await db.categories.find({}, {"_id": 0, "id": 1, "name": 1, "slug": 1, "parent_id": 1,
                                         "is_active": 1}).to_list(5000)
    job.mapper = CategoryMapper(cats)
    try:
        import product_specs as _ps
        job.spec_cfg = await _ps.get_config(db)
    except Exception:  # noqa: BLE001
        job.spec_cfg = {"fields": []}


async def process_host(db, host: str, job) -> Dict[str, int]:
    counts = {"imported": 0, "updated": 0, "skipped": 0, "failed": 0}
    tried: List[str] = []  # bu çalıştırmada başarısız olanlar sonraki açılışta yeniden denenir
    while True:
        row = await db.site_import_queue.find_one({"host": host, "status": "pending", "url": {"$nin": tried}},
                                                  {"_id": 0})
        if not row:
            return counts
        job.items.clear()
        before = dict(job.counters)
        await job._handle_product(row["url"], pd=None, hints=[])
        job.seen_products.discard(clean_url(row["url"]))
        item = job.items[-1] if job.items else {"status": "skipped"}
        st = item.get("status")
        upd = {"updated_at": _now(), "product_id": item.get("product_id") or ""}
        if st in ("imported", "updated"):
            upd["status"] = "done"
            counts[st] += 1
        elif st == "skipped":
            upd["status"] = "skipped"
            counts["skipped"] += 1
        else:
            attempts = int(row.get("attempts") or 0) + 1
            upd.update(attempts=attempts, error=str(item.get("error") or "")[:300],
                       status="failed" if attempts >= MAX_ATTEMPTS else "pending")
            counts["failed"] += 1
            tried.append(row["url"])
            if job.counters.get("failed", 0) > before.get("failed", 0) and "HTTP 429" in upd["error"]:
                await asyncio.sleep(60)
        await db.site_import_queue.update_one({"url": row["url"]}, {"$set": upd})


async def cleanup_non_products(db, delete_file) -> dict:
    """Kuyruktaki ürün olmayan adresleri (etiket/SEO sayfaları) atlar, bunlardan açılmış ürünleri ve
    görsellerini siler. Her çalıştırmada güvenle tekrarlanabilir."""
    hosts: Dict[str, List[dict]] = {}
    async for r in db.site_import_queue.find({}, {"_id": 0, "url": 1, "host": 1, "status": 1}):
        hosts.setdefault(r.get("host") or "", []).append(r)
    bad: List[str] = []
    for host, rows in hosts.items():
        base = "https://" + host
        strict = sum(1 for r in rows if PRODUCT_PATH.search(r["url"])) >= PRODUCT_PATH_MIN
        for r in rows:
            if not is_candidate(r["url"], base) or (strict and not PRODUCT_PATH.search(r["url"])):
                bad.append(r["url"])
    removed = files = 0
    for u in bad:
        await db.site_import_queue.update_one({"url": u}, {"$set": {"status": "skipped", "reason": "not_product",
                                                                    "updated_at": _now()}})
        p = await db.products.find_one({"seed_source": SEED_SOURCE, "source_url": u}, {"_id": 0, "id": 1})
        for rec in await db.files.find({"seed_source": SEED_SOURCE, "source_page": u}, {"_id": 0}).to_list(50):
            try:
                await delete_file(rec)
            except Exception:  # noqa: BLE001
                pass
            await db.files.delete_one({"id": rec.get("id")})
            files += 1
        if p:
            await db.products.delete_one({"id": p["id"]})
            removed += 1
    return {"skipped": len(bad), "removed_products": removed, "removed_files": files}


async def run(db, *, create_product, store_image, delete_file, sites: Optional[List[str]] = None,
              fetcher_factory=Fetcher) -> dict:
    sites = sites or SITES
    st = await _state(db)
    discovered = dict(st.get("discovered") or {})
    for base in sites:
        host = _host(base)
        if discovered.get(host):
            continue
        f = fetcher_factory()
        try:
            urls = await discover_sitemap(f, base)
            method = "sitemap"
            if not urls:
                urls = await discover_crawl(f, base)
                method = "crawl"
        finally:
            await f.close()
        added = await _enqueue(db, host, urls)
        discovered[host] = {"method": method, "found": len(urls), "added": added, "at": _now()}
        await _set_state(db, discovered=discovered)
        logger.warning("[%s] %s: %s ile %d adres bulundu", SEED_SOURCE, host, method, len(urls))

    cleaned = await cleanup_non_products(db, delete_file)
    if cleaned["removed_products"] or cleaned["skipped"]:
        logger.warning("[%s] ürün olmayan adresler ayıklandı: %s", SEED_SOURCE, cleaned)

    async def _worker(base):
        f = fetcher_factory()
        try:
            job = make_job(db, create_product=create_product, store_image=store_image,
                           delete_file=delete_file, fetcher=f)
            await _prepare_job(db, job)
            return await process_host(db, _host(base), job)
        finally:
            await f.close()

    results = await asyncio.gather(*[_worker(b) for b in sites], return_exceptions=True)
    summary = {}
    for base, res in zip(sites, results):
        summary[_host(base)] = res if isinstance(res, dict) else {"error": str(res)[:200]}
    await _set_state(db, last_run=summary, finished_at=_now())
    return summary


async def status(db) -> dict:
    out = {"state": await _state(db), "hosts": {}}
    async for r in db.site_import_queue.find({}, {"_id": 0, "host": 1, "status": 1}):
        h = out["hosts"].setdefault(r.get("host") or "?", {})
        h[r.get("status")] = h.get(r.get("status"), 0) + 1
    return out


async def run_startup(db=None) -> None:
    """server.py açılışından arka plan görevi; açılışı asla düşürmez."""
    if (os.environ.get("SITE_IMPORT_DISABLED") or "").strip().lower() in ("1", "true", "yes"):
        return
    await asyncio.sleep(START_DELAY)
    try:
        if db is None:
            from routes.deps import db as _db
            db = _db
        from starlette.requests import Request
        from routes.products import create_product
        from routes.upload import delete_stored_file, store_image_bytes
        req = Request({"type": "http", "method": "POST", "path": f"/startup/{SEED_SOURCE}", "headers": [],
                       "client": ("127.0.0.1", 0)})
        user = {"id": "system", "email": "system@localhost", "is_admin": True, "role": "system",
                "first_name": "Sistem", "last_name": "(site aktarımı)"}
        res = await run(db, create_product=lambda d: create_product(d, req, user),
                        store_image=store_image_bytes, delete_file=delete_stored_file)
        logger.warning("[%s] bitti: %s", SEED_SOURCE, res)
    except Exception as e:  # noqa: BLE001
        logger.exception("[%s] site aktarımı hatası: %s", SEED_SOURCE, e)
