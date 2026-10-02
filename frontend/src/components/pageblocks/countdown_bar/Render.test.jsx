import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("metin + geri sayım başlığı ayarlardan çizilir", async () => {
  const { container, unmount } = await renderBlock("countdown_bar", { text: "TÜM SİPARİŞLERDE KARGO BEDAVA", background: "#111111" });
  expect(container.textContent).toContain("TÜM SİPARİŞLERDE KARGO BEDAVA");
  expect(container.textContent).toContain("KALAN SÜRE:");
  unmount();
});

const past = "2020-01-01T00:00:00+03:00";
const cd = (extra) => ({ enabled: true, end: "2099-01-01T00:00:00+03:00", units: ["days", "hours", "minutes", "seconds"], labels: { days: "GÜN", hours: "SAAT", minutes: "DK", seconds: "SN" }, heading: "KALAN SÜRE:", on_expire: "hide_block", expired_text: "Bitti", pad: true, ...extra });

test("bağlantı, data-pd-field işaretleri ve sabit metin yok", async () => {
  const { container, unmount } = await renderBlock("countdown_bar", { text: "KAMPANYA", countdown: cd(), link: { kind: "url", url: "/sale" } });
  expect(container.querySelector('a[href="/sale"]')).not.toBeNull();
  expect(container.querySelector('[data-pd-field="text"]').textContent).toBe("KAMPANYA");
  expect(container.querySelector('[data-pd-field="countdown.labels.days"]').textContent).toBe("GÜN");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("süre bitince: hide_timer metni korur, zero 00 gösterir, show_text bitiş metni, hide_block gizler", async () => {
  let r = await renderBlock("countdown_bar", { text: "KAMPANYA", countdown: cd({ end: past, on_expire: "hide_timer" }) });
  expect(r.container.textContent).toContain("KAMPANYA");
  expect(r.container.textContent).not.toContain("SAAT");
  r.unmount();
  r = await renderBlock("countdown_bar", { text: "KAMPANYA", countdown: cd({ end: past, on_expire: "zero" }) });
  expect(r.container.textContent).toContain("00");
  expect(r.container.textContent).toContain("SAAT");
  r.unmount();
  r = await renderBlock("countdown_bar", { text: "KAMPANYA", countdown: cd({ end: past, on_expire: "show_text" }) });
  expect(r.container.textContent).toContain("Bitti");
  r.unmount();
  r = await renderBlock("countdown_bar", { text: "KAMPANYA", countdown: cd({ end: past, on_expire: "hide_block" }) });
  expect(r.container.textContent).toBe("");
  r.unmount();
});
