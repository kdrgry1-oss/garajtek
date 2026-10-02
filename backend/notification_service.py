"""
=============================================================================
notification_service.py — Çok kanallı (SMS + Mail) bildirim servisi
=============================================================================

AMAÇ:
  Siparişin durum değişiklikleri, şifre sıfırlama OTP, kargo güncellemeleri,
  sepette ürün kaldı vb. event'leri tek bir yerden, ayarlanabilir şablonlarla
  müşteriye ulaştıran ortak servis.

Kanallar:
  - SMS  : Netgsm, İletiMerkezi, Twilio, Vatansms, Verimor, Mutlucep,
           Mobildev, Postagüvercini (kargo gibi çoklu — sadece birisi aktif)
  - E-posta : Resend (mevcut altyapıyı kullanır)

Events (template keys):
  order_confirmed, order_packed, order_shipped, order_delivered,
  order_undelivered, order_cancelled, password_reset_otp,
  abandoned_cart, stock_alert, admin_new_order

Şablon içinde değişkenler {variable} ile replace edilir:
  {customer_name}, {order_number}, {amount}, {tracking_number}, {otp_code}

Her provider için credential'lar MongoDB `settings` koleksiyonunda:
  settings.id = "notification_providers"  → {sms_active, email_active, providers: {...}}

Template'ler MongoDB `notification_templates` koleksiyonunda.
=============================================================================
"""
from __future__ import annotations
import asyncio
import base64
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# ---------- Sabit liste: SMS sağlayıcıları ----------
SMS_PROVIDERS = [
    {"key": "netgsm", "name": "Netgsm"},
    {"key": "iletimerkezi", "name": "İleti Merkezi"},
    {"key": "twilio", "name": "Twilio"},
    {"key": "vatansms", "name": "VatanSMS"},
    {"key": "verimor", "name": "Verimor"},
    {"key": "mutlucep", "name": "MutluCep"},
    {"key": "mobildev", "name": "Mobildev"},
    {"key": "postagüvercini", "name": "Posta Güvercini"},
]

DEFAULT_EVENTS = [
    {"key": "order_confirmed", "name": "Sipariş Onaylandı"},
    {"key": "order_packed", "name": "Sipariş Paketleniyor"},
    {"key": "order_shipped", "name": "Sipariş Kargoya Verildi"},
    {"key": "order_delivered", "name": "Sipariş Teslim Edildi"},
    {"key": "order_undelivered", "name": "Teslim Edilemedi (Şubede Bekliyor)"},
    {"key": "order_cancelled", "name": "Sipariş İptal Edildi"},
    {"key": "order_awaiting_payment", "name": "Siparişiniz Alındı · Ödeme Bekleniyor (Havale)"},
    {"key": "order_payment_reminder", "name": "Ödeme Hatırlatma (Havale · elle gönder)"},
    {"key": "order_payment_notified", "name": "Ödeme Bildirimi Alındı"},
    {"key": "order_payment_approved", "name": "Ödemenizi Aldık (Havale Onayı)"},
    {"key": "order_pending", "name": "Sipariş Alındı (Onay Bekliyor)"},
    {"key": "order_preparing", "name": "Sipariş Hazırlanıyor"},
    {"key": "order_ready_to_ship", "name": "Kargoya Hazır"},
    {"key": "order_in_transit", "name": "Kargo Taşınıyor"},
    {"key": "order_out_for_delivery", "name": "Dağıtımda"},
    {"key": "order_return_requested", "name": "İade Talebi Oluşturuldu"},
    {"key": "order_return_approved", "name": "İade Onaylandı"},
    {"key": "order_return_rejected", "name": "İade Reddedildi"},
    {"key": "order_return_in_transit", "name": "İade Kargoda"},
    {"key": "order_returned", "name": "İade Tamamlandı"},
    {"key": "order_refunded", "name": "İade Bedeli Ödendi"},
    {"key": "order_cancel_refunded", "name": "İptal Bedeli İade Edildi (SMS: iptal→ödeme iadesi)"},
    {"key": "order_partial_refunded", "name": "Kısmi İade Yapıldı"},
    {"key": "password_reset_otp", "name": "Şifre Sıfırlama Kodu"},
    # Girişte istenen 2. adım doğrulama kodu (panel MFA). Şifre sıfırlamadan AYRI şablon:
    # müşteriye/personele "şifre sıfırlama" yazan bir mail gitmesin (kafa karıştırıyordu).
    {"key": "login_verification_code", "name": "Giriş Doğrulama Kodu"},
    {"key": "abandoned_cart", "name": "Sepette Ürün Kaldı"},
    {"key": "wishlist_back_in_stock", "name": "Favori Ürün Tekrar Stokta"},
    {"key": "welcome", "name": "Hoş Geldin (Üyelik)"},
    {"key": "stock_alert", "name": "Stok Uyarısı (Admin)"},
    {"key": "admin_new_order", "name": "Yeni Sipariş (Admin)"},
]

