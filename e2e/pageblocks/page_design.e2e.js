// Sayfa Tasarımı uçtan uca testleri (SPEC §8.12 / §9). Çalışan bir backend + build edilmiş vitrin gerekir.
//
//   BASE=http://localhost:8348 API=http://localhost:8414/api TOKEN=<admin jwt> node e2e/pageblocks/page_design.e2e.js
//   (Playwright: PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers; paket yolu PW_MODULE ile değiştirilebilir)
//
// Doğrulananlar:
//   a) panelde alan değişince iframe önizlemesi anında güncellenir (taslak; vitrin değişmez)
//   b) Yayınla → vitrinde görünür
//   c) önizleme == vitrin (blok blok ekran görüntüsü bayt-eşit, hero hariç: otomatik oynayan slider)
//   d) bloğu şablon varsayılanına sıfırla
//   e) geri al + revizyon geri yükleme
//   f) data-pd-field denetimi: vitrindeki blok metinlerinin hepsi panelden ya da katalogdan gelir
const assert = require("assert");
const { chromium } = require(process.env.PW_MODULE || "/opt/node22/lib/node_modules/playwright");

const BASE = process.env.BASE;
const API = process.env.API || `${BASE}/api`;
const TOKEN = process.env.TOKEN;
if (!BASE || !TOKEN) { console.error("BASE ve TOKEN gerekli"); process.exit(2); }
const H = { Authorization: `Bearer ${TOKEN}`, "Content-Type": "application/json" };
const api = async (method, path, body) => {
  const r = await fetch(`${API}${path}`, { method, headers: H, body: body ? JSON.stringify(body) : undefined });
  const t = await r.text();
  return { status: r.status, data: t ? JSON.parse(t) : null };
};

