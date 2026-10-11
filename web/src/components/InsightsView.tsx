import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { CalendarClock, Loader2, RefreshCw, ShieldAlert, Sparkles } from "lucide-react";

import { CATEGORY_META } from "@/lib/categories";
import { formatINR, formatWhen } from "@/lib/format";
import { container, item } from "@/lib/motion";
import { useAnomalies, useForecast, useRefreshAnalytics } from "@/lib/queries";
import { ForecastChart } from "./charts/ForecastChart";
import { GlassCard } from "./ui/GlassCard";
import { Skeleton } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";

const Note = ({ children }: { children: ReactNode }) => <p className="rounded-xl border border-white/[0.07] bg-void/40 px-4 py-6 text-center text-sm text-ink-3">{children}</p>;

/** Anomalies and the 4-week outlook. Both are produced by background jobs: this screen only reads results. */
export function InsightsView() {
  const anomalies = useAnomalies();
  const forecast = useForecast();
  const refresh = useRefreshAnalytics();
  const toast = useToast();
  const a = anomalies.data;
  const f = forecast.data;

  return (
    <motion.div variants={container} initial="hidden" animate="show" className="space-y-4">
      <motion.div variants={item} className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-xl text-sm text-ink-2">Scored by nightly background jobs, never while you wait. Use “Recompute” after adding lots of new data.</p>
        <button className="btn-ghost" disabled={refresh.isPending}
          onClick={() => refresh.mutate(undefined, { onSuccess: () => toast.push({ tone: "info", title: "Recompute queued", body: "Results will appear in a few seconds." }), onError: () => toast.push({ tone: "warn", title: "Please wait a minute", body: "Recompute can run once per minute." }) })}>
          {refresh.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Recompute
        </button>
      </motion.div>

      <GlassCard variants={item} spotlight={false} className="p-5">
        <h3 className="label mb-4 flex items-center gap-2"><ShieldAlert className="h-3.5 w-3.5 text-warn" /> Unusual for you</h3>
        {anomalies.isPending ? <Skeleton className="h-24" /> : !a ? <Note>Couldn't load anomalies.</Note>
          : a.status === "insufficient_data" ? <Note>Add at least {a.min_required} expenses to enable anomaly detection (you have {a.expense_count}).</Note>
          : a.status === "pending" ? <Note>Your history hasn't been scored yet. Click “Recompute” or wait for tonight's run.</Note>
          : (
            <>
              <p className="mb-3 text-xs text-ink-3">{a.method === "isolation_forest" ? "Isolation Forest" : "Robust z-score (MAD)"} · {a.expense_count} expenses{a.scored_at ? ` · scored ${formatWhen(a.scored_at)}` : ""}</p>
              {a.anomalies.length === 0 ? <Note>Nothing unusual in your spending. 🎉</Note> : (
                <ul className="space-y-2">
                  {a.anomalies.map((x) => {
                    const { icon: Icon, color } = CATEGORY_META[x.category];
                    return (
                      <li key={x.id} className="flex items-center gap-3 rounded-xl border border-white/[0.07] bg-void/40 p-3">
                        <span className="grid h-9 w-9 place-items-center rounded-lg" style={{ background: `${color}1f`, color }}><Icon className="h-4 w-4" /></span>
                        <span className="min-w-0 flex-1"><span className="block truncate text-sm font-semibold">{x.description}</span><span className="block truncate text-xs text-ink-3">{x.reason} · {formatWhen(x.occurred_at)}</span></span>
                        <span className="num text-sm font-semibold text-orange-400">{formatINR(x.amount)}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          )}
      </GlassCard>

      <GlassCard variants={item} spotlight={false} className="p-5">
        <h3 className="label mb-4 flex items-center gap-2"><CalendarClock className="h-3.5 w-3.5 text-signal" /> Spending outlook · next 4 weeks</h3>
        {forecast.isPending ? <Skeleton className="h-64" />
          : !f || f.status === "pending" ? <Note><Loader2 className="mr-2 inline h-4 w-4 animate-spin" />Computing your forecast…</Note>
          : f.status === "insufficient_data" ? <Note>Forecasting needs at least {f.min_required_weeks} weeks of history (you have {f.history_weeks}).</Note>
          : (
            <>
              <div className="mb-4 grid gap-3 sm:grid-cols-3">
                {[["Expected next 4 weeks", formatINR(f.total_next_4_weeks)], ["History used", `${f.history_weeks} weeks`], ["Intervals", f.interval_method]].map(([k, v]) => (
                  <div key={k} className="rounded-xl border border-white/[0.07] bg-void/40 px-4 py-3"><p className="label">{k}</p><p className="num mt-1 text-lg font-semibold capitalize">{v}</p></div>
                ))}
              </div>
              <ForecastChart weeks={f.weekly} />
              <p className="mt-3 flex items-center gap-1.5 text-xs text-ink-4"><Sparkles className="h-3.5 w-3.5" /> {f.model} · shaded bands are 80% and 95% prediction intervals.</p>
            </>
          )}
      </GlassCard>
    </motion.div>
  );
}
