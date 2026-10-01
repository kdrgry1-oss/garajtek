import { nextGroupId, validateStatusGroups, toggleStatus, parseHosts } from "./birfatura";

test("new group ids never reuse an existing id", () => {
  expect(nextGroupId([])).toBe(1);
  expect(nextGroupId([{ id: 1 }, { id: 7 }, { id: 3 }])).toBe(8);
});

test("status groups are validated before saving", () => {
  expect(validateStatusGroups([{ id: 1, name: "Onaylandı", statuses: ["confirmed"] }])).toEqual([]);
  expect(validateStatusGroups([])).toHaveLength(1);
  const errs = validateStatusGroups([
    { id: 1, name: "A", statuses: ["confirmed"] },
    { id: 1, name: "", statuses: [] },
  ]);
  expect(errs.join(" ")).toMatch(/tekrar/);
  expect(errs.join(" ")).toMatch(/ad gerekli/);
  expect(errs.join(" ")).toMatch(/en az bir sipariş durumu/);
});

test("toggleStatus adds and removes without mutating", () => {
  const g = { id: 1, name: "A", statuses: ["confirmed"] };
  const added = toggleStatus(g, "shipped");
  expect(added.statuses).toEqual(["confirmed", "shipped"]);
  expect(g.statuses).toEqual(["confirmed"]);
  expect(toggleStatus(added, "confirmed").statuses).toEqual(["shipped"]);
});

test("trusted hosts parse from commas and lines", () => {
  expect(parseHosts("birfatura.com, *.birfatura.com\n\n X.COM ")).toEqual(["birfatura.com", "*.birfatura.com", "x.com"]);
});