let failures = 0;
async function step(name, fn) {
  try { await fn(); console.log(`✓ ${name}`); } catch (e) { failures += 1; console.log(`✕ ${name}\n   ${e && e.stack ? e.stack.split("\n").slice(0, 3).join("\n   ") : e}`); }
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await ctx.addInitScript((t) => {
    try {
      localStorage.setItem("store_cookie_consent", JSON.stringify({ necessary: true, analytics: false, marketing: false, ts: new Date().toISOString(), v: 1 }));
      if (location.pathname.startsWith("/admin") || location.pathname.startsWith("/onizleme")) localStorage.setItem("token", t);
      else localStorage.removeItem("token");
      localStorage.removeItem("home_layout_v2");
    } catch (e) { /* yoksay */ }
  }, TOKEN);
  const page = await ctx.newPage();
  page.on("pageerror", (e) => console.log("  PAGEERR", e.message));

  // temiz başlangıç: taslak yok
  await api("DELETE", "/page-design/home/draft");
  const start = await api("GET", "/page-design/home");
  const startRev = start.data.published.rev;
  const adsIndex = start.data.published.blocks.findIndex((b) => b.type === "ads_block");
  assert(adsIndex >= 0, "ads_block yayında olmalı");
  const MARK = `E2E Başlık ${Date.now()}`;

  await page.goto(`${BASE}/admin/sayfa-tasarimi`, { waitUntil: "networkidle" });
  const frame = () => page.frame({ url: /\/onizleme\/sayfa\/home/ });
  await page.waitForSelector('[data-testid="block-row-0"]');
  await page.waitForFunction(() => document.querySelector('[data-testid="preview-frame"]')?.contentDocument?.querySelector("[data-pd-block]"));

  await step("a) alan değişikliği önizlemeye anında yansır, vitrin değişmez", async () => {
    await page.click(`[data-testid="block-row-${adsIndex}"] button.flex-1`);
    await page.click('[data-testid="repeater-items"] button[aria-expanded="false"]');
    const rt = page.locator('[data-testid="rt-text"]').first();
    await rt.click();
    await page.keyboard.press("Control+A");
    await page.keyboard.type(MARK);
    await frame().waitForFunction((m) => document.body.innerText.includes(m), MARK, { timeout: 5000 });
    const pub = await (await fetch(`${API}/page-blocks?page=home`)).text();
    assert(!pub.includes(MARK), "taslak vitrine sızmamalı");
    await page.waitForFunction(() => /otomatik kaydedildi/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 10000 });
  });

  await step("b) Yayınla → vitrinde görünür", async () => {
    await page.click('[data-testid="publish"]');
    await page.waitForFunction(() => /Yayındaki sürüm/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 15000 });
    const sf = await ctx.newPage();
    await sf.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
    await sf.waitForFunction((m) => document.body.innerText.includes(m), MARK, { timeout: 10000 });
    await sf.close();
  });

  await step("c) önizleme == vitrin (blok ekran görüntüleri bayt-eşit)", async () => {
    const shots = async (url) => {
      const p = await ctx.newPage();
      await p.goto(url, { waitUntil: "networkidle" });
      await p.waitForSelector("[data-pd-block]");
      // yapışkan header şeridi kaydırmaya göre belirir → karşılaştırmada gizlenir
      await p.addStyleTag({ content: ".el-sticky-bar{display:none!important}" });
      await p.waitForTimeout(1500);
      const ids = await p.$$eval("[data-pd-block]", (els) => els.map((e) => e.getAttribute("data-pd-block")));
      const out = {};
      for (const id of ids) {
        const el = await p.$(`[data-pd-block="${id}"]`);
        const type = await el.getAttribute("data-block-type");
        if (type === "hero_slider") continue;
        await el.scrollIntoViewIfNeeded();
        await p.mouse.move(0, 0);
        await p.waitForTimeout(150);
        out[id] = await el.screenshot({ mask: [p.locator('[data-testid="deal-countdown"]')] });
      }
      await p.close();
      return out;
    };
    const a = await shots(`${BASE}/?pd-noanim=1`);
    const b = await shots(`${BASE}/onizleme/sayfa/home?pd-noanim=1`);
    assert.deepStrictEqual(Object.keys(b), Object.keys(a), "aynı bloklar");
    const diff = Object.keys(a).filter((k) => Buffer.compare(a[k], b[k]) !== 0);
    assert.deepStrictEqual(diff, [], `farklı bloklar: ${diff.join(", ")}`);
  });

  await step("d) şablon varsayılanına sıfırla", async () => {
    await page.click(`[data-testid="block-row-${adsIndex}"] button.flex-1`);
    await page.click('[data-testid="reset-block"]');
    await page.click('[data-testid="app-confirm-ok"]');
    await frame().waitForFunction((m) => !document.body.innerText.includes(m), MARK, { timeout: 5000 });
    assert.strictEqual(await page.locator(`[data-testid="block-row-${adsIndex}"] [data-testid="modified-dot"]`).count(), 0);
  });

  await step("e) geri al + revizyon geri yükleme", async () => {
    await page.click('[data-testid="undo"]');
    await frame().waitForFunction((m) => document.body.innerText.includes(m), MARK, { timeout: 5000 });
    await page.click('[data-testid="discard-draft"]');
    await page.click('[data-testid="app-confirm-ok"]');
    await page.waitForFunction(() => /Yayındaki sürüm/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 10000 });
    await page.click('[data-testid="open-revisions"]');
    await page.click(`[data-testid="restore-${startRev}"]`);
    await page.click('[data-testid="app-confirm-ok"]');
    await frame().waitForFunction((m) => !document.body.innerText.includes(m), MARK, { timeout: 10000 });
    await page.click('[data-testid="publish"]');
    await page.waitForFunction(() => /Yayındaki sürüm/.test(document.querySelector('[data-testid="save-status"]').textContent), null, { timeout: 15000 });
    const pub = await (await fetch(`${API}/page-blocks?page=home`)).text();
    assert(!pub.includes(MARK), "eski sürüme dönülmeli");
  });

  await step("f) data-pd-field denetimi: vitrinde sabit kodlu blok metni yok", async () => {
    const p = await ctx.newPage();
    await p.goto(`${BASE}/?pd-noanim=1`, { waitUntil: "networkidle" });
    await p.waitForTimeout(1500);
    const bad = await p.$$eval("[data-pd-block]", (blocks) => {
      const out = [];
      blocks.forEach((b) => {
        const w = document.createTreeWalker(b, NodeFilter.SHOW_TEXT);
        for (let n = w.nextNode(); n; n = w.nextNode()) {
          const t = n.textContent.replace(/\s+/g, " ").trim();
          if (!t || /^[\s:·|/–—%₺,.\-+×x\d]*$/.test(t)) continue;
          const el = n.parentElement;
          if (!el || el.closest("[data-pd-field],[data-pd-data],[data-pd-placeholder],.product-item,.sr-only,script,style,.pd-stub")) continue;
          if (!el.getClientRects().length) continue;
          out.push(`${b.getAttribute("data-block-type")}: ${t.slice(0, 60)}`);
        }
      });
      return out;
    });
    await p.close();
    assert.deepStrictEqual(bad, []);
  });

  await browser.close();
  console.log(failures ? `\n${failures} adım başarısız` : "\nTüm adımlar geçti");
  process.exit(failures ? 1 : 0);
})();
