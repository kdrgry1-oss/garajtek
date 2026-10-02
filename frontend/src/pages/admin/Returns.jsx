import { useState } from "react";
import { createPortal } from "react-dom";
import axios from "axios";
import { toast } from "sonner";
import { FileText, Printer, Download } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../../components/ui/dialog";
import RooftrReturns from "./RooftrReturns";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// İadeler — web sitesi iadeleri (sipariş bazlı iade akışı RooftrReturns'te) + gider pusulası
// (tekil/toplu kesim, koçan aralığı yazdırma, muhasebe Excel'i). Pazaryeri iade ekranları
// pazaryeri entegrasyonlarıyla birlikte kaldırıldı.

// Gider pusulası takip numarası: 6 haneli, başında sıfırla (ör. 000001)
function pad6(n) {
  const v = parseInt(String(n).replace(/\D/g, ""), 10);
  return isNaN(v) ? "" : String(v).padStart(6, "0");
}

// Tutarı sadece tamsayı kısmını TR yazıya çevirir (kuruşsuz): 1862 -> "Binsekizyüzaltmışiki"
function sayiToWords(num) {
  num = Math.abs(Math.floor(Number(num) || 0));
  if (num === 0) return "Sıfır";
  const birler = ["", "Bir", "İki", "Üç", "Dört", "Beş", "Altı", "Yedi", "Sekiz", "Dokuz"];
  const onlar = ["", "On", "Yirmi", "Otuz", "Kırk", "Elli", "Altmış", "Yetmiş", "Seksen", "Doksan"];
  const basamak = ["", "Bin", "Milyon", "Milyar", "Trilyon"];
  const uclu = (n) => {
    let s = "";
    const y = Math.floor(n / 100), o = Math.floor((n % 100) / 10), b = n % 10;
    if (y > 0) s += (y === 1 ? "" : birler[y]) + "Yüz";
    if (o > 0) s += onlar[o];
    if (b > 0) s += birler[b];
    return s;
  };
  const parts = [];
  let i = 0;
  while (num > 0) {
    const grp = num % 1000;
    if (grp > 0) {
      let g = uclu(grp);
      if (i === 1 && grp === 1) g = ""; // "Bin", "BirBin" değil
      parts.unshift(g + basamak[i]);
    }
    num = Math.floor(num / 1000);
    i++;
  }
  const joined = parts.join("");
  return joined.charAt(0) + joined.slice(1).toLocaleLowerCase("tr-TR");
}

// A4 yatay: sayfada aynı pusula 4 kopya (4 sütun), her sütun 74.25mm
const GP_COPIES = 4;            // bir A4 yatay sayfada aynı pusula 4 kopya (4 sütun)
const GP_SLIP_W_MM = 74.25;     // sütun genişliği (297mm / 4)
const GP_SLIP_H_MM = 210;       // sütun yüksekliği (A4 yatay)
const GP_PAGE_W_MM = 297;       // A4 yatay genişlik
const GP_PAGE_H_MM = 210;       // A4 yatay yükseklik

