"use client";

import { useEffect, useState } from "react";

type SignalGain = "normal" | "high";

const STORAGE_KEY = "aus-archive-signal-gain";

function readStoredGain(): SignalGain {
  if (typeof window === "undefined") {
    return "normal";
  }
  return window.localStorage.getItem(STORAGE_KEY) === "high" ? "high" : "normal";
}

export function SignalGainControl() {
  const [gain, setGain] = useState<SignalGain>("normal");

  useEffect(() => {
    setGain(readStoredGain());
  }, []);

  useEffect(() => {
    document.documentElement.dataset.signalGain = gain;
    window.localStorage.setItem(STORAGE_KEY, gain);
  }, [gain]);

  return (
    <button
      type="button"
      className="signal-gain-control"
      data-mode={gain}
      aria-label={`Display gain ${gain === "high" ? "high" : "normal"}; toggle signal brightness`}
      onClick={() => setGain((current) => (current === "high" ? "normal" : "high"))}
    >
      <span>SIGNAL</span>
      <b>{gain === "high" ? "HIGH" : "NORMAL"}</b>
    </button>
  );
}
