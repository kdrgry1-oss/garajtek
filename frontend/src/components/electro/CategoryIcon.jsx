// Kategori ikonu — kategori kaydında `icon` alanı varsa onu kullanır:
//   • "ec-..." / "ec ec-..."  → Electro ikon fontu
//   • "fa-..." / "fas fa-..." → Font Awesome 5 (tema ile birlikte gelir)
//   • http(s) / "/" ile başlayan → görsel
// Yoksa kategori adından (garaj ekipmanı sözlüğü) tahmin edilir; o da yoksa genel ikon.
const GUESS = [
  [/lift|kald[ıi]r[ıa]c/i, "fas fa-car-side"],
  [/kompres[oö]r|hava/i, "fas fa-wind"],
  [/lastik|jant|balans|tire/i, "fas fa-life-ring"],
  [/servis ekipman|oto servis|bak[ıi]m/i, "fas fa-cogs"],
  [/araba|tezgah|dolap|ta[şs][ıi]ma|seyyar/i, "fas fa-toolbox"],
  [/lokma|soket|cırcır|c[ıi]rc[ıi]r/i, "fas fa-cog"],
  [/el alet|anahtar|pense|tornavida/i, "fas fa-wrench"],
  [/ak[üu]|[şs]arj|elektrik|test/i, "fas fa-car-battery"],
  [/ya[ğg]|s[ıi]v[ıi]|pompa|gres/i, "fas fa-oil-can"],
  [/kaynak|torch|ate[şs]/i, "fas fa-fire"],
  [/pnömatik|pnomatik|havalı/i, "fas fa-tachometer-alt"],
  [/[öo]l[çc][üu]m|diagnost|te[şs]his/i, "fas fa-tachometer-alt"],
  [/boya|sprey/i, "fas fa-spray-can"],
  [/kriko|vin[çc]|pres/i, "fas fa-truck-pickup"],
  [/hırdavat|h[ıi]rdavat|sarf/i, "fas fa-screwdriver"],
  [/çekiç|cekic|hammer/i, "fas fa-hammer"],
];

export function iconClassFor(cat) {
  const raw = String((cat && cat.icon) || "").trim();
  if (raw && !/^(https?:)?\//.test(raw)) {
    if (/^ec[\s-]/.test(raw)) return raw.startsWith("ec ") ? raw : `ec ${raw}`;
    if (/^fa[bsr]?\s/.test(raw)) return raw;
    if (/^fa-/.test(raw)) return `fas ${raw}`;
    return raw;
  }
  const name = String((cat && cat.name) || "");
  for (const [re, cls] of GUESS) if (re.test(name)) return cls;
  return "fas fa-tools";
}

export default function CategoryIcon({ cat, className = "" }) {
  const raw = String((cat && cat.icon) || "").trim();
  if (raw && /^(https?:)?\//.test(raw)) {
    return <img src={raw} alt="" className={className} width="20" height="20" loading="lazy" style={{ width: 20, height: 20, objectFit: "contain" }} />;
  }
  return <i className={`${iconClassFor(cat)} ${className}`} aria-hidden="true" />;
}