export default function Returns() {
  const [gpModalOpen, setGpModalOpen] = useState(false);
  const [gpData, setGpData] = useState(null);
  const [bulkPrintData, setBulkPrintData] = useState(null);
  // Gider pusulası: takip no (koçandaki ilk numaradan), matbu bindirme modu ve hizalama (mm)
  const [gpStart, setGpStart] = useState(() => localStorage.getItem("gp_next_no") || "000001");
  const [gpOverlay, setGpOverlay] = useState(() => localStorage.getItem("gp_overlay") !== "0");
  const [gpOffX, setGpOffX] = useState(() => parseFloat(localStorage.getItem("gp_off_x")) || 0);
  const [gpOffY, setGpOffY] = useState(() => parseFloat(localStorage.getItem("gp_off_y")) || 0);
  const [gpGuides, setGpGuides] = useState(false);
  // ÜSTTEKİ TARİH FİLTRESİ (iade onay tarihi) — liste + toplu gider pusulası + Excel ortak.
  const [gpFrom, setGpFrom] = useState("");
  const [gpTo, setGpTo] = useState("");
  // Gider Pusulası — MUHASEBE Excel'i (KDV oranına göre gruplu, negatif tutarlarla).
  const [gpExporting, setGpExporting] = useState(false);
  const [prFrom, setPrFrom] = useState(""); // koçan no aralığı yazdırma — başlangıç
  const [prTo, setPrTo] = useState("");     // koçan no aralığı yazdırma — bitiş
  const [prBusy, setPrBusy] = useState(false);
  // Excel'e YALNIZ pusulası kesilmiş (seri no almış) iadeler girsin (varsayılan AÇIK).
  const [gpOnlyCut, setGpOnlyCut] = useState(true);
  // Toplu pusula kesimi (tarih aralığı, YALNIZ onaylanan iadeler) — kontrollü partiler
  const [gpBulkCount, setGpBulkCount] = useState(10);
  const [gpBulkBusy, setGpBulkBusy] = useState(false);
  const [gpBulkPreview, setGpBulkPreview] = useState(null); // dry_run sonucu
  // Hazır tarih aralıkları — "son 30 gün" gibi çekimleri tek tıkla, elle yazmadan doldurur.
  // Yerel (TR) tarihi YYYY-MM-DD üretir; type="date" bu formatı bekler.
  const _ymd = (dt) => {
    const y = dt.getFullYear();
    const m = String(dt.getMonth() + 1).padStart(2, "0");
    const d = String(dt.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  };
  const applyGpPreset = (key) => {
    const now = new Date();
    let from = new Date(now), to = new Date(now);
    if (key === "today") { /* from=to=bugün */ }
    else if (key === "yesterday") { from.setDate(now.getDate() - 1); to.setDate(now.getDate() - 1); }
    else if (key === "7") { from.setDate(now.getDate() - 6); }
    else if (key === "30") { from.setDate(now.getDate() - 29); }
    else if (key === "month") { from = new Date(now.getFullYear(), now.getMonth(), 1); }
    else if (key === "prevmonth") {
      from = new Date(now.getFullYear(), now.getMonth() - 1, 1);
      to = new Date(now.getFullYear(), now.getMonth(), 0);
    }
    setGpFrom(_ymd(from));
    setGpTo(_ymd(to));
  };
  const exportGiderPusulasi = async () => {
    setGpExporting(true);
    try {
      const params = new URLSearchParams();
      if (gpFrom) params.append("date_from", gpFrom);
      if (gpTo) params.append("date_to", gpTo);
      // Yalnız pusulası kesilenler: seri no'suz iade satırları Excel'e girmez
      if (gpOnlyCut) params.append("only_with_gp", "1");
      const qs = params.toString();
      const res = await fetch(`${API}/orders/returns/gider-pusulasi/export${qs ? `?${qs}` : ""}`, {
        headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
      });
      if (!res.ok) throw new Error("export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "gider-pusulasi.xlsx";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Gider pusulası Excel'i indirildi");
    } catch (e) {
      toast.error("Gider pusulası aktarımı başarısız");
    } finally {
      setGpExporting(false);
    }
  };

  // Toplu Gider Pusulası — YALNIZ ONAYLANAN site iadeleri (iade onay tarihine göre eskiden
  // yeniye). dry=true: kesmeden önizleme; dry=false: başlangıç no'dan sıralı koçanla keser.
  const runGpBulk = async (dry) => {
    if (!gpFrom || !gpTo) { toast.error("Önce yukarıdan tarih aralığı seçin"); return; }
    if (!dry && !window.confirm(
      `${gpBulkCount} adede kadar pusula, ${pad6(gpStart)} numarasından başlayarak kesilecek. Devam?`)) return;
    setGpBulkBusy(true);
    try {
      const token = localStorage.getItem("token");
      const res = await axios.post(`${API}/admin/returns/gp-bulk-range`,
        { date_from: gpFrom, date_to: gpTo, start_no: pad6(gpStart),
          limit: gpBulkCount, dry_run: !!dry },
        { headers: { Authorization: `Bearer ${token}` } });
      if (dry) {
        setGpBulkPreview(res.data);
      } else {
        const d = res.data || {};
        if (d.next_no) { setGpStart(d.next_no); localStorage.setItem("gp_next_no", d.next_no); }
        setGpBulkPreview(null);
        toast.success(`${d.kesilen || 0} pusula kesildi · hata ${d.hata || 0} · kalan aday ${d.kalan_aday || 0}`);
        if (d.hata > 0 && Array.isArray(d.hatalar) && d.hatalar.length) {
          toast.error(`İlk hata: ${d.hatalar[0].siparis || d.hatalar[0].key} — ${d.hatalar[0].hata}`);
        }
        // KESİLEN pusulaları HEMEN yazdır (aynı 4'lü A4 şablonu / matbu form).
        if (Array.isArray(d.pusulalar) && d.pusulalar.length) {
          setBulkPrintData(d.pusulalar);
          setTimeout(() => window.print(), 600);
        }
      }
    } catch (e) {
      toast.error(e.response?.data?.detail || "Toplu pusula işlemi başarısız");
    } finally {
      setGpBulkBusy(false);
    }
  };

  const advanceGpNo = (count) => {
    const base = parseInt(pad6(gpStart) || "0", 10);
    const next = pad6(base + (count || 1));
    setGpStart(next);
    localStorage.setItem("gp_next_no", next);
  };

  // KOÇAN NO ARALIĞI YAZDIR: kesilmiş pusulaları verilen aralıkta (ör. 000100–000150) tekrar bas
  // (kullanıcı: yazıcıda kağıt sıkıştı, o aralığı baştan değil tam o aralıktan yazdır).
  const printGpRange = async () => {
    const f = String(prFrom || "").trim(), t = String(prTo || "").trim();
    if (!f || !t) { toast.error("Başlangıç ve bitiş koçan no girin"); return; }
    setPrBusy(true);
    try {
      const token = localStorage.getItem("token");
      const res = await axios.get(
        `${API}/orders/returns/gider-pusulasi/print-range?from_no=${encodeURIComponent(pad6(f))}&to_no=${encodeURIComponent(pad6(t))}`,
        { headers: { Authorization: `Bearer ${token}` } });
      const list = res.data?.pusulalar || [];
      if (!list.length) { toast.error(`Bu aralıkta (${pad6(f)}–${pad6(t)}) pusula bulunamadı`); return; }
      setBulkPrintData(list);
      toast.success(`${list.length} pusula yazdırılıyor (${pad6(f)}–${pad6(t)})`);
      setTimeout(() => window.print(), 500);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Aralık yazdırma hatası");
    } finally { setPrBusy(false); }
  };

  // Modaldan tek pusula yazdır: aynı 4'lü A4 mekanizmasını kullanır.
  // ÖNİZLEME (site iadesi) ise: numara YAZDIR anında atanır + kalıcılaşır (kullanıcı: 'numara
  // yazdırınca atansın'). TY/manuel akışta numara zaten açılışta atandığından finalize yok.
  const printSingleGp = async () => {
    if (!gpData) return;
    let finalGp = gpData;
    if (gpData.preview && gpData._returnId) {
      try {
        const token = localStorage.getItem("token");
        const res = await axios.post(`${API}/orders/returns/${gpData._returnId}/gider-pusulasi`,
          gpData._gpBody || {}, { headers: { Authorization: `Bearer ${token}` } });
        finalGp = { ...res.data.gider_pusulasi, assigned_no: gpData.assigned_no || res.data.gider_pusulasi?.display_number };
        setGpData(finalGp);
        advanceGpNo(1);
        toast.success(`Gider pusulası atandı: ${finalGp.display_number}`);
      } catch (e) {
        toast.error(e.response?.data?.detail || "Numara atanamadı — yazdırma iptal");
        return;
      }
    }
    setBulkPrintData([finalGp]);
    setTimeout(() => { window.print(); }, 300);
  };

  return (
    <div data-testid="admin-returns">
      {/* Gider Pusulası Yazdırma Katmanı: A4 dikey, sayfa başına 4 pusula */}
      {bulkPrintData && (
        <GpPrintLayer slips={bulkPrintData} overlay={gpOverlay} offX={gpOffX} offY={gpOffY} guides={gpGuides} />
      )}

      <div className="print:hidden">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">İadeler</h1>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-end gap-2 flex-wrap">
              <div className="flex flex-col">
                <label className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5" title="İade ONAY tarihi (muhasebe/admin iadeyi onayladığı tarih) — toplu gider pusulası bu tarihe göre sıralanır">İade Onay Baş.</label>
                <input type="date" value={gpFrom} onChange={(e) => setGpFrom(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm" />
              </div>
              <div className="flex flex-col">
                <label className="text-[10px] text-gray-500 uppercase tracking-wider mb-0.5" title="İade ONAY tarihi (muhasebe/admin iadeyi onayladığı tarih) — toplu gider pusulası bu tarihe göre sıralanır">İade Onay Bit.</label>
                <input type="date" value={gpTo} onChange={(e) => setGpTo(e.target.value)}
                  className="border border-gray-300 rounded-lg px-2 py-1.5 text-sm" />
              </div>
              <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer pb-2"
                title="Açıkken Excel'e YALNIZ gider pusulası kesilmiş (seri no almış) iadeler girer; pusulası olmayan hiçbir satır inmez">
                <input type="checkbox" checked={gpOnlyCut}
                  onChange={(e) => setGpOnlyCut(e.target.checked)}
                  data-testid="gp-only-cut" />
                Yalnız pusulası kesilenler
              </label>
              <button onClick={exportGiderPusulasi} disabled={gpExporting}
                data-testid="export-gider-pusulasi-btn"
                title="Gider pusulalarını (seçili tarih aralığına göre) muhasebe formatında Excel indir"
                className="flex items-center gap-2 px-4 py-2 bg-gray-900 text-white rounded-lg text-sm font-bold hover:bg-black transition-colors disabled:opacity-50">
                <Download size={16} />
                {gpExporting ? "Hazırlanıyor..." : "Gider Pusulası Excel"}
              </button>
              {/* Hazır aralık: elle tarih yazmadan tek tık. */}
              <div className="flex items-center gap-1 flex-wrap">
                {[["today", "Bugün"], ["yesterday", "Dün"], ["7", "Son 7 gün"], ["30", "Son 30 gün"], ["month", "Bu ay"], ["prevmonth", "Geçen ay"]].map(([k, lbl]) => (
                  <button key={k} type="button" onClick={() => applyGpPreset(k)}
                    className="px-2.5 py-1.5 border border-gray-300 rounded-lg text-xs text-gray-600 hover:bg-gray-100 hover:text-black transition-colors">
                    {lbl}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Gider Pusulası Ayarları */}
        <div className="flex flex-wrap items-end gap-4 mb-4 p-3 bg-purple-50 border border-purple-200 rounded-xl">
          <div>
            <label className="block text-[11px] font-bold text-purple-800 uppercase mb-1">Gider Pusulası Başlangıç No</label>
            <input value={gpStart}
              onChange={(e) => setGpStart(e.target.value)}
              onBlur={(e) => { const v = pad6(e.target.value); setGpStart(v); localStorage.setItem("gp_next_no", v); }}
              data-testid="gp-start-no"
              className="w-32 px-3 py-1.5 border border-purple-300 rounded-lg text-sm font-mono"
              placeholder="000001" />
          </div>
          <label className="flex items-center gap-2 text-sm text-purple-800 cursor-pointer pb-1.5">
            <input type="checkbox" checked={gpOverlay}
              onChange={(e) => { setGpOverlay(e.target.checked); localStorage.setItem("gp_overlay", e.target.checked ? "1" : "0"); }} />
            Matbu forma bindir (yalnız veri)
          </label>
          {gpOverlay && (
            <>
              <div>
                <label className="block text-[11px] font-bold text-purple-800 uppercase mb-1">Yatay (mm)</label>
                <input type="number" step="0.5" value={gpOffX}
                  onChange={(e) => { const v = parseFloat(e.target.value) || 0; setGpOffX(v); localStorage.setItem("gp_off_x", v); }}
                  className="w-20 px-2 py-1.5 border border-purple-300 rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-[11px] font-bold text-purple-800 uppercase mb-1">Dikey (mm)</label>
                <input type="number" step="0.5" value={gpOffY}
                  onChange={(e) => { const v = parseFloat(e.target.value) || 0; setGpOffY(v); localStorage.setItem("gp_off_y", v); }}
                  className="w-20 px-2 py-1.5 border border-purple-300 rounded-lg text-sm" />
              </div>
              <label className="flex items-center gap-2 text-sm text-purple-800 cursor-pointer pb-1.5">
                <input type="checkbox" checked={gpGuides} onChange={(e) => setGpGuides(e.target.checked)} />
                Hizalama çerçevesi
              </label>
            </>
          )}
          <p className="text-[11px] text-purple-600 ml-auto max-w-xs pb-1">
            A4 yatay, aynı pusula 4 kopya. Numara kağıda basılmaz (matbuda var); takip için satırda/önizlemede görünür. Her iade çıktısı no'yu 1 ilerletir.
          </p>
        </div>

        {/* KOÇAN NO ARALIĞI YAZDIR — kesilmiş pusulaları verilen aralıkta TEKRAR bas
            (yazıcı sıkışması vb. → baştan değil, tam istenen aralıktan yazdır). */}
        <div className="mb-4 p-3 bg-sky-50 border border-sky-200 rounded-xl">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <p className="text-[11px] font-bold text-sky-800 uppercase mb-1">Koçan No Aralığı Yazdır</p>
              <p className="text-[11px] text-sky-700 max-w-md">
                Kesilmiş gider pusulalarını verilen <b>koçan no aralığında</b> tekrar yazdırır
                (yeni pusula oluşturmaz). Kağıt sıkışması vb. durumda kaldığınız yerden devam edin.
              </p>
            </div>
            <div className="flex flex-col">
              <label className="text-[10px] text-sky-700 uppercase tracking-wider mb-0.5">Başlangıç No</label>
              <input value={prFrom} onChange={(e) => setPrFrom(e.target.value)} placeholder="000100"
                className="border border-sky-300 rounded-lg px-2 py-1.5 text-sm bg-white w-28 font-mono" />
            </div>
            <div className="flex flex-col">
              <label className="text-[10px] text-sky-700 uppercase tracking-wider mb-0.5">Bitiş No</label>
              <input value={prTo} onChange={(e) => setPrTo(e.target.value)} placeholder="000150"
                className="border border-sky-300 rounded-lg px-2 py-1.5 text-sm bg-white w-28 font-mono" />
            </div>
            <button onClick={printGpRange} disabled={prBusy}
              className="px-4 py-2 bg-sky-600 text-white rounded-lg text-sm font-bold hover:bg-sky-700 transition-colors disabled:opacity-50">
              {prBusy ? "..." : "Aralığı Yazdır"}
            </button>
          </div>
        </div>

        {/* Toplu Gider Pusulası — YALNIZ ONAYLANAN iadeler. Yukarıdaki tarih aralığı +
            iade kaynağı filtresini kullanır; başlangıç no yukarıdaki ortak alandan gelir.
            Önizle (kesmeden aday listesi) → Oluştur (kontrollü parti). */}
        <div className="mb-4 p-3 bg-emerald-50 border border-emerald-200 rounded-xl">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <p className="text-[11px] font-bold text-emerald-800 uppercase mb-1">Toplu Gider Pusulası — Onaylanan İadeler</p>
              <p className="text-[11px] text-emerald-700 max-w-md">
                Yukarıda seçili tarih aralığı ({gpFrom || "—"} → {gpTo || "—"}) içindeki
                <b> yalnız iadesi ONAYLANMIŞ ve pusulası henüz olmayan</b> iadeler, İADE ONAY
                tarihine göre sıralanır; {pad6(gpStart)} numarasından itibaren sıralı koçanla kesilir.
              </p>
            </div>
            <div className="flex flex-col">
              <label className="text-[10px] text-emerald-700 uppercase tracking-wider mb-0.5">Parti Adedi</label>
              <select value={gpBulkCount} onChange={(e) => setGpBulkCount(parseInt(e.target.value, 10))}
                data-testid="gp-bulk-count"
                className="border border-emerald-300 rounded-lg px-2 py-1.5 text-sm bg-white">
                {[10, 20, 50, 100, 200, 500, 1000, 2000].map(n => <option key={n} value={n}>{n}</option>)}
              </select>
            </div>
            <button onClick={() => runGpBulk(true)} disabled={gpBulkBusy}
              data-testid="gp-bulk-preview-btn"
              className="px-4 py-2 border border-emerald-400 text-emerald-800 rounded-lg text-sm font-bold hover:bg-emerald-100 transition-colors disabled:opacity-50">
              {gpBulkBusy ? "..." : "Önizle"}
            </button>
            <button onClick={() => runGpBulk(false)} disabled={gpBulkBusy || !gpBulkPreview}
              data-testid="gp-bulk-run-btn"
              title={gpBulkPreview ? "Önizlemedeki partiyi kes" : "Önce Önizle ile aday listesini kontrol edin"}
              className="px-4 py-2 bg-emerald-600 text-white rounded-lg text-sm font-bold hover:bg-emerald-700 transition-colors disabled:opacity-50">
              {gpBulkBusy ? "Kesiliyor..." : `Pusula Kes (${Math.min(gpBulkCount, gpBulkPreview?.bu_partide ?? gpBulkCount)})`}
            </button>
            {gpBulkPreview && (
              <button onClick={() => setGpBulkPreview(null)}
                className="px-3 py-2 text-xs text-emerald-700 hover:text-emerald-900">Önizlemeyi kapat</button>
            )}
          </div>
          {gpBulkPreview && (
            <div className="mt-3 border-t border-emerald-200 pt-2">
              <p className="text-xs font-semibold text-emerald-800 mb-1.5">
                Toplam aday: {gpBulkPreview.toplam_aday} · Bu partide kesilecek: {gpBulkPreview.bu_partide}
                {gpBulkPreview.toplam_aday > gpBulkPreview.bu_partide &&
                  ` (kalan ${gpBulkPreview.toplam_aday - gpBulkPreview.bu_partide} sonraki partilerde)`}
              </p>
              <div className="max-h-56 overflow-y-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-emerald-700">
                      <th className="py-1 pr-2">#</th>
                      <th className="py-1 pr-2">Kaynak</th>
                      <th className="py-1 pr-2">Sipariş</th>
                      <th className="py-1 pr-2">Müşteri</th>
                      <th className="py-1 pr-2">İade Tarihi</th>
                      <th className="py-1 pr-2 text-right">Tutar</th>
                      <th className="py-1">Alacağı No</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(gpBulkPreview.adaylar || []).map((a, i) => (
                      <tr key={a.key} className="border-t border-emerald-100">
                        <td className="py-1 pr-2 text-gray-500">{i + 1}</td>
                        <td className="py-1 pr-2 capitalize">{a.kaynak}</td>
                        <td className="py-1 pr-2 font-mono">{a.siparis}</td>
                        <td className="py-1 pr-2">{a.musteri || "—"}</td>
                        <td className="py-1 pr-2">{a.tarih}</td>
                        <td className="py-1 pr-2 text-right">{Number(a.tutar || 0).toLocaleString("tr-TR", { minimumFractionDigits: 2 })} ₺</td>
                        <td className="py-1 font-mono">{pad6(parseInt(pad6(gpStart) || "0", 10) + i)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>


        {/* Web sitesi iadeleri: sipariş bazlı iade akışı */}
                <RooftrReturns embedded gpStart={gpStart} dateFrom={gpFrom} dateTo={gpTo}
          onGiderCreated={(gp) => { setGpData(gp); setGpModalOpen(true); /* önizleme: numara YAZDIR'da atanır, burada advance YOK */ }}
          onBulkGider={(gps, nextNo) => { setBulkPrintData(gps); const nn = pad6(nextNo); setGpStart(nn); localStorage.setItem("gp_next_no", nn); setTimeout(() => window.print(), 500); }} />
      </div>

      {/* Gider Pusulası Modal */}
      <Dialog open={gpModalOpen} onOpenChange={setGpModalOpen}>
        <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto print:hidden" data-testid="gp-modal">
          <DialogHeader>
            <DialogTitle className="text-lg font-bold flex items-center gap-2">
              <FileText size={20} />
              Gider Pusulası — Takip No {gpData?.assigned_no || gpData?.display_number}
            </DialogTitle>
          </DialogHeader>
          {gpData && (
            <div className="print:hidden">
              {gpData.cargo_campaign_warning && (
                <div className="mb-3 flex items-start gap-2 rounded-lg border-2 border-red-400 bg-red-50 px-3 py-2 text-red-800">
                  <span className="text-lg leading-none">⚠️</span>
                  <span className="text-sm font-bold">{gpData.cargo_campaign_warning}</span>
                </div>
              )}
              {/* Kargo müşteriden kesildiyse gider pusulasında AÇIKÇA belirt (net ödeme kargo kadar düşük). */}
              {gpData.cargo?.mode === "deducted" && Number(gpData.cargo?.amount) > 0 && (
                <div className="mb-3 flex items-start gap-2 rounded-lg border-2 border-amber-400 bg-amber-50 px-3 py-2 text-amber-900">
                  <span className="text-lg leading-none">🚚</span>
                  <span className="text-sm font-semibold">
                    {gpData.cargo_deduction_note
                      || `Kargo bedeli ${fmt2(gpData.cargo.amount)} TL müşteriden kesildi (ücretsiz kargo hakkı iade sonrası kalktı). Net ödeme buna göre ${fmt2(gpData.totals?.net)} TL.`}
                  </span>
                </div>
              )}
              <p className="text-xs text-gray-500 mb-2">
                {gpData.preview
                  ? <>Önizleme — gider pusulası numarası <b className="text-amber-700">YAZDIR'a basınca atanır</b>. Yazdırmadan kapatırsanız numara yanmaz.</>
                  : <>Bu pusula <span className="font-mono font-bold text-purple-700">#{gpData.assigned_no || gpData.display_number}</span> numaralı matbu forma basılacak. Numara kağıda yazılmaz; yalnız veriler basılır.</>}
              </p>
              <div className="border rounded-lg overflow-hidden bg-white mx-auto" style={{ width: `${GP_SLIP_W_MM}mm`, maxWidth: "100%" }}>
                <GiderPusulasiSlip data={gpData} overlay={false} offX={0} offY={0} guides preview />
              </div>
              <div className="flex justify-end gap-3 mt-4">
                <button onClick={() => setGpModalOpen(false)}
                  className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200">Kapat</button>
                <button onClick={printSingleGp}
                  data-testid="gp-print-btn"
                  className="px-6 py-2 bg-purple-600 text-white rounded-lg text-sm font-bold hover:bg-purple-700">
                  <Printer size={16} className="inline mr-2" />Yazdır
                </button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>


    </div>
  );
}

function fmt2(v) {
  return new Intl.NumberFormat("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0);
}

// Tek matbu form (sütun): 74.25mm x 210mm. overlay=true -> yalnız işaretli alan verisi basılır
// (matbu için). overlay=false -> gri referans form + siyah veri (boş kağıt / hizalama testi).
function GiderPusulasiSlip({ data, overlay, offX = 0, offY = 0, guides = false }) {
  if (!data) return null;
  const c = data.customer || {};
  const tot = data.totals || {};
  const items = data.items || [];
  const dt = data.date ? new Date(data.date) : null;
  const dateStr = dt ? dt.toLocaleDateString("tr-TR") : "";
  const timeStr = dt ? dt.toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
  const net = tot.net || 0;
  const matrah = tot.net_without_vat || 0;
  const kdv = tot.vat_amount || 0;
  // Kargo müşteriden kesildiyse (deducted) AYRI göster: kesilen tutar "indirim"e katlanmıştı;
  // burada ayırıp "Kargo mahsubu" satırında gösteririz (çift saymadan, net değişmez).
  const cargoDeducted = (data.cargo && data.cargo.mode === "deducted") ? (Number(data.cargo.amount) || 0) : 0;
  const indirim = Math.max(0, (tot.discount || 0) - cargoDeducted);
  const words = sayiToWords(Math.round(net));
  const cityLine = [c.district, c.city, c.country || "Türkiye"].filter(Boolean).join("/");

  const wrap = {
    position: "relative", width: GP_SLIP_W_MM + "mm", height: GP_SLIP_H_MM + "mm",
    boxSizing: "border-box", overflow: "hidden", fontFamily: "Arial, sans-serif",
    color: "#000", background: "#fff", borderRight: guides ? "0.3mm dashed #c084fc" : "none",
  };

  // --- GRİ REFERANS (yalnız overlay kapalıyken / önizlemede; KAĞIDA BASILMAZ) ---
  const G = "#9aa0a6";
  const Gt = (x, y, s, txt, extra = {}) => (
    <div style={{ position: "absolute", left: x + "mm", top: y + "mm", fontSize: s + "mm", color: G, whiteSpace: "nowrap", ...extra }}>{txt}</div>
  );
  const reference = !overlay && (
    <div style={{ position: "absolute", inset: 0 }}>
      {Gt(5, 4, 1.7, "Adres ______________________")}
      {Gt(5, 7.5, 1.7, "V.D.: __________  VKN: __________")}
      {Gt(5, 11, 1.7, "Ticaret Sicil No: __________")}
      {Gt(5, 14.5, 1.7, "e-posta: __________________")}
      <div style={{ position: "absolute", left: "52mm", top: "4mm", width: "13mm", height: "13mm", border: "0.3mm solid " + G, borderRadius: "50%", textAlign: "center", fontSize: "1.4mm", color: G, lineHeight: "13mm" }}>T.C.</div>
      {Gt(48, 27, 1.9, "İL KODU: __", { fontWeight: 700 })}
      {Gt(52, 34, 2.0, "SERİ A", { fontWeight: 700 })}
      {Gt(5, 188, 1.6, "Yalnız _______________________")}
      {Gt(5, 193, 1.5, "____ den yukarıda belirtilen Mal/İş")}
      {Gt(5, 196.5, 1.5, "bedelini aldım.")}
      {Gt(5, 202, 1.6, "Adı Soyadı ________________")}
      {Gt(5, 206, 1.6, "Adresi ___________   İMZA")}
      <div style={{ position: "absolute", left: "2.4mm", top: "150mm", transform: "rotate(-90deg)", transformOrigin: "left top", fontSize: "1.7mm", color: "#cc2222" }}>SIRA NO   No {data.assigned_no || ""}</div>
    </div>
  );

  // --- SİYAH VERİ: sıkışık akışkan blok (KAĞIDA BASILAN TEK ALAN) ---
  const row = (label, val, bold) => (
    <div style={{ display: "flex", justifyContent: "space-between", gap: "2mm", fontWeight: bold ? 700 : 400 }}>
      <span>{label}</span><span>{val}</span>
    </div>
  );
  const black = (
    <div style={{ position: "absolute", left: "6mm", top: "49mm", width: "63mm", transform: `translate(${offX}mm, ${offY}mm)`, fontSize: "2.0mm", lineHeight: 1.12, color: "#000" }}>
      <div style={{ fontWeight: 700 }}>{c.name || ""}</div>
      <div style={{ height: "2.4mm" }} />
      {c.address ? <div>{c.address}</div> : null}
      <div>{cityLine}</div>
      <div style={{ height: "1.2mm" }} />
      <div>Sipariş: {data.order_number || ""}</div>
      <div>{dateStr}{timeStr ? "  " + timeStr : ""}</div>
      <div style={{ height: "0.8mm" }} />
      <div>Satış Fatura No: {data.sales_invoice_no || "-"}</div>
      <div>Kargo Firma: {data.cargo_company || "-"}</div>
      <div>Satış Sorumlusu: {data.sales_rep || "-"}</div>
      <div style={{ height: "1mm" }} />
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "1.9mm" }}>
        <thead>
          <tr style={{ borderBottom: "0.2mm solid #999" }}>
            <th style={{ textAlign: "left", fontWeight: 700, padding: "0.2mm 0" }}>Açıklama</th>
            <th style={{ textAlign: "right", fontWeight: 700, width: "8mm" }}>Ad.</th>
            <th style={{ textAlign: "right", fontWeight: 700, width: "17mm" }}>Tutar</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={i}>
              <td style={{ padding: "0.3mm 0", wordBreak: "break-word" }}>{it.name || ""}{it.size ? ` — Beden: ${it.size}` : ""}</td>
              <td style={{ textAlign: "right" }}>{it.quantity}</td>
              <td style={{ textAlign: "right" }}>{fmt2(-(it.net_price || 0))}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ height: "1.2mm" }} />
      {row("Tutar (V.D.)", fmt2(net), true)}
      {row("Toplam Satır İsk (VD)", fmt2(indirim))}
      {/* Kargo müşteriden kesildiyse her zaman 0 olan 'Dip İsk' satırını kargo mahsubu için kullan
          (satır sayısı sabit → matbu form hizası bozulmaz). */}
      {cargoDeducted > 0
        ? row("Kargo Mahsubu (müşt.)", "−" + fmt2(cargoDeducted))
        : row("Toplam Dip İsk (/D)", fmt2(0))}
      {row("Vergi Matrahı", fmt2(matrah))}
      {row("Kdv", fmt2(kdv))}
      {row("Net Tutar", fmt2(net), true)}
      <div style={{ height: "0.8mm" }} />
      <div>Yalnız: {words} TL</div>
    </div>
  );

  return <div style={wrap}>{reference}{black}</div>;
}

// A4 YATAY: her iade = 1 sayfa, aynı pusula 4 kopya (4 sütun). Ekranda gizli, yazdırmada görünür.
function GpPrintLayer({ slips, overlay, offX, offY, guides }) {
  if (typeof document === "undefined") return null;
  return createPortal(
    <div className="gp-print">
      <style>{`
        .gp-print { display: none; }
        @media print {
          @page { size: A4 landscape; margin: 0; }
          html, body { margin: 0 !important; padding: 0 !important; background: #fff !important; }
          /* Yazdırmada SADECE gider pusulası katmanı; admin arayüzü/başlık/kenar çubuğu/modal gizlenir */
          body > *:not(.gp-print) { display: none !important; }
          .gp-print { display: block !important; background: #fff; }
          .gp-page { width: ${GP_PAGE_W_MM}mm; height: ${GP_PAGE_H_MM}mm; display: flex; flex-direction: row; page-break-after: always; overflow: hidden; background: #fff; }
          .gp-page:last-child { page-break-after: auto; }
          .gp-col { width: ${GP_SLIP_W_MM}mm; height: ${GP_SLIP_H_MM}mm; }
        }
      `}</style>
      {(slips || []).map((gp, pi) => (
        <div className="gp-page" key={pi}>
          {Array.from({ length: GP_COPIES }).map((_, ci) => (
            <div className="gp-col" key={ci}>
              <GiderPusulasiSlip data={gp} overlay={overlay} offX={offX} offY={offY} guides={guides} />
            </div>
          ))}
        </div>
      ))}
    </div>,
    document.body
  );
}
