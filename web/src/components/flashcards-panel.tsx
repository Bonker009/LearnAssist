"use client";

import { RefreshCw, RotateCcw } from "lucide-react";
import * as React from "react";
import { api } from "@/lib/api";
import type { FlashcardDeck, SourceRef } from "@/lib/types";
import { cn, hasKhmer } from "@/lib/utils";
import { Citation } from "./citation";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

type Phase = "checking" | "idle" | "loading" | "studying" | "done";

/**
 * Flip a card, then grade yourself. "Again" sends the card to the back of this
 * session's queue; each grade is also saved, so the deck remembers what you knew.
 */
export function FlashcardsPanel({
  documentId,
  onNavigate,
}: {
  documentId: string;
  onNavigate?: (source: SourceRef) => void;
}) {
  const [phase, setPhase] = React.useState<Phase>("checking");
  const [deck, setDeck] = React.useState<FlashcardDeck | null>(null);
  // Indexes into deck.cards still to study this session, front first.
  const [queue, setQueue] = React.useState<number[]>([]);
  const [flipped, setFlipped] = React.useState(false);
  const [sessionSize, setSessionSize] = React.useState(0);
  // Cards marked "Again" at least once this session.
  const [missed, setMissed] = React.useState<Set<number>>(new Set());
  // Bumped on every grade so the next card mounts fresh, face up, with no flip-back
  // animation that would briefly show its answer.
  const [step, setStep] = React.useState(0);
  const [error, setError] = React.useState<string | null>(null);

  function study(next: FlashcardDeck, only?: (known: boolean | null) => boolean) {
    const indexes = next.cards.flatMap((card, i) => (!only || only(card.known) ? [i] : []));
    const session = indexes.length ? indexes : next.cards.map((_, i) => i);
    setDeck(next);
    setQueue(session);
    setSessionSize(session.length);
    setMissed(new Set());
    setFlipped(false);
    setPhase("studying");
  }

  React.useEffect(() => {
    let cancelled = false;
    api
      .latestFlashcards(documentId)
      .then((latest) => {
        if (cancelled) return;
        if (latest) study(latest);
        else setPhase("idle");
      })
      .catch(() => !cancelled && setPhase("idle"));
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  async function generate() {
    setError(null);
    setPhase("loading");
    try {
      study(await api.generateFlashcards(documentId, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate flashcards");
      setPhase(deck ? "done" : "idle");
    }
  }

  function grade(knewIt: boolean) {
    if (!deck || queue.length === 0) return;
    const [current, ...rest] = queue;
    const card = deck.cards[current];
    // Record the grade in the background; a failed save must not interrupt studying.
    api.reviewFlashcard(card.id, knewIt).catch(() => {});
    setDeck({
      ...deck,
      cards: deck.cards.map((c, i) => (i === current ? { ...c, known: knewIt } : c)),
    });
    if (!knewIt) setMissed((m) => new Set(m).add(current));
    const next = knewIt ? rest : [...rest, current];
    setQueue(next);
    setFlipped(false);
    setStep((s) => s + 1);
    if (next.length === 0) setPhase("done");
  }

  const card = deck && queue.length > 0 ? deck.cards[queue[0]] : null;
  const again = deck?.cards.filter((c) => c.known === false).length ?? 0;
  const remaining = new Set(queue).size;
  const toReview = queue.filter((i, at) => missed.has(i) && queue.indexOf(i) === at).length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>Flashcards</CardTitle>
        {phase !== "loading" && phase !== "checking" && (
          <Button variant="outline" size="sm" onClick={generate}>
            <RefreshCw aria-hidden className="size-3.5" />
            {deck ? "New deck" : "Generate"}
          </Button>
        )}
      </CardHeader>

      <CardContent className="flex flex-col gap-4">
        {error && (
          <p role="alert" className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        {phase === "checking" && <Skeleton className="h-44 w-full" />}

        {phase === "idle" && !error && (
          <p className="text-sm text-text-muted">
            Generate ten flashcards from across this lecture. Flip each one, then mark
            whether you knew it. Every card links back to the slide, page or moment it
            came from.
          </p>
        )}

        {phase === "loading" && (
          <div className="flex flex-col gap-3" aria-live="polite" aria-busy>
            <p className="text-sm text-text-muted">Writing flashcards from the lecture…</p>
            <Skeleton className="h-44 w-full" />
          </div>
        )}

        {phase === "studying" && deck && card && (
          <>
            <p className="text-xs text-text-muted tabular-nums" aria-live="polite">
              Card {sessionSize - remaining + 1} of {sessionSize}
              {toReview > 0 && ` · ${toReview} to review`}
            </p>

            <button
              key={step}
              type="button"
              onClick={() => setFlipped((f) => !f)}
              aria-pressed={flipped}
              aria-label={flipped ? "Show the front" : "Show the answer"}
              className="group h-52 w-full text-left [perspective:1000px]"
            >
              <span
                className={cn(
                  "relative block size-full transition-transform duration-200 ease-out [transform-style:preserve-3d] motion-reduce:transition-none",
                  flipped && "[transform:rotateY(180deg)]",
                )}
              >
                <span
                  aria-hidden={flipped}
                  className="absolute inset-0 flex flex-col items-center justify-center gap-3 rounded-[var(--radius-lg)] border border-border bg-surface p-5 text-center shadow-sm [backface-visibility:hidden] group-hover:border-border-strong"
                >
                  <span
                    lang={hasKhmer(card.front) ? "km" : undefined}
                    className="text-lg font-semibold text-text"
                  >
                    {card.front}
                  </span>
                  <span className="text-xs text-text-subtle">Tap to flip</span>
                </span>
                <span
                  aria-hidden={!flipped}
                  className="absolute inset-0 flex items-center justify-center overflow-y-auto rounded-[var(--radius-lg)] border border-primary bg-primary-soft p-5 text-center [backface-visibility:hidden] [transform:rotateY(180deg)]"
                >
                  <span
                    lang={hasKhmer(card.back) ? "km" : undefined}
                    className="text-sm leading-relaxed text-text"
                  >
                    {card.back}
                  </span>
                </span>
              </span>
            </button>

            {flipped ? (
              <div className="flex flex-col gap-3">
                <Citation
                  citation={{
                    marker: card.position + 1,
                    source: card.source,
                    label: card.sourceLabel,
                    snippet: card.snippet,
                  }}
                  onNavigate={onNavigate}
                  className="self-start"
                />
                <div className="grid grid-cols-2 gap-2">
                  <Button variant="outline" onClick={() => grade(false)}>
                    Again
                  </Button>
                  <Button onClick={() => grade(true)}>Knew it</Button>
                </div>
              </div>
            ) : (
              <p className="text-xs text-text-subtle">From {card.sourceLabel}</p>
            )}
          </>
        )}

        {phase === "done" && deck && (
          <div className="flex flex-col gap-3">
            <p
              aria-live="polite"
              className="rounded-[var(--radius-md)] bg-primary-soft px-4 py-3 font-medium text-primary-text"
            >
              Done. You knew {sessionSize - missed.size} of {sessionSize} on the first try.
            </p>
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" onClick={() => study(deck)}>
                <RotateCcw aria-hidden className="size-3.5" />
                Study all again
              </Button>
              {again > 0 && (
                <Button size="sm" onClick={() => study(deck, (known) => known === false)}>
                  Study {again} marked “Again”
                </Button>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