CHANNELS = ["sms", "email"]


_TRUSTED_HTML_VARS = frozenset({"coupon_block"})


def render_template(text: str, variables: Dict[str, Any], escape_values: bool = False) -> str:
    """{variable} formatındaki placeholder'ları doldurur.
    escape_values=True (e-posta/HTML kanalı): DEĞİŞKEN değerleri html.escape ile kaçırılır
    (şablonun kendi HTML'i korunur) → müşteri-kontrollü ad/adres alanlarıyla HTML/kimlik-avı
    enjeksiyonu engellenir (DENETİM SEC-4 F7 / bildirim Y4)."""
    if not text:
        return ""
    import html as _html_mod

    def repl(m):
        key = m.group(1).strip()
        if key not in variables:
            return m.group(0)
        val = str(variables.get(key, ""))
        # Sunucuda üretilen güvenilir HTML blokları (müşteri girdisi İÇERMEZ; içindeki
        # değerler üretildiği yerde kaçırılır) ham basılır — aksi halde hoş geldin kod
        # kutusu e-postada "<div style=...>" düz metni olarak görünüyordu.
        if escape_values and key in _TRUSTED_HTML_VARS:
            return val
        return _html_mod.escape(val) if escape_values else val
    return re.sub(r"\{([a-zA-Z0-9_]+)\}", repl, text)


def normalize_phone_tr(phone: str) -> str:
    """TR telefon numaralarını uluslararası formata çevirir (905xxxxxxxxx).
    Giriş: '0 555 123 45 67' / '5551234567' / '+905551234567' / '905551234567'
    Çıkış: '905551234567'
    """
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("90"):
        return digits
    if digits.startswith("0"):
        return "90" + digits[1:]
    if len(digits) == 10:
        return "90" + digits
    return digits


# =============================================================================
# SMS PROVIDERS
# =============================================================================

