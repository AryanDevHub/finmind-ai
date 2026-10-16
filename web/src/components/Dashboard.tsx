import clsx from "clsx";
import { motion } from "framer-motion";
import { AlertCircle, ArrowRight, Building2, PlusCircle, ShieldAlert, ShieldCheck } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import type { Route } from "@/hooks/useHashRoute";
import { formatINR, formatMonthYear } from "@/lib/format";
import { cumulativeNet, categoryBreakdown, flowByMonth, monthTotals, pctChange, savingsRate, sparkline } from "@/lib/metrics";
import { container, item } from "@/lib/motion";
import { useDeleteTransaction, useTransactions } from "@/lib/queries";
import { computeFraudMetrics, THREAT_STYLE } from "@/lib/risk";
import { CategoryDonut } from "./charts/CategoryDonut";
import { FlowBars } from "./charts/FlowBars";
import { SavingsArea } from "./charts/SavingsArea";
import { MetricCard } from "./MetricCard";
import { ProgressRing } from "./ProgressRing";
import { Sparkline } from "./Sparkline";
import { TransactionLedger } from "./TransactionLedger";
import { BankConnectCard } from "./BankConnectCard";
import { useBankConnections } from "@/lib/bankSync";
import { GlassCard } from "./ui/GlassCard";
import { Skeleton } from "./ui/Skeleton";

