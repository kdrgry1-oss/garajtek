import "../testMocks";
import { mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("metin + geri sayım başlığı ayarlardan çizilir", async () => {
  const { container, unmount } = await renderBlock("countdown_bar", { text: "TÜM SİPARİŞLERDE KARGO BEDAVA", background: "#111111" });
  expect(container.textContent).toContain("TÜM SİPARİŞLERDE KARGO BEDAVA");
  expect(container.textContent).toContain("KALAN SÜRE:");
  unmount();
});
