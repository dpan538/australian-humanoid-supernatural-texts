"use client";

import { useEffect, useState } from "react";
import { createTimeline, stagger } from "animejs";
import type { AnimationParams } from "animejs";

export function AboutAmbientMotion() {
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    // Scope to the desktop shell: the hidden mobile tree also carries
    // .about-view and comes first in the DOM, so a bare query matched it and
    // found no .about-flow-line targets.
    const root = document.querySelector<HTMLElement>(".desktop-about-shell .about-view");
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
  params: AnimationParams,
  position: number,
) {
  if (targets.length > 0) {
    timeline.add(targets, params, position);
  }
}
