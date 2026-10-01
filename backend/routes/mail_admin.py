"""
Mail Yönetimi — kendi barındırdığımız mail sunucusunun (deploy/mail) admin API'si.

Panel ↔ sunucu köprüsü: API süreci (Linux kullanıcısı `garajtek`) yalnız
    sudo -n /usr/local/sbin/garajtek-mail <komut> ... --json
çalıştırabilir (/etc/sudoers.d/garajtek-mail). Kabuk KULLANILMAZ
(asyncio.create_subprocess_exec), şifreler argv yerine stdin ile gider, her çağrının
zaman aşımı vardır. Araç kurulu değilse (geliştirme ortamı) 503 + {"installed": false}.

  GET    /api/admin/mail/status
  GET    /api/admin/mail/mailboxes
  POST   /api/admin/mail/mailboxes                      {email, password?, random?, quota?}
  POST   /api/admin/mail/mailboxes/{email}/password     {password?, random?}
  PUT    /api/admin/mail/mailboxes/{email}/quota        {quota}
  DELETE /api/admin/mail/mailboxes/{email}?purge=false
  GET    /api/admin/mail/aliases
  POST   /api/admin/mail/aliases                        {source, destination}
  DELETE /api/admin/mail/aliases/{source}
  GET    /api/admin/mail/dns-check
  GET    /api/admin/mail/port25-check
  GET    /api/admin/mail/queue
  POST   /api/admin/mail/queue/flush
  DELETE /api/admin/mail/queue/{queue_id}
  POST   /api/admin/mail/test-send                      {to}
  GET    /api/admin/mail/dkim-record
  POST   /api/admin/mail/use-for-site-mail              site bildirimlerini noreply@ ile bu sunucudan gönder

Yetki: `settings.mail_server` (süper-admin her zaman geçer). Değiştiren işlemler
activity_audit.record_admin_audit ile kaydedilir (şifreler asla kaydedilmez).
"""
import asyncio
import json
import os
import re
import shutil
from datetime import datetime, timezone
from functools import wraps
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .deps import db, require_permission
from activity_audit import record_admin_audit

router = APIRouter(prefix="/admin/mail", tags=["mail-admin"])

PERM = "settings.mail_server"
CLI_PATH = os.environ.get("GARAJTEK_MAIL_CLI", "/usr/local/sbin/garajtek-mail")
SUDO_PATH = os.environ.get("GARAJTEK_MAIL_SUDO", "/usr/bin/sudo")
DEFAULT_TIMEOUT = 30
NOT_INSTALLED_MSG = "Mail sunucusu kurulu değil — deploy/mail/README.md"

