"""Nesne deposu (görsel/video/PDF) — Cloudflare R2 VEYA yerel disk.

Sıra:
  1. Cloudflare R2 (S3 uyumlu) — R2_* değişkenlerinin hepsi tanımlıysa.
  2. Yerel disk — R2 yoksa ve MEDIA_DIR tanımlıysa. Dosyalar MEDIA_DIR/<key> altına
     yazılır, web sunucusu (nginx) bunları /media/ altında doğrudan servis eder;
     Cloudflare önünde önbelleğe alır. Public adres MEDIA_PUBLIC_URL'den, yoksa
     SITE_URL + "/media"dan üretilir.
  3. Hiçbiri yoksa is_enabled() False → çağıranlar eski DB fallback'ine düşer.

Fonksiyon imzaları (is_enabled / public_url / put_object / get_object / health_check)
eski R2-yalnız modülle AYNIDIR; çağıranlar (routes/upload.py,
orders.py, instagram.py) değişmeden iki depoyla da çalışır.
"""
import os
import logging
import posixpath
import tempfile

logger = logging.getLogger("r2")

_client = None


# --------------------------------------------------------------------------- #
# Yapılandırma
# --------------------------------------------------------------------------- #
def r2_configured() -> bool:
    """R2 yapılandırılmış mı?

    R2_PUBLIC_URL ŞART: yoksa public_url() relatif/bozuk bir URL üretir
    (ör. "/uploads/x.jpg") ve görsel hiçbir yerde açılmaz. Eksikse R2'yi KAPALI say.
    """
    return bool(
        os.environ.get("R2_ENDPOINT")
        and os.environ.get("R2_ACCESS_KEY_ID")
        and os.environ.get("R2_SECRET_ACCESS_KEY")
        and os.environ.get("R2_BUCKET")
        and (os.environ.get("R2_PUBLIC_URL") or "").strip().lower().startswith("http")
    )


def media_dir() -> str:
    """Yerel medya dizini (MEDIA_DIR) — tanımlı değilse ''."""
    return (os.environ.get("MEDIA_DIR") or "").strip()


def media_public_base() -> str:
    """Yerel medyanın public taban adresi (sonunda / yok)."""
    base = (os.environ.get("MEDIA_PUBLIC_URL") or "").strip()
    if not base:
        site = (os.environ.get("SITE_URL") or "").strip().rstrip("/")
        base = f"{site}/media" if site else ""
    return base.rstrip("/")


def local_configured() -> bool:
    """Yerel disk deposu kullanılabilir mi? (MEDIA_DIR + mutlak http(s) public adres)"""
    return bool(media_dir()) and media_public_base().lower().startswith("http")


def backend_name() -> str:
    """Etkin depo: 'r2', 'local' veya '' (yok)."""
    if r2_configured():
        return "r2"
    if local_configured():
        return "local"
    return ""


def is_enabled() -> bool:
    """Kalıcı bir nesne deposu (R2 veya yerel disk) var mı?"""
    return bool(backend_name())


# --------------------------------------------------------------------------- #
# Yerel disk yardımcıları
# --------------------------------------------------------------------------- #
def _safe_key(key: str) -> str:
    """Anahtarı normalize eder; dizin dışına kaçışı (.., mutlak yol, boş) reddeder."""
    k = (key or "").replace("\\", "/").lstrip("/")
    norm = posixpath.normpath(k)
    if not k or norm in (".", "..") or norm.startswith("../") or "/../" in f"/{norm}/" or "\x00" in norm:
        raise ValueError(f"geçersiz nesne anahtarı: {key!r}")
    return norm


def _local_path(key: str) -> str:
    base = os.path.realpath(media_dir())
    path = os.path.realpath(os.path.join(base, _safe_key(key)))
    if not path.startswith(base + os.sep):
        raise ValueError(f"geçersiz nesne anahtarı: {key!r}")
    return path


def _local_put(key: str, data: bytes) -> None:
    path = _local_path(key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Atomik yaz: yarım dosya hiçbir zaman servis edilmez.
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o644)  # web sunucusu (www-data) okuyabilsin
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


_EXT_TYPES = {
    ".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".gif": "image/gif", ".avif": "image/avif", ".mp4": "video/mp4", ".webm": "video/webm",
    ".mov": "video/quicktime", ".pdf": "application/pdf",
}


# --------------------------------------------------------------------------- #
# R2 istemcisi
# --------------------------------------------------------------------------- #
def _get_client():
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config

        _client = boto3.client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )
    return _client


# --------------------------------------------------------------------------- #
# Genel API (imzalar değişmedi)
# --------------------------------------------------------------------------- #
def public_url(key: str) -> str:
    """Bir nesne anahtarı (key) için public URL döndürür."""
    if r2_configured() or not local_configured():
        base = os.environ.get("R2_PUBLIC_URL", "").rstrip("/")
    else:
        base = media_public_base()
    return f"{base}/{key.lstrip('/')}"


def put_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Veriyi etkin depoya (R2 → yerel disk) yazar, public URL döndürür."""
    if r2_configured():
        _get_client().put_object(
            Bucket=os.environ["R2_BUCKET"],
            Key=key.lstrip("/"),
            Body=data,
            ContentType=content_type or "application/octet-stream",
            CacheControl="public, max-age=31536000, immutable",
        )
        return public_url(key)
    if local_configured():
        _local_put(key, data)
        return public_url(_safe_key(key))
    raise RuntimeError("Nesne deposu yapılandırılmamış (R2_* veya MEDIA_DIR gerekli)")


def delete_object(key: str) -> None:
    """Nesneyi etkin depodan siler (yoksa sessizce geçer)."""
    if r2_configured():
        _get_client().delete_object(Bucket=os.environ["R2_BUCKET"], Key=key.lstrip("/"))
        return
    if local_configured():
        try:
            os.unlink(_local_path(key))
        except FileNotFoundError:
            pass


def get_object(key: str):
    """Nesneyi okur → (bytes, content_type). Yoksa (None, None)."""
    if r2_configured():
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            resp = _get_client().get_object(Bucket=os.environ["R2_BUCKET"], Key=key.lstrip("/"))
            return resp["Body"].read(), resp.get("ContentType", "application/octet-stream")
        except (BotoCoreError, ClientError):
            return None, None
    if local_configured():
        try:
            path = _local_path(key)
            with open(path, "rb") as f:
                data = f.read()
        except (OSError, ValueError):
            return None, None
        ext = os.path.splitext(path)[1].lower()
        return data, _EXT_TYPES.get(ext, "application/octet-stream")
    return None, None


def health_check() -> dict:
    """Depo bağlantısını doğrular (R2: head_bucket, yerel: dizin yazılabilir mi)."""
    if r2_configured():
        try:
            _get_client().head_bucket(Bucket=os.environ["R2_BUCKET"])
            return {"ok": True, "backend": "r2", "bucket": os.environ["R2_BUCKET"]}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "backend": "r2", "error": str(e)}
    if local_configured():
        d = media_dir()
        try:
            os.makedirs(d, exist_ok=True)
            ok = os.access(d, os.W_OK)
            return {"ok": ok, "backend": "local", "dir": d,
                    **({} if ok else {"error": "MEDIA_DIR yazılabilir değil"})}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "backend": "local", "dir": d, "error": str(e)}
    return {"ok": False, "backend": "", "error": "R2_* veya MEDIA_DIR tanımlı değil"}
