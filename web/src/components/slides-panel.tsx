"use client";

import { Download, ExternalLink, FileText, RefreshCw } from "lucide-react";
import * as React from "react";
import { api, apiUrl } from "@/lib/api";
import type { SlideDeck, SourceRef } from "@/lib/types";
import { hasKhmer } from "@/lib/utils";
import { Citation } from "./citation";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

const POLL_MS = 3000;

const STAGE: Record<string, string> = {
  GENERATING: "Writing the outline from the lecture…",
  RENDERING: "Building the slides and the PDF…",
};

/**
 * A Slidev deck generated from the lecture. Generation takes minutes (the outline,
 * then a Slidev build and PDF export), so the deck is polled like an ingest job.
 */
export function SlidesPanel({
  documentId,
  onNavigate,
}: {
  documentId: string;
  onNavigate?: (source: SourceRef) => void;
}) {
  const [checking, setChecking] = React.useState(true);
  const [deck, setDeck] = React.useState<SlideDeck | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    let cancelled = false;
    api
      .latestSlides(documentId)
      .then((latest) => !cancelled && setDeck(latest))
      .catch(() => {})
      .finally(() => !cancelled && setChecking(false));
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const working = deck?.status === "GENERATING" || deck?.status === "RENDERING";
  const deckId = deck?.id;

  React.useEffect(() => {
    if (!working || !deckId) return;
    const timer = window.setInterval(async () => {
      try {
        setDeck(await api.getSlideDeck(deckId));
      } catch {
        /* keep polling; a transient failure should not end the wait */
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [working, deckId]);

  async function generate() {
    setError(null);
    try {
      setDeck(await api.generateSlides(documentId, 8));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start generating slides");
    }
  }

  /** Download links are presigned for minutes only, so fetch fresh ones on click. */
  async function download(kind: "pdfUrl" | "markdownUrl") {
    if (!deck) return;
    try {
      const fresh = await api.getSlideDeck(deck.id);
      const url = fresh[kind];
      if (url) window.location.assign(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not download");
    }
  }

  const viewUrl = deck?.viewPath ? apiUrl(deck.viewPath) : null;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>Slides</CardTitle>
        {!checking && !working && (
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

        {checking && <Skeleton className="aspect-video w-full" />}

        {!checking && !deck && !error && (
          <p className="text-sm text-text-muted">
            Generate an eight-slide Slidev presentation of this lecture. Present it here or
            full screen, or download it as a PDF or as Slidev markdown. Every slide shows
            the pages or moments it came from.
          </p>
        )}

        {working && deck && (
          <div className="flex flex-col gap-3" aria-live="polite" aria-busy>
            <p className="text-sm text-text-muted">{STAGE[deck.status]}</p>
            <p className="text-xs text-text-subtle">This usually takes a few minutes.</p>
            <Skeleton className="aspect-video w-full" />
          </div>
        )}

        {deck?.status === "FAILED" && (
          <p role="alert" className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
            {deck.error ?? "Could not generate the slides."}
          </p>
        )}

        {deck?.status === "READY" && viewUrl && (
          <>
            <iframe
              key={viewUrl}
              src={viewUrl}
              title={`Slides: ${deck.title}`}
              allow="fullscreen"
              className="aspect-video w-full rounded-[var(--radius-md)] border border-border bg-surface"
            />
            <div className="flex flex-wrap gap-2">
              <Button size="sm" onClick={() => window.open(viewUrl, "_blank", "noopener")}>
                <ExternalLink aria-hidden className="size-3.5" />
                Present
              </Button>
              {deck.pdfUrl && (
                <Button variant="outline" size="sm" onClick={() => download("pdfUrl")}>
                  <Download aria-hidden className="size-3.5" />
                  PDF
                </Button>
              )}
              <Button variant="outline" size="sm" onClick={() => download("markdownUrl")}>
                <FileText aria-hidden className="size-3.5" />
                slides.md
              </Button>
            </div>

            <ol className="flex flex-col gap-3" aria-label="Slide outline">
              {deck.slides.map((slide, index) => (
                <li key={index} className="flex flex-col gap-1.5">
                  <p
                    lang={hasKhmer(slide.title) ? "km" : undefined}
                    className="text-sm font-medium"
                  >
                    <span className="mr-1.5 text-text-subtle tabular-nums">{index + 2}.</span>
                    {slide.title}
                  </p>
                  <div className="flex flex-wrap gap-1.5 pl-5">
                    {slide.sources.map((source, i) => (
                      <Citation
                        key={i}
                        citation={{
                          marker: i + 1,
                          source: source.source,
                          label: source.sourceLabel,
                          snippet: slide.bullets.join(" · "),
                        }}
                        onNavigate={onNavigate}
                      />
                    ))}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </CardContent>
    </Card>
  );
}
