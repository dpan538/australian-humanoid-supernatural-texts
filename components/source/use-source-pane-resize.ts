"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent as ReactPointerEvent, RefObject } from "react";

const SOURCE_PANE_STORAGE_KEY = "source-terminal-left-width";
const DEFAULT_RATIO = 38;
const MIN_RATIO = 28;
const MAX_RATIO = 58;
const MIN_RIGHT_PX = 420;

export function useSourcePaneResize(rootRef: RefObject<HTMLElement | null>) {
  const ratioRef = useRef(DEFAULT_RATIO);
  const dragRef = useRef<{ pointerId: number; frame: number | null; nextRatio: number }>({
    pointerId: -1,
    frame: null,
    nextRatio: DEFAULT_RATIO,
  });
  const [ratio, setRatio] = useState(DEFAULT_RATIO);
  const [dragging, setDragging] = useState(false);

  const applyRatio = useCallback((nextRatio: number, persist = false, render = false) => {
    const root = rootRef.current;
    const constrained = constrainRatio(root, nextRatio);
    ratioRef.current = constrained;
    root?.style.setProperty("--source-left-width", `${constrained}%`);
    if (render) {
      setRatio(constrained);
    }
    if (persist) {
      window.localStorage.setItem(SOURCE_PANE_STORAGE_KEY, String(Math.round(constrained)));
    }
    return constrained;
  }, [rootRef]);

  useEffect(() => {
    const saved = Number(window.localStorage.getItem(SOURCE_PANE_STORAGE_KEY));
    applyRatio(Number.isFinite(saved) ? saved : DEFAULT_RATIO, false, true);
  }, [applyRatio]);

  const reset = useCallback(() => {
    applyRatio(DEFAULT_RATIO, true, true);
  }, [applyRatio]);

  const onPointerDown = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const root = rootRef.current;
    if (!root || window.matchMedia("(max-width: 720px)").matches) {
      return;
    }
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current.pointerId = event.pointerId;
    dragRef.current.nextRatio = ratioRef.current;
    setDragging(true);
    document.documentElement.classList.add("source-pane-resizing");
  }, [rootRef]);

  const onPointerMove = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    const root = rootRef.current;
    if (!root || dragRef.current.pointerId !== event.pointerId) {
      return;
    }
    const bounds = root.getBoundingClientRect();
    const rawRatio = ((event.clientX - bounds.left) / bounds.width) * 100;
    dragRef.current.nextRatio = constrainRatio(root, rawRatio);
    if (dragRef.current.frame !== null) {
      return;
    }
    dragRef.current.frame = window.requestAnimationFrame(() => {
      dragRef.current.frame = null;
      root.style.setProperty("--source-left-width", `${dragRef.current.nextRatio}%`);
      ratioRef.current = dragRef.current.nextRatio;
    });
  }, [rootRef]);

  const finishDrag = useCallback((pointerId?: number) => {
    if (pointerId !== undefined && dragRef.current.pointerId !== pointerId) {
      return;
    }
    if (dragRef.current.frame !== null) {
      window.cancelAnimationFrame(dragRef.current.frame);
      dragRef.current.frame = null;
    }
    dragRef.current.pointerId = -1;
    setDragging(false);
    document.documentElement.classList.remove("source-pane-resizing");
    applyRatio(ratioRef.current, true, true);
  }, [applyRatio]);

  const onPointerUp = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    finishDrag(event.pointerId);
  }, [finishDrag]);

  const onPointerCancel = useCallback((event: ReactPointerEvent<HTMLElement>) => {
    finishDrag(event.pointerId);
  }, [finishDrag]);

  const onKeyDown = useCallback((event: ReactKeyboardEvent<HTMLElement>) => {
    let nextRatio = ratioRef.current;
    const step = event.shiftKey ? 8 : 2;
    if (event.key === "ArrowLeft") {
      nextRatio -= step;
    } else if (event.key === "ArrowRight") {
      nextRatio += step;
    } else if (event.key === "Home") {
      nextRatio = MIN_RATIO;
    } else if (event.key === "End") {
      nextRatio = MAX_RATIO;
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      reset();
      return;
    } else {
      return;
    }
    event.preventDefault();
    applyRatio(nextRatio, true, true);
  }, [applyRatio, reset]);

  useEffect(() => {
    return () => {
      if (dragRef.current.frame !== null) {
        window.cancelAnimationFrame(dragRef.current.frame);
      }
      document.documentElement.classList.remove("source-pane-resizing");
    };
  }, []);

  return {
    ratio,
    dragging,
    separatorProps: {
      role: "separator",
      "aria-orientation": "vertical" as const,
      "aria-valuemin": MIN_RATIO,
      "aria-valuemax": MAX_RATIO,
      "aria-valuenow": Math.round(ratio),
      tabIndex: 0,
      onDoubleClick: reset,
      onKeyDown,
      onPointerCancel,
      onPointerDown,
      onPointerMove,
      onPointerUp,
    },
  };
}

function constrainRatio(root: HTMLElement | null, ratio: number) {
  const maxForRightWidth = root ? ((root.getBoundingClientRect().width - MIN_RIGHT_PX) / root.getBoundingClientRect().width) * 100 : MAX_RATIO;
  const max = Math.min(MAX_RATIO, Number.isFinite(maxForRightWidth) ? maxForRightWidth : MAX_RATIO);
  return Math.max(MIN_RATIO, Math.min(max, ratio));
}
