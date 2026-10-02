"""
=============================================================================
provider_settings.py — Kargo Entegratör Ayarları
=============================================================================

AMAÇ:
  Yöneticinin kargo firmaları arasından istediğini seçip, sadece o entegratörün gerektirdiği
  bilgileri girip sisteme entegre edebilmesi için ayar altyapısı.

NASIL ÇALIŞIR?
  - Her provider için "schema" (alanlar + validasyon ipucu) tanımlıdır.
    Frontend bu şemayı alıp dinamik form render eder.
  - Kayıt: `providers_config` koleksiyonunda tek bir döküman tutulur:
      {
        "kind": "cargo",
        "active_provider": "mng",
        "providers": {
          "mng": {<credentials>},
          ...
        }
      }
  - Kargo etiketi basma rutinleri `active_provider`'ı
    okuyup o provider'ın config'i ile işlem yapar.

ENDPOINT'LER:
  - GET  /api/provider-settings/cargo/schemas     → Kargo firması şemaları
  (e-fatura artık BirFatura entegrasyonu üzerinden: routes/integrations_birfatura.py)
  - GET  /api/provider-settings/cargo/config
  - POST /api/provider-settings/cargo/config
  - POST /api/provider-settings/cargo/test

KULLANAN FRONTEND:
  - /app/frontend/src/pages/admin/EInvoiceSettings.jsx
  - /app/frontend/src/pages/admin/CargoSettings.jsx
=============================================================================
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from datetime import datetime, timezone

from .deps import db, require_admin, require_permission
try:
    from security.crypto import encrypt as _encrypt, decrypt as _decrypt, is_encrypted as _is_enc
except Exception:  # kripto yoksa güvenli-degrade (yine de çalışsın)
    def _encrypt(v): return v
    def _decrypt(v): return v
    def _is_enc(v): return False

router = APIRouter(prefix="/provider-settings", tags=["Provider Settings"])


# ---------------------------------------------------------------------------
# PROVIDER ŞEMALARI — alan tanımları, etiketler, zorunluluklar.
# Frontend bu şemayı alıp dinamik form oluşturur. Yeni bir provider eklemek
# için bu dict'e yeni kayıt eklemek yeterlidir; frontend'de ekstra kod YOK.
# ---------------------------------------------------------------------------

# Alan tipi: text | password | number | email | select
def _f(key, label, type="text", required=False, placeholder="", help=None, options=None):
    d = {"key": key, "label": label, "type": type, "required": required,
         "placeholder": placeholder}
    if help: d["help"] = help
    if options: d["options"] = options
    return d


CARGO_PROVIDERS = {
    "mng": {
        "name": "DHL E-Commerce",
        "website": "https://www.mngkargo.com.tr",
        "description": "DHL E-Commerce (eski MNG Kargo) API entegrasyonu.",
        "fields": [
            _f("customer_number", "Müşteri Numarası", required=True),
            _f("username", "Kullanıcı Adı", required=True),
            _f("password", "Şifre", type="password", required=True),
            _f("identity_type", "Kimlik Tipi", placeholder="1 (TCKN) / 2 (VKN)"),
            _f("identity_no", "Kimlik No"),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
        ],
    },
    # Aras / PTT: CANLI SOAP entegrasyonu (backend/aras_kargo_client.py, ptt_kargo_client.py,
    # cargo_carriers/). Alan anahtarları cargo_carriers/registry.py tarafından okunur.
    "aras": {
        "name": "Aras Kargo",
        "website": "https://esasweb.araskargo.com.tr",
        "description": "Aras Kargo SetOrder (gönderi kaydı) + GetQueryJSON (takip) — canlı entegrasyon.",
        "fields": [
            _f("username", "Sevkiyat Servisi Kullanıcı Adı", required=True,
               help="SetOrder (Sevkiyat Entegrasyonu) web servis kullanıcısı. Test ortamı: neodyum"),
            _f("password", "Sevkiyat Servisi Şifresi", type="password", required=True,
               help="Test ortamı şifresi: nd2580"),
            _f("customer_code", "Müşteri Kodu (CustomerCode)",
               help="Bilgi sorgulama (takip) servisi için zorunlu. esasweb > Entegrasyonlar > XML Servisleri'nde yazar."),
            _f("query_username", "Sorgulama Servisi Kullanıcı Adı",
               help="Boş bırakılırsa sevkiyat kullanıcısı kullanılır (genelde farklıdır)."),
            _f("query_password", "Sorgulama Servisi Şifresi", type="password"),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
            _f("payor_type", "Kargo Ücretini Kim Öder", type="select",
               options=[{"value": "1", "label": "Gönderici öder (1)"}, {"value": "2", "label": "Alıcı öder (2)"}],
               help="Kapıda ödemeli gönderide Aras kuralı gereği her zaman gönderici öder."),
            _f("cod_collection_type", "Kapıda Ödeme Tahsilat Tipi", type="select",
               options=[{"value": "0", "label": "Nakit (0)"}, {"value": "1", "label": "Kredi kartı (1)"}]),
            _f("sender_address_id", "Gönderici Adres ID (opsiyonel)",
               help="Aras'ta birden çok çıkış adresiniz varsa SenderAccountAddressId."),
            _f("default_desi", "Varsayılan Desi", type="number", placeholder="1",
               help="Üründe ölçü/desi yoksa kullanılır."),
            _f("default_kg", "Varsayılan Ağırlık (kg)", type="number", placeholder="1"),
        ],
    },
    "ptt": {
        "name": "PTT Kargo",
        "website": "https://www.ptt.gov.tr",
        "description": "PTT Veri Yükleme (kabulEkle2) + GonderiTakipV2 — canlı entegrasyon.",
        "fields": [
            _f("customer_number", "Müşteri Numarası (musteriId)", required=True,
               help="Anlaşma yapılan PTT Başmüdürlüğü tarafından verilen 9-10 haneli numara."),
            _f("password", "Web Servis Şifresi", type="password", required=True),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
            _f("barcode_range_start", "Barkod Aralığı Başlangıç (12 hane)", required=True,
               placeholder="275036560000", help="PTT'nin size tahsis ettiği aralık; 13. hane (check digit) otomatik hesaplanır."),
            _f("barcode_range_end", "Barkod Aralığı Bitiş (12 hane)", required=True, placeholder="275036569999"),
            _f("odeme_sekli", "Ödeme Şekli", type="select",
               options=[{"value": "MH", "label": "Mahsup (MH)"}, {"value": "N", "label": "Nakit (N)"},
                        {"value": "UA", "label": "Ücreti alıcıdan (UA)"}]),
            _f("ek_hizmet", "Ek Hizmet Kodları", placeholder="SB",
               help="Sözleşmenizdeki ek hizmetler (ör. SB = SMS ile bilgilendirme). Birleşik yazılır: SBAH"),
            _f("cod_service_code", "Kapıda Ödeme Ek Hizmet Kodu", placeholder="OS",
               help="Ödeme şartlı gönderi kodu (dokümana göre OS). Kapıda ödemeli siparişlerde otomatik eklenir."),
            _f("posta_ceki_no", "Posta Çeki No (rezerve1, opsiyonel)", placeholder="8 hane"),
            _f("send_sender_info", "Gönderici Bilgisini Gönder", type="select",
               options=[{"value": "", "label": "Hayır (PTT'de kayıtlı bilgi)"}, {"value": "true", "label": "Evet (Mağaza bilgileri)"}]),
            _f("default_desi", "Varsayılan Desi", type="number", placeholder="1"),
            _f("default_kg", "Varsayılan Ağırlık (kg)", type="number", placeholder="1"),
        ],
    },
    "sendeo": {
        "name": "Sendeo",
        "website": "https://sendeo.com.tr",
        "description": "Sendeo Kargo entegrasyonu.",
        "fields": [
            _f("customer_code", "Müşteri Kodu", required=True),
            _f("username", "Kullanıcı Adı", required=True),
            _f("password", "Şifre", type="password", required=True),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
        ],
    },
    "kolay-gelsin": {
        "name": "Kolay Gelsin",
        "website": "https://www.kolaygelsin.com",
        "description": "Kolay Gelsin Kargo.",
        "fields": [
            _f("customer_code", "Müşteri Kodu", required=True),
            _f("api_key", "API Key", type="password", required=True),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
        ],
    },
    "dhl": {
        "name": "DHL Express",
        "website": "https://www.dhl.com",
        "description": "DHL Express uluslararası kargo API entegrasyonu.",
        "fields": [
            _f("account_number", "Hesap Numarası", required=True),
            _f("username", "Kullanıcı Adı", required=True),
            _f("password", "Şifre", type="password", required=True),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
        ],
    },
    "ups": {
        "name": "UPS",
        "website": "https://www.ups.com",
        "description": "UPS kargo entegrasyonu.",
        "fields": [
            _f("account_number", "Hesap Numarası", required=True),
            _f("access_key", "Access Key", type="password", required=True),
            _f("username", "Kullanıcı Adı", required=True),
            _f("password", "Şifre", type="password", required=True),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
        ],
    },
    "fedex": {
        "name": "FedEx",
        "website": "https://www.fedex.com",
        "description": "FedEx kargo API entegrasyonu.",
        "fields": [
            _f("account_number", "Hesap Numarası", required=True),
            _f("api_key", "API Key", type="password", required=True),
            _f("api_secret", "API Secret", type="password", required=True),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
        ],
    },
    "tnt": {
        "name": "TNT",
        "website": "https://www.tnt.com",
        "description": "TNT uluslararası kargo.",
        "fields": [
            _f("account_number", "Hesap Numarası", required=True),
            _f("username", "Kullanıcı Adı", required=True),
            _f("password", "Şifre", type="password", required=True),
            _f("env", "Ortam", type="select", required=True,
               options=[{"value": "test", "label": "Test"}, {"value": "prod", "label": "Canlı"}]),
        ],
    },
}


PROVIDERS_BY_KIND = {
    "cargo": CARGO_PROVIDERS,
}


# ---------------------------------------------------------------------------
# Endpoint yardımcıları
# ---------------------------------------------------------------------------
def _kind_guard(kind: str):
    if kind not in PROVIDERS_BY_KIND:
        raise HTTPException(status_code=404, detail="Bilinmeyen ayar grubu")


async def _get_config_doc(kind: str) -> dict:
    _kind_guard(kind)
    doc = await db.providers_config.find_one({"kind": kind}, {"_id": 0})
    if not doc:
        doc = {"kind": kind, "active_provider": None, "providers": {}}
    return doc


# Y14: Gizli alanlar (şifre/api anahtarı) frontend'e DÜZ METİN dönmemeli.
_SECRET_MASK = "********"


def _secret_fields_for(kind: str, provider_key: str) -> set:
    """Bir provider'ın şemasında type=password olan (gizli) alan anahtarları + yaygın sır adları."""
    keys = set()
    try:
        for f in (PROVIDERS_BY_KIND.get(kind, {}).get(provider_key, {}).get("fields") or []):
            if f.get("type") == "password":
                keys.add(f.get("key"))
    except Exception:
        pass
    # Şemada password işaretlenmemiş olsa bile bilinen sır alanlarını maskele.
    for k in ("password", "api_secret", "api_key", "secret", "token", "apiKey", "apiSecret"):
        keys.add(k)
    return keys


