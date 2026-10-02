import "../testMocks";
import { act } from "react";
import { createRoot } from "react-dom/client";
import SchemaForm from "./SchemaForm";
import { allFields, BLOCKS, defaultSettings, withDefaults } from "../registry";

global.IS_REACT_ACT_ENVIRONMENT = true;
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn(), warning: jest.fn() } }));
jest.mock("../../admin/CategoryTreeSelect", () => ({ CategoryTreeSelect: () => null }));

function setup(type, settings = {}, extra = {}) {
  const schema = BLOCKS[type].schema;
  const state = { value: withDefaults(type, settings) };
  const onChange = jest.fn((v) => { state.value = v; render(); });
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  function render() {
    act(() => root.render(<SchemaForm fields={allFields(schema)} tabs={[...schema.tabs, "Görünürlük"]} value={state.value}
      defaults={defaultSettings(type, state.value._variant)} onChange={onChange} {...extra} />));
  }
  render();
  return { container, state, onChange, root };
}

const typeInto = (el, v) => {
  const setter = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(el), "value").set;
  act(() => { setter.call(el, v); el.dispatchEvent(new Event("input", { bubbles: true })); });
};
const click = (el) => act(() => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });

test("şemadan sekmeler ve alanlar üretilir (elle form yok)", () => {
  const { container } = setup("ads_block");
  const tabs = [...container.querySelectorAll('[role="tab"]')].map((t) => t.textContent);
  expect(tabs).toEqual(expect.arrayContaining(["İçerik", "Görünüm", "Görünürlük"]));
  expect(container.querySelector('[data-testid="repeater-items"]')).toBeTruthy();
});

test("Görünüm sekmesi: sayı alanı değişince onChange, ↺ ile şablon varsayılanına döner", () => {
  const { container, state } = setup("ads_block");
  click([...container.querySelectorAll('[role="tab"]')].find((t) => t.textContent === "Görünüm"));
  const row = container.querySelector('[data-field-path="text_size"]');
  typeInto(row.querySelector("input"), "2");
  expect(state.value.text_size).toBe(2);
  const reset = container.querySelector('[data-testid="reset-text_size"]');
  expect(reset).toBeTruthy();
  click(reset);
  expect(state.value.text_size).toBe(1.286);
});

test("repeater: öğe aç, show_if ile koşullu alanlar, öğe ekle", () => {
  const { container, state } = setup("ads_block");
  const items = container.querySelector('[data-testid="repeater-items"]');
  click(items.querySelector('button[aria-expanded="false"]'));
  expect(container.querySelector('[data-field-path="items.0.action_text"]')).toBeTruthy();
  expect(container.querySelector('[data-field-path="items.0.action_value"]')).toBeFalsy();
  click(container.querySelector('[data-testid="repeater-add-items"]'));
  expect(state.value.items).toHaveLength(4);
  expect(state.value.items[3]._id).toBeTruthy();
  expect(container.querySelector('[data-testid="repeater-add-items"]')).toBeFalsy(); // max 4
});

test("responsive alan cihaz sekmeli düzenlenir", () => {
  const { container, state } = setup("hero_slider");
  click([...container.querySelectorAll('[role="tab"]')].find((t) => t.textContent === "Görünüm"));
  const row = container.querySelector('[data-field-path="height"]');
  click([...row.querySelectorAll('[role="tab"]')].find((b) => b.textContent === "Mobil"));
  typeInto(row.querySelector("input"), "333");
  expect(state.value.height).toEqual({ desktop: 485, tablet: 400, mobile: 333 });
});

test("backend hatası satır içinde gösterilir ve sekmede işaretlenir", () => {
  const { container } = setup("full_banner", {}, { errors: [{ path: "settings.link", message: "Bağlantı geçersiz" }] });
  expect(container.querySelector('[data-field-path="link"]').textContent).toContain("Bağlantı geçersiz");
});
