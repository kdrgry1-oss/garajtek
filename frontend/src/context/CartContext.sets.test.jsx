import { act } from "react";
import { createRoot } from "react-dom/client";
import { CartProvider, useCart } from "./CartContext";
import { buildSetLines, mergeSetLines, replaceHref, setPayload, writeReplaceCtx, readReplaceCtx, findPendingByParam } from "../lib/productSets";
import { parseQuickLines } from "../lib/quickOrder";

jest.mock("./AuthContext", () => ({ useAuth: () => ({ token: null }) }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn(), warning: jest.fn() } }));


const SET = {
  set: { id: "S1", name: "Atölye Seti", slug: "atolye-seti-1" },
  components: [
    { product_id: "A", name: "94 Parça Lokma", slug: "lokma-94", price: 1000, sale_price: null, quantity: 1, stock: 0,
      in_stock: false, leaf_category: { id: "11", slug: "lokma-setleri", name: "Lokma Setleri" }, category_id: "11" },
    { product_id: "B", name: "Tork Anahtarı", slug: "tork", price: 500, sale_price: 400, quantity: 1, stock: 5,
      in_stock: true, category_id: "21" },
    { product_id: "D", name: "LED Lamba", slug: "led", price: 100, quantity: 2, stock: 9, in_stock: true,
      variant_id: "D2", variant: { id: "D2", size: "Siyah", price_diff: 20 }, category_id: "20" },
  ],
};

describe("productSets helpers", () => {
  test("buildSetLines: stokta olanlar normal kalem, tükenen bekleyen kalem", () => {
    const lines = buildSetLines(SET, 1);
    expect(lines.map((l) => [l.id, l.needsReplacement || false, l.quantity, l.price])).toEqual([
      ["set:S1:A", true, 1, 1000], ["set:S1:B", false, 1, 400], ["set:S1:D", false, 2, 120],
    ]);
    expect(lines[0].replaceCategory.slug).toBe("lokma-setleri");
    expect(replaceHref(lines[0])).toBe("/lokma-setleri?degistir=S1%3AA");
    expect(setPayload(lines[1])).toEqual({ set_id: "S1", set_slot: "B" });
    expect(setPayload({ productId: "x" })).toEqual({});
  });

  test("mergeSetLines: aynı set tekrar eklenince adet artar, bekleyen yuva çoğalmaz", () => {
    const once = mergeSetLines([], buildSetLines(SET, 1));
    const twice = mergeSetLines(once, buildSetLines(SET, 1));
    expect(twice).toHaveLength(3);
    expect(twice.find((l) => l.id === "set:S1:D").quantity).toBe(4);
    expect(twice.filter((l) => l.needsReplacement)).toHaveLength(1);
  });
});

describe("CartContext — ürün seti", () => {
  let root, container, cart;
  const Probe = () => { cart = useCart(); return null; };
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; });
  beforeEach(async () => {
    localStorage.clear();
    sessionStorage.clear();
    container = document.createElement("div");
    root = createRoot(container);
    await act(async () => root.render(<CartProvider><Probe /></CartProvider>));
  });
  afterEach(async () => { await act(async () => root.unmount()); });

  test("seti ekle → bileşenler gruplu kalem, tükenen bileşen toplama girmez", async () => {
    await act(async () => { cart.addSet(SET, 1); });
    expect(cart.items.map((i) => i.productId)).toEqual(["B", "D"]);
    expect(cart.pendingItems.map((i) => i.productId)).toEqual(["A"]);
    expect(cart.total).toBe(400 + 240);
    expect(cart.items.every((i) => i.setId === "S1" && i.setName === "Atölye Seti")).toBe(true);
  });

  test("değiştir bağlamında aynı kategoriden eklenen ürün boş yuvaya yazılır", async () => {
    await act(async () => { cart.addSet(SET, 1); });
    writeReplaceCtx({ lineId: "set:S1:A", setId: "S1", slot: "A", setName: "Atölye Seti", categoryId: "11" });
    // Başka kategoriden ürün → normal kalem olarak eklenir, yuva boş kalır
    await act(async () => { cart.addItem({ id: "Z", name: "Çekiç", price: 50, stock: 3, category_ids: ["99"] }); });
    expect(cart.pendingItems).toHaveLength(1);
    expect(cart.items.find((i) => i.productId === "Z").setId).toBeUndefined();
    // Aynı alt kategoriden ürün → yuvayı doldurur, set bilgisi korunur
    await act(async () => { cart.addItem({ id: "C", name: "108 Parça Lokma", price: 900, stock: 7, category_ids: ["11", "10"] }); });
    expect(cart.pendingItems).toHaveLength(0);
    const repl = cart.items.find((i) => i.productId === "C");
    expect(repl).toMatchObject({ id: "set:S1:A", setId: "S1", setSlot: "A", replacedFrom: "94 Parça Lokma", quantity: 1 });
    expect(readReplaceCtx()).toBeNull();
  });

  test("set kalemi ile aynı ürün ayrıca eklenirse ayrı kalem olur", async () => {
    await act(async () => { cart.addSet(SET, 1); });
    await act(async () => { cart.addItem({ id: "B", name: "Tork Anahtarı", price: 500, sale_price: 400, stock: 5 }); });
    const bs = cart.items.filter((i) => i.productId === "B");
    expect(bs).toHaveLength(2);
    expect(bs.find((i) => i.setId).quantity).toBe(1);
  });
});

