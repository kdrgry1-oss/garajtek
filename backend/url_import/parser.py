"""Ürün ve listeleme sayfası ayrıştırıcıları (URL'den Ürün Aktar).

ÜRÜN SAYFASI — alanlar şu öncelikle doldurulur (ilk dolu kaynak kazanır):
  1. JSON-LD Product / ProductGroup (@graph ve listeler dahil): name, sku, gtin*, mpn, brand,
     offers.price / lowPrice / priceCurrency / availability, image[], description, category
     (aggregateRating yok sayılır) + JSON-LD BreadcrumbList
  2. Microdata (itemtype=schema.org/Product): itemprop name/price/priceCurrency/image/…
  3. OpenGraph: og:title, og:image (çoklu), og:description, product:price:amount/currency,
     product:availability
  4. Platform seçicileri (IdeaSoft, Ticimax, T-Soft, Shopify, WooCommerce, OpenCart)
  5. Genel geri dönüşler: h1, fiyat sınıflı öğeler (eski/yeni fiyat ayrımıyla), ana galeri
     görselleri (data-zoom/large/original/srcset), kırıntı, teknik tablo (`table` / `dl` /
     "Özellikler" bölümündeki "Etiket: Değer" satırları)

LİSTELEME SAYFASI — ürün linkleri şu sırayla toplanır:
  1. JSON-LD ItemList (itemListElement[].url / item.url)
  2. Bilinen ürün URL kalıpları: /urun/<slug> (grayzer, IdeaSoft, WooCommerce TR), /product(s)/<slug>
     (WooCommerce, Shopify), route=product/product&product_id= (OpenCart), -p-<id> (T-Soft vb.)
  3. Ürün kartı kapsayıcılarındaki linkler (class/id: product-item, productItem, product-card,
     ProductList, urun, productDetailLink, woocommerce-LoopProduct-link…) — kök seviye slug'lı
     siteler (ör. algikitelli, Ticimax) bu yolla bulunur
  4. Fiyat metni + görsel içeren küçük kapsayıcılardaki kök seviye linkler (son çare; her aday
     sayfa yine ürün sayfası olarak doğrulanır, ürün olmayanlar "ürün sayfası değil" diye atlanır)
  Sayfalama: rel=next, "Sonraki"/»/› bağlantıları, ?page=/?sayfa=/?tp=/?pg=/?p= ve /page/N/.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

from .sanitize import _parser, sanitize_html

TRACKING_PARAMS = re.compile(r"^(utm_|gclid|fbclid|yclid|msclkid|_ga|ref$|srsltid)", re.I)
PAGE_PARAMS = ("page", "sayfa", "tp", "pg", "p", "s", "pagenumber", "paged")
IMG_EXT_RE = re.compile(r"\.(jpe?g|png|webp)(\?|$)", re.I)
BAD_IMG_RE = re.compile(r"(logo|icon|sprite|placeholder|loading|lazy|blank|banner|payment|kargo|cargo|"
                        r"social|facebook|instagram|whatsapp|flag|avatar|badge|rozet|star|yildiz|\.svg|\.gif)", re.I)
PRICE_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)")
CURRENCY_TXT = re.compile(r"(₺|\bTL\b|\bTRY\b|\$|€|\bUSD\b|\bEUR\b)", re.I)
NON_PRODUCT_PATH = re.compile(
    r"(^/$|/(sepet|cart|checkout|odeme|uye|uyelik|hesab|account|login|giris|kayit|register|sifre|"
    r"iletisim|contact|hakkimizda|about|blog|haber|sss|faq|kvkk|gizlilik|privacy|sozlesme|"
    r"kampanya|marka|markalar|brand|brands|arama|search|favori|wishlist|karsilastir|compare|"
    r"tag|etiket|wp-|feed|sitemap|cdn-cgi|kategori|category|collections?|page|sayfa)(/|$|\?|-))",
    re.I)
PRODUCT_PATH = re.compile(r"(/urun/[^/?#]+|/products?/[^/?#]+|route=product/product|product_id=\d+|"
                          r"-p-\d+(?:\.html)?$|/p/\d+|-pm-\d+|_p\d+\.html$)", re.I)
CARD_CLASS = re.compile(r"(product[-_ ]?(item|card|box|list|wrapper|thumb|grid|cell|content|layout|"
                        r"name|title|image|link|detail)|productitem|productdetaillink|urun[-_ ]?(kutu|item|kart|"
                        r"liste|adi|resim)|loopproduct|showcase|vitrin|\bproduct\b|card-product|"
                        r"grid-product|product-miniature|productname|productimage|prd[-_]?(item|box))", re.I)
NAV_CLASS = re.compile(r"(^|[-_ ])(nav|menu|header|footer|breadcrumb|pagination|sidebar|filter|"
                       r"mega|topbar|navbar|cookie|modal)([-_ ]|$)", re.I)


# ── yardımcılar ─────────────────────────────────────────────────────────────

def soup_of(body: bytes | str, charset: Optional[str] = None) -> BeautifulSoup:
    if isinstance(body, bytes):
        try:
            return BeautifulSoup(body, _parser(), from_encoding=charset) if charset else BeautifulSoup(body, _parser())
        except LookupError:
            return BeautifulSoup(body, _parser())
    return BeautifulSoup(body, _parser())


def clean_url(url: str) -> str:
    """Parça (#) ve izleme parametrelerini atar; host küçük harf."""
    try:
        p = urlsplit(url.strip())
    except ValueError:
        return url
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if not TRACKING_PARAMS.match(k)]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", urlencode(q), ""))


