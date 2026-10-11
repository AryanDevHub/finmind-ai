import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { useToast } from "@/components/ui/Toast";
import type { User } from "@/types";
import { authApi, onSessionExpired } from "./api";

type AuthState = { status: "loading" } | { status: "anon" } | { status: "authed"; user: User };

interface AuthContextValue {
  state: AuthState;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const qc = useQueryClient();
  const toast = useToast();

  // Restore the session from the refresh cookie on first load; react to server-side expiry afterwards.
  useEffect(() => {
    let alive = true;
    void authApi.restore().then((u) => { if (alive) setState(u ? { status: "authed", user: u } : { status: "anon" }); });
    const off = onSessionExpired(() => {
      qc.clear();
      setState({ status: "anon" });
      toast.push({ tone: "warn", title: "Session expired", body: "Please log in again." });
    });
    return () => { alive = false; off(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const user = await authApi.login(username, password);
    setState({ status: "authed", user });
  }, []);
  const register = useCallback((u: string, e: string, p: string) => authApi.register(u, e, p), []);
  const logout = useCallback(async () => {
    try { await authApi.logout(); } finally { qc.clear(); setState({ status: "anon" }); }
  }, [qc]);

  const value = useMemo(() => ({ state, login, register, logout }), [state, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
