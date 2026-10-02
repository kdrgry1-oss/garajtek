// URL'den Ürün Aktar (Katalog) — referans mağaza sayfalarından GEÇİCİ demo ürünleri içe aktarır.
// İş sunucuda arka planda çalışır (backend/url_import/); bu sayfa ilerlemeyi 1,5 sn'de bir yoklar.
// Aktarılan her ürün demo + noindex etiketlidir; "İçe aktarılanları sil" ya da Sayfa Tasarımı ›
// Demo İçerik › Kaldır ile ürünler ve indirilen görseller silinir. Ayrıntı: docs/URL_IMPORT.md
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { toast } from "sonner";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const auth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } });
const POLL_MS = 1500;
const ACTIVE = new Set(["queued", "running"]);

export const URL_PLACEHOLDER = "https://www.grayzer.net/kategori/liftler\nhttps://www.algikitelli.com.tr/";

const STATUS_TEXT = {
  queued: "Sırada", running: "Çalışıyor", done: "Tamamlandı", cancelled: "İptal edildi",
  error: "Hata", interrupted: "Yarım kaldı (sunucu yeniden başladı)",
};
const ITEM_TEXT = {
  running: "İşleniyor", imported: "Eklendi", updated: "Güncellendi", failed: "Başarısız", skipped: "Atlandı",
};
const KIND_TEXT = { product: "Ürün sayfası", listing: "Liste / kategori", info: "Bilgi", "?": "—" };

function flattenCategories(cats) {
  const byParent = {};
  (cats || []).forEach((c) => {
    const p = c.parent_id || "";
    (byParent[p] = byParent[p] || []).push(c);
  });
  const out = [];
  const walk = (pid, depth, guard) => {
    if (guard > 6) return;
    (byParent[pid] || [])
      .slice()
      .sort((a, b) => (a.sort_order || 0) - (b.sort_order || 0) || String(a.name).localeCompare(String(b.name), "tr"))
      .forEach((c) => {
        out.push({ id: c.id, label: `${"— ".repeat(depth)}${c.name}` });
        walk(c.id, depth + 1, guard + 1);
      });
  };
  walk("", 0, 0);
  return out;
}