def site_key(host: str) -> str:
    h = (host or "").lower()
    return h[4:] if h.startswith("www.") else h


def same_site(a: str, b: str) -> bool:
    return site_key(urlsplit(a).hostname or "") == site_key(urlsplit(b).hostname or "")


def parse_price(text: Any) -> Optional[float]:
    """Türkçe/İngilizce biçimli fiyat: "1.234,56 TL" → 1234.56; "12.500" → 12500; "1,299.90" → 1299.9."""
    if text is None:
        return None
    if isinstance(text, (int, float)) and not isinstance(text, bool):
        return float(text) if text > 0 else None
    s = str(text).replace("\xa0", " ").strip()
    m = PRICE_RE.search(s)
    if not m:
        return None
    raw = m.group(1).replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", raw):        # 1.234,56 | 12.500
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?", raw):      # 1,234.56
        raw = raw.replace(",", "")
    elif "," in raw:                                                  # 12,5 | 1299,90
        raw = raw.replace(",", ".")
    try:
        v = float(raw)
    except ValueError:
        return None
    return v if 0 < v < 100_000_000 else None


def _txt(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def _cls(el: Tag) -> str:
    c = el.get("class") or []
    if isinstance(c, str):
        c = [c]
    return " ".join(c) + " " + str(el.get("id") or "")


def _in_nav(el: Tag) -> bool:
    for p in el.parents:
        if not isinstance(p, Tag):
            continue
        if p.name in ("nav", "header", "footer"):
            return True
        if NAV_CLASS.search(_cls(p)):
            return True
    return False


def _img_src(img: Tag, base: str) -> Optional[str]:
    for a in ("data-zoom-image", "data-zoom", "data-large_image", "data-large", "data-big", "data-original",
              "data-full", "data-image", "data-src", "data-lazy", "data-lazy-src"):
        v = img.get(a)
        if v and not str(v).startswith("data:"):
            return urljoin(base, str(v).strip())
    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        best, bw = None, -1
        for part in str(srcset).split(","):
            bits = part.strip().split()
            if not bits:
                continue
            w = 0
            if len(bits) > 1:
                m = re.match(r"(\d+)", bits[1])
                w = int(m.group(1)) if m else 0
            if w >= bw:
                best, bw = bits[0], w
        if best and not best.startswith("data:"):
            return urljoin(base, best)
    v = img.get("src")
    if v and not str(v).startswith("data:"):
        return urljoin(base, str(v).strip())
    return None


def _as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


# ── JSON-LD ─────────────────────────────────────────────────────────────────

def _jsonld_objects(soup: BeautifulSoup) -> List[dict]:
    out: List[dict] = []

    def walk(o):
        if isinstance(o, list):
            for x in o:
                walk(x)
        elif isinstance(o, dict):
            out.append(o)
            if "@graph" in o:
                walk(o["@graph"])
            for k in ("mainEntity", "itemListElement", "item", "hasVariant", "isVariantOf"):
                if isinstance(o.get(k), (dict, list)):
                    walk(o[k])

    for s in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
        raw = s.string or s.get_text() or ""
        raw = raw.strip().rstrip(";")
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            try:  # bazı temalar kaçışsız satır sonu bırakır
                data = json.loads(re.sub(r"[\r\n\t]+", " ", raw))
            except ValueError:
                continue
        walk(data)
    return out


def _types(o: dict) -> List[str]:
    return [str(t).split("/")[-1].lower() for t in _as_list(o.get("@type"))]


def _ld_image_list(v) -> List[str]:
    out = []
    for x in _as_list(v):
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            u = x.get("url") or x.get("contentUrl") or x.get("@id")
            if u:
                out.append(str(u))
    return out


def _ld_offer(o: dict) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """(fiyat, para birimi, stok durumu) — Offer, AggregateOffer (lowPrice) ve iç içe teklifler."""
    for off in _as_list(o.get("offers")):
        if not isinstance(off, dict):
            continue
        price = parse_price(off.get("price")) or parse_price(off.get("lowPrice"))
        if price is None:
            for ps in _as_list(off.get("priceSpecification")):
                if isinstance(ps, dict) and parse_price(ps.get("price")):
                    price = parse_price(ps.get("price"))
                    break
        if price is None and off.get("offers"):
            r = _ld_offer(off)
            if r[0]:
                return r
        if price:
            return price, (off.get("priceCurrency") or None), str(off.get("availability") or "")
    return None, None, None


def _ld_brand(v) -> str:
    for b in _as_list(v):
        if isinstance(b, str):
            return b.strip()
        if isinstance(b, dict) and b.get("name"):
            return str(b["name"]).strip()
    return ""


# ── veri modeli ─────────────────────────────────────────────────────────────

@dataclass
class ProductData:
    url: str
    name: str = ""
    sku: str = ""
    gtin: str = ""
    mpn: str = ""
    brand: str = ""
    price: Optional[float] = None
    old_price: Optional[float] = None
    currency: str = ""
    availability: str = ""      # "in" | "out" | ""
    images: List[str] = field(default_factory=list)
    description_html: str = ""
    breadcrumb: List[str] = field(default_factory=list)
    spec_rows: List[Tuple[str, str]] = field(default_factory=list)
    canonical: str = ""
    platform: str = ""
    sources: Dict[str, str] = field(default_factory=dict)
    signals: int = 0             # ürün sayfası olduğuna dair güçlü işaret sayısı

    def set(self, key: str, value, source: str):
        if value in (None, "", []) or getattr(self, key) not in (None, "", []):
            return
        setattr(self, key, value)
        self.sources[key] = source

    @property
    def is_product(self) -> bool:
        return bool(self.name) and (self.signals > 0 or (self.price is not None and bool(self.images)))


def detect_platform(soup: BeautifulSoup, html_text: str) -> str:
    gen = " ".join(m.get("content", "") for m in soup.find_all("meta", attrs={"name": re.compile("generator", re.I)}))
    low = (gen + " " + html_text[:400000]).lower()
    if "cdn.shopify.com" in low or "shopify" in gen.lower() or "Shopify.theme" in html_text[:400000]:
        return "shopify"
    if "woocommerce" in low:
        return "woocommerce"
    if "ideasoft" in low or "ideacdn" in low or "myideasoft" in low:
        return "ideasoft"
    if "ticimax" in low or "ticimaxcdn" in low:
        return "ticimax"
    if "tsoft" in low or "t-soft" in low or "tsoftstatic" in low:
        return "tsoft"
    if "route=product/" in low or "catalog/view/theme" in low or "opencart" in low:
        return "opencart"
    return "generic"


# platform → (başlık, fiyat, eski fiyat, galeri, açıklama, teknik tablo, kırıntı, sku) seçicileri
PLATFORM_SELECTORS: Dict[str, Dict[str, List[str]]] = {
    "woocommerce": {
        "name": ["h1.product_title", ".product_title"],
        "price": ["p.price ins .woocommerce-Price-amount", ".summary .price ins .amount",
                  "p.price .woocommerce-Price-amount", ".summary .price .amount"],
        "old_price": ["p.price del .woocommerce-Price-amount", ".summary .price del .amount"],
        "gallery": [".woocommerce-product-gallery__image a", ".woocommerce-product-gallery__image img",
                    ".woocommerce-product-gallery img"],
        "description": ["#tab-description", ".woocommerce-Tabs-panel--description",
                        ".woocommerce-product-details__short-description"],
        "specs": ["table.woocommerce-product-attributes", "table.shop_attributes"],
        "breadcrumb": [".woocommerce-breadcrumb a", "nav.woocommerce-breadcrumb"],
        "sku": [".sku_wrapper .sku", ".product_meta .sku"],
    },
    "shopify": {
        "name": ["h1.product__title", "h1.product-single__title", ".product__title h1", "h1"],
        "price": [".price__sale .price-item--sale", ".price-item--regular", "[data-product-price]",
                  ".product__price", ".price"],
        "old_price": [".price__sale s .price-item--regular", "[data-compare-price]", ".product__price--compare",
                      "s.price-item"],
        "gallery": [".product__media img", ".product-single__photo img", "[data-product-media-type-image] img",
                    ".product__main-photos img"],
        "description": [".product__description", ".product-single__description", ".rte"],
        "specs": [".product__description table", ".rte table"],
        "breadcrumb": [".breadcrumbs a", "nav.breadcrumb a"],
        "sku": [".product__sku", "[data-sku]", ".variant-sku"],
    },
    "ideasoft": {
        "name": ["h1.product-title", "#product-name", ".product-title h1", "h1"],
        "price": [".product-price-new", ".product-price .discounted-price", "#product-price", ".product-price",
                  ".price-new"],
        "old_price": [".product-price-old", ".product-price .old-price", ".price-old"],
        "gallery": ["#product-images a", ".product-images a", ".product-image-wrapper img", "#productImage img",
                    ".product-images img", ".swiper-slide img"],
        "description": ["#product-detail-tab", ".product-details-tab-content", "#tab-description",
                        ".product-detail-content", ".product-description"],
        "specs": [".product-features table", "#product-features table", ".product-detail-tab-content table"],
        "breadcrumb": [".breadcrumb a", ".breadcrumb li", "#breadcrumb a"],
        "sku": [".product-code", "#product-code", ".product-sku"],
    },
    "ticimax": {
        "name": ["h1.ProductName", ".ProductName h1", "#productName", ".productName h1", "h1"],
        "price": ["#divIndirimliFiyat .spanFiyat", ".IndirimliFiyatContent .spanFiyat", "#indirimliFiyat",
                  ".indirimliFiyat .spanFiyat", "#divSatisFiyati .spanFiyat", ".urunDetayFiyat"],
        "old_price": ["#divPiyasaFiyati .spanFiyat", ".PiyasafiyatiContent .spanFiyat", "#divSatisFiyati del"],
        "gallery": ["#divProductImageCarousel img", ".SmallImages img", "#imgUrunResim", ".urunResim img",
                    "a[data-image]"],
        "description": ["#divUrunAciklama", ".urunAciklama", "#urunAciklama", "#divTabOzellikler",
                        ".ProductDetailInfo"],
        "specs": ["#divTabOzellikler table", ".urunOzellikleri table", "#tabOzellikler table"],
        "breadcrumb": [".breadcrumb a", "#divBreadCrumb a", ".BreadCrumb a"],
        "sku": ["#divUrunStokKodu .right_line", ".stokKodu", "#UrunStokKodu"],
    },
    "tsoft": {
        "name": ["h1#product-title", "h1.product-title", "#product-name", "h1"],
        "price": ["#product-price .product-price-new", ".product-price-new", "#product-price-discounted",
                  ".currentPrice", "#product-price", ".product-price"],
        "old_price": [".product-price-old", "#product-price-old", ".oldPrice"],
        "gallery": ["#productImage a", "#product-images img", ".product-images img", "#productImages a",
                    ".product-gallery img"],
        "description": ["#product-detail .product-detail-content", "#productDetailTab", "#product-tab-content",
                        ".product-detail-description"],
        "specs": ["#product-features table", ".product-features table", "#productDetailTab table"],
        "breadcrumb": [".breadcrumb a", "#breadcrumb a"],
        "sku": ["#product-code", ".product-code", "#productCode"],
    },
    "opencart": {
        "name": ["#content h1", "h1"],
        "price": ["#content .price-new", "#content ul.list-unstyled li h2", ".product-price", "#content .price"],
        "old_price": ["#content .price-old", "#content ul.list-unstyled li span[style*=line-through]"],
        "gallery": [".thumbnails a", "ul.thumbnails img", "#image-additional img", ".product-images img"],
        "description": ["#tab-description", "#description"],
        "specs": ["#tab-specification table", "#specification table"],
        "breadcrumb": ["ul.breadcrumb a", ".breadcrumb a"],
        "sku": [],
    },
}
GENERIC_SELECTORS: Dict[str, List[str]] = {
    "name": ["h1[itemprop=name]", "h1.product-name", "h1.product-title", "h1.productName", "h1"],
    "price": ["[class*=discount][class*=price]", "[class*=indirim][class*=fiyat]", "[class*=sale-price]",
              "[class*=new-price]", "[class*=price-new]", "[class*=current-price]", "[class*=product-price]",
              "[class*=productPrice]", "[class*=urun-fiyat]", "[class*=fiyat]", "[id*=price]", "[class*=price]"],
    "old_price": ["del", "s", "strike", "[class*=old-price]", "[class*=price-old]", "[class*=eski]",
                  "[class*=regular-price]", "[class*=piyasa]", "[class*=liste-fiyat]"],
    "gallery": ["[class*=gallery] img", "[class*=product-image] img", "[class*=productImage] img",
                "[class*=zoom] img", "[class*=slider] img", "[class*=swiper] img", "[class*=carousel] img",
                "[class*=product] img"],
    "description": ["[itemprop=description]", "#description", "#tab-description", "[class*=product-description]",
                    "[class*=productDescription]", "[class*=urun-aciklama]", "[class*=description]",
                    "[class*=aciklama]", "[id*=aciklama]", "[class*=detail-content]"],
    "breadcrumb": ["[class*=breadcrumb] li", "[class*=breadcrumb] a", "[class*=Breadcrumb] a",
                   "nav[aria-label*=readcrumb] a"],
}


def _select_first_text(soup, sels: Iterable[str]) -> str:
    for sel in sels:
        try:
            for el in soup.select(sel):
                t = _txt(el)
                if t:
                    return t
        except Exception:  # noqa: BLE001 — geçersiz/desteklenmeyen seçici
            continue
    return ""


def _select_price(soup, sels: Iterable[str], *, exclude_old: bool) -> Optional[float]:
    for sel in sels:
        try:
            els = soup.select(sel)
        except Exception:  # noqa: BLE001
            continue
        for el in els:
            if _in_nav(el):
                continue
            if exclude_old and (el.find_parent(["del", "s", "strike"]) or re.search(r"(old|eski|piyasa|regular|liste)",
                                                                                     _cls(el), re.I)):
                continue
            if el.get("content") and parse_price(el.get("content")):
                return parse_price(el.get("content"))
            t = _txt(el)
            if not t or len(t) > 60 or not re.search(r"\d", t):
                continue
            if not CURRENCY_TXT.search(t) and not re.search(r"[.,]\d{2}\b", t) and "price" not in sel:
                continue
            v = parse_price(t)
            if v:
                return v
    return None


def _breadcrumb_from_ld(objs: List[dict]) -> List[str]:
    for o in objs:
        if "breadcrumblist" in _types(o):
            items = []
            for li in sorted(_as_list(o.get("itemListElement")), key=lambda x: (x or {}).get("position", 0)
                             if isinstance(x, dict) else 0):
                if not isinstance(li, dict):
                    continue
                item = li.get("item")
                nm = li.get("name") or (item.get("name") if isinstance(item, dict) else None)
                if nm:
                    items.append(str(nm).strip())
            if items:
                return items
    return []


def _spec_rows(scope) -> List[Tuple[str, str]]:
    rows: List[Tuple[str, str]] = []
    if scope is None:
        return rows
    for tr in scope.select("table tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if len(cells) == 2:
            k, v = _txt(cells[0]), _txt(cells[1])
            if k and v and len(k) <= 60 and len(v) <= 300 and not re.fullmatch(r"[\d.,\s]+", k):
                rows.append((k, v))
    for dl in scope.find_all("dl"):
        dts = dl.find_all("dt")
        for dt in dts:
            dd = dt.find_next_sibling("dd")
            if dd is not None:
                k, v = _txt(dt), _txt(dd)
                if k and v and len(k) <= 60:
                    rows.append((k, v))
    # "Özellikler" başlığı altındaki "Etiket: Değer" satırları
    for h in scope.find_all(["h2", "h3", "h4", "h5", "strong", "b", "p", "div", "span"]):
        if h.find(["h2", "h3", "h4", "h5", "p", "div", "table", "ul"]):
            continue
        ht = _txt(h)
        if not re.search(r"(teknik\s+)?[öo]zellik(ler)?i?\b|teknik\s+bilgi|specification", ht, re.I) or len(ht) > 40:
            continue
        sib = h.find_next(["ul", "ol", "p", "div"])
        hops = 0
        while sib is not None and hops < 6:
            for li in (sib.find_all(["li", "p"]) if sib.name in ("ul", "ol", "div") else [sib]):
                t = _txt(li)
                m = re.match(r"^([^:：]{2,60})\s*[:：]\s*(.{1,300})$", t)
                if m:
                    rows.append((m.group(1).strip(" -•*"), m.group(2).strip()))
            sib = sib.find_next_sibling(["ul", "ol", "p", "div"])
            hops += 1
        break
    seen, out = set(), []
    for k, v in rows:
        key = k.lower()
        if key not in seen:
            seen.add(key)
            out.append((k, v))
    return out[:60]


def parse_product(html: bytes | str, url: str, charset: Optional[str] = None) -> ProductData:
    soup = soup_of(html, charset)
    html_text = html.decode("utf-8", "ignore") if isinstance(html, bytes) else html
    pd = ProductData(url=url)
    pd.platform = detect_platform(soup, html_text)
    can = soup.find("link", rel=lambda v: v and "canonical" in (v if isinstance(v, list) else [v]))
    if can and can.get("href"):
        pd.canonical = urljoin(url, can["href"].strip())

    # 1) JSON-LD
    objs = _jsonld_objects(soup)
    products = [o for o in objs if {"product", "productgroup"} & set(_types(o))]
    if products:
        o = products[0]
        if len(products) == 1 or "productgroup" in _types(o):
            pd.signals += 2
        pd.set("name", str(o.get("name") or "").strip(), "jsonld")
        pd.set("sku", str(o.get("sku") or o.get("productID") or "").strip(), "jsonld")
        for gk in ("gtin13", "gtin", "gtin14", "gtin12", "gtin8", "ean"):
            if o.get(gk):
                pd.set("gtin", str(o[gk]).strip(), "jsonld")
                break
        pd.set("mpn", str(o.get("mpn") or "").strip(), "jsonld")
        pd.set("brand", _ld_brand(o.get("brand")), "jsonld")
        price, cur, avail = _ld_offer(o)
        if price is None:
            for v in _as_list(o.get("hasVariant")):
                if isinstance(v, dict):
                    price, cur, avail = _ld_offer(v)
                    if price:
                        break
        pd.set("price", price, "jsonld")
        pd.set("currency", str(cur or "").upper(), "jsonld")
        if avail:
            pd.set("availability", "out" if re.search(r"(OutOfStock|SoldOut|Discontinued)", avail, re.I) else "in", "jsonld")
        pd.set("images", _ld_image_list(o.get("image")), "jsonld")
        desc = o.get("description")
        if isinstance(desc, str) and desc.strip():
            pd.set("description_html", desc if "<" in desc else "<p>" + "</p><p>".join(
                x.strip() for x in desc.split("\n") if x.strip()) + "</p>", "jsonld")
        for pv in _as_list(o.get("additionalProperty")):
            if isinstance(pv, dict) and pv.get("name") and pv.get("value") not in (None, ""):
                pd.spec_rows.append((str(pv["name"]), str(pv["value"])))
    pd.set("breadcrumb", _breadcrumb_from_ld(objs), "jsonld")

    # 2) Microdata
    md = soup.find(attrs={"itemtype": re.compile(r"schema\.org/Product", re.I)})
    if md is not None:
        pd.signals += 1

        def ip(name):
            el = md.find(attrs={"itemprop": name})
            if el is None:
                return None, None
            return el, (el.get("content") or el.get("href") or el.get("src") or _txt(el))
        pd.set("name", (ip("name")[1] or "").strip(), "microdata")
        pd.set("sku", (ip("sku")[1] or "").strip(), "microdata")
        pd.set("price", parse_price(ip("price")[1]), "microdata")
        pd.set("currency", (ip("priceCurrency")[1] or "").strip().upper(), "microdata")
        av = ip("availability")[1] or ""
        if av:
            pd.set("availability", "out" if re.search(r"(OutOfStock|SoldOut)", av, re.I) else "in", "microdata")
        b_el, b_val = ip("brand")
        if b_el is not None:
            nm = b_el.find(attrs={"itemprop": "name"})
            pd.set("brand", (nm.get("content") or _txt(nm)) if nm is not None else (b_val or "").strip(), "microdata")
        imgs = []
        for el in md.find_all(attrs={"itemprop": "image"}):
            u = el.get("content") or el.get("href") or (_img_src(el, url) if el.name == "img" else None)
            if u:
                imgs.append(urljoin(url, u))
        pd.set("images", imgs, "microdata")
        d_el = md.find(attrs={"itemprop": "description"})
        if d_el is not None:
            pd.set("description_html", d_el.get("content") or d_el.decode_contents(), "microdata")

    # 3) OpenGraph
    def og(prop):
        el = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        return (el.get("content") or "").strip() if el is not None else ""
    og_type = og("og:type").lower()
    if og_type in ("product", "og:product", "product.item"):
        pd.signals += 1
    if og("product:price:amount") or og("og:price:amount"):
        pd.signals += 1
    pd.set("name", og("og:title"), "og")
    pd.set("price", parse_price(og("product:price:amount") or og("og:price:amount")), "og")
    pd.set("currency", (og("product:price:currency") or og("og:price:currency")).upper(), "og")
    av = og("product:availability") or og("og:availability")
    if av:
        pd.set("availability", "out" if re.search(r"(out|oos|stokta yok|tükendi)", av, re.I) else "in", "og")
    og_imgs = [urljoin(url, m.get("content").strip()) for m in soup.find_all("meta", attrs={"property": re.compile(r"^og:image(:url|:secure_url)?$")})
               if m.get("content")]
    og_desc = og("og:description")

    # 4) Platform + 5) genel seçiciler
    sels = PLATFORM_SELECTORS.get(pd.platform, {})
    for src, table in (("platform", sels), ("generic", GENERIC_SELECTORS)):
        if not table:
            continue
        pd.set("name", _select_first_text(soup, table.get("name", [])), src)
        new_p = _select_price(soup, table.get("price", []), exclude_old=True)
        old_p = _select_price(soup, table.get("old_price", []), exclude_old=False)
        pd.set("price", new_p, src)
        if old_p and pd.price and old_p > pd.price and not pd.old_price:
            pd.old_price, pd.sources["old_price"] = old_p, src
        if table.get("sku"):
            pd.set("sku", _select_first_text(soup, table["sku"]).replace("Stok Kodu", "").strip(" :"), src)
        imgs = []
        for sel in table.get("gallery", []):
            try:
                for el in soup.select(sel):
                    if _in_nav(el):
                        continue
                    if el.name == "a":
                        h = el.get("data-zoom-image") or el.get("data-image") or el.get("data-large") or el.get("href")
                        if h and IMG_EXT_RE.search(h):
                            imgs.append(urljoin(url, h.strip()))
                        else:
                            im = el.find("img")
                            if im is not None and _img_src(im, url):
                                imgs.append(_img_src(im, url))
                    elif el.name == "img":
                        u = _img_src(el, url)
                        if u:
                            imgs.append(u)
            except Exception:  # noqa: BLE001
                continue
            if imgs:
                break
        pd.set("images", imgs, src)
        if not pd.description_html or len(_txt(soup_of(pd.description_html))) < 40:
            for sel in table.get("description", []):
                try:
                    el = soup.select_one(sel)
                except Exception:  # noqa: BLE001
                    el = None
                if el is not None and not _in_nav(el) and len(_txt(el)) >= 40:
                    pd.description_html = el.decode_contents()
                    pd.sources["description_html"] = src
                    break
        if not pd.breadcrumb:
            for sel in table.get("breadcrumb", []):
                try:
                    items = [_txt(el) for el in soup.select(sel)]
                except Exception:  # noqa: BLE001
                    items = []
                items = [x for x in items if x and len(x) <= 80 and x not in ("»", "›", ">", "/")]
                if len(items) >= 2:
                    dedup = []
                    for x in items:
                        if x not in dedup:
                            dedup.append(x)
                    pd.breadcrumb, pd.sources["breadcrumb"] = dedup, src
                    break
        if src == "platform":
            for sel in table.get("specs", []):
                try:
                    el = soup.select_one(sel)
                except Exception:  # noqa: BLE001
                    el = None
                if el is not None:
                    pd.spec_rows.extend(_spec_rows(el if el.name != "table" else el.parent))
    pd.set("images", og_imgs, "og")
    if not pd.description_html and og_desc:
        pd.description_html, pd.sources["description_html"] = f"<p>{og_desc}</p>", "og"

    # Teknik tablo: açıklama alanı + sayfa geneli (nav/header/footer hariç)
    if pd.description_html:
        pd.spec_rows.extend(_spec_rows(soup_of(pd.description_html)))
    main = soup.find("main") or soup.body or soup
    page_rows = [(k, v) for k, v in _spec_rows(main)]
    pd.spec_rows.extend(page_rows)
    seen, rows = set(), []
    for k, v in pd.spec_rows:
        if k.lower() not in seen:
            seen.add(k.lower())
            rows.append((k, v))
    pd.spec_rows = rows[:60]

    # görselleri temizle: mutlak, tekil, yalnız jpg/png/webp veya uzantısız, logo/ikon değil
    out, seen_img = [], set()
    for u in pd.images:
        u = urljoin(url, str(u).strip())
        if not u.startswith(("http://", "https://")) or BAD_IMG_RE.search(u.split("?")[0]):
            continue
        if re.search(r"\.(svg|gif|ico|bmp|tiff?)(\?|$)", u, re.I):
            continue
        key = re.sub(r"-\d{2,4}x\d{2,4}(?=\.\w+$)", "", re.sub(r"[?#].*$", "", u))  # WP boyut varyantları
        if key in seen_img:
            continue
        seen_img.add(key)
        out.append(u)
    pd.images = out[:20]
    pd.name = re.sub(r"\s+", " ", pd.name or "").strip()[:250]
    if pd.name and pd.breadcrumb and pd.breadcrumb[-1].strip().lower() == pd.name.lower():
        pd.breadcrumb = pd.breadcrumb[:-1]
    pd.breadcrumb = [b for b in pd.breadcrumb if not re.fullmatch(r"(ana\s*sayfa|anasayfa|home|ana sayfa)", b, re.I)]
    pd.description_html = sanitize_html(pd.description_html)
    if pd.old_price and pd.price and pd.old_price <= pd.price:
        pd.old_price = None
    # platform ürün işaretleri (ör. sepete ekle düğmesi tek ürün için)
    if soup.find(attrs={"name": re.compile(r"^(add-to-cart|product_id)$")}) or soup.select_one(
            "form.cart, #addToCart, .add-to-cart, [class*=sepete-ekle], [id*=sepeteEkle], [class*=AddToCart]"):
        if pd.price is not None:
            pd.signals += 1
    return pd


# ── listeleme ───────────────────────────────────────────────────────────────

@dataclass
class ListingData:
    url: str
    product_links: List[str] = field(default_factory=list)
    next_page: Optional[str] = None
    method: str = ""
    title: str = ""
    breadcrumb: List[str] = field(default_factory=list)
    ld_product_count: int = 0


def _is_root_slug(path: str) -> bool:
    segs = [s for s in path.split("/") if s]
    return len(segs) == 1 and "-" in segs[0] and not re.search(r"\.(jpe?g|png|webp|gif|css|js|pdf|xml)$", segs[0], re.I)


def _link_ok(href: str, base: str) -> Optional[str]:
    if not href or href.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
        return None
    u = urljoin(base, href.strip())
    if not u.startswith(("http://", "https://")) or not same_site(u, base):
        return None
    return clean_url(u)


def _page_num_of(u: str) -> Optional[int]:
    p = urlsplit(u)
    for k, v in parse_qsl(p.query):
        if k.lower() in PAGE_PARAMS and v.isdigit():
            return int(v)
    m = re.search(r"/(?:page|sayfa)/(\d+)/?$", p.path)
    return int(m.group(1)) if m else None


def _base_listing(u: str) -> str:
    p = urlsplit(u)
    q = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in PAGE_PARAMS]
    path = re.sub(r"/(?:page|sayfa)/\d+/?$", "/", p.path)
    return urlunsplit((p.scheme, p.netloc, path, urlencode(q), ""))


def parse_listing(html: bytes | str, url: str, charset: Optional[str] = None, *, page_no: int = 1) -> ListingData:
    soup = soup_of(html, charset)
    ld = ListingData(url=url)
    ld.title = _txt(soup.find("h1")) or _txt(soup.find("title"))
    objs = _jsonld_objects(soup)
    ld.ld_product_count = sum(1 for o in objs if "product" in _types(o))
    ld.breadcrumb = _breadcrumb_from_ld(objs)
    links: List[str] = []
    me = clean_url(url)

    def add(u):
        if u and u != me and u not in links:
            links.append(u)

    # 1) ItemList
    for o in objs:
        if "itemlist" in _types(o):
            for li in _as_list(o.get("itemListElement")):
                if isinstance(li, dict):
                    item = li.get("item")
                    u = li.get("url") or (item.get("url") or item.get("@id") if isinstance(item, dict) else item)
                    if isinstance(u, str):
                        add(_link_ok(u, url))
    if links:
        ld.method = "jsonld-itemlist"

    anchors = [a for a in soup.find_all("a", href=True)]
    # 2) bilinen ürün URL kalıpları
    if not links:
        for a in anchors:
            u = _link_ok(a["href"], url)
            if u and PRODUCT_PATH.search(urlsplit(u).path + "?" + urlsplit(u).query) and not _in_nav(a):
                add(u)
        if links:
            ld.method = "url-pattern"
    # 3) ürün kartı kapsayıcıları
    if not links:
        for a in anchors:
            u = _link_ok(a["href"], url)
            if not u or _in_nav(a):
                continue
            path = urlsplit(u).path
            if NON_PRODUCT_PATH.search(path) or _page_num_of(u):
                continue
            hit = False
            for p in [a] + list(a.parents)[:4]:
                if isinstance(p, Tag) and CARD_CLASS.search(_cls(p)):
                    hit = True
                    break
            if hit:
                add(u)
        if links:
            ld.method = "product-card"
    # 4) fiyat + görsel içeren kapsayıcılardaki kök slug'lar
    if not links:
        for a in anchors:
            u = _link_ok(a["href"], url)
            if not u or _in_nav(a):
                continue
            path = urlsplit(u).path
            if NON_PRODUCT_PATH.search(path) or not _is_root_slug(path):
                continue
            for p in list(a.parents)[:4]:
                if not isinstance(p, Tag):
                    continue
                others = {_link_ok(x.get("href"), url) for x in p.find_all("a", href=True)} - {u, None}
                if others:
                    break  # kart değil, birden çok ürünü kapsayan liste kapsayıcısı
                t = _txt(p)
                if len(t) < 400 and CURRENCY_TXT.search(t) and p.find("img") is not None:
                    add(u)
                    break
        if links:
            ld.method = "price-context"

    # sayfalama
    nxt = None
    rel = soup.find(["link", "a"], rel=lambda v: v and "next" in (v if isinstance(v, list) else [v]))
    if rel is not None and rel.get("href"):
        nxt = _link_ok(rel["href"], url)
    if not nxt:
        for a in anchors:
            t = _txt(a).lower()
            c = _cls(a).lower()
            if t in ("sonraki", "sonraki sayfa", "»", "›", ">", "next", "ileri") or "next" in c.split() or \
                    re.search(r"(^|[-_ ])next([-_ ]|$)", c) or (a.get("aria-label") or "").lower() in ("next", "sonraki"):
                cand = _link_ok(a["href"], url)
                if cand and cand != me:
                    nxt = cand
                    break
    if not nxt:
        want = (_page_num_of(me) or page_no) + 1
        for a in anchors:
            cand = _link_ok(a["href"], url)
            if cand and cand != me and _page_num_of(cand) == want and _base_listing(cand).rstrip("/") == _base_listing(me).rstrip("/"):
                nxt = cand
                break
    if nxt and nxt in links:
        links.remove(nxt)
    ld.product_links = [u for u in links if _page_num_of(u) is None or PRODUCT_PATH.search(u)]
    ld.next_page = nxt
    return ld
