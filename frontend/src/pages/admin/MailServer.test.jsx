import { act } from "react";
import { createRoot } from "react-dom/client";
import MailServer, { fmtBytes } from "./MailServer";
import { navigationGroups } from "../../lib/adminNav";

jest.mock("axios", () => ({ get: jest.fn(), post: jest.fn(), put: jest.fn(), delete: jest.fn() }));
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));

const axios = require("axios");

const STATUS = {
  ok: true, installed: true, domain: "garajtek.com", host: "mail.garajtek.com",
  webmail_url: "https://mail.garajtek.com",
  services: { postfix: "active", dovecot: "active", opendkim: "failed" },
  ports: { 25: true, 993: true, 587: false }, queue_count: 2, mailbox_count: 3,
  certificate: { days_left: 80, not_after: "2026-12-20T00:00:00+00:00" },
  disk: { vhosts_bytes: 1048576, free_bytes: 10737418240 }, relayhost: "",
};

const MAILBOXES = {
  ok: true, domain: "garajtek.com",
  mailboxes: [{ address: "info@garajtek.com", quota: "1G", quota_bytes: 1073741824, usage_bytes: 536870912, created: null }],
};

describe("MailServer (Mail Yönetimi)", () => {
  let container;
  let root;
  beforeAll(() => { global.IS_REACT_ACT_ENVIRONMENT = true; });
  afterAll(() => { delete global.IS_REACT_ACT_ENVIRONMENT; });
  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
    root = createRoot(container);
    window.confirm = jest.fn(() => true);
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.clearAllMocks();
  });

  const flush = async () => { await act(async () => { await Promise.resolve(); await Promise.resolve(); }); };
  const click = async (el) => { await act(async () => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); }); await flush(); };

  test("shows service status, client settings and webmail link", async () => {
    axios.get.mockResolvedValue({ data: STATUS });
    await act(async () => root.render(<MailServer />));
    await flush();
    expect(container.textContent).toContain("Mail Yönetimi");
    expect(container.querySelector('[data-testid="mail-services"]').textContent).toContain("postfix: active");
    expect(container.querySelector('[data-testid="mail-services"]').textContent).toContain("opendkim: failed");
    expect(container.querySelector('[data-testid="mail-queue-count"]').textContent).toBe("2");
    expect(container.querySelector('[data-testid="mail-webmail-link"]').getAttribute("href")).toBe("https://mail.garajtek.com");
    const client = container.querySelector('[data-testid="mail-client-settings"]').textContent;
    expect(client).toContain("993");
    expect(client).toContain("465");
    expect(client).toContain("587");
  });

  test("shows install hint when the mail server is not installed (503)", async () => {
    axios.get.mockRejectedValue({ response: { status: 503, data: { installed: false, message: "Mail sunucusu kurulu değil — deploy/mail/README.md" } } });
    await act(async () => root.render(<MailServer />));
    await flush();
    const box = container.querySelector('[data-testid="mail-not-installed"]');
    expect(box).not.toBeNull();
    expect(box.textContent).toContain("mail-kur.sh");
  });

  test("password reset shows a one-time password", async () => {
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.endsWith("/mailboxes") ? MAILBOXES : STATUS }));
    axios.post.mockResolvedValue({ data: { ok: true, address: "info@garajtek.com", password: "Tek-Sefer-Sifre-123" } });
    await act(async () => root.render(<MailServer />));
    await flush();
    await click(container.querySelector('[data-testid="mail-tab-kutular"]'));
    expect(container.querySelector('[data-testid="mail-mailbox-table"]').textContent).toContain("info@garajtek.com");
    await click(container.querySelector('[data-testid="mail-reset-info@garajtek.com"]'));
    expect(axios.post).toHaveBeenCalledWith(
      expect.stringContaining("/admin/mail/mailboxes/info%40garajtek.com/password"), { random: true }, expect.anything());
    expect(container.querySelector('[data-testid="mail-secret-value"]').textContent).toBe("Tek-Sefer-Sifre-123");
  });

  test("DNS tab lists PASS/FAIL with the record to add", async () => {
    const dns = {
      ok: true, all_pass: false, checks: [
        { key: "mx", label: "MX kaydı", status: "pass", found: ["10 mail.garajtek.com."], expected: { type: "MX", name: "@", value: "mail.garajtek.com", priority: 10 } },
        { key: "spf", label: "SPF", status: "fail", found: [], message: "SPF kaydı yok.", expected: { type: "TXT", name: "@", value: "v=spf1 mx a ip4:1.2.3.4 ~all" } },
      ],
    };
    axios.get.mockImplementation((url) => Promise.resolve({ data: url.includes("dns-check") ? dns : STATUS }));
    await act(async () => root.render(<MailServer />));
    await flush();
    await click(container.querySelector('[data-testid="mail-tab-dns"]'));
    expect(container.querySelector('[data-testid="mail-dns-mx"]').textContent).toBe("PASS");
    expect(container.querySelector('[data-testid="mail-dns-spf"]').textContent).toBe("FAIL");
    expect(container.textContent).toContain("v=spf1 mx a ip4:1.2.3.4 ~all");
    expect(container.textContent).toContain("mxtoolbox");
  });

  test("formats bytes", () => {
    expect(fmtBytes(0)).toBe("0 B");
    expect(fmtBytes(1536)).toBe("1.5 KB");
    expect(fmtBytes(1073741824)).toBe("1.0 GB");
  });

  test("is reachable from the admin menu under Ayarlar", () => {
    const settings = navigationGroups.find((g) => g.key === "ayarlar");
    expect(settings.children.some((c) => c.path === "/admin/mail-yonetimi")).toBe(true);
  });
});
