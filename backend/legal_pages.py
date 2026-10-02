# -*- coding: utf-8 -*-
"""Kurumsal / hukuki CMS sayfaları: yer tutucu işleme + idempotent tohumlama.

YER TUTUCULAR (sayfa SUNULURKEN işlenir — DB'deki içerik ham kalır):
  {{sirket.unvan}} {{sirket.adres}} {{sirket.telefon}} {{sirket.eposta}} {{sirket.vergi_dairesi}}
  {{sirket.vkn}} {{sirket.mersis}} {{sirket.kep}} {{sirket.ticaret_sicil}} {{sirket.iban}}
  {{sirket.whatsapp}} {{site.ad}} {{site.url}} {{site.alan_adi}} {{tarih.bugun}}
  + eski şablon anahtarları ({{company_name}}, {{store_name}}, {{address}} …) geriye uyum için.
  Değerler Ayarlar › Şirket Bilgileri'nden (tenant_config) gelir ve HTML-escape edilir;
  Şirket Bilgileri değişince tüm sayfalar kendiliğinden güncellenir.
  {{alici.*}} / {{siparis.*}}: ödeme ekranındaki sözleşme penceresinde (LegalModal) sipariş
  verisiyle doldurulur; normal sayfa görünümünde açıklayıcı metinle değiştirilir.

TOHUMLAMA (ensure_legal_pages — açılışta, süreç başına bir kez):
  • Eksik sayfa oluşturulur (bir kez; admin silerse yeniden dayatılmaz).
  • Mevcut sayfa YALNIZCA el değmemişse güncellenir: seed_hash eşleşmesi (yeni seed) veya
    eski (page_seed_data) şablonla birebir eşleşme. Admin'in düzenlediği sayfaya dokunulmaz.
  • Şirket Bilgileri varsayılanları yalnız BOŞ alanlara ve yalnız bir kez yazılır.
"""
from __future__ import annotations

import hashlib
import html
import re
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

from legal_content import LEGAL_PAGES, LEGAL_SEED_VERSION, SLUG_ALIASES

SEED_STATE_ID = "legal_pages_seed"

# Ayarlar › Şirket Bilgileri için mağaza sahibinin verdiği varsayılanlar. YALNIZ boş alanlara,
# yalnız bir kez yazılır (admin'in girdiği değer asla ezilmez).
COMPANY_DEFAULTS = {
    ("brand", "store_name"): "GarajTek",
    ("company", "legal_name"): "USTAELLER TEKNİK YAPI HIRDAVAT SANAYİ VE TİCARET LİMİTED ŞİRKETİ",
    ("company", "address"): "Mahmutbey Mah. 2453. Sk. No: 46",
    ("company", "city"): "Bağcılar / İstanbul",
    ("company", "tax_office"): "Güneşli",
    ("company", "tax_number"): "8961050800",
    ("contact", "phone"): "0543 579 10 56",
    ("contact", "email"): "info@garajtek.com",
    ("domains", "storefront_url"): "https://garajtek.com",
}
# Bu değerler "boş" sayılır (nötr varsayılanlar).
_NEUTRAL = {("brand", "store_name"): {"Mağaza"}}

# Boş bırakılmış firma alanları sayfada açıkça işaretlenir → sahibi kolayca fark edip doldurur.
_EMPTY_MARKERS = {
    "sirket.unvan": "[Firma Ünvanı]", "sirket.adres": "[Adres]", "sirket.telefon": "[Telefon]",
    "sirket.eposta": "[E-posta]", "sirket.vergi_dairesi": "[Vergi Dairesi]", "sirket.vkn": "[VKN]",
    "sirket.mersis": "[MERSİS No]", "sirket.kep": "[KEP Adresi]",
    "sirket.ticaret_sicil": "[Ticaret Sicil No]", "sirket.iban": "[IBAN]",
    "sirket.whatsapp": "[WhatsApp]", "site.ad": "[Mağaza Adı]", "site.url": "[Site Adresi]",
    "site.alan_adi": "[Alan Adı]",
}