async def _sms_netgsm(cfg: Dict, to: str, message: str) -> Dict:
    """Netgsm HTTP GET API — https://api.netgsm.com.tr/sms/send/get

    Gerekli cfg alanları:
      - username : Netgsm abone numarası VEYA tanımlı API alt kullanıcı adı
      - password : API (alt) kullanıcı şifresi
      - header   : Netgsm panelinde ONAYLI gönderici adı (Originator)
    Opsiyonel cfg:
      - dil       : "TR" → Türkçe karakter destekli gönderim (varsayılan "TR")
      - appkey    : API alt kullanıcıya tanımlı uygulama anahtarı (varsa)
      - iysfilter : (ESKİ AD) İYS filtresi değeri — varsa `filter` olarak gönderilir

    İYS FİLTRESİ (17.09 — Netgsm dokümanıyla karşılaştırma sonucu):
    Netgsm'in parametre adı `filter`'dır, `iysfilter` DEĞİL. Dokümanda:
      • ticari olmayan (bilgilendirme/işlemsel) gönderimde  → "0" GÖNDERİLMELİDİR
      • bireye ticari ileti → "11", tacire ticari ileti → "12"
    Bizim kod bu parametreyi HİÇ göndermiyordu ve adını yanlış kullanıyordu. İYS kontrollü
    hesapta filtresiz gönderim, istek "00" (kuyruğa alındı) ile kabul edilip teslim
    aşamasında düşebiliyor — panelde her şey başarılı görünürken müşteriye SMS gitmiyordu.
    Buradan çıkan TÜM mesajlar işlemseldir (sipariş/kargo bildirimi, doğrulama kodu) →
    varsayılan "0". Pazarlama gönderimleri bu fonksiyondan geçmez.
    """
    gsmno = normalize_phone_tr(to)  # 905XXXXXXXXX
    url = "https://api.netgsm.com.tr/sms/send/get"
    params = {
        "usercode": cfg.get("username", ""),
        "password": cfg.get("password", ""),
        "gsmno": gsmno,
        "message": message,
        "msgheader": cfg.get("header", ""),
        "dil": (cfg.get("dil") or "TR"),  # Türkçe karakter desteği (ç,ş,ğ,ı,ö,ü)
    }
    if cfg.get("appkey"):
        params["appkey"] = cfg.get("appkey")
    # Ayarlarda değer varsa o kullanılır (eski `iysfilter` adı da kabul edilir); yoksa "0".
    _flt = str(cfg.get("filter") or cfg.get("iysfilter") or "0").strip()
    params["filter"] = _flt

    err_map = {
        "20": "Mesaj metni hatalı ya da karakter sınırı aşıldı.",
        "30": "Geçersiz kullanıcı adı/şifre, API erişim izni yok veya IP kısıtlaması var.",
        "40": "Gönderici adı (başlık) sistemde tanımlı/onaylı değil.",
        "50": "Hesap İYS kontrollü; alıcının izni bulunmuyor.",
        "51": "Gönderici adı İYS marka eşleşmesi yapılmamış.",
        "60": "Belirtilen JobID bulunamadı.",
        "70": "Hatalı veya eksik parametre.",
        "80": "Gönderim sınırı aşıldı.",
        "85": "Aynı numaraya 1 dakika içinde mükerrer gönderim sınırı.",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        text = (r.text or "").strip()
    # Netgsm GET yanıtı: başarı = "00 JOBID" (tek başarı kodu 00'dır)
    parts = text.split()
    code = parts[0] if parts else ""
    ok = code == "00"
    result = {"success": ok, "response": text}
    if ok:
        result["job_id"] = parts[1] if len(parts) > 1 else ""
    else:
        result["error"] = err_map.get(code, f"Beklenmeyen Netgsm yanıtı: {text or '(boş)'}")
    return result


async def _sms_iletimerkezi(cfg: Dict, to: str, message: str) -> Dict:
    """İletiMerkezi v1 JSON API."""
    url = "https://api.iletimerkezi.com/v1/send-sms/json"
    body = {
        "request": {
            "authentication": {"key": cfg.get("api_key", ""), "hash": cfg.get("api_hash", "")},
            "order": {
                "sender": cfg.get("header", ""),
                "message": {"text": message, "receipents": {"number": [to]}},
            },
        }
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=body)
        ok = r.status_code == 200 and "200" in r.text
        return {"success": ok, "response": r.text[:500]}


async def _sms_twilio(cfg: Dict, to: str, message: str) -> Dict:
    """Twilio REST API."""
    sid = cfg.get("account_sid", "")
    token = cfg.get("auth_token", "")
    from_ = cfg.get("from_number", "")
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    auth = (sid, token)
    data = {"From": from_, "To": "+" + to if not to.startswith("+") else to, "Body": message}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, data=data, auth=auth)
        return {"success": r.status_code in (200, 201), "response": r.text[:500]}


async def _sms_vatansms(cfg: Dict, to: str, message: str) -> Dict:
    """VatanSMS JSON API."""
    url = "https://api.vatansms.net/api/v1/1toN"
    body = {
        "api_id": cfg.get("api_id", ""),
        "api_key": cfg.get("api_key", ""),
        "sender": cfg.get("header", ""),
        "message_type": "normal",
        "message": message,
        "phones": [to],
    }
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(url, json=body)
        ok = r.status_code == 200 and "status" in r.text.lower()
        return {"success": ok, "response": r.text[:500]}


async def _sms_generic(cfg: Dict, to: str, message: str) -> Dict:
    """Henüz bağlanmamış sağlayıcılar için placeholder (Verimor, MutluCep, Mobildev, PostaGüvercini).
    Y19: Önceden success=True dönüyordu → SMS hiç gitmediği halde notification_logs 'başarılı'
    kaydediyordu (sessiz kesinti). Artık success=False döner ki gerçek durum görünür olsun."""
    logger.warning(f"[SMS] Sağlayıcı henüz uygulanmadı — SMS GÖNDERİLMEDİ, to=***{str(to)[-4:]}")  # A3: telefon+OTP loglanmaz
    return {"success": False, "response": "provider-not-implemented", "mock": True,
            "error": "SMS sağlayıcısı entegre değil"}


