import { act } from "react";
import { createRoot } from "react-dom/client";
import UrlImport, { URL_PLACEHOLDER } from "./UrlImport";
import { navigationGroups } from "../../lib/adminNav";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
// react-router v7 paket "exports" eşlemesi CRA jest'inde çözülmüyor → yalın Link taklidi
jest.mock("react-router-dom", () => ({
  // eslint-disable-next-line jsx-a11y/anchor-has-content
  Link: ({ to, children, ...rest }) => <a href={to} {...rest}>{children}</a>,
}), { virtual: true });

const axios = require("axios");
const { toast } = require("sonner");

const CATS = [
  { id: "c1", name: "Liftler", parent_id: null, sort_order: 1 },
  { id: "c2", name: "İki Sütunlu Liftler", parent_id: "c1", sort_order: 1 },
];
const DONE_JOB = {
  id: "job1", status: "done",
  counters: { found: 3, imported: 2, updated: 0, failed: 1, skipped: 0, images: 4 },
  url_log: [{ url: "https://www.grayzer.net/kategori/liftler", kind: "listing", status: "ok", found: 3, message: "" }],
  items: [
    { source_url: "https://www.grayzer.net/urun/a", status: "imported", product_id: "p1", name: "4 Ton Lift", slug: "4-ton-lift-1001",
      is_active: true, price: 129900, images: 2, category: "İki Sütunlu Liftler", category_source: "otomatik", warnings: [] },
    { source_url: "https://www.grayzer.net/urun/b", status: "failed", error: "HTTP 404", warnings: [] },
  ],
};

describe("URL'den Ürün Aktar", () => {
  let container;
  let root;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; });
  beforeEach(() => {
    jest.useFakeTimers();
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    window.confirm = jest.fn(() => true);
    axios.get.mockImplementation((url) => {
      if (url.endsWith("/categories")) return Promise.resolve({ data: CATS });
      if (url.endsWith("/admin/url-import/status")) return Promise.resolve({ data: { products: 5, files: 9, hosts: { "grayzer.net": 5 }, running_job: null } });
      if (url.includes("/admin/url-import/jobs/job1")) return Promise.resolve({ data: DONE_JOB });
      return Promise.reject(new Error("unexpected " + url));
    });
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.clearAllMocks();
    jest.useRealTimers();
  });

  const flush = async () => { await act(async () => { for (let i = 0; i < 5; i++) await Promise.resolve(); }); };
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  const render = async () => {
    await act(async () => root.render(<UrlImport />));
    await flush();
  };
  const setValue = async (el, value) => {
    const proto = el.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(proto, "value").set.call(el, value);
    await act(async () => { el.dispatchEvent(new Event("input", { bubbles: true })); });
  };

  test("menüde Katalog altında yer alır", () => {
    const katalog = navigationGroups.find((g) => g.key === "katalog");
    expect(katalog.children.map((c) => c.path)).toContain("/admin/urlden-urun-aktar");
  });

  test("uyarı, örnek yer tutucu, zorunlu demo ve sayaç gösterilir", async () => {
    await render();
    expect(q("url-import-warning").textContent).toContain("Bu araçla aktarılan içerik ve görseller kaynak sitelere aittir; yalnız geçici demo amaçlı kullanın, canlı satıştan önce kaldırın.");
    const ta = q("url-import-urls");
    expect(ta.getAttribute("placeholder")).toBe(URL_PLACEHOLDER);
    expect(URL_PLACEHOLDER).toContain("https://www.grayzer.net/kategori/liftler");
    expect(URL_PLACEHOLDER).toContain("https://www.algikitelli.com.tr/");
    expect(ta.value).toBe(""); // örnekler yalnız yer tutucu
    expect(q("url-import-demo").checked).toBe(true);
    expect(q("url-import-demo").disabled).toBe(true);
    expect(q("url-import-count").textContent).toBe("5");
    const opts = Array.from(q("url-import-category").querySelectorAll("option")).map((o) => o.textContent);
    expect(opts).toEqual(["Eşleşmezse: kategorisiz", "Liftler", "— İki Sütunlu Liftler"]);
  });

  test("işi başlatır, ilerlemeyi yoklar ve sonuç tablosunda düzenleme linki verir", async () => {
    axios.post.mockResolvedValue({ data: { job_id: "job1" } });
    await render();
    await setValue(q("url-import-urls"), "https://www.grayzer.net/kategori/liftler");
    await setValue(q("url-import-multiplier"), "0,95");
    await act(async () => { q("url-import-form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
    await flush();
    expect(axios.post).toHaveBeenCalledTimes(1);
    const [url, body] = axios.post.mock.calls[0];
    expect(url).toMatch(/\/admin\/url-import\/jobs$/);
    expect(body).toMatchObject({ urls: "https://www.grayzer.net/kategori/liftler", category_mode: "auto", max_per_category: 30,
      import_images: true, price_multiplier: "0,95", publish: true, demo: true });
    expect(q("url-import-status").textContent).toBe("Tamamlandı");
    expect(q("url-import-counters").textContent).toContain("2");
    const link = q("url-import-edit-link");
    expect(link.getAttribute("href")).toBe("/admin/urunler/p1");
    expect(q("url-import-results").textContent).toContain("HTTP 404");
    expect(q("url-import-urllog").textContent).toContain("Liste / kategori");
  });

  test("sabit kategori modunda kategori seçilmeden başlatmaz", async () => {
    await render();
    await setValue(q("url-import-urls"), "https://x.example/");
    await act(async () => { q("url-import-mode-fixed").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    await act(async () => { q("url-import-form").dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })); });
    expect(axios.post).not.toHaveBeenCalled();
    expect(toast.error).toHaveBeenCalledWith("Bir kategori seçin");
  });

  test("İçe aktarılanları sil onay sonrası DELETE çağırır", async () => {
    axios.delete.mockResolvedValue({ data: { removed_products: 5, removed_files: 9 } });
    await render();
    await act(async () => { q("url-import-remove").dispatchEvent(new MouseEvent("click", { bubbles: true })); });
    await flush();
    expect(window.confirm).toHaveBeenCalled();
    expect(axios.delete.mock.calls[0][0]).toMatch(/\/admin\/url-import\/products$/);
    expect(toast.success).toHaveBeenCalledWith("Silindi: 5 ürün, 9 görsel");
  });
});
