import fs from "fs";
import path from "path";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { OrderInvoiceButton, InvoiceIssueDialog } from "./BirFaturaInvoice";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn() }));
// Jest'te "@/..." takma adı çözülmediği için shadcn Dialog yalın karşılıklarıyla taklit edilir.
jest.mock("../ui/dialog", () => ({
  Dialog: ({ open, children }) => (open ? <div data-testid="dialog-root">{children}</div> : null),
  DialogContent: ({ children, ...p }) => <div {...p}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
}));
jest.mock("sonner",() => ({ toast: { error: jest.fn(), success: jest.fn(), loading: jest.fn(() => "t") } }));

const axios = require("axios");

const ORDER = { id: "o1", order_number: "W10001", status: "confirmed" };
const PREVIEW = {
  configured: true, order_number: "W10001", existing: null, blocked: null, maybe_sent: false,
  order_total: 1160, total_incl: 1160, total_excl: 1050, vat: 110, lines: 1, currency: "TRY",
  receiver: { name: "Örnek A.Ş.", tax_no: "1234567801", tax_office: "Çankaya", city: "Ankara", email: "" },
  system_type: "EFATURA", invoice_type: "e-fatura", type_source: "gib", receiver_tag: "urn:mail:pk@ornek",
  lookup_error: null, problems: [],
};

const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

