// Sayfa Tasarımı canlı önizleme durumu (iframe içindeki vitrin). Panel taslağı postMessage ile
// gönderir (pd:draft); bu modül taslağı saklar ve Header / CountdownBar / Footer gibi sayfa
// ağacının dışındaki bileşenlere de yayar. Vitrinde (önizleme değilken) hiçbir etkisi yoktur.
import { useSyncExternalStore } from "react";

let state = { active: false, page: "home", blocks: null, global: null, selectedId: null, device: "desktop" };
const subs = new Set();

export function getPreviewState() {
  return state;
}

export function setPreviewState(patch) {
  state = { ...state, ...patch };
  subs.forEach((fn) => { try { fn(); } catch { /* yoksay */ } });
}

function subscribe(fn) {
  subs.add(fn);
  return () => subs.delete(fn);
}

export function usePreviewState() {
  return useSyncExternalStore(subscribe, getPreviewState, getPreviewState);
}

export const isPreviewActive = () => !!state.active;

/** Önizlemede taslaktaki bloklardan (yoksa null) belirli tipteki ilk aktif blok. */
export function previewBlockOfType(type) {
  if (!state.active || !Array.isArray(state.blocks)) return undefined;
  return state.blocks.find((b) => b && b.type === type && b.is_active !== false) || null;
}

/** iframe → panel mesajı (aynı köken). */
export function postToParent(msg) {
  try {
    if (typeof window !== "undefined" && window.parent && window.parent !== window) {
      window.parent.postMessage(msg, window.location.origin);
    }
  } catch { /* yoksay */ }
}
