"use client";

import { GraduationCap, LogOut } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useAuth } from "./auth-provider";
import { ThemeToggle } from "./theme-toggle";
import { Button } from "./ui/button";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, ready, signOut } = useAuth();
  const router = useRouter();

  React.useEffect(() => {
    if (ready && !user) router.replace("/sign-in");
  }, [ready, user, router]);

  if (!ready || !user) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <p className="text-sm text-text-muted">Loading…</p>
      </div>
    );
  }

  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-surface focus:px-4 focus:py-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-surface/80 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-5xl items-center gap-3 px-4">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <GraduationCap aria-hidden className="size-5 text-primary" />
            LearnAssist
          </Link>
          <div className="ml-auto flex items-center gap-2">
            <span className="hidden text-sm text-text-muted sm:inline">
              {user.displayName}
            </span>
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={signOut} aria-label="Sign out">
              <LogOut className="size-4" />
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-5xl px-4 py-8">
        {children}
      </main>
    </div>
  );
}
