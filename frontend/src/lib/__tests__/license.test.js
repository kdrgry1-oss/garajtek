import { isLicensedHostname } from "../license";

test("yalnız lisanslı alan adı ve yerel geliştirme kabul edilir", () => {
  ["garajtek.com", "www.garajtek.com", "GARAJTEK.COM", "localhost", "127.0.0.1"].forEach((h) =>
    expect(isLicensedHostname(h)).toBe(true));
  ["baskasite.com", "garajtek.com.evil.net", "evilgarajtek.com", "", "garajtek.co"].forEach((h) =>
    expect(isLicensedHostname(h)).toBe(false));
});
