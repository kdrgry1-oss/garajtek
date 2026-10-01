"""Demo içeriği komut satırından yükle / kaldır.

Önerilen yol PANELDİR (Ayarlar › Demo İçerik) — servis çalışırken güvenle yapılır.
Komut satırı iki şekilde çalışır:

1) Çalışan servise API üzerinden (servisi durdurmadan; süper yönetici e-posta/şifresi gerekir):
     /opt/garajtek/venv/bin/python seed_demo.py --api http://127.0.0.1:8001 --email admin@alanadi.com
     /opt/garajtek/venv/bin/python seed_demo.py --api http://127.0.0.1:8001 --email admin@alanadi.com --remove
   (şifre sorulur; yönetici MFA açıksa panel yolunu kullanın)

2) Doğrudan veritabanına (localdb tek-süreç kilidi nedeniyle SERVİS DURDURULMUŞKEN):
     sudo systemctl stop garajtek-api
     cd /opt/garajtek/backend && sudo -u garajtek bash -c 'set -a; . ./.env; set +a; /opt/garajtek/venv/bin/python seed_demo.py'
     sudo systemctl start garajtek-api
   Kaldırmak için sona --remove ekleyin.
"""
import argparse
import asyncio
import getpass
import json
import sys


def _api(base, email, remove):
    import urllib.request
    pw = getpass.getpass("Şifre: ")
    req = urllib.request.Request(f"{base.rstrip('/')}/api/auth/login", method="POST",
                                 data=json.dumps({"email": email, "password": pw}).encode(),
                                 headers={"Content-Type": "application/json"})
    tok = json.load(urllib.request.urlopen(req))["token"]
    req = urllib.request.Request(f"{base.rstrip('/')}/api/admin/demo-content", method="DELETE" if remove else "POST",
                                 headers={"Authorization": f"Bearer {tok}"})
    print(json.dumps(json.load(urllib.request.urlopen(req, timeout=600)), ensure_ascii=False, indent=2))


async def _direct(remove):
    from starlette.requests import Request
    from routes.deps import db
    import demo_content as dc

    if remove:
        print(await dc.remove_demo(db))
        return
    from routes.products import create_product
    req = Request({"type": "http", "method": "POST", "path": "/cli/seed_demo", "headers": [], "client": ("127.0.0.1", 0)})
    user = {"id": "cli", "email": "cli@localhost", "is_admin": True, "first_name": "CLI", "last_name": ""}
    print(json.dumps(await dc.load_demo(db, lambda d: create_product(d, req, user)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="GarajTek demo içerik yükle/kaldır")
    ap.add_argument("--remove", action="store_true", help="yalnız demo etiketli kayıtları sil")
    ap.add_argument("--api", help="çalışan servis adresi (ör. http://127.0.0.1:8001)")
    ap.add_argument("--email", help="süper yönetici e-postası (--api ile)")
    a = ap.parse_args()
    if a.api:
        if not a.email:
            sys.exit("--api ile --email gerekli")
        _api(a.api, a.email, a.remove)
    else:
        asyncio.run(_direct(a.remove))
