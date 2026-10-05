"""SSRF korumalı, nazik HTTP istemcisi (URL'den Ürün Aktar).

Kurallar:
  * yalnız http/https; kullanıcı:parola içeren URL reddedilir
  * yalnız standart portlar (80/443 ya da port belirtilmemiş)
  * host DNS ile çözülür; çözülen adreslerden BİRİ bile genel (global) değilse istek yapılmaz —
    özel (10/8, 172.16/12, 192.168/16, fc00::/7), loopback, link-local (169.254/16 → bulut metadata
    169.254.169.254 dahil), CGNAT, multicast, ayrılmış/belirtilmemiş adresler engellenir
  * bağlantı ANINDA da aynı denetim yapılır ve soket doğrulanan IP'ye açılır (DNS rebinding'e karşı;
    TLS SNI/sertifika doğrulaması yine host adıyla yapılır)
  * yönlendirmeler elle izlenir: en çok 3, her adımda tüm denetimler yeniden
  * HTML yanıtı en çok 5 MB, görsel en çok 5 MB (akış hâlinde okunur, aşılırsa kesilir)
  * çerez SAKLANMAZ (boş izin politikalı çerez kavanozu), ortam proxy/kimlik bilgisi kullanılmaz
  * host başına en az 1 sn aralık, 20 sn zaman aşımı, tarayıcı benzeri User-Agent

TEST-ONLY: URL_IMPORT_ALLOW_PRIVATE=1 ortam değişkeni loopback/özel adreslere ve standart dışı
portlara izin verir (yalnız yerel uçtan uca test için; ÜRETİMDE ASLA AÇMAYIN). Varsayılan kapalı.
Bayrak açıkken bile link-local/metadata (169.254.169.254, fe80::/10) ve multicast engelli kalır.
"""
from __future__ import annotations

import asyncio
import http.cookiejar
import ipaddress
import os
import socket
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List, Optional
from urllib.parse import urljoin, urlsplit

import httpx

MAX_REDIRECTS = 3
MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT = 20.0
DEFAULT_INTERVAL = 1.0
ALLOWED_PORTS = {80, 443}

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
BASE_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.6",
}
HTML_ACCEPT = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5"
IMAGE_ACCEPT = "image/webp,image/png,image/jpeg;q=0.9,*/*;q=0.3"

Resolver = Callable[[str, int], Awaitable[List[str]]]


class FetchError(Exception):
    """Kullanıcıya gösterilecek Türkçe açıklamalı getirme hatası."""


class BlockedURL(FetchError):
    """SSRF politikası gereği engellenen adres."""


def allow_private() -> bool:
    """TEST-ONLY bayrak (bkz. modül başı). Her çağrıda okunur."""
    return os.environ.get("URL_IMPORT_ALLOW_PRIVATE", "").strip() == "1"


def ip_blocked(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str.split("%", 1)[0])
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    if isinstance(ip, ipaddress.IPv6Address) and ip.sixtofour:
        ip = ip.sixtofour
    return (not ip.is_global) or ip.is_multicast or ip.is_reserved or ip.is_loopback \
        or ip.is_link_local or ip.is_private or ip.is_unspecified