# Admin yardım kutusunda gösterilen liste (anahtar → açıklama).
PLACEHOLDER_HELP = [
    ("sirket.unvan", "Firma ticari ünvanı"),
    ("sirket.adres", "Açık adres (Adres + İl/İlçe)"),
    ("sirket.telefon", "Firma telefonu"),
    ("sirket.eposta", "Firma e-postası"),
    ("sirket.vergi_dairesi", "Vergi dairesi"),
    ("sirket.vkn", "Vergi kimlik no"),
    ("sirket.mersis", "MERSİS no"),
    ("sirket.kep", "KEP adresi"),
    ("sirket.ticaret_sicil", "Ticaret sicil no"),
    ("sirket.iban", "IBAN"),
    ("sirket.whatsapp", "WhatsApp hattı"),
    ("site.ad", "Mağaza / marka adı"),
    ("site.url", "Site adresi (https://…)"),
    ("site.alan_adi", "Alan adı (ör. garajtek.com)"),
    ("tarih.bugun", "Bugünün tarihi"),
]
ORDER_PLACEHOLDER_HELP = [
    ("alici.ad", "Alıcı ad soyad / ünvan"), ("alici.adres", "Teslimat adresi"),
    ("alici.telefon", "Alıcı telefonu"), ("alici.eposta", "Alıcı e-postası"),
    ("alici.fatura", "Fatura bilgileri"), ("siparis.tarih", "Sipariş tarihi"),
    ("siparis.urunler", "Ürün tablosu"), ("siparis.ara_toplam", "Ürünler toplamı"),
    ("siparis.indirim", "İndirimler"), ("siparis.kargo", "Kargo bedeli"),
    ("siparis.toplam", "Genel toplam"), ("siparis.odeme", "Ödeme yöntemi"),
]

_PH_RE = re.compile(r"\{\{\s*([a-z_]+(?:\.[a-z_]+)?)\s*\}\}")
_ORDER_PREFIXES = ("alici.", "siparis.")
_ORDER_DEFAULT_TEXT = "(sipariş sırasında doldurulur)"
_ORDER_ITEMS_DEFAULT = ("(Sipariş edilen ürünler; adet, birim fiyat ve KDV dahil tutarlarıyla "
                        "sipariş onayı sırasında burada listelenir.)")


def _months_tr(dt: datetime) -> str:
    ay = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül",
          "Ekim", "Kasım", "Aralık"][dt.month - 1]
    return f"{dt.day} {ay} {dt.year}"


