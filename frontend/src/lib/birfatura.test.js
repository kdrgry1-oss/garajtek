import { nextGroupId, validateStatusGroups, toggleStatus, parseHosts, invoiceIconState, invoiceTypeLabel,
  orderInvoiceInfo, fmtTL } from "./birfatura";

test("invoice icon state: issued > direct > panel", () => {
  expect(invoiceIconState({ invoice_pdf_url: "https://x/y.pdf" }, true)).toBe("issued");
  expect(invoiceIconState({ invoice_number: "A1" }, false)).toBe("issued");
  expect(invoiceIconState({ invoice: { invoice_number: "A1" } }, true)).toBe("issued");
  expect(invoiceIconState({ invoice_issued: true }, true)).toBe("issued");
  expect(invoiceIconState({}, true)).toBe("direct");
  expect(invoiceIconState({}, false)).toBe("panel");
  expect(orderInvoiceInfo({ invoice_link: "https://l" }).pdf).toBe("https://l");
});

test("invoice type labels and money format", () => {
  expect(invoiceTypeLabel("e-arsiv")).toBe("e-Arşiv");
  expect(invoiceTypeLabel("EFATURA")).toBe("e-Fatura");
  expect(invoiceTypeLabel("manual")).toBe("");
  expect(fmtTL(1160)).toBe("1.160,00 TL");
  expect(fmtTL(undefined)).toBe("-");
});

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
