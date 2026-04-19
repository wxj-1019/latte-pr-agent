"use client";

import { ThemeName } from "./tokens";

const STORAGE_KEY = "latte-theme";

/**
 * Client-side only: read theme from localStorage (with SSR safety).
 * Must be called inside useEffect or event handlers.
 */
export function readStoredTheme(): ThemeName | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (
      raw === "latte-night" ||
      raw === "latte-light" ||
      raw === "rose-latte"
    ) {
      return raw;
    }
  } catch {
    // localStorage may be unavailable (private mode, etc.)
  }
  return null;
}

/**
 * Client-side only: write theme to localStorage.
 */
export function writeStoredTheme(name: ThemeName): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, name);
  } catch {
    // ignore
  }
}

/**
 * Returns the inline script string to be placed in <head> for FOUC prevention.
 * This runs synchronously before React hydrates, reading localStorage and
 * setting data-theme + CSS variables before first paint.
 */
export function getThemeInlineScript(): string {
  // Must be a self-contained IIFE with no external deps.
  // Do NOT use backticks here to avoid template injection issues.
  return (
    "(function(){" +
    "try{" +
    "var t=localStorage.getItem('latte-theme')||'latte-night';" +
    "document.documentElement.setAttribute('data-theme',t);" +
    "}catch(e){" +
    "document.documentElement.setAttribute('data-theme','latte-night');" +
    "}" +
    "})();"
  );
}
