import "../../components/pageblocks/testMocks";
import { act } from "react";
import { createRoot } from "react-dom/client";
import PageDesign from "./PageDesign";
import { defaultHome, defaultGlobal } from "../../components/pageblocks/registry";

jest.mock("sonner", () => ({ toast: { error: () => {}, success: () => {}, warning: () => {} } }));
jest.mock("../../context/AuthContext", () => ({ useAuth: () => ({ user: { is_admin: true } }) }));
jest.mock("../../components/admin/DemoContentCard", () => () => null);
jest.mock("../../components/admin/AppConfirm", () => ({ appConfirm: () => Promise.resolve(true) }));
jest.mock("../../components/admin/CategoryTreeSelect", () => ({ CategoryTreeSelect: () => null }));

const axios = require("axios");

describe("Sayfa Tasarımı düzenleyicisi", () => {
  let container;
  let root;
  let puts;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  beforeEach(async () => {
    puts = [];
    const pub = { rev: 1, blocks: defaultHome(), global: defaultGlobal() };
    axios.get = (url) => Promise.resolve({ data: url.includes("/page-design/home") ? { published: pub, draft: null } : [] });
    axios.put = (url, body, cfg) => { puts.push({ url, body, cfg }); return Promise.resolve({ data: { rev: puts.length, errors: [] } }); };
    axios.post = () => Promise.resolve({ data: {} });
    axios.delete = () => Promise.resolve({ data: {} });
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    await act(async () => { root.render(<PageDesign />); });
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
  });
  afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

  const q = (s) => container.querySelector(s);
  const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); };

  test("şablon ana sayfası blok listesi + seçili bloğun şema formu + canlı önizleme çerçevesi", async () => {
    const rows = container.querySelectorAll('[data-testid^="block-row-"]');
    expect(rows).toHaveLength(9);
    expect(rows[0].getAttribute("data-block-type")).toBe("hero_slider");
    expect(q('[data-testid="block-form"]')).toBeTruthy();
    expect(q('[data-testid="preview-frame"]').getAttribute("src")).toBe("/onizleme/sayfa/home");
    expect(q('[data-testid="save-status"]').textContent).toMatch(/Yayındaki sürüm/);
  });

  test("gizle → taslak değişikliği; geri al / ileri al", async () => {
    await click(q('[data-testid="toggle-1"]'));
    expect(q('[data-testid="block-row-1"]').className).toMatch(/opacity-60/);
    expect(q('[data-testid="save-status"]').textContent).toMatch(/Taslak/);
    await click(q('[data-testid="undo"]'));
    expect(q('[data-testid="block-row-1"]').className).not.toMatch(/opacity-60/);
    await click(q('[data-testid="redo"]'));
    expect(q('[data-testid="block-row-1"]').className).toMatch(/opacity-60/);
  });

  test("galeriden blok ekle (varsayılanlarla dolu) ve çoğalt", async () => {
    await click(q('[data-testid="add-block"]'));
    expect(q('[data-testid="block-gallery"]')).toBeTruthy();
    await click(q('[data-testid="gallery-add-text_block"]'));
    expect(container.querySelectorAll('[data-testid^="block-row-"]')).toHaveLength(10);
    await click(q('[data-testid="dup-0"]'));
    expect(container.querySelectorAll('[data-testid^="block-row-"]')).toHaveLength(11);
  });

  test("otomatik taslak kaydı (3 sn) If-Match ile", async () => {
    jest.useFakeTimers();
    await click(q('[data-testid="toggle-2"]'));
    await act(async () => { jest.advanceTimersByTime(3200); });
    jest.useRealTimers();
    await act(async () => { await new Promise((r) => setTimeout(r, 0)); });
    expect(puts.length).toBe(1);
    expect(puts[0].url).toMatch(/\/page-design\/home\/draft$/);
    expect(puts[0].body.blocks[2].is_active).toBe(false);
  });
});