def decrypt_provider_doc(kind: str, doc: dict) -> dict:
    """A1.1: Tüketiciler için — providers.<key>.<secret> alanlarını ÇÖZ (decrypt).
    Eski düz-metin değerler crypto.decrypt tarafından olduğu gibi geçirilir (kesintisiz
    migrasyon). Bu fonksiyonu SIRRI KULLANAN yerler çağırmalı (admin GET DEĞİL — o maskeli)."""
    if not doc:
        return doc
    out = dict(doc)
    providers = {}
    for pkey, pval in (out.get("providers") or {}).items():
        secrets_keys = _secret_fields_for(kind, pkey)
        dec = {}
        for fk, fv in (pval or {}).items():
            dec[fk] = _decrypt(fv) if (fk in secrets_keys and isinstance(fv, str)) else fv
        providers[pkey] = dec
    out["providers"] = providers
    return out


def _mask_config_doc(kind: str, doc: dict) -> dict:
    """providers.<key>.<secret_field> değerlerini maskele (varlığını koru, değeri gizle)."""
    out = dict(doc or {})
    providers = {}
    for pkey, pval in (out.get("providers") or {}).items():
        secrets_keys = _secret_fields_for(kind, pkey)
        masked = {}
        for fk, fv in (pval or {}).items():
            if fk in secrets_keys and fv not in (None, "", False):
                masked[fk] = _SECRET_MASK
            else:
                masked[fk] = fv
        providers[pkey] = masked
    out["providers"] = providers
    return out


