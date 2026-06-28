"use client";

import { useEffect, useState } from "react";
import { createTimeline } from "animejs";
import type { Timeline } from "animejs";

export function useSourceTerminalMotion({
  root,
  selectedId,
  filterKey,
}: {
  root: HTMLElement | null;
  selectedId: number | null;
  filterKey: string;
}) {
  const reducedMotion = usePrefersReducedMotion();

  useEffect(() => {
    if (!root || reducedMotion) {
      return;
    }

    let timeline: Timeline | null = null;
    const start = () => {
      timeline?.cancel();
      timeline = createTimeline({
        loop: true,
        alternate: true,
        defaults: {
          ease: "inOutSine",
          duration: 4200,
          composition: "replace",
        },
      });
      addIfTargets(timeline, root.querySelectorAll(".source-terminal-led.is-live, .source-divider-led.is-live, .source-family-marker.is-active"), {
        opacity: [0.38, 0.62],
        scale: [1, 1.025],
      }, 0);
      addIfTargets(timeline, root.querySelectorAll(".source-terminal-divider > span"), {
        opacity: [0.3, 0.5],
      }, 420);
    };
    const stop = () => {
      timeline?.cancel();
      timeline = null;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        start();
      } else {
        stop();
      }
    };

    start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      stop();
    };
  }, [reducedMotion, root]);

  useEffect(() => {
    if (!root || reducedMotion || selectedId === null) {
      return;
    }
    const timeline = createTimeline({
      defaults: {
        ease: "outCubic",
        duration: 180,
        composition: "replace",
      },
    });
    addIfTargets(timeline, root.querySelectorAll(`[data-source-id="${selectedId}"] .source-selection-bracket`), {
      opacity: [0, 1],
      scaleY: [0.4, 1],
    }, 0);
    addIfTargets(timeline, root.querySelectorAll(".source-inspector-line"), {
      scaleX: [0, 1],
      opacity: [0.2, 1],
    }, 30);
    return () => {
      timeline.cancel();
    };
  }, [reducedMotion, root, selectedId]);

  useEffect(() => {
    if (!root || reducedMotion) {
      return;
    }
    const timeline = createTimeline({
      defaults: {
        ease: "outCubic",
        duration: 220,
        composition: "replace",
      },
    });
    addIfTargets(timeline, root.querySelectorAll(".source-result-marker"), {
      opacity: [0.3, 0.82, 0.48],
      scale: [1, 1.08, 1],
    }, 0);
    return () => {
      timeline.cancel();
    };
  }, [filterKey, reducedMotion, root]);
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
