// BirFatura OutEBelgeV2 — panelden DOĞRUDAN fatura kesimi (sipariş listesi ikonu + onay penceresi).
// Doğrudan kesim yapılandırılmamışsa ikon eski davranışını korur (BirFatura paneline bağlantı).
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { FileText, AlertTriangle } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../ui/dialog";
import { invoiceIconState, invoiceTypeLabel, orderInvoiceInfo, fmtTL } from "../../lib/birfatura";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const BASE = `${API}/integrations/birfatura`;
const auth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

/** Doğrudan kesim yapılandırılmış mı? (yetki/ağ hatasında false → eski davranış) */
export function useDirectInvoiceStatus() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    let active = true;
    axios.get(`${BASE}/out/status`, auth())
      .then((r) => { if (active) setEnabled(!!r?.data?.configured); })
      .catch(() => { if (active) setEnabled(false); });
    return () => { active = false; };
  }, []);
  return enabled;
}

/** Sipariş satırındaki fatura ikonu. */
export function OrderInvoiceButton({ order, directEnabled, onIssue, onOpenDetail }) {
  const state = invoiceIconState(order, directEnabled);
  const { pdf, number, type } = orderInvoiceInfo(order);
  const testId = `order-invoice-${order.id}`;
  if (state === "issued") {
    const label = invoiceTypeLabel(type);
    return (
      <button type="button" title={`${label || "Fatura"} kesildi${number ? `: ${number}` : ""} — ${pdf ? "PDF'i aç" : "detayı aç"}`}
        data-testid={testId} data-state="issued"
        onClick={() => (pdf ? window.open(pdf, "_blank", "noopener,noreferrer") : onOpenDetail?.())}
        className="tci-btn" style={{ background: "#ecfdf5", color: "#047857", borderColor: "#a7f3d0" }}>
        <FileText size={15} />
      </button>
    );
  }
  if (state === "direct") {
    return (
      <button type="button" data-testid={testId} data-state="direct"
        title="Fatura henüz kesilmedi — tıklayın: BirFatura ile e-Arşiv / e-Fatura kes"
        onClick={() => onIssue?.(order)}
        className="tci-btn" style={{ color: "#2563eb" }}>
        <FileText size={15} />
      </button>
    );
  }
  return (
    <a href="https://uygulama.birfatura.com" target="_blank" rel="noopener noreferrer" data-testid={testId} data-state="panel"
      title="Fatura henüz kesilmedi — BirFatura panelinde 'Onaylanmış Siparişler'den faturalayın (BirFatura siparişi otomatik çeker; kesilince PDF burada görünür)"
      className="tci-btn" style={{ color: "#9ca3af" }}>
      <FileText size={15} />
    </a>
  );
}

const Row = ({ k, v, bold }) => (
  <div className="flex justify-between gap-3 py-0.5">
    <span className="text-gray-500">{k}</span>
    <span className={`text-right ${bold ? "font-semibold text-gray-900" : "text-gray-800"}`}>{v || "-"}</span>
  </div>
);

function typeSource(p) {
  if (p.type_source === "gib") return "GİB kayıtlı kullanıcı sorgusuna göre";
  if (p.type_source === "bireysel") return "bireysel müşteri (VKN yok)";
  if (p.type_source === "bilinmiyor") return "belirlenemedi — kesim sırasında yeniden sorgulanır";
  return "";
}

