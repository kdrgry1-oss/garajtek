/**
 * Yeni şifre için en kısa uzunluk. Sunucu (backend/routes/auth.py: register,
 * convert-guest-order, change-password, reset-password) 8 karakter istiyor;
 * kayıt / şifre değiştirme / misafir→üye ekranları bu sabiti kullanır ki
 * ekrandaki kural ile sunucu mesajı birbirini tutsun.
 * Not: GİRİŞ alanına uygulanmaz — eski hesapların 6-7 karakterlik şifreleri olabilir.
 */
export const PASSWORD_MIN_LENGTH = 8;

export const passwordTooShort = (pw) => String(pw || "").length < PASSWORD_MIN_LENGTH;