describe("sözleşme 7.2 / 7.3 / 7.4", () => {
  let root, container, cart;
  const Probe = () => { cart = useCart(); return null; };
  const OLD_ENV = process.env.REACT_APP_BACKEND_URL;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; process.env.REACT_APP_BACKEND_URL = OLD_ENV; delete global.fetch; });
  beforeEach(async () => {
    localStorage.clear();
    sessionStorage.clear();
    process.env.REACT_APP_BACKEND_URL = "";
    container = document.createElement("div");
    root = createRoot(container);
    await act(async () => root.render(<CartProvider><Probe /></CartProvider>));
  });
  afterEach(async () => { await act(async () => root.unmount()); });

  test("100 bileşenli set tek çağrıda, tek sepet güncellemesiyle eklenir", async () => {
    const big = { set: { id: "BIG", name: "Büyük Set" }, components: Array.from({ length: 100 }, (_, i) => ({
      product_id: `H${i}`, name: `Parça ${i}`, price: 10 + i, quantity: 1 + (i % 3), stock: 50, in_stock: true })) };
    let n;
    await act(async () => { n = cart.addSet(big, 1); });
    expect(n).toBe(100);
    expect(cart.items).toHaveLength(100);
    expect(cart.itemCount).toBe(Array.from({ length: 100 }, (_, i) => 1 + (i % 3)).reduce((a, b) => a + b, 0));
  });

  test("Hızlı Sipariş: liste ayrıştırma ve toplu ekleme", async () => {
    expect(parseQuickLines("A-1, 2\nB-2 3\nC-3;4\nD-4\n\n")).toEqual([
      { code: "A-1", qty: 2 }, { code: "B-2", qty: 3 }, { code: "C-3", qty: 4 }, { code: "D-4", qty: 1 }]);
    await act(async () => {
      cart.addMany([{ product: { id: "p1", name: "X", price: 10, stock: 9 }, quantity: 2 },
        { product: { id: "p2", name: "Y", price: 5, stock: 1 }, quantity: 4 },
        { product: { id: "p1", name: "X", price: 10, stock: 9 }, quantity: 1 }]);
    });
    expect(cart.items.map((i) => [i.productId, i.quantity])).toEqual([["p1", 3], ["p2", 1]]);
  });

  test("tükenen herhangi bir kalem işaretlenir, stoklu ürünle değiştirilir", async () => {
    await act(async () => { cart.addItem({ id: "Q", name: "Kriko", price: 100, stock: 3, category_id: "7" }); });
    process.env.REACT_APP_BACKEND_URL = "http://x";
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ items: {
      "Q|": { stock: 0, available: false, leaf_category: { id: "7", slug: "yer-krikolari", name: "Yer Krikoları" } } } }) }));
    await act(async () => { await cart.refreshStock(); });
    expect(cart.items).toHaveLength(0);
    expect(cart.pendingItems[0]).toMatchObject({ productId: "Q", needsReplacement: true });
    expect(replaceHref(cart.pendingItems[0])).toBe("/yer-krikolari?degistir=urun%3AQ");
    expect(findPendingByParam(cart.pendingItems, "urun:Q").id).toBe("Q");
    await act(async () => { cart.replacePending("Q", { id: "R", name: "Kriko 3T", price: 120, stock: 5, category_id: "7" }); });
    expect(cart.pendingItems).toHaveLength(0);
    expect(cart.items[0]).toMatchObject({ productId: "R", replacedFrom: "Kriko", quantity: 1 });
  });

  test("stok geri gelirse bekleyen kalem geri döner", async () => {
    await act(async () => { cart.addSet(SET, 1); });
    process.env.REACT_APP_BACKEND_URL = "http://x";
    global.fetch = jest.fn(() => Promise.resolve({ ok: true, json: () => Promise.resolve({ items: {
      "A|": { stock: 3, available: true } } }) }));
    await act(async () => { await cart.refreshStock(); });
    expect(cart.pendingItems).toHaveLength(0);
    expect(cart.items.find((i) => i.productId === "A")).toMatchObject({ setId: "S1", quantity: 1, stock: 3 });
  });
});
