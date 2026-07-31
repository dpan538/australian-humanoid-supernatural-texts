"use client";

export type ArchiveDisplayTheme = "dark" | "light";

type ThemeCommit = () => void;

type NativeViewTransition = {
  finished: Promise<void>;
};

type ViewTransitionDocument = Document & {
  startViewTransition?: (update: () => void | Promise<void>) => NativeViewTransition;
};

const LIGHT_CANVAS = "#dfd0b3";
const DARK_CANVAS = "#080a09";

function transitionGeometry(trigger: HTMLElement) {
  const rect = trigger.getBoundingClientRect();
  const x = rect.left + rect.width / 2;
  const y = rect.top + rect.height / 2;
  const radius = Math.hypot(
    Math.max(x, window.innerWidth - x),
    Math.max(y, window.innerHeight - y),
  );
  return { x, y, radius };
}

function animateSettledSurfaces(originX: number, originY: number) {
  const selectors = [
    ".view-area",
    ".source-terminal-header",
    ".dashboard-console",
    ".density-chart-card",
    ".figure-dictionary-profile",
    ".map-readout",
    ".mobile-map-dashboard-card",
    ".mobile-density-overview-card",
    ".mobile-dashboard-hero",
    ".mobile-analysis-card",
    ".mobile-source-visual-card",
    ".mobile-expand-card",
    ".about-status-panel",
  ].join(",");
  const surfaces = [...document.querySelectorAll<HTMLElement>(selectors)]
    .filter((element) => {
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight;
    })
    .slice(0, 10);

  surfaces.forEach((surface, index) => {
    surface.animate(
      [
        { transform: "translateY(10px) scaleY(0.985)", transformOrigin: `${originX}px ${originY}px` },
        { transform: "translateY(0) scaleY(1)", transformOrigin: `${originX}px ${originY}px` },
      ],
      {
        duration: 360 + index * 24,
        delay: index * 22,
        easing: "cubic-bezier(0.22, 1, 0.36, 1)",
        fill: "both",
      },
    );
  });
}

async function runFallbackIris(
  targetTheme: ArchiveDisplayTheme,
  geometry: ReturnType<typeof transitionGeometry>,
  commit: ThemeCommit,
) {
  const veil = document.createElement("div");
  veil.className = "theme-transition-veil";
  veil.style.setProperty("--theme-transition-x", `${geometry.x}px`);
  veil.style.setProperty("--theme-transition-y", `${geometry.y}px`);
  veil.style.background = targetTheme === "light" ? LIGHT_CANVAS : DARK_CANVAS;
  document.body.appendChild(veil);

  const expand = veil.animate(
    [
      { clipPath: `circle(0px at ${geometry.x}px ${geometry.y}px)` },
      { clipPath: `circle(${geometry.radius}px at ${geometry.x}px ${geometry.y}px)` },
    ],
    {
      duration: 380,
      easing: "cubic-bezier(0.65, 0, 0.35, 1)",
      fill: "forwards",
    },
  );
  await expand.finished;
  commit();

  const reveal = veil.animate(
    [
      { clipPath: `circle(${geometry.radius}px at ${geometry.x}px ${geometry.y}px)` },
      { clipPath: `circle(0px at ${geometry.x}px ${geometry.y}px)` },
    ],
    {
      duration: 420,
      easing: "cubic-bezier(0.22, 1, 0.36, 1)",
      fill: "forwards",
    },
  );
  await reveal.finished;
  veil.remove();
  animateSettledSurfaces(geometry.x, geometry.y);
}

export function runThemeTransition(
  trigger: HTMLElement,
  targetTheme: ArchiveDisplayTheme,
  commit: ThemeCommit,
) {
  const root = document.documentElement;
  if (root.dataset.themeTransitioning === "true") {
    return;
  }

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduceMotion) {
    commit();
    return;
  }

  const geometry = transitionGeometry(trigger);
  root.dataset.themeTransitioning = "true";
  root.style.setProperty("--theme-transition-x", `${geometry.x}px`);
  root.style.setProperty("--theme-transition-y", `${geometry.y}px`);
  root.style.setProperty("--theme-transition-radius", `${geometry.radius}px`);

  const finish = () => {
    delete root.dataset.themeTransitioning;
  };
  const transitionDocument = document as ViewTransitionDocument;

  if (typeof transitionDocument.startViewTransition === "function") {
    const transition = transitionDocument.startViewTransition(() => {
      commit();
    });
    transition.finished
      .then(() => animateSettledSurfaces(geometry.x, geometry.y))
      .finally(finish);
    return;
  }

  void runFallbackIris(targetTheme, geometry, commit).finally(finish);
}