def values_from_config(cfg: dict) -> dict:
    """tenant_config → yer tutucu değerleri (ham, escape EDİLMEMİŞ). Boş alan → ''."""
    cfg = cfg or {}
    brand, legal = cfg.get("brand") or {}, cfg.get("company") or {}
    contact, domains = cfg.get("contact") or {}, cfg.get("domains") or {}
    store = (brand.get("store_name") or "").strip()
    url = (domains.get("storefront_url") or "").strip().rstrip("/")
    host = re.sub(r"^https?://", "", url).rstrip("/")
    phone = (contact.get("phone") or "").strip()
    addr = " ".join(x.strip() for x in [legal.get("address") or "", legal.get("district") or "",
                                          legal.get("city") or ""] if x and x.strip())
    v = {
        "sirket.unvan": (legal.get("legal_name") or "").strip(),
        "sirket.adres": addr,
        "sirket.telefon": phone,
        "sirket.telefon_tel": "".join(ch for ch in phone if ch.isdigit() or ch == "+"),
        "sirket.eposta": (contact.get("email") or "").strip(),
        "sirket.vergi_dairesi": (legal.get("tax_office") or "").strip(),
        "sirket.vkn": (legal.get("tax_number") or "").strip(),
        "sirket.mersis": (legal.get("mersis_number") or "").strip(),
        "sirket.kep": (legal.get("kep_address") or "").strip(),
        "sirket.ticaret_sicil": (legal.get("trade_registry_no") or "").strip(),
        "sirket.iban": (legal.get("iban") or "").strip(),
        "sirket.whatsapp": (contact.get("whatsapp") or "").strip(),
        "site.ad": store if store and store != "Mağaza" else "",
        "site.url": url,
        "site.alan_adi": host,
        "tarih.bugun": _months_tr(datetime.now(timezone.utc)),
    }
    v["sirket.adres_url"] = quote(addr) if addr else ""
    if not v["sirket.unvan"]:
        v["sirket.unvan"] = v["site.ad"]
    # Eski (page_seed_data) şablon anahtarları — admin'in elle yazdığı eski içerik de çalışsın.
    legacy = {
        "store_name": v["site.ad"] or "Mağaza", "company_name": v["sirket.unvan"],
        "address": v["sirket.adres"], "phone": phone, "phone_tel": v["sirket.telefon_tel"],
        "email": v["sirket.eposta"], "iban": v["sirket.iban"], "tax_office": v["sirket.vergi_dairesi"],
        "tax_number": v["sirket.vkn"], "mersis_number": v["sirket.mersis"],
        "site": host or "web sitemiz",
    }
    v.update(legacy)
    return v


def render(text, values: dict, *, keep_order_fields: bool = False) -> str:
    """{{anahtar}} → HTML-escape edilmiş değer. Bilinmeyen anahtar olduğu gibi kalır.
    Sipariş alanları keep_order_fields=True ise korunur (LegalModal doldurur)."""
    if not isinstance(text, str) or "{{" not in text:
        return text

    def _sub(m):
        key = m.group(1)
        if key.startswith(_ORDER_PREFIXES):
            if keep_order_fields:
                return "{{" + key + "}}"
            return _ORDER_ITEMS_DEFAULT if key == "siparis.urunler" else _ORDER_DEFAULT_TEXT
        if key not in values:
            return m.group(0)
        val = values.get(key) or ""
        if not val:
            val = _EMPTY_MARKERS.get(key, "")
        if key == "sirket.adres_url":
            return val                      # zaten URL-encode
        return html.escape(val, quote=True)

    return _PH_RE.sub(_sub, text)


async def placeholder_values(db) -> dict:
    from tenant_config import get_tenant_config
    try:
        cfg = await get_tenant_config(db)
    except Exception:
        cfg = {}
    return values_from_config(cfg)


async def render_page(db, page: dict, *, keep_order_fields: bool = False) -> dict:
    vals = await placeholder_values(db)
    out = dict(page)
    for k in ("title", "content", "meta_title", "meta_description"):
        if isinstance(out.get(k), str):
            out[k] = render(out[k], vals, keep_order_fields=keep_order_fields)
    for k in ("seed_hash", "seed_version", "seed_key"):
        out.pop(k, None)
    return out


def canonical_slug(slug: str) -> str:
    return SLUG_ALIASES.get((slug or "").strip().lower(), slug)


# ─────────────────────────────────────────────────────────────────── tohumlama
def content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


_LEGACY_RX_CACHE: dict = {}


def _legacy_regex(slug: str):
    """Eski seed şablonundan (page_seed_data) — yer tutucular joker olacak şekilde — regex.
    Eski seed, değerleri ekleme anında içeriğe gömüyordu; bu yüzden birebir karşılaştırma
    yerine şablon eşleşmesi yapılır."""
    if slug in _LEGACY_RX_CACHE:
        return _LEGACY_RX_CACHE[slug]
    rx = None
    try:
        from page_seed_data import DEFAULT_PAGES as _OLD
        tpl = next((p.get("content") or "" for p in _OLD if p.get("slug") == slug), None)
        if tpl:
            parts = re.split(r"\{\{[a-z_]+\}\}", _norm_ws(tpl))
            rx = re.compile("[^<>]*?".join(re.escape(p) for p in parts), re.S)
    except Exception:
        rx = None
    _LEGACY_RX_CACHE[slug] = rx
    return rx


