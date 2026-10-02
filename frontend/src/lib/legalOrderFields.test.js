import { fillOrderFields } from "./legalOrderFields";

describe("fillOrderFields", () => {
  const html = "<td>{{alici.ad}}</td><td>{{siparis.toplam}}</td>{{siparis.urunler}}<p>{{sirket.unvan}}</p>";

  it("fills buyer/order fields and escapes values", () => {
    const out = fillOrderFields(html, {
      buyer: { name: "Ali <Veli>" },
      order: { total: 1234.5, items: [{ name: "Lift & Kriko", quantity: 2, price: 100 }] },
    });
    expect(out).toContain("Ali &lt;Veli&gt;");
    expect(out).toContain("1.234,50 TL");
    expect(out).toContain("Lift &amp; Kriko");
    expect(out).toContain("200,00 TL");
    expect(out).toContain("{{sirket.unvan}}"); // firma alanları sunucuda doldurulur
  });

  it("uses a neutral text when there is no order context", () => {
    const out = fillOrderFields(html, null);
    expect(out).not.toMatch(/\{\{(alici|siparis)\./);
    expect(out).toContain("sipariş sırasında doldurulur");
  });
});