describe("BirFatura doğrudan fatura kesimi", () => {
  let container;
  let root;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; });
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.clearAllMocks();
    jest.restoreAllMocks();
  });

  const render = async (el) => { await act(async () => root.render(el)); await flush(); };
  const icon = () => document.querySelector('[data-testid="order-invoice-o1"]');

  test("kesilmiş fatura: yeşil ikon PDF'i açar", async () => {
    const open = jest.spyOn(window, "open").mockReturnValue(null);
    const onIssue = jest.fn();
    await render(<OrderInvoiceButton order={{ ...ORDER, invoice_number: "GRJ1", invoice_type: "e-arsiv",
      invoice_pdf_url: "https://uygulama.edonustur.com/f.pdf" }} directEnabled onIssue={onIssue} />);
    expect(icon().dataset.state).toBe("issued");
    expect(icon().title).toContain("e-Arşiv kesildi: GRJ1");
    await act(async () => icon().click());
    expect(open).toHaveBeenCalledWith("https://uygulama.edonustur.com/f.pdf", "_blank", "noopener,noreferrer");
    expect(onIssue).not.toHaveBeenCalled();
  });

  test("doğrudan kesim yapılandırılmışsa ikon onay penceresini tetikler", async () => {
    const onIssue = jest.fn();
    await render(<OrderInvoiceButton order={ORDER} directEnabled onIssue={onIssue} />);
    expect(icon().tagName).toBe("BUTTON");
    expect(icon().dataset.state).toBe("direct");
    await act(async () => icon().click());
    expect(onIssue).toHaveBeenCalledWith(ORDER);
  });

  test("yapılandırılmamışsa eski davranış: BirFatura paneline bağlantı", async () => {
    const onIssue = jest.fn();
    await render(<OrderInvoiceButton order={ORDER} directEnabled={false} onIssue={onIssue} />);
    expect(icon().tagName).toBe("A");
    expect(icon().getAttribute("href")).toBe("https://uygulama.birfatura.com");
    expect(icon().dataset.state).toBe("panel");
  });

  test("onay penceresi tutar/alıcı/tür gösterir ve onayla faturayı keser", async () => {
    axios.get.mockResolvedValue({ data: PREVIEW });
    axios.post.mockResolvedValue({ data: { success: true, message: "e-Fatura kesildi: GRJ1.",
      invoice: { invoice_number: "GRJ1", invoice_type: "e-fatura" } } });
    const onIssued = jest.fn();
    const onClose = jest.fn();
    await render(<InvoiceIssueDialog order={ORDER} onIssued={onIssued} onClose={onClose} />);
    expect(axios.get.mock.calls[0][0]).toMatch(/\/api\/integrations\/birfatura\/invoices\/o1\/preview$/);
    const text = document.body.textContent;
    expect(document.querySelector('[data-testid="bf-invoice-type"]').textContent).toBe("e-Fatura");
    expect(text).toContain("Örnek A.Ş.");
    expect(text).toContain("1234567801");
    expect(text).toMatch(/1\.160,00 TL/);
    const btn = document.querySelector('[data-testid="bf-invoice-confirm"]');
    expect(btn.disabled).toBe(false);
    await act(async () => btn.click());
    await flush();
    expect(axios.post.mock.calls[0][0]).toMatch(/\/api\/integrations\/birfatura\/invoices\/o1$/);
    expect(onIssued).toHaveBeenCalledWith({ invoice_number: "GRJ1", invoice_type: "e-fatura" });
    expect(onClose).toHaveBeenCalled();
  });

  test("iptal/engelli siparişte onay butonu pasif, istek atılmaz", async () => {
    axios.get.mockResolvedValue({ data: { ...PREVIEW, blocked: "İptal/iade sürecindeki siparişe fatura kesilemez (durum: cancelled)." } });
    await render(<InvoiceIssueDialog order={ORDER} onIssued={jest.fn()} onClose={jest.fn()} />);
    expect(document.querySelector('[data-testid="bf-invoice-blocked"]').textContent).toContain("İptal");
    const btn = document.querySelector('[data-testid="bf-invoice-confirm"]');
    expect(btn.disabled).toBe(true);
    expect(axios.post).not.toHaveBeenCalled();
  });

  test("tutarsızlık varsa onay pasif; BirFatura hatası pencerede gösterilir", async () => {
    axios.get.mockResolvedValue({ data: { ...PREVIEW, problems: ["Fatura toplamı uyuşmuyor."] } });
    await render(<InvoiceIssueDialog order={ORDER} onIssued={jest.fn()} onClose={jest.fn()} />);
    expect(document.querySelector('[data-testid="bf-invoice-confirm"]').disabled).toBe(true);
    await act(async () => root.render(<div />));

    axios.get.mockResolvedValue({ data: PREVIEW });
    axios.post.mockRejectedValue({ response: { status: 502, data: { detail: "BirFatura isteği reddetti: Yetersiz kontör." } } });
    const onIssued = jest.fn();
    await render(<InvoiceIssueDialog order={{ ...ORDER }} onIssued={onIssued} onClose={jest.fn()} />);
    await act(async () => document.querySelector('[data-testid="bf-invoice-confirm"]').click());
    await flush();
    expect(document.querySelector('[role="alert"]').textContent).toContain("Yetersiz kontör");
    expect(onIssued).not.toHaveBeenCalled();
  });

  test("409 (zaten faturalı) mevcut faturayla tamamlanır", async () => {
    axios.get.mockResolvedValue({ data: PREVIEW });
    axios.post.mockRejectedValue({ response: { status: 409, data: { detail: "zaten kesilmiş", invoice: { invoice_number: "X1" } } } });
    const onIssued = jest.fn();
    await render(<InvoiceIssueDialog order={ORDER} onIssued={onIssued} onClose={jest.fn()} />);
    await act(async () => document.querySelector('[data-testid="bf-invoice-confirm"]').click());
    await flush();
    expect(onIssued).toHaveBeenCalledWith({ invoice_number: "X1" });
  });
});

test("Orders.jsx satır ikonu ve detay 'Fatura Kes' doğrudan kesime bağlı", () => {
  const src = fs.readFileSync(path.join(__dirname, "../../pages/admin/Orders.jsx"), "utf8");
  expect(src).toMatch(/<OrderInvoiceButton order=\{order\} directEnabled=\{directInvoice\}/);
  expect(src).toMatch(/onIssue=\{\(o\) => setInvoiceTarget\(o\)\}/);
  expect(src).toMatch(/<InvoiceIssueDialog[\s\S]*order=\{invoiceTarget\}/);
  expect(src).toMatch(/data-testid="order-detail-issue-invoice"/);
  expect(src).not.toMatch(/href="https:\/\/uygulama\.birfatura\.com"/);   // eski satır içi bağlantı bileşene taşındı
});
