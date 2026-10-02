"""URL'den Ürün Aktar: ayrıştırıcılar (JSON-LD / OG / IdeaSoft listesi + sayfalama / WooCommerce /
teknik tablo), SSRF korumaları, görsel doğrulama, kategori eşleme, iş akışı (dedupe/güncelleme),
kaldırma (araç + Demo İçerik › Kaldır), sitemap/feed/robots dışlaması ve panel uçları.

HTTP tamamen sahte (httpx.MockTransport + sahte DNS çözücü) — ağ erişimi yok."""
import asyncio
import io
import sys
import time
import types
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from url_import import SEED_SOURCE  # noqa: E402
from url_import import fetcher as F  # noqa: E402
from url_import import job as J  # noqa: E402
from url_import.catmap import CategoryMapper  # noqa: E402
from url_import.parser import clean_url, parse_listing, parse_price, parse_product  # noqa: E402
from url_import.sanitize import sanitize_html  # noqa: E402
from url_import.specs_map import map_specs  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "url_import"
PUBLIC_IP = "93.184.216.34"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


def _run(coro):
    return asyncio.run(coro)


def _img(fmt="JPEG", size=(640, 480), color=(200, 30, 30)) -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", size, color).save(b, fmt)
    return b.getvalue()


def _spec_cfg():
    import product_specs as ps
    return ps.default_config()


# ── ayrıştırıcılar ──────────────────────────────────────────────────────────

def test_parse_price_formats():
    assert parse_price("1.234,56 TL") == 1234.56
    assert parse_price("12.500 ₺") == 12500
    assert parse_price("1,299.90") == 1299.9
    assert parse_price("2.990,00\xa0₺") == 2990
    assert parse_price("129900.00") == 129900
    assert parse_price("12,5") == 12.5
    assert parse_price("Fiyat sorunuz") is None and parse_price("0") is None


def test_jsonld_product_fixture():
    p = parse_product(fx("jsonld_product.html"), "https://www.grayzer.example/urun/4-ton-cift-sutunlu-hidrolik-lift-grz-40")
    assert p.name == "4 Ton Çift Sütunlu Hidrolik Lift GRZ-40" and p.sources["name"] == "jsonld"
    assert (p.sku, p.gtin, p.brand, p.price, p.currency, p.availability) == (
        "GRZ-40", "8680000000017", "Grayzer", 129900.0, "TRY", "in")
    # svg logosu atılır, göreli adres mutlaklaşır; ilgili ürün görselleri (ilgili ürünler kartı) karışmaz
    assert p.images == ["https://cdn.grayzer.example/img/lift-1.jpg", "https://cdn.grayzer.example/img/lift-2.png",
                        "https://www.grayzer.example/images/lift-3.webp"]
    assert p.breadcrumb == ["Liftler", "İki Sütunlu Liftler"]
    assert p.canonical.endswith("/urun/4-ton-cift-sutunlu-hidrolik-lift-grz-40")
    d = p.description_html
    assert "<script" not in d and "<iframe" not in d and "onclick" not in d and "href" not in d
    assert "<strong>tabandan bağlantılı</strong>" in d and "bize ulaşın" in d
    assert ("Kaldırma Kapasitesi", "4 Ton") in p.spec_rows
    assert p.is_product and p.signals >= 2


def test_og_only_product_fixture():
    p = parse_product(fx("og_only_product.html"), "https://www.algikitelli.example/200-lt-pistonlu-hava-kompresoru-3-hp")
    assert p.name == "200 Lt Pistonlu Hava Kompresörü 3 HP" and p.sources["name"] == "og"
    assert p.price == 25900 and p.currency == "TRY" and p.availability == "out"
    assert len(p.images) == 2 and all(u.endswith(".jpg") for u in p.images)
    assert "çift kafalı" in p.description_html
    assert ("Tank Hacmi", "200 Lt") in p.spec_rows and ("Renk", "Kırmızı") in p.spec_rows


def test_woocommerce_product_fixture():
    p = parse_product(fx("woocommerce_product.html"), "https://woo.example/urun/havali-somun-sokme/")
    assert p.platform == "woocommerce"
    assert p.name.startswith('1/2" Havalı Somun Sökme') and p.sku == "TM-1350"
    assert p.price == 2990 and p.old_price == 3490
    assert p.images == ["https://woo.example/wp-content/uploads/2026/01/tabanca.jpg",
                        "https://woo.example/wp-content/uploads/2026/01/tabanca-2.jpg"]
    assert p.breadcrumb == ["Havalı Aletler", "Havalı Somun Sökme"]
    assert "<img" not in p.description_html and "1.350 Nm" in p.description_html
    assert ("Maks. Tork", "1.350 Nm") in p.spec_rows


