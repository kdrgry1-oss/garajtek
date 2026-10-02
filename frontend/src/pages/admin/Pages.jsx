import { useState, useEffect, useRef, useCallback } from "react";
import { Plus, Edit, ExternalLink, RotateCcw, Info } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "../../components/ui/dialog";
import { sanitizeHtml } from "../../lib/sanitizeHtml";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/**
 * RichTextEditor — hafif WYSIWYG (contentEditable + execCommand; yeni npm paketi YOK) ve
 * "HTML Kaynak" görünümü. Dış değişiklikte (mod değişimi, yer tutucu ekleme) innerHTML yazılır;
 * kullanıcı yazarken yazılmaz → imleç zıplamaz.
 */
function RichTextEditor({ value, onChange, editorRef }) {
  const [mode, setMode] = useState("visual"); // visual | source
  const localRef = useRef(null);
  const ref = editorRef || localRef;

  useEffect(() => {
    const el = ref.current;
    if (mode !== "visual" || !el) return;
    const safe = sanitizeHtml(value || "");
    if (el.innerHTML !== safe && document.activeElement !== el) el.innerHTML = safe;
  }, [value, mode, ref]);

  const cmd = (command, arg = null) => {
    ref.current?.focus();
    try { document.execCommand(command, false, arg); } catch { /* eski tarayıcı */ }
    onChange(ref.current?.innerHTML || "");
  };
  const addLink = () => {
    const url = window.prompt("Bağlantı adresi (ör. /sayfa/kvkk veya https://…)");
    if (url && !/^\s*javascript:/i.test(url)) cmd("createLink", url.trim());
  };
  const Btn = ({ onClick, children, title }) => (
    <button type="button" title={title} onMouseDown={(e) => e.preventDefault()} onClick={onClick}
      className="px-2 py-1 text-xs rounded border bg-white hover:bg-gray-100">{children}</button>
  );

  return (
    <div className="border rounded" data-testid="page-rte">
      <div className="flex flex-wrap items-center gap-1 px-2 py-1.5 bg-gray-50 border-b">
        {mode === "visual" && (
          <>
            <Btn title="Paragraf" onClick={() => cmd("formatBlock", "<p>")}>¶</Btn>
            <Btn title="Bölüm başlığı (H3)" onClick={() => cmd("formatBlock", "<h3>")}>H3</Btn>
            <Btn title="Alt başlık (H4)" onClick={() => cmd("formatBlock", "<h4>")}>H4</Btn>
            <Btn title="Kalın" onClick={() => cmd("bold")}><b>B</b></Btn>
            <Btn title="İtalik" onClick={() => cmd("italic")}><i>I</i></Btn>
            <Btn title="Altı çizili" onClick={() => cmd("underline")}><u>U</u></Btn>
            <Btn title="Madde işaretli liste" onClick={() => cmd("insertUnorderedList")}>• Liste</Btn>
            <Btn title="Numaralı liste" onClick={() => cmd("insertOrderedList")}>1. Liste</Btn>
            <Btn title="Bağlantı" onClick={addLink}>Bağlantı</Btn>
            <Btn title="Bağlantıyı kaldır" onClick={() => cmd("unlink")}>Bağlantı ×</Btn>
            <Btn title="Biçimi temizle" onClick={() => cmd("removeFormat")}>Temizle</Btn>
          </>
        )}
        <div className="ml-auto flex gap-1">
          <button type="button" onClick={() => setMode("visual")} data-testid="rte-mode-visual"
            className={`px-2 py-1 text-xs rounded ${mode === "visual" ? "bg-black text-white" : "bg-gray-200"}`}>Görsel</button>
          <button type="button" onClick={() => setMode("source")} data-testid="rte-mode-source"
            className={`px-2 py-1 text-xs rounded ${mode === "source" ? "bg-black text-white" : "bg-gray-200"}`}>HTML Kaynak</button>
        </div>
      </div>
      {mode === "visual" ? (
        <div ref={ref} contentEditable suppressContentEditableWarning data-testid="page-rte-visual"
          onInput={(e) => onChange(e.currentTarget.innerHTML)}
          className="prose prose-sm max-w-none px-3 py-2 min-h-[320px] max-h-[55vh] overflow-y-auto outline-none text-sm [&_h3]:text-base [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-1 [&_h4]:font-semibold [&_h4]:mt-3 [&_p]:my-1.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_a]:text-blue-600 [&_a]:underline [&_table]:w-full [&_table]:my-2 [&_td]:border [&_th]:border [&_td]:px-1.5 [&_th]:px-1.5 [&_th]:text-left [&_th]:bg-gray-50" />
      ) : (
        <textarea value={value || ""} onChange={(e) => onChange(e.target.value)} rows={18}
          data-testid="page-rte-source" className="w-full px-3 py-2 text-xs font-mono outline-none" />
      )}
    </div>
  );
}

