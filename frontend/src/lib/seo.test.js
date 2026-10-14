/**
 * SPA gezinmesinde SEO meta sızıntısı (e2e #43) ve boş panel değerinin
 * mevcut etiketleri silmemesi (#45) regresyonları.
 */
import { resetSeoDefaults, setPageSeo, applyRuntimeSeo, routeOwnsSeo } from "./seo";

function head(html) {
  document.head.innerHTML = html;
}
const attr = (sel, a = "content") => document.head.querySelector(sel)?.getAttribute(a);

beforeEach(() => {
  head(`
    <title>Mağaza</title>
    <meta name="description" content="Varsayılan açıklama" />
    <meta name="robots" content="index, follow, max-image-preview:large" />
    <link rel="canonical" href="https://x/" />
    <meta property="og:image" content="/og-image.jpg" />
    <script type="application/ld+json" data-seo="edge">{}</script>
  `);
  document.title = "Mağaza";
});

test("önceki sayfanın noindex/title/canonical değeri gezinmede sıfırlanır", () => {
  setPageSeo({ title: "Ürün A", description: "Ürün açıklaması", canonical: "/urun/a", robots: "noindex,nofollow" });
  expect(document.title).toBe("Ürün A");
  expect(attr('meta[name="robots"]')).toBe("noindex,nofollow");

  resetSeoDefaults("/sayfa/kvkk");
  expect(document.title).not.toBe("Ürün A");
  expect(attr('meta[name="robots"]')).toBe("index, follow, max-image-preview:large");
  expect(attr('meta[name="description"]')).not.toBe("Ürün açıklaması");
  expect(attr('link[rel="canonical"]', "href")).toMatch(/\/sayfa\/kvkk$/);
  expect(document.head.querySelector('script[data-seo="edge"]')).toBeNull();
});

test("boş açıklama/görsel mevcut etiketi boşaltmaz", () => {
  setPageSeo({ title: "", description: "", ogImage: "" });
  expect(document.title).toBe("Mağaza");
  expect(attr('meta[name="description"]')).toBe("Varsayılan açıklama");
  expect(attr('meta[property="og:image"]')).toBe("/og-image.jpg");
});

test("applyRuntimeSeo panel değerlerini uygular, boş alanları atlar", async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ found: true, title: "SYNC- Ana Baslik", canonical: "https://x/", robots: "index,follow" }),
  });
  await applyRuntimeSeo("/");
  expect(document.title).toBe("SYNC- Ana Baslik");
  expect(attr('meta[name="description"]')).toBe("Varsayılan açıklama");
});

test("meta'yı kendisi uygulayan rotalar", () => {
  expect(routeOwnsSeo("/urun/x")).toBe(true);
  expect(routeOwnsSeo("/kategori/x")).toBe(true);
  expect(routeOwnsSeo("/sayfa/kvkk")).toBe(true);
  expect(routeOwnsSeo("/admin/seo")).toBe(true);
  expect(routeOwnsSeo("/")).toBe(false);
  expect(routeOwnsSeo("/sss")).toBe(false);
});
