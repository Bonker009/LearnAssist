"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-primary text-text-inverse hover:bg-primary-hover disabled:bg-border-strong",
  secondary:
    "bg-surface text-text border border-border hover:bg-surface-muted",
  ghost: "bg-transparent text-text-muted hover:bg-surface-muted hover:text-text",
  danger: "bg-danger text-text-inverse hover:opacity-90",
};

const SIZES: Record<Size, string> = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-base gap-2",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export function Button({
  className,
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      // aria-busy rather than swapping in a spinner-only label: a screen reader
      // user should still hear what the button does while it is working.
      aria-busy={loading || undefined}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center rounded-[var(--control-radius)]",
        "font-medium transition-colors",
        "disabled:cursor-not-allowed disabled:opacity-60",
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {loading && (
        <span
          aria-hidden
          className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
        />
      )}
      {children}
    </button>
  );
}
