import { describe, expect, it } from "vitest";

import { elapsedFraction, pacing, projectedSpend, utilizationColor } from "@/lib/budget";
import { formatCompactINR, formatINR, formatWhen } from "@/lib/format";
import { categoryBreakdown, cumulativeNet, flowByMonth, monthTotals, pctChange, savingsRate, sparkline } from "@/lib/metrics";
import { computeFraudMetrics, gaugeColor, lerpColor } from "@/lib/risk";
import { tx } from "./factories";

const NOW = new Date(2026, 9, 15, 12, 0, 0); // 15 Oct 2026, local time
const at = (y: number, m: number, d: number) => new Date(y, m - 1, d, 10).toISOString();

describe("format", () => {
  it("uses Indian digit grouping and a real minus sign", () => {
    expect(formatINR(123456)).toBe("₹1,23,456");
    expect(formatINR(-500)).toBe("−₹500");
    expect(formatINR(1234.5, { decimals: true })).toBe("₹1,234.50");
    expect(formatINR(10, { signed: true })).toBe("+₹10");
  });
  it("compacts to K / L / Cr", () => {
    expect(formatCompactINR(950)).toBe("₹950");
    expect(formatCompactINR(12_500)).toBe("₹12.5K");
    expect(formatCompactINR(150_000)).toBe("₹1.5L");
    expect(formatCompactINR(25_000_000)).toBe("₹2.5Cr");
    expect(formatCompactINR(-3000)).toBe("−₹3K");
  });
  it("labels today and yesterday", () => {
    expect(formatWhen(new Date(2026, 9, 15, 9, 5).toISOString(), NOW)).toMatch(/^Today · /);
    expect(formatWhen(new Date(2026, 9, 14, 23, 0).toISOString(), NOW)).toMatch(/^Yesterday · /);
  });
});

describe("metrics", () => {
  const data = [
    tx({ transaction_type: "income", category: "Salary", amount: 50_000, occurred_at: at(2026, 10, 1) }),
    tx({ amount: 10_000, occurred_at: at(2026, 10, 5) }),
    tx({ amount: 5_000, category: "Shopping", occurred_at: at(2026, 10, 9) }),
    tx({ transaction_type: "income", category: "Salary", amount: 40_000, occurred_at: at(2026, 9, 1) }),
    tx({ amount: 20_000, occurred_at: at(2026, 9, 12) }),
  ];
  it("splits this month from last month", () => {
    expect(monthTotals(data, NOW)).toEqual({ inflow: 50_000, outflow: 15_000, prevInflow: 40_000, prevOutflow: 20_000 });
  });
  it("percentage change is null without a baseline", () => {
    expect(pctChange(120, 100)).toBe(20);
    expect(pctChange(50, 0)).toBeNull();
  });
  it("savings rate can go negative and is 0 with no income", () => {
    expect(savingsRate(50_000, 15_000)).toBe(70);
    expect(savingsRate(1000, 1500)).toBe(-50);
    expect(savingsRate(0, 500)).toBe(0);
  });
  it("breaks spending down by category, largest first, shares summing to 100", () => {
    const m = categoryBreakdown(data, "month", NOW);
    expect(m.map((s) => s.category)).toEqual(["Food", "Shopping"]);
    expect(m.reduce((a, s) => a + s.pct, 0)).toBeCloseTo(100);
    expect(categoryBreakdown(data, "all", NOW)[0]).toMatchObject({ category: "Food", amount: 30_000 });
  });
  it("zero-fills six months oldest-first", () => {
    const f = flowByMonth(data, 6, NOW);
    expect(f).toHaveLength(6);
    expect(f[5]).toMatchObject({ key: "2026-10", inflow: 50_000, outflow: 15_000 });
    expect(f[4]).toMatchObject({ key: "2026-09", inflow: 40_000, outflow: 20_000 });
    expect(f[0]).toMatchObject({ inflow: 0, outflow: 0 });
  });
  it("cumulative net carries the pre-window balance and ends at the true total", () => {
    const series = cumulativeNet(data, 20, NOW);
    expect(series).toHaveLength(20);
    expect(series[series.length - 1]!.value).toBe(50_000 + 40_000 - 10_000 - 5_000 - 20_000);
  });
  it("sparkline is a running total", () => {
    const s = sparkline(data, "expense", 14, NOW);
    expect(s).toHaveLength(14);
    expect(s[s.length - 1]).toBe(15_000);
    expect([...s].sort((a, b) => a - b)).toEqual(s);
  });
});

describe("budget pacing", () => {
  it("computes the elapsed fraction of a month", () => {
    expect(elapsedFraction("2026-10", new Date(2026, 9, 16, 12))).toBeCloseTo(0.5, 1);
    expect(elapsedFraction("2026-09", NOW)).toBe(1);
    expect(elapsedFraction("2026-11", NOW)).toBe(0);
  });
  it("classifies pace by spent% / elapsed%", () => {
    expect(pacing(75, 0.5, false).state).toBe("overpacing");      // 75% spent, 50% of month gone
    expect(pacing(50, 0.5, false).state).toBe("on_track");
    expect(pacing(20, 0.5, false).state).toBe("under_pace");
    expect(pacing(120, 0.9, true).state).toBe("over_budget");
    expect(pacing(90, 0.01, false).state).toBe("on_track");        // too early in the month to judge
  });
  it("only projects once the month is old enough", () => {
    expect(projectedSpend(500, 0.05)).toBeNull();
    expect(projectedSpend(500, 0.5)).toBe(1000);
  });
  it("colours run emerald → amber → crimson", () => {
    expect(utilizationColor(0)).toBe("#34d399");
    expect(utilizationColor(70)).toBe("#fbbf24");
    expect(utilizationColor(100)).toBe("#f43f5e");
    expect(utilizationColor(250)).toBe("#f43f5e");
  });
});

describe("risk", () => {
  it("interpolates colours", () => {
    expect(lerpColor("#000000", "#ffffff", 0.5)).toBe("#808080");
    expect(gaugeColor(0)).toBe("#34d399");
    expect(gaugeColor(100)).toBe("#f43f5e");
  });
  it("derives the threat level from RECENT flagged activity only", () => {
    const old = tx({ is_flagged: true, risk_level: "CRITICAL", occurred_at: at(2026, 9, 1) });
    const recentHigh = tx({ is_flagged: true, risk_level: "HIGH", occurred_at: at(2026, 10, 14) });
    const recentCrit = tx({ is_flagged: true, risk_level: "CRITICAL", amount: 900, occurred_at: at(2026, 10, 14) });
    expect(computeFraudMetrics([old], NOW).threat).toBe("clear");
    expect(computeFraudMetrics([old, recentHigh], NOW).threat).toBe("moderate");
    const m = computeFraudMetrics([old, recentHigh, recentCrit], NOW);
    expect(m).toMatchObject({ threat: "high", flaggedCount: 3, criticalCount: 2, recentFlagged: 2, recentCritical: 1 });
    expect(m.amountAtRisk).toBe(450 + 450 + 900);
  });
});
