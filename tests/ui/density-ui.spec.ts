import { expect, test, type Browser, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

type DensityMode = {
  label: string;
  theme: "dark" | "light";
  signal: "normal" | "high";
  optional?: boolean;
};

type DensityViewport = {
  label: string;
  width: number;
  height: number;
  mobile?: boolean;
};

const DENSITY_MODES: DensityMode[] = [
  { label: "dark normal", theme: "dark", signal: "normal" },
  { label: "dark high", theme: "dark", signal: "high" },
  { label: "light normal", theme: "light", signal: "normal", optional: true },
];

const DENSITY_VIEWPORTS: DensityViewport[] = [
  { label: "desktop 1920x1080", width: 1920, height: 1080 },
  { label: "desktop 1440x900", width: 1440, height: 900 },
  { label: "mobile 390x844", width: 390, height: 844, mobile: true },
];

const FORBIDDEN_PUBLIC_LABELS = [
  "FIELD 01",
  "FIELD 02",
  "FIELD 03",
  "PERIOD METHOD COMPARATOR",
  "ANALYTICAL FIELD",
  "SOURCE FIELD",
];

async function openDensity(browser: Browser, viewport: DensityViewport, mode: DensityMode) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    deviceScaleFactor: 1,
    isMobile: Boolean(viewport.mobile),
  });

  await context.addInitScript(({ signal, theme }) => {
    window.localStorage.setItem("aus-archive-theme", theme);
    window.localStorage.setItem("aus-archive-signal-gain", signal);
  }, mode);

  const page = await context.newPage();
  await page.goto("/density");
  await page.locator(".density-view").waitFor({ state: "visible" });
  await page.locator(".density-line-chart").waitFor({ state: "visible" });
  return { context, page };
}

async function assertAxeContrast(page: Page) {
  const result = await new AxeBuilder({ page })
    .include(".density-view")
    .withRules(["color-contrast"])
    .analyze();

  expect(
    result.violations.map((violation) => ({
      id: violation.id,
      impact: violation.impact,
      nodes: violation.nodes.map((node) => ({
        target: node.target,
        summary: node.failureSummary,
      })),
    })),
    "Density view must pass axe color-contrast checks",
  ).toEqual([]);
}

