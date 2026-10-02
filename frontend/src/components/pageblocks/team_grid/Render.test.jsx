import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: 6 üye, yuvarlak fotoğraf yer tutucusu, gri bant", async () => {
  const { container, unmount } = await renderBlock("team_grid", {});
  expect(container.querySelectorAll(".col-xl.text-center").length).toBe(6);
  expect(container.querySelector('[data-pd-field="members.0.name"]').textContent).toBe("Ahmet Yılmaz");
  expect(container.querySelector('[data-pd-field="members.0.role"]').textContent).toBe("Kurucu / Genel Müdür");
  expect(container.querySelector('[data-pd-field="members.0.photo"]').className).toContain("rounded-circle");
  expect(require("./defaults.json")._section.background).toBe("#f5f5f5");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("4 sütun, köşeli fotoğraf, başlık", async () => {
  const r = await renderBlock("team_grid", { columns: "4", round: false, title: "Ekibimiz", members: [{ name: "A", role: "B", photo: { url: "/api/uploads/a.jpg" } }] });
  expect(r.container.querySelector(".col-xl-3")).not.toBeNull();
  expect(r.container.querySelector("img").className).not.toContain("rounded-circle");
  expect(r.container.querySelector('[data-pd-field="title"]').textContent).toBe("Ekibimiz");
  r.unmount();
});
