import { act } from "react";
import "../testMocks";
import { hardcodedTexts, mockFetch, renderBlock } from "../testUtils";

beforeEach(() => { mockFetch([]); });

test("varsayılan: başlık, 5 soru, ilki açık; tıklayınca diğeri açılır, ilki kapanır", async () => {
  const { container, unmount } = await renderBlock("accordion", {});
  expect(container.querySelector('[data-pd-field="title"]').textContent).toBe("Size nasıl yardımcı olabiliriz?");
  const btns = container.querySelectorAll(".card-btn");
  expect(btns.length).toBe(5);
  expect(btns[0].getAttribute("aria-expanded")).toBe("true");
  expect(container.querySelectorAll(".collapse.show").length).toBe(1);
  await act(async () => { btns[1].click(); });
  expect(btns[1].getAttribute("aria-expanded")).toBe("true");
  expect(btns[0].getAttribute("aria-expanded")).toBe("false");
  expect(hardcodedTexts(container)).toEqual([]);
  unmount();
});

test("çoklu açık, başta kapalı, dar genişlik, zengin metin cevap", async () => {
  const r = await renderBlock("accordion", { multiple: true, open_index: 0, width: "narrow", items: [{ question: "S1", answer: "<strong>C1</strong>" }, { question: "S2", answer: "C2" }] });
  expect(r.container.querySelectorAll(".collapse.show").length).toBe(0);
  expect(r.container.querySelector(".col-lg-5")).not.toBeNull();
  expect(r.container.querySelector('[data-pd-field="items.0.answer"] strong').textContent).toBe("C1");
  const btns = r.container.querySelectorAll(".card-btn");
  await act(async () => { btns[0].click(); });
  await act(async () => { btns[1].click(); });
  expect(r.container.querySelectorAll(".collapse.show").length).toBe(2);
  r.unmount();
});
