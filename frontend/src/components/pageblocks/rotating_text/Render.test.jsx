import "../testMocks";
import { mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("mesaj, renkler ve bağlantı ayarlardan; metin data-pd-field taşır", async () => {
  const { container, unmount } = await renderBlock("rotating_text", {
    messages: [{ text: "Kargo bedava", link: { kind: "url", url: "/kargo" } }, { text: "İkinci", link: { kind: "none" } }],
    background: "#000000", text_color: "#ffffff",
  });
  const bar = container.querySelector('[data-testid="rotating-text"]');
  expect(bar.style.backgroundColor).toBe("rgb(0, 0, 0)");
  const a = container.querySelector('[data-pd-field="messages.0.text"]');
  expect(a.textContent).toBe("Kargo bedava");
  expect(a.getAttribute("href")).toBe("/kargo");
  unmount();
});
