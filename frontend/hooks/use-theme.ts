"use client";

import { useSyncExternalStore, useCallback } from "react";
import { THEME_KEY, THEME_EVENT } from "@/lib/constants";

function subscribe(callback: () => void) {
  window.addEventListener(THEME_EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(THEME_EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

function getSnapshot(): "light" | "dark" {
  if (typeof window === "undefined") return "dark";
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function getServerSnapshot(): "light" | "dark" {
  return "dark";
}

export function useTheme() {
  const theme = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  const toggleTheme = useCallback(() => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Storage access blocked or unavailable
    }
    window.dispatchEvent(new Event(THEME_EVENT));
  }, [theme]);

  const setTheme = useCallback((newTheme: "light" | "dark") => {
    document.documentElement.dataset.theme = newTheme;
    try {
      localStorage.setItem(THEME_KEY, newTheme);
    } catch {
      // Storage access blocked or unavailable
    }
    window.dispatchEvent(new Event(THEME_EVENT));
  }, []);

  return { theme, toggleTheme, setTheme, isDark: theme === "dark" };
}
