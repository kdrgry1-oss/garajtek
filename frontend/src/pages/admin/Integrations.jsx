import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  CreditCard, Truck, MessageSquare, FileText, RefreshCw, Check, X, AlertCircle,
  Megaphone, ExternalLink,
} from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const authHeaders = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });

/**
 * Entegrasyonlar — yalnız mağazanın kullandığı servisler:
 *   • Ödeme: iyzico (kart), Havale/EFT, Kapıda ödeme (Ödeme Tipleri)
 *   • Kargo: DHL E-Commerce (MNG), Aras Kargo, PTT Kargo (Ayarlar → Kargo Firmaları)
 *   • e-Fatura / e-Arşiv: BirFatura
 *   • Reklam pikselleri + CAPI (Meta / TikTok / Google)
 *   • SMS + İYS (NetGSM)
 */
export default function Integrations() {
  const [iyzicoStatus, setIyzicoStatus] = useState({ configured: false, mode: "sandbox" });
  const [iyzicoModalOpen, setIyzicoModalOpen] = useState(false);
  const [iyzicoSettings, setIyzicoSettings] = useState({
    api_key: "", api_secret: "", mode: "sandbox", is_active: false,
  });
  const [iyzicoTesting, setIyzicoTesting] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);

  const [logsModalOpen, setLogsModalOpen] = useState(false);
  const [integrationLogs, setIntegrationLogs] = useState([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logFilters, setLogFilters] = useState({ platform: "", status: "" });

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/integrations/payment/status`, { headers: authHeaders() });
      setIyzicoStatus(res.data || { configured: false, mode: "sandbox" });
    } catch {
      setIyzicoStatus({ configured: false, mode: "sandbox" });
    }
  };

  useEffect(() => { fetchStatus(); }, []);

  const fetchLogs = async () => {
    setLogsLoading(true);
    try {
      const params = new URLSearchParams();
      if (logFilters.platform) params.append("platform", logFilters.platform);
      if (logFilters.status) params.append("status", logFilters.status);
      const res = await axios.get(`${API}/integrations/integration-logs?${params.toString()}`, {
        headers: authHeaders(),
      });
      if (res.data.success) setIntegrationLogs(res.data.logs || []);
    } catch {
      toast.error("Loglar alınamadı");
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    if (logsModalOpen) fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [logsModalOpen, logFilters]);

  const openIyzicoSettings = async () => {
    try {
      const res = await axios.get(`${API}/integrations/iyzico/settings?t=${Date.now()}`, { headers: authHeaders() });
      setIyzicoSettings(res.data || {});
      setIyzicoModalOpen(true);
    } catch {
      toast.error("Ayarlar alınamadı");
    }
  };

  const saveIyzicoSettings = async () => {
    setSavingSettings(true);
    try {
      await axios.post(`${API}/integrations/iyzico/settings`, iyzicoSettings, { headers: authHeaders() });
      toast.success("iyzico ayarları kaydedildi");
      setIyzicoModalOpen(false);
      fetchStatus();
    } catch {
      toast.error("Ayarlar kaydedilemedi");
    } finally {
      setSavingSettings(false);
    }
  };

  const testIyzico = async () => {
    setIyzicoTesting(true);
    try {
      const res = await axios.post(`${API}/integrations/iyzico/test-connection`, {}, { headers: authHeaders() });
      if (res.data.success) toast.success(res.data.message);
      else toast.error(res.data.message);
    } catch (err) {
      toast.error(err.response?.data?.detail || "Test başarısız");
    } finally {
      setIyzicoTesting(false);
    }
  };

  const sections = [
    {
      title: "Ödeme",
      items: [
        {
          id: "iyzico",
          name: "iyzico",
          description: "Kredi/banka kartı ödemeleri, 3D Secure ve kart iadeleri.",
          icon: <CreditCard className="w-7 h-7" />,
          status: iyzicoStatus,
          actions: [
            { label: "Ayarları Yapılandır", icon: <CreditCard size={16} />, onClick: openIyzicoSettings },
            { label: "Bağlantı Test Et", icon: <RefreshCw size={16} />, onClick: testIyzico,
              loading: iyzicoTesting, disabled: !iyzicoStatus?.configured },
          ],
        },
        {
          id: "payment-methods",
          name: "Havale/EFT & Kapıda Ödeme",
          description: "Banka hesapları, havale bildirimi ve kapıda ödeme seçenekleri.",
          icon: <CreditCard className="w-7 h-7" />,
          link: "/admin/odeme-tipleri",
          linkLabel: "Ödeme Tipleri",
        },
      ],
    },
    {
      title: "Kargo",
      items: [
        {
          id: "cargo",
          name: "DHL E-Commerce (MNG) · Aras Kargo · PTT Kargo",
          description: "Gönderi oluşturma, etiket, takip ve iade kargosu ayarları.",
          icon: <Truck className="w-7 h-7" />,
          link: "/admin/ayarlar?tab=cargo",
          linkLabel: "Kargo Firmaları",
        },
      ],
    },
    {
      title: "e-Fatura / e-Arşiv",
      items: [
        {
          id: "birfatura",
          name: "BirFatura",
          description: "Siparişler BirFatura'ya aktarılır; kesilen fatura linki siparişe geri yazılır.",
          icon: <FileText className="w-7 h-7" />,
          link: "/admin/birfatura",
          linkLabel: "BirFatura Ayarları",
        },
      ],
    },
    {
      title: "Pazarlama & İletişim",
      items: [
        {
          id: "pixels",
          name: "Reklam Pikselleri & CAPI",
          description: "Meta, TikTok, Google pikselleri ve sunucu tarafı dönüşüm (CAPI) olayları.",
          icon: <Megaphone className="w-7 h-7" />,
          link: "/admin/ayarlar?tab=pixels",
          linkLabel: "Piksel Ayarları",
        },
        {
          id: "netgsm",
          name: "NetGSM SMS & İYS",
          description: "Sipariş/kargo SMS bildirimleri ve İleti Yönetim Sistemi (İYS) izin bildirimi.",
          icon: <MessageSquare className="w-7 h-7" />,
          link: "/admin/ayarlar?tab=notifications",
          linkLabel: "Bildirim Sağlayıcıları",
          extraLink: "/admin/iys",
          extraLabel: "İYS",
        },
      ],
    },
  ];

  return (
    <div data-testid="integrations-page">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Entegrasyonlar</h1>
          <p className="text-sm text-gray-500 mt-1">Ödeme, kargo, e-fatura ve iletişim entegrasyonları</p>
        </div>
        <button
          onClick={() => setLogsModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-gray-100 border text-sm rounded hover:bg-gray-200"
        >
          <FileText size={16} /> Loglar
        </button>
      </div>

      {sections.map((section) => (
        <section key={section.title} className="mb-8">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-500 mb-3">{section.title}</h2>
          <div className="grid md:grid-cols-2 gap-4">
            {section.items.map((item) => (
              <div key={item.id} className="bg-white border rounded-lg p-5" data-testid={`integration-card-${item.id}`}>
                <div className="flex items-start gap-3">
                  <div className="text-gray-700">{item.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="font-semibold">{item.name}</h3>
                      {item.status && (
                        item.status.configured ? (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-green-100 text-green-700">
                            <Check size={12} /> Aktif · {item.status.mode === "live" ? "Canlı" : "Test"}
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded bg-gray-100 text-gray-600">
                            <X size={12} /> Yapılandırılmadı
                          </span>
                        )
                      )}
                    </div>
                    <p className="text-sm text-gray-500 mt-1">{item.description}</p>
                    <div className="flex flex-wrap gap-2 mt-4">
                      {(item.actions || []).map((a, idx) => (
                        <button
                          key={idx}
                          onClick={a.onClick}
                          disabled={a.disabled || a.loading}
                          data-testid={`integration-action-${item.id}-${idx}`}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm border rounded hover:bg-gray-50 disabled:opacity-50"
                        >
                          {a.loading ? <RefreshCw size={16} className="animate-spin" /> : a.icon}
                          {a.label}
                        </button>
                      ))}
                      {item.link && (
                        <Link to={item.link}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm border rounded hover:bg-gray-50">
                          <ExternalLink size={16} /> {item.linkLabel}
                        </Link>
                      )}
                      {item.extraLink && (
                        <Link to={item.extraLink}
                          className="flex items-center gap-2 px-3 py-1.5 text-sm border rounded hover:bg-gray-50">
                          <ExternalLink size={16} /> {item.extraLabel}
                        </Link>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      ))}

      {/* iyzico Settings Modal */}
      <Dialog open={iyzicoModalOpen} onOpenChange={setIyzicoModalOpen}>
        <DialogContent data-testid="iyzico-settings-modal">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <CreditCard size={20} /> iyzico Ayarları
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); saveIyzicoSettings(); }} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1">API Key</label>
              <input data-testid="iyzico-api-key" type="text" required value={iyzicoSettings.api_key || ""}
                onChange={(e) => setIyzicoSettings({ ...iyzicoSettings, api_key: e.target.value })}
                placeholder="sandbox-xxxxxx veya api-xxxxxx"
                className="w-full border px-3 py-2 rounded text-sm" />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">API Secret</label>
              <input data-testid="iyzico-api-secret" type="password" value={iyzicoSettings.api_secret || ""}
                onChange={(e) => setIyzicoSettings({ ...iyzicoSettings, api_secret: e.target.value })}
                placeholder={iyzicoSettings.api_secret === "********" ? "********" : "Yeni Secret Key"}
                className="w-full border px-3 py-2 rounded text-sm" />
              <p className="text-xs text-gray-500 mt-1">Sadece güncellemek istediğinizde doldurun</p>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Mod</label>
              <select value={iyzicoSettings.mode || "sandbox"}
                onChange={(e) => setIyzicoSettings({ ...iyzicoSettings, mode: e.target.value })}
                className="w-full border px-3 py-2 rounded text-sm bg-white">
                <option value="sandbox">Sandbox (Test)</option>
                <option value="live">Canlı Mod</option>
              </select>
            </div>
            <label className="flex items-center gap-2 mt-2">
              <input data-testid="iyzico-is-active" type="checkbox" checked={!!iyzicoSettings.is_active}
                onChange={(e) => setIyzicoSettings({ ...iyzicoSettings, is_active: e.target.checked })} />
              <span className="text-sm">Entegrasyon Aktif</span>
            </label>
            <div className="bg-blue-50 border border-blue-200 p-3 rounded text-xs text-blue-800 flex gap-2">
              <AlertCircle size={14} className="shrink-0 mt-0.5" />
              <span>iyzico kart ödemeleri ve iade sürecinde kullanılır. Kart ödemelerinin kısmi/tam iadesi İadeler sayfasından yapılabilir.</span>
            </div>
            <div className="flex justify-end gap-2 pt-4 border-t">
              <button type="button" onClick={() => setIyzicoModalOpen(false)} className="px-4 py-2 border rounded hover:bg-gray-50">İptal</button>
              <button data-testid="iyzico-save-btn" type="submit" disabled={savingSettings}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50">
                {savingSettings ? "Kaydediliyor..." : "Kaydet"}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>

      {/* Integration Logs Modal */}
      <Dialog open={logsModalOpen} onOpenChange={setLogsModalOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText size={20} /> Entegrasyon Logları
            </DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4 overflow-hidden h-full mt-4">
            <div className="flex gap-4 p-4 border rounded-lg bg-gray-50">
              <div className="flex flex-col gap-1 w-1/3">
                <label className="text-xs font-medium text-gray-600">Platform</label>
                <select className="border rounded px-3 py-1.5 text-sm" value={logFilters.platform}
                  onChange={(e) => setLogFilters({ ...logFilters, platform: e.target.value })}>
                  <option value="">Tümü</option>
                  <option value="iyzico">iyzico</option>
                </select>
              </div>
              <div className="flex flex-col gap-1 w-1/3">
                <label className="text-xs font-medium text-gray-600">Durum</label>
                <select className="border rounded px-3 py-1.5 text-sm" value={logFilters.status}
                  onChange={(e) => setLogFilters({ ...logFilters, status: e.target.value })}>
                  <option value="">Tümü</option>
                  <option value="success">Başarılı</option>
                  <option value="error">Hatalı</option>
                  <option value="warning">Uyarı</option>
                </select>
              </div>
              <div className="flex items-end flex-1">
                <button onClick={fetchLogs} className="flex items-center gap-1 bg-black text-white px-4 py-1.5 rounded text-sm hover:bg-gray-800">
                  <RefreshCw size={14} className={logsLoading ? "animate-spin" : ""} /> Yenile
                </button>
              </div>
            </div>
            <div className="flex-1 overflow-auto border rounded-lg bg-white relative">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 sticky top-0 z-10 border-b">
                  <tr>
                    <th className="py-2 px-4 whitespace-nowrap">Tarih</th>
                    <th className="py-2 px-4">Platform</th>
                    <th className="py-2 px-4">Olay/Bölüm</th>
                    <th className="py-2 px-4">Referans</th>
                    <th className="py-2 px-4">Durum</th>
                    <th className="py-2 px-4 w-1/3">Detay</th>
                  </tr>
                </thead>
                <tbody>
                  {logsLoading && integrationLogs.length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-8 text-gray-500">Yükleniyor...</td></tr>
                  ) : integrationLogs.length === 0 ? (
                    <tr><td colSpan={6} className="text-center py-8 text-gray-500">Log kaydı bulunamadı.</td></tr>
                  ) : (
                    integrationLogs.map((log, i) => (
                      <tr key={log.id || log._id || i} className="border-b hover:bg-gray-50">
                        <td className="py-2 px-4 whitespace-nowrap text-xs text-gray-500">
                          {new Date(log.created_at).toLocaleString("tr-TR")}
                        </td>
                        <td className="py-2 px-4 font-medium uppercase text-xs">{log.platform}</td>
                        <td className="py-2 px-4">{log.event_type}</td>
                        <td className="py-2 px-4 font-mono text-xs">{log.reference_id}</td>
                        <td className="py-2 px-4">
                          <span className={`px-2 py-0.5 rounded text-xs ${
                            log.status === "error" ? "bg-red-100 text-red-700"
                              : log.status === "warning" ? "bg-yellow-100 text-yellow-700"
                                : "bg-green-100 text-green-700"}`}>
                            {log.status === "error" ? "Hata" : log.status === "warning" ? "Uyarı" : "Başarılı"}
                          </span>
                        </td>
                        <td className="py-2 px-4 text-xs text-gray-600 max-w-xs truncate" title={log.message}>
                          {log.message}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
