"use client";

/**
 * The chat composer.
 *
 * Built from two blocks.so shadcn blocks: `ai-04` (attachment badges, the + menu,
 * drag-and-drop overlay) and `ai-01` (the microphone control), wired to real
 * resources instead of demo state. Attachments here are not held in the browser
 * until send — each one is uploaded and starts ingesting the moment it is added,
 * because a lecture recording can take minutes to transcribe and the student should
 * not have to wait for that after pressing send.
 */

import {
  IconAlertTriangle,
  IconArrowUp,
  IconBooks,
  IconBrandYoutube,
  IconCheck,
  IconCirclePlus,
  IconFileText,
  IconLink,
  IconMicrophone,
  IconNote,
  IconPaperclip,
  IconPhoto,
  IconPlus,
  IconVideo,
  IconVolume,
  IconWorld,
  IconX,
} from "@tabler/icons-react";
import * as React from "react";
import { AiOrb } from "@/components/ai-orb";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Textarea } from "@/components/ui/textarea";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { ACCEPTED_TYPES } from "@/lib/api";
import type { DocType, LectureDocument } from "@/lib/types";
import { cn, hasKhmer } from "@/lib/utils";

export interface PendingUpload {
  id: string;
  name: string;
  progress: number;
  error?: string;
}

const DOC_ICONS: Record<DocType, typeof IconFileText> = {
  PDF: IconFileText,
  PPTX: IconFileText,
  DOCX: IconFileText,
  TEXT: IconNote,
  IMAGE: IconPhoto,
  AUDIO: IconVolume,
  VIDEO: IconVideo,
  WEB: IconWorld,
  YOUTUBE: IconBrandYoutube,
};

export interface ComposerProps {
  documents: LectureDocument[];
  uploads: PendingUpload[];
  sending: boolean;
  /** Large centred pill on the empty state, docked bar in a conversation. */
  variant: "hero" | "docked";
  onSend: (text: string) => void;
  onAttachFiles: (files: File[]) => void;
  onAddLink: (url: string) => Promise<void>;
  onAddNote: (title: string, text: string) => Promise<void>;
  onOpenLibrary: () => void;
  onOpenDocument: (id: string) => void;
  onRemoveDocument: (id: string) => void;
  onDismissUpload: (id: string) => void;
  /** Speech to text. The service detects the language, Khmer included. */
  onTranscribe: (clip: Blob) => Promise<string>;
  /** Receives the live microphone level, for the orb. */
  voiceLevelRef?: React.RefObject<number>;
  /** Receives 0..1 progress toward the automatic stop on silence, for the orb's ring. */
  voiceSilenceRef?: React.RefObject<number>;
  /** Told when voice input starts listening, starts transcribing, or goes idle. */
  onVoiceStateChange?: (state: "idle" | "listening" | "thinking") => void;
  /** Lets an orb outside the composer (the welcome screen's) finish listening. */
  handleRef?: React.Ref<ComposerHandle>;
}

export interface ComposerHandle {
  /** Stop listening now and transcribe what was said. */
  finishVoice: () => void;
}