def test_spec_table_microdata_windows1254():
    p = parse_product(fx("spec_table_product.html"), "https://shop.example/balans")
    assert p.name.startswith("Otomatik Ölçü Kollu Dijital Balans") and p.brand == "Balanstek"
    assert p.price == 54900 and p.images == ["https://shop.example/resim/balans-1.jpg"]
    specs, extras, meta = map_specs(p.spec_rows, _spec_cfg())
    assert specs["motor_power_kw"] == 0.25 and specs["voltage"] == "220 V"
    assert specs["origin_country"] == "İtalya" and specs["net_weight_kg"] == 145
    assert specs["rim_diameter_in"].startswith("10")
    assert {"name": "Hassasiyet", "value": "±1 g"} in extras


def test_spec_mapping_units_and_extras():
    rows = [("Kaldırma Kapasitesi", "4 Ton"), ("Kaldırma Yüksekliği", "1,9 m"), ("Motor Gücü", "3 HP"),
            ("Voltaj", "220V / 380V"), ("Garanti", "2 Yıl"), ("Kapasite", "100 Lt"), ("Renk", "Kırmızı"),
            ("Marka", "Örnek"), ("Lokma Girişi", '1/2"'), ("Faz", "Trifaze"), ("Menşei", "Mars")]
    specs, extras, meta = map_specs(rows, _spec_cfg())
    assert specs["lifting_capacity_kg"] == 4000 and specs["lift_height_mm"] == 1900
    assert specs["motor_power_hp"] == 3 and specs["voltage"] == "220 / 380 V" and specs["warranty_months"] == 24
    assert specs["tank_volume_l"] == 100 and specs["drive_size"] == ['1/2"'] and specs["phase"] == "Trifaze"
    assert {"name": "Renk", "value": "Kırmızı"} in extras
    assert meta["brand"] == "Örnek"


def test_ideasoft_listing_with_pagination():
    l1 = parse_listing(fx("ideasoft_listing_p1.html"), "https://shop.ideasoft.example/kategori/liftler")
    assert l1.method == "url-pattern"
    # nav'daki ürün linki ve izleme parametreleri atılır
    assert l1.product_links == ["https://shop.ideasoft.example/urun/iki-sutunlu-lift-4-ton",
                                "https://shop.ideasoft.example/urun/makasli-lift-3-2-ton",
                                "https://shop.ideasoft.example/urun/motosiklet-lifti-500-kg"]
    assert l1.next_page == "https://shop.ideasoft.example/kategori/liftler?tp=2"
    l2 = parse_listing(fx("ideasoft_listing_p2.html"), l1.next_page, page_no=2)
    assert "https://shop.ideasoft.example/urun/dort-sutunlu-lift-4-ton" in l2.product_links
    assert l2.next_page is None


def test_root_slug_listing_uses_price_context():
    l = parse_listing(fx("rootslug_listing.html"), "https://www.algikitelli.example/")
    assert l.product_links == ["https://www.algikitelli.example/200-lt-pistonlu-hava-kompresoru-3-hp",
                               "https://www.algikitelli.example/yari-otomatik-lastik-sokme-takma-makinesi"]


def test_listing_pagination_variants():
    html = """<html><body><div class="product-item"><a href="/products/a">A</a></div>
    <div class="product-item"><a href="/products/b">B</a></div>
    <ul class="pagination"><li><a href="/collections/x/page/2/">2</a></li></ul></body></html>"""
    l = parse_listing(html, "https://s.example/collections/x/")
    assert l.product_links == ["https://s.example/products/a", "https://s.example/products/b"]
    assert l.next_page == "https://s.example/collections/x/page/2/"
    html2 = '<html><head><link rel="next" href="?page=3"></head><body><a href="/urun/x">x</a></body></html>'
    assert parse_listing(html2, "https://s.example/kat?page=2", page_no=2).next_page == "https://s.example/kat?page=3"


def test_sanitizer_allowlist():
    out = sanitize_html('<div style="x" onmouseover="e()"><h1>Başlık</h1><p>A <a href="https://x.example">link</a>'
                        '<img src=x onerror=alert(1)></p><script>bad()</script><style>p{}</style>'
                        '<table class="t"><tr><td colspan="2" onclick="z">v</td></tr></table>'
                        '<object data="x"></object><svg><script>1</script></svg></div>')
    assert out == '<h2>Başlık</h2><p>A link</p><table><tr><td colspan="2">v</td></tr></table>'
    assert clean_url("https://WWW.X.example/a?utm_source=g&id=5#top") == "https://www.x.example/a?id=5"


