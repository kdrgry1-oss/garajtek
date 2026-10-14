import { initialsOf } from "./initials";

test("baş harfler Türkçe kurala göre büyütülür", () => {
  expect(initialsOf({ first_name: "ilker", last_name: "şahin" })).toBe("İŞ");
  expect(initialsOf({ first_name: "ırmak", last_name: "çelik" })).toBe("IÇ");
  expect(initialsOf({ email: "ilker@example.com" })).toBe("İL");
  expect(initialsOf({})).toBe("FA");
});
