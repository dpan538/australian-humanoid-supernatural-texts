"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

type MobileControlView = "about" | "map" | "density" | "dashboard" | "source";
type DisplayTheme = "dark" | "light";
type MobileNavName = "theme" | "about" | "source" | "density" | "map";
const MOBILE_ARCHIVE_QUERY = "(max-width: 980px), (pointer: coarse)";
const MOBILE_NAV_IDLE_MS = 4600;
const THEME_STORAGE_KEY = "aus-archive-theme";

function isMobileArchiveViewport() {
  return typeof window !== "undefined" && window.matchMedia(MOBILE_ARCHIVE_QUERY).matches;
}

export function MobileArchiveView({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export function useMobileArchiveRouteGuard(view: MobileControlView) {
  const router = useRouter();
  const [blockedDashboard, setBlockedDashboard] = useState(() => view === "dashboard" && isMobileArchiveViewport());

  useEffect(() => {
    if (view !== "dashboard") {
      setBlockedDashboard(false);
      return;
    }

    const mediaQuery = window.matchMedia(MOBILE_ARCHIVE_QUERY);
    const syncRoute = () => {
      const shouldBlock = mediaQuery.matches;
      setBlockedDashboard(shouldBlock);
      if (shouldBlock) {
        router.replace("/map");
      }
    };

    syncRoute();
    mediaQuery.addEventListener("change", syncRoute);
    return () => mediaQuery.removeEventListener("change", syncRoute);
  }, [router, view]);

  return { blockedDashboard };
}

export function MobileArchiveControls({ view }: { view: MobileControlView }) {
  const [collapsed, setCollapsed] = useState(false);
  const idleTimer = useRef<number | null>(null);

  const clearIdleTimer = useCallback(() => {
    if (idleTimer.current) {
      window.clearTimeout(idleTimer.current);
      idleTimer.current = null;
    }
  }, []);

  const scheduleCollapse = useCallback(() => {
    clearIdleTimer();
    idleTimer.current = window.setTimeout(() => setCollapsed(true), MOBILE_NAV_IDLE_MS);
  }, [clearIdleTimer]);

  const expandAndSchedule = useCallback(() => {
    setCollapsed(false);
    scheduleCollapse();
  }, [scheduleCollapse]);

  useEffect(() => {
    expandAndSchedule();
    return clearIdleTimer;
  }, [clearIdleTimer, expandAndSchedule, view]);

  return (
    <div
      className={collapsed ? "mobile-archive-controls is-collapsed" : "mobile-archive-controls"}
      aria-label="Mobile archive controls"
    >
      <button
        type="button"
        className="mobile-nav-collapse-toggle"
        aria-label="Open mobile navigation"
        aria-expanded={!collapsed}
        onClick={expandAndSchedule}
      >
        <b className="mobile-nav-pill-label" aria-hidden="true">NAV</b>
        <span>AusFigures navigation</span>
      </button>
      <div className="mobile-archive-expanded">
        <MobileThemeControl />
        <nav className="mobile-archive-nav" aria-label="Mobile archive navigation">
          <Link
            className={view === "about" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/about"
            aria-label="Open about"
            aria-current={view === "about" ? "page" : undefined}
          >
            <MobileNavIcon name="about" />
            <span>About</span>
          </Link>
          <Link
            className={view === "source" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/source"
            aria-label="Open source"
            aria-current={view === "source" ? "page" : undefined}
          >
            <MobileNavIcon name="source" />
            <span>Source</span>
          </Link>
          <Link
            className={view === "density" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/density"
            aria-label="Open density"
            aria-current={view === "density" ? "page" : undefined}
          >
            <MobileNavIcon name="density" />
            <span>Density</span>
          </Link>
          <Link
            className={view === "map" ? "mobile-archive-link is-active" : "mobile-archive-link"}
            href="/map"
            aria-label="Open map"
            aria-current={view === "map" ? "page" : undefined}
          >
            <MobileNavIcon name="map" />
            <span>Map</span>
          </Link>
        </nav>
      </div>
    </div>
  );
}

function readStoredTheme(): DisplayTheme {
  if (typeof window === "undefined") {
    return "dark";
  }
  try {
    const stored = window.sessionStorage.getItem(THEME_STORAGE_KEY);
    if (stored === "dark" || stored === "light") {
      return stored;
    }
  } catch {
    return "dark";
  }
  return "dark";
}

function MobileThemeControl() {
  const [theme, setTheme] = useState<DisplayTheme>("dark");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setTheme(readStoredTheme());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) {
      return;
    }
    document.documentElement.dataset.theme = theme;
    window.sessionStorage.setItem(THEME_STORAGE_KEY, theme);
    window.dispatchEvent(new CustomEvent("archive-display-change", { detail: { theme } }));
  }, [theme, hydrated]);

  return (
    <button
      type="button"
      className="mobile-archive-link mobile-theme-button"
      aria-label={`Theme ${theme}; toggle dark and light mode`}
      onClick={() => setTheme((current) => (current === "dark" ? "light" : "dark"))}
    >
      <MobileNavIcon name="theme" theme={theme} />
      <span>{theme === "dark" ? "Dark mode" : "Light mode"}</span>
    </button>
  );
}

function MobileNavIcon({ name, theme }: { name: MobileNavName; theme?: DisplayTheme }) {
  if (name === "theme") {
    if (theme === "light") {
      return (
        <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
          <circle cx="12" cy="12" r="4.4" />
          <path d="M12 3.6v2" />
          <path d="M12 18.4v2" />
          <path d="M3.6 12h2" />
          <path d="M18.4 12h2" />
          <path d="m6.1 6.1 1.4 1.4" />
          <path d="m16.5 16.5 1.4 1.4" />
          <path d="m17.9 6.1-1.4 1.4" />
          <path d="m7.5 16.5-1.4 1.4" />
        </svg>
      );
    }

    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M18.7 15.3A7.2 7.2 0 0 1 8.7 5.3 7.5 7.5 0 1 0 18.7 15.3Z" />
      </svg>
    );
  }

  if (name === "about") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M8.4 18.2 12 6.4l3.6 11.8" />
        <path d="M9.7 14.2h4.6" />
      </svg>
    );
  }

  if (name === "source") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M9.6 14.4 14.4 9.6" />
        <path d="M8.6 11.1 7.3 12.4a3 3 0 0 0 4.3 4.3l1.3-1.3" />
        <path d="M15.4 12.9 16.7 11.6a3 3 0 0 0-4.3-4.3l-1.3 1.3" />
      </svg>
    );
  }

  if (name === "density") {
    return (
      <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
        <path d="M6 18.2h12" />
        <path d="M8 15.8V10" />
        <path d="M12 15.8V6.8" />
        <path d="M16 15.8v-4.2" />
      </svg>
    );
  }

  return (
    <svg className="mobile-nav-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M5.2 7.3 9.5 5.4l5 2 4.3-1.9v11.2l-4.3 1.9-5-2-4.3 1.9z" />
      <path d="M9.5 5.4v11.2" />
      <path d="M14.5 7.4v11.2" />
    </svg>
  );
}