def test_category_mapping_with_ancestors():
    from seed_categories import load_tree
    cats = [{"id": f"c-{n['slug']}", "name": n["name"], "slug": n["slug"],
             "parent_id": f"c-{n['parent']}" if n.get("parent") else None} for n in load_tree()]
    m = CategoryMapper(cats)
    r = m.best(["Liftler", "İki Sütunlu Liftler"], "4 Ton Çift Sütunlu Hidrolik Lift")
    assert r["slug"] == "iki-sutunlu-liftler" and r["ids"] == ["c-iki-sutunlu-liftler", "c-liftler"]
    assert m.best([], "200 Lt Pistonlu Hava Kompresörü")["slug"] == "pistonlu-kompresorler"
    assert m.best(["Havalı Aletler", "Havalı Somun Sökme"], '1/2" Havalı Somun Sökme Tabancası')["slug"] == \
        "havali-somun-sokme-makineleri"
    assert m.best([], "Dijital Balans Makinesi")["slug"] == "lastik-balans-makineleri"
    assert m.best([], "Rastgele bir şey") is None
    # indirim/set kategorileri otomatik hedef olmaz
    assert m.best(["İndirimli Ürünler"], "İndirimli ürün") is None


# ── SSRF / getirme ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("ip", ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.10", "169.254.169.254",
                                "100.64.0.1", "0.0.0.0", "::1", "fd00:ec2::254", "fe80::1", "::ffff:127.0.0.1",
                                "224.0.0.1", "240.0.0.1"])
def test_ip_blocked(ip):
    assert F.ip_blocked(ip)


def test_public_ip_allowed():
    assert not F.ip_blocked(PUBLIC_IP) and not F.ip_blocked("2606:4700:4700::1111")


@pytest.mark.parametrize("url,msg", [
    ("ftp://x.example/a", "http/https"), ("file:///etc/passwd", "http/https"), ("javascript:alert(1)", "http/https"),
    ("https://user:pw@x.example/", "parola"), ("https://x.example:8080/", "port"), ("http://x.example:22/", "port"),
    ("https:///nohost", "alan adı"),
])
def test_url_syntax_blocked(url, msg, monkeypatch):
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    with pytest.raises(F.BlockedURL) as e:
        F.check_url_syntax(url)
    assert msg in str(e.value)


def _resolver(mapping=None):
    mapping = mapping or {}

    async def resolve(host, port):
        return mapping.get(host, [PUBLIC_IP])
    return resolve


def _fetcher(routes, *, dns=None, seen=None, interval=0.0):
    def handler(req: httpx.Request):
        url = str(req.url)
        if seen is not None:
            seen.append((url, dict(req.headers)))
        r = routes.get(url)
        if r is None:
            return httpx.Response(404, text="yok")
        if callable(r):
            return r(req)
        status, headers, body = r
        return httpx.Response(status, headers=headers, content=body)
    return F.Fetcher(min_interval=interval, transport=httpx.MockTransport(handler), resolver=_resolver(dns))


def test_fetch_blocks_private_dns_and_redirect_to_metadata(monkeypatch):
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    seen = []
    routes = {"https://ok.example/r": (302, {"location": "http://169.254.169.254/latest/meta-data/"}, b""),
              "https://ok.example/r2": (301, {"location": "https://intranet.example/x"}, b""),
              "https://ok.example/r3": (302, {"location": "http://ok.example:8080/x"}, b"")}

    async def go():
        async with _fetcher(routes, dns={"intranet.example": ["10.0.0.7"], "mixed.example": [PUBLIC_IP, "127.0.0.1"]},
                            seen=seen) as f:
            for u in ("https://intranet.example/", "https://mixed.example/", "https://ok.example/r",
                      "https://ok.example/r2", "https://ok.example/r3", "http://127.0.0.1/", "http://[::1]/"):
                with pytest.raises(F.BlockedURL):
                    await f.fetch(u)
    _run(go())
    urls = [u for u, _ in seen]
    assert all("169.254" not in u and "intranet" not in u and "127.0.0.1" not in u for u in urls)
    assert urls == ["https://ok.example/r", "https://ok.example/r2", "https://ok.example/r3"]


