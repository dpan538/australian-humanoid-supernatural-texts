"use client";

import { useEffect, useState } from "react";
import { createTimeline, stagger } from "animejs";

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

    return () => {
      drawTimeline.cancel();
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

function addIfTargets(
  timeline: ReturnType<typeof createTimeline>,
  targets: NodeListOf<Element>,
  params: Record<string, unknown>,
  position: number,
) {
  if (targets.length > 0) {
    timeline.add(targets, params, position);
  }
}
