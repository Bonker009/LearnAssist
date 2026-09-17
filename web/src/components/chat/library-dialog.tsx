"use client";

import { IconCheck, IconSearch } from "@tabler/icons-react";
import * as React from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { LectureDocument } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Reuse resources already in the library. Attaching is free: the document is
 * already indexed, so it is ready to answer from immediately.
 */
export function LibraryDialog(props: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  attachedIds: Set<string>;
  onAttach: (documentIds: string[]) => Promise<void>;
}) {
  return (
    <Dialog open={props.open} onOpenChange={(next) => props.onOpenChange(next)}>
      {/* Mounted only while open, so every opening starts with a fresh list and selection. */}
      {props.open && <LibraryPicker {...props} />}
    </Dialog>
  );
}

function LibraryPicker({
  onOpenChange,
  attachedIds,
  onAttach,
}: {
  onOpenChange: (open: boolean) => void;
  attachedIds: Set<string>;
  onAttach: (documentIds: string[]) => Promise<void>;
}) {
  const [documents, setDocuments] = React.useState<LectureDocument[] | null>(null);
  const [selected, setSelected] = React.useState<Set<string>>(new Set());
  const [query, setQuery] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    api.listDocuments().then(setDocuments, () => setDocuments([]));
  }, []);

  const visible = (documents ?? []).filter(
    (d) => d.status !== "FAILED" && d.filename.toLowerCase().includes(query.toLowerCase()),
  );

  function toggle(id: string) {
    setSelected((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function attach() {
    setBusy(true);
    setError(null);
    try {
      await onAttach([...selected]);
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't attach those resources");
    } finally {
      setBusy(false);
    }
  }

  return (
    <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Add from your library</DialogTitle>
          <DialogDescription>
            Anything you added to another chat can be reused here without processing it again.
          </DialogDescription>
        </DialogHeader>

        <div className="flex items-center gap-2 rounded-lg border border-input px-2.5">
          <IconSearch size={15} className="text-muted-foreground" />
          <input
            aria-label="Search your library"
            placeholder="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-9 flex-1 bg-transparent text-sm outline-none focus-visible:outline-none"
          />
        </div>

        <ul className="-mx-1 flex max-h-80 flex-col gap-1 overflow-y-auto px-1">
          {documents === null ? (
            [0, 1, 2].map((i) => <Skeleton key={i} className="h-11 w-full" />)
          ) : visible.length === 0 ? (
            <li className="py-6 text-center text-sm text-muted-foreground">
              {documents.length === 0 ? "Your library is empty." : "No matches."}
            </li>
          ) : (
            visible.map((document) => {
              const attached = attachedIds.has(document.id);
              const checked = attached || selected.has(document.id);
              return (
                <li key={document.id}>
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={checked}
                    disabled={attached}
                    onClick={() => toggle(document.id)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left text-sm transition-colors",
                      checked ? "bg-primary-soft" : "hover:bg-muted",
                      attached && "opacity-60",
                    )}
                  >
                    <span
                      aria-hidden
                      className={cn(
                        "flex size-4 shrink-0 items-center justify-center rounded border",
                        checked ? "border-primary bg-primary text-primary-foreground" : "border-input",
                      )}
                    >
                      {checked && <IconCheck size={11} stroke={3} />}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{document.filename}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {attached ? "In this chat" : document.docType.toLowerCase()}
                    </span>
                  </button>
                </li>
              );
            })
          )}
        </ul>

        {error && (
          <p role="alert" className="text-xs text-destructive">
            {error}
          </p>
        )}

        <DialogFooter>
          <Button onClick={attach} loading={busy} disabled={selected.size === 0}>
            Add {selected.size > 0 ? selected.size : ""} to chat
          </Button>
        </DialogFooter>
    </DialogContent>
  );
}
