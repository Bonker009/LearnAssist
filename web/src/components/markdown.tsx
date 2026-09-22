"use client";

import * as React from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/utils";

/**
 * Markdown for assistant answers, styled from the semantic tokens.
 *
 * Raw HTML in the model's output is never rendered (react-markdown escapes it unless
 * rehype-raw is added, and it must not be): the text comes from a model reading
 * student-supplied documents, so anything it echoes is untrusted.
 *
 * `renderCitation` turns the answer's `[n]` markers into citation chips. They are
 * rewritten to `#cite-n` links before parsing so the parser keeps them inline in
 * whatever paragraph, list item or table cell they sit in.
 */
export function Markdown({
  content,
  renderCitation,
  className,
}: {
  content: string;
  renderCitation?: (marker: number) => React.ReactNode;
  className?: string;
}) {
  const source = renderCitation ? content.replace(/\[(\d{1,3})\](?!\()/g, "[$1](#cite-$1)") : content;

  const components: Components = {
    p: ({ children }) => <p className="leading-relaxed">{children}</p>,
    ul: ({ children }) => <ul className="list-disc space-y-1.5 pl-5 marker:text-text-subtle">{children}</ul>,
    ol: ({ children }) => (
      <ol className="list-decimal space-y-1.5 pl-5 marker:text-text-muted marker:tabular-nums">
        {children}
      </ol>
    ),
    li: ({ children }) => <li className="pl-1 leading-relaxed">{children}</li>,
    h1: ({ children }) => <h3 className="text-base font-semibold">{children}</h3>,
    h2: ({ children }) => <h3 className="text-base font-semibold">{children}</h3>,
    h3: ({ children }) => <h4 className="text-[15px] font-semibold">{children}</h4>,
    h4: ({ children }) => <h4 className="text-[15px] font-semibold">{children}</h4>,
    strong: ({ children }) => <strong className="font-semibold text-text">{children}</strong>,
    blockquote: ({ children }) => (
      <blockquote className="border-l-2 border-border-strong pl-3 text-text-muted">{children}</blockquote>
    ),
    hr: () => <hr className="border-border" />,
    code: ({ className: language, children }) =>
      language ? (
        <code className={language}>{children}</code>
      ) : (
        <code className="rounded-sm bg-surface-muted px-1 py-0.5 font-mono text-[0.9em]">{children}</code>
      ),
    pre: ({ children }) => (
      <pre className="overflow-x-auto rounded-md bg-surface-muted p-3 font-mono text-[13px] leading-relaxed">
        {children}
      </pre>
    ),
    table: ({ children }) => (
      <div className="overflow-x-auto rounded-md border border-border">
        <table className="w-full border-collapse text-sm">{children}</table>
      </div>
    ),
    thead: ({ children }) => <thead className="bg-surface-muted text-left">{children}</thead>,
    th: ({ children }) => <th className="border-b border-border px-3 py-2 font-semibold">{children}</th>,
    td: ({ children }) => <td className="border-t border-border px-3 py-2 align-top">{children}</td>,
    a: ({ href, children }) => {
      const cite = href ? /^#cite-(\d{1,3})$/.exec(href) : null;
      if (cite && renderCitation) return <>{renderCitation(Number(cite[1]))}</>;
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary-text underline underline-offset-2 hover:no-underline"
        >
          {children}
        </a>
      );
    },
  };

  return (
    <div className={cn("flex flex-col gap-3 text-text", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {source}
      </ReactMarkdown>
    </div>
  );
}