/** Onay penceresi: önizlemeyi çeker (tutar, alıcı, belge türü), onaylanınca faturayı keser. */
export function InvoiceIssueDialog({ order, onClose, onIssued }) {
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const orderId = order?.id;

  useEffect(() => {
    if (!orderId) return undefined;
    let active = true;
    setPreview(null);
    setError("");
    axios.get(`${BASE}/invoices/${encodeURIComponent(orderId)}/preview`, auth())
      .then((r) => { if (active) setPreview(r.data || {}); })
      .catch((e) => { if (active) setError(e.response?.data?.detail || "Fatura önizlemesi alınamadı"); });
    return () => { active = false; };
  }, [orderId]);

  const issue = async () => {
    setBusy(true);
    const t = toast.loading("Fatura kesiliyor…");
    try {
      const r = await axios.post(`${BASE}/invoices/${encodeURIComponent(orderId)}`, {}, auth());
      toast.success(r.data?.message || "Fatura kesildi", { id: t });
      onIssued?.(r.data?.invoice || {});
      onClose?.();
    } catch (e) {
      const d = e.response?.data || {};
      if (e.response?.status === 409 && d.invoice) {
        toast.success(d.detail || "Fatura zaten kesilmiş", { id: t });
        onIssued?.(d.invoice);
        onClose?.();
      } else {
        const msg = d.detail || "Fatura kesilemedi";
        toast.error(msg, { id: t, duration: 10000 });
        setError(msg);
      }
    } finally {
      setBusy(false);
    }
  };

  const p = preview || {};
  const problems = p.problems || [];
  const canIssue = !!preview && p.configured && !p.existing && !p.blocked && problems.length === 0 && !busy;
  const typeLabel = invoiceTypeLabel(p.invoice_type);

  return (
    <Dialog open={!!order} onOpenChange={(o) => { if (!o && !busy) onClose?.(); }}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="bf-invoice-dialog">
        <DialogHeader>
          <DialogTitle>Fatura Kes{order?.order_number ? ` — ${order.order_number}` : ""}</DialogTitle>
        </DialogHeader>
        {!preview && !error && <p className="text-sm text-gray-500">Önizleme hazırlanıyor…</p>}
        {preview && !p.configured && (
          <p className="text-sm text-amber-700">Doğrudan fatura kesimi yapılandırılmamış (Entegrasyonlar → BirFatura).</p>
        )}
        {p.existing && (
          <p className="text-sm text-green-700" data-testid="bf-invoice-existing">
            Bu siparişin faturası zaten kesilmiş{p.existing.invoice_number ? `: ${p.existing.invoice_number}` : ""}.
          </p>
        )}
        {preview && p.configured && !p.existing && (
          <div className="text-sm space-y-3" data-testid="bf-invoice-preview">
            <div className="rounded-lg border p-3">
              <div className="text-[11px] font-bold text-gray-500 uppercase mb-1">Belge türü (tahmin)</div>
              <div className="text-base font-semibold" data-testid="bf-invoice-type">{typeLabel || "Belirlenemedi"}</div>
              <div className="text-xs text-gray-500">{typeSource(p)}</div>
              {p.lookup_error && <div className="text-xs text-amber-700 mt-1">{p.lookup_error}</div>}
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-[11px] font-bold text-gray-500 uppercase mb-1">Alıcı</div>
              <Row k="Ad / Unvan" v={p.receiver?.name} bold />
              <Row k="VKN / TCKN" v={p.receiver?.tax_no} />
              {p.receiver?.tax_office && <Row k="Vergi dairesi" v={p.receiver.tax_office} />}
              <Row k="Şehir" v={p.receiver?.city} />
              {p.receiver?.email && <Row k="E-posta" v={p.receiver.email} />}
            </div>
            <div className="rounded-lg border p-3">
              <div className="text-[11px] font-bold text-gray-500 uppercase mb-1">Tutar</div>
              <Row k="KDV hariç" v={fmtTL(p.total_excl)} />
              <Row k="KDV" v={fmtTL(p.vat)} />
              <Row k="Fatura toplamı (KDV dahil)" v={fmtTL(p.total_incl)} bold />
              <Row k="Sipariş toplamı" v={fmtTL(p.order_total)} />
              <Row k="Satır sayısı" v={String(p.lines ?? "-")} />
            </div>
            {p.maybe_sent && (
              <div className="flex gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
                <AlertTriangle size={14} className="shrink-0 mt-0.5" />
                Önceki denemede BirFatura yanıt vermedi; fatura kesilmiş olabilir. Önce BirFatura panelinden kontrol edin.
                Tekrar denerseniz aynı ETTN ile gönderilir.
              </div>
            )}
          </div>
        )}
        {p.blocked && <p className="text-sm text-red-700" data-testid="bf-invoice-blocked">{p.blocked}</p>}
        {problems.length > 0 && (
          <ul className="text-sm text-red-700 list-disc pl-5" data-testid="bf-invoice-problems">
            {problems.map((x, i) => <li key={i}>{x}</li>)}
          </ul>
        )}
        {error && <p className="text-sm text-red-700" role="alert">{error}</p>}
        <div className="flex justify-end gap-2 pt-1">
          <button type="button" onClick={() => onClose?.()} disabled={busy}
            className="px-4 py-2 border rounded text-sm hover:bg-gray-50 disabled:opacity-50">Vazgeç</button>
          <button type="button" onClick={issue} disabled={!canIssue} data-testid="bf-invoice-confirm"
            className="inline-flex items-center gap-1.5 px-4 py-2 bg-green-700 text-white rounded text-sm font-semibold hover:bg-green-800 disabled:opacity-50">
            <FileText size={15} /> {busy ? "Kesiliyor…" : `${typeLabel || "Fatura"} Kes`}
          </button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
