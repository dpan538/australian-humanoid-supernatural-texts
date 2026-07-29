"use client";

import { useEffect, useRef, useState } from "react";
import { createTimeline, stagger } from "animejs";
import type { AnimationParams, Timeline } from "animejs";
import type { RefObject } from "react";

const MOTION_TARGETS = [
  ".figure-dictionary-segment-meter i.is-active",
  ".figure-dictionary-timeline-bars i",
  ".figure-dictionary-threshold-dots i.is-active",
  ".figure-dictionary-document-clusters li i",
  ".figure-dictionary-sparse-timeline polygon",
  ".figure-dictionary-sparse-timeline circle",
  ".figure-dictionary-region-waffle i",
  ".figure-dictionary-source-concentration li i b",
  ".figure-dictionary-source-constellation line.is-stem",
  ".figure-dictionary-source-constellation circle.is-record",
  ".figure-dictionary-source-constellation circle.is-centroid",
  ".figure-dictionary-narrative-baseline line.is-stem",
  ".figure-dictionary-narrative-baseline circle",
  ".figure-dictionary-completeness-plot i b",
].join(", ");

const DRAW_PATHS = [
  ".figure-dictionary-sparse-timeline polyline",
].join(", ");

export function useFigureDictionaryMotion(
  rootRef: RefObject<HTMLElement | null>,
  entryKey: string | null,
) {
  const reducedMotion = usePrefersReducedMotion();
  const timelineRef = useRef<Timeline | null>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !entryKey) {
      return;
    }

    timelineRef.current?.cancel();
    timelineRef.current = null;
    resetFigureDictionaryMotion(root);

    if (reducedMotion) {
      return;
    }

    prepareFigureDictionaryDrawPaths(root);
    prepareTransformOrigins(root);

    const timeline = createTimeline({
      defaults: {
        ease: "outCubic",
        composition: "replace",
      },
    });

    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-segment-meter i.is-active"),
      {
        opacity: [0, 1],
        scaleY: [0.08, 1],
        duration: 820,
        delay: stagger(22),
      },
      80,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-timeline-bars i"),
      {
        opacity: [0, 1],
        scaleY: [0.08, 1],
        duration: 940,
        ease: "linear",
        delay: stagger(26),
      },
      100,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-threshold-dots i.is-active"),
      {
        opacity: [0, 1],
        scale: [0.18, 1],
        duration: 660,
        delay: stagger(18),
      },
      100,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-document-clusters li i"),
      {
        opacity: [0, 1],
        scale: [0.2, 1],
        duration: 680,
        delay: stagger(28),
      },
      150,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-sparse-timeline polygon"),
      {
        opacity: [0, 1],
        scaleY: [0.05, 1],
        duration: 920,
      },
      140,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-sparse-timeline polyline"),
      {
        strokeDashoffset: 0,
        duration: 1120,
        ease: "linear",
      },
      210,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-sparse-timeline circle"),
      {
        opacity: [0, 1],
        scale: [0.25, 1],
        duration: 620,
        delay: stagger(70),
      },
      420,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-region-waffle i"),
      {
        opacity: [0, 1],
        scale: [0.12, 1],
        duration: 720,
        delay: stagger(10, { grid: [10, 10], from: "first" }),
      },
      220,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-source-concentration li i b"),
      {
        opacity: [0.55, 1],
        scaleX: [0.03, 1],
        duration: 920,
        ease: "linear",
        delay: stagger(70),
      },
      240,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-source-constellation line.is-stem"),
      {
        opacity: [0, 1],
        scaleY: [0.05, 1],
        duration: 760,
        delay: stagger(90),
      },
      160,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-source-constellation circle.is-record"),
      {
        opacity: [0, 1],
        scale: [0.15, 1],
        duration: 620,
        delay: stagger(18),
      },
      260,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-source-constellation circle.is-centroid"),
      {
        opacity: [0, 1],
        scale: [0.3, 1],
        duration: 760,
        delay: stagger(110),
      },
      420,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-narrative-baseline line.is-stem"),
      {
        opacity: [0, 1],
        scaleY: [0.05, 1],
        duration: 760,
        delay: stagger(100),
      },
      180,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-narrative-baseline circle"),
      {
        opacity: [0, 1],
        scale: [0.18, 1],
        duration: 860,
        delay: stagger(120),
      },
      260,
    );
    addIfTargets(
      timeline,
      root.querySelectorAll(".figure-dictionary-completeness-plot i b"),
      {
        opacity: [0.55, 1],
        scaleX: [0.03, 1],
        duration: 940,
        ease: "linear",
        delay: stagger(120),
      },
      360,
    );

    timelineRef.current = timeline;

    return () => {
      timeline.cancel();
    };
  }, [entryKey, reducedMotion, rootRef]);

  useEffect(() => {
    return () => {
      timelineRef.current?.cancel();
      timelineRef.current = null;
    };
  }, []);
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

function prepareFigureDictionaryDrawPaths(root: HTMLElement) {
  root.querySelectorAll<SVGGeometryElement>(DRAW_PATHS).forEach((path) => {
    const length = Math.max(1, path.getTotalLength());
    path.style.strokeDasharray = String(length);
    path.style.strokeDashoffset = String(length);
  });
}

function prepareTransformOrigins(root: HTMLElement) {
  root.querySelectorAll<HTMLElement | SVGElement>(
    ".figure-dictionary-timeline-bars i, .figure-dictionary-segment-meter i.is-active",
  ).forEach((element) => {
    element.style.transformOrigin = "center bottom";
  });

  root.querySelectorAll<HTMLElement | SVGElement>(
    ".figure-dictionary-source-concentration li i b, .figure-dictionary-completeness-plot i b",
  ).forEach((element) => {
    element.style.transformOrigin = "left center";
  });

  root.querySelectorAll<SVGElement>(
    ".figure-dictionary-threshold-dots i.is-active, .figure-dictionary-document-clusters li i, .figure-dictionary-sparse-timeline polygon, .figure-dictionary-sparse-timeline circle, .figure-dictionary-region-waffle i, .figure-dictionary-source-constellation line.is-stem, .figure-dictionary-source-constellation circle.is-record, .figure-dictionary-source-constellation circle.is-centroid, .figure-dictionary-narrative-baseline line.is-stem, .figure-dictionary-narrative-baseline circle",
  ).forEach((element) => {
    element.style.transformOrigin = "center";
    element.style.setProperty("transform-box", "fill-box");
  });
}

function resetFigureDictionaryMotion(root: HTMLElement) {
  root.querySelectorAll<HTMLElement | SVGElement>(MOTION_TARGETS).forEach((element) => {
    element.style.opacity = "";
    element.style.transform = "";
    element.style.transformOrigin = "";
    element.style.removeProperty("transform-box");
  });

  root.querySelectorAll<SVGGeometryElement>(DRAW_PATHS).forEach((path) => {
    path.style.strokeDasharray = "";
    path.style.strokeDashoffset = "";
  });
}

function addIfTargets(
  timeline: Timeline,
  targets: NodeListOf<Element>,
  params: AnimationParams,
  position: number,
) {
  if (targets.length > 0) {
    timeline.add(targets, params, position);
  }
}