/** Yer tutucu yardım kutusu: tıklayınca imleç konumuna (veya panoya) ekler. */
function PlaceholderHelp({ help, onInsert }) {
  const [open, setOpen] = useState(true);
  if (!help) return null;
  const Chip = ({ k, label, value }) => (
    <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => onInsert(`{{${k}}}`)}
      title={value ? `Şu anki değer: ${value}` : label}
      className="inline-flex items-center gap-1 px-2 py-0.5 m-0.5 rounded border border-blue-200 bg-white text-[11px] font-mono hover:bg-blue-100">
      {`{{${k}}}`}
      <span className="font-sans text-gray-500">— {label}{value ? `: ${value}` : " (boş)"}</span>
    </button>
  );
  return (
    <div className="rounded border border-blue-200 bg-blue-50 p-3 text-xs" data-testid="placeholder-help">
      <button type="button" onClick={() => setOpen(!open)} className="flex items-center gap-1 font-medium text-blue-900">
        <Info size={14} /> Yer tutucular (firma bilgisi metne yazılmaz, otomatik doldurulur) {open ? "▲" : "▼"}
      </button>
      {open && (
        <div className="mt-2 space-y-2 text-blue-900">
          <p>
            Aşağıdaki kodlar sayfa yayınlanırken <b>Ayarlar › İşletme Ayarları › Şirket Bilgileri</b>'nden doldurulur;
            şirket bilgisi değişince tüm sayfalar kendiliğinden güncellenir. Tıklayarak imleç konumuna ekleyin.
            Boş alanlar sitede <code>[MERSİS No]</code> gibi köşeli parantezle görünür.
          </p>
          <div>{help.company.map((p) => <Chip key={p.key} k={p.key} label={p.label} value={p.value} />)}</div>
          <p className="pt-1">
            <b>Sipariş alanları</b> — yalnız Mesafeli Satış Sözleşmesi ve Ön Bilgilendirme Formu'nda, ödeme
            ekranındaki pencerede müşterinin o anki sipariş bilgileriyle doldurulur (normal sayfada
            "sipariş sırasında doldurulur" yazar):
          </p>
          <div>{help.order.map((p) => <Chip key={p.key} k={p.key} label={p.label} />)}</div>
          <p className="pt-1 text-blue-800">
            SSS sayfasında <b>H3</b> = sekme başlığı, <b>H4</b> = soru, altındaki metin = yanıt olarak gösterilir.
            İade ve İletişim sayfalarında her <b>H3</b> bir ikonlu kart olur.
          </p>
        </div>
      )}
    </div>
  );
}