SMS_IMPL = {
    "netgsm": _sms_netgsm,
    "iletimerkezi": _sms_iletimerkezi,
    "twilio": _sms_twilio,
    "vatansms": _sms_vatansms,
}


# ── SMS KARA LİSTESİ (db.sms_suppressions) ────────────────────────────────────
# Yanlış kayıtlı numaralara (başkasına giden mesaj şikâyeti) HİÇBİR yoldan SMS gitmesin:
# tüm sağlayıcı fonksiyonları tek kapıdan geçer (bildirim, OTP, influencer, kampanya).
_SMS_BLOCK = {"set": set(), "at": 0.0}


async def sms_suppressed(to: str) -> bool:
    import time as _t
    try:
        if _t.time() - _SMS_BLOCK["at"] > 120:
            from routes.deps import db as _db
            found = set()
            async for r in _db.sms_suppressions.find({}, {"_id": 0, "phone": 1}):
                n = normalize_phone_tr(r.get("phone") or "")
                if n:
                    found.add(n)
            _SMS_BLOCK["set"], _SMS_BLOCK["at"] = found, _t.time()
    except Exception:
        pass
    n = normalize_phone_tr(to or "")
    return bool(n) and (n in _SMS_BLOCK["set"] or n[-10:] in {x[-10:] for x in _SMS_BLOCK["set"]})


def _sms_guard(fn):
    async def _wrapped(cfg, to, message, *a, **k):
        if await sms_suppressed(to):
            logger.warning("[sms] kara listedeki numaraya gönderim engellendi")
            return {"success": False, "response": "suppressed", "suppressed": True}
        return await fn(cfg, to, message, *a, **k)
    _wrapped.__name__ = getattr(fn, "__name__", "sms")
    return _wrapped


for _k in list(SMS_IMPL):
    SMS_IMPL[_k] = _sms_guard(SMS_IMPL[_k])
_sms_generic = _sms_guard(_sms_generic)


# =============================================================================
# EMAIL (RESEND)
# =============================================================================

async def _email_send(db, to: str, subject: str, html: str,
                      from_email: Optional[str] = None,
                      from_name: Optional[str] = None,
                      reply_to: Optional[str] = None) -> Dict:
    """Kurumsal SMTP (Zoho) üzerinden tek alıcıya mail.
    from_email verilirse gönderen adresi geçersiz kılınır (ör. sipariş mailleri
    siparis@... adresinden). Boşsa varsayılan yapılandırılmış gönderen kullanılır."""
    from email_smtp import send_smtp_email
    return await send_smtp_email(db, to, subject, html,
                                 from_email=from_email, from_name=from_name,
                                 reply_to=reply_to)


async def _order_sender(db, event: str) -> Dict:
    """Sipariş yaşam-döngüsü maillerinin (order_*) gönderen kimliğini çözer.
    Panelden (Ayarlar → E-posta) ayarlanan `order_from_email` doluysa sipariş
    mailleri o adresten gider (ör. siparis@example.com); pazarlama/işlemsel
    itibar ayrımı korunur. Boşsa varsayılan gönderen kullanılır (davranış değişmez).
    Yalnız `order_` ile başlayan MÜŞTERİ olayları için; admin/şifre/pazarlama hariç."""
    if not str(event or "").startswith("order_"):
        return {}
    try:
        s = await db.settings.find_one(
            {"id": "email_smtp"},
            {"_id": 0, "order_from_email": 1, "order_from_name": 1, "order_reply_to": 1}) or {}
    except Exception:
        return {}
    oe = str(s.get("order_from_email") or "").strip()
    if not oe:
        return {}
    return {
        "from_email": oe,
        "from_name": (str(s.get("order_from_name") or "").strip() or None),
        "reply_to": (str(s.get("order_reply_to") or "").strip() or None),
    }


# =============================================================================
# ORCHESTRATION
# =============================================================================