def is_pristine(existing: dict) -> bool:
    """Sayfa admin tarafından DEĞİŞTİRİLMEMİŞ mi? (yeni seed hash'i ya da eski seed şablonu)"""
    content = existing.get("content") or ""
    if existing.get("seed_hash"):
        return content_hash(content) == existing["seed_hash"]
    rx = _legacy_regex(existing.get("slug") or "")
    return bool(rx and rx.fullmatch(_norm_ws(content)))


def _seed_doc(p: dict, now: str) -> dict:
    return {
        "title": p["title"], "slug": p["slug"], "content": p["content"],
        "meta_title": p.get("meta_title", ""), "meta_description": p.get("meta_description", ""),
        "is_active": True, "updated_at": now,
        "seed_key": p["slug"], "seed_version": LEGAL_SEED_VERSION,
        "seed_hash": content_hash(p["content"]),
    }


async def ensure_legal_pages(db, *, force_slugs=None) -> dict:
    """İdempotent kurulum/yükseltme. force_slugs: admin'in açıkça 'varsayılana döndür' dediği
    slug'lar (bunlar düzenlenmiş olsa bile yeniden yazılır)."""
    force_slugs = set(force_slugs or ())
    state = await db.settings.find_one({"id": SEED_STATE_ID}, {"_id": 0}) or {}
    created_before = set(state.get("created_slugs") or [])
    now = datetime.now(timezone.utc).isoformat()
    res = {"created": [], "updated": [], "kept_customized": [], "unchanged": [], "skipped_deleted": []}
    for p in LEGAL_PAGES:
        slug = p["slug"]
        existing = await db.pages.find_one({"slug": slug}, {"_id": 0})
        if not existing:
            if slug in created_before and slug not in force_slugs:
                res["skipped_deleted"].append(slug)       # admin silmiş → yeniden dayatma
                continue
            doc = _seed_doc(p, now)
            doc["id"] = str(uuid.uuid4())
            doc["created_at"] = now
            await db.pages.insert_one(doc)
            created_before.add(slug)
            res["created"].append(slug)
            continue
        created_before.add(slug)
        same = (existing.get("seed_hash") == content_hash(p["content"])
                and existing.get("seed_version") == LEGAL_SEED_VERSION)
        if same and slug not in force_slugs:
            res["unchanged" if is_pristine(existing) else "kept_customized"].append(slug)
            continue
        if slug in force_slugs or is_pristine(existing):
            doc = _seed_doc(p, now)
            if existing.get("is_active") is False:
                doc["is_active"] = False                 # admin'in pasif kararı korunur
            await db.pages.update_one({"slug": slug}, {"$set": doc})
            res["updated"].append(slug)
        else:
            res["kept_customized"].append(slug)
    await db.settings.update_one(
        {"id": SEED_STATE_ID},
        {"$set": {"version": LEGAL_SEED_VERSION, "created_slugs": sorted(created_before),
                  "last_run": now}},
        upsert=True,
    )
    return res


