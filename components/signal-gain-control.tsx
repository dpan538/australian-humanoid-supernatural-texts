"use client";

import { useEffect, useState } from "react";

type SignalGain = "normal" | "high";
type DisplayTheme = "dark" | "light";

const SIGNAL_STORAGE_KEY = "aus-archive-signal-gain";
const THEME_STORAGE_KEY = "aus-archive-theme";

function readStoredGain(): SignalGain {
  if (typeof window === "undefined") {
    return "normal";
  }
  return window.localStorage.getItem(SIGNAL_STORAGE_KEY) === "high" ? "high" : "normal";
}

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
  const [gain, setGain] = useState<SignalGain>("normal");
  const [theme, setTheme] = useState<DisplayTheme>("dark");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setGain(readStoredGain());
    setTheme(readStoredTheme());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    document.documentElement.dataset.signalGain = gain;
    window.localStorage.setItem(SIGNAL_STORAGE_KEY, gain);
    window.dispatchEvent(new CustomEvent("archive-display-change", { detail: { signalGain: gain } }));
  }, [gain, hydrated]);

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
      <button
        type="button"
        className="display-control-button signal-gain-control"
        data-mode={gain}
        aria-label={`Display gain ${gain === "high" ? "high" : "normal"}; toggle signal brightness`}
        onClick={() => setGain((current) => (current === "high" ? "normal" : "high"))}
      >
        <span>SIGNAL</span>
        <b>{gain === "high" ? "HIGH" : "NORMAL"}</b>
      </button>
    </div>
  );
}

export function SignalGainControl() {
  return <DisplayControls />;
}
