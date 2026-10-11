/** Pure aggregation helpers behind the dashboard. No React, so they are trivially unit-testable. */
import { formatDay } from "./format";
import type { Category, Transaction } from "@/types";

const monthKey = (d: Date): string => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
const sum = (xs: readonly number[]): number => xs.reduce((a, b) => a + b, 0);

export interface MonthTotals { inflow: number; outflow: number; prevInflow: number; prevOutflow: number }

export function monthTotals(txs: readonly Transaction[], now: Date = new Date()): MonthTotals {
  const cur = monthKey(now);
  const prev = monthKey(new Date(now.getFullYear(), now.getMonth() - 1, 1));
  const by = (key: string, type: Transaction["transaction_type"]) =>
    sum(txs.filter((t) => t.transaction_type === type && monthKey(new Date(t.occurred_at)) === key).map((t) => t.amount));
  return { inflow: by(cur, "income"), outflow: by(cur, "expense"), prevInflow: by(prev, "income"), prevOutflow: by(prev, "expense") };
}

/** Percentage change vs a previous value; null when there is nothing to compare against. */
export const pctChange = (cur: number, prev: number): number | null => (prev > 0 ? ((cur - prev) / prev) * 100 : null);

/** (inflow − outflow) / inflow × 100. Can be negative (overspending); 0 when there was no income. */
export const savingsRate = (inflow: number, outflow: number): number => (inflow > 0 ? ((inflow - outflow) / inflow) * 100 : 0);

export interface CategorySlice { category: Category; amount: number; pct: number }

export function categoryBreakdown(txs: readonly Transaction[], scope: "month" | "all", now: Date = new Date()): CategorySlice[] {
  const cur = monthKey(now);
  const totals = new Map<Category, number>();
  for (const t of txs) {
    if (t.transaction_type !== "expense") continue;
    if (scope === "month" && monthKey(new Date(t.occurred_at)) !== cur) continue;
    totals.set(t.category, (totals.get(t.category) ?? 0) + t.amount);
  }
  const total = sum([...totals.values()]);
  return [...totals.entries()]
    .map(([category, amount]) => ({ category, amount, pct: total ? (amount / total) * 100 : 0 }))
    .sort((a, b) => b.amount - a.amount);
}

export interface MonthFlow { key: string; month: string; inflow: number; outflow: number }

/** Last `months` calendar months (oldest first), zero-filled so the axis never has gaps. */
export function flowByMonth(txs: readonly Transaction[], months = 6, now: Date = new Date()): MonthFlow[] {
  const out: MonthFlow[] = [];
  for (let i = months - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    const key = monthKey(d);
    const inMonth = txs.filter((t) => monthKey(new Date(t.occurred_at)) === key);
    out.push({
      key,
      month: d.toLocaleString("en-IN", { month: "short" }),
      inflow: sum(inMonth.filter((t) => t.transaction_type === "income").map((t) => t.amount)),
      outflow: sum(inMonth.filter((t) => t.transaction_type === "expense").map((t) => t.amount)),
    });
  }
  return out;
}

export interface SeriesPoint { date: string; value: number }

/** Cumulative net (income − expense) per day over the last `days`, starting from the balance before the window. */
export function cumulativeNet(txs: readonly Transaction[], days = 45, now: Date = new Date()): SeriesPoint[] {
  const dayStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const startMs = dayStart(now) - (days - 1) * 86_400_000;
  const signed = (t: Transaction) => (t.transaction_type === "income" ? t.amount : -t.amount);
  let running = sum(txs.filter((t) => dayStart(new Date(t.occurred_at)) < startMs).map(signed));
  const perDay = new Map<number, number>();
  for (const t of txs) {
    const k = dayStart(new Date(t.occurred_at));
    if (k >= startMs) perDay.set(k, (perDay.get(k) ?? 0) + signed(t));
  }
  const out: SeriesPoint[] = [];
  for (let i = 0; i < days; i++) {
    const k = startMs + i * 86_400_000;
    running += perDay.get(k) ?? 0;
    out.push({ date: formatDay(new Date(k)), value: running });
  }
  return out;
}

/** Cumulative amount per day for the last `days` (sparkline). */
export function sparkline(txs: readonly Transaction[], type: Transaction["transaction_type"], days = 14, now: Date = new Date()): number[] {
  const dayStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const startMs = dayStart(now) - (days - 1) * 86_400_000;
  const buckets = new Array<number>(days).fill(0);
  for (const t of txs) {
    if (t.transaction_type !== type) continue;
    const idx = Math.round((dayStart(new Date(t.occurred_at)) - startMs) / 86_400_000);
    if (idx >= 0 && idx < days) buckets[idx] = (buckets[idx] ?? 0) + t.amount;
  }
  let run = 0;
  return buckets.map((v) => (run += v));
}
