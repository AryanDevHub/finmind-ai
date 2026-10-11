/**
 * api.ts — typed fetch client for the FinMind API.
 *
 *  • The 15-minute access token lives in memory only (never localStorage: XSS can't read what isn't there).
 *  • The rotating refresh token is an HttpOnly, SameSite=Strict cookie the browser manages; JS never sees it.
 *  • On a 401 we refresh ONCE (single-flight, and serialised across browser tabs with the Web Locks API so two
 *    tabs can't race the same rotating token and trip the server's replay detection), then retry the request.
 *  • If refresh fails the session is dropped and `onSessionExpired` listeners fire.
 */
import type { User } from "@/types";

export const API_BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? "/api").replace(/\/$/, "");
const BASE = API_BASE;

let accessToken: string | null = null;
const expiredListeners = new Set<() => void>();

export const session = {
  get token(): string | null { return accessToken; },
  set(token: string): void { accessToken = token; },
  clear(): void { accessToken = null; },
};

export function onSessionExpired(fn: () => void): () => void {
  expiredListeners.add(fn);
  return () => void expiredListeners.delete(fn);
}

export class ApiError extends Error {
  constructor(public readonly status: number, public readonly detail: string) {
    super(detail);
    this.name = "ApiError";
  }
}

/** FastAPI returns `detail` as a string, or a list of validation errors. */
export function formatDetail(body: unknown, status: number): string {
  if (body && typeof body === "object" && "detail" in body) {
    const d = (body as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((e: { loc?: unknown[]; msg?: string }) => {
          const where = (e.loc ?? []).slice(1).join(".");
          return where ? `${where}: ${e.msg ?? "invalid"}` : (e.msg ?? "invalid");
        })
        .join("; ");
    }
  }
  return `Request failed (${status})`;
}

// ───────────────────────────── refresh ─────────────────────────────
let inflight: Promise<boolean> | null = null;

async function doRefresh(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" });
    if (!res.ok) return false;
    const body = (await res.json()) as { access_token: string };
    accessToken = body.access_token;
    return true;
  } catch {
    return false;
  }
}

export function refreshSession(): Promise<boolean> {
  if (!inflight) {
    const run = async (): Promise<boolean> =>
      typeof navigator !== "undefined" && "locks" in navigator
        ? await navigator.locks.request("finmind-refresh", doRefresh) // serialises refreshes across tabs
        : await doRefresh();
    inflight = run().finally(() => { inflight = null; });
  }
  return inflight;
}

// ───────────────────────────── core request ─────────────────────────────
export interface RequestOptions {
  method?: "GET" | "POST" | "DELETE";
  json?: unknown;
  form?: Record<string, string>;
  signal?: AbortSignal;
  /** Attach the bearer token and auto-refresh on 401 (default true). */
  auth?: boolean;
  timeoutMs?: number;
}

async function send(path: string, o: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = { Accept: "application/json" };
  let body: BodyInit | undefined;
  if (o.json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(o.json); }
  if (o.form) { headers["Content-Type"] = "application/x-www-form-urlencoded"; body = new URLSearchParams(o.form); }
  if (o.auth !== false && accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), o.timeoutMs ?? 20_000);
  o.signal?.addEventListener("abort", () => ctrl.abort(), { once: true });
  try {
    return await fetch(`${BASE}${path}`, { method: o.method ?? "GET", headers, body, credentials: "include", signal: ctrl.signal });
  } catch (e) {
    if (o.signal?.aborted) throw e; // caller cancelled: let react-query see the AbortError
    throw new ApiError(0, ctrl.signal.aborted ? "The server took too long to respond." : "Can't reach the server. Is the API running?");
  } finally {
    clearTimeout(timer);
  }
}

export async function api<T = void>(path: string, o: RequestOptions = {}): Promise<T> {
  let res = await send(path, o);
  if (res.status === 401 && o.auth !== false && !path.startsWith("/auth/")) {
    if (await refreshSession()) {
      res = await send(path, o);
    } else {
      session.clear();
      expiredListeners.forEach((fn) => fn());
      throw new ApiError(401, "Your session expired. Please log in again.");
    }
  }
  if (res.status === 204) return undefined as T;
  let payload: unknown = null;
  try { payload = await res.json(); } catch { /* empty or non-JSON body */ }
  if (!res.ok) throw new ApiError(res.status, formatDetail(payload, res.status));
  return payload as T;
}

// ───────────────────────────── auth endpoints ─────────────────────────────
export const authApi = {
  async login(username: string, password: string): Promise<User> {
    const t = await api<{ access_token: string }>("/auth/login", { method: "POST", form: { username, password }, auth: false });
    session.set(t.access_token);
    return api<User>("/auth/me");
  },
  async register(username: string, email: string, password: string): Promise<void> {
    await api("/auth/register", { method: "POST", json: { username, email, password }, auth: false });
  },
  /** Revokes the access token and the whole refresh-token family server-side. */
  async logout(): Promise<void> {
    try { await api("/auth/logout", { method: "POST", timeoutMs: 8_000 }); } finally { session.clear(); }
  },
  /** On page load: trade the refresh cookie for a fresh access token, if there is a valid session. */
  async restore(): Promise<User | null> {
    if (!(await refreshSession())) return null;
    try { return await api<User>("/auth/me"); } catch { return null; }
  },
};
