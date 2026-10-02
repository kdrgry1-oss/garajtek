"""Açıklama HTML'i için izin listeli temizleyici (URL'den Ürün Aktar).

* İzinli etiketler dışındaki her şey ya tümden silinir (script/style/iframe/form/svg/img/video…)
  ya da içeriği korunarak açılır (div/span/font/section… → yalnız metin ve izinli çocuklar kalır).
* Hiçbir öznitelik korunmaz (on* olay işleyicileri, style, class, id, href, src…); yalnız tablo
  hücrelerinde colspan/rowspan (sayısal) kalır.
* Bağlantılar (dış/iç fark etmeksizin) açılır: metin kalır, href silinir → kaynak siteye link yok.
* Görseller açıklamadan çıkarılır (hotlink YOK; ürün görselleri ayrıca indirilip depoya yazılır).
"""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, Comment, Tag

ALLOWED = {"p", "br", "ul", "ol", "li", "strong", "b", "em", "i", "u", "h2", "h3", "h4", "h5",
           "table", "thead", "tbody", "tfoot", "tr", "th", "td", "blockquote", "hr", "sub", "sup"}
DROP_WITH_CONTENT = {"script", "style", "iframe", "frame", "frameset", "object", "embed", "applet",
                     "form", "input", "button", "select", "textarea", "option", "svg", "math",
                     "noscript", "template", "video", "audio", "source", "track", "img", "picture",
                     "canvas", "map", "area", "link", "meta", "base", "head", "title", "dialog"}
RENAME = {"h1": "h2", "h6": "h5", "dt": "strong", "dd": "p", "caption": "p"}
MAX_LEN = 60000


def _parser() -> str:
    try:
        import lxml  # noqa: F401
        return "lxml"
    except Exception:  # noqa: BLE001
        return "html.parser"


def sanitize_html(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(str(raw), _parser())
    root = soup.body or soup
    for c in root.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    for t in root.find_all(list(DROP_WITH_CONTENT)):
        t.decompose()
    # içten dışa: önce çocuklar işlensin diye ters sırada
    for t in reversed(root.find_all(True)):
        if not isinstance(t, Tag) or t.parent is None:
            continue
        name = t.name.lower()
        if name in RENAME:
            t.name = name = RENAME[name]
        if name not in ALLOWED:
            # blok elemanlar açılırken metin birleşmesin
            if name in ("div", "section", "article", "header", "footer", "main", "aside", "center"):
                t.insert_after(" ")
            t.unwrap()
            continue
        keep = {}
        if name in ("td", "th"):
            for a in ("colspan", "rowspan"):
                v = str(t.attrs.get(a) or "")
                if v.isdigit() and 0 < int(v) < 50:
                    keep[a] = v
        t.attrs = keep
    # boş paragrafları/başlıkları temizle
    for t in root.find_all(["p", "h2", "h3", "h4", "h5", "li", "strong", "b", "em", "i", "u"]):
        if not t.get_text(strip=True) and not t.find(["br", "table"]):
            t.decompose()
    html = "".join(str(x) for x in root.contents) if root is not soup else str(soup)
    html = re.sub(r"(\s*<br/?>\s*){3,}", "<br/><br/>", html)
    html = re.sub(r"[ \t\r\f\v]+", " ", html)
    html = re.sub(r"\n\s*\n+", "\n", html).strip()
    return html[:MAX_LEN]


def text_of(raw: str) -> str:
    if not raw:
        return ""
    soup = BeautifulSoup(str(raw), _parser())
    return re.sub(r"\s+", " ", soup.get_text(" ")).strip()
