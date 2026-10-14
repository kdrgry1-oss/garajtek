import fs from "fs";
import path from "path";
import { parse } from "@babel/parser";

// Sayfa modülünü (ağır bağımlılıklar) yüklemeden modül düzeyi yardımcıları çalıştır.
const source = fs.readFileSync(path.join(__dirname, "Orders.jsx"), "utf8");
const ast = parse(source, { sourceType: "module", plugins: ["jsx"] });
const pick = (name) => {
  const n = ast.program.body.find((d) => {
    const decl = d.type === "ExportNamedDeclaration" ? d.declaration : d;
    if (!decl) return false;
    if (decl.type === "FunctionDeclaration") return decl.id.name === name;
    return (decl.declarations || []).some((v) => v.id.name === name);
  });
  const decl = n.type === "ExportNamedDeclaration" ? n.declaration : n;
  return source.slice(decl.start, decl.end);
};
const code = ["statusOptions", "NEUTRAL_STATUS_CLASS", "buildStatusOptions", "statusInfoFor",
  "COD_PMS", "paymentMethodLabel"].map(pick).join("\n");
const { buildStatusOptions, statusInfoFor, paymentMethodLabel } = new Function(
  "isOtherChannelOrder", "OTHER_LABEL",
  `${code}\nreturn { buildStatusOptions, statusInfoFor, paymentMethodLabel };`,
)((o) => o.platform === "trendyol", "Pazaryeri");

// Panel ↔ vitrin senkronu: Ayarlar > Sipariş Durumları özel durumları panel menüsünde
// seçilebilir olmalı; bilinmeyen durum 'Onay Bekliyor' gösterilmemeli; kapıda ödeme etiketi.
const api = [
  { key: "pending", label: "Onay Bekliyor", active: true },
  { key: "shipped", label: "Kargoya Verildi", active: true },
  { key: "preparing", label: "Hazırlanıyor", active: false },
  { key: "sync_ozel", label: "SYNC Özel Durum", active: true, is_custom: true },
  { key: "pasif_ozel", label: "Pasif Özel", active: false, is_custom: true },
];

test("custom statuses appear in the status menus", () => {
  const { all, visible } = buildStatusOptions(api);
  expect(all.map((s) => s.value)).toEqual(expect.arrayContaining(["sync_ozel", "pasif_ozel"]));
  const vis = visible.map((s) => s.value);
  expect(vis).toEqual(expect.arrayContaining(["pending", "shipped", "sync_ozel"]));
  expect(vis).not.toContain("preparing");
  expect(vis).not.toContain("pasif_ozel");
  expect(all.find((s) => s.value === "sync_ozel").label).toBe("SYNC Özel Durum");
});

test("without settings every static status is selectable", () => {
  const { all, visible } = buildStatusOptions([]);
  expect(visible).toEqual(all);
  expect(all.some((s) => s.value === "cancel_refunded")).toBe(true);
});

test("unknown status is not shown as 'Onay Bekliyor'", () => {
  const { all } = buildStatusOptions(api);
  expect(statusInfoFor("sync_ozel", all).label).toBe("SYNC Özel Durum");
  expect(statusInfoFor("bilinmeyen").label).toBe("bilinmeyen");
  expect(statusInfoFor("pending").label).toBe("Onay Bekliyor");
});

test("cash on delivery aliases get a payment label", () => {
  for (const pm of ["cash_on_delivery", "kapida", "kapida_odeme", "cod"]) {
    expect(paymentMethodLabel({ payment_method: pm })).toBe("Kapıda Ödeme");
    expect(paymentMethodLabel({ payment_method: pm }, true)).toBe("Kapıda");
  }
  expect(paymentMethodLabel({ payment_method: "bank_transfer" })).toBe("Havale/EFT");
  expect(paymentMethodLabel({ payment_method: "credit_card" })).toBe("Kredi Kartı");
  expect(paymentMethodLabel({ payment_method: "", platform: "trendyol" })).toBe("Pazaryeri");
});

test("order detail summary shows the COD fee row", () => {
  expect(source).toMatch(/Number\(selectedOrder\.cod_fee\) > 0/);
  expect(source).toContain("Kapıda Ödeme Hizmet Bedeli");
});
