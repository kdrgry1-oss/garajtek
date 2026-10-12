"""Ürün adı anahtar kelime kuralları → garaj kategorisi (toplu site aktarımı için).

CategoryMapper (kırıntı + başlık puanı) eşleştiremediği ya da kaba eşleştirdiği ürünleri
(sprey, kriko, mengene, bits seti…) ürün adındaki kalıplarla doğru yaprak kategoriye koyar.
Metin tr_norm ile küçük harf + Türkçe karaktersiz hâle getirilir; kurallar SIRAYLA denenir,
ilk eşleşen kazanır. override=True kurallar mevcut (otomatik) kategoriyi de düzeltir — ör.
"Fren Balata Temizleme Spreyi" bir fren test cihazı değil, bakım spreyidir.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .specs_map import tr_norm

# (kalıp, kategori slug'ı, override)
RULES: List[Tuple[str, str, bool]] = [
    # kimyasallar ve araç koruma — her zaman öncelikli
    (r"\b(sprey|spreyi|kopugu)\b|\bpas sokucu", "temizleme-ve-bakim-spreyleri", True),
    (r"(enjektor|yakit sistemi|motor ic|radyator) (temizleyici|sizinti)|partikul temizleme sivisi|"
     r"temizleyici \d+ ?ml|sizinti onleyici", "yakit-motor-ve-radyator-katkilari", True),
    (r"\b(rtv|sivi conta)\b", "sivi-conta-ve-yapistiricilar", True),
    (r"koltuk kilifi|direksiyon (kilifi|streci)|arac koruma|rulo aski", "koltuk-direksiyon-ve-arac-koruma", True),
    (r"is guvenligi|ayakkabi", "is-guvenligi", True),
    # makineler
    (r"kaporta cektirme|spot pro|kaporta dayama", "kaporta-cektirme-spot-makineleri", False),
    (r"aku sarj|redresor|batarya test|aku test", "aku-test-ve-takviye-cihazlari", False),
    (r"tas motoru|tel firca", "tas-motorlari", False),
    (r"geriye yatarli|lastik sokme", "lastik-sokme-takma-makineleri", False),
    (r"kopuk sivi tanki|kopuk tanki", "oto-yikama-ekipmanlari", False),
    (r"petek temizleme|dpf|kumlama", "oto-servis-ekipmanlari", False),
    (r"karterden yag|yag (toplama|hunisi|emme)|legen", "yag-bosaltma-ve-degistirme-cihazlari", False),
    (r"kriko", "yer-krikolari", False),
    (r"hidrolik dogrultma", "hidrolik-duzeltme-setleri", False),
    (r"motor aski|zincirli cektirme|hubzug|vinc", "motor-vincleri", False),
    (r"mengene", "mengeneler", False),
    (r"yatma tahtasi|bakim tablasi|tamirci koltugu", "yatma-tahtalari-ve-tamirci-koltuklari", False),
    (r"manyetik|miknatisli|aski kancasi|takim cantasi|takim tepsisi", "manyetik-tepsi-aski-ve-duzenleyiciler", False),
    (r"\bo[ -]?ring|conta seti|oring", "o-ring-ve-sarf-malzemeleri", False),
    # test ve ölçüm
    (r"refraktometre|antifriz", "antifriz-ve-sivi-olcerler", False),
    (r"(yag basin\w*|conta|enjektor|radyator) test|test (kiti|cihazi)", "oto-test-kitleri", False),
    (r"kontrol kalemi|steteskop|endoskop|termometre|boya olcum|izolasyon|alt takim kontrol",
     "kontrol-kalemleri-ve-olcum-cihazlari", False),
    (r"fener|projektor|lumen", "led-lambalar-ve-calisma-isiklari", False),
    # tezgah, dolap
    (r"tezgah|altigen masa|cekmeceli", "takim-tezgahlari", False),
    # el aletleri
    (r"bits|uc seti", "bits-uc-setleri", False),
    (r"rulman|rayli cektirme|yatak", "rulman-ve-rayli-cektirmeler", False),
    (r"rotil|rot kolu|helezon|yay (cektirme|sokme)|amortisor", "suspansiyon-ve-yay-aparatlari", False),
    (r"kumpas|sentil|feeler", "olcum-aletleri", False),
    (r"\bege\b|testere kolu|pafta|kilavuz", "ege-testere-ve-pafta-kilavuz", False),
    (r"kerpeten|kargaburun|k\W?burun|yankeski|yan keski|pense", "penseler", False),
    (r"cekic|keski|levye|tranca|kurt agzi|aslan pencesi|zimba", "cekic-ve-keskiler", False),
    (r"allen|alyan|torx", "allen-ve-torx", False),
    (r"circir (kolu|ara)", "lokma-kollari-ve-circirlar", False),
    (r"kurbag\w*|bijon|anahtar", "anahtarlar", False),
    (r"somun kirici", "ozel-aparatlar", False),
    (r"yagdanlik", "yaglama-ekipmanlari", False),
    (r"akulu|komursuz|kirici delici|zincirli testere", "elektrikli-ve-sarjli-el-aletleri", False),
    (r"paket|seti \d+ parca|hobi garaj", "servis-kurulum-paketleri", False),
]
_COMPILED = [(re.compile(p), slug, ov) for p, slug, ov in RULES]


def match(name: str, *, has_category: bool) -> Optional[str]:
    """Ürün adına uyan kategori slug'ı; ürünün kategorisi varsa yalnız override kuralları."""
    text = tr_norm(name or "")
    for rx, slug, override in _COMPILED:
        if has_category and not override:
            continue
        if rx.search(text):
            return slug
    return None
