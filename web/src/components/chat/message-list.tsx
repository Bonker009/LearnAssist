"use client";

import { IconSparkles } from "@tabler/icons-react";
import * as React from "react";
import { AiOrb } from "@/components/ai-orb";
import { AnswerWithCitations, type NavigateHandler } from "@/components/citation";
import { ShimmeringText } from "@/components/ui/shimmering-text";
import type { ChatMessage } from "@/lib/types";
import { hasKhmer } from "@/lib/utils";


export function MessageList({
  messages,
  thinking,
  documentNames,
  onNavigate,
}: {
  messages: ChatMessage[];
  thinking: boolean;
  documentNames: Map<string, string>;
  onNavigate: NavigateHandler;
}) {
  const end = React.useRef<HTMLDivElement>(null);
  // Answer the wait in the language the student just used.
  const lastQuestion = [...messages].reverse().find((m) => m.role === "USER");
  const khmerTurn = lastQuestion ? hasKhmer(lastQuestion.content) : false;

  React.useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, thinking]);

  return (
    <div
      className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-6"
      aria-live="polite"
      aria-busy={thinking}
    >
      {messages.map((message) =>
        message.role === "USER" ? (
          <div key={message.id} className="flex justify-end">
            <p
              lang={hasKhmer(message.content) ? "km" : undefined}
              className="max-w-[85%] rounded-xl bg-primary-soft px-4 py-2.5 whitespace-pre-wrap text-text"
            >
              {message.content}
            </p>
          </div>
        ) : (
          <div key={message.id} className="flex gap-3">
            <span
              aria-hidden
              className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground"
            >
              <IconSparkles size={15} stroke={1.75} />
            </span>
            <div
              className="min-w-0 flex-1 pt-0.5"
              lang={hasKhmer(message.content) ? "km" : undefined}
            >
              <span className="sr-only">Assistant:</span>
              <AnswerWithCitations
                content={message.content}
                citations={message.citations}
                onNavigate={onNavigate}
                documentNames={documentNames}
              />
            </div>
          </div>
        ),
      )}

      {thinking && (
        <div className="flex items-center gap-3" role="status">
          <AiOrb state="thinking" className="-ml-1.5 size-10" />
          <ShimmeringText
            text={khmerTurn ? "កំពុងអានឯកសាររបស់អ្នក…" : "Reading your materials…"}
            className="text-sm font-medium"
            duration={1.8}
          />
        </div>
      )}
      <div ref={end} />
    </div>
  );
}
