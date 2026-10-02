import { useState, useEffect } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Plus, Trash2, ChevronUp, ChevronDown, Save, RotateCcw, CornerDownRight,
} from "lucide-react";
import { DEFAULT_MENU_TABS } from "../../lib/headerMenu";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Basit dizi taşıma (dnd yerine oklarla — menü düzenleme nadir yapılan iş, oklar hem
// masaüstünde hem mobilde sorunsuz)
const move = (arr, from, to) => {
  if (to < 0 || to >= arr.length) return arr;
  const a = [...arr];
  const [x] = a.splice(from, 1);
  a.splice(to, 0, x);
  return a;
};

const uid = () => Math.random().toString(36).slice(2, 8);

const STYLE_OPTIONS = [
  { value: "normal", label: "Normal" },
  { value: "accent", label: "Vurgulu ◆ (Yeni Koleksiyon stili)" },
  { value: "sale", label: "Kırmızı (SALE stili)" },
];

/** Orta menü (ana navigasyon) sekmeleri — link / mega menü kolonları. */
export function CenterTabsEditor() {
  const [tabs, setTabs] = useState([]);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await axios.get(`${API}/page-blocks/header-menu`);
        const t = Array.isArray(res.data?.tabs) && res.data.tabs.length ? res.data.tabs : DEFAULT_MENU_TABS;
        setTabs(JSON.parse(JSON.stringify(t)));
      } catch (e) {
        setTabs(JSON.parse(JSON.stringify(DEFAULT_MENU_TABS)));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const update = (fn) => {
    setTabs((prev) => {
      const next = JSON.parse(JSON.stringify(prev));
      fn(next);
      return next;
    });
    setDirty(true);
  };

  const selected = tabs[selectedIdx];

  const handleSave = async () => {
    for (const t of tabs) {
      if (!String(t.label || "").trim()) { toast.error("Etiketi boş sekme var"); return; }
    }
    setSaving(true);
    try {
      const token = localStorage.getItem("token");
      await axios.put(`${API}/page-blocks/header-menu`, { tabs }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDirty(false);
      toast.success("Menü kaydedildi — site üst menüsü güncellendi");
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Kaydedilemedi");
    } finally {
      setSaving(false);
    }
  };

  const resetDefaults = () => {
    if (!window.confirm("Menü, sitenin varsayılan yapısına (Yeni Koleksiyon / Giyim / Aksesuar / Sale) sıfırlansın mı? Kaydetmeden yürürlüğe girmez.")) return;
    setTabs(JSON.parse(JSON.stringify(DEFAULT_MENU_TABS)));
    setSelectedIdx(0);
    setDirty(true);
  };

  if (loading) return <div className="p-8 text-center">Yükleniyor...</div>;

  return (
    <div data-testid="center-tabs-editor" className="max-w-6xl">
      <div className="flex items-center justify-between mb-2 flex-wrap gap-3">
        <div>
          <h2 className="text-lg font-bold">Orta Menü Sekmeleri</h2>
          <p className="text-sm text-gray-500 mt-1">Sekmeler, mega menü kolonları ve bağlantılar. "Otomatik" modda hamburger menü de bu sekmeleri listeler.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={resetDefaults} className="flex items-center gap-2 border px-3 py-2 rounded text-sm hover:bg-gray-50">
            <RotateCcw size={15} /> Varsayılana Sıfırla
          </button>
          <button onClick={handleSave} disabled={saving || !dirty}
                  className="flex items-center gap-2 bg-black text-white px-4 py-2 rounded hover:bg-gray-800 disabled:opacity-40">
            <Save size={16} /> {saving ? "Kaydediliyor..." : "Kaydet & Yayınla"}
          </button>
        </div>
      </div>

      {/* Önizleme şeridi */}
      <div className="bg-white border rounded-lg px-6 py-4 mb-6 overflow-x-auto">
        <div className="flex items-center gap-6 whitespace-nowrap">
          {tabs.filter((t) => t.active !== false).map((t, i) => (
            <span key={i} className={`text-xs uppercase tracking-[0.2em] flex items-center gap-1.5 ${t.style === "sale" ? "text-red-700" : ""} ${t.style === "accent" ? "font-medium" : "font-normal"}`}>
              {t.style === "accent" && <span className="inline-block w-[5px] h-[5px] rotate-45 bg-black/60" />}
              {t.label || "—"}
              {t.type === "mega" && <span className="text-[9px] text-gray-400 normal-case tracking-normal">▾</span>}
            </span>
          ))}
          {tabs.some((t) => t.active === false) && (
            <span className="text-[10px] text-gray-400">(+{tabs.filter((t) => t.active === false).length} gizli)</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-6 items-start">
        {/* Sol: sekme listesi */}
        <div className="bg-white border rounded-lg p-3 space-y-2">
          <div className="text-xs font-semibold text-gray-500 uppercase px-1 mb-1">Sekmeler</div>
          {tabs.map((t, i) => (
            <div key={t.id || i}
                 onClick={() => setSelectedIdx(i)}
                 className={`flex items-center gap-2 p-2.5 rounded border cursor-pointer ${i === selectedIdx ? "border-black bg-gray-50" : "border-gray-200 hover:border-gray-400"} ${t.active === false ? "opacity-45" : ""}`}>
              <div className="flex flex-col gap-0.5">
                <button onClick={(e) => { e.stopPropagation(); update((n) => { const m = move(n, i, i - 1); n.length = 0; n.push(...m); }); setSelectedIdx(Math.max(0, i - 1)); }}
                        disabled={i === 0} className="text-gray-400 hover:text-black disabled:opacity-20"><ChevronUp size={13} /></button>
                <button onClick={(e) => { e.stopPropagation(); update((n) => { const m = move(n, i, i + 1); n.length = 0; n.push(...m); }); setSelectedIdx(Math.min(tabs.length - 1, i + 1)); }}
                        disabled={i === tabs.length - 1} className="text-gray-400 hover:text-black disabled:opacity-20"><ChevronDown size={13} /></button>
              </div>
              <div className="flex-1 min-w-0">
                <div className={`text-sm truncate ${t.style === "sale" ? "text-red-700" : ""}`}>{t.label || "—"}</div>
                <div className="text-[10px] text-gray-400">{t.type === "mega" ? `Mega menü · ${(t.columns || []).reduce((s, c) => s + (c.items || []).length, 0)} link` : "Düz link"}{t.active === false ? " · gizli" : ""}</div>
              </div>
              <button onClick={(e) => {
                        e.stopPropagation();
                        if (!window.confirm(`"${t.label}" sekmesi silinsin mi?`)) return;
                        update((n) => n.splice(i, 1));
                        setSelectedIdx((s) => Math.max(0, Math.min(s > i ? s - 1 : s, tabs.length - 2)));
                      }}
                      className="text-gray-300 hover:text-red-600"><Trash2 size={14} /></button>
            </div>
          ))}
          <button onClick={() => { update((n) => n.push({ id: `tab-${uid()}`, label: "YENİ SEKME", type: "link", link: "/", style: "normal", active: true })); setSelectedIdx(tabs.length); }}
                  className="w-full flex items-center justify-center gap-2 border-2 border-dashed rounded p-2.5 text-sm text-gray-500 hover:border-black hover:text-black">
            <Plus size={15} /> Sekme Ekle
          </button>
        </div>

        {/* Sağ: seçili sekme düzenleme */}
        {selected ? (
          <div className="bg-white border rounded-lg p-5 space-y-5">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-1">Etiket</label>
                <input value={selected.label} onChange={(e) => update((n) => { n[selectedIdx].label = e.target.value; })}
                       className="w-full border px-3 py-2 rounded" placeholder="GİYİM" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Sekme Linki</label>
                <input value={selected.link || ""} onChange={(e) => update((n) => { n[selectedIdx].link = e.target.value; })}
                       className="w-full border px-3 py-2 rounded" placeholder="/giyim" />
                <p className="text-[11px] text-gray-400 mt-1">Sekmeye tıklanınca gidilen sayfa. Mega menüde açılır panelin yedek linki de budur.</p>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tip</label>
                <select value={selected.type}
                        onChange={(e) => update((n) => {
                          n[selectedIdx].type = e.target.value;
                          if (e.target.value === "mega" && !(n[selectedIdx].columns || []).length) {
                            n[selectedIdx].columns = [{ title: n[selectedIdx].label || "KOLON", link: n[selectedIdx].link || "/", items: [] }];
                          }
                        })}
                        className="w-full border px-3 py-2 rounded bg-white">
                  <option value="link">Düz link</option>
                  <option value="mega">Mega menü (açılır panel)</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Stil</label>
                <select value={selected.style || "normal"} onChange={(e) => update((n) => { n[selectedIdx].style = e.target.value; })}
                        className="w-full border px-3 py-2 rounded bg-white">
                  {STYLE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={selected.active !== false}
                     onChange={(e) => update((n) => { n[selectedIdx].active = e.target.checked; })} />
              Menüde göster
            </label>

            {selected.type === "mega" && (
              <div className="pt-2 border-t">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold">Mega Menü Kolonları</h3>
                  <button onClick={() => update((n) => { (n[selectedIdx].columns = n[selectedIdx].columns || []).push({ title: "YENİ KOLON", link: "/", items: [] }); })}
                          className="flex items-center gap-1.5 text-xs border px-2.5 py-1.5 rounded hover:bg-gray-50">
                    <Plus size={13} /> Kolon Ekle
                  </button>
                </div>
                <p className="text-[11px] text-gray-400 mb-3">Tek kolon = Aksesuar tarzı geniş liste · Birden çok kolon = Giyim tarzı başlıklı gruplar. Sağdaki 3 ürün kartı otomatiktir: üzerine gelinen linkin kategorisinden çok satanlar gösterilir.</p>
                <div className="space-y-4">
                  {(selected.columns || []).map((col, ci) => (
                    <div key={ci} className="border rounded-lg p-3 bg-gray-50/60">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="flex flex-col gap-0.5">
                          <button onClick={() => update((n) => { n[selectedIdx].columns = move(n[selectedIdx].columns, ci, ci - 1); })}
                                  disabled={ci === 0} className="text-gray-400 hover:text-black disabled:opacity-20"><ChevronUp size={13} /></button>
                          <button onClick={() => update((n) => { n[selectedIdx].columns = move(n[selectedIdx].columns, ci, ci + 1); })}
                                  disabled={ci === (selected.columns || []).length - 1} className="text-gray-400 hover:text-black disabled:opacity-20"><ChevronDown size={13} /></button>
                        </div>
                        <input value={col.title} onChange={(e) => update((n) => { n[selectedIdx].columns[ci].title = e.target.value; })}
                               className="flex-1 border px-2.5 py-1.5 rounded text-sm font-medium" placeholder="KOLON BAŞLIĞI (örn. ÜST GİYİM)" />
                        <input value={col.link || ""} onChange={(e) => update((n) => { n[selectedIdx].columns[ci].link = e.target.value; })}
                               className="w-44 border px-2.5 py-1.5 rounded text-xs" placeholder="Tümünü Gör linki" title="Başlık ve 'Tümünü Gör' bu linke gider" />
                        <button onClick={() => { if (window.confirm("Kolon silinsin mi?")) update((n) => { n[selectedIdx].columns.splice(ci, 1); }); }}
                                className="text-gray-300 hover:text-red-600"><Trash2 size={15} /></button>
                      </div>
                      <div className="space-y-1.5 pl-6">
                        {(col.items || []).map((item, ii) => (
                          <div key={ii} className="flex items-center gap-2">
                            <CornerDownRight size={12} className="text-gray-300 shrink-0" />
                            <div className="flex flex-col gap-0">
                              <button onClick={() => update((n) => { n[selectedIdx].columns[ci].items = move(n[selectedIdx].columns[ci].items, ii, ii - 1); })}
                                      disabled={ii === 0} className="text-gray-400 hover:text-black disabled:opacity-20 leading-none"><ChevronUp size={12} /></button>
                              <button onClick={() => update((n) => { n[selectedIdx].columns[ci].items = move(n[selectedIdx].columns[ci].items, ii, ii + 1); })}
                                      disabled={ii === (col.items || []).length - 1} className="text-gray-400 hover:text-black disabled:opacity-20 leading-none"><ChevronDown size={12} /></button>
                            </div>
                            <input value={item.name} onChange={(e) => update((n) => { n[selectedIdx].columns[ci].items[ii].name = e.target.value; })}
                                   className="w-40 border px-2 py-1 rounded text-sm" placeholder="Elbise" />
                            <input value={item.link || ""} onChange={(e) => update((n) => { n[selectedIdx].columns[ci].items[ii].link = e.target.value; })}
                                   className="flex-1 border px-2 py-1 rounded text-xs font-mono" placeholder="/elbise" />
                            <button onClick={() => update((n) => { n[selectedIdx].columns[ci].items.splice(ii, 1); })}
                                    className="text-gray-300 hover:text-red-600"><Trash2 size={13} /></button>
                          </div>
                        ))}
                        <button onClick={() => update((n) => { (n[selectedIdx].columns[ci].items = n[selectedIdx].columns[ci].items || []).push({ name: "", link: "/" }); })}
                                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-black mt-1">
                          <Plus size={12} /> Link Ekle
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="text-sm text-gray-400 p-8 text-center border rounded-lg bg-white">Soldan bir sekme seçin</div>
        )}
      </div>

      {dirty && (
        <div className="mt-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-3 py-2 inline-block">
          Kaydedilmemiş değişiklikler var — yayına almak için "Kaydet &amp; Yayınla"ya basın.
        </div>
      )}
    </div>
  );
}

/* ===================================================================================
   MENÜ YÖNETİMİ — vitrindeki TÜM menü grupları tek ekranda.
   Her grup: Türkçe ad + nerede göründüğü + header şeması (ilgili alan kırmızıyla vurgulu)
   + "Sitede göster" (vitrini o alan vurgulu açar). Gruplar /api/site-menus (orta menü
   sekmeleri /api/page-blocks/header-menu) üzerinden kaydedilir.
   =================================================================================== */
const MENU_GROUPS = [
  { key: "topbar", title: "Üst Bar Bağlantıları", where: "Sayfanın en üstündeki ince şerit (masaüstü): hoş geldiniz yazısı ve sağdaki bağlantılar.", show: "/?menu-highlight=topbar" },
  { key: "hamburger", title: "Hamburger (Yan) Menü", where: "Logonun yanındaki ☰ ikonuna tıklanınca soldan açılan panel (masaüstünde de çalışır).", show: "/?menu-highlight=hamburger" },
  { key: "departments", title: "Tüm Kategoriler (Sol Menü)", where: "Ana sayfada solda açık duran sarı başlıklı dikey menü; diğer sayfalarda sarı şeritteki “Kategoriler” açılır menüsü.", show: "/?menu-highlight=departments" },
  { key: "center", title: "Orta Menü (Ana Navigasyon)", where: "Ana sayfada “Tüm Kategoriler” yanındaki yatay menü; diğer sayfalarda logonun yanındaki menü. Sağda kampanya yazısı.", show: "/?menu-highlight=center" },
  { key: "mobile", title: "Mobil Menü", where: "Telefon/tablette ☰ ikonuyla açılan menü. Varsayılan: Hamburger menüyle aynı.", show: "/?menu-highlight=mobile" },
  { key: "footer", title: "Footer Sütunları", where: "Sayfanın en altındaki bağlantı sütunları, e-bülten şeridi ve iletişim bilgileri.", show: null },
];

/** Header şeması (SVG tel kafes) — seçili grup alanı kırmızı vurgulu. */
export function MenuSchematic({ group, small = false }) {
  const hl = (g) => (g === group ? { fill: "rgba(223,55,55,.18)", stroke: "#df3737", strokeWidth: 2.5 } : {});
  const w = 320; const h = 190;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" style={{ maxWidth: small ? 220 : 320 }} role="img" aria-label="Vitrin üst bölüm şeması">
      <rect x="0" y="0" width={w} height={h} rx="6" fill="#fff" stroke="#e5e7eb" />
      {/* üst bar */}
      <rect x="6" y="6" width="308" height="12" rx="2" fill="#f3f4f6" stroke="#e5e7eb" {...hl("topbar")} />
      {[200, 230, 260, 290].map((x) => <rect key={x} x={x} y="10" width="20" height="4" rx="1" fill="#9ca3af" />)}
      <rect x="12" y="10" width="60" height="4" rx="1" fill="#9ca3af" />
      {/* logo + hamburger + arama + ikonlar */}
      <text x="12" y="38" fontSize="12" fontWeight="800" fill="#333e48">garajtek</text>
      <circle cx="70" cy="34" r="2" fill="#fed700" />
      <g {...hl("hamburger")}><rect x="80" y="26" width="16" height="14" rx="2" fill={group === "hamburger" ? "rgba(223,55,55,.18)" : "#fff"} stroke={group === "hamburger" ? "#df3737" : "#d1d5db"} />
        {[30, 33, 36].map((y) => <rect key={y} x="83" y={y} width="10" height="1.6" fill="#333e48" />)}</g>
      <rect x="108" y="27" width="150" height="12" rx="6" fill="#fff" stroke="#fed700" strokeWidth="2" />
      {[270, 284, 298].map((x) => <circle key={x} cx={x} cy="33" r="4" fill="#d1d5db" />)}
      {/* nav satırı */}
      <rect x="6" y="48" width="74" height="14" rx="2" fill="#fed700" {...hl("departments")} />
      <text x="12" y="58" fontSize="7" fontWeight="700" fill="#333e48">Tüm Kategoriler</text>
      <g><rect x="86" y="48" width="228" height="14" rx="2" fill={group === "center" ? "rgba(223,55,55,.18)" : "#fff"} stroke={group === "center" ? "#df3737" : "#fff"} strokeWidth={group === "center" ? 2.5 : 0} />
        {[92, 122, 152, 182].map((x) => <rect key={x} x={x} y="53" width="24" height="4" rx="1" fill="#333e48" />)}
        <rect x="262" y="53" width="46" height="4" rx="1" fill="#9ca3af" /></g>
      {/* sol menü + hero */}
      <rect x="6" y="62" width="74" height="86" fill="#fff" stroke="#e5e7eb" {...hl("departments")} />
      {[68, 78, 88, 98, 108, 118, 128, 138].map((y) => <rect key={y} x="12" y={y} width={y < 90 ? 46 : 56} height="4" rx="1" fill={y < 90 ? "#333e48" : "#9ca3af"} />)}
      <rect x="80" y="62" width="234" height="86" fill="#f5f5f5" />
      <text x="150" y="104" fontSize="10" fill="#9ca3af">Ana Slider</text>
      {/* hamburger paneli */}
      {group === "hamburger" && <g><rect x="6" y="20" width="110" height="164" rx="3" fill="#fff" stroke="#df3737" strokeWidth="2.5" />
        {[34, 46, 58, 70, 82, 94, 106].map((y) => <rect key={y} x="14" y={y} width="80" height="5" rx="1" fill="#333e48" opacity=".7" />)}
        <text x="14" y="130" fontSize="7" fill="#df3737">☰ yan menü</text></g>}
      {/* mobil */}
      {group === "mobile" && <g><rect x="232" y="64" width="78" height="120" rx="10" fill="#fff" stroke="#df3737" strokeWidth="2.5" />
        <rect x="238" y="74" width="66" height="10" fill="#fed700" />
        {[92, 104, 116, 128, 140, 152].map((y) => <rect key={y} x="242" y={y} width="50" height="5" rx="1" fill="#333e48" opacity=".7" />)}</g>}
      {/* footer */}
      <rect x="6" y="156" width="308" height="28" rx="2" fill="#f3f4f6" {...hl("footer")} />
      {[20, 90, 160, 230].map((x) => <g key={x}><rect x={x} y="162" width="40" height="4" rx="1" fill="#333e48" />
        <rect x={x} y="170" width="50" height="3" rx="1" fill="#9ca3af" /><rect x={x} y="176" width="44" height="3" rx="1" fill="#9ca3af" /></g>)}
    </svg>
  );
}

const nid = () => `m${Math.random().toString(36).slice(2, 8)}`;
const ICON_CHOICES = [
  ["", "İkon yok"], ["ec ec-map-pointer", "Konum"], ["ec ec-transport", "Kargo"], ["ec ec-shopping-bag", "Çanta"],
  ["ec ec-user", "Kullanıcı"], ["ec ec-favorites", "Favori"], ["ec ec-support", "Destek"], ["ec ec-returning", "İade"],
  ["fas fa-percent", "Yüzde"], ["fas fa-fire", "Ateş"], ["fas fa-star", "Yıldız"], ["fas fa-tools", "Alet"], ["fas fa-phone", "Telefon"],
];

/** Bağlantı seçici: kategori / sayfa / adres */
function LinkPicker({ value, onChange, cats, pages }) {
  return (
    <div className="flex gap-1">
      <input value={value || ""} onChange={(e) => onChange(e.target.value)} placeholder="/kategori-adresi, /sayfa/... veya https://"
        className="flex-1 min-w-0 border rounded px-2 py-1 text-xs font-mono" />
      <select value="" onChange={(e) => { if (e.target.value) onChange(e.target.value); }} className="w-28 border rounded px-1 py-1 text-xs" aria-label="Hazır bağlantı seç">
        <option value="">Seç…</option>
        <optgroup label="Özel">
          <option value="/sale">İndirimli ürünler</option><option value="/en-yeniler">Yeni ürünler</option>
          <option value="/tum-urunler">Tüm ürünler</option><option value="/tum-urunler?sort=popular&order=desc">Çok satanlar</option>
          <option value="/siparis-takip">Sipariş takibi</option><option value="/hesabim">Hesabım</option><option value="/favoriler">Favoriler</option>
        </optgroup>
        <optgroup label="Kategoriler">{cats.map((c) => <option key={c.id} value={`/${c.slug}`}>{c.full_name || c.name}</option>)}</optgroup>
        <optgroup label="Sayfalar">{pages.map((p) => <option key={p.slug} value={`/sayfa/${p.slug}`}>{p.title}</option>)}</optgroup>
      </select>
    </div>
  );
}

/** 3 seviyeye kadar menü ağacı düzenleyici (ekle / düzenle / sırala / alt öğe). */
function MenuTreeEditor({ items, onChange, cats, pages, depth = 1, maxDepth = 3, allowIcon = false, allowStyle = true }) {
  const list = items || [];
  const upd = (i, patch) => onChange(list.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  return (
    <div className={depth > 1 ? "ml-5 mt-1 border-l-2 border-gray-200 pl-3 space-y-1" : "space-y-1"}>
      {list.map((it, i) => (
        <div key={it.id || i} className="rounded border bg-white p-2" data-testid={`menu-item-${depth}-${i}`}>
          <div className="flex flex-wrap items-center gap-1">
            <input value={it.label || ""} onChange={(e) => upd(i, { label: e.target.value })} placeholder="Etiket" className="w-40 border rounded px-2 py-1 text-xs" />
            <div className="flex-1 min-w-[220px]"><LinkPicker value={it.link} onChange={(v) => upd(i, { link: v })} cats={cats} pages={pages} /></div>
            {allowStyle && (
              <select value={it.style || "normal"} onChange={(e) => upd(i, { style: e.target.value })} className="border rounded px-1 py-1 text-xs" aria-label="Stil">
                <option value="normal">Normal</option><option value="bold">Kalın</option><option value="sale">Kırmızı (indirim)</option>
              </select>
            )}
            {allowIcon && (
              <select value={it.icon || ""} onChange={(e) => upd(i, { icon: e.target.value })} className="border rounded px-1 py-1 text-xs" aria-label="İkon">
                {ICON_CHOICES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            )}
            <button type="button" className="p-1 hover:bg-gray-100 rounded" title="Yukarı" onClick={() => onChange(move(list, i, i - 1))}><ChevronUp size={14} /></button>
            <button type="button" className="p-1 hover:bg-gray-100 rounded" title="Aşağı" onClick={() => onChange(move(list, i, i + 1))}><ChevronDown size={14} /></button>
            {depth < maxDepth && (
              <button type="button" className="p-1 hover:bg-gray-100 rounded text-xs flex items-center gap-0.5" title="Alt öğe ekle"
                onClick={() => upd(i, { children: [...(it.children || []), { id: nid(), label: "", link: "/" }] })}><CornerDownRight size={13} /> Alt</button>
            )}
            <button type="button" className="p-1 hover:bg-red-50 text-red-600 rounded" title="Sil" onClick={() => onChange(list.filter((_, j) => j !== i))}><Trash2 size={14} /></button>
          </div>
          {(it.children || []).length > 0 && (
            <MenuTreeEditor items={it.children} onChange={(v) => upd(i, { children: v })} cats={cats} pages={pages} depth={depth + 1} maxDepth={maxDepth} allowStyle={allowStyle} />
          )}
        </div>
      ))}
      <button type="button" onClick={() => onChange([...list, { id: nid(), label: "", link: "/" }])}
        className="flex items-center gap-1 text-xs border border-dashed rounded px-2 py-1 hover:bg-gray-50" data-testid={`add-item-${depth}`}>
        <Plus size={13} /> {depth === 1 ? "Öğe ekle" : "Alt öğe ekle"}
      </button>
    </div>
  );
}

/** Canlı önizleme — dikey liste (alt öğeler girintili). */
function TreePreview({ items, title, quick = [] }) {
  const row = (it, d) => (
    <div key={it.id || it.label} style={{ paddingLeft: d * 12 }} className={`py-1 border-b border-gray-100 text-[12px] ${it.style === "bold" ? "font-bold" : ""} ${it.style === "sale" ? "text-red-600 font-bold" : "text-gray-800"}`}>
      {it.icon && <i className={`${it.icon} mr-1`} />}{it.label || <span className="text-gray-300">(etiketsiz)</span>}
      {(it.children || []).length > 0 && <span className="text-gray-400"> ›</span>}
    </div>
  );
  const walk = (list, d, out) => { (list || []).forEach((it) => { out.push(row(it, d)); walk(it.children, d + 1, out); }); return out; };
  return (
    <div className="rounded-lg border bg-white overflow-hidden">
      {title && <div className="bg-[#fed700] px-3 py-2 text-xs font-bold text-[#333e48]">{title}</div>}
      <div className="px-3 py-1 max-h-80 overflow-y-auto">{walk(quick, 0, [])}{walk(items, 0, [])}</div>
    </div>
  );
}

function useMenuRefs() {
  const [cats, setCats] = useState([]);
  const [pages, setPages] = useState([]);
  useEffect(() => {
    axios.get(`${API}/categories`).then((r) => setCats(Array.isArray(r.data) ? r.data : [])).catch(() => {});
    axios.get(`${API}/pages`, { headers: { Authorization: `Bearer ${localStorage.getItem("token")}` } }).then((r) => setPages(Array.isArray(r.data) ? r.data : (r.data?.pages || []))).catch(() => {});
  }, []);
  return { cats, pages };
}

function GroupEditor({ group, data, onSave, onReset, refs }) {
  const [d, setD] = useState(data);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setD(data); }, [data]);
  const dirty = JSON.stringify(d) !== JSON.stringify(data);
  const save = async () => { setSaving(true); try { await onSave(d); } finally { setSaving(false); } };
  const bar = (
    <div className="flex items-center gap-2">
      <button type="button" onClick={onReset} className="flex items-center gap-1 border px-3 py-1.5 rounded text-sm hover:bg-gray-50"><RotateCcw size={14} /> Varsayılana Dön</button>
      <button type="button" onClick={save} disabled={!dirty || saving} data-testid="menu-group-save"
        className="flex items-center gap-1 bg-black text-white px-4 py-1.5 rounded text-sm disabled:opacity-40"><Save size={14} /> {saving ? "Kaydediliyor…" : "Kaydet & Yayınla"}</button>
    </div>
  );
  const modeSwitch = (labels) => (
    <div className="flex gap-4 text-sm">
      {labels.map(([v, l]) => (
        <label key={v} className="flex items-center gap-1"><input type="radio" checked={(d.mode || labels[0][0]) === v} onChange={() => setD({ ...d, mode: v })} /> {l}</label>
      ))}
    </div>
  );
  let body = null; let preview = null;
  if (group === "topbar") {
    body = (
      <div className="space-y-3">
        <label className="block text-sm">Hoş geldiniz yazısı <span className="text-gray-400 text-xs">(boşsa “Mağaza adı'e Hoş Geldiniz …”)</span>
          <input value={d.welcome || ""} onChange={(e) => setD({ ...d, welcome: e.target.value })} className="mt-1 w-full border rounded px-2 py-1.5 text-sm" /></label>
        <p className="text-xs text-gray-500">Sağdaki bağlantılar (alt öğe desteklenmez). “Hesabım” öğesi, ziyaretçi giriş yapmamışsa otomatik “Üye Ol veya Giriş Yap” olur.</p>
        <MenuTreeEditor items={d.items} onChange={(v) => setD({ ...d, items: v })} {...refs} maxDepth={1} allowIcon allowStyle={false} />
      </div>
    );
    preview = <div className="rounded border bg-[#f8f8f8] px-3 py-2 text-[11px] flex flex-wrap gap-3 text-gray-700">{(d.items || []).map((it) => <span key={it.id}>{it.icon && <i className={`${it.icon} mr-1`} />}{it.label}</span>)}</div>;
  } else if (group === "departments") {
    body = (
      <div className="space-y-3">
        {modeSwitch([["auto", "Otomatik — kategori ağacından"], ["manual", "Elle oluşturulan menü"]])}
        <label className="block text-sm">En fazla ana kategori sayısı
          <input type="number" min={4} max={30} value={d.max_roots || 14} onChange={(e) => setD({ ...d, max_roots: Number(e.target.value) || 14 })} className="ml-2 w-20 border rounded px-2 py-1 text-sm" /></label>
        <div><div className="text-sm font-semibold mb-1">Üste sabitlenen hızlı bağlantılar</div>
          <MenuTreeEditor items={d.quick} onChange={(v) => setD({ ...d, quick: v })} {...refs} maxDepth={1} /></div>
        {d.mode === "manual" && <div><div className="text-sm font-semibold mb-1">Menü öğeleri (alt öğeler sağda açılan panelde sütun olur)</div>
          <MenuTreeEditor items={d.items} onChange={(v) => setD({ ...d, items: v })} {...refs} /></div>}
        {d.mode !== "manual" && <p className="text-xs text-gray-500">Kategoriler <a className="underline" href="/admin/kategoriler">Kategoriler</a> ekranındaki sıra ve “menüde göster” ayarına göre listelenir.</p>}
      </div>
    );
    preview = <TreePreview title="☰ Tüm Kategoriler" quick={d.quick} items={d.mode === "manual" ? d.items : (refs.cats || []).filter((c) => !c.parent_id).slice(0, d.max_roots || 14).map((c) => ({ id: c.id, label: c.name }))} />;
  } else if (group === "hamburger") {
    body = (
      <div className="space-y-3">
        {modeSwitch([["auto", "Otomatik — hızlı bağlantılar + orta menü sekmeleri + kategoriler"], ["manual", "Elle oluşturulan menü"]])}
        {d.mode !== "manual" && <div><div className="text-sm font-semibold mb-1">Üstteki hızlı bağlantılar</div>
          <MenuTreeEditor items={d.quick} onChange={(v) => setD({ ...d, quick: v })} {...refs} maxDepth={1} /></div>}
        {d.mode === "manual" && <MenuTreeEditor items={d.items} onChange={(v) => setD({ ...d, items: v })} {...refs} allowIcon />}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={d.show_account_links !== false} onChange={(e) => setD({ ...d, show_account_links: e.target.checked })} /> Alta hesap bağlantılarını ekle (Hesabım, Favoriler, Sipariş Takibi, İade, İletişim)</label>
      </div>
    );
    preview = <TreePreview title="☰ Yan Menü" quick={d.mode === "manual" ? [] : d.quick} items={d.mode === "manual" ? d.items : (refs.cats || []).filter((c) => !c.parent_id).map((c) => ({ id: c.id, label: c.name, children: [{ id: `${c.id}k`, label: "… alt kategoriler" }] }))} />;
  } else if (group === "mobile") {
    body = (
      <div className="space-y-3">
        {modeSwitch([["same", "Hamburger menüyle aynı (önerilen)"], ["manual", "Mobil için ayrı menü"]])}
        {d.mode === "manual" && <MenuTreeEditor items={d.items} onChange={(v) => setD({ ...d, items: v })} {...refs} allowIcon />}
      </div>
    );
    preview = d.mode === "manual" ? <TreePreview title="📱 Mobil Menü" items={d.items} /> : <p className="text-xs text-gray-500">Mobilde Hamburger (Yan) Menü içeriği gösterilir.</p>;
  } else if (group === "center") {
    body = (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <label className="block text-sm">Sağdaki kampanya yazısı <span className="text-gray-400 text-xs">(boş = gösterme)</span>
            <input value={d.right_text || ""} onChange={(e) => setD({ ...d, right_text: e.target.value })} className="mt-1 w-full border rounded px-2 py-1.5 text-sm" /></label>
          <label className="block text-sm">Kampanya yazısı bağlantısı
            <div className="mt-1"><LinkPicker value={d.right_link} onChange={(v) => setD({ ...d, right_link: v })} {...refs} /></div></label>
        </div>
      </div>
    );
  }
  return (
    <div className="rounded-xl border bg-white p-4" data-testid={`menu-group-editor-${group}`}>
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 className="font-bold">{MENU_GROUPS.find((g) => g.key === group)?.title}</h2>
        {bar}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_300px]">
        <div>{body}</div>
        <div><div className="text-xs font-semibold text-gray-500 mb-1">Canlı önizleme</div>{preview || <MenuSchematic group={group} />}</div>
      </div>
      {group === "center" && <div className="mt-6 border-t pt-4"><CenterTabsEditor /></div>}
    </div>
  );
}

export default function SiteMenusPage() {
  const [menus, setMenus] = useState(null);
  const initial = new URLSearchParams(window.location.search).get("grup");
  const [group, setGroup] = useState(MENU_GROUPS.some((g) => g.key === initial) ? initial : "departments");
  const refs = useMenuRefs();
  const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("token")}` });
  const load = () => axios.get(`${API}/site-menus`, { headers: headers() }).then((r) => setMenus(r.data)).catch(() => setMenus({}));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const clean = (g) => { const { customized, ...rest } = (menus || {})[g] || {}; return rest; };
  const save = async (g, data) => {
    try { await axios.put(`${API}/site-menus/${g}`, data, { headers: headers() }); toast.success("Menü kaydedildi ve yayınlandı"); await load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Kaydedilemedi"); }
  };
  const reset = async (g) => {
    const ok = window.appConfirm ? await window.appConfirm("Bu menü grubu varsayılana dönsün mü?") : window.confirm("Bu menü grubu varsayılana dönsün mü?");
    if (!ok) return;
    try { await axios.delete(`${API}/site-menus/${g}`, { headers: headers() }); toast.success("Varsayılana döndü"); await load(); } catch { toast.error("Sıfırlanamadı"); }
  };
  return (
    <div data-testid="menu-admin" className="max-w-6xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold">Menü Yönetimi</h1>
        <p className="text-sm text-gray-500 mt-1">Vitrindeki tüm menüler tek ekranda. Bir grup seçin; şemada kırmızıyla gösterilen alan o menünün sitedeki yeridir. “Sitede göster” vitrini o alan vurgulu açar.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="tablist" aria-label="Menü grupları">
        {MENU_GROUPS.map((g) => (
          <div key={g.key} role="tab" aria-selected={group === g.key} tabIndex={0} data-testid={`menu-group-${g.key}`}
            onClick={() => (g.key === "footer" ? null : setGroup(g.key))} onKeyDown={(e) => { if (e.key === "Enter" && g.key !== "footer") setGroup(g.key); }}
            className={`rounded-xl border-2 bg-white p-3 cursor-pointer transition ${group === g.key ? "border-gray-900 shadow" : "border-gray-200 hover:border-gray-400"}`}>
            <div className="flex items-start justify-between gap-2">
              <div>
                <div className="font-semibold text-sm">{g.title}</div>
                <div className="text-[11px] text-gray-500 leading-snug mt-0.5">{g.where}</div>
              </div>
              {menus && menus[g.key]?.customized && <span className="text-[10px] bg-emerald-100 text-emerald-700 rounded px-1.5 py-0.5">özelleştirildi</span>}
            </div>
            <div className="mt-2"><MenuSchematic group={g.key} small /></div>
            <div className="mt-2 flex gap-2 text-xs">
              {g.key === "footer" ? (
                <a href="/admin/footer-tasarim" className="font-semibold underline">Footer Tasarımı'nda düzenle →</a>
              ) : (
                <>
                  <button type="button" className="font-semibold underline" onClick={(e) => { e.stopPropagation(); setGroup(g.key); }}>Düzenle</button>
                  <a href={g.show} target="_blank" rel="noopener noreferrer" className="underline text-gray-600" onClick={(e) => e.stopPropagation()} data-testid={`menu-show-${g.key}`}>Sitede göster ↗</a>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
      {!menus ? <div className="p-6 text-center text-sm text-gray-500">Yükleniyor…</div> : (
        <GroupEditor key={group} group={group} data={clean(group)} refs={refs} onSave={(d) => save(group, d)} onReset={() => reset(group)} />
      )}
    </div>
  );
}
