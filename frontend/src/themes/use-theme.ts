"use client";

import { useCallback, useEffect, useState } from "react";
import { ThemeName, themes } from "./tokens";
import { readStoredTheme, writeStoredTheme } from "./theme-script";

const TRANSITION_CLASS = "theme-transitioning";
const TRANSITION_DURATION_MS = 400;

function applyTokens(name: ThemeName): void {
  const root = document.documentElement;
  const tokens = themes[name];

  // Enable transitions temporarily for smooth theme switch
  root.classList.add(TRANSITION_CLASS);

  root.setAttribute("data-theme", name);
  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(key, value);
  }

  // Remove transition class after animation completes to avoid
  // performance overhead from persistent * { transition } rules.
  const r = root as HTMLElement & { __themeTransitionTimer?: number };
  window.clearTimeout(r.__themeTransitionTimer);
  r.__themeTransitionTimer = window.setTimeout(() => {
    root.classList.remove(TRANSITION_CLASS);
  }, TRANSITION_DURATION_MS);
}

export function useTheme() {
  const [theme, setThemeState] = useState<ThemeName>("latte-night");

  // Hydration: read stored theme on mount
  useEffect(() => {
    const stored = readStoredTheme() ?? "latte-night";
    setThemeState(stored);
    applyTokens(stored);
  }, []);

  const setTheme = useCallback((name: ThemeName) => {
    setThemeState(name);
    writeStoredTheme(name);
    applyTokens(name);
  }, []);

  return { theme, setTheme };
}