# DENETİM (kimlik B-1): providers.* sırları (Netgsm password, sağlayıcı
# page_access_token & app_secret, Telegram auth_token …) DB'de AÇIK yazılıyordu.
# Kaydederken Fernet ile şifrelenir (notifications.save_providers), okuyan HER yer
# aşağıdaki yardımcılarla çözer. decrypt legacy düz-metni olduğu gibi döndürür →
# migration güvenli (eski değerler yeni kayda kadar bozulmaz).
PROVIDER_SECRET_FIELDS = {"password", "auth_token", "api_hash", "api_key",
                          "access_token", "api_secret", "app_secret", "page_access_token"}


def decrypt_provider_block(block: Optional[Dict]) -> Dict:
    """Tek bir provider bloğundaki (ör. providers.netgsm) sır alanlarını çözer."""
    if not block or not isinstance(block, dict):
        return block or {}
    try:
        from security.crypto import decrypt as _dec
    except Exception:
        return dict(block)
    out = dict(block)
    for f in PROVIDER_SECRET_FIELDS:
        if out.get(f):
            try:
                out[f] = _dec(out[f])
            except Exception:
                pass
    return out


def decrypt_providers_doc(doc: Optional[Dict]) -> Dict:
    """Tüm providers alt-bloklarındaki sırları çözer (full notification_providers doc)."""
    if not doc or not isinstance(doc, dict):
        return doc or {}
    out = dict(doc)
    provs = out.get("providers") or {}
    out["providers"] = {k: decrypt_provider_block(v) for k, v in provs.items()}
    return out


async def _get_providers_config(db) -> Dict:
    doc = await db.settings.find_one({"id": "notification_providers"}, {"_id": 0})
    if not doc:
        return {"sms_active": None, "email_active": True,
                "providers": {}}
    return decrypt_providers_doc(doc)


async def _get_template(db, event_key: str, channel: str) -> Optional[Dict]:
    return await db.notification_templates.find_one(
        {"event": event_key, "channel": channel}, {"_id": 0}
    )


# DENETİM (bildirim Y2): OTP/şifre-sıfırlama kodları ve tam telefon numarası
# notification_logs'a AÇIK yazılıyordu (admin log ekranından okunabilir). Loglamadan
# önce hassas değişkenleri redakte et, alıcıyı maskele.
_SENSITIVE_VAR_KEYS = {"otp", "otp_code", "code", "mfa_code", "sms_code", "reset_code",
                       "verification_code", "password", "token", "otp_kodu", "kod"}


def _redact_log_vars(variables: Optional[Dict]) -> Dict:
    if not variables:
        return {}
    out = {}
    for k, v in variables.items():
        if str(k).strip().lower() in _SENSITIVE_VAR_KEYS:
            out[k] = "***"
        else:
            out[k] = v
    return out


def _mask_to(to: str) -> str:
    s = str(to or "")
    if "@" in s:  # e-posta: ilk 2 karakter + alan
        name, _, dom = s.partition("@")
        return (name[:2] + "***@" + dom) if dom else "***"
    if len(s) >= 4:  # telefon: yalnız son 4 hane
        return "***" + s[-4:]
    return "***"


