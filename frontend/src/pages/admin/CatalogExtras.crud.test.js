import { act } from "react";
import { createRoot } from "react-dom/client";
import axios from "axios";
import { Brands } from "./CatalogExtras";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("recharts", () => new Proxy({}, { get: () => () => null }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let host; let root;
beforeEach(() => {
  axios.get.mockResolvedValue({ data: { items: [] } });
  axios.post.mockResolvedValue({ data: { id: "b1" } });
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});
afterEach(() => { act(() => root.unmount()); host.remove(); jest.clearAllMocks(); });

const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };
const btn = (text) => [...host.querySelectorAll("button")].find((b) => b.textContent.trim() === text);

test("Marka Yönetimi: 'Yeni' butonu formu açar ve kayıt POST edilir", async () => {
  await act(async () => { root.render(<Brands />); });
  expect(host.querySelectorAll("input").length).toBe(0);
  await click(btn("Yeni"));
  const inputs = host.querySelectorAll("input");
  expect(inputs.length).toBeGreaterThan(3);   // Marka Adı, Slug, Logo URL, Sıra, Aktif
  // Zorunlu ad boşken kaydetmez
  await click(btn("Kaydet"));
  expect(axios.post).not.toHaveBeenCalled();
  const nameInput = inputs[0];
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
    setter.call(nameInput, "SYNC-Marka");
    nameInput.dispatchEvent(new Event("input", { bubbles: true }));
  });
  await click(btn("Kaydet"));
  expect(axios.post).toHaveBeenCalledWith(
    expect.stringMatching(/\/brands$/),
    expect.objectContaining({ name: "SYNC-Marka", is_active: true }),
    expect.anything(),
  );
  expect(host.querySelectorAll("input").length).toBe(0);   // başarıyla kaydedilince kapanır
});
