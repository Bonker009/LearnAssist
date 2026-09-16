"use client";

import { ArrowLeft, Send } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import * as React from "react";
import { AppShell } from "@/components/app-shell";
import { AnswerWithCitations } from "@/components/citation";
import { QuizPanel } from "@/components/quiz-panel";
import { SourceViewer, type SourceViewerHandle } from "@/components/source-viewer";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { ChatMessage, LectureDocument, SourceRef } from "@/lib/types";

export default function DocumentPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [document, setDocument] = React.useState<LectureDocument | null>(null);
  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [question, setQuestion] = React.useState("");
  const [asking, setAsking] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const viewerRef = React.useRef<SourceViewerHandle>(null);

  React.useEffect(() => {
    void (async () => {
      try {
        const [doc, history] = await Promise.all([
          api.getDocument(id),
          api.getMessages(id),
        ]);
        setDocument(doc);
        setMessages(history);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load this lecture");
      }
    })();
  }, [id]);

  const navigate = React.useCallback((source: SourceRef) => {
    viewerRef.current?.goTo(source);
  }, []);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || asking) return;

    setError(null);
    setAsking(true);
    setQuestion("");

    // Show the student's own turn immediately; waiting for a slow local model
    // before echoing their question makes the app feel broken.
    const optimistic: ChatMessage = {
      id: `pending-${Date.now()}`,
      role: "USER",
      content: text,
      citations: [],
      createdAt: new Date().toISOString(),
    };
    setMessages((previous) => [...previous, optimistic]);

    try {
      const answer = await api.ask(id, text);
      setMessages((previous) => [...previous, answer]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not get an answer");
    } finally {
      setAsking(false);
    }
  }

  if (error && !document) {
    return (
      <AppShell>
        <p role="alert" className="rounded-md bg-danger-bg px-4 py-3 text-danger">
          {error}
        </p>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-5">
        <Link
          href="/"
          className="inline-flex w-fit items-center gap-1.5 text-sm text-text-muted hover:text-text"
        >
          <ArrowLeft aria-hidden className="size-4" />
          All lectures
        </Link>

        <h1 className="truncate text-xl font-semibold tracking-tight">
          {document?.filename ?? <Skeleton className="h-6 w-64" />}
        </h1>

        <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
          {/* Source viewer — the target of every citation chip. */}
          <div className="lg:sticky lg:top-20 lg:h-[calc(100dvh-7rem)]">
            {document ? (
              <SourceViewer ref={viewerRef} document={document} />
            ) : (
              <Skeleton className="h-96 w-full" />
            )}
          </div>

          <div className="flex flex-col gap-5">
            {document?.summary && (
              <Card>
                <CardHeader>
                  <CardTitle>Summary</CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-4">
                  <p className="text-sm leading-relaxed text-text-muted">
                    {document.summary.summary}
                  </p>
                  {document.summary.keyConcepts.length > 0 && (
                    <div>
                      <h3 className="mb-2 text-sm font-medium">Key concepts</h3>
                      <dl className="flex flex-col gap-2">
                        {document.summary.keyConcepts.map((concept) => (
                          <div key={concept.term}>
                            <dt className="text-sm font-medium">{concept.term}</dt>
                            <dd className="text-sm text-text-muted">
                              {concept.explanation}
                            </dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            <QuizPanel documentId={id} onNavigate={navigate} />

            <Card className="flex min-h-96 flex-col">
              <CardHeader>
                <CardTitle>Ask about this lecture</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-1 flex-col gap-4">
                <div
                  className="flex flex-1 flex-col gap-4 overflow-y-auto"
                  aria-live="polite"
                  aria-busy={asking}
                >
                  {messages.length === 0 && !asking && (
                    <p className="my-auto text-center text-sm text-text-subtle">
                      Ask a question and the answer will cite the exact slide, page or
                      moment it came from.
                    </p>
                  )}

                  {messages.map((message) =>
                    message.role === "USER" ? (
                      <div key={message.id} className="self-end max-w-[85%]">
                        <p className="rounded-[var(--radius-md)] bg-primary-soft px-3 py-2 text-sm text-primary-text">
                          {message.content}
                        </p>
                      </div>
                    ) : (
                      <div key={message.id} className="max-w-[95%]">
                        <AnswerWithCitations
                          content={message.content}
                          citations={message.citations}
                          onNavigate={navigate}
                        />
                      </div>
                    ),
                  )}

                  {asking && (
                    <div className="flex flex-col gap-2">
                      <Skeleton className="h-4 w-4/5" />
                      <Skeleton className="h-4 w-3/5" />
                    </div>
                  )}
                </div>

                {error && (
                  <p role="alert" className="text-sm text-danger">
                    {error}
                  </p>
                )}

                <form onSubmit={ask} className="flex gap-2">
                  <input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="e.g. What does RuBisCO do?"
                    aria-label="Your question"
                    className="h-[var(--control-height)] flex-1 rounded-[var(--control-radius)] border border-border bg-surface px-3 text-base placeholder:text-text-subtle"
                  />
                  <Button type="submit" loading={asking} aria-label="Send question">
                    <Send className="size-4" />
                  </Button>
                </form>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
