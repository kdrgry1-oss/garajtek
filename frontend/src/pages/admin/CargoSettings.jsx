/**
 * CargoSettings.jsx — Kargo Firması Ayarları sayfası.
 *
 * Desteklenen kargo entegrasyonları: Aras Kargo ve PTT Kargo.
 *   1) CarrierDefaults — varsayılan kargo firması, desi/kg, Aras/PTT takip senkronu, canlı bağlantı testleri.
 *   2) ProviderSettings (kind="cargo") — kargo firması kimlik bilgisi ayarları.
 *
 * Bağlantılı:
 *   - components/admin/ProviderSettings.jsx (provider credential UI)
 *   - backend/routes/cargo_carriers.py, backend/cargo_carriers/ (Aras/PTT akışı + 30 dk senkron)
 */
import { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Truck, RefreshCw, Wifi } from "lucide-react";
import ProviderSettings from "../../components/admin/ProviderSettings";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

/**
 * CarrierDefaults — Kargo firması genel ayarları (Aras Kargo + PTT Kargo).
 *   - Varsayılan kargo firması (sipariş detayı / toplu barkod başlangıç seçimi)
 *   - Varsayılan desi / kg (üründe ölçü yoksa)
 *   - Aras/PTT otomatik takip senkronu (30 dk) aç/kapa + "Şimdi senkronla"
 *   - Firma bazında canlı "Bağlantıyı test et"
 * Uçlar: GET /api/cargo-carriers, POST /api/cargo-carriers/settings,
 *        POST /api/cargo-carriers/{code}/test, POST /api/cargo-carriers/poll-now
 */
function CarrierDefaults() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({ default_carrier: "", default_desi: "1", default_kg: "1", auto_sync: true });
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState("");
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data: d } = await axios.get(`${API}/cargo-carriers`, { headers: authHeaders() });
      setData(d);
      setForm({
        default_carrier: d?.default_carrier || "ARAS",
        default_desi: String(d?.settings?.default_desi ?? 1),
        default_kg: String(d?.settings?.default_kg ?? 1),
        auto_sync: d?.settings?.auto_sync !== false,
      });
    } catch (e) {
      setData({ _failed: true });
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      await axios.post(`${API}/cargo-carriers/settings`, form, { headers: authHeaders() });
      toast.success("Kargo ayarları kaydedildi");
      await load();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  const test = async (code) => {
    setTesting(code);
    try {
      const { data: r } = await axios.post(`${API}/cargo-carriers/${code}/test`, {}, { headers: authHeaders() });
      if (r?.success) toast.success(r.message); else toast.error(r?.message || "Bağlantı başarısız");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Test edilemedi");
    } finally {
      setTesting("");
    }
  };

  const syncNow = async () => {
    setSyncing(true);
    try {
      const { data: r } = await axios.post(`${API}/cargo-carriers/poll-now`, {}, { headers: authHeaders() });
      toast.success(`Aras/PTT senkronu: ${r?.processed ?? 0} sorgu, ${r?.shipped ?? 0} kargoya verildi, ${r?.delivered ?? 0} teslim`);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Senkron çalıştırılamadı");
    } finally {
      setSyncing(false);
    }
  };

  if (!data) return <div className="text-sm text-gray-400">Kargo firmaları yükleniyor…</div>;
  if (data._failed) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5 space-y-4" data-testid="carrier-defaults">
      <div>
        <h2 className="text-lg font-bold flex items-center gap-2 text-gray-900">
          <Truck className="w-5 h-5 text-indigo-600" /> Kargo Firmaları ve Varsayılanlar
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Sipariş detayında “Barkod Oluştur / Kargoya Ver” ile seçilen firmada gönderi kaydı açılır.
          Aras Kargo ve PTT Kargo bilgileri aşağıdaki listeden ilgili firma seçilerek girilir.
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {(data.carriers || []).map((c) => (
          <div key={c.code} className="border rounded-xl p-3 flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <span className="font-semibold text-sm">{c.name}</span>
              {c.configured
                ? <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">{String(c.env || "").toLowerCase() === "prod" ? "CANLI" : "TEST"}</span>
                : <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">AYARLANMADI</span>}
            </div>
            <button
              onClick={() => test(c.code)}
              disabled={!!testing}
              className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-indigo-300 text-sm text-indigo-700 hover:bg-indigo-50 disabled:opacity-60"
              data-testid={`carrier-test-${c.code}`}
            >
              <Wifi className={`w-4 h-4 ${testing === c.code ? "animate-pulse" : ""}`} />
              {testing === c.code ? "Test ediliyor…" : "Bağlantıyı test et"}
            </button>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
        <label className="text-xs font-semibold text-gray-600">
          Varsayılan kargo firması
          <select
            value={form.default_carrier}
            onChange={(e) => setForm({ ...form, default_carrier: e.target.value })}
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm bg-white"
            data-testid="default-carrier-select"
          >
            {(data.carriers || []).map((c) => <option key={c.code} value={c.code}>{c.name}</option>)}
          </select>
        </label>
        <label className="text-xs font-semibold text-gray-600">
          Varsayılan desi
          <input type="number" min="0.1" step="0.1" value={form.default_desi}
            onChange={(e) => setForm({ ...form, default_desi: e.target.value })}
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" data-testid="default-desi" />
        </label>
        <label className="text-xs font-semibold text-gray-600">
          Varsayılan ağırlık (kg)
          <input type="number" min="0.1" step="0.1" value={form.default_kg}
            onChange={(e) => setForm({ ...form, default_kg: e.target.value })}
            className="mt-1 w-full border border-gray-200 rounded-lg px-3 py-2 text-sm" data-testid="default-kg" />
        </label>
        <label className="text-xs font-semibold text-gray-600 flex items-center gap-2 pb-2">
          <input type="checkbox" checked={!!form.auto_sync}
            onChange={(e) => setForm({ ...form, auto_sync: e.target.checked })} />
          Aras/PTT takip senkronu (30 dk)
        </label>
      </div>
      <div className="flex items-center gap-2 flex-wrap">
        <button onClick={save} disabled={saving}
          className="px-4 py-2 rounded-lg bg-black text-white text-sm hover:bg-gray-800 disabled:opacity-50"
          data-testid="carrier-defaults-save">
          {saving ? "Kaydediliyor…" : "Kaydet"}
        </button>
        <button onClick={syncNow} disabled={syncing}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-gray-300 text-sm hover:bg-gray-50 disabled:opacity-60">
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Senkronlanıyor…" : "Aras/PTT takibini şimdi senkronla"}
        </button>
        <span className="text-xs text-gray-400">Desi/kg önceliği: siparişe özel ölçü → ürün en×boy×yükseklik/3000 ve ağırlık → bu varsayılanlar.</span>
      </div>
    </div>
  );
}

export default function CargoSettings() {
  return (
    <div className="space-y-6">
      <CarrierDefaults />
      <ProviderSettings
        kind="cargo"
        title="Kargo Firması Ayarları"
        subtitle="Aras Kargo ve PTT Kargo bilgilerini girin. İki firma için de bilgi girilebilir; sipariş kargo oluşturma ve etiket basmada seçilen / varsayılan firma kullanılır."
      />
    </div>
  );
}
