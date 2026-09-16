"use client";

import { useRouter } from "next/navigation";
import * as React from "react";
import { api, getToken, setToken } from "@/lib/api";
import type { AuthUser } from "@/lib/types";

interface AuthState {
  user: AuthUser | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string, displayName: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = React.createContext<AuthState | null>(null);
const USER_KEY = "learnassist.user";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<AuthUser | null>(null);
  const [ready, setReady] = React.useState(false);
  const router = useRouter();

  React.useEffect(() => {
    try {
      const stored = window.localStorage.getItem(USER_KEY);
      if (stored && getToken()) setUser(JSON.parse(stored));
    } catch {
      /* unreadable storage: stay signed out */
    }
    setReady(true);
  }, []);

  const persist = React.useCallback((token: string, nextUser: AuthUser) => {
    setToken(token);
    try {
      window.localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    } catch {
      /* non-fatal */
    }
    setUser(nextUser);
  }, []);

  const value: AuthState = {
    user,
    ready,
    signIn: async (email, password) => {
      const result = await api.login(email, password);
      persist(result.token, result.user);
    },
    signUp: async (email, password, displayName) => {
      const result = await api.register(email, password, displayName);
      persist(result.token, result.user);
    },
    signOut: () => {
      setToken(null);
      try {
        window.localStorage.removeItem(USER_KEY);
      } catch {
        /* non-fatal */
      }
      setUser(null);
      router.push("/sign-in");
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
