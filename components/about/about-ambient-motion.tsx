"use client";

import { useEffect, useState } from "react";
import { createTimeline, stagger } from "animejs";
import type { Timeline } from "animejs";

export function AboutAmbientMotion() {
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    const root = document.querySelector<HTMLElement>(".about-view");
    if (!root || reducedMotion) {
      return;
    }

    const drawTimeline = createTimeline({
      defaults: {
        ease: "outCubic",
        duration: 520,
        composition: "replace",
      },
    });
    addIfTargets(drawTimeline, root.querySelectorAll(".about-flow-line"), {
      strokeDashoffset: [1, 0],
      opacity: [0.18, 0.62],
      delay: stagger(80),
    }, 80);

    let ambientTimeline: Timeline | null = null;
    const startAmbient = () => {
      ambientTimeline?.cancel();
      ambientTimeline = createTimeline({
        loop: true,
        alternate: true,
        defaults: {
          ease: "inOutSine",
          duration: 4600,
          composition: "replace",
        },
      });
      addIfTargets(ambientTimeline, root.querySelectorAll(".about-status-led, .about-raster-cell.is-live"), {
        opacity: [0.36, 0.68],
        scale: [1, 1.018],
      }, 0);
    };
    const stopAmbient = () => {
      ambientTimeline?.cancel();
      ambientTimeline = null;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        startAmbient();
      } else {
        stopAmbient();
      }
    };

    startAmbient();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      drawTimeline.cancel();
      stopAmbient();
    };
  }, [reducedMotion]);

  return null;
}

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);

  return reduced;
}

function addIfTargets(timeline: Timeline, targets: NodeListOf<Element>, params: Record<string, unknown>, position: number) {
  if (targets.length > 0) {
    timeline.add(targets, params, position);
  }
}
