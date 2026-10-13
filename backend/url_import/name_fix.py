"""Aktarılan ürün adlarında yazım/biçim düzeltmesi (sahip talebi 13.10.2026).

  * Rakam yerine yazılmış O harfi: "1O Çekmeceli" → "10 Çekmeceli"
  * Bilinen yazım hataları: "Gress" → "Gres", "Profosyonel" → "Profesyonel", "Kurbağcık" → "Kurbağacık"
  * Türkçe karaktersiz yazımlar: "Baglantili" → "Bağlantılı", "Cekmeceli" → "Çekmeceli" …
  * TAMAMI BÜYÜK HARF adlar Türkçe "Başlık Biçimi"ne çevrilir; model/stok kodları (rakam içeren), kısaltmalar
    (ALG, DHT, NT, ARM…) ve 1/2, 3/8 gibi ölçüler korunur.
  * Birimler: "300MM"/"300 Mm" → "300 mm", "15 Cm" → "15 cm", "200 Lt" korunur.
Yalnız biçim değişir; ürünün anlamı/kodları değişmez. Idempotent.
"""
from __future__ import annotations

import re

KEEP_UPPER = {"ALG", "DHT", "NT", "ARM", "RC", "KK", "HP", "LED", "DPF", "RTV", "SDS", "CR", "CRV", "CR-V", "TIG", "MIG",
              "MMA", "AC", "DC", "USB", "LCD", "PVC", "ABS", "OBD", "OBD2", "ATV", "UV", "XL", "XXL", "BC", "CS", "GR",
              "PRODHT", "MCTEST", "BAT", "IW", "TW", "MT", "EG", "FK", "FR", "S2", "II", "III", "IV", "4X4"}
FIXES = [
    (r"\bgress\b", "gres"), (r"\bprofosyonel\b", "profesyonel"), (r"\bkurbağcık\b", "kurbağacık"),
    (r"\bbaglantili\b", "bağlantılı"), (r"\bbaglanti\b", "bağlantı"), (r"\bcekmeceli\b", "çekmeceli"),
    (r"\bcekmece\b", "çekmece"), (r"\bcelik\b", "çelik"), (r"\bcalisma\b", "çalışma"), (r"\bsokme\b", "sökme"),
    (r"\btakimi\b", "takımı"), (r"\bpense\b", "pense"), (r"\bcircir\b", "cırcır"), (r"\bkaynak\b", "kaynak"),
    (r"\bisikli\b", "ışıklı"), (r"\bsarjli\b", "şarjlı"), (r"\bakulu\b", "akülü"), (r"\bkriko\b", "kriko"),
    (r"\bustu\b", "üstü"), (r"\bdusuk\b", "düşük"), (r"\bsase\b", "şase"), (r"\byag\b", "yağ"),
    (r"\barac\b", "araç"),
]
# Büyük harfli kaynakta noktasız "I" belirsiz (TORNAVIDA=tornavida, HAVALI=havalı). Ünlü uyumu + istisnalar.
I_AS_I = {"tornavida", "rico", "vida", "vidalı", "vidalama", "kriko", "silikon", "bits", "mini", "profil", "otomatik",
          "dijital", "digital", "pnömatik", "pnomatik", "elektrik", "elektrikli", "spiral", "radyatör", "plastik",
          "hidrolik", "manyetik", "mekanik", "magnetik", "sanayi", "seri", "servis", "sistemi", "sistem", "tip", "tipi",
          "litre", "metrik", "titanyum", "nikel", "krom", "digital", "lift", "lifti", "liftler", "kit", "kiti",
          "kompresyon", "testere", "takviye", "dizel", "benzinli", "enjektör", "kilit", "kilitli", "lityum", "pistonlu",
          "fiber", "stil", "tork", "torx", "allen", "alyan", "pim", "pimli", "segman", "kablo", "kablolu", "ince",
          "film", "filtre", "kristal", "orbital", "universal", "ünivesal", "endüstriyel", "profesyonel", "craft"}
