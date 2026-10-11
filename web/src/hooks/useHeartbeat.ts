import { useEffect, useState } from "react";

import { API_BASE } from "@/lib/api";

export interface Heartbeat { status: "checking" | "up" | "down"; latencyMs: number | null }

/** Pings the unauthenticated /health endpoint on an interval and reports round-trip latency. */
export function useHeartbeat(intervalMs = 10_000): Heartbeat {
  const [hb, setHb] = useState<Heartbeat>({ status: "checking", latencyMs: null });
  useEffect(() => {
    let alive = true;
    const ping = async () => {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 4_000);
      const t0 = performance.now();
      try {
        const res = await fetch(`${API_BASE}/health`, { cache: "no-store", signal: ctrl.signal });
        if (alive) setHb(res.ok ? { status: "up", latencyMs: Math.round(performance.now() - t0) } : { status: "down", latencyMs: null });
      } catch {
        if (alive) setHb({ status: "down", latencyMs: null });
      } finally {
        clearTimeout(timer);
      }
    };
    void ping();
    const id = setInterval(() => void ping(), intervalMs);
    return () => { alive = false; clearInterval(id); };
  }, [intervalMs]);
  return hb;
}
