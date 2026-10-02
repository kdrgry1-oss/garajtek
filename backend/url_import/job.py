"""URL'den Ürün Aktar — arka plan işi, ürün yazımı ve kaldırma.

İş uygulama sürecinin olay döngüsünde (asyncio görevi) çalışır → localdb'nin tek-süreç kilidiyle
çakışmaz. Aynı anda yalnız BİR iş çalışır; ilerleme db.url_import_jobs belgesine yazılır ve
panel bu belgeyi yoklar (GET /api/admin/url-import/jobs/{id}).

Her içe aktarılan ürün:
  demo=True, seed_source="url_import_v1", noindex=True, source_url, source_host,
  image_credit="Görsel: <host>", stok 10 (kaynakta "stokta yok" ise 0), SKU yoksa IMP-xxxxxxxx.
Aynı source_url yeniden aktarılırsa yeni ürün açılmaz, mevcut kayıt güncellenir (eski görseller silinir).
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional
from urllib.parse import urlsplit

from . import SEED_SOURCE
from .catmap import CategoryMapper
from .fetcher import BlockedURL, FetchError, Fetcher, check_url_syntax
from .parser import ProductData, clean_url, parse_listing, parse_product, same_site
from .sanitize import text_of
from .specs_map import map_specs

logger = logging.getLogger("url_import")

MAX_PRODUCTS_PER_JOB = 200
MAX_URLS = 50
MAX_PAGES_PER_LISTING = 10
MAX_IMAGES = 6
MAX_IMAGE_SIDE = 1600
MIN_IMAGE_SIDE = 120
MAX_IMAGE_PIXELS = 40_000_000
IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/pjpeg", "image/png", "image/webp"}
DEFAULT_STOCK = 10

_RUNNING: Dict[str, asyncio.Task] = {}

CreateProduct = Callable[[dict], Awaitable[dict]]
StoreImage = Callable[..., Awaitable[dict]]
DeleteFile = Callable[[dict], Awaitable[None]]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── seçenekler ──────────────────────────────────────────────────────────────

def validate_options(payload: dict) -> dict:
    """Panel isteğini doğrular. Hatada ValueError (Türkçe)."""
    raw = payload.get("urls")
    if isinstance(raw, str):
        raw = raw.splitlines()
    urls: List[str] = []
    for line in raw or []:
        u = str(line or "").strip()
        if not u or u.startswith("#"):
            continue
        if not re.match(r"^[a-z][a-z0-9+.-]*:", u, re.I):  # şemasız ("www.x.com/...") → https
            u = "https://" + u
        check_url_syntax(u)  # BlockedURL → ValueError'a çevrilir (çağıran)
        if u not in urls:
            urls.append(u)
    if not urls:
        raise ValueError("En az bir URL girin")
    if len(urls) > MAX_URLS:
        raise ValueError(f"En çok {MAX_URLS} URL girilebilir")
    mode = str(payload.get("category_mode") or "auto")
    if mode not in ("auto", "fixed"):
        raise ValueError("Geçersiz kategori modu")
    cat = str(payload.get("category_id") or "").strip()
    if mode == "fixed" and not cat:
        raise ValueError("Sabit kategori modunda bir kategori seçin")
    try:
        _m = payload.get("max_per_category")
        mpc = 30 if _m in (None, "") else int(_m)
    except (TypeError, ValueError):
        raise ValueError("Kategori başına ürün sayısı sayı olmalı")
    if not 1 <= mpc <= MAX_PRODUCTS_PER_JOB:
        raise ValueError(f"Kategori başına ürün sayısı 1–{MAX_PRODUCTS_PER_JOB} arası olmalı")

    def _num(key, lo, hi):
        v = payload.get(key)
        if v in (None, ""):
            return None
        try:
            n = float(str(v).replace(",", "."))
        except ValueError:
            raise ValueError(f"{key}: sayı olmalı")
        if not lo <= n <= hi:
            raise ValueError(f"{key}: {lo}–{hi} arası olmalı")
        return n

    return {
        "urls": urls,
        "category_mode": mode,
        "category_id": cat,
        "max_per_category": mpc,
        "import_images": payload.get("import_images", True) is not False,
        "price_multiplier": _num("price_multiplier", 0.01, 100),
        "fixed_price": _num("fixed_price", 0.01, 100_000_000),
        "publish": payload.get("publish", True) is not False,
        "demo": True,  # zorunlu: bu araçla aktarılan her şey demo etiketlidir
    }


# ── görsel ──────────────────────────────────────────────────────────────────

def convert_image(data: bytes, content_type: str) -> bytes:
    """İçerik türünü ve Pillow ile gerçek biçimi doğrular, WebP'ye (≤1600 px) çevirir. Hatada ValueError."""
    from PIL import Image, ImageOps

    ct = (content_type or "").split(";")[0].strip().lower()
    if ct not in IMAGE_TYPES:
        raise ValueError(f"Görsel türü kabul edilmedi ({ct or 'bilinmiyor'})")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            fmt = (probe.format or "").upper()
            w, h = probe.size
            probe.verify()
    except Exception as e:  # noqa: BLE001
        raise ValueError("Görsel çözülemedi") from e
    if fmt not in ("JPEG", "MPO", "PNG", "WEBP"):
        raise ValueError(f"Görsel biçimi kabul edilmedi ({fmt or '?'})")
    if w * h > MAX_IMAGE_PIXELS:
        raise ValueError("Görsel çözünürlüğü çok yüksek")
    if max(w, h) < MIN_IMAGE_SIDE:
        raise ValueError("Görsel çok küçük (ikon/logo)")
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        im = ImageOps.exif_transpose(im)
        im = im.convert("RGBA" if im.mode in ("RGBA", "LA", "P") else "RGB")
        im.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        out = io.BytesIO()
        im.save(out, "WEBP", quality=82, method=4)
    return out.getvalue()