async def apply_company_defaults(db) -> dict:
    """Şirket Bilgileri'ni sahibin verdiği değerlerle doldurur — YALNIZ boş alanlar, YALNIZ
    bir kez (sonradan admin bir alanı bilerek boşaltırsa tekrar doldurulmaz)."""
    state = await db.settings.find_one({"id": SEED_STATE_ID}, {"_id": 0}) or {}
    if state.get("company_defaults_applied"):
        return {"applied": [], "reason": "already_applied"}
    from tenant_config import get_tenant_config, migrate_tenant_config, invalidate, legacy_write_through
    await migrate_tenant_config(db, apply=True)          # kanonik belge yoksa eski ayarlardan oluştur
    invalidate(db)
    cfg = await get_tenant_config(db, use_cache=False)
    patch = {}
    for (sec, field), val in COMPANY_DEFAULTS.items():
        cur = str((cfg.get(sec) or {}).get(field) or "").strip()
        if not cur or cur in _NEUTRAL.get((sec, field), set()):
            patch[f"{sec}.{field}"] = val
    if patch:
        await db.settings.update_one({"id": "tenant_config"}, {"$set": patch}, upsert=True)
        invalidate(db)
        try:   # eski tüketiciler (settings.main) için ayna — settings rotasıyla aynı davranış
            full = await get_tenant_config(db, use_cache=False)
            await db.settings.update_one({"id": "main"}, {"$set": legacy_write_through(full),
                                                          "$setOnInsert": {"id": "main"}}, upsert=True)
        except Exception:
            pass
        try:
            from company import invalidate as _co_inv
            _co_inv()
        except Exception:
            pass
    await db.settings.update_one(
        {"id": SEED_STATE_ID},
        {"$set": {"company_defaults_applied": True,
                  "company_defaults_fields": sorted(patch.keys())}},
        upsert=True,
    )
    return {"applied": sorted(patch.keys())}


# footer_template._DEFAULT'un bu sürümden önceki sütunları. Kayıtlı footer bunlarla BİREBİR aynıysa
# (admin "varsayılana sıfırla" demiş ama hiç düzenlememiş) yeni hukuki bağlantılarla güncellenir;
# admin'in düzenlediği footer'a dokunulmaz.
_OLD_FOOTER_LINK_COLUMNS = [
    ("Alışveriş", ["/en-yeniler", "/sale", "/tum-urunler?sort=popular&order=desc", "/tum-urunler", "/karsilastir"]),
    ("Yardım", ["/siparis-takip", "/sayfa/uyelik-islemleri", "/iade-islemleri", "/sayfa/iade-kosullari",
                "/sikca-sorulan-sorular", "/sayfa/iletisim"]),
    ("Kurumsal", ["/sayfa/hakkimizda", "/sayfa/mesafeli-satis", "/sayfa/uyelik-sozlesmesi", "/sayfa/kvkk",
                  "/sayfa/gizlilik"]),
]


async def upgrade_untouched_footer(db) -> bool:
    doc = await db.settings.find_one({"id": "footer"}, {"_id": 0})
    if not doc or not isinstance(doc.get("columns"), list):
        return False                                   # kayıt yok → zaten yeni varsayılan sunulur
    link_cols = [(c.get("title"), [l.get("to") for l in (c.get("links") or [])])
                 for c in doc["columns"] if isinstance(c, dict) and c.get("links")]
    if link_cols != _OLD_FOOTER_LINK_COLUMNS:
        return False
    from routes.footer_template import _DEFAULT
    new_link_cols = [c for c in _DEFAULT["columns"] if c.get("links")]
    static_cols = [c for c in doc["columns"] if isinstance(c, dict) and not c.get("links")]
    await db.settings.update_one({"id": "footer"}, {"$set": {"columns": new_link_cols + static_cols}})
    return True


async def run_startup(db, logger=None) -> dict:
    out = {}
    try:
        out["footer_upgraded"] = await upgrade_untouched_footer(db)
    except Exception as e:  # noqa: BLE001
        out["footer_error"] = str(e)
    try:
        out["company"] = await apply_company_defaults(db)
    except Exception as e:  # noqa: BLE001
        out["company_error"] = str(e)
    try:
        out["pages"] = await ensure_legal_pages(db)
    except Exception as e:  # noqa: BLE001
        out["pages_error"] = str(e)
    if logger:
        pg = out.get("pages") or {}
        logger.info(f"[legal-pages] firma={out.get('company')} sayfa: +{len(pg.get('created', []))} "
                    f"~{len(pg.get('updated', []))} korunan={pg.get('kept_customized')} "
                    f"{out.get('company_error') or ''}{out.get('pages_error') or ''}")
    return out
