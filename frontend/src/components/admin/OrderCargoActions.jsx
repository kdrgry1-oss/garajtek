/**
 * OrderCargoActions.jsx — Sipariş detayında kargo işlemleri (MNG/DHL, Aras Kargo, PTT Kargo).
 *
 *   - Kargo firması seçimi (varsayılan: Kargo Ayarları'ndaki "Varsayılan kargo firması")
 *   - "Barkod Oluştur / Kargoya Ver"  → POST /api/cargo-carriers/orders/{id}/create?carrier=…
 *   - "Takibi Yenile"                  → POST /api/cargo-carriers/orders/{id}/refresh
 *   - "Kargo Kaydını İptal Et"         → POST /api/cargo-carriers/orders/{id}/cancel
 *   - Etiket yazdırma mevcut "Etiket Yazdır" butonundadır (/orders/{id}/cargo-label);
 *     Aras/PTT etiketinde taşıyıcının okuttuğu barkod basılır.
 *
 * Props: order (sipariş dokümanı), onChanged() (liste/detay tazeleme)
 */
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Package, RefreshCw, XCircle, Truck } from "lucide-react";
import { isOtherChannelOrder } from "../../lib/salesChannels";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const auth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });

export const CARRIER_OPTIONS = [
  { value: "MNG", label: "DHL E-Commerce (MNG)" },
  { value: "ARAS", label: "Aras Kargo" },
  { value: "PTT", label: "PTT Kargo" },
];

const PRE_SHIP = ["pending", "confirmed", "processing", "preparing", "ready_to_ship"];

/** Siparişin mevcut kargo kaydını (varsa) özetler — test edilebilir saf fonksiyon. */
export function cargoSummary(order) {
  const o = order || {};
  const cargo = o.cargo || {};
  const code = (o.cargo_provider_code || cargo.provider || "").toUpperCase();
  const barcode = o.cargo_barcode_number || cargo.barcode || cargo.mng_siparis_no || "";
  const tracking = o.cargo_tracking_number || "";
  const hasShipment = Boolean(o.cargo_barcode_created || barcode || tracking);
  return {
    code,
    name: o.cargo_provider_name || cargo.provider_name || "",
    barcode,
    tracking,
    link: o.cargo_tracking_link || cargo.tracking_link || "",
    statusText: o.cargo_status_text || cargo.status_text || "",
    env: cargo.env || "",
    hasShipment,
    canCancel: hasShipment && PRE_SHIP.includes(o.status || "") && ["ARAS", "PTT", "MNG"].includes(code),
  };
}

export default function OrderCargoActions({ order, onChanged }) {
  const [carrier, setCarrier] = useState("");
  const [busy, setBusy] = useState("");
  const s = cargoSummary(order);
  const isMarketplace = isOtherChannelOrder(order);

  useEffect(() => {
    let off = false;
    axios.get(`${API}/cargo-carriers`, auth())
      .then(({ data }) => { if (!off) setCarrier((c) => c || data?.default_carrier || "MNG"); })
      .catch(() => { if (!off) setCarrier((c) => c || "MNG"); });
    return () => { off = true; };
  }, []);

  if (!order || isMarketplace) return null;

  const call = async (kind, url, okMsg) => {
    setBusy(kind);
    try {
      const { data } = await axios.post(url, {}, auth());
      toast.success(data?.message || okMsg);
      onChanged && onChanged();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "İşlem başarısız");
    } finally {
      setBusy("");
    }
  };

  const create = () => call("create",
    `${API}/cargo-carriers/orders/${order.id}/create?carrier=${encodeURIComponent(carrier || "")}`,
    "Kargo kaydı oluşturuldu");
  const refresh = () => call("refresh", `${API}/cargo-carriers/orders/${order.id}/refresh`, "Takip güncellendi");
  const cancel = () => {
    if (!window.confirm(`${s.name || "Kargo"} kaydı iptal edilsin mi? Barkod geçersiz olur.`)) return;
    call("cancel", `${API}/cargo-carriers/orders/${order.id}/cancel`, "Kargo kaydı iptal edildi");
  };

  return (
    <div className="w-full border rounded-lg p-3 bg-slate-50 text-sm" data-testid="order-cargo-actions">
      <div className="flex items-center gap-2 flex-wrap">
        <Truck size={16} className="text-indigo-600" />
        {s.hasShipment ? (
          <>
            <span className="font-medium">{s.name || s.code}</span>
            {s.env === "test" && (
              <span className="text-[10px] font-bold bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">TEST</span>
            )}
            {s.barcode && <span className="text-gray-600">Barkod: <b className="font-mono">{s.barcode}</b></span>}
            <span className="text-gray-600">
              Takip: {s.tracking
                ? (s.link ? <a href={s.link} target="_blank" rel="noopener noreferrer" className="font-mono text-indigo-700 underline">{s.tracking}</a>
                  : <b className="font-mono">{s.tracking}</b>)
                : <i className="text-gray-400">şube okutunca gelecek</i>}
            </span>
            {s.statusText && <span className="text-gray-500">· {s.statusText}</span>}
            <div className="flex gap-2 ml-auto">
              <button onClick={refresh} disabled={!!busy}
                className="flex items-center gap-1 px-3 py-1.5 border rounded hover:bg-white disabled:opacity-50"
                data-testid="cargo-refresh-btn">
                <RefreshCw size={14} className={busy === "refresh" ? "animate-spin" : ""} /> Takibi Yenile
              </button>
              {s.canCancel && (
                <button onClick={cancel} disabled={!!busy}
                  className="flex items-center gap-1 px-3 py-1.5 border border-red-300 text-red-700 rounded hover:bg-red-50 disabled:opacity-50"
                  data-testid="cargo-cancel-btn">
                  <XCircle size={14} /> {busy === "cancel" ? "İptal ediliyor…" : "Kargo Kaydını İptal Et"}
                </button>
              )}
            </div>
          </>
        ) : (
          <>
            <span className="text-gray-700">Kargo firması:</span>
            <select value={carrier} onChange={(e) => setCarrier(e.target.value)}
              className="border rounded px-2 py-1.5 bg-white" data-testid="cargo-carrier-select">
              {CARRIER_OPTIONS.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
            </select>
            <button onClick={create} disabled={!!busy || !carrier}
              className="flex items-center gap-1 px-3 py-1.5 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
              data-testid="cargo-create-btn">
              <Package size={14} /> {busy === "create" ? "Oluşturuluyor…" : "Barkod Oluştur / Kargoya Ver"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