export function Composer(props: ComposerProps) {
  const {
    documents,
    uploads,
    sending,
    variant,
    onSend,
    onAttachFiles,
    onOpenLibrary,
    onOpenDocument,
    onRemoveDocument,
    onDismissUpload,
    onTranscribe,
    voiceLevelRef,
    voiceSilenceRef,
    onVoiceStateChange,
    handleRef,
  } = props;

  const [prompt, setPrompt] = React.useState("");
  const [dragOver, setDragOver] = React.useState(false);
  const [linkOpen, setLinkOpen] = React.useState(false);
  const [noteOpen, setNoteOpen] = React.useState(false);
  const [transcribing, setTranscribing] = React.useState(false);
  const [voiceError, setVoiceError] = React.useState<string | null>(null);
  const fileInput = React.useRef<HTMLInputElement>(null);
  const textarea = React.useRef<HTMLTextAreaElement>(null);

  const recorder = useVoiceRecorder(async (clip) => {
    setTranscribing(true);
    setVoiceError(null);
    try {
      const text = (await onTranscribe(clip)).trim();
      if (!text) {
        setVoiceError("Didn't catch that. Try again a little closer to the mic.");
        return;
      }
      // Append rather than replace, so a student can dictate in several goes and
      // edit between them before sending.
      setPrompt((previous) => {
        if (!previous.trim()) return text;
        // Khmer has no spaces between words, so a Khmer continuation joins directly.
        const joiner = hasKhmer(text) ? "" : " ";
        return `${previous.trimEnd()}${joiner}${text}`;
      });
      requestAnimationFrame(() => textarea.current?.focus());
    } catch (err) {
      setVoiceError(err instanceof Error ? err.message : "Couldn't transcribe that recording");
    } finally {
      setTranscribing(false);
    }
  }, voiceLevelRef, { silenceRef: voiceSilenceRef });

  const recording = recorder.state === "recording";
  React.useImperativeHandle(handleRef, () => ({ finishVoice: recorder.stop }), [recorder.stop]);

  const voiceState = recording ? "listening" : transcribing ? "thinking" : "idle";
  React.useEffect(() => {
    onVoiceStateChange?.(voiceState);
  }, [voiceState, onVoiceStateChange]);
  const hasReady = documents.some((d) => d.status === "READY");
  const canSend = Boolean(prompt.trim()) && !sending && !recording && !transcribing;

  function submit() {
    if (!canSend) return;
    onSend(prompt.trim());
    setPrompt("");
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    // isComposing: Khmer and other IME input uses Enter to commit a candidate,
    // which must not also send the half-typed message.
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  function handleDrop(event: React.DragEvent) {
    event.preventDefault();
    setDragOver(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) onAttachFiles(files);
  }

  function handlePaste(event: React.ClipboardEvent<HTMLTextAreaElement>) {
    // Pasting a screenshot or file attaches it instead of doing nothing.
    const files = Array.from(event.clipboardData.files);
    if (files.length > 0) {
      event.preventDefault();
      onAttachFiles(files);
    }
  }

  const hint = !documents.length
    ? "Ask a question anytime — files, links, and notes are optional."
    : !hasReady
      ? "Files are still processing, but you can still ask a question in chat."
      : null;
  const error = voiceError ?? recorder.error;

  return (
    <div className="flex w-full flex-col gap-2">
      <form
        className={cn(
          "relative overflow-visible border bg-background p-2 transition-colors duration-200 focus-within:border-ring",
          "rounded-xl shadow-md",
          variant === "hero" && "p-3",
        )}
        onDragLeave={(e) => {
          e.preventDefault();
          setDragOver(false);
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDrop={handleDrop}
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        {!recording && !transcribing && (documents.length > 0 || uploads.length > 0) && (
          <ul
            aria-label="Resources in this chat"
            className="mb-2 flex max-h-24 flex-wrap items-center gap-1.5 overflow-y-auto"
          >
            {uploads.map((upload) => (
              <li key={upload.id}>
                <Badge
                  variant="outline"
                  className={cn(
                    "h-7 max-w-56 gap-1.5 pr-1 pl-2 text-[13px] font-normal",
                    upload.error && "border-destructive/40 text-destructive",
                  )}
                  title={upload.error ?? `Uploading ${upload.name}`}
                >
                  {upload.error ? (
                    <IconAlertTriangle size={13} />
                  ) : (
                    <span className="size-3 animate-spin rounded-full border-2 border-current border-t-transparent opacity-60" />
                  )}
                  <span className="truncate">{upload.name}</span>
                  <span className="text-muted-foreground tabular-nums">
                    {upload.error ? "failed" : `${upload.progress}%`}
                  </span>
                  {upload.error && (
                    <button
                      type="button"
                      aria-label={`Dismiss ${upload.name}`}
                      onClick={() => onDismissUpload(upload.id)}
                      className="rounded-sm p-0.5 hover:bg-accent"
                    >
                      <IconX size={12} />
                    </button>
                  )}
                </Badge>
              </li>
            ))}

            {documents.map((document) => (
              <li key={document.id}>
                <ResourceBadge
                  document={document}
                  onOpen={() => onOpenDocument(document.id)}
                  onRemove={() => onRemoveDocument(document.id)}
                />
              </li>
            ))}
          </ul>
        )}

        {recording || transcribing ? (
          <ListeningView
            recording={recording}
            tall={variant === "hero"}
            levelRef={recorder.levelRef}
            silenceRef={recorder.silenceRef}
            onCancel={recorder.cancel}
            onDone={recorder.stop}
          />
        ) : (
          <>
            <Textarea
              ref={textarea}
              lang={hasKhmer(prompt) ? "km" : undefined}
              className={cn(
                "max-h-52 resize-none rounded-none border-none bg-transparent! p-1 shadow-none focus-visible:border-transparent focus-visible:ring-0 dark:bg-transparent!",
                variant === "hero" ? "min-h-16 text-base" : "min-h-12 text-[15px]",
              )}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              onPaste={handlePaste}
              placeholder="Ask anything about your materials — សួរអ្វីក៏បាន"
              aria-label="Message"
              value={prompt}
            />

          <div className="flex items-center gap-1">
            <input
              ref={fileInput}
              className="sr-only"
              multiple
              type="file"
              accept={ACCEPTED_TYPES}
              tabIndex={-1}
              onChange={(e) => {
                const files = Array.from(e.target.files ?? []);
                if (files.length) onAttachFiles(files);
                e.target.value = "";
              }}
            />

            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button
                    aria-label="Add a resource"
                    className="rounded-md"
                    size="icon-sm"
                    type="button"
                    variant="ghost"
                    disabled={recording}
                  />
                }
              >
                <IconPlus size={18} />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-64 rounded-xl p-1.5">
                <DropdownMenuGroup className="space-y-0.5">
                  <MenuItem
                    icon={IconPaperclip}
                    label="Upload files"
                    hint="PDF, slides, Word, photos, audio, video"
                    onClick={() => fileInput.current?.click()}
                  />
                  <MenuItem
                    icon={IconLink}
                    label="Add a link"
                    hint="Web page or YouTube video"
                    onClick={() => setLinkOpen(true)}
                  />
                  <MenuItem
                    icon={IconNote}
                    label="Paste text or notes"
                    onClick={() => setNoteOpen(true)}
                  />
                  <MenuItem
                    icon={IconBooks}
                    label="From your library"
                    hint="Reuse something you added before"
                    onClick={onOpenLibrary}
                  />
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>

            <div className="ml-auto flex items-center gap-1">
              {recorder.supported && (
                <Button
                  aria-label="Dictate a message"
                  title="Dictate — Khmer or English, detected automatically"
                  className="rounded-md text-muted-foreground hover:text-foreground"
                  size="icon"
                  type="button"
                  variant="ghost"
                  loading={recorder.state === "requesting"}
                  onClick={() => {
                    setVoiceError(null);
                    recorder.clearError();
                    void recorder.start();
                  }}
                >
                  {recorder.state !== "requesting" && <IconMicrophone size={19} stroke={1.75} />}
                </Button>
              )}
              <Button
                aria-label="Send message"
                className="rounded-full transition-[scale,opacity] duration-150 ease-out active:scale-[0.96] disabled:opacity-40"
                disabled={!canSend}
                loading={sending}
                size="icon"
                type="submit"
              >
                {!sending && <IconArrowUp size={17} />}
              </Button>
            </div>
          </div>
          </>
        )}

        <div
          aria-hidden
          className={cn(
            "pointer-events-none absolute inset-0 z-20 flex items-center justify-center rounded-[inherit] border border-dashed border-primary bg-primary-soft text-sm text-primary-text transition-opacity duration-200",
            dragOver ? "opacity-100" : "opacity-0",
          )}
        >
          <span className="flex items-center gap-1.5 font-medium">
            <IconCirclePlus size={16} />
            Drop files to add them to this chat
          </span>
        </div>
      </form>

      {(error || hint) && (
        <p
          role={error ? "alert" : undefined}
          className={cn(
            "flex items-center gap-1.5 px-3 text-xs",
            error ? "text-destructive" : "text-muted-foreground",
          )}
        >
          {error && <IconAlertTriangle size={13} aria-hidden />}
          {error ?? hint}
        </p>
      )}

      <LinkDialog open={linkOpen} onOpenChange={setLinkOpen} onSubmit={props.onAddLink} />
      <NoteDialog open={noteOpen} onOpenChange={setNoteOpen} onSubmit={props.onAddNote} />
    </div>
  );
}

/**
 * Voice input in progress: only the orb. The recording ends by itself when the
 * student stops talking (the orb’s ring closes as the pause lengthens); tapping
 * the orb or pressing Enter finishes early, Esc cancels. The transcript is appended
 * to the message for the student to edit and send. On the welcome screen the whole
 * composer is hidden and the large orb above it does this instead.
 */
function ListeningView({
  recording,
  tall,
  levelRef,
  silenceRef,
  onCancel,
  onDone,
}: {
  recording: boolean;
  tall: boolean;
  levelRef: React.RefObject<number>;
  silenceRef: React.RefObject<number>;
  onCancel: () => void;
  onDone: () => void;
}) {
  React.useEffect(() => {
    if (!recording) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCancel();
      } else if (event.key === "Enter" && !event.isComposing) {
        event.preventDefault();
        onDone();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [recording, onCancel, onDone]);

  return (
    <div className={cn("flex items-center justify-center", tall ? "min-h-[100px]" : "min-h-[84px]")}>
      <span className="sr-only" role="status" aria-live="polite">
        {recording
          ? "Listening. Stops when you pause. Press Enter to finish or Escape to cancel."
          : "Transcribing"}
      </span>
      <AiOrb
        state={recording ? "listening" : "thinking"}
        levelRef={levelRef}
        silenceRef={silenceRef}
        onPress={recording ? onDone : undefined}
        pressLabel="Finish and transcribe"
        className="size-14"
      />
    </div>
  );
}

function MenuItem({
  icon: Icon,
  label,
  hint,
  onClick,
}: {
  icon: typeof IconPaperclip;
  label: string;
  hint?: string;
  onClick: () => void;
}) {
  return (
    <DropdownMenuItem className="items-start gap-2.5 rounded-md px-2.5 py-2" onClick={onClick}>
      <Icon className="mt-0.5 text-primary-text" size={18} stroke={1.75} />
      <span className="flex flex-col">
        <span>{label}</span>
        {hint && <span className="text-xs text-muted-foreground">{hint}</span>}
      </span>
    </DropdownMenuItem>
  );
}

function ResourceBadge({
  document,
  onOpen,
  onRemove,
}: {
  document: LectureDocument;
  onOpen: () => void;
  onRemove: () => void;
}) {
  const Icon = DOC_ICONS[document.docType] ?? IconFileText;
  const failed = document.status === "FAILED";
  const ready = document.status === "READY";
  const status = ready
    ? "ready"
    : failed
      ? (document.job?.error ?? "failed")
      : `processing, ${document.job?.progress ?? 0}%`;

  return (
    <Badge
      variant="outline"
      className={cn(
        "group h-7 max-w-60 gap-0 overflow-hidden p-0 text-[13px] font-normal transition-colors hover:bg-accent",
        failed && "border-destructive/40",
      )}
    >
      <button
        type="button"
        onClick={onOpen}
        title={`${document.filename} — ${status}`}
        className="flex h-full min-w-0 items-center gap-1.5 pr-1 pl-2"
      >
        <Icon size={14} className={cn("shrink-0 opacity-70", failed && "text-destructive")} />
        <span className="truncate">{document.filename}</span>
        {ready ? (
          <IconCheck size={12} className="shrink-0 text-success" aria-label="ready" />
        ) : failed ? (
          <IconAlertTriangle size={12} className="shrink-0 text-destructive" aria-label="failed" />
        ) : (
          <span className="shrink-0 text-muted-foreground tabular-nums">
            {document.job?.progress ?? 0}%
          </span>
        )}
      </button>
      <button
        type="button"
        aria-label={`Remove ${document.filename} from this chat`}
        onClick={onRemove}
        className="mr-1 rounded-sm p-0.5 text-muted-foreground opacity-60 hover:bg-background hover:opacity-100 focus-visible:opacity-100"
      >
        <IconX size={12} />
      </button>
    </Badge>
  );
}

function LinkDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (url: string) => Promise<void>;
}) {
  const [url, setUrl] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const isYoutube = /(^|\/\/|\.)(youtube\.com|youtu\.be)\//i.test(url);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(url.trim());
      setUrl("");
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add that link");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => onOpenChange(next)}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Add a link</DialogTitle>
            <DialogDescription>
              A web article is read and split into sections. A YouTube video is transcribed,
              and answers link to the exact moment.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <label htmlFor="resource-url" className="text-sm font-medium">
              URL
            </label>
            <div
              className={cn(
                "flex items-center gap-2 rounded-md border border-input px-2.5 transition-[border-color,box-shadow] duration-150 ease-out focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/40",
                error &&
                  "border-destructive ring-3 ring-destructive/20 focus-within:border-destructive focus-within:ring-destructive/30",
              )}
            >
              {isYoutube ? (
                <IconBrandYoutube size={16} className="text-destructive" />
              ) : (
                <IconWorld size={16} className="text-muted-foreground" />
              )}
              <input
                id="resource-url"
                type="url"
                inputMode="url"
                autoFocus
                required
                placeholder="https://…"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                aria-invalid={error ? true : undefined}
                className="h-9 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground focus-visible:outline-none"
              />
            </div>
            {error && (
              <p role="alert" className="flex items-center gap-1.5 text-xs text-destructive">
                <IconAlertTriangle size={13} aria-hidden />
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" loading={busy} disabled={!url.trim()}>
              Add {isYoutube ? "video" : "page"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function NoteDialog({
  open,
  onOpenChange,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (title: string, text: string) => Promise<void>;
}) {
  const [title, setTitle] = React.useState("");
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit(title, text);
      setTitle("");
      setText("");
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add those notes");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => onOpenChange(next)}>
      <DialogContent className="sm:max-w-xl">
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>Paste text or notes</DialogTitle>
            <DialogDescription>
              Markdown headings (# Heading) become sections that answers can cite.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-1.5">
            <label htmlFor="note-title" className="text-sm font-medium">
              Title
            </label>
            <input
              id="note-title"
              placeholder="Week 3 notes"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="h-9 rounded-md border border-input bg-transparent px-2.5 text-sm outline-none transition-[border-color,box-shadow] duration-150 ease-out focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/40"
            />
          </div>
          <div className="grid gap-1.5">
            <label htmlFor="note-text" className="text-sm font-medium">
              Text
            </label>
            <Textarea
              id="note-text"
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="max-h-[50dvh] min-h-48"
              placeholder="Paste lecture notes, an article, a transcript…"
            />
            {error && (
              <p role="alert" className="flex items-center gap-1.5 text-xs text-destructive">
                <IconAlertTriangle size={13} aria-hidden />
                {error}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" loading={busy} disabled={!text.trim()}>
              Add notes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
