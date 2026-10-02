"""Kaynak sayfadaki Türkçe teknik özellik satırlarını (etiket → değer) ekipman şablonunun
kanonik `specs` alanlarına eşler (product_specs.py / data/spec_templates.json).

* Etiket eşlemesi: alan etiketleri (spec_templates "label") + bilinen eş anlamlılar
  (product_specs.SPEC_ALIASES anahtarları dahil) Türkçe-normalize edilerek karşılaştırılır.
* Sayısal alanlarda birim dönüşümü: ton→kg, cm/m→mm, g→kg, yıl→ay, W→kW, HP/BG ayrımı.
* Şablona uymayan (ör. seçenek listesinde olmayan) değerler ve bilinmeyen etiketler
  "Ek Teknik Özellikler" (extra_specs) satırı olarak korunur.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

_TR = str.maketrans({"ı": "i", "İ": "i", "I": "i", "ş": "s", "Ş": "s", "ç": "c", "Ç": "c",
                     "ğ": "g", "Ğ": "g", "ö": "o", "Ö": "o", "ü": "u", "Ü": "u", "â": "a", "î": "i", "û": "u"})


def tr_norm(s: Any) -> str:
    """Türkçe-güvenli küçük harf ASCII + tek boşluk (noktalama boşluğa)."""
    t = str(s or "").translate(_TR).lower()
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# normalize edilmiş etiket → kanonik alan anahtarı
SYNONYMS: Dict[str, str] = {
    "kapasite": "lifting_capacity_kg", "kaldirma kapasitesi": "lifting_capacity_kg",
    "tasima kapasitesi": "lifting_capacity_kg", "kaldirma gucu": "lifting_capacity_kg",
    "yuk kapasitesi": "lifting_capacity_kg", "maks kapasite": "lifting_capacity_kg",
    "maksimum kapasite": "lifting_capacity_kg", "max kapasite": "lifting_capacity_kg",
    "kaldirma yuksekligi": "lift_height_mm", "maks kaldirma yuksekligi": "lift_height_mm",
    "maksimum kaldirma yuksekligi": "lift_height_mm", "max kaldirma yuksekligi": "lift_height_mm",
    "maks yukseklik": "lift_height_mm", "maksimum yukseklik": "lift_height_mm",
    "min yukseklik": "min_height_mm", "minimum yukseklik": "min_height_mm",
    "en dusuk yukseklik": "min_height_mm", "min kaldirma yuksekligi": "min_height_mm",
    "kaldirma suresi": "lift_time_s", "kaldirma indirme suresi": "lift_time_s",
    "calisma basinci": "working_pressure_bar", "maks basinc": "working_pressure_bar",
    "maksimum basinc": "working_pressure_bar", "max basinc": "working_pressure_bar",
    "basinc": "working_pressure_bar", "calisma basinci bar": "working_pressure_bar",
    "tank hacmi": "tank_volume_l", "depo hacmi": "tank_volume_l", "hava tanki": "tank_volume_l",
    "tank kapasitesi": "tank_volume_l", "hava debisi": "air_flow_lpm", "hava cikisi": "air_flow_lpm",
    "emis kapasitesi": "air_flow_lpm", "debi": "air_flow_lpm", "hava verimi": "air_flow_lpm",
    "hava tuketimi": "air_consumption_lpm", "jant capi": "rim_diameter_in",
    "jant araligi": "rim_diameter_in", "jant olcusu": "rim_diameter_in", "jant capi araligi": "rim_diameter_in",
    "devir": "rpm", "rpm": "rpm", "bos devir": "rpm", "devir sayisi": "rpm",
    "tork": "torque_nm", "maks tork": "torque_nm", "maksimum tork": "torque_nm",
    "max tork": "torque_nm", "sokme torku": "torque_nm",
    "gurultu": "noise_db", "ses seviyesi": "noise_db", "gurultu seviyesi": "noise_db",
    "guc kaynagi": "power_source", "enerji kaynagi": "power_source", "calisma tipi": "power_source",
    "voltaj": "voltage", "gerilim": "voltage", "calisma voltaji": "voltage", "besleme gerilimi": "voltage",
    "besleme": "voltage", "elektrik": "voltage", "faz": "phase", "frekans": "frequency_hz",
    "motor gucu": "motor_power", "guc": "motor_power", "motor": "motor_power", "nominal guc": "motor_power",
    "aku voltaji": "battery_voltage_v", "aku gerilimi": "battery_voltage_v",
    "aku kapasitesi": "battery_capacity_ah", "lokma girisi": "drive_size", "lokma olcusu": "drive_size",
    "surucu": "drive_size", "kare giris": "drive_size", "giris": "drive_size", "baglanti olcusu": "drive_size",
    "parca sayisi": "piece_count", "parca adedi": "piece_count", "toplam parca": "piece_count",
    "cekmece sayisi": "drawer_count", "cekmece adedi": "drawer_count",
    "malzeme": "material", "malzeme cinsi": "material", "malzemesi": "material",
    "olcum araligi": "measurement_range", "ekran": "display_type", "ekran tipi": "display_type",
    "baglanti": "connectivity", "baglanti tipi": "connectivity",
    "net agirlik": "net_weight_kg", "agirlik": "net_weight_kg", "urun agirligi": "net_weight_kg",
    "garanti": "warranty_months", "garanti suresi": "warranty_months",
    "mensei": "origin_country", "mense": "origin_country", "uretim yeri": "origin_country",
    "uretici ulke": "origin_country", "model": "model", "model no": "model", "model kodu": "model",
    "seri": "model", "mpn": "mpn", "uretici parca no": "mpn",
    "kutu icerigi": "box_contents", "paket icerigi": "box_contents",
    "kullanim alani": "usage_area", "sertifika": "certifications", "sertifikalar": "certifications",
    "belgeler": "certifications",
}
# alan dışı ama ürüne yazılan etiketler
META_LABELS = {"marka": "brand", "stok kodu": "sku", "urun kodu": "sku", "barkod": "gtin", "gtin": "gtin",
               "ean": "gtin"}

_NUM_RE = re.compile(r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?)")


def _first_num(s: str) -> Optional[float]:
    m = _NUM_RE.search(str(s or ""))
    if not m:
        return None
    raw = m.group(1).replace(" ", "")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d+)?", raw):
        raw = raw.replace(".", "").replace(",", ".")
    elif "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return None


def _unit_value(key: str, value: str) -> Optional[float]:
    """Etiket alanına göre birim dönüşümlü sayı (yoksa None)."""
    n = _first_num(value)
    if n is None:
        return None
    v = tr_norm(value)
    if key == "lifting_capacity_kg":
        if re.search(r"\bton\b|\bt\b", v):
            return n * 1000
        return n
    if key in ("lift_height_mm", "min_height_mm"):
        if re.search(r"\bcm\b", v):
            return n * 10
        if re.search(r"\bm\b", v) and n < 10:
            return n * 1000
        return n
    if key == "net_weight_kg":
        if re.search(r"\bgr?\b|\bgram\b", v) and not re.search(r"\bkg\b", v):
            return n / 1000
        return n
    if key == "warranty_months":
        if re.search(r"\byil\b|\bsene\b", v):
            return n * 12
        return n
    if key == "working_pressure_bar" and re.search(r"\bpsi\b", v) and not re.search(r"\bbar\b", v):
        return round(n / 14.5038, 2)
    return n


def _motor_power(value: str) -> Tuple[Optional[str], Optional[float]]:
    v = tr_norm(value)
    n = _first_num(value)
    if n is None:
        return None, None
    if re.search(r"\b(hp|bg|ps)\b", v) and not re.search(r"\bkw\b", v):
        return "motor_power_hp", n
    if re.search(r"\bkw\b", v):
        return "motor_power_kw", n
    if re.search(r"\bw\b|\bwatt\b", v):
        return "motor_power_kw", round(n / 1000, 3)
    return "motor_power_kw", n


def _voltage(value: str) -> Optional[str]:
    v = tr_norm(value)
    has220 = bool(re.search(r"(?<!\d)2[23]0(?!\d)", v))
    has380 = bool(re.search(r"(?<!\d)(380|400)(?!\d)", v))
    if has220 and has380:
        return "220 / 380 V"
    if has380:
        return "380 V"
    if has220:
        return "220 V"
    if re.search(r"(?<!\d)24(?!\d)", v):
        return "24 V"
    if re.search(r"(?<!\d)12(?!\d)", v):
        return "12 V"
    return None


def _phase(value: str) -> Optional[str]:
    v = tr_norm(value)
    if "trifaze" in v or re.search(r"\b3\b", v) or "uc faz" in v:
        return "Trifaze"
    if "monofaze" in v or re.search(r"\b1\b", v) or "tek faz" in v:
        return "Monofaze"
    return None


def _label_key(label: str, fm: Dict[str, Dict[str, Any]]) -> Optional[str]:
    n = tr_norm(label)
    n = re.sub(r"\b(mm|cm|kg|lt|bar|nm|kw|hp|db|v|hz|ah|inc|inch|adet)\b", "", n).strip()
    n = re.sub(r"\s+", " ", n)
    if n in SYNONYMS:
        return SYNONYMS[n]
    for k, f in fm.items():
        if tr_norm(f.get("label")) == n:
            return k
    return None


def map_specs(rows: List[Tuple[str, str]], cfg: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]], Dict[str, str]]:
    """rows: [(etiket, değer)] → (specs, extra_specs, meta) — meta: brand/sku/gtin ipuçları."""
    from product_specs import field_map, _clean_value  # noqa: PLC2701 — aynı doğrulama kuralları

    fm = field_map(cfg)
    specs: Dict[str, Any] = {}
    extras: List[Dict[str, str]] = []
    meta: Dict[str, str] = {}
    seen_labels = set()
    for label, value in rows:
        label = re.sub(r"\s+", " ", str(label or "")).strip(" :\t-–")[:80]
        value = re.sub(r"\s+", " ", str(value or "")).strip()[:300]
        if not label or not value or tr_norm(label) in seen_labels:
            continue
        seen_labels.add(tr_norm(label))
        nl = tr_norm(label)
        if nl in META_LABELS:
            meta.setdefault(META_LABELS[nl], value)
            continue
        key = _label_key(label, fm)
        val: Any = value
        done = False
        if key == "motor_power":
            key, val = _motor_power(value)
            done = True
        if key == "voltage":
            val = _voltage(value)
        elif key == "phase":
            val = _phase(value)
        if key == "lifting_capacity_kg":
            vn = tr_norm(value)
            if re.search(r"\b(lt|litre|l) (dk|dakika)\b|\blt dk\b|\bl min\b", vn):
                key = "air_flow_lpm"
            elif re.search(r"\b(lt|litre|l)\b", vn):
                key = "tank_volume_l"
            elif not re.search(r"\b(kg|ton|t)\b", vn):
                key = None
        if done:
            pass
        elif key and fm.get(key, {}).get("type") in ("number", "int"):
            val = _unit_value(key, value)
            if val is not None and fm[key].get("type") == "int":
                val = int(round(val))
        elif key and fm.get(key, {}).get("type") == "multiselect":
            sep = r"[,;+]| ve " if key == "drive_size" else r"[,;/+]| ve "
            val = [x.strip() for x in re.split(sep, value) if x.strip()]
        elif key and fm.get(key, {}).get("type") == "bool":
            val = value
        f = fm.get(key or "")
        if not f or key in specs or val in (None, "", []):
            extras.append({"name": label, "value": value})
            continue
        try:
            cv = _clean_value(f, val)
        except (ValueError, TypeError):
            cv = None
        if cv in (None, "", [], {}):
            extras.append({"name": label, "value": value})
        else:
            specs[key] = cv
    return specs, extras[:40], meta
