// BirFatura e-Fatura / e-Arşiv entegrasyonu — panel sayfası.
// BirFatura siparişleri bu siteden ÇEKER (token'lı uçlar), faturayı keser ve fatura
// bağlantısını geri gönderir. Bu sayfa: aç/kapat, token, panele girilecek adresler,
// durum eşlemesi, fatura ayarları, bağlantı testi ve son çağrı kayıtları.
import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Copy, KeyRound, RefreshCw, PlayCircle, Plus, Trash2, Check, X, FileText } from "lucide-react";
import { nextGroupId, validateStatusGroups, toggleStatus, parseHosts } from "../../lib/birfatura";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE = `${API}/integrations/birfatura`;
const auth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success("Kopyalandı");
  } catch {
    toast.error("Kopyalanamadı — elle seçip kopyalayın");
  }
}

function CopyRow({ label, value, testId }) {
  return (
    <div className="flex items-center gap-2 py-1.5">
      <div className="w-44 shrink-0 text-xs font-semibold text-gray-500">{label}</div>
      <code className="flex-1 min-w-0 truncate text-xs bg-gray-50 border rounded px-2 py-1" data-testid={testId}>{value || "-"}</code>
      <button type="button" onClick={() => copy(value)} disabled={!value}
        className="p-1.5 rounded border hover:bg-gray-50 disabled:opacity-40" title="Kopyala">
        <Copy size={14} />
      </button>
    </div>
  );
}

const Section = ({ title, children, right }) => (
  <div className="bg-white border rounded-xl p-5 shadow-sm mb-5">
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-sm font-bold text-gray-700 uppercase tracking-wide">{title}</h2>
      {right}
    </div>
    {children}
  </div>
);

const fmtDate = (s) => {
  if (!s) return "-";
  try { return new Date(s).toLocaleString("tr-TR"); } catch { return s; }
};