async function assertDensityReadability(page: Page, viewport: DensityViewport, mode: DensityMode) {
  const result = await page.evaluate(
    ({ forbiddenPublicLabels, isMobile }) => {
      const visible = (element: Element) => {
        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return (
          style.display !== "none" &&
          style.visibility !== "hidden" &&
          Number(style.opacity) > 0 &&
          rect.width > 0 &&
          rect.height > 0
        );
      };

      const directText = (element: Element) =>
        Array.from(element.childNodes)
          .filter((node) => node.nodeType === Node.TEXT_NODE)
          .map((node) => node.textContent?.trim() ?? "")
          .join(" ")
          .trim();

      const selectorFor = (element: Element) => {
        if (element.id) return `#${element.id}`;
        const className = Array.from(element.classList).join(".");
        const tagName = element.tagName.toLowerCase();
        return className ? `${tagName}.${className}` : tagName;
      };

      const fontSize = (element: Element) => Number.parseFloat(window.getComputedStyle(element).fontSize);
      const failures: string[] = [];

      const forbiddenLabels = forbiddenPublicLabels.filter((label) => document.body.innerText.includes(label));
      if (forbiddenLabels.length > 0) {
        failures.push(`forbidden engineering labels are visible: ${forbiddenLabels.join(", ")}`);
      }

      document.querySelectorAll(".density-view *").forEach((element) => {
        if (element.closest("svg") || !visible(element) || !directText(element)) return;
        const size = fontSize(element);
        if (size < 14) {
          failures.push(`core Density text below 14px: ${selectorFor(element)} = ${size.toFixed(2)}px`);
        }
      });

      document.querySelectorAll(".density-chart-axis, .density-box-label, .density-box-count").forEach((element) => {
        if (!visible(element)) return;
        const size = fontSize(element);
        if (size < 12) {
          failures.push(`chart axis/label text below 12px: ${selectorFor(element)} = ${size.toFixed(2)}px`);
        }
      });

      document
        .querySelectorAll(".band-meta span, .density-signal .tiny-label, .density-figure-rail .tiny-label, .density-chart-card header span")
        .forEach((element) => {
          if (!visible(element)) return;
          const size = fontSize(element);
          if (size < 13) {
            failures.push(`period/card label below 13px: ${selectorFor(element)} = ${size.toFixed(2)}px`);
          }
        });

      document.querySelectorAll(".band-meta b").forEach((element) => {
        if (!visible(element)) return;
        const size = fontSize(element);
        if (size < 32) {
          failures.push(`main numeric count below 32px: ${selectorFor(element)} = ${size.toFixed(2)}px`);
        }
      });

      document.querySelectorAll(".density-view, .density-view *").forEach((element) => {
        const style = window.getComputedStyle(element);
        if (style.scrollSnapType !== "none") {
          failures.push(`scroll-snap-type is not allowed: ${selectorFor(element)} = ${style.scrollSnapType}`);
        }
        if (style.scrollSnapAlign !== "none") {
          failures.push(`scroll-snap-align is not allowed: ${selectorFor(element)} = ${style.scrollSnapAlign}`);
        }
      });

      if (isMobile) {
        if (document.documentElement.scrollWidth > document.documentElement.clientWidth + 1) {
          failures.push(`document horizontal overflow on mobile: ${document.documentElement.scrollWidth}px > ${document.documentElement.clientWidth}px`);
        }

        document
          .querySelectorAll(".density-view, .density-view > *, .density-band, .density-chart-card, .density-signal, .density-figure-rail")
          .forEach((element) => {
            if (!visible(element)) return;
            const htmlElement = element as HTMLElement;
            if (htmlElement.scrollWidth > htmlElement.clientWidth + 1) {
              failures.push(
                `density panel horizontal overflow on mobile: ${selectorFor(element)} = ${htmlElement.scrollWidth}px > ${htmlElement.clientWidth}px`,
              );
            }
          });
      }

      type Rgba = { r: number; g: number; b: number; a: number };

      const colorToRgb = (color: string): Rgba | null => {
        const scratch = document.createElement("span");
        scratch.style.color = color;
        document.body.appendChild(scratch);
        const parsed = window.getComputedStyle(scratch).color;
        scratch.remove();
        const match = parsed.match(/rgba?\(([^)]+)\)/);
        if (!match) return null;
        const [r = 0, g = 0, b = 0, a = 1] = match[1].split(",").map((part) => Number.parseFloat(part.trim()));
        return { r, g, b, a };
      };

      const blend = (foreground: Rgba | null, background: Rgba | null): Rgba | null => {
        if (!foreground || !background) return null;
        const alpha = Number.isFinite(foreground.a) ? foreground.a : 1;
        return {
          r: foreground.r * alpha + background.r * (1 - alpha),
          g: foreground.g * alpha + background.g * (1 - alpha),
          b: foreground.b * alpha + background.b * (1 - alpha),
          a: 1,
        };
      };

      const luminance = (rgb: { r: number; g: number; b: number }) => {
        const channel = [rgb.r, rgb.g, rgb.b].map((value) => {
          const normalized = value / 255;
          return normalized <= 0.03928 ? normalized / 12.92 : ((normalized + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * channel[0] + 0.7152 * channel[1] + 0.0722 * channel[2];
      };

      const contrast = (a: { r: number; g: number; b: number }, b: { r: number; g: number; b: number }) => {
        const light = Math.max(luminance(a), luminance(b));
        const dark = Math.min(luminance(a), luminance(b));
        return (light + 0.05) / (dark + 0.05);
      };

      const backgroundFor = (element: Element) => {
        let current: Element | null = element;
        while (current) {
          const background = colorToRgb(window.getComputedStyle(current).backgroundColor);
          if (background && background.a > 0) return background;
          current = current.parentElement;
        }
        return colorToRgb(window.getComputedStyle(document.documentElement).backgroundColor);
      };

      document.querySelectorAll(".density-chart-axis, .density-box-label, .density-box-count").forEach((element) => {
        if (!visible(element)) return;
        const foreground = blend(colorToRgb(window.getComputedStyle(element).fill), backgroundFor(element));
        const background = backgroundFor(element);
        if (!foreground || !background) return;
        const ratio = contrast(foreground, background);
        if (ratio < 4.5) {
          failures.push(`chart text contrast below 4.5: ${selectorFor(element)} = ${ratio.toFixed(2)}`);
        }
      });

      document
        .querySelectorAll(
          ".density-line-public, .density-line-mapped, .density-box-whisker, .density-box-cap, .density-box-rect, .density-box-median, .density-chart-axis-line",
        )
        .forEach((element) => {
          if (!visible(element)) return;
          const style = window.getComputedStyle(element);
          const paint = style.stroke !== "none" ? style.stroke : style.fill;
          const foreground = blend(colorToRgb(paint), backgroundFor(element));
          const background = backgroundFor(element);
          if (!foreground || !background) return;
          const ratio = contrast(foreground, background);
          if (ratio < 3) {
            failures.push(`chart mark contrast below 3.0: ${selectorFor(element)} = ${ratio.toFixed(2)}`);
          }
        });

      return failures;
    },
    {
      forbiddenPublicLabels: FORBIDDEN_PUBLIC_LABELS,
      isMobile: Boolean(viewport.mobile),
    },
  );

  expect(result, `${viewport.label} / ${mode.label} Density readability failures`).toEqual([]);
}

for (const mode of DENSITY_MODES) {
  for (const viewport of DENSITY_VIEWPORTS) {
    test(`Density UI quality gate: ${viewport.label} / ${mode.label}`, async ({ browser }) => {
      const { context, page } = await openDensity(browser, viewport, mode);

      try {
        const appliedTheme = await page.evaluate(() => document.documentElement.dataset.theme);
        if (mode.optional && appliedTheme !== mode.theme) {
          test.skip(true, `${mode.theme} mode is not exposed by this build`);
        }

        await expect(page.locator(".density-band")).toHaveCount(6);
        await assertAxeContrast(page);
        await assertDensityReadability(page, viewport, mode);
      } finally {
        await context.close();
      }
    });
  }
}
