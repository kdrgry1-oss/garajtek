// Ürün formu — "Kapıda ödemeye kapalı" (Ürün Setleri / kapıda ödeme paketi; ayrı bölüm).
// İşaretli ürün sepetteyse kasada kapıda ödeme sunulmaz ve sunucu (cod_rules.py) reddeder.
// Kategori bazında kapatma: Katalog › Kategoriler › kategori düzenle.
export default function CodExclusionField({ value, onChange }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-4" data-testid="product-cod-section">
      <h4 className="text-sm font-semibold text-gray-900">Kapıda Ödeme</h4>
      <label className="mt-2 flex items-start gap-2 text-sm text-gray-700">
        <input type="checkbox" className="mt-0.5" checked={!!value} onChange={(e) => onChange(e.target.checked)}
          data-testid="product-cod-disabled" />
        <span>
          Kapıda ödemeye kapalı
          <span className="block text-xs text-gray-500">Ağır/hacimli (ambar teslim) ürünler için. Bu ürün sepetteyse kasada kapıda ödeme gösterilmez; ürün sayfasında “kapıda ödemeye uygun değil” yazar.</span>
        </span>
      </label>
    </section>
  );
}
