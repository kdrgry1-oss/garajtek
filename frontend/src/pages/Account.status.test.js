import fs from "fs";
import path from "path";
import { parse } from "@babel/parser";

// Sayfa modülünü (ağır bağımlılıklar) yüklemeden modül düzeyi rozet yardımcısını çalıştır.
const source = fs.readFileSync(path.join(__dirname, "Account.jsx"), "utf8");
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
const icon = () => null;
const orderStatusBadge = new Function(
  "Clock", "CheckCircle", "Package", "Truck", "X",
  `${["ORDER_STATUS", "NEUTRAL_STATUS", "orderStatusBadge"].map(pick).join("\n")}\nreturn orderStatusBadge;`,
)(icon, icon, icon, icon, icon);

// Hesabım rozeti: bilinmeyen / panel-tanımlı durum 'Onay Bekliyor'a düşmemeli.
test("cancel_refunded and payment_failed have their own labels", () => {
  expect(orderStatusBadge({ status: "cancel_refunded" }).label).toBe("İptal Bedeli İade Edildi");
  expect(orderStatusBadge({ status: "payment_failed" }).label).toBe("Ödeme Alınamadı");
});

test("panel custom status uses backend customer label", () => {
  const b = orderStatusBadge({ status: "sync_ozel", status_label: "SYNC Özel Müşteri", status_label_custom: true });
  expect(b.label).toBe("SYNC Özel Müşteri");
  expect(b.icon).toBeTruthy();
});

test("panel label override replaces the short storefront label", () => {
  expect(orderStatusBadge({ status: "shipped", status_label: "SYNC Kargo", status_label_custom: true }).label)
    .toBe("SYNC Kargo");
  expect(orderStatusBadge({ status: "shipped", status_label: "Siparişiniz Kargoya Verildi" }).label)
    .toBe("Kargoda");
});

test("unknown status without label never shows 'Onay Bekliyor'", () => {
  expect(orderStatusBadge({ status: "garip" }).label).toBe("garip");
});
