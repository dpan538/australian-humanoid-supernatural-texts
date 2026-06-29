"use client";

import { useEffect, useState } from "react";

type DisplayTheme = "dark" | "light";

const THEME_STORAGE_KEY = "aus-archive-theme";

function readStoredTheme(): DisplayTheme {
  if (typeof window === "undefined") {
    return "dark";
  }
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === "dark" || stored === "light") {
    return stored;
  }
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function DisplayControls() {
  const [theme, setTheme] = useState<DisplayTheme>("dark");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setTheme(readStoredTheme());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
    window.dispatchEvent(new CustomEvent("archive-display-change", { detail: { theme } }));
  }, [theme, hydrated]);

  return (
    <div className="display-control-group" aria-label="Display controls">
      <button
        type="button"
        className="display-control-button theme-mode-control"
        data-mode={theme}
        aria-label={`Theme ${theme}; toggle dark and light mode`}
        onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
      >
        <span>MODE</span>
        <b>{theme === "dark" ? "DARK" : "LIGHT"}</b>
      </button>
    </div>
  );
}
