# Copyright (c) 2026 kdrgry1-oss. Tüm hakları saklıdır. Bkz. LICENSE.
"""Lisans kilidi: bu yazılım YALNIZ lisanslı alan adında (garajtek.com ve alt alan adları) çalışır.

Her HTTP isteğinin Host / X-Forwarded-Host başlığı denetlenir; başka bir alan adıyla gelen istek
403 ile reddedilir. Loopback (127.0.0.1/localhost) yalnız istek gerçekten makinenin kendisinden
geliyorsa ve ön vekil başka bir alan adı iletmiyorsa kabul edilir (sağlık kontrolü, yerel geliştirme,
testler). Lisanslı alan adı koda gömülüdür; ortam değişkeniyle DEĞİŞTİRİLEMEZ (bilerek).

Lisans sahibinin yazılı izni olmadan bu kilidi kaldırmak, atlatmak ya da yazılımı başka bir alan
adında çalıştırmak LICENSE dosyasındaki koşulların ihlalidir.
"""
import ipaddress

LICENSED_DOMAIN = "garajtek.com"
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]", "testserver"}
_LOCAL_CLIENTS = {"testclient", "localhost"}
_MSG = (b'{"detail":"Bu yaz\\u0131l\\u0131m yaln\\u0131z lisansl\\u0131 alan ad\\u0131nda '
        b'\\u00e7al\\u0131\\u015f\\u0131r."}')


def _hostname(value: str) -> str:
    v = (value or "").strip().lower().split(",")[0].strip()
    if v.startswith("["):  # [::1]:8000
        return v[: v.find("]") + 1] if "]" in v else v
    return v.rsplit(":", 1)[0] if v.count(":") == 1 else v


def is_licensed_host(host: str) -> bool:
    h = _hostname(host).rstrip(".")
    return h == LICENSED_DOMAIN or h.endswith("." + LICENSED_DOMAIN)


def _is_local_client(ip: str) -> bool:
    if not ip:
        return False
    if ip in _LOCAL_CLIENTS:
        return True
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def request_allowed(host: str, forwarded_host: str, client_ip: str) -> bool:
    if forwarded_host and not is_licensed_host(forwarded_host):
        # Ön vekil (nginx/Cloudflare) başka bir alan adı iletiyorsa: yalnız aynı makineden gelen,
        # loopback'e yönelik yerel istekte forwarded_host da loopback olabilir.
        if not (_hostname(forwarded_host) in _LOOPBACK_HOSTS and _is_local_client(client_ip)):
            return False
    if is_licensed_host(host):
        return True
    return _hostname(host) in _LOOPBACK_HOSTS and _is_local_client(client_ip)


class LicenseMiddleware:
    """Saf ASGI ara katmanı (her isteğe çok düşük ek yük)."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers") or []}
        client = scope.get("client") or ("", 0)
        if request_allowed(headers.get("host", ""), headers.get("x-forwarded-host", ""), client[0] or ""):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json; charset=utf-8"),
                                (b"cache-control", b"no-store")]})
        await send({"type": "http.response.body", "body": _MSG})