function Section({ title, aside, children, className }: { title: string; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <GlassCard variants={item} className={clsx("p-5", className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h3 className="label">{title}</h3>
        {aside}
      </div>
      {children}
    </GlassCard>
  );
}

/** Executive Financial Telemetry Dashboard */
export function Dashboard({ onAdd, goTo }: { onAdd: () => void; goTo: (r: Route) => void }) {
  const { data: txs = [], isPending, isError, refetch } = useTransactions();
  const { data: bankConns, isLoading: bankLoading, refetch: refetchBank } = useBankConnections();
  const del = useDeleteTransaction();
  const [scope, setScope] = useState<"month" | "all">("month");

  const d = useMemo(() => {
    const now = new Date();
    const totals = monthTotals(txs, now);
    const month = categoryBreakdown(txs, "month", now);
    return {
      now,
      totals,
      rate: savingsRate(totals.inflow, totals.outflow),
      fraud: computeFraudMetrics(txs, now),
      slices: scope === "month" && month.length ? month : categoryBreakdown(txs, "all", now),
      monthHasSpend: month.length > 0,
      flow: flowByMonth(txs, 6, now),
      net: cumulativeNet(txs, 45, now),
      inSpark: sparkline(txs, "income", 14, now),
      outSpark: sparkline(txs, "expense", 14, now),
    };
  }, [txs, scope]);

  if (isError) {
    return (
      <GlassCard className="grid place-items-center gap-3 py-16 text-center">
        <AlertCircle className="h-8 w-8 text-danger" />
        <p className="font-semibold text-ink-1">Could not connect to database</p>
        <button className="btn-secondary" onClick={() => void refetch()}>
          Retry Connection
        </button>
      </GlassCard>
    );
  }

  if (isPending) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-[120px] rounded-xl" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-[300px] rounded-xl" />
          <Skeleton className="h-[300px] rounded-xl" />
        </div>
      </div>
    );
  }

  if (txs.length === 0) {
    return (
      <div className="space-y-5">
        <motion.div variants={item}>
          <BankConnectCard
            connections={bankConns}
            isLoading={bankLoading}
            onRefresh={() => void refetchBank()}
          />
        </motion.div>

        <GlassCard className="grid place-items-center gap-4 px-6 py-14 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl border border-border bg-surface">
            <Building2 className="h-6 w-6 text-brand" />
          </div>
          <div className="max-w-md space-y-1">
            <h2 className="text-lg font-bold tracking-tight text-ink-1">No transactions recorded yet</h2>
            <p className="text-xs leading-relaxed text-ink-3">
              Connect your bank account via the RBI Account Aggregator protocol above, or record a transaction manually.
            </p>
          </div>
          <button className="btn-primary" onClick={onAdd}>
            <PlusCircle className="h-3.5 w-3.5" />
            <span>Add Manual Transaction</span>
          </button>
        </GlassCard>
      </div>
    );
  }

  const { totals, rate, fraud } = d;
  const threat = THREAT_STYLE[fraud.threat];
  const rateColor = rate >= 20 ? "#10B981" : rate >= 0 ? "#F59E0B" : "#EF4444";

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-4">
      {/* 4 Executive KPI Tiles */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Monthly Inflow"
          value={totals.inflow}
          format={formatINR}
          color="#10B981"
          delta={{ pct: pctChange(totals.inflow, totals.prevInflow), good: "up" }}
          hint="this calendar month"
          footer={<Sparkline data={d.inSpark} color="#10B981" />}
        />
        <MetricCard
          label="Monthly Outflow"
          value={totals.outflow}
          format={formatINR}
          color="#38BDF8"
          delta={{ pct: pctChange(totals.outflow, totals.prevOutflow), good: "down" }}
          hint="this calendar month"
          footer={<Sparkline data={d.outSpark} color="#38BDF8" />}
        />
        <MetricCard
          label="Net Savings Rate"
          value={rate}
          format={(n) => `${n.toFixed(1)}%`}
          color={rateColor}
          hint={
            totals.inflow > 0 ? (
              <span className="num">
                {formatINR(totals.inflow - totals.outflow)} {totals.inflow >= totals.outflow ? "saved" : "overspent"}
              </span>
            ) : (
              "no income recorded"
            )
          }
          visual={<ProgressRing value={rate} color={rateColor} label="Savings rate" />}
        />
        <MetricCard
          label="ML Fraud Alerts"
          value={fraud.flaggedCount}
          format={(n) => String(Math.round(n))}
          color={threat.hex}
          pulse={fraud.threat !== "clear"}
          hint={
            <span className="num">
              {fraud.recentFlagged} flagged · {formatINR(fraud.amountAtRisk)} at risk
            </span>
          }
          visual={
            <span
              className="flex h-11 w-11 items-center justify-center rounded-xl border border-border"
              style={{ background: `${threat.hex}14`, color: threat.hex }}
              aria-label={`Threat level: ${threat.label}`}
            >
              {fraud.threat === "clear" ? <ShieldCheck className="h-5 w-5" /> : <ShieldAlert className="h-5 w-5" />}
            </span>
          }
        />
      </div>

      {/* Bank Account Connection Status */}
      <motion.div variants={item}>
        <BankConnectCard
          connections={bankConns}
          isLoading={bankLoading}
          onRefresh={() => void refetchBank()}
        />
      </motion.div>

      {/* Breakdown and Flow Analytics */}
      <div className="grid gap-4 xl:grid-cols-[1.05fr_1fr]">
        <Section
          title={scope === "month" && d.monthHasSpend ? "Expense Breakdown · This Month" : "Expense Breakdown · All Time"}
          aside={
            <div className="flex rounded-md border border-border bg-surface p-0.5 text-[11px] font-semibold">
              {(["month", "all"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setScope(s)}
                  className={clsx(
                    "rounded px-2.5 py-0.5 transition-colors",
                    scope === s ? "bg-[#1E2942] text-ink-1" : "text-ink-3 hover:text-ink-1"
                  )}
                >
                  {s === "month" ? "Month" : "All Time"}
                </button>
              ))}
            </div>
          }
        >
          {d.slices.length ? <CategoryDonut data={d.slices} /> : <p className="py-14 text-center text-xs text-ink-3">No expenses recorded yet.</p>}
        </Section>

        <Section title="Income vs Outflow Trend · 6 Months">
          <FlowBars data={d.flow} />
        </Section>
      </div>

      {/* Cumulative Net Savings Area Chart */}
      <Section title={`Cumulative Net Savings · Last 45 Days (${formatMonthYear(d.now)})`}>
        <SavingsArea data={d.net} />
      </Section>

      {/* Recent Ledger */}
      <motion.section variants={item}>
        <div className="mb-2.5 flex items-center justify-between px-1">
          <h3 className="label">Recent Activity</h3>
          <button
            onClick={() => goTo("transactions")}
            className="inline-flex items-center gap-1 text-xs font-semibold text-brand hover:text-brand-hover transition-colors"
          >
            <span>Full Ledger</span>
            <ArrowRight className="h-3 w-3" />
          </button>
        </div>
        <TransactionLedger transactions={txs} preview={5} onDelete={(id) => del.mutate(id)} />
      </motion.section>
    </motion.div>
  );
}
