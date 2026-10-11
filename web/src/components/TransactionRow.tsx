import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { ChevronDown, ShieldAlert, Sparkles, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { CATEGORY_META } from "@/lib/categories";
import { formatINR, formatWhen } from "@/lib/format";
import { spring } from "@/lib/motion";
import type { Transaction } from "@/types";
import { FraudGauge } from "./FraudGauge";
import { ShapBars } from "./ShapBars";
import { RiskBadge } from "./ui/RiskBadge";

interface Props {
  tx: Transaction;
  onDelete: (id: string) => void;
  defaultOpen?: boolean;
}

/**
 * One ledger row. Expenses expand into an "ML Fraud Diagnostics" drawer: calibrated probability gauge,
 * diverging SHAP attribution bars, and a two-step delete (the second click must land within 3.5 s).
 */
export function TransactionRow({ tx, onDelete, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const [confirming, setConfirming] = useState(false);
  const { icon: Icon, color } = CATEGORY_META[tx.category];
  const expense = tx.transaction_type === "expense";

  useEffect(() => {
    if (!confirming) return;
    const id = setTimeout(() => setConfirming(false), 3500);
    return () => clearTimeout(id);
  }, [confirming]);

  const header = (
    <>
      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: `${color}1f`, boxShadow: `0 0 20px -6px ${color}aa`, color }}>
        <Icon className="h-[18px] w-[18px]" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold">{tx.description}</span>
        <span className="mt-0.5 block truncate text-xs text-ink-3">
          {tx.category}{tx.merchant ? ` · ${tx.merchant}` : ""} · {formatWhen(tx.occurred_at)}
        </span>
      </span>
      <span className="flex shrink-0 flex-col items-end gap-1">
        <span className={clsx("num text-sm font-semibold", expense ? "text-ink-1" : "text-gain")}>
          {expense ? "−" : "+"}{formatINR(tx.amount).replace("−", "")}
        </span>
        {expense && <RiskBadge level={tx.risk_level} />}
      </span>
      {expense && <ChevronDown className={clsx("ml-1 h-4 w-4 shrink-0 text-ink-3 transition-transform duration-300", open && "rotate-180")} />}
    </>
  );

  return (
    <motion.li
      initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 30 }} className="overflow-hidden"
    >
      <div className={clsx("glass my-1.5", tx.is_flagged && "!border-danger/30 shadow-[0_0_30px_-14px_rgba(244,63,94,0.6)]")}>
        {expense ? (
          <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-3.5 rounded-2xl p-3.5 text-left">
            {header}
          </button>
        ) : (
          <div className="flex w-full items-center gap-3.5 p-3.5">{header}</div>
        )}

        <AnimatePresence initial={false}>
          {open && expense && (
            <motion.div
              key="drawer" initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }}
              transition={{ type: "spring", stiffness: 240, damping: 30 }} className="overflow-hidden"
            >
              <div className="border-t border-white/[0.06] p-4 sm:p-5">
                <div className="mb-4 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.14em] text-signal">
                  <Sparkles className="h-3.5 w-3.5" /> ML Fraud Diagnostics
                </div>
                <div className="grid items-center gap-6 md:grid-cols-[220px_1fr]">
                  <div className="flex justify-center"><FraudGauge value={tx.fraud_score} level={tx.risk_level} size={210} /></div>
                  <div>
                    <p className="label mb-3">Why this score</p>
                    <ShapBars factors={tx.fraud_factors ?? []} />
                  </div>
                </div>
                <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-4">
                  <p className="flex items-center gap-2 text-xs text-ink-3">
                    {tx.is_anomaly && <span className="inline-flex items-center gap-1 rounded-full bg-warn/10 px-2 py-0.5 font-semibold text-warn"><ShieldAlert className="h-3 w-3" /> Unusual for you</span>}
                    <span className="num">{formatINR(tx.amount, { decimals: true })}</span>
                  </p>
                  <motion.button
                    type="button" whileTap={{ scale: 0.97 }} transition={spring}
                    onClick={() => (confirming ? onDelete(tx.id) : setConfirming(true))}
                    className={clsx("btn-danger relative overflow-hidden !py-2 text-[13px]", confirming && "!bg-danger !text-white")}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    {confirming ? "Click again to delete" : "Delete"}
                    {confirming && <motion.span className="absolute inset-x-0 bottom-0 h-0.5 origin-left bg-white/70" initial={{ scaleX: 1 }} animate={{ scaleX: 0 }} transition={{ duration: 3.5, ease: "linear" }} />}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </motion.li>
  );
}
