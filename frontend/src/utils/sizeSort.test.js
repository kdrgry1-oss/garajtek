import { sortLikeSize } from "./sizeSort";

test("ölçü (NxM mm) seçenekleri sayısal sıralanır", () => {
  const api = ["14x15 mm", "18x19 mm", "20x22 mm", "16x17 mm", "8x9 mm", "6x7 mm", "10x11 mm", "12x13 mm"];
  expect(sortLikeSize(api)).toEqual(["6x7 mm", "8x9 mm", "10x11 mm", "12x13 mm", "14x15 mm", "16x17 mm", "18x19 mm", "20x22 mm"]);
});

test("standart bedenler ve sayısal bedenler bozulmaz", () => {
  expect(sortLikeSize(["XL", "S", "M/L", "M"])).toEqual(["S", "M", "M/L", "XL"]);
  expect(sortLikeSize(["40", "36", "38"])).toEqual(["36", "38", "40"]);
});

test("metin içi sayılar sayı gibi karşılaştırılır (M10 > M8)", () => {
  expect(sortLikeSize(["M10 Cıvata", "M8 Cıvata", "M12 Cıvata"])).toEqual(["M8 Cıvata", "M10 Cıvata", "M12 Cıvata"]);
});
