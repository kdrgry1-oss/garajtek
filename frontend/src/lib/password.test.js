import { PASSWORD_MIN_LENGTH, passwordTooShort } from "./password";

test("şifre kuralı sunucuyla aynı: en az 8 karakter", () => {
  expect(PASSWORD_MIN_LENGTH).toBe(8);
  expect(passwordTooShort("abc1234")).toBe(true);   // 7 karakter → sunucu 400 döner
  expect(passwordTooShort("abc12345")).toBe(false);
  expect(passwordTooShort("")).toBe(true);
  expect(passwordTooShort(undefined)).toBe(true);
});