def test_fetch_redirect_limit_size_cap_cookies_and_headers(monkeypatch):
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    seen = []
    routes = {f"https://a.example/r{i}": (302, {"location": f"/r{i + 1}"}, b"") for i in range(6)}
    routes.update({f"https://a.example/s{i}": (302, {"location": f"/s{i + 1}"}, b"") for i in range(3)})
    routes["https://a.example/big"] = (200, {"content-type": "text/html"}, b"x" * (F.MAX_HTML_BYTES + 10))
    routes["https://a.example/c1"] = (200, {"content-type": "text/html", "set-cookie": "sid=SECRET; Path=/"}, b"<p>1</p>")
    routes["https://a.example/c2"] = (200, {"content-type": "text/html; charset=windows-1254"}, b"<p>2</p>")
    routes["https://a.example/pdf"] = (200, {"content-type": "application/pdf"}, b"%PDF")
    routes["https://a.example/s3"] = (200, {"content-type": "text/html"}, b"ok")

    async def go():
        async with _fetcher(routes, seen=seen) as f:
            with pytest.raises(F.FetchError, match="yönlendirme"):
                await f.fetch("https://a.example/r0")         # 4. yönlendirme → hata
            r = await f.fetch("https://a.example/s0")         # s0→s1→s2→s3 : 3 yönlendirme → izin
            assert r.body == b"ok" and r.url == "https://a.example/s3"
            with pytest.raises(F.FetchError, match="büyük"):
                await f.fetch("https://a.example/big")
            with pytest.raises(F.FetchError, match="HTML"):
                await f.fetch("https://a.example/pdf")
            await f.fetch("https://a.example/c1")
            r2 = await f.fetch("https://a.example/c2")
            assert r2.charset == "windows-1254"
            with pytest.raises(F.FetchError, match="404"):
                await f.fetch("https://a.example/missing")
    _run(go())
    c2_headers = next(h for u, h in seen if u.endswith("/c2"))
    assert "cookie" not in {k.lower() for k in c2_headers}       # çerez saklanmadı
    assert "Mozilla/5.0" in c2_headers["user-agent"] and "tr-TR" in c2_headers["accept-language"]


def test_throttle_per_host():
    routes = {"https://a.example/1": (200, {"content-type": "text/html"}, b"1"),
              "https://a.example/2": (200, {"content-type": "text/html"}, b"2"),
              "https://b.example/1": (200, {"content-type": "text/html"}, b"3")}

    async def go():
        async with _fetcher(routes, interval=0.3) as f:
            t0 = time.monotonic()
            await f.fetch("https://a.example/1")
            await f.fetch("https://b.example/1")
            t1 = time.monotonic()
            await f.fetch("https://a.example/2")
            t2 = time.monotonic()
            return t1 - t0, t2 - t0
    other_host, same_host = _run(go())
    assert other_host < 0.25 and same_host >= 0.29


def test_guarded_backend_checks_ip_at_connect(monkeypatch):
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    calls = []

    class Inner:
        async def connect_tcp(self, host, port, **kw):
            calls.append((host, port))
            return "stream"

        async def sleep(self, s):
            pass

    gb = F.GuardedBackend(Inner(), _resolver({"rebind.example": ["127.0.0.1"], "good.example": [PUBLIC_IP]}))
    with pytest.raises(F.BlockedURL):
        _run(gb.connect_tcp("rebind.example", 443))
    assert _run(gb.connect_tcp("good.example", 443)) == "stream"
    assert calls == [(PUBLIC_IP, 443)]   # soket doğrulanan IP'ye açıldı
    # varsayılan istemci taşıyıcısı bu arka ucu kullanır
    t = F._guarded_transport(_resolver())
    assert isinstance(t._pool._network_backend, F.GuardedBackend)


def test_allow_private_flag_is_off_by_default_and_test_only(monkeypatch):
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    assert F.allow_private() is False
    with pytest.raises(F.BlockedURL):
        _run(F.resolve_checked("127.0.0.1", 80, _resolver()))
    monkeypatch.setenv("URL_IMPORT_ALLOW_PRIVATE", "1")
    assert _run(F.resolve_checked("127.0.0.1", 8765, _resolver())) == ["127.0.0.1"]
    assert F.check_url_syntax("http://127.0.0.1:8765/x")[2] == 8765
    # bayrak açıkken bile bulut metadata / link-local engelli
    for ip in ("169.254.169.254", "fe80::1", "fd00:ec2::254"):
        with pytest.raises(F.BlockedURL):
            _run(F.resolve_checked(ip, 80, _resolver()))