export default function UrlImport() {
  const [urls, setUrls] = useState("");
  const [mode, setMode] = useState("auto");
  const [categoryId, setCategoryId] = useState("");
  const [maxPer, setMaxPer] = useState(30);
  const [importImages, setImportImages] = useState(true);
  const [multiplier, setMultiplier] = useState("");
  const [fixedPrice, setFixedPrice] = useState("");
  const [publish, setPublish] = useState(true);
  const [cats, setCats] = useState([]);
  const [status, setStatus] = useState(null);
  const [job, setJob] = useState(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef(null);

  const loadStatus = useCallback(() => axios.get(`${API}/admin/url-import/status`, auth())
    .then((r) => { setStatus(r.data); return r.data; })
    .catch(() => null), []);

  const poll = useCallback(async (jobId) => {
    clearTimeout(timer.current);
    try {
      const r = await axios.get(`${API}/admin/url-import/jobs/${jobId}`, auth());
      setJob(r.data);
      if (ACTIVE.has(r.data?.status)) {
        timer.current = setTimeout(() => poll(jobId), POLL_MS);
      } else {
        loadStatus();
      }
    } catch (e) {
      toast.error(e?.response?.data?.detail || "İlerleme alınamadı");
    }
  }, [loadStatus]);

  useEffect(() => {
    axios.get(`${API}/categories`).then((r) => {
      const arr = Array.isArray(r.data) ? r.data : (r.data?.categories || []);
      setCats(flattenCategories(arr));
    }).catch(() => setCats([]));
    loadStatus().then((st) => { if (st?.running_job) poll(st.running_job); });
    return () => clearTimeout(timer.current);
  }, [loadStatus, poll]);

  const running = job && ACTIVE.has(job.status);

  const start = async (e) => {
    e.preventDefault();
    if (!urls.trim()) { toast.error("En az bir URL girin"); return; }
    if (mode === "fixed" && !categoryId) { toast.error("Bir kategori seçin"); return; }
    setBusy(true);
    try {
      const r = await axios.post(`${API}/admin/url-import/jobs`, {
        urls, category_mode: mode, category_id: categoryId, max_per_category: Number(maxPer) || 30,
        import_images: importImages, price_multiplier: multiplier, fixed_price: fixedPrice, publish, demo: true,
      }, auth());
      toast.success("İçe aktarma başladı");
      setJob({ id: r.data.job_id, status: "queued", counters: {}, url_log: [], items: [] });
      poll(r.data.job_id);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Başlatılamadı");
    } finally { setBusy(false); }
  };

  const cancel = async () => {
    if (!job) return;
    try {
      await axios.post(`${API}/admin/url-import/jobs/${job.id}/cancel`, {}, auth());
      toast.success("İptal istendi — sıradaki üründen sonra durur");
    } catch (err) { toast.error(err?.response?.data?.detail || "İptal edilemedi"); }
  };

  const removeAll = async () => {
    const msg = `URL'den aktarılan ${status?.products || 0} ürün ve indirilen görselleri silinsin mi? Bu işlem geri alınamaz.`;
    const ok = window.appConfirm ? await window.appConfirm(msg) : window.confirm(msg);
    if (!ok) return;
    setBusy(true);
    try {
      const r = await axios.delete(`${API}/admin/url-import/products`, { ...auth(), timeout: 600000 });
      toast.success(`Silindi: ${r.data?.removed_products || 0} ürün, ${r.data?.removed_files || 0} görsel`);
      loadStatus();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Silinemedi");
    } finally { setBusy(false); }
  };

  const c = job?.counters || {};
  return (
    <div data-testid="url-import-page">
      <div className="mb-4">
        <h1 className="text-2xl font-bold">URL'den Ürün Aktar</h1>
        <p className="text-sm text-gray-500 mt-1">
          Ürün ya da kategori/liste sayfası adreslerini yapıştırın; sunucu sayfaları okuyup ürünleri
          (ad, fiyat, açıklama, teknik özellikler, görseller) mağazaya <b>demo</b> olarak ekler.
        </p>
      </div>

      <div className="mb-5 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900" role="alert" data-testid="url-import-warning">
        <b>Uyarı:</b> Bu araçla aktarılan içerik ve görseller kaynak sitelere aittir; yalnız geçici demo amaçlı
        kullanın, canlı satıştan önce kaldırın.
        <span className="block text-xs mt-1 text-amber-800">
          Aktarılan ürünler arama motorlarına kapalıdır (noindex), sitemap ve ürün feed'lerine girmez; ürün
          sayfasında görselin kaynağı belirtilir.
        </span>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mb-6">
        <form onSubmit={start} className="lg:col-span-2 bg-white border rounded-xl p-5 space-y-4" data-testid="url-import-form">
          <div>
            <label className="block text-sm font-semibold mb-1" htmlFor="ui-urls">Adresler (her satıra bir URL)</label>
            <textarea id="ui-urls" rows={6} value={urls} onChange={(e) => setUrls(e.target.value)}
              placeholder={URL_PLACEHOLDER} className="w-full border rounded-lg px-3 py-2 text-sm font-mono"
              data-testid="url-import-urls" />
            <p className="text-xs text-gray-500 mt-1">Ürün sayfası ya da kategori/liste sayfası olabilir; liste sayfalarında sonraki sayfalar da taranır. İş başına en çok 200 ürün.</p>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <span className="block text-sm font-semibold mb-1">Hedef kategori</span>
              <label className="flex items-center gap-2 text-sm"><input type="radio" name="ui-mode" checked={mode === "auto"} onChange={() => setMode("auto")} data-testid="url-import-mode-auto" /> Otomatik eşle (kırıntı + başlık)</label>
              <label className="flex items-center gap-2 text-sm"><input type="radio" name="ui-mode" checked={mode === "fixed"} onChange={() => setMode("fixed")} data-testid="url-import-mode-fixed" /> Hepsini seçilen kategoriye</label>
              <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="mt-2 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="url-import-category">
                <option value="">{mode === "auto" ? "Eşleşmezse: kategorisiz" : "Kategori seçin…"}</option>
                {cats.map((o) => <option key={o.id} value={o.id}>{o.label}</option>)}
              </select>
              {mode === "auto" && <p className="text-xs text-gray-500 mt-1">Otomatik modda seçilen kategori, eşleşme bulunamazsa yedek olarak kullanılır.</p>}
            </div>
            <div className="space-y-2">
              <label className="block text-sm"><span className="font-semibold">Kategori sayfası başına en çok ürün</span>
                <input type="number" min={1} max={200} value={maxPer} onChange={(e) => setMaxPer(e.target.value)} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="url-import-max" />
              </label>
              <label className="block text-sm"><span className="font-semibold">Fiyat çarpanı</span> <span className="text-gray-500">(isteğe bağlı, ör. 0,95)</span>
                <input type="text" inputMode="decimal" value={multiplier} onChange={(e) => setMultiplier(e.target.value)} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="url-import-multiplier" />
              </label>
              <label className="block text-sm"><span className="font-semibold">Sabit fiyat</span> <span className="text-gray-500">(isteğe bağlı, tüm ürünlere)</span>
                <input type="text" inputMode="decimal" value={fixedPrice} onChange={(e) => setFixedPrice(e.target.value)} className="mt-1 w-full border rounded-lg px-2 py-1.5 text-sm" data-testid="url-import-fixed-price" />
              </label>
            </div>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            <label className="flex items-center gap-2"><input type="checkbox" checked={importImages} onChange={(e) => setImportImages(e.target.checked)} data-testid="url-import-images" /> Görselleri indir (ürün başına en çok 6, WebP)</label>
            <label className="flex items-center gap-2"><input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} data-testid="url-import-publish" /> Hemen yayınla</label>
            <label className="flex items-center gap-2 text-gray-500" title="Bu araçla aktarılan her ürün demo olarak işaretlenir"><input type="checkbox" checked disabled data-testid="url-import-demo" /> Demo olarak işaretle (zorunlu)</label>
          </div>
          <div className="flex gap-2">
            <button type="submit" disabled={busy || running} className="bg-black text-white px-4 py-2 rounded-lg text-sm font-semibold disabled:opacity-50" data-testid="url-import-start">
              {running ? "Çalışıyor…" : "İçe Aktarmayı Başlat"}
            </button>
            {running && <button type="button" onClick={cancel} className="px-4 py-2 rounded-lg text-sm border" data-testid="url-import-cancel">İptal</button>}
          </div>
        </form>

        <aside className="bg-white border rounded-xl p-5" data-testid="url-import-summary">
          <h3 className="font-semibold mb-2">Mağazadaki aktarılmış ürünler</h3>
          <p className="text-3xl font-black" data-testid="url-import-count">{status?.products ?? "—"}</p>
          {status?.hosts && Object.keys(status.hosts).length > 0 && (
            <ul className="text-xs text-gray-600 mt-1">{Object.entries(status.hosts).map(([h, n]) => <li key={h}>{h}: {n}</li>)}</ul>
          )}
          <p className="text-xs text-gray-500 mt-1">{status?.files ?? 0} indirilen görsel</p>
          <button type="button" onClick={removeAll} disabled={busy || running || !status?.products}
            className="mt-3 w-full rounded-lg border border-red-300 bg-white px-3 py-2 text-sm font-semibold text-red-700 disabled:opacity-50" data-testid="url-import-remove">
            İçe aktarılanları sil
          </button>
          <p className="text-[11px] text-gray-500 mt-2">Sayfa Tasarımı › Demo İçerik › Kaldır da bu ürünleri siler.</p>
        </aside>
      </div>

      {job && (
        <section className="bg-white border rounded-xl p-5 mb-6" data-testid="url-import-progress">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <h3 className="font-semibold">İş #{job.id}</h3>
            <span className={`text-xs px-2 py-0.5 rounded-full ${running ? "bg-blue-100 text-blue-800" : job.status === "done" ? "bg-green-100 text-green-800" : "bg-gray-100 text-gray-700"}`} data-testid="url-import-status">{STATUS_TEXT[job.status] || job.status}</span>
            {job.error && <span className="text-xs text-red-600">{job.error}</span>}
          </div>
          <div className="grid grid-cols-3 md:grid-cols-6 gap-2 text-center mb-4" data-testid="url-import-counters">
            {[["Bulunan", c.found], ["Eklenen", c.imported], ["Güncellenen", c.updated], ["Başarısız", c.failed], ["Atlanan", c.skipped], ["Görsel", c.images]].map(([l, v]) => (
              <div key={l} className="rounded-lg bg-gray-50 p-2"><div className="text-lg font-bold">{v || 0}</div><div className="text-[11px] text-gray-500">{l}</div></div>
            ))}
          </div>
          {(job.url_log || []).length > 0 && (
            <div className="overflow-x-auto mb-4">
              <table className="w-full text-xs" data-testid="url-import-urllog">
                <thead><tr className="text-left text-gray-500 border-b"><th className="py-1 pr-2">Adres</th><th className="pr-2">Tür</th><th className="pr-2">Bulunan</th><th className="pr-2">Durum</th><th>Not</th></tr></thead>
                <tbody>
                  {job.url_log.map((u, i) => (
                    <tr key={i} className="border-b last:border-0">
                      <td className="py-1 pr-2 break-all max-w-xs">{u.url}</td>
                      <td className="pr-2">{KIND_TEXT[u.kind] || u.kind}</td>
                      <td className="pr-2">{u.found ?? ""}</td>
                      <td className={`pr-2 ${u.status === "failed" ? "text-red-600" : ""}`}>{u.status === "failed" ? "Başarısız" : u.status === "ok" ? "Tamam" : u.status === "running" ? "İşleniyor" : u.status}</td>
                      <td className="text-gray-600">{u.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {(job.items || []).length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="url-import-results">
                <thead><tr className="text-left text-gray-500 border-b"><th className="py-1 pr-2">Ürün</th><th className="pr-2">Kategori</th><th className="pr-2">Fiyat</th><th className="pr-2">Görsel</th><th className="pr-2">Durum</th><th>Notlar</th></tr></thead>
                <tbody>
                  {job.items.map((it, i) => (
                    <tr key={i} className="border-b last:border-0 align-top" data-testid="url-import-item">
                      <td className="py-1 pr-2 max-w-xs">
                        {it.product_id ? (
                          <Link to={`/admin/urunler/${it.product_id}`} className="text-blue-700 hover:underline" data-testid="url-import-edit-link">{it.name || it.product_id}</Link>
                        ) : (it.name || "")}
                        {it.slug && it.is_active ? <a href={`/urun/${it.slug}`} target="_blank" rel="noopener noreferrer" className="ml-1 text-gray-400 hover:text-gray-700" title="Mağazada aç">↗</a> : null}
                        <div className="text-[10px] text-gray-400 break-all">{it.source_url}</div>
                      </td>
                      <td className="pr-2">{it.category || "—"}{it.category_source ? <span className="text-gray-400"> ({it.category_source})</span> : null}</td>
                      <td className="pr-2 whitespace-nowrap">{it.price ? `${Number(it.sale_price || it.price).toLocaleString("tr-TR")} ₺` : "—"}</td>
                      <td className="pr-2">{it.images ?? ""}</td>
                      <td className={`pr-2 ${it.status === "failed" ? "text-red-600" : it.status === "skipped" ? "text-amber-700" : ""}`}>{ITEM_TEXT[it.status] || it.status}{it.product_id && it.is_active === false ? " (taslak)" : ""}</td>
                      <td className="text-gray-600">{it.error || ""}{(it.warnings || []).map((w, k) => <div key={k}>{w}</div>)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