# ---------------------------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------------------------
@router.get("/{kind}/schemas")
async def get_schemas(kind: str, current_user: dict = Depends(require_admin)):
    """
    Belirtilen tür için (cargo) tüm provider şemalarını döner.
    Frontend bu şemayı alıp dinamik form render eder.
    """
    _kind_guard(kind)
    return {
        "kind": kind,
        "providers": [
            {"key": k, **{kk: vv for kk, vv in v.items()}}
            for k, v in PROVIDERS_BY_KIND[kind].items()
        ],
    }


# ---------------------------------------------------------------------------
# CONFIG (read / write)
# ---------------------------------------------------------------------------
@router.get("/{kind}/config")
async def get_config(kind: str, current_user: dict = Depends(require_admin)):
    """Kayıtlı active_provider + per-provider credential map döner.
    Y14: Gizli alanlar (şifre/api anahtarı) maskelenir ('********'); düz metin sızmaz."""
    doc = await _get_config_doc(kind)
    return _mask_config_doc(kind, doc)


@router.post("/{kind}/config")
async def save_config(kind: str, payload: dict,
                      current_user: dict = Depends(require_permission("integrations.view"))):
    """
    Tüm config'i (active_provider + providers map) günceller. Provider
    credential'ları `providers.<key>.<field>` şeklinde saklanır.
    """
    _kind_guard(kind)
    active = payload.get("active_provider")
    providers = payload.get("providers") or {}
    valid_keys = set(PROVIDERS_BY_KIND[kind].keys())
    if active and active not in valid_keys:
        raise HTTPException(status_code=400, detail=f"Geçersiz provider: {active}")

    # Yalnızca tanınan provider'ların verisini saklıyoruz (diğerlerini at)
    providers = {k: v for k, v in providers.items() if k in valid_keys}

    # Y14: Frontend gizli alanları maskeli ('********') geri gönderir. Maskeli değer GELİRSE
    # (kullanıcı değiştirmediyse) mevcut kayıtlı sırrı KORU — maske ile ezme.
    _existing = await _get_config_doc(kind)
    _existing_providers = _existing.get("providers") or {}
    for pkey, pval in providers.items():
        secrets_keys = _secret_fields_for(kind, pkey)
        cur = _existing_providers.get(pkey) or {}
        for fk in list((pval or {}).keys()):
            if fk in secrets_keys and pval.get(fk) == _SECRET_MASK:
                if cur.get(fk) not in (None, ""):
                    pval[fk] = cur.get(fk)
                else:
                    pval.pop(fk, None)

    # A1.1: Gizli alanları AT-REST ŞİFRELE (düz metin disk/DB'ye yazılmasın).
    # Maske-koruma yukarıda mevcut (zaten şifreli) değeri geri yazmış olabilir;
    # yalnız henüz şifrelenmemiş gerçek değerleri şifrele (is_encrypted ile idempotent).
    for pkey, pval in providers.items():
        secrets_keys = _secret_fields_for(kind, pkey)
        for fk in list((pval or {}).keys()):
            if fk in secrets_keys:
                v = pval.get(fk)
                if isinstance(v, str) and v not in ("", _SECRET_MASK) and not _is_enc(v):
                    pval[fk] = _encrypt(v)

    update_doc = {
        "kind": kind,
        "active_provider": active,
        "providers": providers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user.get("email") or current_user.get("id"),
    }
    await db.providers_config.update_one(
        {"kind": kind}, {"$set": update_doc}, upsert=True
    )
    return {"success": True, "message": "Ayarlar kaydedildi",
            "active_provider": active,
            "configured_providers": list(providers.keys())}