def test_convert_image_validation():
    out = J.convert_image(_img("JPEG", (2400, 1200)), "image/jpeg")
    from PIL import Image
    im = Image.open(io.BytesIO(out))
    assert im.format == "WEBP" and max(im.size) == 1600
    assert J.convert_image(_img("PNG"), "image/png")[:4] == b"RIFF"
    with pytest.raises(ValueError, match="türü"):
        J.convert_image(_img("JPEG"), "text/html")
    with pytest.raises(ValueError, match="çözülemedi"):
        J.convert_image(b"<html>not an image</html>", "image/jpeg")
    with pytest.raises(ValueError, match="biçimi"):
        J.convert_image(_img("GIF"), "image/jpeg")
    with pytest.raises(ValueError, match="küçük"):
        J.convert_image(_img("PNG", (40, 40)), "image/png")


def test_validate_options():
    o = J.validate_options({"urls": "www.grayzer.example/kategori/liftler\n\n# yorum\nhttps://x.example/"})
    assert o["urls"] == ["https://www.grayzer.example/kategori/liftler", "https://x.example/"]
    assert o["demo"] is True and o["max_per_category"] == 30 and o["publish"] and o["import_images"]
    assert J.validate_options({"urls": ["https://a.example"], "demo": False})["demo"] is True  # zorunlu
    for bad in ({"urls": ""}, {"urls": "https://a.example", "category_mode": "fixed"},
                {"urls": "https://a.example", "max_per_category": 0},
                {"urls": "https://a.example", "price_multiplier": "abc"}):
        with pytest.raises(ValueError):
            J.validate_options(bad)
    with pytest.raises(F.BlockedURL):
        J.validate_options({"urls": "ftp://a.example/x"})


# ── iş akışı (gerçek localdb, sahte HTTP + sahte depo) ───────────────────────

@pytest.fixture
def db(tmp_path):
    from localdb import AsyncIOMotorClient
    return AsyncIOMotorClient(path=str(tmp_path / "imp.db"))["test"]


class Store:
    def __init__(self, db):
        self.db, self.n, self.saved = db, 0, []

    async def store(self, data, ctype, ext, name, extra=None):
        self.n += 1
        rec = {"id": f"f{self.n}", "storage_path": f"{self.n}.{ext}", "original_filename": name,
               "content_type": ctype, "size": len(data), **(extra or {})}
        self.saved.append(data)
        await self.db.files.insert_one(rec)
        return {"success": True, "path": rec["storage_path"], "url": f"/api/upload/files/{rec['storage_path']}"}

    async def delete(self, rec):
        await self.db.files.delete_one({"id": rec["id"]})


def _creator(db):
    counter = {"n": 0}

    async def create(data):
        counter["n"] += 1
        pid = f"p{counter['n']}"
        await db.products.insert_one({**data, "id": pid, "slug": f"urun-{pid}",
                                      "category_ids": data.get("categories") or []})
        return {"id": pid}
    return create


def _ld_page(name, price, sku="", images=(), avail="InStock", crumbs=("Liftler",)):
    import json
    ld = {"@context": "https://schema.org", "@type": "Product", "name": name,
          "image": list(images), "offers": {"@type": "Offer", "price": str(price), "priceCurrency": "TRY",
                                            "availability": f"https://schema.org/{avail}"},
          "description": f"{name} açıklaması."}
    if sku:
        ld["sku"] = sku
    bc = {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": c}
                                                         for i, c in enumerate(crumbs)]}
    return (f'<html><head><script type="application/ld+json">{json.dumps([ld, bc])}</script></head>'
            f"<body><h1>{name}</h1></body></html>").encode()


def _shop_routes():
    H = {"content-type": "text/html; charset=utf-8"}
    J_ = {"content-type": "image/jpeg"}
    ide = "https://shop.ideasoft.example"
    g = "https://www.grayzer.example"
    a = "https://www.algikitelli.example"
    return {
        f"{ide}/kategori/liftler": (200, H, fx("ideasoft_listing_p1.html")),
        f"{ide}/kategori/liftler?tp=2": (200, H, fx("ideasoft_listing_p2.html")),
        f"{ide}/urun/iki-sutunlu-lift-4-ton": (200, H, _ld_page("İki Sütunlu Lift 4 Ton", "129900", "IS-4",
                                                                 [f"{ide}/img/is4.jpg"], crumbs=("Liftler", "İki Sütunlu Liftler"))),
        f"{ide}/urun/makasli-lift-3-2-ton": (200, H, _ld_page("Makaslı Lift 3,2 Ton", "162500", "", [f"{ide}/img/mk.jpg"])),
        f"{ide}/urun/motosiklet-lifti-500-kg": (200, H, b"<html><body><p>Kampanya sayfasi</p></body></html>"),
        # dort-sutunlu-lift-4-ton → 404 (başarısız)
        f"{ide}/img/is4.jpg": (200, J_, _img()),
        f"{ide}/img/mk.jpg": (200, J_, _img(color=(1, 2, 3))),
        f"{g}/urun/4-ton-cift-sutunlu-hidrolik-lift-grz-40": (200, H, fx("jsonld_product.html")),
        "https://cdn.grayzer.example/img/lift-1.jpg": (200, J_, _img()),
        "https://cdn.grayzer.example/img/lift-2.png": (200, {"content-type": "image/png"}, _img("PNG")),
        f"{g}/images/lift-3.webp": (200, {"content-type": "text/html"}, b"<html>hotlink korumasi</html>"),
        f"{a}/200-lt-pistonlu-hava-kompresoru-3-hp": (200, H, fx("og_only_product.html")),
        f"{a}/uploads/kompresor-200-1.jpg": (200, J_, _img()),
    }


