"use client";

import { Check, RefreshCw, X } from "lucide-react";
import * as React from "react";
import { api } from "@/lib/api";
import type { Grade, Quiz, SourceRef } from "@/lib/types";
import { Citation } from "./citation";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";
import { Skeleton } from "./ui/skeleton";

type Phase = "idle" | "loading" | "taking" | "graded";

export function QuizPanel({
  documentId,
  onNavigate,
}: {
  documentId: string;
  onNavigate?: (source: SourceRef) => void;
}) {
  const [phase, setPhase] = React.useState<Phase>("idle");
  const [quiz, setQuiz] = React.useState<Quiz | null>(null);
  const [answers, setAnswers] = React.useState<Record<string, number>>({});
  const [grade, setGrade] = React.useState<Grade | null>(null);
  const [error, setError] = React.useState<string | null>(null);

  async function generate() {
    setError(null);
    setPhase("loading");
    setGrade(null);
    setAnswers({});
    try {
      setQuiz(await api.generateQuiz(documentId, 5));
      setPhase("taking");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate a quiz");
      setPhase("idle");
    }
  }

  async function submit() {
    if (!quiz) return;
    setError(null);
    try {
      setGrade(await api.submitQuiz(quiz.id, answers));
      setPhase("graded");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit your answers");
    }
  }

  const answeredAll =
    quiz != null && quiz.questions.every((q) => answers[String(q.position)] !== undefined);

  const gradeByPosition = new Map(grade?.questions.map((g) => [g.position, g]) ?? []);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle>Practice quiz</CardTitle>
        {phase !== "loading" && (
          <Button variant="outline" size="sm" onClick={generate}>
            <RefreshCw aria-hidden className="size-3.5" />
            {phase === "idle" ? "Generate" : "New quiz"}
          </Button>
        )}
      </CardHeader>

      <CardContent className="flex flex-col gap-5">
        {error && (
          <p role="alert" className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        {phase === "idle" && !error && (
          <p className="text-sm text-text-muted">
            Generate five multiple-choice questions drawn from across this lecture. Each
            answer shows the slide, page or moment it came from.
          </p>
        )}

        {phase === "loading" && (
          <div className="flex flex-col gap-3" aria-live="polite" aria-busy>
            <p className="text-sm text-text-muted">Writing questions from the lecture…</p>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        )}

        {quiz && (phase === "taking" || phase === "graded") && (
          <ol className="flex flex-col gap-6">
            {quiz.questions.map((question, index) => {
              const key = String(question.position);
              const graded = gradeByPosition.get(question.position);

              return (
                <li key={question.id} className="flex flex-col gap-3">
                  <div className="flex items-start gap-2">
                    <span className="text-sm font-medium text-text-subtle">{index + 1}.</span>
                    <p className="font-medium">{question.question}</p>
                  </div>

                  <fieldset className="flex flex-col gap-2 pl-6" disabled={phase === "graded"}>
                    <legend className="sr-only">{question.question}</legend>
                    {question.options.map((option, optionIndex) => {
                      const chosen = answers[key] === optionIndex;
                      const isCorrect = graded?.correctIndex === optionIndex;
                      const isWrongChoice = graded != null && chosen && !graded.correct;

                      return (
                        <label
                          key={optionIndex}
                          className={[
                            "flex cursor-pointer items-center gap-2 rounded-[var(--radius-md)]",
                            "border px-3 py-2 text-sm",
                            graded
                              ? isCorrect
                                ? "border-success bg-success-bg"
                                : isWrongChoice
                                  ? "border-danger bg-danger-bg"
                                  : "border-border"
                              : chosen
                                ? "border-primary bg-primary-soft"
                                : "border-border hover:bg-surface-muted",
                          ].join(" ")}
                        >
                          <input
                            type="radio"
                            name={`question-${question.id}`}
                            value={optionIndex}
                            checked={chosen}
                            onChange={() =>
                              setAnswers((prev) => ({ ...prev, [key]: optionIndex }))
                            }
                            className="accent-[var(--color-primary)]"
                          />
                          <span className="flex-1">{option}</span>
                          {graded && isCorrect && (
                            <Check aria-label="Correct answer" className="size-4 text-success" />
                          )}
                          {graded && isWrongChoice && (
                            <X
                              aria-label="Your answer, incorrect"
                              className="size-4 text-danger"
                            />
                          )}
                        </label>
                      );
                    })}
                  </fieldset>

                  {/* Before grading, show only where to look; afterwards, show why. */}
                  <div className="pl-6">
                    {graded ? (
                      <div className="flex flex-col gap-2 rounded-[var(--radius-md)] bg-surface-muted px-3 py-2">
                        <p className="text-sm text-text-muted">{graded.explanation}</p>
                        <Citation
                          citation={{
                            marker: graded.position,
                            source: graded.source,
                            label: graded.sourceLabel,
                            snippet: graded.snippet,
                          }}
                          onNavigate={onNavigate}
                          className="self-start"
                        />
                      </div>
                    ) : (
                      <p className="text-xs text-text-subtle">From {question.sourceLabel}</p>
                    )}
                  </div>
                </li>
              );
            })}
          </ol>
        )}

        {phase === "taking" && quiz && (
          <Button onClick={submit} disabled={!answeredAll} className="self-start">
            {answeredAll ? "Check answers" : `Answer all ${quiz.questions.length} questions`}
          </Button>
        )}

        {phase === "graded" && grade && (
          <p
            aria-live="polite"
            className="rounded-[var(--radius-md)] bg-primary-soft px-4 py-3 font-medium text-primary-text"
          >
            You scored {grade.score} out of {grade.total}.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
