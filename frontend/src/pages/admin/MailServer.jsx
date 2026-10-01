/**
 * MailServer.jsx — Mail Yönetimi (kendi mail sunucumuz: Postfix + Dovecot + OpenDKIM + Roundcube)
 * Backend: /api/admin/mail/* (routes/mail_admin.py) → sudo garajtek-mail CLI (deploy/mail)
 */
import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  AlertTriangle, CheckCircle2, Copy, ExternalLink, Forward, Globe, HardDrive, Inbox, KeyRound,
  ListOrdered, Mail, Plus, RefreshCw, Send, Server, ShieldCheck, Trash2, XCircle,
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api/admin/mail`;
const auth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

const TABS = [
  { key: "genel", label: "Genel Durum", icon: Server },
  { key: "kutular", label: "Posta Kutuları", icon: Inbox },
  { key: "yonlendirmeler", label: "Yönlendirmeler", icon: Forward },
  { key: "dns", label: "DNS & Teslim Edilebilirlik", icon: Globe },
  { key: "kuyruk", label: "Kuyruk", icon: ListOrdered },
];

const QUOTAS = [
  { v: "500M", l: "500 MB" }, { v: "1G", l: "1 GB" }, { v: "2G", l: "2 GB" },
  { v: "5G", l: "5 GB" }, { v: "10G", l: "10 GB" }, { v: "0", l: "Sınırsız" },
];

export const fmtBytes = (n) => {
  if (n === null || n === undefined || Number.isNaN(Number(n))) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let v = Number(n); let i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${u[i]}`;
};

const fmtDate = (iso) => { try { return iso ? new Date(iso).toLocaleString("tr-TR") : "—"; } catch { return iso; } };
const errText = (e, fb = "İşlem başarısız") => {
  const d = e?.response?.data;
  return (d && (d.detail || d.message || d.error)) || e?.message || fb;
};

async function copyText(text) {
  try {
    if (navigator?.clipboard?.writeText) { await navigator.clipboard.writeText(text); }
    else {
      const ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); ta.remove();
    }
    toast.success("Kopyalandı");
  } catch { toast.error("Kopyalanamadı"); }
}

const CopyBtn = ({ text, testid, label }) => (
  <button type="button" data-testid={testid} onClick={() => copyText(text)}
    className="inline-flex items-center gap-1 px-2 py-1 text-xs border rounded-md hover:bg-gray-50 shrink-0">
    <Copy className="w-3.5 h-3.5" /> {label || "Kopyala"}
  </button>
);

