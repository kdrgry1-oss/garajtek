import { applyRuntimeSiteName } from "./storeInfo";
import { SITE_NAME } from "./brand";

jest.mock("axios", () => ({ get: jest.fn() }));

describe("applyRuntimeSiteName — panel › Site Adı", () => {
  test("build-time adı title / og:site_name / açıklama / JSON-LD'de değiştirir", () => {
    document.head.innerHTML = `<meta property="og:site_name" content="${SITE_NAME}"><meta name="description" content="${SITE_NAME} — online alışveriş">`
      + `<script type="application/ld+json">{"@type":"Organization","name":"${SITE_NAME}"}</script>`;
    document.title = SITE_NAME;
    applyRuntimeSiteName("SYNC-Garaj");
    expect(document.title).toBe("SYNC-Garaj");
    expect(document.querySelector('meta[property="og:site_name"]').getAttribute("content")).toBe("SYNC-Garaj");
    expect(document.querySelector('meta[name="description"]').getAttribute("content")).toBe("SYNC-Garaj — online alışveriş");
    expect(JSON.parse(document.querySelector('script[type="application/ld+json"]').textContent).name).toBe("SYNC-Garaj");
  });

  test("yalnız sonek değişir; ürün adının içindeki kelimeye dokunulmaz", () => {
    document.title = `${SITE_NAME} Rafı | ${SITE_NAME}`;
    applyRuntimeSiteName("SYNC-Garaj");
    expect(document.title).toBe(`${SITE_NAME} Rafı | SYNC-Garaj`);
  });

  test("ad aynıysa / boşsa hiçbir şey yapmaz", () => {
    document.title = SITE_NAME;
    applyRuntimeSiteName("");
    applyRuntimeSiteName(SITE_NAME);
    expect(document.title).toBe(SITE_NAME);
  });
});