async def system_resolver(host: str, port: int) -> List[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise FetchError(f"Alan adı çözümlenemedi ({host})") from e
    out: List[str] = []
    for info in infos:
        addr = info[4][0]
        if addr not in out:
            out.append(addr)
    if not out:
        raise FetchError(f"Alan adı çözümlenemedi ({host})")
    return out


def check_url_syntax(url: str) -> tuple:
    """Biçim denetimi. Dönüş: (scheme, host, port)."""
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError as e:
        raise BlockedURL("Geçersiz URL") from e
    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise BlockedURL("Yalnız http/https adresleri kabul edilir")
    if parts.username or parts.password:
        raise BlockedURL("Kullanıcı adı/parola içeren adresler kabul edilmez")
    host = (parts.hostname or "").strip().lower()
    if not host:
        raise BlockedURL("Adreste alan adı yok")
    try:
        port = parts.port
    except ValueError as e:
        raise BlockedURL("Geçersiz port") from e
    if port is None:
        port = 443 if scheme == "https" else 80
    if port not in ALLOWED_PORTS and not allow_private():
        raise BlockedURL(f"Standart dışı port engellendi ({port})")
    return scheme, host, port


def ip_always_blocked(ip_str: str) -> bool:
    """TEST-ONLY bayrak açıkken bile engellenenler: link-local (169.254/16 — bulut metadata
    169.254.169.254 dahil, fe80::/10), multicast, belirtilmemiş adres."""
    try:
        ip = ipaddress.ip_address(ip_str.split("%", 1)[0])
    except ValueError:
        return True
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_link_local or ip.is_multicast or ip.is_unspecified or str(ip) == "fd00:ec2::254"


async def resolve_checked(host: str, port: int, resolver: Resolver) -> List[str]:
    """Host'u çözer; adreslerden biri bile engelliyse BlockedURL."""
    try:
        ipaddress.ip_address(host.strip("[]"))
        ips = [host.strip("[]")]
    except ValueError:
        ips = await resolver(host, port)
    check = ip_always_blocked if allow_private() else ip_blocked
    bad = [ip for ip in ips if check(ip)]
    if bad:
        raise BlockedURL(f"İç/özel ağ adresi engellendi ({host} → {bad[0]})")
    return ips


try:  # httpcore ağ arka ucu: bağlantı anında IP denetimi + doğrulanan IP'ye bağlanma
    import httpcore

    class GuardedBackend(httpcore.AsyncNetworkBackend):  # type: ignore[no-redef]
        def __init__(self, inner, resolver: Resolver):
            self._inner = inner
            self._resolver = resolver

        async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            ips = await resolve_checked(str(host), int(port), self._resolver)
            last: Optional[BaseException] = None
            for ip in ips:
                try:
                    return await self._inner.connect_tcp(ip, port, timeout=timeout, local_address=local_address,
                                                         socket_options=socket_options)
                except Exception as e:  # noqa: BLE001 — sıradaki adresi dene
                    last = e
            raise last or FetchError("Bağlantı kurulamadı")

        async def connect_unix_socket(self, path, timeout=None, socket_options=None):
            raise BlockedURL("Unix soketi engellendi")

        async def sleep(self, seconds):
            await self._inner.sleep(seconds)
except Exception:  # noqa: BLE001 — httpcore iç API'si değişirse yalnız ön denetim kalır
    httpcore = None  # type: ignore[assignment]


def _guarded_transport(resolver: Resolver) -> httpx.AsyncBaseTransport:
    t = httpx.AsyncHTTPTransport(retries=0)
    pool = getattr(t, "_pool", None)
    if httpcore is not None and pool is not None and hasattr(pool, "_network_backend"):
        pool._network_backend = GuardedBackend(pool._network_backend, resolver)
    return t


def _no_cookie_jar() -> http.cookiejar.CookieJar:
    return http.cookiejar.CookieJar(policy=http.cookiejar.DefaultCookiePolicy(allowed_domains=[]))


@dataclass
class FetchResult:
    url: str             # son (yönlendirme sonrası) adres
    status: int
    content_type: str
    charset: Optional[str]
    body: bytes


class Fetcher:
    """Tek iş boyunca kullanılan istemci. `transport` / `resolver` testler için enjekte edilebilir."""

    def __init__(self, *, min_interval: float = DEFAULT_INTERVAL, timeout: float = DEFAULT_TIMEOUT,
                 transport: Optional[httpx.AsyncBaseTransport] = None, resolver: Optional[Resolver] = None):
        self.resolver: Resolver = resolver or system_resolver
        self.min_interval = max(0.0, float(min_interval))
        self._last: Dict[str, float] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self.requests = 0
        self.client = httpx.AsyncClient(
            transport=transport or _guarded_transport(self.resolver),
            timeout=httpx.Timeout(timeout),
            follow_redirects=False,
            trust_env=False,
            cookies=_no_cookie_jar(),
            headers=BASE_HEADERS,
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def _throttle(self, host: str):
        lock = self._locks.setdefault(host, asyncio.Lock())
        async with lock:
            wait = self._last.get(host, 0.0) + self.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last[host] = time.monotonic()

    async def fetch(self, url: str, *, kind: str = "html", max_bytes: Optional[int] = None,
                    headers: Optional[Dict[str, str]] = None) -> FetchResult:
        """GET; yönlendirmeleri elle izler. kind: "html" | "image". headers: yalnız Referer kabul
        edilir (görsel sıcak-bağlantı korumalı CDN'ler için ürün sayfası adresi)."""
        limit = max_bytes or (MAX_HTML_BYTES if kind == "html" else MAX_IMAGE_BYTES)
        accept = HTML_ACCEPT if kind == "html" else IMAGE_ACCEPT
        cur = str(url or "").strip()
        for _hop in range(MAX_REDIRECTS + 1):
            _scheme, host, port = check_url_syntax(cur)
            await resolve_checked(host, port, self.resolver)
            await self._throttle(host)
            self.requests += 1
            try:
                req_headers = {"Accept": accept}
                ref = str((headers or {}).get("Referer") or "").strip()
                if ref.startswith(("http://", "https://")) and len(ref) < 2048:
                    req_headers["Referer"] = ref
                async with self.client.stream("GET", cur, headers=req_headers) as r:
                    if r.status_code in (301, 302, 303, 307, 308):
                        loc = r.headers.get("location")
                        if not loc:
                            raise FetchError(f"HTTP {r.status_code} (hedefsiz yönlendirme)")
                        cur = urljoin(cur, loc.strip())
                        continue
                    if r.status_code >= 400:
                        raise FetchError(f"HTTP {r.status_code}")
                    ctype_full = r.headers.get("content-type", "")
                    ctype = ctype_full.split(";", 1)[0].strip().lower()
                    charset = None
                    for part in ctype_full.split(";")[1:]:
                        k, _, v = part.partition("=")
                        if k.strip().lower() == "charset" and v.strip():
                            charset = v.strip().strip('"\'')
                    if kind == "html" and ctype and ctype not in ("text/html", "application/xhtml+xml", "text/plain"):
                        raise FetchError(f"HTML sayfası değil ({ctype})")
                    try:
                        declared = int(r.headers.get("content-length") or 0)
                    except ValueError:
                        declared = 0
                    if declared > limit:
                        raise FetchError(f"Yanıt çok büyük ({declared // 1024} KB > {limit // 1024} KB)")
                    buf = bytearray()
                    async for chunk in r.aiter_bytes():
                        buf.extend(chunk)
                        if len(buf) > limit:
                            raise FetchError(f"Yanıt çok büyük (> {limit // 1024} KB)")
                    return FetchResult(url=str(r.url), status=r.status_code, content_type=ctype,
                                       charset=charset, body=bytes(buf))
            except FetchError:
                raise
            except httpx.TimeoutException as e:
                raise FetchError("Zaman aşımı (20 sn)") from e
            except httpx.HTTPError as e:
                raise FetchError(f"Bağlantı hatası: {type(e).__name__}") from e
        raise FetchError(f"Çok fazla yönlendirme (> {MAX_REDIRECTS})")
