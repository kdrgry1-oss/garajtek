"""
email_smtp.py — E-posta gonderimi Zoho ZeptoMail HTTPS API'si (port 443) uzerinden.
Railway giden SMTP portlarini (25/465/587) engelledigi icin SMTP yerine HTTPS API kullanilir.
Fonksiyon adlari korunmustur; cagiran tum moduller degismeden calisir.

settings.id="email_smtp" alanlari (ayar sayfasiyla uyumlu):
  enabled   : bool  -> gonderim aktif mi
  username  : str   -> GONDEREN e-posta adresi (or. info@example.com)
  password  : str   -> ZeptoMail "Send Mail Token" (API anahtari)
  from_name : str   -> gonderen adi (bos ise Firma Bilgileri > magaza adi)
  host      : str   -> 'eu' iceriyorsa api.zeptomail.eu, aksi halde api.zeptomail.com

Kendi mail sunucusu (deploy/mail): host 127.0.0.1 / localhost (veya transport="smtp" ya da
"smtp://sunucu") ise ZeptoMail yerine dogrudan SMTP kullanilir:
  host=127.0.0.1, port=587 (STARTTLS) | 465 (SSL), username=noreply@alanadi, password=kutu sifresi.
Mevcut ZeptoMail ayarlari (host api.zeptomail.* / smtp.zoho.*) aynen calismaya devam eder.
"""
import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

import httpx

_LOCAL_SMTP_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _use_smtp(cfg: dict) -> bool:
    host = str(cfg.get("host") or "").strip().lower()
    return (str(cfg.get("transport") or "").strip().lower() == "smtp"
            or host in _LOCAL_SMTP_HOSTS or host.startswith("smtp://"))


def _smtp_send_blocking(cfg: dict, msg: EmailMessage) -> None:
    host = str(cfg.get("host") or "127.0.0.1").strip()
    if host.lower().startswith("smtp://"):
        host = host[7:]
    if ":" in host and host.count(":") == 1:
        host, _p = host.split(":", 1)
        port = int(_p or 587)
    else:
        port = int(cfg.get("port") or 587)
    secure = str(cfg.get("secure") or "").strip().lower()
    ctx = ssl.create_default_context()
    if host.lower() in _LOCAL_SMTP_HOSTS:
        # Sertifika mail.<alan> adına; 127.0.0.1'e bağlanırken ad eşleşmez → yalnız yerelde doğrulama kapalı
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    use_ssl = port == 465 or (secure == "ssl" and port not in (25, 587))
    if use_ssl:
        client = smtplib.SMTP_SSL(host, port, context=ctx, timeout=20)
    else:
        client = smtplib.SMTP(host, port, timeout=20)
    try:
        client.ehlo()
        if not use_ssl and client.has_extn("starttls"):
            client.starttls(context=ctx)
            client.ehlo()
        if cfg.get("username") and cfg.get("password") and client.has_extn("auth"):
            client.login(str(cfg["username"]), str(cfg["password"]))
        client.send_message(msg)
    finally:
        try:
            client.quit()
        except Exception:
            pass


async def _send_via_smtp(cfg: dict, sender: str, name: str, to: str, subject: str,
                         html: str, text=None, reply_to=None) -> dict:
    msg = EmailMessage()
    msg["From"] = formataddr((name or "", sender))
    msg["To"] = to
    msg["Subject"] = subject or ""
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=(sender.split("@", 1)[-1] if "@" in sender else None))
    if reply_to:
        msg["Reply-To"] = reply_to
    msg.set_content(text or "Bu e-postayı görüntülemek için HTML destekleyen bir istemci kullanın.")
    msg.add_alternative(html or "", subtype="html")
    try:
        await asyncio.to_thread(_smtp_send_blocking, cfg, msg)
        return {"success": True, "response": "smtp: accepted"}
    except Exception as e:
        return {"success": False, "response": ("smtp: %s" % e)[:300]}


