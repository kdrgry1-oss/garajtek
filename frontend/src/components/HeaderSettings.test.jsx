// Sayfa Tasarımı › Genel Alanlar ayarlarının vitrin header'ına bağlanması (e2e 2. tur #31) +
// SSS taksit cevabı (kart kapalıyken vaat yok) + WhatsApp sepet mesajı.
import "./pageblocks/testMocks";
import { deptBtnClass, searchLook } from "./Header";
import { faqForPayment } from "../pages/FAQ";
import { cartMessage } from "./cod/WhatsAppOrderButton";

describe("Dikey menü › Başlık stili", () => {
  test("varsayılan yuvarlak ana renk; köşeli; şeffaf üst çizgili ana renk sınıfı taşımaz", () => {
    expect(deptBtnClass(undefined)).toMatch(/btn-primary rounded-top-lg/);
    expect(deptBtnClass("primary_square")).toMatch(/btn-primary rounded-0/);
    expect(deptBtnClass("primary_square")).not.toMatch(/rounded-top-lg/);
    expect(deptBtnClass("transparent_topline")).not.toMatch(/btn-primary/);
    expect(deptBtnClass("transparent_topline")).toMatch(/bg-transparent/);
  });
});

describe("Header › Arama › Görünüm", () => {
  test("varsayılan (pill_bordered) eski davranışı korur: ana sayfa çerçeveli, iç sayfa şerit üstü", () => {
    expect(searchLook("pill_bordered", false).look).toBe("bordered");
    expect(searchLook("pill_bordered", true).look).toBe("band");
    expect(searchLook(undefined, false).input).toMatch(/border-primary/);
  });
  test("pill_on_band ana sayfada da şerit üstü; underline köşesiz alt çizgili", () => {
    expect(searchLook("pill_on_band", false).look).toBe("band");
    const u = searchLook("underline", false);
    expect(u.look).toBe("underline");
    expect(u.input).toMatch(/rounded-0/);
    expect(u.inputStyle.borderBottom).toBeTruthy();
  });
});

describe("SSS › taksit cevabı", () => {
  const data = [{ id: "odeme", label: "ÖDEME", items: [
    { q: "Taksit seçeneğiniz var mı?", a: "…taksit seçeneklerini ödeme ekranında görebilirsiniz.", card: true },
    { q: "KDV?", a: "dahil" }] }];
  test("kart açıkken orijinal cevap", () => {
    expect(faqForPayment(data, true)[0].items[0].a).toMatch(/görebilirsiniz/);
  });
  test("kart kapalıyken taksit vaadi yok; diğer cevaplar aynı", () => {
    const out = faqForPayment(data, false)[0].items;
    expect(out[0].a).toMatch(/sunulmamaktadır/);
    expect(out[1].a).toBe("dahil");
  });
  test("bilinmiyorken nötr (koşullu) metin", () => {
    expect(faqForPayment(data, null)[0].items[0].a).toMatch(/aktifse/);
  });
});

describe("WhatsApp sepet mesajı", () => {
  test("Toplam, verilen (sepet sayfasıyla aynı: kargo dahil) tutarı yazar", () => {
    const msg = cartMessage([{ name: "Kriko", quantity: 2, size: "3T" }], 652.42);
    expect(msg).toMatch(/• Kriko \(3T\) × 2/);
    expect(msg).toMatch(/Toplam \(kargo dahil\): 652,42 TL/);
  });
});
