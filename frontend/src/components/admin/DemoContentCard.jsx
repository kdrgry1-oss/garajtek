// Demo içerik — gerçek ürünler eklenene kadar vitrini dolu göstermek için (yalnız süper yönetici).
// Yükle: ~36 demo ürün + slider/banner/marka görselleri (Sayfa Tasarımı bloklarının boş alanlarına).
// Kaldır: YALNIZ demo etiketli kayıtlar silinir (backend/demo_content.py).
import { useEffect, useState } from "react";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function DemoContentCard({ onChanged }) {
  const [st, setSt] = useState(null);
  const [busy, setBusy] = useState(false);
  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });
  const load = () => axios.get(`${API}/admin/demo-content`, { headers: headers() }).then((r) => setSt(r.data)).catch(() => setSt(false));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (st === false) return null; // yetki yok (yalnız süper yönetici)
  const run = async (method) => {
    const msg = method === "post"
      ? "Demo içerik yüklensin mi? (~36 demo ürün, slider ve banner görselleri; önceki demo seti yenilenir)"
      : "Demo içerik kaldırılsın mı? Yalnız demo ürünler, demo bannerlar ve demo görseller silinir.";
    const ok = window.appConfirm ? await window.appConfirm(msg) : window.confirm(msg);
    if (!ok) return;
    setBusy(true);
    try {
      const r = await axios({ method, url: `${API}/admin/demo-content`, headers: headers(), timeout: 600000 });
      toast.success(method === "post" ? `Demo içerik yüklendi: ${r.data?.created_products || 0} ürün` : `Demo içerik kaldırıldı: ${r.data?.removed_products || 0} ürün`);
      await load();
      if (onChanged) onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "İşlem tamamlanamadı");
    } finally { setBusy(false); }
  };
  return (
    <section className="rounded-lg border border-amber-200 bg-amber-50 p-3" data-testid="demo-content-card">
      <h3 className="text-xs font-semibold text-amber-900">Demo İçerik</h3>
      <p className="mt-1 text-[11px] leading-snug text-amber-900/80">
        Gerçek ürünler eklenene kadar mağazayı dolu göstermek için örnek ürünler ve görseller.
        {st ? <> Şu an: <b>{st.products}</b> demo ürün, <b>{st.banners}</b> banner.</> : null}
      </p>
      <div className="mt-2 flex gap-1.5">
        <button type="button" disabled={busy} onClick={() => run("post")} data-testid="demo-load-btn"
          className="flex-1 rounded bg-gray-900 px-2 py-1.5 text-[11px] font-semibold text-white disabled:opacity-50">{busy ? "Çalışıyor…" : st?.products ? "Yeniden Yükle" : "Demo İçerik Yükle"}</button>
        {st?.products > 0 && (
          <button type="button" disabled={busy} onClick={() => run("delete")} data-testid="demo-remove-btn"
            className="flex-1 rounded border border-red-300 bg-white px-2 py-1.5 text-[11px] font-semibold text-red-700 disabled:opacity-50">Kaldır</button>
        )}
      </div>
    </section>
  );
}
