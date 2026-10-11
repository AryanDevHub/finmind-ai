import type { FraudMetrics, RiskLevel, ThreatLevel, Transaction } from "@/types";

export const RISK_STYLE: Record<RiskLevel, { hex: string; text: string; bg: string; ring: string; label: string }> = {
  LOW: { hex: "#34D399", text: "text-gain", bg: "bg-gain/10", ring: "border-gain/25", label: "Low" },
  MEDIUM: { hex: "#FBBF24", text: "text-warn", bg: "bg-warn/10", ring: "border-warn/25", label: "Medium" },
  HIGH: { hex: "#FB923C", text: "text-orange-400", bg: "bg-orange-400/10", ring: "border-orange-400/25", label: "High" },
  CRITICAL: { hex: "#F43F5E", text: "text-danger", bg: "bg-danger/10", ring: "border-danger/30", label: "Critical" },
};

export const THREAT_STYLE: Record<ThreatLevel, { hex: string; label: string; text: string; description: string }> = {
  clear: { hex: "#34D399", label: "Clear", text: "text-gain", description: "No flagged activity in the last 7 days" },
  moderate: { hex: "#FBBF24", label: "Moderate", text: "text-warn", description: "Flagged activity in the last 7 days" },
  high: { hex: "#F43F5E", label: "High threat", text: "text-danger", description: "Critical-risk activity in the last 7 days" },
};

// ───────────────────────────── colour maths ─────────────────────────────
const hexToRgb = (h: string): [number, number, number] => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
const toHex = (n: number): string => Math.round(Math.max(0, Math.min(255, n))).toString(16).padStart(2, "0");

/** Linear interpolation between two #RRGGBB colours. */
export function lerpColor(a: string, b: string, t: number): string {
  const [r1, g1, b1] = hexToRgb(a);
  const [r2, g2, b2] = hexToRgb(b);
  const k = Math.max(0, Math.min(1, t));
  return `#${toHex(r1 + (r2 - r1) * k)}${toHex(g1 + (g2 - g1) * k)}${toHex(b1 + (b2 - b1) * k)}`;
}

/** Emerald → amber → crimson as a 0..100 risk value rises. */
export function gaugeColor(value: number): string {
  const v = Math.max(0, Math.min(100, value));
  return v < 40 ? lerpColor("#34D399", "#FBBF24", v / 40) : lerpColor("#FBBF24", "#F43F5E", (v - 40) / 60);
}

// ───────────────────────────── fraud aggregates ─────────────────────────────
const DAY = 86_400_000;

/**
 * Threat level is about RECENT activity: any critical-risk transaction in the last 7 days is "high",
 * any other flagged one is "moderate", otherwise "clear". Old alerts don't keep the bar red forever.
 */
export function computeFraudMetrics(txs: readonly Transaction[], now: Date = new Date()): FraudMetrics {
  const flagged = txs.filter((t) => t.is_flagged);
  const expenses = txs.filter((t) => t.transaction_type === "expense");
  const recent = (t: Transaction) => now.getTime() - new Date(t.occurred_at).getTime() <= 7 * DAY;
  const recentFlagged = flagged.filter(recent);
  const recentCritical = recentFlagged.filter((t) => t.risk_level === "CRITICAL");
  return {
    flaggedCount: flagged.length,
    criticalCount: flagged.filter((t) => t.risk_level === "CRITICAL").length,
    amountAtRisk: flagged.reduce((s, t) => s + t.amount, 0),
    avgScore: expenses.length ? expenses.reduce((s, t) => s + t.fraud_score, 0) / expenses.length : 0,
    recentFlagged: recentFlagged.length,
    recentCritical: recentCritical.length,
    threat: recentCritical.length ? "high" : recentFlagged.length ? "moderate" : "clear",
  };
}
