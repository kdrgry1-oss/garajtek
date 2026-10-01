"""routes/mail_admin.py — sudo CLI köprüsü (subprocess mock'lanır, gerçek sistem değişmez)."""
import asyncio
import importlib.util
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

ROOT = Path(__file__).parents[1]


class FakeProc:
    def __init__(self, out=b"", err=b"", rc=0, hang=False):
        self._out, self._err, self.returncode, self._hang = out, err, rc, hang
        self.stdin_data = None
        self.killed = False

    async def communicate(self, input=None):
        self.stdin_data = input
        if self._hang:
            await asyncio.sleep(10)
        return self._out, self._err

    def kill(self):
        self.killed = True


@pytest.fixture
def env(monkeypatch, tmp_path):
    # routes paketini __init__ (tüm uygulama) çalıştırmadan yükle; deps'i taklit et
    pkg = types.ModuleType("routes")
    pkg.__path__ = [str(ROOT / "routes")]
    deps = types.ModuleType("routes.deps")
    settings = SimpleNamespace(find_one=AsyncMock(return_value={"id": "email_smtp", "host": "api.zeptomail.eu",
                                                                "from_name": "GarajTek"}),
                               update_one=AsyncMock())
    audit_logs = SimpleNamespace(insert_one=AsyncMock())
    deps.db = SimpleNamespace(settings=settings, audit_logs=audit_logs)
    state = {"perms": ["*"], "required": []}

    def require_permission(key):
        async def _checker():
            state["required"].append(key)
            if "*" in state["perms"] or key in state["perms"]:
                return {"id": "u1", "email": "admin@garajtek.com", "is_admin": True}
            raise HTTPException(status_code=403, detail="yetki yok")
        return _checker

    deps.require_permission = require_permission
    monkeypatch.setitem(sys.modules, "routes", pkg)
    monkeypatch.setitem(sys.modules, "routes.deps", deps)
    monkeypatch.delitem(sys.modules, "routes.mail_admin", raising=False)
    spec = importlib.util.spec_from_file_location("routes.mail_admin", ROOT / "routes" / "mail_admin.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "routes.mail_admin", mod)
    spec.loader.exec_module(mod)

    cli = tmp_path / "garajtek-mail"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o755)
    monkeypatch.setattr(mod, "CLI_PATH", str(cli))
    monkeypatch.setattr(mod, "SUDO_PATH", "/usr/bin/sudo")

    calls = []
    queue = []

    async def fake_exec(*cmd, **kwargs):
        proc = queue.pop(0) if queue else FakeProc(out=b'{"ok": true}')
        calls.append({"cmd": list(cmd), "kwargs": kwargs, "proc": proc})
        return proc

    monkeypatch.setattr(mod.asyncio, "create_subprocess_exec", fake_exec)
    app = FastAPI()
    app.include_router(mod.router, prefix="/api")
    return SimpleNamespace(mod=mod, client=TestClient(app), calls=calls, queue=queue, db=deps.db,
                           state=state, cli=str(cli))


def ok(payload):
    return FakeProc(out=json.dumps(payload).encode())


def test_not_installed_returns_503(env, monkeypatch):
    monkeypatch.setattr(env.mod, "CLI_PATH", "/nonexistent/garajtek-mail")
    r = env.client.get("/api/admin/mail/status")
    assert r.status_code == 503
    body = r.json()
    assert body["installed"] is False
    assert "deploy/mail/README.md" in body["message"]
    assert env.calls == []


def test_status_runs_cli_via_sudo_without_shell(env):
    env.queue.append(ok({"ok": True, "services": {"postfix": "active"}}))
    r = env.client.get("/api/admin/mail/status")
    assert r.status_code == 200 and r.json()["services"]["postfix"] == "active"
    assert env.calls[0]["cmd"] == ["/usr/bin/sudo", "-n", env.cli, "status", "--json"]
    assert env.state["required"] == ["settings.mail_server"]


def test_create_mailbox_password_goes_via_stdin_not_argv(env):
    env.queue.append(ok({"ok": True, "address": "satis@garajtek.com", "quota": "2G"}))
    r = env.client.post("/api/admin/mail/mailboxes",
                        json={"email": "Satis@GarajTek.com", "password": "CokGizli-Sifre-1", "quota": "2g"})
    assert r.status_code == 200, r.text
    call = env.calls[0]
    assert "CokGizli-Sifre-1" not in " ".join(call["cmd"])
    assert call["cmd"][-2:] == ["--", "satis@garajtek.com"]
    assert "--password-stdin" in call["cmd"] and "2G" in call["cmd"]
    assert call["proc"].stdin_data == b"CokGizli-Sifre-1\n"
    audit = env.db.audit_logs.insert_one.await_args.args[0]
    assert audit["action"] == "mail.mailbox.create"
    assert "CokGizli" not in json.dumps(audit)


def test_create_mailbox_random_returns_one_time_password(env):
    env.queue.append(ok({"ok": True, "address": "a@garajtek.com", "password": "R4nd0m-pw-xyz"}))
    r = env.client.post("/api/admin/mail/mailboxes", json={"email": "a@garajtek.com"})
    assert r.status_code == 200 and r.json()["password"] == "R4nd0m-pw-xyz"
    assert "--random" in env.calls[0]["cmd"]
    assert env.calls[0]["proc"].stdin_data is None


@pytest.mark.parametrize("email", ["--purge@garajtek.com", "a;rm -rf /@garajtek.com", "a b@garajtek.com",
                                   "$(id)@garajtek.com", "info@garajtek..com", "noatsign", ""])