async def _log_event(db, *, event: str, channel: str, to: str, status: str,
                     response: str = "", variables: Optional[Dict] = None):
    try:
        await db.notification_logs.insert_one({
            "event": event,
            "channel": channel,
            "to": _mask_to(to),
            "status": status,
            "response": response[:1000] if response else "",
            "variables": _redact_log_vars(variables),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"notification log insert failed: {e}")


async def send_notification(
    db,
    event: str,
    *,
    to_phone: Optional[str] = None,
    to_email: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    channels: Optional[List[str]] = None,
) -> Dict:
    """
    Tek çağrı → uygun kanallara event'i tetikler.
    channels verilmezse tüm aktif kanallar kullanılır.
    Template'ler DB'den çekilir. Bulunamazsa default kısa metin.
    """
    variables = dict(variables or {})
    results: Dict[str, Dict] = {}
    # BEYAZ ETİKET: şablonlardaki {store_name}/{site_url}/{store_email}/{store_phone} firma
    # bilgisinden (company.get_company) doldurulur — çağıran açıkça verdiyse o korunur.
    try:
        from company import get_company as _get_company
        _co = await _get_company(db)
        variables.setdefault("store_name", _co.get("store_name") or "")
        variables.setdefault("site_url", _co.get("site_url") or "")
        variables.setdefault("store_email", _co.get("contact_email") or "")
        variables.setdefault("store_phone", _co.get("contact_phone") or "")
    except Exception:
        pass

    cfg = await _get_providers_config(db)
    providers = cfg.get("providers", {})

    active_channels = channels or CHANNELS

    # GÜVENLİK-KRİTİK event'ler (OTP / MFA / şifre sıfırlama kodu) admin'in bildirim
    # AÇ/KAPA toggle'ından BAĞIMSIZ her zaman gönderilir. Aksi halde şablon yanlışlıkla
    # pasif bırakılınca giriş doğrulama kodu / şifre sıfırlama kodu HİÇ gitmiyordu
    # ("doğrulama kodu gitmiyor" kök nedeni). Şablon metni yine düzenlenebilir.
    _CRITICAL_EVENTS = {"password_reset_otp", "login_verification_code"}
    # DENETİM (bildirim Y1): kritik event'te ŞABLON SATIRI HİÇ YOKSA (tpl is None) eski
    # _tpl_on False dönüyordu → şifre sıfırlama/doğrulama kodu SMS'i HİÇ gitmiyordu (yeni/
    # beyaz-etiket kurulumda seed tıklanmadıysa müşteri hesabına giremiyordu). Kritik
    # event'lerde şablon yoksa aşağıdaki varsayılan gövdeyle yine de gönderilir.
    _CRITICAL_DEFAULT_SMS = {
        "password_reset_otp": "{store_name} dogrulama kodunuz: {otp_code} (5 dk gecerli).",
        "login_verification_code": "{store_name} giris dogrulama kodunuz: {otp_code} (5 dk gecerli).",
    }
    def _tpl_on(_tpl) -> bool:
        # Şablon VARSA (e-posta için de güvenli): aktif olmalı VEYA kritik event.
        return bool(_tpl) and (_tpl.get("enabled", True) or event in _CRITICAL_EVENTS)

    def _sms_on(_tpl) -> bool:
        # SMS'e özel: kritik event'te şablon HİÇ yoksa da (varsayılan gövdeyle) gönder.
        if _tpl:
            return _tpl.get("enabled", True) or event in _CRITICAL_EVENTS
        return event in _CRITICAL_EVENTS and bool(_CRITICAL_DEFAULT_SMS.get(event))

    # --- SMS ---
    if "sms" in active_channels and to_phone:
        to = normalize_phone_tr(to_phone)
        tpl = await _get_template(db, event, "sms")
        if _sms_on(tpl):
            _body = (tpl or {}).get("body", "") or _CRITICAL_DEFAULT_SMS.get(event, "")
            msg = render_template(_body, variables) or f"[{event}]"
            sms_active = cfg.get("sms_active")
            impl = SMS_IMPL.get(sms_active, _sms_generic)
            prov_cfg = providers.get(sms_active, {}) if sms_active else {}
            try:
                res = await impl(prov_cfg, to, msg)
                results["sms"] = res
                await _log_event(db, event=event, channel="sms", to=to,
                                 status="success" if res.get("success") else "failed",
                                 response=str(res.get("response", "")), variables=variables)
            except Exception as e:
                results["sms"] = {"success": False, "response": str(e)}
                await _log_event(db, event=event, channel="sms", to=to, status="error",
                                 response=str(e), variables=variables)
        else:
            # H1 fix: durum ayarı "SMS gönder" dedi ama bu event için ŞABLON YOK / PASİF →
            # eskiden iz bırakmadan atlanıyordu (admin gitti sanıyordu). Artık "skipped" loglanır.
            results["sms"] = {"success": False, "response": "sms-template-missing-or-disabled"}
            await _log_event(db, event=event, channel="sms", to=to, status="skipped",
                             response="şablon yok veya pasif (event=%s)" % event, variables=variables)

    # --- Email ---
    if "email" in active_channels and to_email and cfg.get("email_active", True):
        tpl = await _get_template(db, event, "email")
        if _tpl_on(tpl):
            # subject düz metin; body HTML → değişken değerleri kaçırılır (SEC-4 F7)
            _subj_tpl = tpl.get("subject", "")
            _body_tpl = tpl.get("body", "")
            # EMNİYET AĞI (17.09): doğrulama kodu e-postası şablonunda {otp_code} yoksa e-posta
            # KODSUZ gidiyordu (müşteri/personel giriş yapamıyordu). Kritik event'te kod gövdede
            # geçmiyorsa sona net bir kod bloğu eklenir — şablon bozuk olsa da kod MUTLAKA gider.
            if (event in _CRITICAL_EVENTS and (variables or {}).get("otp_code")
                    and "{otp_code}" not in str(_body_tpl)):
                _body_tpl = str(_body_tpl) + (
                    '<div style="margin:20px auto;text-align:center;font-family:Arial,sans-serif">'
                    '<div style="font-size:12px;color:#777">Doğrulama kodunuz</div>'
                    '<div style="font-size:32px;font-weight:700;letter-spacing:8px;color:#111">{otp_code}</div>'
                    '<div style="font-size:12px;color:#777">Kod 5 dakika geçerlidir.</div></div>')
            subj = render_template(_subj_tpl, variables) or f"Bildirim: {event}"
            html = render_template(_body_tpl, variables, escape_values=True) or f"<p>{event}</p>"
            try:
                _snd = await _order_sender(db, event)
                res = await _email_send(db, to_email, subj, html, **_snd)
                results["email"] = res
                await _log_event(db, event=event, channel="email", to=to_email,
                                 status="success" if res.get("success") else "failed",
                                 response=str(res.get("response", "")), variables=variables)
            except Exception as e:
                results["email"] = {"success": False, "response": str(e)}
                await _log_event(db, event=event, channel="email", to=to_email, status="error",
                                 response=str(e), variables=variables)

    return {"event": event, "results": results}


# =============================================================================
# TEST HELPERS
# =============================================================================

async def test_provider(db, channel: str, provider_key: Optional[str], to: str, message: str) -> Dict:
    cfg = await _get_providers_config(db)
    providers = cfg.get("providers", {})
    prov_cfg = providers.get(provider_key or "", {}) if provider_key else {}
    if channel == "sms":
        impl = SMS_IMPL.get(provider_key or "", _sms_generic)
        return await impl(prov_cfg, normalize_phone_tr(to), message)
    if channel == "email":
        return await _email_send(db, to, "Test Bildirim", f"<p>{message}</p>")
    return {"success": False, "response": "unknown_channel"}


# =============================================================================
# ADMIN "YENİ SİPARİŞ" MAİLİ — ORTAK ÜRETEÇ
# -----------------------------------------------------------------------------
# Aynı HTML iki ayrı yerde kopyalanmıştı (orders._send_admin_new_order_email ve
# payment._notify_paid_order_confirmed); biri değişince diğeri geride kalıyordu.
# Tek yerden üretilir ki bundan sonraki TÜM sipariş mailleri aynı ve ORTALI gelsin.
#
# Markalı kabuk (email_layout.email_shell) zaten 600px ortalı bir kart; ancak içerik
# hücresinde text-align yok, bu yüzden içerik solda kalıyordu. Burada içerik kendi
# içinde ortalanır ve tablo da ortalı bir blok olarak yerleşir.
# =============================================================================
def build_admin_order_email_html(order: Dict, ship: Dict, heading: str = "Yeni Sipariş",
                                 kind_label: str = "") -> str:
    """Admin yeni-sipariş maili için ORTALANMIŞ HTML gövdesi.

    Müşteri-kontrollü alanlar html.escape ile kaçırılır (DENETİM SEC-4 F7:
    ad/adres alanına <a href=evil> ile admin gelen kutusuna kimlik avı).
    """
    import html as _h

    order = order or {}
    ship = ship or {}

    try:
        _tl = float(order.get("total") or 0)
    except Exception:
        _tl = 0.0
    _tl_fmt = f"{_tl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    _who = _h.escape(f"{ship.get('first_name','')} {ship.get('last_name','')}".strip()
                     or ship.get("full_name") or "Müşteri")
    _phone = _h.escape(str(ship.get("phone") or order.get("phone") or "-"))
    # Ödeme yöntemi ham anahtar olarak ("credit_card") görünüyordu → Türkçe etiket.
    _PM_TR = {
        "credit_card": "Kredi Kartı", "card": "Kredi Kartı", "creditcard": "Kredi Kartı",
        "bank_transfer": "Havale / EFT", "havale": "Havale / EFT", "eft": "Havale / EFT",
        "cash_on_delivery": "Kapıda Ödeme", "cod": "Kapıda Ödeme", "kapida": "Kapıda Ödeme",
        "gift_card": "Hediye Çeki", "marketplace": "Diğer kanal",
    }
    _pm_raw = str(order.get("payment_method") or order.get("payment_type") or "").strip()
    _pm = _h.escape(_PM_TR.get(_pm_raw.lower(), _pm_raw) or "-")
    _no = _h.escape(str(order.get("order_number") or ""))
    _adr = _h.escape(str(ship.get("address") or ""))
    _loc = _h.escape(" / ".join([x for x in (ship.get("district") or ship.get("ilce") or "",
                                             ship.get("city") or ship.get("il") or "") if x]))
    # Kabuk zaten "Yeni Sipariş · W11203" başlığını basıyor; burada onu TEKRARLAMA.
    # Yalnız durum etiketi (Havale/EFT bekleniyor, Ödendi…) alt satır olarak gösterilir.
    _title = _h.escape(kind_label) if kind_label else ""

    # KOMPAKT DÜZEN: her alan eskiden TAM GENİŞLİK + iki satır (üstte etiket, altta
    # değer) olarak basılıyordu; 5 alan + ürünler mailin dikeyde gereksiz uzamasına yol
    # açıyordu ("aşağıya doğru çok uzatmış"). Artık etiket solda, değer sağda tek satır:
    # aynı bilgi yarı yükseklikte. Sipariş numarası konu satırında ve mail başlığında
    # ZATEN var, gövdede tekrar edilmiyor.
    _lbl = ("color:#8a8a8a;font-size:11px;letter-spacing:.06em;text-transform:uppercase;"
            "white-space:nowrap;vertical-align:top;")
    _val = "font-size:14px;color:#111;line-height:1.4;vertical-align:top;text-align:right;"
    _sep = "border-bottom:1px solid #f0f0f0;"

    def _line(label: str, value: str, strong: bool = False) -> str:
        if not value:
            return ""
        _w = "font-weight:700;font-size:16px;" if strong else ""
        return (f'<tr>'
                f'<td style="padding:7px 12px 7px 0;{_lbl}{_sep}width:32%;">{label}</td>'
                f'<td style="padding:7px 0;{_val}{_sep}{_w}">{value}</td>'
                f'</tr>')

    # Ürünler: ad solda, adet sağda — iki sütun artık hizalı (düzen sola dayalı).
    _rows = ""
    for _it in (order.get("items") or []):
        _nm = _h.escape(str(_it.get("name") or _it.get("product_name") or "Ürün"))
        _qty = _h.escape(str(_it.get("quantity") or _it.get("qty") or 1))
        _var = _h.escape(" · ".join([x for x in (_it.get("color") or "", _it.get("size") or "") if x]))
        _vh = f'<span style="color:#999;"> ({_var})</span>' if _var else ""
        _rows += (f'<tr>'
                  f'<td style="padding:6px 12px 6px 0;font-size:13px;line-height:1.35;'
                  f'color:#111;{_sep}">{_nm}{_vh}</td>'
                  f'<td style="padding:6px 0;font-size:13px;color:#111;font-weight:600;'
                  f'text-align:right;white-space:nowrap;{_sep}">&times; {_qty}</td>'
                  f'</tr>')

    _items_block = ""
    if _rows:
        _items_block = (f'<tr><td colspan="2" style="padding:14px 0 4px;{_lbl}">Ürünler</td></tr>'
                        + _rows)

    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td align="center">'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" '
        f'style="width:100%;max-width:440px;margin:0 auto;border-collapse:collapse;">'
        + (f'<tr><td colspan="2" style="padding:0 0 12px;text-align:center;">'
           f'<div style="display:inline-block;padding:4px 12px;border:1px solid #ddd;'
           f'border-radius:999px;font-size:11px;letter-spacing:.06em;color:#444;'
           f'text-transform:uppercase;">{_title}</div></td></tr>' if _title else '')
        + _line("Müşteri", f"{_who}<br>{_phone}")
        + _line("Tutar", f"{_tl_fmt} TL", strong=True)
        + _line("Ödeme", _pm)
        + _line("Teslimat", f"{_adr}<br>{_loc}" if _loc else _adr)
        + _items_block
        + f'</table></td></tr></table>'
    )
