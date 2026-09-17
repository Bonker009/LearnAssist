"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
  hint?: string;
}

/**
 * Text input with its label, hint and error wired together.
 *
 * The label is required rather than optional: an unlabelled control is the single
 * most common accessibility failure in a form, and making it a type error is more
 * reliable than an audit that catches it later.
 */
export function Input({ label, error, hint, className, id, ...props }: InputProps) {
  const generated = React.useId();
  const inputId = id ?? generated;
  const hintId = `${inputId}-hint`;
  const errorId = `${inputId}-error`;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-text">
        {label}
      </label>
      <input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={cn(hint && hintId, error && errorId) || undefined}
        className={cn(
          "h-[var(--control-height)] rounded-[var(--control-radius)] border px-3",
          "bg-surface text-text placeholder:text-text-subtle",
          "outline-none transition-[border-color,box-shadow] duration-150 ease-out",
          "focus-visible:border-focus focus-visible:ring-3 focus-visible:ring-focus/40",
          // Invalid: border and ring both carry the danger tint, and the message
          // below says what is wrong, so colour is never the only signal.
          error
            ? "border-danger ring-3 ring-danger/20 focus-visible:border-danger focus-visible:ring-danger/30"
            : "border-border-strong",
          className,
        )}
        {...props}
      />
      {hint && !error && (
        <p id={hintId} className="text-xs text-text-subtle">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