# ── iş ──────────────────────────────────────────────────────────────────────

class ImportJob:
    def __init__(self, db, job_id: str, opts: dict, *, create_product: CreateProduct, store_image: StoreImage,
                 delete_file: DeleteFile, fetcher: Fetcher, user: Optional[dict] = None):
        self.db = db
        self.id = job_id
        self.opts = opts
        self.create_product = create_product
        self.store_image = store_image
        self.delete_file = delete_file
        self.fetcher = fetcher
        self.user = user or {}
        self.seen_products: set = set()
        self.processed = 0
        self.counters = {"urls": len(opts["urls"]), "found": 0, "imported": 0, "updated": 0, "failed": 0,
                         "skipped": 0, "images": 0}
        self.url_log: List[dict] = []
        self.items: List[dict] = []
        self.mapper: Optional[CategoryMapper] = None
        self.spec_cfg: Optional[dict] = None
        self._last_save = 0.0

    # ilerleme kaydı
    async def save(self, *, status: Optional[str] = None, force: bool = True, **extra):
        loop = asyncio.get_running_loop()
        if not force and loop.time() - self._last_save < 0.5:
            return
        self._last_save = loop.time()
        upd = {"counters": self.counters, "url_log": self.url_log, "items": self.items, "updated_at": _now(), **extra}
        if status:
            upd["status"] = status
        await self.db.url_import_jobs.update_one({"id": self.id}, {"$set": upd})

    async def cancelled(self) -> bool:
        doc = await self.db.url_import_jobs.find_one({"id": self.id}, {"_id": 0, "cancel_requested": 1})
        return bool((doc or {}).get("cancel_requested"))

    async def run(self):
        await self.save(status="running", started_at=_now())
        try:
            cats = await self.db.categories.find({}, {"_id": 0, "id": 1, "name": 1, "slug": 1, "parent_id": 1,
                                                       "is_active": 1}).to_list(5000)
            self.mapper = CategoryMapper(cats)
            try:
                import product_specs as _ps
                self.spec_cfg = await _ps.get_config(self.db)
            except Exception:  # noqa: BLE001
                self.spec_cfg = {"fields": []}
            for url in self.opts["urls"]:
                if self.processed >= MAX_PRODUCTS_PER_JOB or await self.cancelled():
                    break
                await self._handle_input(url)
                await self.save()
            status = "cancelled" if await self.cancelled() else "done"
            if self.processed >= MAX_PRODUCTS_PER_JOB:
                self.url_log.append({"url": "", "kind": "info", "status": "info",
                                     "message": f"İş başına en çok {MAX_PRODUCTS_PER_JOB} ürün sınırına ulaşıldı"})
            await self.save(status=status, finished_at=_now())
        except Exception as e:  # noqa: BLE001
            logger.exception("url import job failed")
            await self.save(status="error", finished_at=_now(), error=str(e)[:300])
        finally:
            await self.fetcher.close()

    async def _handle_input(self, url: str):
        entry = {"url": url, "kind": "?", "status": "running", "found": 0, "message": ""}
        self.url_log.append(entry)
        try:
            res = await self.fetcher.fetch(url)
        except (FetchError, BlockedURL) as e:
            entry.update(status="failed", message=str(e))
            self.counters["failed"] += 1
            return
        pd = parse_product(res.body, res.url, res.charset)
        listing = parse_listing(res.body, res.url, res.charset)
        is_product = pd.signals >= 2 or (pd.signals == 1 and len(listing.product_links) < 4) or \
            (pd.is_product and not listing.product_links)
        if is_product and pd.is_product:
            entry["kind"] = "product"
            entry["found"] = 1
            self.counters["found"] += 1
            await self._handle_product(res.url, pd=pd, hints=[])
            entry["status"] = "ok"
            return
        if not listing.product_links:
            entry.update(kind="?", status="failed", message="Sayfada ürün ya da ürün listesi bulunamadı")
            self.counters["failed"] += 1
            return
        entry["kind"] = "listing"
        entry["method"] = listing.method
        hints = list(listing.breadcrumb) + [listing.title,
                                            urlsplit(res.url).path.strip("/").split("/")[-1].replace("-", " ")]
        queue: List[str] = []
        page, cur = 1, listing
        while True:
            for u in cur.product_links:
                if u not in queue and len(queue) < self.opts["max_per_category"]:
                    queue.append(u)
            if len(queue) >= self.opts["max_per_category"] or not cur.next_page or page >= MAX_PAGES_PER_LISTING:
                break
            page += 1
            try:
                nres = await self.fetcher.fetch(cur.next_page)
            except (FetchError, BlockedURL) as e:
                entry["message"] = f"{page}. sayfa alınamadı: {e}"
                break
            nxt = parse_listing(nres.body, nres.url, nres.charset, page_no=page)
            if not set(nxt.product_links) - set(queue):
                break
            cur = nxt
        entry["found"] = len(queue)
        entry["pages"] = page
        self.counters["found"] += len(queue)
        await self.save()
        for u in queue:
            if self.processed >= MAX_PRODUCTS_PER_JOB or await self.cancelled():
                break
            await self._handle_product(u, pd=None, hints=hints)
            await self.save(force=False)
        entry["status"] = "ok"

    def _price(self, pd: ProductData):
        o = self.opts
        if o.get("fixed_price"):
            return round(float(o["fixed_price"]), 2), None
        if pd.price is None:
            return None, None
        mult = o.get("price_multiplier") or 1.0
        new = round(pd.price * mult, 2)
        old = round(pd.old_price * mult, 2) if pd.old_price else None
        if old and old > new:
            return old, new
        return new, None

    async def _handle_product(self, url: str, *, pd: Optional[ProductData], hints: List[str]):
        key = clean_url(url)
        if key in self.seen_products:
            return
        self.seen_products.add(key)
        self.processed += 1
        item: Dict[str, Any] = {"source_url": key, "status": "running", "warnings": []}
        self.items.append(item)
        try:
            if pd is None:
                res = await self.fetcher.fetch(url)
                pd = parse_product(res.body, res.url, res.charset)
                url = res.url
            if not pd.is_product:
                item.update(status="skipped", error="Ürün sayfası değil (ad/fiyat/ürün işareti bulunamadı)")
                self.counters["skipped"] += 1
                return
            await self._save_product(url, pd, hints, item)
        except (FetchError, BlockedURL) as e:
            item.update(status="failed", error=str(e))
            self.counters["failed"] += 1
        except Exception as e:  # noqa: BLE001
            logger.exception("url import product failed: %s", url)
            item.update(status="failed", error=f"Beklenmeyen hata: {str(e)[:200]}")
            self.counters["failed"] += 1

    async def _download_images(self, pd: ProductData, source_url: str, host: str, item: dict) -> List[dict]:
        out: List[dict] = []
        if not self.opts["import_images"]:
            return out
        errors = 0
        for n, img_url in enumerate(pd.images):
            if len(out) >= MAX_IMAGES or errors >= 6:
                break
            try:
                r = await self.fetcher.fetch(img_url, kind="image")
                webp = await asyncio.to_thread(convert_image, r.body, r.content_type)
            except (FetchError, BlockedURL, ValueError) as e:
                errors += 1
                if len(item["warnings"]) < 8:
                    item["warnings"].append(f"Görsel atlandı ({img_url.rsplit('/', 1)[-1][:60]}): {e}")
                continue
            res = await self.store_image(
                webp, "image/webp", "webp", f"import-{host}-{len(out) + 1}.webp",
                extra={"demo": True, "seed_source": SEED_SOURCE, "source_page": source_url, "source_image": img_url,
                       "import_job_id": self.id})
            out.append({"url": res.get("url"), "path": res.get("path")})
        return out

    async def _save_product(self, url: str, pd: ProductData, hints: List[str], item: dict):
        o = self.opts
        source_url = clean_url(pd.canonical) if pd.canonical and same_site(pd.canonical, url) else clean_url(url)
        host = (urlsplit(source_url).hostname or "").lower()
        host_disp = host[4:] if host.startswith("www.") else host
        item["source_url"] = source_url
        item["name"] = pd.name
        if pd.currency and pd.currency not in ("TRY", "TL", "YTL"):
            item["warnings"].append(f"Kaynak para birimi {pd.currency} — fiyat dönüştürülmedi (çarpan kullanın)")
        price, sale = self._price(pd)
        if price is None:
            item["warnings"].append("Fiyat bulunamadı — ürün taslak (yayında değil) olarak kaydedildi")

        # kategori
        cat_ids: List[str] = []
        cat_name = ""
        if o["category_mode"] == "fixed":
            if self.mapper and o["category_id"] in self.mapper.by_id:
                cat_ids = self.mapper.ancestors(o["category_id"])
                cat_name = self.mapper.by_id[o["category_id"]].get("name") or ""
            item["category_source"] = "seçilen"
        else:
            # önce ürünün kendi kırıntısı + adı; eşleşmezse liste sayfasının bağlamı (başlık/kırıntı/slug)
            m = self.mapper.best(pd.breadcrumb, pd.name) if self.mapper else None
            if m is None and self.mapper and hints:
                m = self.mapper.best(pd.breadcrumb, pd.name, hints)
            if m:
                cat_ids, cat_name = m["ids"], m["name"]
                item["category_source"] = "otomatik"
            elif o["category_id"] and self.mapper and o["category_id"] in self.mapper.by_id:
                cat_ids = self.mapper.ancestors(o["category_id"])
                cat_name = self.mapper.by_id[o["category_id"]].get("name") or ""
                item["category_source"] = "yedek"
            else:
                item["warnings"].append("Kategori eşleşmedi — kategorisiz kaydedildi")
        item["category"] = cat_name

        specs, extras, meta = map_specs(pd.spec_rows, self.spec_cfg or {"fields": []})
        brand = (pd.brand or meta.get("brand") or "").strip()[:80]
        sku = (pd.sku or meta.get("sku") or "").strip()[:60]
        if not sku:
            sku = "IMP-" + hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:8].upper()
        gtin = (pd.gtin or meta.get("gtin") or "").strip()[:20]
        desc = pd.description_html or ""
        plain = text_of(desc)
        stock = 0 if pd.availability == "out" else DEFAULT_STOCK
        active = bool(o["publish"]) and price is not None

        existing = await self.db.products.find_one({"source_url": source_url, "seed_source": SEED_SOURCE},
                                                   {"_id": 0, "id": 1, "slug": 1})
        images = await self._download_images(pd, source_url, host_disp, item)
        if self.opts["import_images"] and not images:
            item["warnings"].append("Hiç görsel indirilemedi")
        img_urls = [x["url"] for x in images if x.get("url")]
        self.counters["images"] += len(img_urls)

        fields = {
            "name": pd.name, "brand": brand, "manufacturer": brand,
            "price": float(price or 0), "sale_price": float(sale) if sale else None,
            "description": desc, "short_description": plain[:300],
            "images": img_urls, "stock": stock, "stock_code": sku, "sku": sku, "is_active": active,
            "categories": cat_ids[:1], "category_id": cat_ids[0] if cat_ids else "", "category_name": cat_name,
            "vat_rate": 20,
        }
        tag = {
            "demo": True, "seed_source": SEED_SOURCE, "noindex": True,
            "source_url": source_url, "source_host": host_disp, "image_credit": f"Görsel: {host_disp}",
            "source_platform": pd.platform, "import_job_id": self.id, "imported_at": _now(),
            "category_ids": cat_ids, "specs": specs, "extra_specs": extras, "gtin": gtin,
            "meta_title": pd.name[:70], "meta_description": plain[:155],
            "cod_disabled": False, "vat_included": True,
        }
        if existing:
            pid = existing["id"]
            await self.db.products.update_one({"id": pid}, {"$set": {**fields, **tag, "updated_at": _now()}})
            item["status"] = "updated"
            self.counters["updated"] += 1
        else:
            res = await self.create_product(dict(fields))
            pid = res.get("id")
            if not pid:
                raise RuntimeError("Ürün oluşturulamadı")
            await self.db.products.update_one({"id": pid}, {"$set": tag})
            item["status"] = "imported"
            self.counters["imported"] += 1
        # aynı sayfanın eski görselleri (yeniden aktarım) → sil
        new_paths = {x.get("path") for x in images}
        old = await self.db.files.find({"seed_source": SEED_SOURCE, "source_page": source_url},
                                       {"_id": 0}).to_list(200)
        for rec in old:
            if rec.get("storage_path") not in new_paths and rec.get("import_job_id") != self.id:
                try:
                    await self.delete_file(rec)
                except Exception:  # noqa: BLE001
                    pass
        doc = await self.db.products.find_one({"id": pid}, {"_id": 0, "slug": 1})
        item.update(product_id=pid, slug=(doc or {}).get("slug") or "", price=fields["price"], sale_price=sale,
                    images=len(img_urls), is_active=active, specs=len(specs), extra_specs=len(extras))


