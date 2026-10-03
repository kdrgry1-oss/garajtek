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

  it("taşıyıcı listesi yalnız Aras ve PTT içerir", () => {
    expect(CARRIER_OPTIONS.map((c) => c.value)).toEqual(["ARAS", "PTT"]);
  });

  it("eski (entegrasyonu kaldırılmış) MNG kaydı görüntülenir, yerelde kaldırılabilir", () => {
    const s = cargoSummary({
      status: "preparing", cargo_provider_code: "MNG", cargo_provider_name: "MNG Kargo",
      cargo_barcode_created: true, cargo_tracking_number: "",
      cargo_tracking_link: "https://kargotakip.example/?no=1", cargo: { provider: "MNG", mng_siparis_no: "123456" },
    });
    expect(s).toMatchObject({ code: "MNG", name: "MNG Kargo", barcode: "123456", hasShipment: true, canCancel: true, legacy: true });
    const shipped = cargoSummary({ status: "delivered", cargo_provider_code: "MNG", cargo_tracking_number: "NZ1" });
    expect(shipped).toMatchObject({ tracking: "NZ1", canCancel: false });
  });
});
