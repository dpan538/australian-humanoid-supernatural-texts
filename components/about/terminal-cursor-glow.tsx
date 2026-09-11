"use client";

import { useEffect } from "react";

/**
 * Publishes the pointer position as --cursor-x / --cursor-y on <html>.
 *
 * Text that should light up near the pointer paints itself with a
 * viewport-fixed radial gradient centred on those two variables (see the
 * "cursor-lit text" rules in globals.css). So the glow lives in the text,
 * not around the pointer, and the only JavaScript is one passive listener
 * coalesced to a single requestAnimationFrame. When the pointer leaves the
 * window the centre is parked off-screen, which returns every element to
 * its base colour with no transition work. Skipped for reduced-motion and
 * coarse (touch) pointers; light mode never consumes the variables.
 */
export function TerminalCursorGlow() {
  useEffect(() => {
    if (
      window.matchMedia("(prefers-reduced-motion: reduce)").matches ||
      window.matchMedia("(pointer: coarse)").matches
    ) {
      return;
    }

    const root = document.documentElement;
    let frame: number | null = null;
    let x = -9999;
    let y = -9999;

    const flush = () => {
      frame = null;
      root.style.setProperty("--cursor-x", `${x}px`);
      root.style.setProperty("--cursor-y", `${y}px`);
    };
    const schedule = () => {
      if (frame === null) {
        frame = window.requestAnimationFrame(flush);
      }
    };
    const handleMove = (event: PointerEvent) => {
      x = event.clientX;
      y = event.clientY;
      schedule();
    };
    const handleLeave = () => {
      x = -9999;
      y = -9999;
      schedule();
    };

    window.addEventListener("pointermove", handleMove, { passive: true });
    root.addEventListener("pointerleave", handleLeave);
    window.addEventListener("blur", handleLeave);

    return () => {
      window.removeEventListener("pointermove", handleMove);
      root.removeEventListener("pointerleave", handleLeave);
      window.removeEventListener("blur", handleLeave);
      if (frame !== null) {
        window.cancelAnimationFrame(frame);
      }
      root.style.removeProperty("--cursor-x");
      root.style.removeProperty("--cursor-y");
    };
  }, []);

  return null;
}
