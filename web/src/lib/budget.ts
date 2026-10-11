/** Budget velocity maths: how fast is the money going relative to how much of the month has passed? */
import { lerpColor } from "./risk";

/** Fraction (0..1] of `month` ('YYYY-MM') that has elapsed at `now`. Past months are 1, future months 0. */
export function elapsedFraction(month: string, now: Date = new Date()): number {
  const y = Number(month.slice(0, 4));
  const m = Number(month.slice(5, 7)) - 1;
  const start = new Date(y, m, 1).getTime();
  const end = new Date(y, m + 1, 1).getTime();
  if (now.getTime() >= end) return 1;
  if (now.getTime() <= start) return 0;
  return (now.getTime() - start) / (end - start);
}

export type PaceState = "over_budget" | "overpacing" | "on_track" | "under_pace";

export interface Pace { state: PaceState; label: string; ratio: number }

/**
 * ratio = (% of budget spent) / (% of month elapsed).  >1.15 spending faster than the calendar,
 * <0.85 slower. Tiny elapsed fractions (first ~3% of the month) are too noisy to judge, so they read as on-track.
 */
export function pacing(percentUsed: number, elapsed: number, overBudget: boolean): Pace {
  if (overBudget) return { state: "over_budget", label: "OVER BUDGET", ratio: Infinity };
  if (elapsed < 0.03) return { state: "on_track", label: "ON TRACK", ratio: 1 };
  const ratio = percentUsed / 100 / elapsed;
  if (ratio > 1.15) return { state: "overpacing", label: "OVERPACING", ratio };
  if (ratio < 0.85) return { state: "under_pace", label: "UNDER PACE", ratio };
  return { state: "on_track", label: "ON TRACK", ratio };
}

/** Straight-line projection of month-end spend; null while the month is too young to extrapolate. */
export const projectedSpend = (spent: number, elapsed: number): number | null => (elapsed >= 0.1 ? spent / elapsed : null);

/** Emerald (safe) → amber (70%) → crimson (100%+). */
export function utilizationColor(percentUsed: number): string {
  const p = Math.max(0, percentUsed);
  return p < 70 ? lerpColor("#34D399", "#FBBF24", p / 70) : lerpColor("#FBBF24", "#F43F5E", Math.min(1, (p - 70) / 30));
}