# ---------------------------------------------------------------------------
# CONNECTION TEST (mock)
# ---------------------------------------------------------------------------
@router.post("/{kind}/test")
async def test_connection(kind: str, payload: dict,
                          current_user: dict = Depends(require_admin)):
    """
    Seçili provider için bağlantı testi. Şu an mock — gerçek SDK'lar
    canlı API key'leri geldiğinde devreye alınacak. Zorunlu alanların
    dolu olduğunu doğrular.
    """
    _kind_guard(kind)
    provider_key = payload.get("provider")
    config = payload.get("config") or {}
    providers = PROVIDERS_BY_KIND[kind]
    if provider_key not in providers:
        raise HTTPException(status_code=404, detail="Provider bulunamadı")

    schema = providers[provider_key]
    missing = []
    for field in schema["fields"]:
        if field.get("required") and not str(config.get(field["key"], "")).strip():
            missing.append(field["label"])
    if missing:
        return {"success": False, "message": "Eksik alan(lar): " + ", ".join(missing),
                "missing": missing}

    # Canlı entegrasyonu olan kargo firmaları (MNG/DHL, Aras, PTT): gerçek SOAP bağlantı testi.
    if kind == "cargo" and provider_key in ("mng", "aras", "ptt"):
        from routes.cargo_carriers import test_carrier as _cc_test
        return await _cc_test(provider_key, {"config": config}, current_user)

    # MOCK: başarılı gibi davran. Canlıda burada gerçek login/HTTP request
    # yapılacak. Kullanıcının canlıya geçişte yalnızca bu fonksiyonu
    # güncellemesi yeterlidir.
    return {
        "success": True,
        "provider": provider_key,
        "provider_name": schema["name"],
        "message": f"{schema['name']} yapılandırması doğrulandı. (Bağlantı testi canlıya geçişte aktif olacak.)",
        "mock": True,
    }
