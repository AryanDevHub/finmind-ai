import clsx from "clsx";
import { motion } from "framer-motion";
import { AlertCircle, ArrowRight, PlusCircle, ShieldAlert, ShieldCheck } from "lucide-react";
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
    <GlassCard variants={item} className={clsx("p-5", className)} spotlight={false}>
      <div className="mb-4 flex items-center justify-between gap-3"><h3 className="label">{title}</h3>{aside}</div>
      {children}
    </GlassCard>
  );
}

/** Executive telemetry: 4 animated KPIs, three interactive charts and the latest transactions. */
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
      now, totals,
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
      <GlassCard spotlight={false} className="grid place-items-center gap-3 py-16 text-center">
        <AlertCircle className="h-8 w-8 text-danger" />
        <p className="font-semibold">Couldn't load your data</p>
        <button className="btn-ghost" onClick={() => void refetch()}>Retry</button>
      </GlassCard>
    );
  }
  if (isPending) {
    return (
      <div className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-[132px] rounded-2xl" />)}</div>
        <div className="grid gap-4 lg:grid-cols-2"><Skeleton className="h-[320px] rounded-2xl" /><Skeleton className="h-[320px] rounded-2xl" /></div>
      </div>
    );
  }
  if (txs.length === 0) {
    return (
      <div className="space-y-6">
        <motion.div variants={item}>
          <BankConnectCard
            connections={bankConns}
            isLoading={bankLoading}
            onRefresh={() => void refetchBank()}
          />
        </motion.div>

        <GlassCard spotlight={false} className="grid place-items-center gap-4 overflow-hidden px-6 py-14 text-center">
          <div aria-hidden className="absolute -top-24 left-1/2 h-64 w-64 -translate-x-1/2 animate-glow rounded-full blur-3xl" style={{ background: "radial-gradient(circle,#22D3EE,transparent 70%)" }} />
          <ShieldCheck className="relative h-10 w-10 text-signal animate-float" />
          <h2 className="relative text-xl font-bold">Your command center is empty</h2>
          <p className="relative max-w-sm text-sm text-ink-2">Connect your bank account above to automatically sync statements, or add a transaction manually.</p>
          <button className="btn-primary relative" onClick={onAdd}><PlusCircle className="h-4 w-4" /> Add a manual transaction</button>
        </GlassCard>
      </div>
    );
  }

  const { totals, rate, fraud } = d;
  const threat = THREAT_STYLE[fraud.threat];
  const rateColor = rate >= 20 ? "#34D399" : rate >= 0 ? "#FBBF24" : "#F43F5E";

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Monthly inflow" value={totals.inflow} format={formatINR} color="#34D399"
          delta={{ pct: pctChange(totals.inflow, totals.prevInflow), good: "up" }} hint="this month" footer={<Sparkline data={d.inSpark} color="#34D399" />} />
        <MetricCard label="Monthly outflow" value={totals.outflow} format={formatINR} color="#22D3EE"
          delta={{ pct: pctChange(totals.outflow, totals.prevOutflow), good: "down" }} hint="this month" footer={<Sparkline data={d.outSpark} color="#22D3EE" />} />
        <MetricCard label="Net savings rate" value={rate} format={(n) => `${n.toFixed(1)}%`} color={rateColor}
          hint={totals.inflow > 0 ? <span className="num">{formatINR(totals.inflow - totals.outflow)} {totals.inflow >= totals.outflow ? "saved" : "overspent"}</span> : "no income yet"}
          visual={<ProgressRing value={rate} color={rateColor} label="Savings rate" />} />
        <MetricCard label="Active fraud flags" value={fraud.flaggedCount} format={(n) => String(Math.round(n))} color={threat.hex} pulse={fraud.threat !== "clear"}
          hint={<span className="num">{fraud.recentFlagged} in last 7d · {formatINR(fraud.amountAtRisk)} at risk</span>}
          visual={
            <span className="relative grid h-14 w-14 place-items-center rounded-2xl" style={{ background: `${threat.hex}1f`, color: threat.hex, boxShadow: `0 0 28px -6px ${threat.hex}` }} aria-label={`Threat level: ${threat.label}`}>
              {fraud.threat !== "clear" && <span className="absolute inset-0 animate-ping rounded-2xl opacity-30" style={{ background: threat.hex }} />}
              {fraud.threat === "clear" ? <ShieldCheck className="relative h-6 w-6" /> : <ShieldAlert className="relative h-6 w-6" />}
            </span>
          } />
      </div>

      <motion.div variants={item}>
        <BankConnectCard
          connections={bankConns}
          isLoading={bankLoading}
          onRefresh={() => void refetchBank()}
        />
      </motion.div>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_1fr]">
        <Section title={scope === "month" && d.monthHasSpend ? "Spending by category · this month" : "Spending by category · all time"}
          aside={
            <div className="flex rounded-lg border border-white/10 p-0.5 text-[11px] font-semibold">
              {(["month", "all"] as const).map((s) => (
                <button key={s} onClick={() => setScope(s)} className={clsx("rounded-md px-2.5 py-1 transition-colors", scope === s ? "bg-white/10 text-ink-1" : "text-ink-3 hover:text-ink-1")}>{s === "month" ? "Month" : "All"}</button>
              ))}
            </div>
          }>
          {d.slices.length ? <CategoryDonut data={d.slices} /> : <p className="py-16 text-center text-sm text-ink-3">No expenses yet.</p>}
        </Section>
        <Section title="Inflow vs outflow · 6 months"><FlowBars data={d.flow} /></Section>
      </div>

      <Section title={`Cumulative net savings · last 45 days · ${formatMonthYear(d.now)}`}><SavingsArea data={d.net} /></Section>

      <motion.section variants={item}>
        <div className="mb-2 flex items-center justify-between px-1">
          <h3 className="label">Recent transactions</h3>
          <button onClick={() => goTo("transactions")} className="inline-flex items-center gap-1 text-xs font-semibold text-signal hover:underline">View all <ArrowRight className="h-3.5 w-3.5" /></button>
        </div>
        <TransactionLedger transactions={txs} preview={5} onDelete={(id) => del.mutate(id)} />
      </motion.section>
    </motion.div>
  );
}