# Arka uçta da (savunma derinliği) sıkı biçim kontrolü; asıl alan adı kontrolünü CLI yapar.
_EMAIL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9._+-]{0,62}[a-z0-9])?@(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_QUOTA_RE = re.compile(r"^(0|[1-9][0-9]{0,5}[MG])$")
_QUEUE_ID_RE = re.compile(r"^([0-9A-Za-z]{5,20}|ALL)$")


class MailCliError(Exception):
    def __init__(self, status: int, body: dict):
        super().__init__(body.get("message") or body.get("detail") or "mail cli error")
        self.status = status
        self.body = body


def _err(status: int, message: str, **extra) -> MailCliError:
    return MailCliError(status, {"detail": message, "message": message, **extra})


def mail_endpoint(fn):
    """CLI hatalarını tutarlı JSON yanıtlarına çevirir (503 kurulu değil, 4xx doğrulama...)."""
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except MailCliError as e:
            return JSONResponse(status_code=e.status, content=e.body)
    return wrapper


def cli_installed() -> bool:
    return os.path.isfile(CLI_PATH) and os.access(CLI_PATH, os.X_OK)


def _command(args: list) -> list:
    if os.geteuid() == 0 and not os.path.exists(SUDO_PATH):
        return [CLI_PATH, *args]
    return [SUDO_PATH, "-n", CLI_PATH, *args]


async def run_mail_cli(args: list, stdin: Optional[str] = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    """garajtek-mail'i shell OLMADAN çalıştırır, JSON çıktısını döndürür."""
    if not cli_installed():
        raise MailCliError(503, {"installed": False, "message": NOT_INSTALLED_MSG, "detail": NOT_INSTALLED_MSG})
    for a in args:
        if not isinstance(a, str) or "\x00" in a or "\n" in a:
            raise _err(400, "Geçersiz parametre")
    try:
        proc = await asyncio.create_subprocess_exec(
            *_command(args),
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
    except (FileNotFoundError, PermissionError) as e:
        raise _err(503, "Mail aracı çalıştırılamadı: %s" % e.__class__.__name__, installed=True)
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(input=(stdin.encode() if stdin is not None else None)), timeout=timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        raise _err(504, "Mail sunucusu yanıt vermedi (zaman aşımı)")
    stdout = (out or b"").decode("utf-8", "replace").strip()
    stderr = (err or b"").decode("utf-8", "replace").strip()
    data = None
    if stdout:
        try:
            data = json.loads(stdout.splitlines()[-1])
        except ValueError:
            data = None
    if proc.returncode == 0 and isinstance(data, dict):
        return data
    if data is None:
        low = stderr.lower()
        if "password is required" in low or "not allowed" in low or "sudoers" in low or "may not run sudo" in low:
            raise _err(503, "API kullanıcısının sudo yetkisi yok — /etc/sudoers.d/garajtek-mail (deploy/mail/README.md)",
                       installed=True)
        raise _err(502, "Mail aracı beklenmeyen çıktı verdi: %s" % (stderr or stdout)[:200])
    msg = str(data.get("error") or "Mail işlemi başarısız")
    code = data.get("code")
    status = {2: 400, 3: 409, 4: 404}.get(code, 500)
    raise _err(status, msg)


def _email(value: str, field: str = "E-posta") -> str:
    v = (value or "").strip().lower()
    if len(v) > 254 or not _EMAIL_RE.match(v) or ".." in v:
        raise _err(400, "%s geçersiz" % field)
    return v


def _password(value: Optional[str]) -> Optional[str]:
    if value is None or value == "":
        return None
    if any(c in value for c in "\r\n\x00") or not (10 <= len(value) <= 128):
        raise _err(400, "Şifre 10-128 karakter olmalı ve satır sonu içermemeli")
    return value


def _quota(value: Optional[str]) -> str:
    q = (value or "1G").strip().upper().rstrip("B")
    if not _QUOTA_RE.match(q):
        raise _err(400, "Kota geçersiz (ör. 500M, 1G, 0=sınırsız)")
    return q


async def _audit(action: str, entity_id: str, current_user, request, after=None, metadata=None):
    await record_admin_audit(db, action=action, entity_type="mail_server", entity_id=entity_id,
                             after=after, current_user=current_user, request=request,
                             source="mail_admin", metadata=metadata)


# ─────────────────────────────── modeller ───────────────────────────────

class MailboxCreate(BaseModel):
    email: str
    password: Optional[str] = None
    random: bool = True
    quota: Optional[str] = "1G"


class PasswordReset(BaseModel):
    password: Optional[str] = None
    random: bool = True


class QuotaUpdate(BaseModel):
    quota: str


class AliasCreate(BaseModel):
    source: str
    destination: str


class TestSend(BaseModel):
    to: str


# ─────────────────────────────── okuma ───────────────────────────────

@router.get("/status")
@mail_endpoint
async def mail_status(current_user: dict = Depends(require_permission(PERM))):
    return await run_mail_cli(["status", "--json"])


@router.get("/mailboxes")
@mail_endpoint
async def list_mailboxes(current_user: dict = Depends(require_permission(PERM))):
    return await run_mail_cli(["list", "--json"], timeout=60)


@router.get("/aliases")
@mail_endpoint
async def list_aliases(current_user: dict = Depends(require_permission(PERM))):
    return await run_mail_cli(["alias-list", "--json"])


@router.get("/dns-check")
@mail_endpoint
async def dns_check(current_user: dict = Depends(require_permission(PERM))):
    return await run_mail_cli(["dns-check", "--json"], timeout=90)


@router.get("/port25-check")
@mail_endpoint
async def port25_check(current_user: dict = Depends(require_permission(PERM))):
    return await run_mail_cli(["port25-check", "--json"], timeout=20)


@router.get("/queue")
@mail_endpoint
async def mail_queue(current_user: dict = Depends(require_permission(PERM))):
    return await run_mail_cli(["queue", "--json"])


@router.get("/dkim-record")
@mail_endpoint
async def dkim_record(current_user: dict = Depends(require_permission(PERM))):
    return await run_mail_cli(["dkim-record", "--json"])


# ─────────────────────────────── değiştiren ───────────────────────────────

@router.post("/mailboxes")
@mail_endpoint
async def create_mailbox(payload: MailboxCreate, request: Request,
                         current_user: dict = Depends(require_permission(PERM))):
    email = _email(payload.email)
    quota = _quota(payload.quota)
    pw = _password(payload.password)
    args = ["add", "--json", "--quota", quota]
    if pw:
        args.append("--password-stdin")
    else:
        args.append("--random")
    res = await run_mail_cli(args + ["--", email], stdin=(pw + "\n") if pw else None)
    await _audit("mail.mailbox.create", email, current_user, request, after={"quota": quota})
    return res  # rastgele üretildiyse 'password' alanı YALNIZ bu yanıtta döner


@router.post("/mailboxes/{email}/password")
@mail_endpoint
async def reset_password(email: str, payload: PasswordReset, request: Request,
                         current_user: dict = Depends(require_permission(PERM))):
    email = _email(email)
    pw = _password(payload.password)
    args = ["passwd", "--json", "--password-stdin" if pw else "--random", "--", email]
    res = await run_mail_cli(args, stdin=(pw + "\n") if pw else None)
    await _audit("mail.mailbox.password_reset", email, current_user, request,
                 metadata={"generated": not bool(pw)})
    return res


@router.put("/mailboxes/{email}/quota")
@mail_endpoint
async def update_quota(email: str, payload: QuotaUpdate, request: Request,
                       current_user: dict = Depends(require_permission(PERM))):
    email = _email(email)
    quota = _quota(payload.quota)
    res = await run_mail_cli(["quota", "--json", "--", email, quota], timeout=60)
    await _audit("mail.mailbox.quota", email, current_user, request, after={"quota": quota})
    return res


@router.delete("/mailboxes/{email}")
@mail_endpoint
async def delete_mailbox(email: str, request: Request, purge: bool = Query(False),
                         current_user: dict = Depends(require_permission(PERM))):
    email = _email(email)
    args = ["del", "--json"] + (["--purge"] if purge else []) + ["--", email]
    res = await run_mail_cli(args, timeout=120)
    await _audit("mail.mailbox.delete", email, current_user, request, metadata={"purge": purge})
    return res


@router.post("/aliases")
@mail_endpoint
async def create_alias(payload: AliasCreate, request: Request,
                       current_user: dict = Depends(require_permission(PERM))):
    source = _email(payload.source, "Kaynak adres")
    dests = [_email(d, "Hedef adres") for d in (payload.destination or "").split(",") if d.strip()]
    if not dests or len(dests) > 20:
        raise HTTPException(status_code=400, detail="1-20 hedef adres girin")
    res = await run_mail_cli(["alias-add", "--json", "--", source, ",".join(dests)])
    await _audit("mail.alias.upsert", source, current_user, request, after={"destinations": dests})
    return res


@router.delete("/aliases/{source}")
@mail_endpoint
async def delete_alias(source: str, request: Request,
                       current_user: dict = Depends(require_permission(PERM))):
    source = _email(source, "Kaynak adres")
    res = await run_mail_cli(["alias-del", "--json", "--", source])
    await _audit("mail.alias.delete", source, current_user, request)
    return res


@router.post("/queue/flush")
@mail_endpoint
async def queue_flush(request: Request, current_user: dict = Depends(require_permission(PERM))):
    res = await run_mail_cli(["queue-flush", "--json"])
    await _audit("mail.queue.flush", "queue", current_user, request)
    return res


@router.delete("/queue/{queue_id}")
@mail_endpoint
async def queue_delete(queue_id: str, request: Request,
                       current_user: dict = Depends(require_permission(PERM))):
    if not _QUEUE_ID_RE.match(queue_id or ""):
        raise HTTPException(status_code=400, detail="Geçersiz kuyruk kimliği")
    res = await run_mail_cli(["queue-delete", "--json", "--", queue_id])
    await _audit("mail.queue.delete", queue_id, current_user, request)
    return res


@router.post("/test-send")
@mail_endpoint
async def test_send(payload: TestSend, request: Request,
                    current_user: dict = Depends(require_permission(PERM))):
    to = _email(payload.to, "Alıcı")
    res = await run_mail_cli(["test-send", "--json", "--", to])
    await _audit("mail.test_send", to, current_user, request)
    return res


@router.post("/use-for-site-mail")
@mail_endpoint
async def use_for_site_mail(request: Request, current_user: dict = Depends(require_permission(PERM))):
    """Site bildirimlerini (sipariş, üyelik, şifre...) bu sunucudan gönder:
    noreply@<alan> şifresi yenilenir ve settings.email_smtp → 127.0.0.1:587 STARTTLS yapılır.
    Önceki (ZeptoMail) ayar `email_smtp_previous` olarak saklanır."""
    status = await run_mail_cli(["status", "--json"])
    domain = str(status.get("domain") or "").lower()
    if not domain:
        raise _err(500, "Alan adı okunamadı")
    sender = _email("noreply@" + domain)
    boxes = await run_mail_cli(["list", "--json"], timeout=60)
    exists = any((m or {}).get("address") == sender for m in boxes.get("mailboxes") or [])
    if exists:
        res = await run_mail_cli(["passwd", "--json", "--random", "--", sender])
    else:
        res = await run_mail_cli(["add", "--json", "--random", "--quota", "1G", "--", sender])
    pw = res.get("password")
    if not pw:
        raise _err(500, "noreply şifresi üretilemedi")
    try:
        from security.crypto import encrypt as _enc
        enc_pw = _enc(pw)
    except Exception:
        enc_pw = pw
    existing = await db.settings.find_one({"id": "email_smtp"}, {"_id": 0}) or {}
    if existing and not str(existing.get("host") or "").startswith(("127.0.0.1", "localhost")):
        prev = {k: v for k, v in existing.items() if k != "id"}
        await db.settings.update_one({"id": "email_smtp_previous"},
                                     {"$set": {"id": "email_smtp_previous", **prev}}, upsert=True)
    data = {
        "id": "email_smtp", "enabled": True, "transport": "smtp",
        "host": "127.0.0.1", "port": 587, "secure": "starttls",
        "username": sender, "password": enc_pw,
        "from_name": existing.get("from_name") or "",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.settings.update_one({"id": "email_smtp"}, {"$set": data}, upsert=True)
    await _audit("mail.site_mail.enable", "email_smtp", current_user, request,
                 after={"host": "127.0.0.1", "port": 587, "username": sender})
    return {"ok": True, "username": sender, "host": "127.0.0.1", "port": 587, "secure": "starttls"}


@router.get("/installed")
async def mail_installed(current_user: dict = Depends(require_permission(PERM))):
    """Hafif kontrol (CLI çağırmaz) — UI ilk açılışta kullanır."""
    return {"installed": cli_installed(), "sudo": bool(shutil.which("sudo")),
            "message": None if cli_installed() else NOT_INSTALLED_MSG}