# ── iş yönetimi ─────────────────────────────────────────────────────────────

def running_job_id() -> Optional[str]:
    for jid, t in list(_RUNNING.items()):
        if t.done():
            _RUNNING.pop(jid, None)
        else:
            return jid
    return None


async def start_job(db, opts: dict, *, create_product: CreateProduct, store_image: StoreImage,
                    delete_file: DeleteFile, fetcher: Optional[Fetcher] = None, user: Optional[dict] = None) -> str:
    if running_job_id():
        raise RuntimeError("Zaten çalışan bir içe aktarma işi var")
    job_id = uuid.uuid4().hex[:12]
    await db.url_import_jobs.insert_one({
        "id": job_id, "status": "queued", "options": opts, "created_at": _now(),
        "created_by": (user or {}).get("email") or (user or {}).get("id") or "",
        "counters": {}, "url_log": [], "items": [], "cancel_requested": False,
    })
    job = ImportJob(db, job_id, opts, create_product=create_product, store_image=store_image,
                    delete_file=delete_file, fetcher=fetcher or Fetcher(), user=user)
    _RUNNING[job_id] = asyncio.create_task(job.run())
    return job_id


async def get_job(db, job_id: str) -> Optional[dict]:
    doc = await db.url_import_jobs.find_one({"id": job_id}, {"_id": 0})
    if doc and doc.get("status") in ("queued", "running") and job_id not in _RUNNING:
        # süreç yeniden başladı → iş yarım kaldı
        await db.url_import_jobs.update_one({"id": job_id}, {"$set": {"status": "interrupted"}})
        doc["status"] = "interrupted"
    if doc and job_id in _RUNNING and _RUNNING[job_id].done():
        _RUNNING.pop(job_id, None)
    return doc


async def import_status(db) -> dict:
    q = {"seed_source": SEED_SOURCE}
    hosts: Dict[str, int] = {}
    async for p in db.products.find(q, {"_id": 0, "source_host": 1}):
        h = p.get("source_host") or "?"
        hosts[h] = hosts.get(h, 0) + 1
    return {"products": sum(hosts.values()), "files": await db.files.count_documents(q), "hosts": hosts,
            "running_job": running_job_id()}


async def remove_imports(db, delete_file: DeleteFile) -> dict:
    """YALNIZ url_import_v1 etiketli ürünleri ve indirilen görsellerini siler."""
    q = {"seed_source": SEED_SOURCE}
    files = await db.files.find(q, {"_id": 0}).to_list(20000)
    for rec in files:
        try:
            await delete_file(rec)
        except Exception:  # noqa: BLE001
            logger.warning("url import file delete failed: %s", rec.get("id"))
    await db.files.delete_many(q)
    pr = await db.products.delete_many({**q, "demo": True})
    return {"removed_products": pr.deleted_count, "removed_files": len(files)}
