import clsx from "clsx";
import { motion } from "framer-motion";
import { Gauge, Loader2, PiggyBank } from "lucide-react";
import { useState } from "react";

import { ApiError } from "@/lib/api";
import { elapsedFraction, pacing, projectedSpend, utilizationColor, type PaceState } from "@/lib/budget";
import { CATEGORY_META } from "@/lib/categories";
import { formatINR, formatMonthYear } from "@/lib/format";
import { container, item, spring } from "@/lib/motion";
import { useBudgets, useSetBudget } from "@/lib/queries";
import { BUDGET_CATEGORIES, type Budget, type Category } from "@/types";
import { GlassCard } from "./ui/GlassCard";
import { Skeleton } from "./ui/Skeleton";
import { useToast } from "./ui/Toast";

const PACE_STYLE: Record<PaceState, string> = {
  over_budget: "border-danger/30 bg-danger/10 text-danger",
  overpacing: "border-orange-400/30 bg-orange-400/10 text-orange-400",
  on_track: "border-gain/30 bg-gain/10 text-gain",
  under_pace: "border-signal/30 bg-signal/10 text-signal",
};

/**
 * Dual-track bar: the upper track is money spent (colour shifts emerald → amber → crimson with utilisation),
 * the lower "shadow" track is how much of the month has elapsed. Spent racing ahead of the shadow = overpacing.
 */
function BudgetCard({ b, onEdit }: { b: Budget; onEdit: (b: Budget) => void }) {
  const elapsed = elapsedFraction(b.month);
  const pace = pacing(b.percent_used, elapsed, b.over_budget);
  const projected = projectedSpend(b.spent_amount, elapsed);
  const color = utilizationColor(b.percent_used);
  const { icon: Icon, color: catColor } = CATEGORY_META[b.category];
  const left = b.limit_amount - b.spent_amount;

  return (
    <GlassCard variants={item} className="p-5">
      <button type="button" onClick={() => onEdit(b)} className="absolute inset-0 z-10 rounded-2xl" aria-label={`Edit ${b.category} budget`} />
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-xl" style={{ background: `${catColor}1f`, color: catColor, boxShadow: `0 0 20px -6px ${catColor}aa` }}><Icon className="h-[18px] w-[18px]" /></span>
          <div>
            <p className="text-sm font-semibold">{b.category}</p>
            <p className="num text-xs text-ink-3">{formatINR(b.spent_amount)} of {formatINR(b.limit_amount)}</p>
          </div>
        </div>
        <span className={clsx("rounded-full border px-2.5 py-0.5 text-[10px] font-bold tracking-wider", PACE_STYLE[pace.state])}>{pace.label}</span>
      </div>

      <div className="mt-5" role="img" aria-label={`${Math.round(b.percent_used)}% of budget spent, ${Math.round(elapsed * 100)}% of the month elapsed`}>
        <div className="relative h-3 overflow-hidden rounded-full bg-white/[0.06]">
          <motion.div className="h-full rounded-full" style={{ background: `linear-gradient(90deg, ${color}aa, ${color})`, boxShadow: `0 0 14px ${color}88` }}
            initial={{ width: 0 }} animate={{ width: `${Math.min(100, b.percent_used)}%` }} transition={{ type: "spring", stiffness: 70, damping: 18, delay: 0.2 }} />
        </div>
        <div className="relative mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.04]">
          <motion.div className="h-full rounded-full bg-signal/40" initial={{ width: 0 }} animate={{ width: `${elapsed * 100}%` }} transition={{ type: "spring", stiffness: 60, damping: 20, delay: 0.35 }} />
        </div>
        <div className="num mt-1.5 flex justify-between text-[11px] text-ink-3">
          <span style={{ color }}>{b.percent_used.toFixed(0)}% spent</span>
          <span>{(elapsed * 100).toFixed(0)}% of month elapsed</span>
        </div>
      </div>

      <p className="mt-3 text-xs leading-relaxed text-ink-2">
        {b.over_budget
          ? <>Over by <span className="num font-semibold text-danger">{formatINR(-left)}</span>.</>
          : <><span className="num font-semibold text-ink-1">{formatINR(left)}</span> left{projected !== null && <> · on pace for <span className={clsx("num font-semibold", projected > b.limit_amount ? "text-orange-400" : "text-ink-1")}>{formatINR(projected)}</span> ({((projected / b.limit_amount) * 100).toFixed(0)}% of limit)</>}.</>}
      </p>
    </GlassCard>
  );
}

export function BudgetView() {
  const { data: budgets = [], isPending } = useBudgets();
  const set = useSetBudget();
  const toast = useToast();
  const [category, setCategory] = useState<Category>("Food");
  const [limit, setLimit] = useState("");

  const valid = Number(limit) > 0;
  const save = (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    set.mutate({ category, limit_amount: Number(limit) }, {
      onSuccess: () => { toast.push({ tone: "success", title: "Budget saved", body: `${category}: ${formatINR(Number(limit))} / month` }); setLimit(""); },
    });
  };
  const err = set.error instanceof ApiError ? set.error.detail : null;

  return (
    <div className="space-y-4">
      <GlassCard spotlight={false} className="p-5">
        <form onSubmit={save} className="flex flex-wrap items-end gap-3">
          <div className="min-w-[160px] flex-1"><label htmlFor="b-cat" className="label">Category</label>
            <select id="b-cat" value={category} onChange={(e) => setCategory(e.target.value as Category)} className="field mt-1.5">
              {BUDGET_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select></div>
          <div className="min-w-[160px] flex-1"><label htmlFor="b-lim" className="label">Monthly limit (₹)</label>
            <input id="b-lim" inputMode="decimal" value={limit} onChange={(e) => setLimit(e.target.value.replace(/[^\d.]/g, ""))} placeholder="5000" className="field num mt-1.5" /></div>
          <motion.button type="submit" whileTap={{ scale: 0.98 }} transition={spring} disabled={!valid || set.isPending} className="btn-primary">
            {set.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <PiggyBank className="h-4 w-4" />} Set budget
          </motion.button>
        </form>
        {err && <p role="alert" className="mt-3 text-sm text-danger">{err}</p>}
        <p className="mt-3 flex items-center gap-1.5 text-xs text-ink-3"><Gauge className="h-3.5 w-3.5" /> {formatMonthYear(new Date())} · setting a budget for an existing category updates its limit. Click a card to edit it.</p>
      </GlassCard>

      {isPending ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[200px] rounded-2xl" />)}</div>
      ) : budgets.length === 0 ? (
        <GlassCard spotlight={false} className="grid place-items-center gap-2 py-16 text-center"><PiggyBank className="h-8 w-8 text-ink-4" /><p className="font-semibold">No budgets yet</p><p className="text-sm text-ink-3">Set a monthly limit above to track your spending velocity.</p></GlassCard>
      ) : (
        <motion.div variants={container} initial="hidden" animate="show" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {budgets.map((b) => <BudgetCard key={b.category} b={b} onEdit={(x) => { setCategory(x.category); setLimit(String(x.limit_amount)); window.scrollTo({ top: 0, behavior: "smooth" }); }} />)}
        </motion.div>
      )}
    </div>
  );
}
