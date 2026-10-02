// Sayfa bağlamı: önizleme mi, seçili blok, sayfa adı, kategori kökleri…
import { createContext, useContext } from "react";

export const PageCtx = createContext({ preview: false, page: "home", selectedId: null });
export const usePageCtx = () => useContext(PageCtx);