export default function AdminPages() {
  const [pages, setPages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPage, setEditingPage] = useState(null);
  const [help, setHelp] = useState(null);
  const [seeding, setSeeding] = useState(false);
  const editorRef = useRef(null);
  const [formData, setFormData] = useState({
    title: "",
    slug: "",
    content: "",
    meta_title: "",
    meta_description: "",
    is_active: true,
  });

  const fetchPages = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/pages`);
      setPages(res.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPages();
    axios.get(`${API}/pages/placeholders`).then((r) => setHelp(r.data)).catch(() => setHelp(null));
  }, [fetchPages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    // İçerik yalnız kullanıcı düzenlediğinde değişir (editör onInput) → dokunulmayan varsayılan
    // sayfa "Varsayılan" olarak kalır ve sonraki sürümlerde otomatik güncellenebilir.
    const payload = { ...formData };
    try {
      if (editingPage) {
        await axios.put(`${API}/pages/${editingPage.id}`, payload);
        toast.success("Sayfa güncellendi");
      } else {
        await axios.post(`${API}/pages`, payload);
        toast.success("Sayfa oluşturuldu");
      }
      setModalOpen(false);
      resetForm();
      fetchPages();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Hata oluştu");
    }
  };

  const openEditModal = (page) => {
    setEditingPage(page);
    setFormData({
      title: page.title,
      slug: page.slug,
      content: page.content,
      meta_title: page.meta_title || "",
      meta_description: page.meta_description || "",
      is_active: page.is_active,
    });
    setModalOpen(true);
  };

  const resetForm = () => {
    setEditingPage(null);
    setFormData({
      title: "", slug: "", content: "", meta_title: "", meta_description: "", is_active: true
    });
  };

  const generateSlug = (title) => {
    return title.toLowerCase()
      .replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ş/g, 's')
      .replace(/ı/g, 'i').replace(/ö/g, 'o').replace(/ç/g, 'c')
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  };

  const insertPlaceholder = (token) => {
    const el = editorRef.current;
    if (el && document.body.contains(el)) {
      el.focus();
      try { document.execCommand("insertText", false, token); } catch { el.innerHTML += token; }
      setFormData((f) => ({ ...f, content: el.innerHTML }));
      return;
    }
    // HTML kaynak modunda: panoya kopyala
    try { navigator.clipboard?.writeText(token); toast.success(`${token} panoya kopyalandı`); }
    catch { toast.message(token); }
  };

  const seedDefaults = async () => {
    setSeeding(true);
    try {
      const r = await axios.post(`${API}/pages/seed-defaults`);
      toast.success(r.data?.message || "Varsayılan sayfalar kontrol edildi");
      fetchPages();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Varsayılan sayfalar yüklenemedi");
    } finally { setSeeding(false); }
  };

  const resetToDefault = async (page) => {
    if (!window.confirm(`"${page.title}" sayfasındaki değişiklikleriniz silinip varsayılan metin geri yüklenecek. Emin misiniz?`)) return;
    try {
      await axios.post(`${API}/pages/seed-defaults`, null, { params: { force: true, slugs: page.slug } });
      toast.success("Varsayılan metin geri yüklendi");
      fetchPages();
    } catch (err) {
      toast.error(err.response?.data?.detail || "İşlem başarısız");
    }
  };

  return (
    <div data-testid="admin-pages">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-6">
        <h1 className="text-2xl font-bold">Sayfalar (CMS)</h1>
        <div className="flex gap-2">
          <button onClick={seedDefaults} disabled={seeding} data-testid="seed-default-pages"
            title="Eksik kurumsal/hukuki sayfaları ekler; yalnız düzenlenmemiş sayfaları günceller"
            className="flex items-center gap-2 border px-4 py-2 rounded hover:bg-gray-50 disabled:opacity-50">
            <RotateCcw size={16} /> {seeding ? "Kontrol ediliyor…" : "Varsayılan sayfaları yükle"}
          </button>
          <button
            onClick={() => { resetForm(); setModalOpen(true); }}
            className="flex items-center gap-2 bg-black text-white px-4 py-2 rounded hover:bg-gray-800"
          >
            <Plus size={18} />
            Yeni Sayfa
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm overflow-hidden">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Sayfa Başlığı</th>
              <th>Adres</th>
              <th>İçerik</th>
              <th>Durum</th>
              <th>İşlemler</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} className="text-center py-8">Yükleniyor...</td>
              </tr>
            ) : pages.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-8 text-gray-500">Sayfa bulunamadı</td>
              </tr>
            ) : (
              pages.map((page) => (
                <tr key={page.id}>
                  <td className="font-medium">{page.title}</td>
                  <td className="text-gray-500">/sayfa/{page.slug}</td>
                  <td>
                    {page.is_seed_page ? (
                      page.is_default_content
                        ? <span className="px-2 py-1 text-xs rounded bg-blue-50 text-blue-700" title="Varsayılan metin; yeni sürüm çıktığında otomatik güncellenir">Varsayılan</span>
                        : <span className="px-2 py-1 text-xs rounded bg-amber-50 text-amber-700" title="Sizin düzenlediğiniz metin; otomatik güncellemeler dokunmaz">Düzenlendi</span>
                    ) : <span className="text-xs text-gray-400">Özel sayfa</span>}
                  </td>
                  <td>
                    <span className={`px-2 py-1 text-xs rounded ${page.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {page.is_active ? "Aktif" : "Pasif"}
                    </span>
                  </td>
                  <td className="whitespace-nowrap">
                    <button onClick={() => openEditModal(page)} className="p-1 hover:bg-gray-100 rounded text-blue-600" title="Düzenle" data-testid={`edit-page-${page.slug}`}>
                      <Edit size={16} />
                    </button>
                    <a href={`/sayfa/${page.slug}`} target="_blank" rel="noreferrer" className="inline-block p-1 hover:bg-gray-100 rounded text-gray-600" title="Sitede görüntüle">
                      <ExternalLink size={16} />
                    </a>
                    {page.is_seed_page && !page.is_default_content && (
                      <button onClick={() => resetToDefault(page)} className="p-1 hover:bg-gray-100 rounded text-amber-700" title="Varsayılan metne döndür">
                        <RotateCcw size={16} />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-4xl max-h-[92vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>{editingPage ? "Sayfa Düzenle" : "Yeni Sayfa"}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Sayfa Başlığı *</label>
                <input
                  type="text"
                  value={formData.title}
                  onChange={(e) => setFormData({ ...formData, title: e.target.value, slug: editingPage ? formData.slug : generateSlug(e.target.value) })}
                  required
                  className="w-full border px-3 py-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Slug (adres: /sayfa/…)</label>
                <input
                  type="text"
                  value={formData.slug}
                  onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                  className="w-full border px-3 py-2 rounded text-sm"
                />
                {editingPage?.is_seed_page && formData.slug !== editingPage.slug && (
                  <p className="text-xs text-amber-700 mt-1">Bu adres footer ve ödeme sayfasında kullanılıyor; değiştirirseniz eski bağlantılar çalışmaz.</p>
                )}
              </div>
            </div>
            <PlaceholderHelp help={help} onInsert={insertPlaceholder} />
            <div>
              <label className="block text-sm font-medium mb-1">İçerik</label>
              <RichTextEditor value={formData.content} editorRef={editorRef}
                onChange={(html) => setFormData((f) => ({ ...f, content: html }))} />
              <p className="text-xs text-gray-500 mt-1 flex items-center gap-1">
                <Info size={12} /> Word/PDF'ten yapıştırırken biçim bozulursa "Temizle" düğmesini kullanın. Hukuki metinlerde
                yaptığınız değişiklikleri yayına almadan önce hukuk danışmanınıza kontrol ettirmeniz önerilir.
              </p>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">SEO Başlık</label>
                <input
                  type="text"
                  value={formData.meta_title}
                  onChange={(e) => setFormData({ ...formData, meta_title: e.target.value })}
                  className="w-full border px-3 py-2 rounded text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">SEO Açıklama</label>
                <input
                  type="text"
                  value={formData.meta_description}
                  onChange={(e) => setFormData({ ...formData, meta_description: e.target.value })}
                  className="w-full border px-3 py-2 rounded text-sm"
                />
              </div>
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              <span className="text-sm">Aktif</span>
            </label>
            <div className="flex justify-end gap-2 pt-4 border-t">
              <button type="button" onClick={() => setModalOpen(false)} className="px-4 py-2 border rounded hover:bg-gray-50">
                İptal
              </button>
              <button type="submit" className="px-4 py-2 bg-black text-white rounded hover:bg-gray-800" data-testid="save-page">
                {editingPage ? "Güncelle" : "Oluştur"}
              </button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
