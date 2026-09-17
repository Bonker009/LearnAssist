"use client";

import { ExternalLink, ScanLine } from "lucide-react";
import * as React from "react";
import { api } from "@/lib/api";
import type { LectureDocument, ReaderSnapshot, SourceRef } from "@/lib/types";
import { cn, hasKhmer } from "@/lib/utils";
import { Skeleton } from "./ui/skeleton";

export interface SourceViewerHandle {
  goTo: (source: SourceRef) => void;
}

/** Extract a YouTube video id from the URL shapes the API accepts. */
export function youtubeId(url: string | null): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^(www|m|music)\./, "");
    let id: string | null = null;
    if (host === "youtu.be") id = parsed.pathname.split("/")[1] ?? null;
    else if (host === "youtube.com") {
      id =
        parsed.searchParams.get("v") ??
        parsed.pathname.match(/^\/(?:shorts|live|embed|v)\/([^/]+)/)?.[1] ??
        null;
    }
    return id && /^[\w-]{11}$/.test(id) ? id : null;
  } catch {
    return null;
  }
}

/**
 * Displays the original resource and jumps to a cited location.
 *
 * This is the other half of the citation promise: a "Slide 4" chip is only worth
 * showing if activating it actually puts slide 4 in front of the student.
 */
export const SourceViewer = React.forwardRef<SourceViewerHandle, { document: LectureDocument }>(
  function SourceViewer({ document }, ref) {
    const [url, setUrl] = React.useState<string | null>(null);
    const [failed, setFailed] = React.useState(false);
    const [page, setPage] = React.useState(1);
    const [seek, setSeek] = React.useState<{ at: number; nonce: number } | null>(null);
    const mediaRef = React.useRef<HTMLVideoElement | HTMLAudioElement>(null);
    const readerRef = React.useRef<ReaderHandle>(null);

    const usesFile = ["PDF", "AUDIO", "VIDEO", "IMAGE"].includes(document.docType);

    // No reset on document change: the panel keys this component by document id,
    // so a different document is always a fresh mount.
    React.useEffect(() => {
      if (!usesFile) return;
      void (async () => {
        try {
          setUrl((await api.getFileUrl(document.id)).url);
        } catch {
          setFailed(true);
        }
      })();
    }, [document.id, usesFile]);

    React.useImperativeHandle(ref, () => ({
      goTo(source) {
        if (source.kind === "timestamp" && source.start_sec != null) {
          if (document.docType === "YOUTUBE") {
            // The embed can't be driven without the IFrame API; remounting at
            // ?start= is the dependency-free way to seek it.
            setSeek({ at: Math.floor(source.start_sec), nonce: Date.now() });
            return;
          }
          const media = mediaRef.current;
          if (media) {
            media.currentTime = source.start_sec;
            void media.play?.().catch(() => {
              /* autoplay may be blocked; the seek still happened */
            });
          }
          return;
        }
        const target = source.page_no ?? source.slide_no;
        if (!target) return;
        if (document.docType === "PDF") {
          // PDF viewers accept a #page= fragment. Changing it remounts the iframe,
          // which is the only portable way to drive the built-in viewer.
          setPage(target);
        } else {
          readerRef.current?.scrollTo(target);
        }
      },
    }));

    if (document.docType === "YOUTUBE") {
      const id = youtubeId(document.sourceUrl);
      if (!id) return <Unavailable message="This video link can't be embedded." />;
      const start = seek ? `&start=${seek.at}&autoplay=1` : "";
      return (
        <div className="flex flex-col gap-3">
          <div className="aspect-video overflow-hidden rounded-lg bg-black">
            <iframe
              key={seek?.nonce ?? "initial"}
              src={`https://www.youtube-nocookie.com/embed/${id}?rel=0${start}`}
              title={document.filename}
              allow="autoplay; encrypted-media; picture-in-picture"
              allowFullScreen
              className="size-full"
            />
          </div>
          <OriginalLink href={document.sourceUrl} label="Open on YouTube" />
        </div>
      );
    }

    if (!usesFile) {
      return (
        <Reader
          ref={readerRef}
          document={document}
          header={
            document.docType === "WEB" ? (
              <OriginalLink href={document.sourceUrl} label="Open the original page" />
            ) : undefined
          }
        />
      );
    }

    if (failed) return <Unavailable message="Could not load the original file." />;
    if (!url) return <Skeleton className="h-96 w-full" />;

    if (document.docType === "VIDEO") {
      return (
        <video
          ref={mediaRef as React.RefObject<HTMLVideoElement>}
          src={url}
          controls
          className="w-full rounded-lg bg-black"
        />
      );
    }

    if (document.docType === "AUDIO") {
      return (
        <audio
          ref={mediaRef as React.RefObject<HTMLAudioElement>}
          src={url}
          controls
          className="w-full"
        />
      );
    }

    if (document.docType === "IMAGE") {
      return (
        <div className="flex flex-col gap-4">
          {/* A presigned object URL: next/image would try to optimise it server-side. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={url}
            alt={document.filename}
            className="max-h-[60dvh] w-full rounded-lg border border-border object-contain"
          />
          <Reader ref={readerRef} document={document} compact />
        </div>
      );
    }

    return (
      <iframe
        key={page}
        src={`${url}#page=${page}&view=FitH`}
        title={`${document.filename}, page ${page}`}
        className="h-[calc(100dvh-14rem)] min-h-96 w-full rounded-lg border border-border"
      />
    );
  },
);

function OriginalLink({ href, label }: { href: string | null; label: string }) {
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex w-fit items-center gap-1.5 text-sm text-primary-text underline-offset-2 hover:underline"
    >
      <ExternalLink aria-hidden className="size-3.5" />
      {label}
    </a>
  );
}

function Unavailable({ message }: { message: string }) {
  return (
    <div className="flex min-h-48 items-center justify-center rounded-lg border border-dashed border-border p-6">
      <p className="text-sm text-text-muted">{message}</p>
    </div>
  );
}

interface ReaderHandle {
  scrollTo: (unit: number) => void;
}

/**
 * The extracted text of a resource, section by section.
 *
 * Word, PowerPoint, web pages and notes have no browser viewer that can jump to
 * "Section 3", so citations land here instead: the cited section is scrolled into
 * view and briefly highlighted.
 */
const Reader = React.forwardRef<
  ReaderHandle,
  { document: LectureDocument; header?: React.ReactNode; compact?: boolean }
>(function Reader({ document, header, compact }, ref) {
  const [snapshot, setSnapshot] = React.useState<ReaderSnapshot | null>(null);
  const [failed, setFailed] = React.useState(false);
  const [highlight, setHighlight] = React.useState<number | null>(null);
  const container = React.useRef<HTMLDivElement>(null);
  const pending = React.useRef<number | null>(null);

  React.useEffect(() => {
    void (async () => {
      try {
        setSnapshot(await api.getReader(document.id));
      } catch {
        setFailed(true);
      }
    })();
  }, [document.id]);

  const scrollTo = React.useCallback((unit: number) => {
    const element = container.current?.querySelector<HTMLElement>(`[data-unit="${unit}"]`);
    if (!element) {
      // Not rendered yet: a citation clicked while the snapshot is loading.
      pending.current = unit;
      return;
    }
    element.scrollIntoView({ behavior: "smooth", block: "start" });
    setHighlight(unit);
    window.setTimeout(() => setHighlight((current) => (current === unit ? null : current)), 2400);
  }, []);

  React.useImperativeHandle(ref, () => ({ scrollTo }), [scrollTo]);

  React.useEffect(() => {
    if (snapshot && pending.current != null) {
      const unit = pending.current;
      pending.current = null;
      requestAnimationFrame(() => scrollTo(unit));
    }
  }, [snapshot, scrollTo]);

  if (failed) {
    return (
      <div className="flex flex-col gap-3">
        {header}
        <Unavailable
          message={
            document.status === "READY"
              ? "No text preview is available for this resource."
              : "The preview appears once processing finishes."
          }
        />
      </div>
    );
  }
  if (!snapshot) {
    return (
      <div className="flex flex-col gap-3">
        {header}
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-24 w-full" />
        ))}
      </div>
    );
  }

  return (
    <div ref={container} className="flex flex-col gap-3">
      {header}
      {snapshot.units.map((unit, index) => {
        const number = unit.page_no ?? unit.slide_no ?? index + 1;
        const khmer = hasKhmer(unit.text);
        return (
          <section
            key={`${number}-${index}`}
            data-unit={number}
            className={cn(
              "scroll-mt-4 rounded-lg border border-border bg-surface p-4 transition-colors duration-200 ease-out",
              highlight === number && "border-citation-border bg-citation-bg",
            )}
          >
            <div className="mb-1.5 flex items-center gap-2 text-xs font-medium text-citation">
              {unit.ocr && <ScanLine aria-label="Text read by OCR" className="size-3.5" />}
              {unit.label}
              {unit.title && <span className="truncate text-text-muted">· {unit.title}</span>}
            </div>
            <p
              lang={khmer ? "km" : undefined}
              className={cn(
                "text-sm leading-relaxed whitespace-pre-wrap text-text",
                compact && "line-clamp-[12]",
              )}
            >
              {unit.text}
            </p>
          </section>
        );
      })}
    </div>
  );
});