export default function BirFatura() {
  const [s, setS] = useState(null);
  const [form, setForm] = useState(null);
  const [saving, setSaving] = useState(false);
  const [newToken, setNewToken] = useState("");
  const [logs, setLogs] = useState([]);
  const [test, setTest] = useState(null);
  const [testing, setTesting] = useState(false);
  const [testGroup, setTestGroup] = useState("");
  const [testDays, setTestDays] = useState(7);

  const load = useCallback(async () => {
    try {
      const r = await axios.get(`${BASE}/settings`, auth());
      setS(r.data);
      setForm({
        ...r.data,
        trusted_hosts_text: (r.data.trusted_invoice_hosts || []).join("\n"),
        default_vat_rate: r.data.default_vat_rate ?? "",
      });
    } catch (e) {
      toast.error(e.response?.data?.detail || "BirFatura ayarları yüklenemedi");
    }
  }, []);

  const loadLogs = useCallback(async () => {
    try {
      const r = await axios.get(`${BASE}/logs?limit=50`, auth());
      setLogs(r.data?.logs || []);
    } catch { /* yetkisizse sessiz */ }
  }, []);

  useEffect(() => { load(); loadLogs(); }, [load, loadLogs]);

  const save = async (patch = {}) => {
    const body = {
      enabled: form.enabled,
      status_groups: form.status_groups,
      date_field: form.date_field,
      discount_mode: form.discount_mode,
      default_vat_rate: form.default_vat_rate === "" ? null : Number(form.default_vat_rate),
      shipping_vat_rate: Number(form.shipping_vat_rate),
      service_vat_rate: Number(form.service_vat_rate),
      default_tckn: form.default_tckn,
      only_site_orders: form.only_site_orders,
      skip_invoiced_elsewhere: form.skip_invoiced_elsewhere,
      store_cargo_updates: form.store_cargo_updates,
      max_window_days: Number(form.max_window_days),
      trusted_invoice_hosts: parseHosts(form.trusted_hosts_text),
      invoice_explanation: form.invoice_explanation,
      ...patch,
    };
    const errs = validateStatusGroups(body.status_groups);
    if (errs.length) { toast.error(errs[0]); return; }
    try {
      setSaving(true);
      await axios.put(`${BASE}/settings`, body, auth());
      toast.success("BirFatura ayarları kaydedildi");
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  const regenerate = async () => {
    const msg = s?.has_token
      ? "Yeni token üretilecek; ESKİ token hemen geçersiz olur ve BirFatura panelindeki API şifresini güncellemeniz gerekir. Devam edilsin mi?"
      : "BirFatura için yeni bir token üretilsin mi?";
    const ok = (await window.appConfirm?.(msg)) ?? window.confirm(msg);
    if (!ok) return;
    try {
      const r = await axios.post(`${BASE}/token`, {}, auth());
      setNewToken(r.data.token);
      toast.success("Token oluşturuldu — şimdi kopyalayın, tekrar gösterilmez");
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Token üretilemedi");
    }
  };

  const runTest = async () => {
    try {
      setTesting(true);
      const r = await axios.post(`${BASE}/test`, { days: Number(testDays) || 7, status_id: testGroup ? Number(testGroup) : undefined }, auth());
      setTest(r.data);
      loadLogs();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Test çalıştırılamadı");
    } finally {
      setTesting(false);
    }
  };

  if (!form) return <div className="p-6 text-sm text-gray-500">Yükleniyor…</div>;

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setGroup = (i, g) => setForm((f) => ({ ...f, status_groups: f.status_groups.map((x, j) => (j === i ? g : x)) }));
  const catalog = s.status_catalog || [];
  const urls = s.urls || {};

  return (
    <div className="max-w-5xl" data-testid="admin-birfatura">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">BirFatura · e-Fatura / e-Arşiv</h1>
        <p className="text-sm text-gray-500 mt-1">
          BirFatura siparişleri bu siteden otomatik çeker, e-Fatura mükellefi müşteriye e-Fatura, diğerlerine
          e-Arşiv keser ve fatura bağlantısını siparişe geri yazar. Fatura, sipariş detayında ve müşterinin
          hesabındaki siparişte görünür.
        </p>
      </div>

      <Section title="Durum">
        <div className="flex flex-wrap items-center gap-4">
          <label className="inline-flex items-center gap-2 text-sm font-semibold">
            <input type="checkbox" checked={!!form.enabled} data-testid="bf-enabled"
              onChange={(e) => save({ enabled: e.target.checked })} disabled={saving || (!s.has_token && !form.enabled)} />
            Entegrasyon {form.enabled ? <span className="text-green-700">açık</span> : <span className="text-gray-500">kapalı</span>}
          </label>
          {!s.has_token && <span className="text-xs text-amber-700">Açmak için önce token oluşturun.</span>}
          <span className="text-xs text-gray-500">Son BirFatura çağrısı: <b>{fmtDate(s.last_call_at)}</b>{s.last_call_endpoint ? ` (${s.last_call_endpoint})` : ""}</span>
        </div>
        <p className="text-xs text-gray-500 mt-2">Kapalıyken BirFatura'nın çağırdığı uçlar 404 döner; hiçbir sipariş paylaşılmaz.</p>
      </Section>

      <Section title="Token (BirFatura'da “API Şifresi”)"
        right={
          <button onClick={regenerate} data-testid="bf-token-btn"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800">
            <KeyRound size={15} /> {s.has_token ? "Yeni token üret" : "Token oluştur"}
          </button>
        }>
        {s.has_token ? (
          <p className="text-sm text-gray-700">Kayıtlı token: <code>••••••••-{s.token_hint}</code> · oluşturma: {fmtDate(s.token_created_at)}</p>
        ) : (
          <p className="text-sm text-gray-500">Henüz token yok.</p>
        )}
        {newToken && (
          <div className="mt-3 border border-amber-300 bg-amber-50 rounded-lg p-3">
            <div className="text-xs font-semibold text-amber-800 mb-1">Yeni token — yalnız şimdi gösteriliyor. Kopyalayıp BirFatura paneline yapıştırın.</div>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-sm bg-white border rounded px-2 py-1 select-all" data-testid="bf-new-token">{newToken}</code>
              <button onClick={() => copy(newToken)} className="p-1.5 rounded border bg-white hover:bg-gray-50"><Copy size={14} /></button>
              <button onClick={() => setNewToken("")} className="p-1.5 rounded border bg-white hover:bg-gray-50" title="Gizle"><X size={14} /></button>
            </div>
          </div>
        )}
      </Section>

      <Section title="BirFatura paneline girilecek adresler">
        <p className="text-xs text-gray-500 mb-2">
          BirFatura → Mağazalar → Yeni mağaza → <b>Özel Entegrasyon (API)</b>. “Site adresi” alanına aşağıdaki
          site adresini, “API şifresi” alanına token'ı girin. Panel uçları ayrı ayrı istiyorsa tam adresleri kullanın.
        </p>
        <CopyRow label="Site adresi" value={urls.site_address} testId="bf-site-address" />
        <CopyRow label="Sipariş durumları" value={urls.order_status} />
        <CopyRow label="Ödeme yöntemleri" value={urls.payment_methods} />
        <CopyRow label="Siparişler" value={urls.orders} />
        <CopyRow label="Fatura bağlantısı (geri)" value={urls.invoice_link_update} />
        <CopyRow label="Kargo bilgisi (geri)" value={urls.order_cargo_update} />
        <p className="text-xs text-gray-500 mt-2">
          Ödeme yöntemleri: {(s.payment_methods || []).map((m) => `${m.Id} = ${m.Value}`).join(" · ")}
        </p>
      </Section>

      <Section title="Sipariş durumu eşlemesi"
        right={
          <button type="button" onClick={() => set("status_groups", [...form.status_groups, { id: nextGroupId(form.status_groups), name: "Yeni grup", statuses: [] }])}
            className="inline-flex items-center gap-1 text-sm text-blue-700 hover:text-blue-900"><Plus size={14} /> Grup ekle</button>
        }>
        <p className="text-xs text-gray-500 mb-3">
          BirFatura'da “faturalanacak sipariş durumu” olarak bu gruplardan biri seçilir. Seçilen grubun kapsadığı
          site durumlarındaki siparişler BirFatura'ya gönderilir. Grup <b>Id</b>'leri BirFatura'da saklandığı için
          sabittir; bir grubu silerseniz panelde onu seçen mağaza sipariş alamaz.
        </p>
        {form.status_groups.map((g, i) => (
          <div key={g.id} className="border rounded-lg p-3 mb-3">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-mono bg-gray-100 rounded px-2 py-1">Id {g.id}</span>
              <input value={g.name} onChange={(e) => setGroup(i, { ...g, name: e.target.value })}
                className="flex-1 border rounded px-2 py-1 text-sm" />
              <button type="button" title="Grubu sil" disabled={form.status_groups.length <= 1}
                onClick={() => set("status_groups", form.status_groups.filter((_, j) => j !== i))}
                className="p-1.5 rounded border hover:bg-red-50 text-red-600 disabled:opacity-30"><Trash2 size={14} /></button>
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1">
              {catalog.map((c) => (
                <label key={c.key} className="inline-flex items-center gap-1.5 text-xs">
                  <input type="checkbox" checked={(g.statuses || []).includes(c.key)} onChange={() => setGroup(i, toggleStatus(g, c.key))} />
                  {c.label}
                </label>
              ))}
            </div>
          </div>
        ))}
      </Section>

      <Section title="Fatura ayarları">
        <div className="grid sm:grid-cols-2 gap-4 text-sm">
          <label className="block">
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">İskonto gösterimi</span>
            <select value={form.discount_mode} onChange={(e) => set("discount_mode", e.target.value)} className="w-full border rounded-lg px-3 py-2">
              <option value="net">İndirimli birim fiyat (önerilen)</option>
              <option value="line">Brüt fiyat + satır iskontosu</option>
            </select>
            <span className="text-xs text-gray-500">Kupon/kampanya/havale indirimi ve hediye çeki ürün satırlarına dağıtılır.</span>
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Tarih aralığı alanı</span>
            <select value={form.date_field} onChange={(e) => set("date_field", e.target.value)} className="w-full border rounded-lg px-3 py-2">
              <option value="created_at">Sipariş tarihi</option>
              <option value="updated_at">Son güncelleme tarihi</option>
            </select>
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Varsayılan ürün KDV %</span>
            <input type="number" min="0" max="100" value={form.default_vat_rate} placeholder="Genel ayardan (10)"
              onChange={(e) => set("default_vat_rate", e.target.value)} className="w-full border rounded-lg px-3 py-2" />
            <span className="text-xs text-gray-500">Üründe KDV oranı yoksa kullanılır.</span>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Kargo KDV %</span>
              <input type="number" min="0" max="100" value={form.shipping_vat_rate} onChange={(e) => set("shipping_vat_rate", e.target.value)} className="w-full border rounded-lg px-3 py-2" />
            </label>
            <label className="block">
              <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Hizmet KDV %</span>
              <input type="number" min="0" max="100" value={form.service_vat_rate} onChange={(e) => set("service_vat_rate", e.target.value)} className="w-full border rounded-lg px-3 py-2" />
              <span className="text-xs text-gray-500">Hediye paketi, kapıda ödeme</span>
            </label>
          </div>
          <label className="block">
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">TCKN'siz bireysel müşteri</span>
            <input value={form.default_tckn} onChange={(e) => set("default_tckn", e.target.value)} className="w-full border rounded-lg px-3 py-2 font-mono" />
          </label>
          <label className="block">
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">En geniş çekim aralığı (gün)</span>
            <input type="number" min="1" max="366" value={form.max_window_days} onChange={(e) => set("max_window_days", e.target.value)} className="w-full border rounded-lg px-3 py-2" />
          </label>
          <label className="block sm:col-span-2">
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Fatura açıklaması</span>
            <input value={form.invoice_explanation || ""} onChange={(e) => set("invoice_explanation", e.target.value)} className="w-full border rounded-lg px-3 py-2" />
            <span className="text-xs text-gray-500">{"{order_number}"} sipariş numarasıyla değiştirilir.</span>
          </label>
          <label className="block sm:col-span-2">
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Güvenilen fatura adresleri</span>
            <textarea rows={2} value={form.trusted_hosts_text} onChange={(e) => set("trusted_hosts_text", e.target.value)} className="w-full border rounded-lg px-3 py-2 font-mono text-xs" />
            <span className="text-xs text-gray-500">BirFatura'nın geri gönderdiği fatura bağlantısı yalnız bu alan adlarından kabul edilir (https).</span>
          </label>
          <div className="sm:col-span-2 flex flex-col gap-1.5">
            <label className="inline-flex items-center gap-2"><input type="checkbox" checked={!!form.only_site_orders} onChange={(e) => set("only_site_orders", e.target.checked)} /> Yalnız site siparişleri (pazaryeri siparişleri gönderilmez)</label>
            <label className="inline-flex items-center gap-2"><input type="checkbox" checked={!!form.skip_invoiced_elsewhere} onChange={(e) => set("skip_invoiced_elsewhere", e.target.checked)} /> Başka yoldan (manuel yükleme vb.) faturalanmış siparişleri gönderme</label>
            <label className="inline-flex items-center gap-2"><input type="checkbox" checked={!!form.store_cargo_updates} onChange={(e) => set("store_cargo_updates", e.target.checked)} /> BirFatura'dan gelen kargo takip no'yu (boşsa) siparişe yaz</label>
          </div>
        </div>
        <div className="mt-4">
          <button onClick={() => save()} disabled={saving} data-testid="bf-save"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-semibold hover:bg-gray-800 disabled:opacity-50">
            <Check size={15} /> {saving ? "Kaydediliyor…" : "Kaydet"}
          </button>
        </div>
      </Section>

      <Section title="Bağlantıyı test et">
        <div className="flex flex-wrap items-end gap-3 mb-3 text-sm">
          <label>
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Durum grubu</span>
            <select value={testGroup} onChange={(e) => setTestGroup(e.target.value)} className="border rounded-lg px-3 py-2">
              <option value="">İlk grup</option>
              {(s.status_groups || []).map((g) => <option key={g.id} value={g.id}>{g.id} · {g.name}</option>)}
            </select>
          </label>
          <label>
            <span className="block text-[11px] font-bold text-gray-500 uppercase mb-1">Son … gün</span>
            <input type="number" min="1" max="31" value={testDays} onChange={(e) => setTestDays(e.target.value)} className="w-24 border rounded-lg px-3 py-2" />
          </label>
          <button onClick={runTest} disabled={testing || !s.has_token} data-testid="bf-test"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50">
            <PlayCircle size={16} /> {testing ? "Test ediliyor…" : "Bağlantıyı test et"}
          </button>
        </div>
        {test && (
          <div className="text-sm" data-testid="bf-test-result">
            <ul className="mb-2">
              {(test.checks || []).map((c, i) => (
                <li key={i} className="flex items-start gap-2">
                  {c.ok ? <Check size={15} className="text-green-600 mt-0.5" /> : <X size={15} className="text-red-600 mt-0.5" />}
                  <span><b>{c.name}:</b> {c.detail}{c.url ? <span className="text-xs text-gray-500"> ({c.url})</span> : null}</span>
                </li>
              ))}
            </ul>
            {test.request && <div className="text-xs text-gray-500 mb-1">BirFatura isteği: <code>{JSON.stringify(test.request)}</code></div>}
            {(test.skipped || []).length > 0 && (
              <div className="text-xs text-amber-700 mb-1">Atlananlar: {test.skipped.map((x) => `${x.order_number} (${x.reason})`).join(", ")}</div>
            )}
            {test.sample && (
              <pre className="text-xs bg-gray-900 text-green-200 rounded-lg p-3 max-h-96 overflow-auto">{JSON.stringify(test.sample, null, 2)}</pre>
            )}
          </div>
        )}
      </Section>

      <Section title="Son çağrılar"
        right={<button onClick={loadLogs} className="inline-flex items-center gap-1 text-sm text-blue-700"><RefreshCw size={14} /> Yenile</button>}>
        {logs.length === 0 ? (
          <p className="text-sm text-gray-500 inline-flex items-center gap-1"><FileText size={14} /> Henüz kayıt yok.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-gray-500 text-left">
                <tr><th className="py-1 pr-2">Zaman</th><th className="pr-2">Uç</th><th className="pr-2">HTTP</th><th className="pr-2">Adet</th><th className="pr-2">Süre</th><th className="pr-2">IP</th><th>Not</th></tr>
              </thead>
              <tbody>
                {logs.map((l) => (
                  <tr key={l.id} className="border-t align-top">
                    <td className="py-1 pr-2 whitespace-nowrap">{fmtDate(l.at)}</td>
                    <td className="pr-2">{l.endpoint}{l.source === "panel" ? " (panel)" : ""}</td>
                    <td className={`pr-2 font-semibold ${l.status >= 400 ? "text-red-600" : "text-green-700"}`}>{l.status}</td>
                    <td className="pr-2">{l.count ?? ""}</td>
                    <td className="pr-2">{l.duration_ms} ms</td>
                    <td className="pr-2">{l.ip}</td>
                    <td className="break-all">{l.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>
    </div>
  );
}