def _run_job(db, store, urls, routes, dns=None, **opts):
    async def go():
        o = J.validate_options({"urls": urls, **opts})
        f = _fetcher(routes, dns=dns)
        jid = await J.start_job(db, o, create_product=_creator(db), store_image=store.store,
                                delete_file=store.delete, fetcher=f, user={"email": "a@example.com"})
        await J._RUNNING[jid]
        return await J.get_job(db, jid)
    return _run(go())


def test_job_end_to_end_dedupe_and_removal(db, monkeypatch):
    from seed_categories import load_tree, seed_categories
    monkeypatch.delenv("URL_IMPORT_ALLOW_PRIVATE", raising=False)
    _run(seed_categories(db, load_tree()))
    _run(db.products.insert_one({"id": "real1", "name": "Gerçek ürün", "is_active": True}))
    store = Store(db)
    urls = ["https://shop.ideasoft.example/kategori/liftler",
            "https://www.grayzer.example/urun/4-ton-cift-sutunlu-hidrolik-lift-grz-40",
            "https://www.algikitelli.example/200-lt-pistonlu-hava-kompresoru-3-hp",
            "https://intranet.example/admin"]
    job = _run_job(db, store, urls, _shop_routes(), dns={"intranet.example": ["10.0.0.9"]}, price_multiplier="0.9")
    assert job["status"] == "done", job
    c = job["counters"]
    assert (c["found"], c["imported"], c["failed"], c["skipped"]) == (6, 4, 2, 1), c
    log = {x["url"]: x for x in job["url_log"]}
    assert log["https://shop.ideasoft.example/kategori/liftler"]["kind"] == "listing"
    assert log["https://shop.ideasoft.example/kategori/liftler"]["found"] == 4
    assert log["https://shop.ideasoft.example/kategori/liftler"]["pages"] == 2
    assert log["https://intranet.example/admin"]["status"] == "failed"
    assert "engellendi" in log["https://intranet.example/admin"]["message"]
    items = {i["source_url"]: i for i in job["items"]}
    assert items["https://shop.ideasoft.example/urun/dort-sutunlu-lift-4-ton"]["status"] == "failed"
    assert items["https://shop.ideasoft.example/urun/motosiklet-lifti-500-kg"]["status"] == "skipped"

    prods = {p["source_url"]: p for p in _run(db.products.find({"seed_source": SEED_SOURCE}, {"_id": 0}).to_list(50))}
    assert len(prods) == 4
    grz = prods["https://www.grayzer.example/urun/4-ton-cift-sutunlu-hidrolik-lift-grz-40"]
    assert grz["demo"] is True and grz["noindex"] is True and grz["seed_source"] == "url_import_v1"
    assert grz["source_host"] == "grayzer.example" and grz["image_credit"] == "Görsel: grayzer.example"
    assert grz["price"] == round(129900 * 0.9, 2) and grz["stock"] == 10 and grz["is_active"] is True
    assert grz["sku"] == "GRZ-40" and grz["gtin"] == "8680000000017" and grz["brand"] == "Grayzer"
    assert len(grz["images"]) == 2 and all(u.startswith("/api/upload/files/") for u in grz["images"])
    assert any("lift-3.webp" in w for w in items[grz["source_url"]]["warnings"])  # text/html görsel reddedildi
    cats = {c["id"]: c["slug"] for c in _run(db.categories.find({}, {"_id": 0}).to_list(500))}
    assert [cats[x] for x in grz["category_ids"]] == ["iki-sutunlu-liftler", "liftler"]
    assert grz["specs"]["lifting_capacity_kg"] == 4000 and grz["specs"]["motor_power_kw"] == 2.2
    assert {"name": "Sütunlar Arası Mesafe", "value": "2.800 mm"} in grz["extra_specs"]
    assert "<script" not in grz["description"] and "href" not in grz["description"]
    assert grz["cod_disabled"] is False

    comp = prods["https://www.algikitelli.example/200-lt-pistonlu-hava-kompresoru-3-hp"]
    assert comp["stock"] == 0  # kaynakta stokta yok
    assert comp["sku"].startswith("IMP-") and len(comp["sku"]) == 12
    assert [cats[x] for x in comp["category_ids"]][0] == "pistonlu-kompresorler"
    mk = prods["https://shop.ideasoft.example/urun/makasli-lift-3-2-ton"]
    assert [cats[x] for x in mk["category_ids"]] == ["makasli-liftler", "liftler"]

    files = _run(db.files.find({"seed_source": SEED_SOURCE}, {"_id": 0}).to_list(50))
    assert len(files) == 5 and all(f["demo"] is True for f in files)
    from PIL import Image
    assert all(Image.open(io.BytesIO(b)).format == "WEBP" for b in store.saved)
    old_grz_files = {f["id"] for f in files if f["source_page"] == grz["source_url"]}

    # yeniden aktarım: yeni ürün açılmaz, mevcut güncellenir; eski görseller silinir
    job2 = _run_job(db, store, ["https://www.grayzer.example/urun/4-ton-cift-sutunlu-hidrolik-lift-grz-40"],
                    _shop_routes(), fixed_price="1000")
    assert job2["counters"]["updated"] == 1 and job2["counters"]["imported"] == 0
    assert _run(db.products.count_documents({"seed_source": SEED_SOURCE})) == 4
    grz2 = _run(db.products.find_one({"id": grz["id"]}, {"_id": 0}))
    assert grz2["price"] == 1000 and grz2["slug"] == grz["slug"]
    ids_now = {f["id"] for f in _run(db.files.find({"source_page": grz["source_url"]}, {"_id": 0}).to_list(20))}
    assert ids_now and not (ids_now & old_grz_files)

    st = _run(J.import_status(db))
    assert st["products"] == 4 and st["hosts"]["grayzer.example"] == 1

    rm = _run(J.remove_imports(db, store.delete))
    assert rm["removed_products"] == 4
    assert _run(db.products.count_documents({})) == 1 and _run(db.files.count_documents({})) == 0