const Badge = ({ ok, warn, children, testid }) => {
  const cls = ok ? "bg-emerald-50 text-emerald-800 border-emerald-200"
    : warn ? "bg-amber-50 text-amber-800 border-amber-200"
      : "bg-red-50 text-red-800 border-red-200";
  return <span data-testid={testid} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${cls}`}>{children}</span>;
};

const Modal = ({ open, title, onClose, children, testid }) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" data-testid={testid}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md">
        <div className="flex items-center justify-between px-5 py-3 border-b">
          <h3 className="font-semibold text-gray-900">{title}</h3>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-700" aria-label="Kapat"><XCircle className="w-5 h-5" /></button>
        </div>
        <div className="p-5 space-y-4">{children}</div>
      </div>
    </div>
  );
};

const UsageBar = ({ used, total }) => {
  if (!total) return <div className="text-xs text-gray-500">{fmtBytes(used)} · sınırsız</div>;
  const pct = Math.min(100, Math.round((Number(used || 0) / total) * 100));
  const tone = pct >= 90 ? "bg-red-500" : pct >= 75 ? "bg-amber-500" : "bg-emerald-500";
  return (
    <div className="min-w-[140px]">
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden"><div className={`h-full ${tone}`} style={{ width: `${pct}%` }} /></div>
      <div className="text-[11px] text-gray-500 mt-1">{fmtBytes(used)} / {fmtBytes(total)} (%{pct})</div>
    </div>
  );
};

const Card = ({ title, icon: Icon, children, right }) => (
  <div className="bg-white border rounded-xl p-5 shadow-sm">
    <div className="flex items-center justify-between mb-3 gap-2">
      <h2 className="font-semibold text-gray-900 flex items-center gap-2">{Icon ? <Icon className="w-4 h-4 text-gray-500" /> : null}{title}</h2>
      {right}
    </div>
    {children}
  </div>
);

// ───────────────────────────── Genel Durum ─────────────────────────────
function OverviewTab({ status, onSiteMail, siteMailBusy }) {
  if (!status) return <div className="p-10 text-center text-gray-400">Yükleniyor…</div>;
  const services = status.services || {};
  const ports = status.ports || {};
  const cert = status.certificate || {};
  const disk = status.disk || {};
  const host = status.host || "mail.garajtek.com";
  const webmail = status.webmail_url || `https://${host}`;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="border rounded-lg p-4 bg-white"><div className="text-xs text-gray-500">Posta kutusu</div><div className="text-2xl font-light mt-1" data-testid="mail-mailbox-count">{status.mailbox_count ?? "—"}</div></div>
        <div className={`border rounded-lg p-4 ${status.queue_count > 0 ? "bg-amber-50 border-amber-200" : "bg-white"}`}><div className="text-xs text-gray-500">Kuyruktaki mesaj</div><div className="text-2xl font-light mt-1" data-testid="mail-queue-count">{status.queue_count ?? 0}</div></div>
        <div className={`border rounded-lg p-4 ${cert.days_left !== null && cert.days_left < 14 ? "bg-red-50 border-red-200" : "bg-white"}`}>
          <div className="text-xs text-gray-500">TLS sertifikası</div>
          <div className="text-2xl font-light mt-1" data-testid="mail-cert-days">{cert.days_left ?? "—"} <span className="text-sm">gün</span></div>
          <div className="text-[11px] text-gray-500">{cert.not_after ? `Bitiş: ${fmtDate(cert.not_after)}` : "Sertifika bulunamadı"}</div>
        </div>
        <div className="border rounded-lg p-4 bg-white"><div className="text-xs text-gray-500">Posta verisi</div><div className="text-2xl font-light mt-1">{fmtBytes(disk.vhosts_bytes)}</div><div className="text-[11px] text-gray-500">Disk boş: {fmtBytes(disk.free_bytes)}</div></div>
      </div>

      <Card title="Servisler" icon={Server}>
        <div className="flex flex-wrap gap-2" data-testid="mail-services">
          {Object.entries(services).map(([name, st]) => (
            <Badge key={name} ok={st === "active"} warn={st === "inactive" && name === "fail2ban"}>
              {st === "active" ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />} {name}: {st}
            </Badge>
          ))}
        </div>
        <div className="mt-4 text-xs text-gray-500 mb-1">Dinlenen portlar</div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(ports).map(([p, open]) => <Badge key={p} ok={open}>{p}</Badge>)}
        </div>
        <div className="mt-3 text-xs text-gray-500">
          Giden posta: {status.relayhost ? <b>relay üzerinden ({status.relayhost})</b> : <b>doğrudan (port 25)</b>}
          {status.memory?.MemAvailable ? <> · Boş RAM: {fmtBytes(status.memory.MemAvailable)} / {fmtBytes(status.memory.MemTotal)}</> : null}
        </div>
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        <Card title="Webmail" icon={Mail} right={<a href={webmail} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-sm px-3 py-1.5 bg-gray-900 text-white rounded-lg" data-testid="mail-webmail-link">Webmail'e Git <ExternalLink className="w-3.5 h-3.5" /></a>}>
          <p className="text-sm text-gray-600">Roundcube: <a className="underline" href={webmail} target="_blank" rel="noreferrer">{webmail}</a>. Kullanıcı adı tam adres (ör. info@{status.domain || "garajtek.com"}) ya da yalnızca "info".</p>
        </Card>
        <Card title="Outlook / Telefon ayarları" icon={KeyRound}>
          <table className="text-sm w-full" data-testid="mail-client-settings">
            <tbody>
              <tr><td className="py-1 text-gray-500 pr-3">Gelen (IMAP)</td><td className="font-mono">{host} · 993 · SSL/TLS</td></tr>
              <tr><td className="py-1 text-gray-500 pr-3">Giden (SMTP)</td><td className="font-mono">{host} · 465 · SSL/TLS</td></tr>
              <tr><td className="py-1 text-gray-500 pr-3">alternatif</td><td className="font-mono">{host} · 587 · STARTTLS</td></tr>
              <tr><td className="py-1 text-gray-500 pr-3">Kullanıcı adı</td><td>tam e-posta adresi</td></tr>
              <tr><td className="py-1 text-gray-500 pr-3">Kimlik doğrulama</td><td>normal şifre (giden sunucu da kimlik doğrulama ister)</td></tr>
            </tbody>
          </table>
        </Card>
      </div>

      <Card title="Site bildirimleri (sipariş, üyelik, şifre)" icon={Send}>
        <p className="text-sm text-gray-600 mb-3">
          Sitenin işlemsel e-postalarını ZeptoMail yerine bu sunucudan <b>noreply@{status.domain || "garajtek.com"}</b> ile göndermek için butona basın.
          noreply şifresi yenilenir ve Ayarlar › E-posta yapılandırması <span className="font-mono">127.0.0.1:587 STARTTLS</span> olarak güncellenir (önceki ayar yedeklenir).
          Önce DNS sekmesindeki kontrollerin (SPF/DKIM/DMARC/PTR) geçtiğinden emin olun.
        </p>
        <button type="button" onClick={onSiteMail} disabled={siteMailBusy} data-testid="mail-site-mail-btn"
          className="inline-flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-semibold disabled:opacity-50">
          <Send className="w-4 h-4" /> {siteMailBusy ? "Ayarlanıyor…" : "Site bildirimlerini bu sunucudan gönder"}
        </button>
      </Card>
    </div>
  );
}

