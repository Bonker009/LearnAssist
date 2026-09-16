"use client";

import { Upload } from "lucide-react";
import * as React from "react";
import { ACCEPTED_TYPES, api } from "@/lib/api";
import { formatBytes } from "@/lib/utils";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

export function UploadCard({ onUploaded }: { onUploaded: () => void }) {
  const inputRef = React.useRef<HTMLInputElement>(null);
  const [file, setFile] = React.useState<File | null>(null);
  const [progress, setProgress] = React.useState(0);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [dragging, setDragging] = React.useState(false);

  async function send(selected: File) {
    setError(null);
    setBusy(true);
    setProgress(0);
    try {
      await api.upload(selected, setProgress);
      setFile(null);
      onUploaded();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  function choose(selected: File | undefined) {
    if (!selected) return;
    setFile(selected);
    void send(selected);
  }

  return (
    <Card>
      <CardContent className="pt-5">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            choose(e.dataTransfer.files[0]);
          }}
          className={[
            "flex flex-col items-center gap-3 rounded-[var(--radius-md)]",
            "border-2 border-dashed p-8 text-center transition-colors",
            dragging ? "border-primary bg-primary-soft" : "border-border",
          ].join(" ")}
        >
          <Upload aria-hidden className="size-6 text-text-subtle" />
          <div>
            <p className="font-medium">Upload a lecture</p>
            <p className="text-sm text-text-muted">
              PDF, PowerPoint, Word, audio or video
            </p>
          </div>

          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED_TYPES}
            className="sr-only"
            onChange={(e) => choose(e.target.files?.[0])}
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            Choose a file
          </Button>

          {busy && file && (
            <div className="w-full max-w-sm">
              <div className="mb-1 flex justify-between text-xs text-text-muted">
                <span className="truncate">{file.name}</span>
                <span>{formatBytes(file.size)}</span>
              </div>
              {/* Real determinate progress from the XHR, not a spinner: a large
                  recording takes long enough that "is it stuck?" is a real question. */}
              <div
                role="progressbar"
                aria-valuenow={progress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Upload progress"
                className="h-1.5 overflow-hidden rounded-full bg-surface-muted"
              >
                <div
                  className="h-full bg-primary transition-[width]"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
          )}

          {error && (
            <p role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
