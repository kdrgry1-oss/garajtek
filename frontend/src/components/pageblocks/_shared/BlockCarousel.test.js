import { perViewAt, perViewVars } from "./BlockCarousel";

test("kırılım tablosu: min-width kuralı, standart dışı kırılımlar (1400, 480) da çalışır", () => {
  const pv = { 0: 2, 480: 3, 992: 3, 1200: 4, 1400: 5 };
  expect(perViewAt(pv, 390)).toBe(2);
  expect(perViewAt(pv, 500)).toBe(3);
  expect(perViewAt(pv, 1440)).toBe(5);
  expect(perViewAt(pv, 1300)).toBe(4);
  expect(perViewVars({ 0: 1, 768: 2 })["--el-n-md"]).toBe(2);
});
