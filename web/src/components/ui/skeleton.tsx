import { cn } from "@/lib/utils";

/** Content-shaped loading placeholder. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "relative overflow-hidden rounded-[var(--radius-sm)] bg-surface-muted",
        "after:absolute after:inset-0 after:-translate-x-full",
        "after:bg-gradient-to-r after:from-transparent after:via-black/5 after:to-transparent",
        "after:animate-[shimmer_1.6s_infinite] dark:after:via-white/10",
        className,
      )}
    />
  );
}