def test_listing_cap_and_unpublished_without_price(db):
    _run(db.categories.insert_one({"id": "k1", "name": "Liftler", "slug": "liftler"}))
    routes = _shop_routes()
    routes["https://shop.ideasoft.example/urun/iki-sutunlu-lift-4-ton"] = (
        200, {"content-type": "text/html"},
        b'<html><head><meta property="og:type" content="product"><meta property="og:title" content="Fiyatsiz Lift">'
        b"</head><body><h1>Fiyatsiz Lift</h1></body></html>")
    store = Store(db)
    job = _run_job(db, store, ["https://shop.ideasoft.example/kategori/liftler"], routes, max_per_category=2,
                   import_images=False, category_mode="fixed", category_id="k1")
    log = job["url_log"][0]
    assert log["found"] == 2 and log["pages"] == 1
    p = _run(db.products.find_one({"name": "Fiyatsiz Lift"}, {"_id": 0}))
    assert p["is_active"] is False and p["images"] == [] and p["category_ids"] == ["k1"]
    assert any("taslak" in w for w in job["items"][0]["warnings"])
    assert _run(db.files.count_documents({})) == 0


def test_demo_remove_includes_imports_but_reload_does_not(db, monkeypatch):
    import demo_content as dc
    mod = types.ModuleType("routes.upload")

    async def delete_stored_file(rec):
        await db.files.delete_one({"id": rec["id"]})
    mod.delete_stored_file = delete_stored_file
    pkg = types.ModuleType("routes")
    pkg.__path__ = [str(ROOT / "routes")]
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.upload", mod)
    _run(db.products.insert_one({"id": "i1", "demo": True, "seed_source": SEED_SOURCE}))
    _run(db.files.insert_one({"id": "fi1", "demo": True, "seed_source": SEED_SOURCE}))
    _run(db.products.insert_one({"id": "d1", "demo": True, "seed_source": dc.DEMO_TAG}))
    _run(db.products.insert_one({"id": "real", "name": "Gerçek"}))
    assert _run(dc.demo_status(db))["imported_products"] == 1
    r0 = _run(dc.remove_demo(db))           # load_demo'nun kullandığı yol: içe aktarılanlara dokunmaz
    assert r0["removed_products"] == 1 and _run(db.products.find_one({"id": "i1"}))
    r = _run(dc.remove_demo(db, include_imports=True))   # panel "Kaldır"
    assert r["removed_imported_products"] == 1 and r["removed_files"] == 1
    assert [p["id"] for p in _run(db.products.find({}, {"_id": 0}).to_list(10))] == ["real"]


