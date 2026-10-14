import "../components/pageblocks/testMocks";
import { mergeContact, applyLazyImages } from "./siteDesign";

describe("mergeContact — tek iletişim kaynağı", () => {
  test("Genel Ayarlar (tenant) önceliklidir; Sayfa Tasarımı yalnız boş alanları doldurur", () => {
    const sc = { phone: "0543 276 89 73", address: "Eski Adres", whatsapp: "0543 276 89 73", email: "", phone_2: "0212 1", working_hours: "09-18" };
    const info = { phone: "0212 999 88 77", address: "SYNC Adres Sok. No:1", email: "sync@e2e.local", whatsapp: "" };
    expect(mergeContact(sc, info)).toEqual({
      phone: "0212 999 88 77", phone2: "0212 1", email: "sync@e2e.local",
      whatsapp: "0543 276 89 73", address: "SYNC Adres Sok. No:1", hours: "09-18",
    });
  });
  test("tenant boşsa site_contact kullanılır", () => {
    expect(mergeContact({ phone: "1" }, {}).phone).toBe("1");
  });
});

describe("applyLazyImages — Tema › Görselleri gerektikçe yükle", () => {
  afterEach(() => { applyLazyImages(true); document.body.innerHTML = ""; });
  test("kapalıyken mevcut ve sonradan eklenen lazy görseller eager olur", async () => {
    document.body.innerHTML = '<img loading="lazy" id="a" />';
    applyLazyImages(false);
    expect(document.getElementById("a").getAttribute("loading")).toBe("eager");
    const img = document.createElement("img");
    img.setAttribute("loading", "lazy");
    document.body.appendChild(img);
    await new Promise((r) => setTimeout(r, 0));
    expect(img.getAttribute("loading")).toBe("eager");
  });
  test("açıkken dokunulmaz", () => {
    document.body.innerHTML = '<img loading="lazy" id="b" />';
    applyLazyImages(true);
    expect(document.getElementById("b").getAttribute("loading")).toBe("lazy");
  });
});