def test_invalid_email_rejected_before_cli(env, email):
    r = env.client.post("/api/admin/mail/mailboxes", json={"email": email})
    assert r.status_code == 400
    assert env.calls == []


def test_short_password_rejected(env):
    r = env.client.post("/api/admin/mail/mailboxes", json={"email": "a@garajtek.com", "password": "kisa"})
    assert r.status_code == 400 and env.calls == []


@pytest.mark.parametrize("code,status", [(2, 400), (3, 409), (4, 404), (1, 500)])
def test_cli_error_codes_map_to_http(env, code, status):
    env.queue.append(FakeProc(out=json.dumps({"ok": False, "error": "hata metni", "code": code}).encode(), rc=code))
    r = env.client.delete("/api/admin/mail/mailboxes/info@garajtek.com")
    assert r.status_code == status
    assert r.json()["detail"] == "hata metni"


def test_sudo_not_permitted_is_503(env):
    env.queue.append(FakeProc(err=b"sudo: a password is required", rc=1))
    r = env.client.get("/api/admin/mail/mailboxes")
    assert r.status_code == 503 and "sudoers" in r.json()["detail"]


def test_timeout_kills_process(env, monkeypatch):
    monkeypatch.setattr(env.mod, "DEFAULT_TIMEOUT", 0.05)
    proc = FakeProc(hang=True)
    env.queue.append(proc)

    async def go():
        with pytest.raises(env.mod.MailCliError) as e:
            await env.mod.run_mail_cli(["status", "--json"], timeout=0.05)
        return e.value

    err = asyncio.run(go())
    assert err.status == 504 and proc.killed


def test_permission_required(env):
    env.state["perms"] = ["orders.view"]
    r = env.client.get("/api/admin/mail/status")
    assert r.status_code == 403 and env.calls == []


def test_password_reset_and_delete_purge_args(env):
    env.queue.append(ok({"ok": True, "address": "info@garajtek.com", "password": "Yeni-Sifre-123"}))
    r = env.client.post("/api/admin/mail/mailboxes/info@garajtek.com/password", json={})
    assert r.json()["password"] == "Yeni-Sifre-123"
    assert env.calls[0]["cmd"][3:] == ["passwd", "--json", "--random", "--", "info@garajtek.com"]
    env.queue.append(ok({"ok": True}))
    env.client.delete("/api/admin/mail/mailboxes/info@garajtek.com?purge=true")
    assert env.calls[1]["cmd"][3:] == ["del", "--json", "--purge", "--", "info@garajtek.com"]


def test_alias_add_multiple_destinations(env):
    env.queue.append(ok({"ok": True}))
    r = env.client.post("/api/admin/mail/aliases",
                        json={"source": "satis@garajtek.com", "destination": "a@gmail.com, b@garajtek.com"})
    assert r.status_code == 200
    assert env.calls[0]["cmd"][3:] == ["alias-add", "--json", "--", "satis@garajtek.com",
                                       "a@gmail.com,b@garajtek.com"]


def test_queue_delete_validates_id(env):
    r = env.client.delete("/api/admin/mail/queue/abc;rm")
    assert r.status_code in (400, 404) and env.calls == []
    env.queue.append(ok({"ok": True}))
    assert env.client.delete("/api/admin/mail/queue/0EF8B102CCD").status_code == 200


def test_quota_update(env):
    env.queue.append(ok({"ok": True}))
    assert env.client.put("/api/admin/mail/mailboxes/info@garajtek.com/quota", json={"quota": "5x"}).status_code == 400
    r = env.client.put("/api/admin/mail/mailboxes/info@garajtek.com/quota", json={"quota": "2G"})
    assert r.status_code == 200
    assert env.calls[0]["cmd"][3:] == ["quota", "--json", "--", "info@garajtek.com", "2G"]


def test_use_for_site_mail_points_settings_to_local_server(env):
    env.queue.extend([
        ok({"ok": True, "domain": "garajtek.com"}),
        ok({"ok": True, "mailboxes": [{"address": "noreply@garajtek.com"}]}),
        ok({"ok": True, "address": "noreply@garajtek.com", "password": "Yeni-noreply-pw-1"}),
    ])
    r = env.client.post("/api/admin/mail/use-for-site-mail")
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "noreply@garajtek.com"
    assert "password" not in r.json()
    assert env.calls[2]["cmd"][3:] == ["passwd", "--json", "--random", "--", "noreply@garajtek.com"]
    writes = [c.args for c in env.db.settings.update_one.await_args_list]
    prev = [w for w in writes if w[0] == {"id": "email_smtp_previous"}]
    assert prev and prev[0][1]["$set"]["host"] == "api.zeptomail.eu"
    smtp = [w for w in writes if w[0] == {"id": "email_smtp"}][0][1]["$set"]
    assert smtp["host"] == "127.0.0.1" and smtp["port"] == 587 and smtp["transport"] == "smtp"
    assert smtp["username"] == "noreply@garajtek.com" and smtp["password"]


def test_email_smtp_transport_selection():
    sys.path.insert(0, str(ROOT))
    import email_smtp
    assert email_smtp._use_smtp({"host": "127.0.0.1"})
    assert email_smtp._use_smtp({"host": "api.zeptomail.eu", "transport": "smtp"})
    assert not email_smtp._use_smtp({"host": "api.zeptomail.eu"})
    assert not email_smtp._use_smtp({"host": "smtp.zoho.eu"})