_BACK = set("aıouAIOU")
_VOWELS = set("aeıioöuüAEIİOÖUÜ")


def _ascii_I_word(core: str) -> str:
    """Noktasız-I içeren BÜYÜK harf kelime (İ yok) → küçük harf; her I ünlü uyumuyla ı/i olur."""
    cand = core.replace("I", "i").lower()
    if cand in I_AS_I:
        return cand
    out, last = [], None
    for ch in core:
        if ch == "I":
            low = "ı" if (last is None or last in _BACK) else "i"
            out.append(low)
            last = "ı" if low == "ı" else "i"
            continue
        lo = tr_lower(ch)
        out.append(lo)
        if ch in _VOWELS:
            last = ch
    return "".join(out)


_TR_UP = str.maketrans({"i": "İ", "ı": "I"})
_TR_LO = str.maketrans({"I": "ı", "İ": "i"})


def tr_lower(s: str) -> str:
    return s.translate(_TR_LO).lower()


def tr_upper(s: str) -> str:
    return s.translate(_TR_UP).upper()


def _match_case(src: str, dst: str) -> str:
    if src.isupper():
        return tr_upper(dst)
    if src[:1].isupper():
        return tr_upper(dst[:1]) + dst[1:]
    return dst


def _mostly_upper(s: str) -> bool:
    letters = [c for c in s if c.isalpha()]
    return len(letters) >= 6 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.75


_DOTTED_CTX: dict = {}


def _title_word(w: str) -> str:
    core = w.strip("()[],.'\"’")
    if not core or any(ch.isdigit() for ch in core) or core in KEEP_UPPER or tr_upper(core) in KEEP_UPPER:
        return w
    if "-" in w and not any(ch.isdigit() for ch in w):
        return "-".join(_title_word(p) for p in w.split("-"))
    exc = core.replace("I", "i").replace("İ", "i").lower()
    if "I" in core and exc in I_AS_I:
        low = w.replace(core, exc)
    elif "I" in core and "İ" not in core and not _DOTTED_CTX.get("dotted"):
        low = w.replace(core, _ascii_I_word(core))
    else:
        low = tr_lower(w)
    for i, ch in enumerate(low):
        if ch.isalpha():
            return low[:i] + tr_upper(ch) + low[i + 1:]
    return low


def _is_caps_word(w: str) -> bool:
    core = w.strip("()[],.'\"’")
    letters = [c for c in core if c.isalpha()]
    return len(letters) >= 3 and not any(ch.isdigit() for ch in core) and all(c.isupper() for c in letters) \
        and core not in KEEP_UPPER and tr_upper(core) not in KEEP_UPPER


def fix_name(name: str) -> str:
    if not name:
        return name
    s = re.sub(r"\s+", " ", str(name)).strip()
    s = re.sub(r"(?<=\d)[Oo](?=\s|$|\d)", "0", s)            # 1O → 10
    s = re.sub(r"(?<=\s)[Oo](?=\d)", "0", s)                 # O5 → 05 (kelime başı)
    for pat, rep in FIXES:
        s = re.sub(pat, lambda m, rep=rep: _match_case(m.group(0), rep), s, flags=re.I)
    words = s.split(" ")
    caps = [w for w in words if _is_caps_word(w)]
    if _mostly_upper(s) or caps:
        _DOTTED_CTX["dotted"] = "İ" in s           # kaynak İ kullanıyorsa noktasız I gerçekten ı'dır
        s = " ".join(_title_word(w) if (_mostly_upper(s) or _is_caps_word(w)) else w for w in words)
    s = re.sub(r"(\d)\s?(mm|MM|Mm)\b", r"\1 mm", s)
    s = re.sub(r"(\d)\s?(cm|CM|Cm)\b", r"\1 cm", s)
    s = re.sub(r"(\d)\s?(Lt|LT|lt)\b", r"\1 L", s)
    s = re.sub(r"(\d)\s?(kg|KG|Kg)\b", r"\1 kg", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