// ───────────────────────────── Posta Kutuları ─────────────────────────────
function MailboxesTab({ domain, onChanged }) {
  const [items, setItems] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState({ local: "", mode: "random", password: "", quota: "1G" });
  const [busy, setBusy] = useState(false);
  const [secret, setSecret] = useState(null); // {address, password}
  const [toDelete, setToDelete] = useState(null);
  const [purge, setPurge] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${API}/mailboxes`, auth());
      setItems(r.data?.mailboxes || []);
    } catch (e) { setItems([]); toast.error(errText(e, "Posta kutuları alınamadı")); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    const local = form.local.trim().toLowerCase();
    if (!/^[a-z0-9](?:[a-z0-9._-]{0,62}[a-z0-9])?$/.test(local)) { toast.error("Geçersiz kullanıcı adı (harf, rakam, . _ -)"); return; }
    if (form.mode === "manual" && form.password.length < 10) { toast.error("Şifre en az 10 karakter olmalı"); return; }
    setBusy(true);
    try {
      const body = { email: `${local}@${domain}`, quota: form.quota, random: form.mode === "random" };
      if (form.mode === "manual") body.password = form.password;
      const r = await axios.post(`${API}/mailboxes`, body, auth());
      toast.success(`${body.email} oluşturuldu`);
      setAddOpen(false);
      setForm({ local: "", mode: "random", password: "", quota: "1G" });
      if (r.data?.password) setSecret({ address: body.email, password: r.data.password });
      load(); onChanged?.();
    } catch (e) { toast.error(errText(e)); } finally { setBusy(false); }
  };

  const resetPassword = async (address) => {
    if (!window.confirm(`${address} için yeni rastgele şifre üretilsin mi? Eski şifre hemen geçersiz olur.`)) return;
    try {
      const r = await axios.post(`${API}/mailboxes/${encodeURIComponent(address)}/password`, { random: true }, auth());
      setSecret({ address, password: r.data?.password });
    } catch (e) { toast.error(errText(e)); }
  };

  const changeQuota = async (address, quota) => {
    try {
      await axios.put(`${API}/mailboxes/${encodeURIComponent(address)}/quota`, { quota }, auth());
      toast.success("Kota güncellendi"); load();
    } catch (e) { toast.error(errText(e)); }
  };

  const doDelete = async () => {
    if (!toDelete) return;
    setBusy(true);
    try {
      await axios.delete(`${API}/mailboxes/${encodeURIComponent(toDelete)}?purge=${purge ? "true" : "false"}`, auth());
      toast.success(`${toDelete} silindi`);
      setToDelete(null); setPurge(false); load(); onChanged?.();
    } catch (e) { toast.error(errText(e)); } finally { setBusy(false); }
  };

  return (
    <Card title="Posta Kutuları" icon={Inbox} right={
      <button type="button" data-testid="mail-add-mailbox-btn" onClick={() => setAddOpen(true)}
        className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-900 text-white rounded-lg text-sm"><Plus className="w-4 h-4" /> Yeni Posta Kutusu</button>}>
      {items === null ? <div className="p-6 text-center text-gray-400">Yükleniyor…</div> : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="mail-mailbox-table">
            <thead><tr className="text-left text-xs text-gray-500 border-b"><th className="py-2">Adres</th><th>Kullanım</th><th>Kota</th><th>Oluşturma</th><th className="text-right">İşlemler</th></tr></thead>
            <tbody>
              {items.length === 0 && <tr><td colSpan={5} className="py-6 text-center text-gray-400">Henüz posta kutusu yok</td></tr>}
              {items.map((m) => (
                <tr key={m.address} className="border-b last:border-0">
                  <td className="py-2 font-medium">{m.address}</td>
                  <td><UsageBar used={m.usage_bytes} total={m.quota_bytes} /></td>
                  <td>
                    <select aria-label="Kota" value={QUOTAS.some((q) => q.v === m.quota) ? m.quota : ""} onChange={(e) => changeQuota(m.address, e.target.value)}
                      className="border rounded-md px-2 py-1 text-xs">
                      {!QUOTAS.some((q) => q.v === m.quota) && <option value="">{m.quota}</option>}
                      {QUOTAS.map((q) => <option key={q.v} value={q.v}>{q.l}</option>)}
                    </select>
                  </td>
                  <td className="text-xs text-gray-500">{fmtDate(m.created)}</td>
                  <td className="text-right whitespace-nowrap">
                    <button type="button" onClick={() => resetPassword(m.address)} data-testid={`mail-reset-${m.address}`}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs border rounded-md hover:bg-gray-50 mr-1"><KeyRound className="w-3.5 h-3.5" /> Şifre sıfırla</button>
                    <button type="button" onClick={() => { setToDelete(m.address); setPurge(false); }} data-testid={`mail-delete-${m.address}`}
                      className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-red-200 text-red-700 rounded-md hover:bg-red-50"><Trash2 className="w-3.5 h-3.5" /> Sil</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={addOpen} title="Yeni Posta Kutusu" onClose={() => setAddOpen(false)} testid="mail-add-dialog">
        <div>
          <label className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Adres</label>
          <div className="flex items-center border rounded-lg overflow-hidden">
            <input className="flex-1 px-3 py-2 text-sm outline-none" placeholder="satis" value={form.local}
              data-testid="mail-add-local" onChange={(e) => setForm({ ...form, local: e.target.value })} />
            <span className="px-3 py-2 bg-gray-50 text-sm text-gray-500 border-l">@{domain}</span>
          </div>
        </div>
        <div>
          <label className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Şifre</label>
          <div className="flex gap-4 text-sm">
            <label className="flex items-center gap-1"><input type="radio" checked={form.mode === "random"} onChange={() => setForm({ ...form, mode: "random" })} /> Rastgele üret</label>
            <label className="flex items-center gap-1"><input type="radio" checked={form.mode === "manual"} onChange={() => setForm({ ...form, mode: "manual" })} /> Kendim belirleyeceğim</label>
          </div>
          {form.mode === "manual" && (
            <input type="password" autoComplete="new-password" className="mt-2 w-full border rounded-lg px-3 py-2 text-sm" placeholder="en az 10 karakter"
              value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          )}
        </div>
        <div>
          <label className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Kota</label>
          <select className="border rounded-lg px-3 py-2 text-sm w-full" value={form.quota} onChange={(e) => setForm({ ...form, quota: e.target.value })}>
            {QUOTAS.map((q) => <option key={q.v} value={q.v}>{q.l}</option>)}
          </select>
        </div>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => setAddOpen(false)} className="px-3 py-2 text-sm border rounded-lg">Vazgeç</button>
          <button type="button" onClick={create} disabled={busy} data-testid="mail-add-submit" className="px-3 py-2 text-sm bg-gray-900 text-white rounded-lg disabled:opacity-50">{busy ? "Oluşturuluyor…" : "Oluştur"}</button>
        </div>
      </Modal>

      <Modal open={!!secret} title="Tek seferlik şifre" onClose={() => setSecret(null)} testid="mail-secret-dialog">
        <p className="text-sm text-gray-600"><b>{secret?.address}</b> için şifre aşağıdadır. Bu pencere kapandıktan sonra <b>tekrar gösterilmez</b>; şimdi kopyalayıp güvenli bir yere kaydedin.</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 bg-gray-50 border rounded-lg px-3 py-2 font-mono text-sm break-all" data-testid="mail-secret-value">{secret?.password}</code>
          <CopyBtn text={secret?.password || ""} testid="mail-secret-copy" />
        </div>
        <div className="flex justify-end"><button type="button" onClick={() => setSecret(null)} className="px-3 py-2 text-sm bg-gray-900 text-white rounded-lg">Kaydettim, kapat</button></div>
      </Modal>

      <Modal open={!!toDelete} title="Posta kutusunu sil" onClose={() => setToDelete(null)} testid="mail-delete-dialog">
        <p className="text-sm text-gray-700"><b>{toDelete}</b> silinsin mi? Bu adrese gelen postalar artık reddedilir.</p>
        <label className="flex items-center gap-2 text-sm text-red-700">
          <input type="checkbox" checked={purge} onChange={(e) => setPurge(e.target.checked)} data-testid="mail-delete-purge" />
          Tüm e-postaları da kalıcı olarak sil (geri alınamaz)
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={() => setToDelete(null)} className="px-3 py-2 text-sm border rounded-lg">Vazgeç</button>
          <button type="button" onClick={doDelete} disabled={busy} data-testid="mail-delete-confirm" className="px-3 py-2 text-sm bg-red-600 text-white rounded-lg disabled:opacity-50">Sil</button>
        </div>
      </Modal>
    </Card>
  );
}

// ───────────────────────────── Yönlendirmeler ─────────────────────────────
function AliasesTab({ domain }) {
  const [items, setItems] = useState(null);
  const [src, setSrc] = useState("");
  const [dst, setDst] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/aliases`, auth()); setItems(r.data?.aliases || []); }
    catch (e) { setItems([]); toast.error(errText(e, "Yönlendirmeler alınamadı")); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    const local = src.trim().toLowerCase();
    if (!local || !dst.trim()) { toast.error("Kaynak ve hedef gerekli"); return; }
    setBusy(true);
    try {
      await axios.post(`${API}/aliases`, { source: `${local}@${domain}`, destination: dst.trim() }, auth());
      toast.success("Yönlendirme kaydedildi"); setSrc(""); setDst(""); load();
    } catch (e) { toast.error(errText(e)); } finally { setBusy(false); }
  };
  const del = async (source) => {
    if (!window.confirm(`${source} yönlendirmesi silinsin mi?`)) return;
    try { await axios.delete(`${API}/aliases/${encodeURIComponent(source)}`, auth()); toast.success("Silindi"); load(); }
    catch (e) { toast.error(errText(e)); }
  };

  return (
    <Card title="Yönlendirmeler (alias / forward)" icon={Forward}>
      <p className="text-sm text-gray-600 mb-3">Posta kutusu olmayan bir adrese gelen postaları başka adres(ler)e iletir. Ör. <span className="font-mono">siparis@{domain} → info@{domain}, ortak@gmail.com</span></p>
      <div className="flex flex-col md:flex-row gap-2 mb-4">
        <div className="flex items-center border rounded-lg overflow-hidden md:w-64">
          <input className="flex-1 px-3 py-2 text-sm outline-none min-w-0" placeholder="siparis" value={src} onChange={(e) => setSrc(e.target.value)} data-testid="mail-alias-source" />
          <span className="px-2 py-2 bg-gray-50 text-xs text-gray-500 border-l">@{domain}</span>
        </div>
        <input className="flex-1 border rounded-lg px-3 py-2 text-sm" placeholder="hedef@ornek.com, ikinci@ornek.com" value={dst} onChange={(e) => setDst(e.target.value)} data-testid="mail-alias-dest" />
        <button type="button" onClick={add} disabled={busy} data-testid="mail-alias-add" className="inline-flex items-center gap-1 px-3 py-2 bg-gray-900 text-white rounded-lg text-sm disabled:opacity-50"><Plus className="w-4 h-4" /> Ekle</button>
      </div>
      {items === null ? <div className="text-gray-400 text-sm">Yükleniyor…</div> : (
        <table className="w-full text-sm" data-testid="mail-alias-table">
          <tbody>
            {items.length === 0 && <tr><td className="py-4 text-center text-gray-400">Yönlendirme yok</td></tr>}
            {items.map((a) => (
              <tr key={a.source} className="border-b last:border-0">
                <td className="py-2 font-medium">{a.source}</td>
                <td className="text-gray-600">→ {(a.destinations || []).join(", ")}</td>
                <td className="text-right"><button type="button" onClick={() => del(a.source)} className="inline-flex items-center gap-1 px-2 py-1 text-xs border border-red-200 text-red-700 rounded-md"><Trash2 className="w-3.5 h-3.5" /> Sil</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// ───────────────────────────── DNS ─────────────────────────────
const recordText = (exp) => {
  if (!exp) return "";
  if (exp.type === "MX") return `${exp.value}`;
  return exp.value || "";
};

function DnsTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const run = useCallback(async () => {
    setLoading(true);
    try { const r = await axios.get(`${API}/dns-check`, { ...auth(), timeout: 120000 }); setData(r.data); }
    catch (e) { toast.error(errText(e, "DNS kontrolü yapılamadı")); } finally { setLoading(false); }
  }, []);
  useEffect(() => { run(); }, [run]);

  return (
    <div className="space-y-4">
      <Card title="DNS & Teslim Edilebilirlik" icon={ShieldCheck} right={
        <button type="button" onClick={run} disabled={loading} data-testid="mail-dns-run" className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg text-sm"><RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Yeniden kontrol et</button>}>
        {!data ? <div className="text-gray-400 text-sm">{loading ? "Kontrol ediliyor (DNS sorguları ~10 sn)…" : "—"}</div> : (
          <div className="space-y-2" data-testid="mail-dns-checks">
            {data.all_pass && <div className="p-3 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-800 text-sm">Tüm kontroller geçti — teslim edilebilirlik için temel ayarlar tamam.</div>}
            {(data.checks || []).map((c) => (
              <div key={c.key} className="border rounded-lg p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="font-medium text-sm">{c.label}</div>
                  <Badge ok={c.status === "pass"} warn={c.status === "warn"} testid={`mail-dns-${c.key}`}>{c.status === "pass" ? "PASS" : c.status === "warn" ? "UYARI" : "FAIL"}</Badge>
                </div>
                {c.message ? <div className="text-xs text-gray-600 mt-1">{c.message}</div> : null}
                {(c.found || []).length > 0 && <div className="text-[11px] text-gray-500 mt-1 font-mono break-all">Bulunan: {(c.found || []).join(" | ").slice(0, 300)}</div>}
                {c.expected && c.status !== "pass" && (
                  <div className="mt-2 bg-gray-50 border rounded-md p-2 text-xs">
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-gray-600">
                      <span>Tür: <b>{c.expected.type}</b></span>
                      <span>Ad: <b className="font-mono">{c.expected.name}</b></span>
                      {c.expected.priority ? <span>Öncelik: <b>{c.expected.priority}</b></span> : null}
                    </div>
                    <div className="flex items-start gap-2 mt-1">
                      <code className="flex-1 font-mono break-all">{recordText(c.expected)}</code>
                      <CopyBtn text={recordText(c.expected)} testid={`mail-dns-copy-${c.key}`} />
                    </div>
                    {c.expected.note ? <div className="text-amber-700 mt-1">{c.expected.note}</div> : null}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
      <Card title="İpuçları" icon={AlertTriangle}>
        <ul className="text-sm text-gray-600 list-disc pl-5 space-y-1">
          <li>Cloudflare'de <b>mail</b> A kaydı mutlaka <b>DNS only (gri bulut)</b> olmalı; turuncu bulut SMTP/IMAP'i keser.</li>
          <li>PTR (rDNS) DNS sağlayıcıda değil, <b>SNET müşteri panelinde</b> IP için <span className="font-mono">mail.garajtek.com</span> olarak ayarlanır.</li>
          <li>Tek bir SPF kaydı olmalı; birden fazla <span className="font-mono">v=spf1</span> kaydı SPF'yi bozar.</li>
          <li>Kara liste kontrolü: <a className="underline" href="https://mxtoolbox.com/blacklists.aspx" target="_blank" rel="noreferrer">mxtoolbox.com/blacklists</a> · Puan testi: <a className="underline" href="https://www.mail-tester.com" target="_blank" rel="noreferrer">mail-tester.com</a> (10/10 hedefleyin).</li>
          <li>Yeni IP'de <b>ısınma</b>: ilk 2-3 hafta günde az sayıda (≈50-100) gerçek mail gönderin; toplu pazarlama mailini bu sunucudan değil Brevo/SES üzerinden yapın.</li>
          <li>Birkaç hafta sorunsuz geçtikten sonra DMARC'ı <span className="font-mono">p=quarantine</span> seviyesine yükseltin.</li>
        </ul>
      </Card>
    </div>
  );
}

// ───────────────────────────── Kuyruk ─────────────────────────────
function QueueTab() {
  const [data, setData] = useState(null);
  const [to, setTo] = useState("");
  const [busy, setBusy] = useState(false);
  const [p25, setP25] = useState(null);

  const load = useCallback(async () => {
    try { const r = await axios.get(`${API}/queue`, auth()); setData(r.data); }
    catch (e) { setData({ items: [] }); toast.error(errText(e, "Kuyruk alınamadı")); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const flush = async () => {
    setBusy(true);
    try { await axios.post(`${API}/queue/flush`, {}, auth()); toast.success("Kuyruk yeniden deneniyor"); setTimeout(load, 1500); }
    catch (e) { toast.error(errText(e)); } finally { setBusy(false); }
  };
  const remove = async (id) => {
    if (!window.confirm(`${id === "ALL" ? "Kuyruktaki TÜM mesajlar" : id} silinsin mi?`)) return;
    try { await axios.delete(`${API}/queue/${encodeURIComponent(id)}`, auth()); toast.success("Silindi"); load(); }
    catch (e) { toast.error(errText(e)); }
  };
  const send = async () => {
    if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(to.trim())) { toast.error("Geçerli bir alıcı adresi girin"); return; }
    setBusy(true);
    try { await axios.post(`${API}/test-send`, { to: to.trim() }, auth()); toast.success("Test e-postası kuyruğa alındı"); setTimeout(load, 1500); }
    catch (e) { toast.error(errText(e)); } finally { setBusy(false); }
  };
  const check25 = async () => {
    try { const r = await axios.get(`${API}/port25-check`, auth()); setP25(r.data); }
    catch (e) { toast.error(errText(e)); }
  };

  const items = data?.items || [];
  return (
    <div className="space-y-4">
      <Card title="Test e-postası" icon={Send}>
        <div className="flex flex-col md:flex-row gap-2">
          <input className="flex-1 border rounded-lg px-3 py-2 text-sm" placeholder="adresiniz@gmail.com" value={to} onChange={(e) => setTo(e.target.value)} data-testid="mail-test-to" />
          <button type="button" onClick={send} disabled={busy} data-testid="mail-test-send" className="inline-flex items-center gap-1 px-3 py-2 bg-gray-900 text-white rounded-lg text-sm disabled:opacity-50"><Send className="w-4 h-4" /> Gönder</button>
          <button type="button" onClick={check25} className="inline-flex items-center gap-1 px-3 py-2 border rounded-lg text-sm" data-testid="mail-port25">Port 25 testi</button>
        </div>
        <p className="text-xs text-gray-500 mt-2">Gmail'de mesajı açın › ⋮ › <b>Orijinali göster</b>: SPF, DKIM ve DMARC satırları <b>PASS</b> olmalı.</p>
        {p25 && <div className="mt-2"><Badge ok={p25.open}>{p25.open ? "Giden 25 AÇIK" : "Giden 25 KAPALI"}</Badge> <span className="text-xs text-gray-600 ml-2">{p25.advice}</span></div>}
      </Card>
      <Card title={`Kuyruk (${items.length})`} icon={ListOrdered} right={
        <div className="flex gap-2">
          <button type="button" onClick={load} className="inline-flex items-center gap-1 px-3 py-1.5 border rounded-lg text-sm"><RefreshCw className="w-4 h-4" /> Yenile</button>
          <button type="button" onClick={flush} disabled={busy} data-testid="mail-queue-flush" className="inline-flex items-center gap-1 px-3 py-1.5 bg-gray-900 text-white rounded-lg text-sm disabled:opacity-50">Yeniden dene (flush)</button>
          {items.length > 0 && <button type="button" onClick={() => remove("ALL")} className="inline-flex items-center gap-1 px-3 py-1.5 border border-red-200 text-red-700 rounded-lg text-sm">Tümünü sil</button>}
        </div>}>
        {data === null ? <div className="text-gray-400 text-sm">Yükleniyor…</div> : items.length === 0 ? (
          <div className="text-sm text-emerald-700 flex items-center gap-1" data-testid="mail-queue-empty"><CheckCircle2 className="w-4 h-4" /> Kuyruk boş — bekleyen mesaj yok.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="mail-queue-table">
              <thead><tr className="text-left text-xs text-gray-500 border-b"><th className="py-2">ID</th><th>Zaman</th><th>Gönderen</th><th>Alıcı / Sebep</th><th>Boyut</th><th /></tr></thead>
              <tbody>
                {items.map((q) => (
                  <tr key={q.queue_id} className="border-b last:border-0 align-top">
                    <td className="py-2 font-mono text-xs">{q.queue_id}<div className="text-[10px] text-gray-400">{q.queue_name}</div></td>
                    <td className="text-xs">{fmtDate(q.arrival_time)}</td>
                    <td className="text-xs">{q.sender || "<>"}</td>
                    <td className="text-xs">{(q.recipients || []).map((r) => <div key={r.address}><b>{r.address}</b>{r.reason ? <div className="text-amber-700">{r.reason}</div> : null}</div>)}</td>
                    <td className="text-xs">{fmtBytes(q.size)}</td>
                    <td className="text-right"><button type="button" onClick={() => remove(q.queue_id)} className="text-red-600" aria-label="Sil"><Trash2 className="w-4 h-4" /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ───────────────────────────── Sayfa ─────────────────────────────
export default function MailServer() {
  const [tab, setTab] = useState("genel");
  const [status, setStatus] = useState(null);
  const [notInstalled, setNotInstalled] = useState(null); // mesaj
  const [loading, setLoading] = useState(false);
  const [siteMailBusy, setSiteMailBusy] = useState(false);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    try {
      const r = await axios.get(`${API}/status`, auth());
      setStatus(r.data); setNotInstalled(null);
    } catch (e) {
      const d = e?.response?.data;
      if (e?.response?.status === 503) setNotInstalled(d?.message || d?.detail || "Mail sunucusu kurulu değil — deploy/mail/README.md");
      else toast.error(errText(e, "Durum alınamadı"));
    } finally { setLoading(false); }
  }, []);
  useEffect(() => { loadStatus(); }, [loadStatus]);

  const enableSiteMail = async () => {
    if (!window.confirm("Site bildirim e-postaları bu sunucudan (noreply@) gönderilecek ve noreply şifresi yenilenecek. Devam edilsin mi?")) return;
    setSiteMailBusy(true);
    try {
      const r = await axios.post(`${API}/use-for-site-mail`, {}, auth());
      toast.success(`Site bildirimleri artık ${r.data?.username} ile ${r.data?.host}:${r.data?.port} üzerinden gönderiliyor`);
    } catch (e) { toast.error(errText(e)); } finally { setSiteMailBusy(false); }
  };

  const domain = status?.domain || "garajtek.com";

  return (
    <div data-testid="admin-mail-server" className="p-4 md:p-6 max-w-6xl">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div className="flex items-center gap-2">
          <Mail className="w-6 h-6 text-gray-600" />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Mail Yönetimi</h1>
            <p className="text-sm text-gray-500">{status?.host || `mail.${domain}`} — Postfix · Dovecot · OpenDKIM · Roundcube</p>
          </div>
        </div>
        <button type="button" onClick={loadStatus} disabled={loading} className="inline-flex items-center gap-1 px-3 py-2 border rounded-lg text-sm" data-testid="mail-refresh">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Yenile
        </button>
      </div>

      {notInstalled ? (
        <div className="border border-amber-200 bg-amber-50 rounded-xl p-5" data-testid="mail-not-installed">
          <div className="flex items-center gap-2 font-semibold text-amber-900"><HardDrive className="w-5 h-5" /> {notInstalled}</div>
          <p className="text-sm text-amber-900 mt-2">Sunucuda (root) şu komutla kurun, ardından bu sayfayı yenileyin:</p>
          <pre className="mt-2 bg-white border rounded-lg p-3 text-xs overflow-x-auto">sudo bash /opt/garajtek/deploy/mail/mail-kur.sh garajtek.com mail.garajtek.com</pre>
          <p className="text-xs text-amber-800 mt-2">Ayrıntılar: deploy/mail/README.md (port 25, PTR, DNS kayıtları, relay seçeneği).</p>
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-1 border-b mb-4" role="tablist">
            {TABS.map((t) => {
              const Icon = t.icon;
              const active = tab === t.key;
              return (
                <button key={t.key} type="button" role="tab" aria-selected={active} data-testid={`mail-tab-${t.key}`}
                  onClick={() => setTab(t.key)}
                  className={`inline-flex items-center gap-1.5 px-3 py-2 text-sm border-b-2 -mb-px ${active ? "border-gray-900 text-gray-900 font-semibold" : "border-transparent text-gray-500 hover:text-gray-800"}`}>
                  <Icon className="w-4 h-4" /> {t.label}
                </button>
              );
            })}
          </div>
          {tab === "genel" && <OverviewTab status={status} onSiteMail={enableSiteMail} siteMailBusy={siteMailBusy} />}
          {tab === "kutular" && <MailboxesTab domain={domain} onChanged={loadStatus} />}
          {tab === "yonlendirmeler" && <AliasesTab domain={domain} />}
          {tab === "dns" && <DnsTab />}
          {tab === "kuyruk" && <QueueTab />}
        </>
      )}
    </div>
  );
}
