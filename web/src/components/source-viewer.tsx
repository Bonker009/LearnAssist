"use client";

import * as React from "react";
import { api } from "@/lib/api";
import type { LectureDocument, SourceRef } from "@/lib/types";
import { Card } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

export interface SourceViewerHandle {
  goTo: (source: SourceRef) => void;
}

/**
 * Displays the original lecture file and jumps to a cited location.
 *
 * This is the other half of the citation promise: a "Slide 4" chip is only worth
 * showing if activating it actually puts slide 4 in front of the student.
 */
export const SourceViewer = React.forwardRef<SourceViewerHandle, { document: LectureDocument }>(
  function SourceViewer({ document }, ref) {
    const [url, setUrl] = React.useState<string | null>(null);
    const [failed, setFailed] = React.useState(false);
    const [page, setPage] = React.useState(1);
    const mediaRef = React.useRef<HTMLVideoElement | HTMLAudioElement>(null);

    React.useEffect(() => {
      void (async () => {
        try {
          setUrl((await api.getFileUrl(document.id)).url);
        } catch {
          setFailed(true);
        }
      })();
    }, [document.id]);

    React.useImperativeHandle(ref, () => ({
      goTo(source) {
        if (source.kind === "timestamp" && source.start_sec != null) {
          const media = mediaRef.current;
          if (media) {
            media.currentTime = source.start_sec;
            void media.play?.().catch(() => {
              /* autoplay may be blocked; the seek still happened */
            });
          }
          return;
        }
        // PDF viewers accept a #page= fragment. Changing it remounts the iframe,
        // which is the only portable way to drive the built-in viewer.
        const target = source.page_no ?? source.slide_no;
        if (target) setPage(target);
      },
    }));

    if (failed) {
      return (
        <Card className="flex h-full items-center justify-center p-6">
          <p className="text-sm text-text-muted">Could not load the original file.</p>
        </Card>
      );
    }

    if (!url) return <Skeleton className="h-full min-h-96 w-full" />;

    if (document.docType === "VIDEO") {
      return (
        <Card className="h-full overflow-hidden">
          <video
            ref={mediaRef as React.RefObject<HTMLVideoElement>}
            src={url}
            controls
            className="h-full w-full bg-black"
          />
        </Card>
      );
    }

    if (document.docType === "AUDIO") {
      return (
        <Card className="flex h-full items-center p-6">
          <audio
            ref={mediaRef as React.RefObject<HTMLAudioElement>}
            src={url}
            controls
            className="w-full"
          />
        </Card>
      );
    }

    if (document.docType === "PDF") {
      return (
        <Card className="h-full overflow-hidden">
          <iframe
            key={page}
            src={`${url}#page=${page}&view=FitH`}
            title={`${document.filename}, page ${page}`}
            className="h-full min-h-96 w-full"
          />
        </Card>
      );
    }

    // PowerPoint and Word have no in-browser viewer. Offering the download is
    // more honest than an iframe that renders a download prompt or nothing.
    return (
      <Card className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-text-muted">
          {document.docType} files can&apos;t be previewed in the browser.
        </p>
        <a
          href={url}
          download={document.filename}
          className="text-sm font-medium text-primary-text underline-offset-2 hover:underline"
        >
          Download {document.filename}
        </a>
      </Card>
    );
  },
);