async def get_smtp_config(db) -> dict:
    cfg = await db.settings.find_one({"id": "email_smtp"}, {"_id": 0}) or {}
    # A1.1: şifre at-rest şifreli saklanır; kullanım için çöz (eski düz metin olduğu gibi geçer).
    if cfg.get("password"):
        try:
            from security.crypto import decrypt as _dec
            cfg = {**cfg, "password": _dec(cfg["password"])}
        except Exception:
            pass
    return cfg


def is_configured(cfg: dict) -> bool:
    return bool(cfg.get("enabled") and cfg.get("username") and cfg.get("password"))


def _endpoint(cfg: dict) -> str:
    # Varsayilan: Zoho EU (Avrupa) veri merkezi endpoint'i.
    # Yalnizca host ACIKCA ".com" (US) ise US endpoint kullanilir. Boylece host bos/eksik
    # olsa bile EU'ya gider (US endpoint EU token'ini reddedip "mail gitmiyor"a yol aciyordu).
    host = (cfg.get("host") or "").lower()
    base = "https://api.zeptomail.com" if "com" in host else "https://api.zeptomail.eu"
    return base + "/v1.1/email"


def _auth_header(token: str) -> str:
    token = (token or "").strip()
    if token.lower().startswith("zoho-enczapikey"):
        return token
    return "Zoho-enczapikey " + token


async def send_smtp_email(db, to: str, subject: str, html: str,
                          from_name=None, reply_to=None, text=None, wrap=True,
                          from_email=None) -> dict:
    """Tek aliciya ZeptoMail API ile mail. Doner: {success, response}.
    wrap=True (varsayilan): HTML markali magaza kabuguna (logo + sosyal footer) sarilir.
    Zaten markaliysa tekrar sarilmaz (idempotent). Boylece sistemden cikan TUM mailler
    -- uyelik, sifre, s3 durum bildirimi, toplu, test -- istisnasiz ayni tasarimda gider.
    Markasiz gitmesi gereken ozel durumlar icin wrap=False gecilebilir."""
    cfg = await get_smtp_config(db)
    if not is_configured(cfg):
        return {"success": False, "response": "email_not_configured"}

    # BEYAZ ETİKET: e-posta markasını (ad/logo/site/sosyal) ayardaki firma bilgisinden uygula.
    _store_name = ""
    try:
        from company import get_company
        from email_layout import set_brand as _set_brand
        _co = await get_company(db)
        _store_name = (_co or {}).get("store_name") or ""
        _set_brand(_co)
    except Exception:
        pass  # marka uygulanamazsa nötr varsayılanla devam
    if wrap:
        try:
            from email_layout import render_email
            html = render_email(subject, html or "")
        except Exception:
            pass  # sarma basarisiz olursa ham HTML ile devam (mail asla bloklanmaz)
    try:
        from email_layout import apply_brand as _apply_brand
        html = _apply_brand(html or "")
    except Exception:
        pass

    # from_email: çağrı bazında gönderen adresini geçersiz kılar (ör. sipariş mailleri
    # siparis@... adresinden gitsin diye). Boşsa varsayılan yapılandırılmış gönderen
    # (cfg.username) kullanılır → mevcut davranış korunur. ZeptoMail'de gönderilen adres
    # DOĞRULANMIŞ domaine ait olmalıdır (doğrulanmış alan adındaki adresler çalışır).
    sender = (str(from_email).strip() if from_email else "") or cfg.get("username")
    name = from_name or cfg.get("from_name") or _store_name or "Mağaza"
    if _use_smtp(cfg):  # kendi mail sunucusu (deploy/mail) — ZeptoMail yerine SMTP
        return await _send_via_smtp(cfg, sender, name, to, subject, html, text=text, reply_to=reply_to)
    payload = {
        "from": {"address": sender, "name": name},
        "to": [{"email_address": {"address": to}}],
        "subject": subject or "",
        "htmlbody": html or "",
    }
    if text:
        payload["textbody"] = text
    if reply_to:
        payload["reply_to"] = [{"address": reply_to}]

    headers = {
        "Authorization": _auth_header(cfg.get("password")),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(_endpoint(cfg), headers=headers, json=payload)
        ok = r.status_code in (200, 201, 202)
        return {"success": ok, "response": (r.text or "")[:400]}
    except Exception as e:
        return {"success": False, "response": str(e)[:300]}
