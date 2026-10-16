import { act } from "react";
import { createRoot } from "react-dom/client";
import ClearCartButton from "../ClearCartButton";

let host, root;
beforeEach(() => { host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host); });
afterEach(() => { act(() => root.unmount()); host.remove(); });
const q = (id) => host.querySelector(`[data-testid="${id}"]`);
const click = (el) => act(() => { el.dispatchEvent(new MouseEvent("click", { bubbles: true })); });

test("onay sayfa içinde sorulur; window.confirm engelli olsa da sepet temizlenir", () => {
  window.confirm = jest.fn(() => false);   // uygulama içi tarayıcı: confirm engelli
  const onClear = jest.fn();
  act(() => root.render(<ClearCartButton onClear={onClear} testId="cc" />));
  click(q("cc"));
  expect(onClear).not.toHaveBeenCalled();
  click(q("cc-yes"));
  expect(onClear).toHaveBeenCalledTimes(1);
  expect(window.confirm).not.toHaveBeenCalled();
});

test("Vazgeç ile hiçbir şey silinmez", () => {
  const onClear = jest.fn();
  act(() => root.render(<ClearCartButton onClear={onClear} testId="cc" />));
  click(q("cc"));
  click([...host.querySelectorAll("button")].find((b) => b.textContent === "Vazgeç"));
  expect(onClear).not.toHaveBeenCalled();
  expect(q("cc")).not.toBeNull();
});
