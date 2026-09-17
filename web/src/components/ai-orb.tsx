"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * The assistant's presence: a soft glow in the brand tints with a sparkle at its heart.
 *
 * - idle      — colours drift slowly and the glow breathes
 * - listening — the glow swells with the microphone level while the student speaks
 * - thinking  — colours turn faster and the sparkle pulses while an answer is on its way
 *
 * Plain CSS and one animation-frame loop (only while listening). No WebGL: it is
 * cheap enough to show several at once and renders the same in every browser. Motion
 * lives in globals.css under "AI presence" and is switched off for reduced motion.
 */

export type OrbState = "idle" | "listening" | "thinking";

/** Writes the live mic level into a CSS variable, without re-rendering React. */
function useLevelVariable(
  element: React.RefObject<HTMLElement | null>,
  levelRef: React.RefObject<number> | undefined,
  active: boolean,
) {
  React.useEffect(() => {
    const node = element.current;
    if (!node) return;
    if (!active || !levelRef) {
      node.style.setProperty("--ai-level", "0");
      return;
    }
    let frame = 0;
    let smoothed = 0;
    const tick = () => {
      // Ease towards the target so the glow swells with speech instead of flickering.
      smoothed += ((levelRef.current ?? 0) - smoothed) * 0.25;
      node.style.setProperty("--ai-level", smoothed.toFixed(3));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [element, levelRef, active]);
}

export function AiOrb({
  state = "idle",
  levelRef,
  className,
}: {
  state?: OrbState;
  /** Live 0..1 microphone level, read every frame while listening. */
  levelRef?: React.RefObject<number>;
  className?: string;
}) {
  const root = React.useRef<HTMLDivElement>(null);
  useLevelVariable(root, levelRef, state === "listening");

  return (
    <div
      ref={root}
      aria-hidden
      data-state={state}
      className={cn("ai-orb relative aspect-square shrink-0", className)}
    >
      <div className="ai-orb-bloom" />
      <div className="ai-orb-body">
        <div className="ai-orb-gloss" />
      </div>
      <svg viewBox="0 0 24 24" className="ai-orb-sparkle">
        {/* A four-point spark: the "AI is here" mark. */}
        <path d="M12 2c.6 4.9 2.1 7.4 4.6 8.7 1.4.7 3.2 1.1 5.4 1.3-2.2.2-4 .6-5.4 1.3-2.5 1.3-4 3.8-4.6 8.7-.6-4.9-2.1-7.4-4.6-8.7C6 12.6 4.2 12.2 2 12c2.2-.2 4-.6 5.4-1.3C9.9 9.4 11.4 6.9 12 2Z" />
      </svg>
    </div>
  );
}

/**
 * Flowing waves in the brand tints, for the bottom edge of a full-screen view.
 * They quicken while thinking and rise with the voice while listening.
 */
export function AiWaves({
  state = "idle",
  levelRef,
  className,
}: {
  state?: OrbState;
  levelRef?: React.RefObject<number>;
  className?: string;
}) {
  const root = React.useRef<HTMLDivElement>(null);
  useLevelVariable(root, levelRef, state === "listening");

  // One period of a gentle sine, drawn twice so the loop is seamless when the strip
  // slides left by half its width.
  const wave = (amplitude: number, offset: number) => {
    const points: string[] = [];
    for (let x = 0; x <= 800; x += 10) {
      const y = 60 + offset + Math.sin((x / 400) * Math.PI * 2) * amplitude;
      points.push(`${x},${y.toFixed(1)}`);
    }
    return `M${points.join(" L")} L800,120 L0,120 Z`;
  };

  return (
    <div
      ref={root}
      aria-hidden
      data-state={state}
      className={cn("ai-waves pointer-events-none overflow-hidden", className)}
    >
      {[
        { amplitude: 14, offset: 6, className: "ai-wave-1" },
        { amplitude: 10, offset: 14, className: "ai-wave-2" },
        { amplitude: 7, offset: 22, className: "ai-wave-3" },
      ].map((layer) => (
        <svg
          key={layer.className}
          viewBox="0 0 800 120"
          preserveAspectRatio="none"
          className={cn("ai-wave", layer.className)}
        >
          <path d={wave(layer.amplitude, layer.offset)} />
        </svg>
      ))}
    </div>
  );
}
