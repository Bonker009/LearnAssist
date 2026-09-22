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
 * While listening it can also show a ring that closes as silence builds toward an
 * automatic stop, and it can be a button (tap to finish).
 *
 * Plain CSS and one animation-frame loop (only while listening). No WebGL: it is
 * cheap enough to show several at once and renders the same in every browser. Motion
 * lives in globals.css under "AI presence" and is switched off for reduced motion.
 */

export type OrbState = "idle" | "listening" | "thinking";

/**
 * Writes the live mic level into --ai-level, and how close silence is to ending the
 * recording into --ai-silence, every frame while listening, without re-rendering React.
 */
function useVoiceVariables(
  element: React.RefObject<HTMLElement | null>,
  levelRef: React.RefObject<number> | undefined,
  silenceRef: React.RefObject<number> | undefined,
  active: boolean,
) {
  React.useEffect(() => {
    const node = element.current;
    if (!node) return;
    if (!active || (!levelRef && !silenceRef)) {
      node.style.setProperty("--ai-level", "0");
      node.style.setProperty("--ai-silence", "0");
      return;
    }
    let frame = 0;
    let smoothed = 0;
    let closing = 0;
    const tick = () => {
      // Ease towards the target so the glow swells with speech instead of flickering.
      smoothed += ((levelRef?.current ?? 0) - smoothed) * 0.25;
      // The ring closes steadily with silence but snaps open when the voice returns.
      const silence = silenceRef?.current ?? 0;
      closing = silence < closing ? silence : closing + (silence - closing) * 0.3;
      node.style.setProperty("--ai-level", smoothed.toFixed(3));
      node.style.setProperty("--ai-silence", closing.toFixed(3));
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [element, levelRef, silenceRef, active]);
}

const RING_LENGTH = 2 * Math.PI * 48;

export function AiOrb({
  state = "idle",
  levelRef,
  silenceRef,
  onPress,
  pressLabel,
  className,
}: {
  state?: OrbState;
  /** Live 0..1 microphone level, read every frame while listening. */
  levelRef?: React.RefObject<number>;
  /**
   * 0..1 progress toward stopping on silence. While listening, a ring closes around
   * the orb and the glow dims, so the student sees the recording is about to end.
   */
  silenceRef?: React.RefObject<number>;
  /** Makes the orb a button, e.g. to finish listening early. */
  onPress?: () => void;
  pressLabel?: string;
  className?: string;
}) {
  const root = React.useRef<HTMLElement>(null);
  useVoiceVariables(root, levelRef, silenceRef, state === "listening");

  const content = (
    <>
      <div className="ai-orb-bloom" />
      <div className="ai-orb-body">
        <div className="ai-orb-gloss" />
      </div>
      <svg viewBox="0 0 24 24" className="ai-orb-sparkle">
        {/* A four-point spark: the "AI is here" mark. */}
        <path d="M12 2c.6 4.9 2.1 7.4 4.6 8.7 1.4.7 3.2 1.1 5.4 1.3-2.2.2-4 .6-5.4 1.3-2.5 1.3-4 3.8-4.6 8.7-.6-4.9-2.1-7.4-4.6-8.7C6 12.6 4.2 12.2 2 12c2.2-.2 4-.6 5.4-1.3C9.9 9.4 11.4 6.9 12 2Z" />
      </svg>
      {silenceRef && (
        <svg viewBox="0 0 100 100" className="ai-orb-ring" style={{ "--ai-ring": RING_LENGTH } as React.CSSProperties}>
          <circle cx="50" cy="50" r="48" />
        </svg>
      )}
    </>
  );
  const classes = cn("ai-orb relative aspect-square shrink-0", className);

  if (onPress) {
    return (
      <button
        ref={root as React.RefObject<HTMLButtonElement>}
        type="button"
        data-state={state}
        aria-label={pressLabel}
        title={pressLabel}
        onClick={onPress}
        className={cn(classes, "cursor-pointer rounded-full")}
      >
        {content}
      </button>
    );
  }
  return (
    <div ref={root as React.RefObject<HTMLDivElement>} aria-hidden data-state={state} className={classes}>
      {content}
    </div>
  );
}
