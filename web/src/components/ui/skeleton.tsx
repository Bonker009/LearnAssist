import { cn } from "@/lib/utils";

/** Content-shaped loading placeholder: a muted block with a soft pulse. */
export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn("animate-pulse rounded-md bg-surface-muted", className)}
    />
  );
}
