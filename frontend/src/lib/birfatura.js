// BirFatura panel sayfası için saf yardımcılar (test edilebilir).

/** Yeni durum grubu Id'si: mevcutların en büyüğü + 1 (Id'ler BirFatura'da saklandığı için asla yeniden kullanılmaz). */
export function nextGroupId(groups) {
  const ids = (groups || []).map((g) => Number(g?.id) || 0);
  return (ids.length ? Math.max(...ids) : 0) + 1;
}

/** Kaydetmeden önce durum gruplarını doğrular; hata mesajı listesi döner (boşsa geçerli). */
export function validateStatusGroups(groups) {
  const errs = [];
  if (!Array.isArray(groups) || groups.length === 0) {
    errs.push("En az bir durum grubu gerekli.");
    return errs;
  }
  const seen = new Set();
  groups.forEach((g) => {
    const id = Number(g?.id);
    if (!Number.isInteger(id) || id <= 0) errs.push(`Geçersiz grup Id: ${g?.id}`);
    else if (seen.has(id)) errs.push(`Grup Id tekrar ediyor: ${id}`);
    seen.add(id);
    if (!String(g?.name || "").trim()) errs.push(`Grup ${g?.id}: ad gerekli.`);
    if (!Array.isArray(g?.statuses) || g.statuses.length === 0) errs.push(`"${g?.name || g?.id}": en az bir sipariş durumu seçin.`);
  });
  return errs;
}

/** Bir grubun durum listesinde anahtarı aç/kapat (değişmez kopya döner). */
export function toggleStatus(group, key) {
  const has = (group.statuses || []).includes(key);
  return { ...group, statuses: has ? group.statuses.filter((s) => s !== key) : [...(group.statuses || []), key] };
}

/** "birfatura.com, *.birfatura.com" / satır satır → temiz liste. */
export function parseHosts(text) {
  return String(text || "")
    .split(/[\n,]/)
    .map((h) => h.trim().toLowerCase())
    .filter(Boolean);
}
