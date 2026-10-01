import { cargoSummary, CARRIER_OPTIONS } from "../../components/admin/OrderCargoActions";

jest.mock("axios", () => ({ get: jest.fn(() => Promise.resolve({ data: {} })), post: jest.fn() }));

describe("cargoSummary", () => {
  it("kargo kaydı olmayan sipariş", () => {
    const s = cargoSummary({ id: "1", status: "confirmed" });
    expect(s.hasShipment).toBe(false);
    expect(s.canCancel).toBe(false);
  });

  it("Aras kaydı: takip no yokken barkod gösterilir ve iptal edilebilir", () => {
    const s = cargoSummary({
      id: "1", status: "preparing", cargo_provider_code: "ARAS", cargo_provider_name: "Aras Kargo",
      cargo_barcode_number: "W1006301", cargo_barcode_created: true, cargo_tracking_number: "",
      cargo: { env: "test", provider: "ARAS" },
    });
    expect(s).toMatchObject({ code: "ARAS", barcode: "W1006301", tracking: "", hasShipment: true, canCancel: true, env: "test" });
  });

  it("kargoya verilmiş PTT gönderisi iptal edilemez", () => {
    const s = cargoSummary({
      status: "shipped", cargo_provider_code: "PTT", cargo_barcode_number: "2750365698456",
      cargo_tracking_number: "2750365698456", cargo_tracking_link: "https://gonderitakip.ptt.gov.tr/Track/Verify?q=2750365698456",
    });
    expect(s.canCancel).toBe(false);
    expect(s.link).toContain("ptt.gov.tr");
  });

  it("taşıyıcı listesi MNG, Aras, PTT içerir", () => {
    expect(CARRIER_OPTIONS.map((c) => c.value)).toEqual(["MNG", "ARAS", "PTT"]);
  });
});
