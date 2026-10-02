// Blok testleri için ortak jest taklitleri — test dosyasında İLK içe aktarım olmalı: `import "../testMocks";`
// (react-router-dom v7 ve axios ESM paketleri CRA jest'inde yüklenemez; ağ/oturum bağımlılıkları sahte.)
/* eslint-disable no-undef */
jest.mock("react-router-dom", () => {
  const React = require("react");
  return {
    Link: ({ to, children, ...p }) => React.createElement("a", { href: typeof to === "string" ? to : "#", ...p }, children),
    NavLink: ({ to, children, ...p }) => React.createElement("a", { href: typeof to === "string" ? to : "#", ...p }, children),
    useNavigate: () => () => {}, useLocation: () => ({ pathname: "/", search: "" }), useParams: () => ({}),
  };
}, { virtual: true });
// Not: CRA jest'te resetMocks açık → jest.fn uygulamaları her testte sıfırlanır; düz fonksiyon kullanılır.
jest.mock("axios", () => {
  const ok = () => Promise.resolve({ data: {} });
  return { get: ok, post: ok, put: ok, delete: ok };
});
jest.mock("embla-carousel-react", () => () => [() => {}, null]);
jest.mock("../electro/useCategoryTree", () => () => ({ roots: [{ id: "c1", name: "Liftler", slug: "liftler", children: [] }], menuRoots: null, byId: new Map() }));
jest.mock("../../lib/storeInfo", () => ({ useStoreInfo: () => ({ name: "Test", instagram: "" }) }));
jest.mock("../../lib/dataLayer", () => ({ trackSelectPromotion: () => {}, trackSelectItem: () => {} }));
jest.mock("../ProductCard", () => {
  const React = require("react");
  const C = ({ product, as: Tag = "div" }) => React.createElement(Tag, { className: "product-item" }, product.name);
  return { __esModule: true, default: C, CardPrice: () => null, useProductActions: () => ({ href: "/", select() {}, add() {}, fav() {}, cmp() {} }) };
});
