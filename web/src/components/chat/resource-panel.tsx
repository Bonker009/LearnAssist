"use client";

import { IconArrowLeft, IconX } from "@tabler/icons-react";
import * as React from "react";
import type { NavigateHandler } from "@/components/citation";
import { FlashcardsPanel } from "@/components/flashcards-panel";
import { QuizPanel } from "@/components/quiz-panel";
import { SlidesPanel } from "@/components/slides-panel";
import { SourceViewer, type SourceViewerHandle } from "@/components/source-viewer";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DOC_TYPE_LABELS, STAGE_LABELS, type LectureDocument, type SourceRef } from "@/lib/types";
import { cn, formatBytes, formatTimestamp, hasKhmer } from "@/lib/utils";

export interface ResourcePanelHandle {
  show: (documentId: string, source?: SourceRef) => void;
}

function describe(document: LectureDocument): string {
  if (document.status === "FAILED") return document.job?.error ?? "Failed";
  if (document.status !== "READY") {
    const stage = document.job?.stage ?? "QUEUED";
    return `${STAGE_LABELS[stage]} · ${document.job?.progress ?? 0}%`;
  }
  const parts = [DOC_TYPE_LABELS[document.docType]];
  if (document.durationSec) parts.push(formatTimestamp(document.durationSec));
  else if (document.unitCount) {
    parts.push(`${document.unitCount} ${document.docType === "PPTX" ? "slides" : document.docType === "PDF" ? "pages" : "sections"}`);
  }
  if (document.sizeBytes) parts.push(formatBytes(document.sizeBytes));
  return parts.join(" · ");
}

/**
 * The resources attached to a chat, and a viewer for the selected one.
 *
 * Citation chips drive it: activating "notes.md · Section 3" selects that resource
 * and scrolls its viewer to the section.
 */
export const ResourcePanel = React.forwardRef<
  ResourcePanelHandle,
  {
    documents: LectureDocument[];
    onClose: () => void;
  }
>(function ResourcePanel({ documents, onClose }, ref) {
  const [selectedId, setSelectedId] = React.useState<string | null>(null);
  const [tab, setTab] = React.useState<string>("source");
  const viewer = React.useRef<SourceViewerHandle>(null);
  const pendingSource = React.useRef<SourceRef | null>(null);

  const selected = documents.find((d) => d.id === selectedId) ?? null;

  React.useImperativeHandle(ref, () => ({
    show(documentId, source) {
      setTab("source");
      if (documentId === selectedId && source) {
        viewer.current?.goTo(source);
        return;
      }
      pendingSource.current = source ?? null;
      setSelectedId(documentId);
    },
  }));

  // Navigate once the newly selected resource's viewer has mounted.
  React.useEffect(() => {
    if (!selected || !pendingSource.current) return;
    const source = pendingSource.current;
    pendingSource.current = null;
    const frame = requestAnimationFrame(() => viewer.current?.goTo(source));
    return () => cancelAnimationFrame(frame);
  }, [selected]);

  const navigate: NavigateHandler = React.useCallback((source: SourceRef) => {
    setTab("source");
    viewer.current?.goTo(source);
  }, []);

  return (
    <aside aria-label="Resources" className="flex h-full flex-col bg-background">
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-border px-3">
        {selected ? (
          <>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Back to all resources"
              onClick={() => setSelectedId(null)}
            >
              <IconArrowLeft size={16} />
            </Button>
            <h2 className="min-w-0 flex-1 truncate text-sm font-medium">{selected.filename}</h2>
          </>
        ) : (
          <h2 className="micro-label flex-1 text-text-muted">
            Resources <span className="text-text-subtle tabular-nums">({documents.length})</span>
          </h2>
        )}
        <Button variant="ghost" size="icon-sm" aria-label="Close resources" onClick={onClose}>
          <IconX size={16} />
        </Button>
      </div>

      {/* `relative` keeps absolutely positioned content (sr-only legends in the quiz)
          inside this scroller; otherwise it is placed against the page, makes the
          document taller than the viewport, and focusing a quiz answer scrolls the
          whole app out of view. */}
      <div className="relative min-h-0 flex-1 overflow-y-auto p-4">
        {!selected ? (
          documents.length === 0 ? (
            <p className="text-sm text-text-muted">
              Nothing attached yet. Use the + button in the message box to add files, links or
              notes.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {documents.map((document) => (
                <li key={document.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(document.id)}
                    className="flex w-full flex-col gap-0.5 rounded-lg border border-border bg-surface p-3 text-left shadow-sm transition-[border-color,box-shadow] duration-150 ease-out hover:border-border-strong hover:shadow-md"
                  >
                    <span className="truncate text-sm font-medium">{document.filename}</span>
                    <span
                      className={cn(
                        "truncate text-xs tabular-nums",
                        document.status === "FAILED"
                          ? "text-danger"
                          : document.status === "READY"
                            ? "text-text-muted"
                            : "text-primary-text",
                      )}
                    >
                      {describe(document)}
                    </span>
                    {document.status !== "READY" && document.status !== "FAILED" && (
                      <span
                        role="progressbar"
                        aria-valuenow={document.job?.progress ?? 0}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-label={`${document.filename} processing`}
                        className="mt-1.5 h-1 overflow-hidden rounded-full bg-surface-muted"
                      >
                        <span
                          className="block h-full bg-primary transition-[width]"
                          style={{ width: `${document.job?.progress ?? 0}%` }}
                        />
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )
        ) : (
          <Tabs value={tab} onValueChange={(value) => setTab(String(value))}>
            <TabsList className="w-full">
              <TabsTrigger value="source">Source</TabsTrigger>
              <TabsTrigger value="summary" disabled={!selected.summary}>
                Summary
              </TabsTrigger>
              <TabsTrigger value="quiz" disabled={selected.status !== "READY"}>
                Quiz
              </TabsTrigger>
              <TabsTrigger value="cards" disabled={selected.status !== "READY"}>
                Cards
              </TabsTrigger>
              <TabsTrigger value="slides" disabled={selected.status !== "READY"}>
                Slides
              </TabsTrigger>
            </TabsList>

            {/* Kept mounted so a citation can seek media that is already playing. */}
            <TabsContent value="source" keepMounted className="pt-2 data-[hidden]:hidden">
              <p className="mb-3 text-xs text-text-muted tabular-nums">{describe(selected)}</p>
              <SourceViewer key={selected.id} ref={viewer} document={selected} />
            </TabsContent>

            <TabsContent value="summary" className="pt-2">
              {selected.summary && (
                <div className="flex flex-col gap-4" lang={hasKhmer(selected.summary.summary) ? "km" : undefined}>
                  <p className="text-sm leading-relaxed text-text">{selected.summary.summary}</p>
                  {selected.summary.keyConcepts.length > 0 && (
                    <dl className="flex flex-col gap-3">
                      {selected.summary.keyConcepts.map((concept) => (
                        <div key={concept.term}>
                          <dt className="text-sm font-medium">{concept.term}</dt>
                          <dd className="text-sm text-text-muted">{concept.explanation}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </div>
              )}
            </TabsContent>

            <TabsContent value="quiz" className="pt-2">
              <QuizPanel documentId={selected.id} onNavigate={navigate} />
            </TabsContent>

            <TabsContent value="cards" className="pt-2">
              <FlashcardsPanel documentId={selected.id} onNavigate={navigate} />
            </TabsContent>

            <TabsContent value="slides" className="pt-2">
              <SlidesPanel documentId={selected.id} onNavigate={navigate} />
            </TabsContent>
          </Tabs>
        )}
      </div>
    </aside>
  );
});
