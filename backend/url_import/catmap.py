"""Kaynak kırıntı (breadcrumb) + başlık anahtar kelimeleri → garaj kategori ağacında en iyi eşleşme.

Puan: kategori adındaki/slug'ındaki anlamlı kelimelerin kaçı metinde geçiyor (Türkçe-normalize,
kök eşleşmesi: "lift" ≈ "liftler", "makas" ≈ "makasli"). Tümü eşleşen derin (daha özel) kategori
öne geçer; kırıntıdan gelen eşleşmeler başlıktan gelenlerden ağırdır. Seçilen kategorinin tüm
ataları `category_ids`'e eklenir (vitrin üst kategori sayfalarında da görünür).
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .specs_map import tr_norm

STOP = {"ve", "ile", "icin", "the", "and", "urun", "urunler", "urunleri", "ana", "sayfa", "anasayfa",
        "kategori", "kategoriler", "tum", "yeni", "diger", "cesitleri", "modelleri", "fiyatlari",
        "fiyat", "en", "cok", "satan", "home", "shop", "magaza", "online", "satis", "set", "seti",
        "setleri", "takimi", "takimlari", "ekipman", "ekipmanlari", "aletleri", "aletler", "makine",
        "makinesi", "makineleri", "makinalari", "cihaz", "cihazi", "cihazlari", "aparat", "aparatlari"}
EXCLUDED_SLUGS = {"urun-setleri", "indirimli-urunler"}

_PHRASES = [
    (r"\b(cift|2|iki)\s*(li|lu)?\s*(sutun|direk)", "iki sutunlu"),
    (r"\b(4|dort)\s*(lu)?\s*(sutun|direk)", "dort sutunlu"),
    (r"\bmakas\w*", "makasli"),
    (r"\bkompres\w*", "kompresor"),
    (r"\bmoto(r)?siklet\w*", "motosiklet"),
    (r"\bsomun\s+sok\w*", "somun sokme"),
    (r"\blastik\s+sok\w*", "lastik sokme"),
]


def _tokens(text: str) -> List[str]:
    t = tr_norm(text)
    for pat, rep in _PHRASES:
        t = re.sub(pat, rep, t)
    return [w for w in t.split() if len(w) >= 2 and w not in STOP and not w.isdigit()]


def _stem(w: str) -> str:
    for suf in ("lerinin", "larinin", "leri", "lari", "ler", "lar", "si", "su", "li", "lu", "i", "u"):
        if len(w) - len(suf) >= 4 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def _match(a: str, b: str) -> bool:
    if a == b:
        return True
    sa, sb = _stem(a), _stem(b)
    if sa == sb:
        return True
    short, long_ = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    return len(short) >= 4 and long_.startswith(short)


class CategoryMapper:
    def __init__(self, categories: Iterable[Dict[str, Any]]):
        self.by_id: Dict[str, Dict[str, Any]] = {}
        for c in categories:
            if c.get("id") is None:
                continue
            self.by_id[str(c["id"])] = c
        self.nodes: List[Tuple[str, List[str], int]] = []
        for cid, c in self.by_id.items():
            if c.get("slug") in EXCLUDED_SLUGS or c.get("is_active") is False:
                continue
            toks = []
            for w in _tokens(f"{c.get('name') or ''} {str(c.get('slug') or '').replace('-', ' ')}"):
                if not any(_match(w, x) for x in toks):
                    toks.append(w)
            if toks:
                self.nodes.append((cid, toks, len(self.ancestors(cid)) - 1))
        # IDF benzeri ağırlık: çok kategoride geçen kelime ("lastik", "lokma") daha az ayırt edicidir
        df: Dict[str, int] = {}
        for _cid, toks, _d in self.nodes:
            for t in toks:
                df[_stem(t)] = df.get(_stem(t), 0) + 1
        self.weight = {k: 1.0 / v for k, v in df.items()}

    def ancestors(self, cid: str) -> List[str]:
        """[kategori, ebeveyn, …, kök] (döngü korumalı)."""
        out: List[str] = []
        cur, guard = str(cid), 0
        while cur and cur in self.by_id and cur not in out and guard < 20:
            out.append(cur)
            cur = str(self.by_id[cur].get("parent_id") or "")
            guard += 1
        return out

    def best(self, breadcrumb: List[str], title: str = "", hints: Iterable[str] = ()) -> Optional[Dict[str, Any]]:
        """Dönüş: {"id", "name", "slug", "score", "ids": [kategori + atalar]} ya da None."""
        bc_tokens = _tokens(" ".join(list(breadcrumb or []) + list(hints or [])))
        ti_tokens = _tokens(title or "")
        best: Optional[Tuple[float, str]] = None
        for cid, toks, depth in self.nodes:
            w = [self.weight.get(_stem(t), 1.0) for t in toks]
            hit_bc = [any(_match(t, x) for x in bc_tokens) for t in toks]
            hit_ti = [any(_match(t, x) for x in ti_tokens) for t in toks]
            w_hit = sum(wi for wi, a, b in zip(w, hit_bc, hit_ti) if a or b)
            if w_hit == 0:
                continue
            ratio = w_hit / sum(w)
            if ratio < 0.5:
                continue
            w_bc = sum(wi for wi, a in zip(w, hit_bc) if a)
            score = ratio * 10 + w_hit * 3 + w_bc * 1.5 + depth * 0.5 + sum(hit_ti) * 0.3
            score += sum(1 for a, b in zip(hit_bc, hit_ti) if a or b)
            if ratio < 0.999:
                score -= 2
            if best is None or score > best[0]:
                best = (score, cid)
        if not best or best[0] < 8:
            return None
        cid = best[1]
        c = self.by_id[cid]
        return {"id": cid, "name": c.get("name") or "", "slug": c.get("slug") or "", "score": round(best[0], 2),
                "ids": self.ancestors(cid)}
