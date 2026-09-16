"use client";

import { GraduationCap } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function SignInPage() {
  const { user, ready, signIn, signUp } = useAuth();
  const router = useRouter();
  const [mode, setMode] = React.useState<"in" | "up">("in");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [displayName, setDisplayName] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (ready && user) router.replace("/");
  }, [ready, user, router]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (mode === "in") await signIn(email, password);
      else await signUp(email, password, displayName);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-dvh items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <GraduationCap aria-hidden className="size-8 text-primary" />
          <h1 className="text-2xl font-semibold tracking-tight">LearnAssist</h1>
          <p className="text-sm text-text-muted">
            Study from your lectures, with every answer showing its source.
          </p>
        </div>

        <Card>
          <CardContent className="pt-5">
            <form onSubmit={onSubmit} className="flex flex-col gap-4">
              {mode === "up" && (
                <Input
                  label="Your name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  autoComplete="name"
                  required
                />
              )}
              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
              <Input
                label="Password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "in" ? "current-password" : "new-password"}
                hint={mode === "up" ? "At least 8 characters" : undefined}
                minLength={8}
                required
              />

              {error && (
                <p role="alert" className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
                  {error}
                </p>
              )}

              <Button type="submit" loading={busy}>
                {mode === "in" ? "Sign in" : "Create account"}
              </Button>
            </form>

            <p className="mt-4 text-center text-sm text-text-muted">
              {mode === "in" ? "No account yet?" : "Already have an account?"}{" "}
              <button
                type="button"
                className="font-medium text-primary-text underline-offset-2 hover:underline"
                onClick={() => {
                  setMode(mode === "in" ? "up" : "in");
                  setError(null);
                }}
              >
                {mode === "in" ? "Create one" : "Sign in"}
              </button>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
