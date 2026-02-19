"use client";

import { useEffect, useMemo, useState } from "react";

type TourStep = {
  targetId: string;
  title: string;
  body: string;
};

type OnboardingTourProps = {
  enabled: boolean;
  storageKey: string;
  steps: TourStep[];
  backLabel: string;
  nextLabel: string;
  skipLabel: string;
  doneLabel: string;
};

type RectLike = {
  top: number;
  left: number;
  width: number;
  height: number;
};

const POPOVER_WIDTH = 320;

export function OnboardingTour({
  enabled,
  storageKey,
  steps,
  backLabel,
  nextLabel,
  skipLabel,
  doneLabel
}: OnboardingTourProps) {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const [anchorRect, setAnchorRect] = useState<RectLike | null>(null);

  useEffect(() => {
    if (!enabled) {
      setOpen(false);
      return;
    }
    try {
      if (window.localStorage.getItem(storageKey) === "1") return;
      setOpen(true);
    } catch {
      setOpen(true);
    }
  }, [enabled, storageKey]);

  useEffect(() => {
    if (!open) return;

    const update = () => {
      const step = steps[index];
      if (!step) {
        setAnchorRect(null);
        return;
      }
      const el = document.querySelector(`[data-guide-id=\"${step.targetId}\"]`) as HTMLElement | null;
      if (!el) {
        setAnchorRect(null);
        return;
      }
      const rect = el.getBoundingClientRect();
      setAnchorRect({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height
      });
    };

    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, index, steps]);

  const step = steps[index];
  const isLast = index >= steps.length - 1;

  const popoverStyle = useMemo(() => {
    if (typeof window === "undefined") return { top: 24, left: 24 };
    if (!anchorRect) {
      return {
        top: Math.max(20, Math.round(window.innerHeight * 0.18)),
        left: Math.max(16, Math.round((window.innerWidth - POPOVER_WIDTH) / 2))
      };
    }

    const margin = 12;
    let top = anchorRect.top + anchorRect.height + margin;
    const maxTop = window.innerHeight - 190;
    if (top > maxTop) {
      top = Math.max(16, anchorRect.top - 170);
    }

    const centerX = anchorRect.left + anchorRect.width / 2;
    let left = centerX - POPOVER_WIDTH / 2;
    left = Math.max(12, Math.min(left, window.innerWidth - POPOVER_WIDTH - 12));

    return {
      top: Math.round(top),
      left: Math.round(left)
    };
  }, [anchorRect]);

  function closeTour() {
    setOpen(false);
    try {
      window.localStorage.setItem(storageKey, "1");
    } catch {
      // ignore storage failures
    }
  }

  if (!open || !step) return null;

  return (
    <>
      <button className="tour-backdrop" aria-label={skipLabel} onClick={closeTour} />
      {anchorRect ? (
        <div
          className="tour-spotlight"
          style={{
            top: anchorRect.top - 4,
            left: anchorRect.left - 4,
            width: anchorRect.width + 8,
            height: anchorRect.height + 8
          }}
        />
      ) : null}

      <div className="tour-popover" role="dialog" aria-live="polite" style={popoverStyle}>
        <div className="tour-step">{index + 1}/{steps.length}</div>
        <h3>{step.title}</h3>
        <div className="muted" style={{ lineHeight: 1.55 }}>
          {step.body}
        </div>

        <div className="row" style={{ justifyContent: "space-between", marginTop: 12 }}>
          <div className="row">
            {index > 0 ? (
              <button className="btn" type="button" onClick={() => setIndex((n) => Math.max(0, n - 1))}>
                {backLabel}
              </button>
            ) : null}
          </div>
          <div className="row">
            <button className="btn" type="button" onClick={closeTour}>
              {skipLabel}
            </button>
            <button
              className="btn primary"
              type="button"
              onClick={() => {
                if (isLast) {
                  closeTour();
                  return;
                }
                setIndex((n) => Math.min(steps.length - 1, n + 1));
              }}
            >
              {isLast ? doneLabel : nextLabel}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