def _real_routes(monkeypatch):
    """Diğer test modüllerinin sys.modules'e bıraktığı sahte `routes` paketlerini (yalnız bu test
    süresince) gerçek paketle değiştirir; tam takımda sıra bağımlılığını önler."""
    real_dir = str(ROOT / "routes")
    for name in [n for n in list(sys.modules) if n == "routes" or n.startswith("routes.")]:
        mod = sys.modules[name]
        f = getattr(mod, "__file__", None) or ""
        if not f.startswith(real_dir):
            monkeypatch.delitem(sys.modules, name)


# ── vitrin: sitemap / feed / robots ─────────────────────────────────────────

def test_noindex_products_excluded_from_sitemap_feeds_and_get_robots(db, monkeypatch):
    _real_routes(monkeypatch)
    import routes.analytics_extra as ax
    import routes.products as rp
    import routes.seo as seo
    from seo_runtime import resolve_product
    from tenant_config import get_tenant_config
    for m in (seo, rp, ax):
        monkeypatch.setattr(m, "db", db)
    _run(db.products.insert_one({"id": "a", "slug": "gercek-urun", "name": "Gerçek", "is_active": True, "price": 10}))
    _run(db.products.insert_one({"id": "b", "slug": "demo-aktarilan", "name": "Demo", "is_active": True, "price": 10,
                                 "noindex": True, "seed_source": SEED_SOURCE}))
    body = _run(seo.sitemap_xml()).body.decode()
    assert "/urun/gercek-urun" in body and "demo-aktarilan" not in body
    _site, _shop, prods = _run(rp._feed_site_shop_prods())
    assert [p["id"] for p in prods] == ["a"]
    xml = _run(ax.google_merchant_feed()).body.decode()
    assert "Demo" not in xml
    cfg = _run(get_tenant_config(db))
    assert resolve_product({"name": "Demo", "slug": "x", "noindex": True}, cfg)["robots"] == "noindex,nofollow"
    assert resolve_product({"name": "Gerçek", "slug": "y"}, cfg)["robots"] != "noindex,nofollow"


# ── panel uçları ────────────────────────────────────────────────────────────

@pytest.fixture
def client(db, monkeypatch):
    _real_routes(monkeypatch)
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import routes.url_import as ui
    monkeypatch.setattr(ui, "db", db)
    app = FastAPI()
    app.include_router(ui.router, prefix="/api")
    c = TestClient(app)
    c.app_ = app
    c.ui = ui
    return c


def test_api_requires_permission(client):
    assert client.get("/api/admin/url-import/status").status_code in (401, 403)
    assert client.post("/api/admin/url-import/jobs", json={"urls": "https://a.example"}).status_code in (401, 403)
    assert client.delete("/api/admin/url-import/products").status_code in (401, 403)


def test_api_validation_status_and_remove(client, db, monkeypatch):
    client.app_.dependency_overrides[client.ui.require_url_import] = lambda: {"id": "u1", "email": "a@example.com"}
    import routes.upload as up

    async def fake_delete(rec):
        await db.files.delete_one({"id": rec["id"]})
    monkeypatch.setattr(up, "delete_stored_file", fake_delete)
    r = client.post("/api/admin/url-import/jobs", json={"urls": ""})
    assert r.status_code == 400 and "URL" in r.json()["detail"]
    r = client.post("/api/admin/url-import/jobs", json={"urls": "ftp://a.example/x"})
    assert r.status_code == 400 and "http" in r.json()["detail"]
    r = client.post("/api/admin/url-import/jobs", json={"urls": "https://a.example/", "category_mode": "fixed",
                                                        "category_id": "yok"})
    assert r.status_code == 400 and "kategori" in r.json()["detail"].lower()
    _run(db.products.insert_one({"id": "i1", "demo": True, "seed_source": SEED_SOURCE, "source_host": "x.example"}))
    _run(db.files.insert_one({"id": "f1", "demo": True, "seed_source": SEED_SOURCE}))
    st = client.get("/api/admin/url-import/status").json()
    assert st["products"] == 1 and st["files"] == 1 and st["hosts"] == {"x.example": 1}
    assert client.get("/api/admin/url-import/jobs/yok").status_code == 404
    r = client.delete("/api/admin/url-import/products")
    assert r.status_code == 200 and r.json() == {"removed_products": 1, "removed_files": 1}
