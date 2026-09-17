"use client";

import { FileText, Presentation, Play, ScanLine } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";
import type { Citation as CitationData, SourceRef } from "@/lib/types";

/**
 * The product's signature element.
 *
 * Every surface that shows where an answer came from — chat, quiz review, the
 * summary — renders this one component from a `SourceRef`. Centralising it is
 * what keeps a slide citation, a page citation and a timestamp citation looking
 * and behaving like the same idea, and it means adding a new source kind is a
 * change in one file.
 *
 * It is a button, not a link: activating it moves the viewer already on screen
 * rather than navigating away.
 */

function iconFor(source: SourceRef, ocr: boolean) {
  if (ocr) return ScanLine;
  if (source.kind === "slide") return Presentation;
  if (source.kind === "timestamp") return Play;
  return FileText;
}

export type NavigateHandler = (source: SourceRef, documentId?: string | null) => void;

export interface CitationProps {
  citation: CitationData;
  onNavigate?: NavigateHandler;
  /** Shown before the label when a chat has several resources, e.g. "notes.md · Section 2". */
  documentName?: string;
  className?: string;
}

/** Keep a filename short enough that a chip still reads as a chip. */
function shortName(name: string) {
  const base = name.replace(/\.[a-z0-9]{2,5}$/i, "");
  return base.length > 24 ? `${base.slice(0, 22)}…` : base;
}

export function Citation({ citation, onNavigate, documentName, className }: CitationProps) {
  const Icon = iconFor(citation.source, Boolean(citation.ocr));
  const interactive = Boolean(onNavigate);

  const describedBy = React.useId();

  return (
    <button
      type="button"
      disabled={!interactive}
      onClick={() => onNavigate?.(citation.source, citation.document_id)}
      aria-describedby={describedBy}
      title={citation.snippet}
      className={cn(
        "inline-flex items-center gap-1 align-baseline",
        "rounded-[var(--chip-radius)] border px-2 py-0.5",
        "border-citation-border bg-citation-bg text-citation",
        "text-xs font-medium",
        interactive && "hover:brightness-95 cursor-pointer",
        !interactive && "cursor-default",
        className,
      )}
    >
      <Icon aria-hidden className="size-3" />
      {documentName && (
        <span className="max-w-40 truncate opacity-80">{shortName(documentName)} ·</span>
      )}
      {citation.label}
      {citation.ocr && <span className="sr-only">(text read by OCR)</span>}
      {/* The snippet is available to assistive tech, not just as a hover title,
          which a keyboard or touch user never sees. */}
      <span id={describedBy} className="sr-only">
        Source: {documentName ? `${documentName}, ` : ""}
        {citation.label}. {citation.snippet}
      </span>
    </button>
  );
}

/**
 * Render an answer, replacing each `[n]` marker with its citation chip.
 *
 * Markers that survived server-side validation are the only ones present, so
 * anything unmatched here is rendered as plain text rather than a chip.
 */
export function AnswerWithCitations({
  content,
  citations,
  onNavigate,
  documentNames,
}: {
  content: string;
  citations: CitationData[];
  onNavigate?: NavigateHandler;
  /** document id -> filename; names are only shown when the answer cites several files. */
  documentNames?: Map<string, string>;
}) {
  const byMarker = new Map(citations.map((c) => [c.marker, c]));
  const parts = content.split(/(\[\d{1,3}\])/g);
  const cited = new Set(citations.map((c) => c.document_id).filter(Boolean));
  const showNames = cited.size > 1;

  return (
    <p className="leading-relaxed whitespace-pre-wrap text-text">
      {parts.map((part, index) => {
        const match = /^\[(\d{1,3})\]$/.exec(part);
        if (!match) return <React.Fragment key={index}>{part}</React.Fragment>;

        const citation = byMarker.get(Number(match[1]));
        if (!citation) return <React.Fragment key={index}>{part}</React.Fragment>;

        return (
          <Citation
            key={index}
            citation={citation}
            onNavigate={onNavigate}
            documentName={
              showNames && citation.document_id
                ? documentNames?.get(citation.document_id)
                : undefined
            }
            className="mx-0.5"
          />
        );
      })}
    </p>
  );
}
