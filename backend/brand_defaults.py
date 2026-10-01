"""
Mağaza sabit öznitelik varsayılanları — TÜM pazaryerleri (Trendyol / Hepsiburada / Temu) için ORTAK.

Tasarım:
- Pazaryerine BAĞIMSIZ. Değerler İSİMLE tutulur (value_id değil); her pazaryeri push
  çekirdeği bu değeri kendi value_id'sine ADA GÖRE çözer (TR ↔ Türkiye gibi).
- Push'a GAP-FILL olarak eklenir: ürün/varyant/kategori o özelliği ZATEN taşıyorsa
  DOKUNULMAZ; yalnız boş kalan özelliğe varsayılan yazılır.
- TEK OTORİTE DB'dir (attributes.default_value — Özellik Ayar Kartı). Bu modüldeki
  statik harita bilinçli olarak BOŞTUR (beyaz etiket: firma-özel değer koda gömülmez);
  işletme varsayılanlarını admin panelinden girer.
- Üretici/İthalatçı (GPSR) değerleri koddan DEĞİL merkezî Firma Bilgileri'nden
  (company.get_company) gelir; `refresh_runtime_company(db)` ile önbelleğe alınır.
- Eşleşme yoksa mevcut akış AYNEN korunur, sessizce atlanır → hiçbir push'u bozmaz.
- Hiçbir pazaryeri modülüne import bağımlılığı YOKTUR (yalnız bu modül dışa verir).
"""

import re as _re

# Üretici / İthalatçı (GPSR / "Ürün Denetim Bilgileri") — çalışma anında Firma
# Bilgileri'nden doldurulur (refresh_runtime_company). Statik değer YOK.
_RUNTIME_COMPANY = {"company_name": "", "email": "", "address": ""}

# Düz sabitler (ada göre). Beyaz etiket: varsayılan olarak BOŞ — işletme kendi
# varsayılanlarını Özellik Ayar Kartı'ndan (attributes.default_value) tanımlar.
FIXED_ATTR_DEFAULTS: dict = {}


def _norm(s) -> str:
    """Türkçe-duyarsız normalize (eşleştirme için). İ/ı/ş/ğ/ü/ö/ç + birleşik nokta."""
    s = (s or "").casefold()
    for a, b in (("ı", "i"), ("İ", "i"), ("ş", "s"), ("ğ", "g"),
                 ("ü", "u"), ("ö", "o"), ("ç", "c"), ("̇", "")):
        s = s.replace(a, b)
    return " ".join(s.split())


_FIXED_NORM = {_norm(k): v for k, v in FIXED_ATTR_DEFAULTS.items()}


async def refresh_runtime_company(db) -> dict:
    """GPSR gap-fill için Firma Bilgileri'ni (company.get_company, 60 sn cache'li) yükler.
    Hata olursa mevcut önbellek korunur (push akışı bozulmaz)."""
    try:
        from company import get_company
        co = await get_company(db)
        _RUNTIME_COMPANY.update({
            "company_name": (co.get("company_name") or "").strip(),
            "email": (co.get("email") or co.get("contact_email") or "").strip(),
            "address": (co.get("address") or "").strip(),
        })
    except Exception:
        pass
    return dict(_RUNTIME_COMPANY)


def company_value_for_attr(attr_name, company: dict | None = None):
    """Üretici/İthalatçı (GPSR) bir özellik adını firma bilgisine eşler.
    'Üretici Adı', 'Birincil/İkincil/Üçüncül İthalatçı Adı' → firma adı;
    '...Mail...' → e-posta; '...Adres...' → adres. Değer yoksa None (akış bozulmaz).
    """
    field = company_field_for_attr(attr_name)
    if not field:
        return None
    src = company if company is not None else _RUNTIME_COMPANY
    return (src.get(field) or "").strip() or None


def company_field_for_attr(attr_name):
    """GPSR üretici/ithalatçı özellik adının hangi şirket alanına denk geldiğini döndürür:
    'company_name' | 'email' | 'address' | None.
    İSİM-EŞLEME TEK KAYNAK — hem push gap-fill (company_value_for_attr) hem kategori
    şirket-doldurma (category_mapping._resolve_company_value) bunu kullanır.
    """
    if not attr_name:
        return None
    nm = _norm(attr_name)  # İthalatçı → "ithalatci" (combining-dot temizlenir)
    if not _re.search(r"uretici|ithalatc|imalatc", nm):
        return None
    if "mail" in nm or "posta" in nm or "email" in nm:
        return "email"
    if "adres" in nm:
        return "address"
    if _re.search(r"\bad[i]\b|\bism", nm) or "unvan" in nm or "firma" in nm \
            or nm in ("uretici", "ithalatci"):
        return "company_name"
    return None  # tanımadığımız alt-alan (telefon/vergi no…) → dokunma


def fixed_value_for(attr_name):
    """Pazaryeri özellik ADINA sabit varsayılanı döndürür; eşleşmezse None.
    Push çekirdekleri yalnız BOŞ kalan özellik için çağırır (gap-fill)."""
    if not attr_name:
        return None
    cv = company_value_for_attr(attr_name)
    if cv:
        return cv
    return _FIXED_NORM.get(_norm(attr_name))
