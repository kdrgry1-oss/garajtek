import { fitTabs } from "./navFit";

const tab = (id, style = "normal") => ({ id, label: id, style });

describe("fitTabs", () => {
  test("genişlik bilinmiyorsa yalnız en fazla sayısı uygulanır", () => {
    const tabs = Array.from({ length: 15 }, (_, i) => tab(`t${i}`));
    expect([...fitTabs(tabs, [], 0, 0, 7)]).toEqual([0, 1, 2, 3, 4, 5, 6]);
  });

  test("sığmayan sekmeler dışarıda kalır, 'Daha Fazla' için yer ayrılır", () => {
    const tabs = [tab("a"), tab("b"), tab("c"), tab("d")];
    // 100'er px, bütçe 330, more 60 → a,b (200+60=260), c ile 300+60=360 > 330
    expect([...fitTabs(tabs, [100, 100, 100, 100], 330, 60, 10)]).toEqual([0, 1]);
    // hepsi sığarsa "Daha Fazla" gerekmez
    expect([...fitTabs(tabs, [100, 100, 100, 100], 400, 60, 10)]).toEqual([0, 1, 2, 3]);
  });

  test("SALE sekmesi sonda olsa bile önceliklidir (uzun eski menü)", () => {
    const tabs = [...Array.from({ length: 14 }, (_, i) => tab(`cat${i}`)), tab("sale", "sale")];
    const vis = fitTabs(tabs, tabs.map(() => 120), 870, 110, 7);
    expect(vis.has(14)).toBe(true);
    expect(vis.size).toBe(6); // 6*120 + 110 = 830 ≤ 870
  });
});
