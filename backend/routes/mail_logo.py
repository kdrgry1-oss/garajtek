"""Gönderen logosu (BIMI) — gelen kutusunda mailin yanında görünen marka logosu.

BIMI: alan adının DNS'ine `default._bimi` TXT kaydı (v=BIMI1; l=<SVG adresi>) eklenir; destekleyen
posta servisleri (Yahoo, Apple Mail, Fastmail…; Gmail ayrıca VMC sertifikası ister) logoyu gösterir.
Şart: DMARC p=quarantine/reject ve logonun "SVG Tiny PS" biçiminde, HTTPS'ten sunulması.

  GET    /api/admin/mail-logo        durum + DNS kaydı (yetki: settings.mail_server)
  POST   /api/admin/mail-logo        {svg: "<svg…>"} yükle (doğrula + Tiny PS'e uyarla)
  DELETE /api/admin/mail-logo
  GET    /api/bimi/logo.svg          herkese açık logo (image/svg+xml)
"""
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from .deps import db, require_permission
from activity_audit import record_admin_audit

router = APIRouter(tags=["mail-logo"])
PERM = "settings.mail_server"
DOC_ID = "mail_bimi_logo"
MAX_BYTES = 32 * 1024
SVG_NS = "http://www.w3.org/2000/svg"

# Tiny PS'te yasak / güvenlik açısından tehlikeli öğeler ve öznitelikler
_FORBIDDEN_TAGS = {"script", "foreignobject", "image", "a", "animate", "animatemotion", "animatetransform",
                   "set", "iframe", "embed", "object", "use", "style"}
_FORBIDDEN_RX = re.compile(r"<!DOCTYPE|<!ENTITY|javascript:|\son[a-z]+\s*=|xlink:href\s*=\s*[\"'](?!#)|href\s*=\s*[\"'](?!#)",
                           re.I)


def _site_url(request: Request = None) -> str:
    env = (os.environ.get("SITE_URL") or os.environ.get("FRONTEND_PUBLIC_URL") or "").strip().rstrip("/")
    if env:
        return env
    domain = (os.environ.get("SITE_DOMAIN") or "garajtek.com").strip()
    return f"https://{domain}"


def logo_url(request: Request = None) -> str:
    return f"{_site_url(request)}/api/bimi/logo.svg"


def bimi_record(url: str) -> dict:
    return {"type": "TXT", "name": "default._bimi", "value": f"v=BIMI1; l={url};"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def sanitize_svg(raw: str, title: str = "GarajTek") -> str:
    """SVG'yi doğrular ve BIMI 'SVG Tiny PS' profiline uyarlar; uygun değilse HTTPException(400)."""
    s = (raw or "").strip()
    if not s:
        raise HTTPException(status_code=400, detail="SVG içeriği boş")
    if len(s.encode("utf-8")) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="Logo en fazla 32 KB olmalı (BIMI sınırı)")
    s = re.sub(r"^<\?xml[^>]*\?>\s*", "", s)
    if _FORBIDDEN_RX.search(s):
        raise HTTPException(status_code=400, detail="SVG'de betik, dış bağlantı veya DOCTYPE olamaz")
    try:
        root = ET.fromstring(s)
    except ET.ParseError:
        raise HTTPException(status_code=400, detail="Geçerli bir SVG dosyası değil")
    if _local(root.tag) != "svg":
        raise HTTPException(status_code=400, detail="Dosya bir SVG değil")
    for el in root.iter():
        if _local(el.tag) in _FORBIDDEN_TAGS:
            raise HTTPException(status_code=400, detail=f"SVG'de <{_local(el.tag)}> öğesi kullanılamaz (BIMI Tiny PS)")
        for k in list(el.attrib):
            lk = _local(k)
            if lk.startswith("on") or lk in ("href",) and not str(el.attrib[k]).startswith("#"):
                raise HTTPException(status_code=400, detail="SVG'de olay/dış bağlantı özniteliği olamaz")
    vb = (root.attrib.get("viewBox") or "").replace(",", " ").split()
    if len(vb) == 4:
        try:
            w, h = float(vb[2]), float(vb[3])
            if w <= 0 or h <= 0 or abs(w - h) / max(w, h) > 0.02:
                raise HTTPException(status_code=400, detail="Logo kare olmalı (viewBox genişlik = yükseklik)")
        except ValueError:
            raise HTTPException(status_code=400, detail="viewBox geçersiz")
    else:
        raise HTTPException(status_code=400, detail="SVG'de kare bir viewBox olmalı (ör. viewBox=\"0 0 512 512\")")
    # Tiny PS profili: version/baseProfile, x/y yok, <title> zorunlu
    root.set("version", "1.2")
    root.set("baseProfile", "tiny-ps")
    for a in ("x", "y", "width", "height"):
        root.attrib.pop(a, None)
    if not any(_local(c.tag) == "title" for c in list(root)):
        t = ET.Element(f"{{{SVG_NS}}}title" if root.tag.startswith("{") else "title")
        t.text = title
        root.insert(0, t)
    ET.register_namespace("", SVG_NS)
    out = ET.tostring(root, encoding="unicode")
    if 'xmlns="' not in out[:300]:
        out = out.replace("<svg", f'<svg xmlns="{SVG_NS}"', 1)
    return out


@router.get("/admin/mail-logo")
async def get_mail_logo(request: Request, current_user: dict = Depends(require_permission(PERM))):
    doc = await db.settings.find_one({"id": DOC_ID}, {"_id": 0}) or {}
    url = logo_url(request)
    return {"has_logo": bool(doc.get("svg")), "url": url, "updated_at": doc.get("updated_at"),
            "size": len((doc.get("svg") or "").encode("utf-8")), "record": bimi_record(url)}


@router.post("/admin/mail-logo")
async def set_mail_logo(payload: dict, request: Request, current_user: dict = Depends(require_permission(PERM))):
    svg = sanitize_svg(str((payload or {}).get("svg") or ""), str((payload or {}).get("title") or "GarajTek")[:60])
    now = datetime.now(timezone.utc).isoformat()
    await db.settings.update_one({"id": DOC_ID}, {"$set": {"id": DOC_ID, "svg": svg, "updated_at": now}}, upsert=True)
    await record_admin_audit(db, action="mail_logo.update", entity_type="settings", entity_id=DOC_ID,
                             before=None, after={"size": len(svg)}, current_user=current_user, request=request,
                             source="mail_admin")
    url = logo_url(request)
    return {"ok": True, "url": url, "size": len(svg.encode("utf-8")), "record": bimi_record(url)}


@router.delete("/admin/mail-logo")
async def delete_mail_logo(request: Request, current_user: dict = Depends(require_permission(PERM))):
    await db.settings.delete_one({"id": DOC_ID})
    await record_admin_audit(db, action="mail_logo.delete", entity_type="settings", entity_id=DOC_ID,
                             before=None, after=None, current_user=current_user, request=request, source="mail_admin")
    return {"ok": True}


@router.get("/bimi/logo.svg")
async def public_logo():
    doc = await db.settings.find_one({"id": DOC_ID}, {"_id": 0, "svg": 1}) or {}
    if not doc.get("svg"):
        raise HTTPException(status_code=404, detail="Logo yok")
    return Response(content=doc["svg"], media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
                             "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
