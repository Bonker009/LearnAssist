"use client";

import { FileAudio, FileText, FileVideo, Presentation } from "lucide-react";
import Link from "next/link";
import * as React from "react";
import { AppShell } from "@/components/app-shell";
import { UploadCard } from "@/components/upload-card";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { STAGE_LABELS, type LectureDocument } from "@/lib/types";
import { formatBytes } from "@/lib/utils";

const ICONS = {
  PDF: FileText,
  DOCX: FileText,
  PPTX: Presentation,
  AUDIO: FileAudio,
  VIDEO: FileVideo,
} as const;

function StatusLine({ document }: { document: LectureDocument }) {
  if (document.status === "READY") {
    const unit =
      document.docType === "PPTX"
        ? `${document.unitCount} slides`
        : document.unitCount
          ? `${document.unitCount} pages`
          : "Ready";
    return <span className="text-success">{unit}</span>;
  }
  if (document.status === "FAILED") {
    return <span className="text-danger">{document.job?.error ?? "Failed"}</span>;
  }
  const stage = document.job?.stage ?? "QUEUED";
  return (
    <span className="text-text-muted">
      {STAGE_LABELS[stage]} · {document.job?.progress ?? 0}%
    </span>
  );
}

export default function HomePage() {
  const [documents, setDocuments] = React.useState<LectureDocument[] | null>(null);

  const load = React.useCallback(async () => {
    try {
      setDocuments(await api.listDocuments());
    } catch {
      setDocuments([]);
    }
  }, []);

  React.useEffect(() => {
    void load();
  }, [load]);

  // Poll only while something is actually processing, so an idle library is not
  // hammering the API every two seconds.
  const processing = documents?.some(
    (d) => d.status === "PROCESSING" || d.status === "UPLOADED",
  );
  React.useEffect(() => {
    if (!processing) return;
    const timer = setInterval(() => void load(), 2000);
    return () => clearInterval(timer);
  }, [processing, load]);

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Your lectures</h1>
          <p className="mt-1 text-sm text-text-muted">
            Upload lecture material and ask questions about it. Every answer shows the
            slide, page or timestamp it came from.
          </p>
        </div>

        <UploadCard onUploaded={load} />

        {documents === null ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>
        ) : documents.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <p className="font-medium">No lectures yet</p>
              <p className="mt-1 text-sm text-text-muted">
                Upload your first file above to get started.
              </p>
            </CardContent>
          </Card>
        ) : (
          <ul className="flex flex-col gap-3">
            {documents.map((document) => {
              const Icon = ICONS[document.docType] ?? FileText;
              const ready = document.status === "READY";
              const inner = (
                <Card className={ready ? "transition-colors hover:border-border-strong" : ""}>
                  <CardContent className="flex items-center gap-4 py-4">
                    <Icon aria-hidden className="size-5 shrink-0 text-text-subtle" />
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium">{document.filename}</p>
                      <p className="mt-0.5 text-sm">
                        <StatusLine document={document} />
                        <span className="text-text-subtle">
                          {" · "}
                          {formatBytes(document.sizeBytes)}
                        </span>
                      </p>
                    </div>
                  </CardContent>
                </Card>
              );

              return (
                <li key={document.id}>
                  {ready ? (
                    <Link href={`/documents/${document.id}`} className="block">
                      {inner}
                    </Link>
                  ) : (
                    inner
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </AppShell>
  );
}
