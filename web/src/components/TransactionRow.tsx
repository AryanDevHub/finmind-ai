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
 * Precision Ledger Row
 * Clean row styling, expandable ML fraud diagnostic drawer with SHAP explainability.
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
      {/* Category Icon */}
      <span
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-border"
        style={{ background: `${color}14`, color }}
      >
        <Icon className="h-4 w-4" />
      </span>

      {/* Description & Metadata */}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-xs font-semibold text-ink-1">{tx.description}</span>
        <span className="mt-0.5 block truncate text-[11px] text-ink-3">
          {tx.category}{tx.merchant ? ` · ${tx.merchant}` : ""} · {formatWhen(tx.occurred_at)}
        </span>
      </span>

      {/* Financial Figure & Risk Pill */}
      <span className="flex shrink-0 flex-col items-end gap-1">
        <span className={clsx("num text-xs font-bold", expense ? "text-ink-1" : "text-emerald")}>
          {expense ? "−" : "+"}{formatINR(tx.amount).replace("−", "")}
        </span>
        {expense && <RiskBadge level={tx.risk_level} />}
      </span>

      {expense && (
        <ChevronDown
          className={clsx(
            "ml-1 h-3.5 w-3.5 shrink-0 text-ink-3 transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      )}
    </>
  );

  return (
    <motion.li
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: "auto" }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 30 }}
      className="overflow-hidden"
    >
      <div
        className={clsx(
          "glass my-1.5 overflow-hidden transition-all",
          tx.is_flagged && "!border-danger/40 bg-danger/[0.02]"
        )}
      >
        {expense ? (
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
            className="flex w-full items-center gap-3 p-3 text-left transition-colors hover:bg-surface/50"
          >
            {header}
          </button>
        ) : (
          <div className="flex w-full items-center gap-3 p-3">{header}</div>
        )}

        <AnimatePresence initial={false}>
          {open && expense && (
            <motion.div
              key="drawer"
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ type: "spring", stiffness: 240, damping: 30 }}
              className="overflow-hidden"
            >
              <div className="border-t border-border bg-surface/30 p-4 sm:p-5">
                <div className="mb-3.5 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-brand">
                  <Sparkles className="h-3 w-3" />
                  <span>ML Fraud Diagnostics</span>
                </div>

                <div className="grid items-center gap-6 md:grid-cols-[200px_1fr]">
                  <div className="flex justify-center">
                    <FraudGauge value={tx.fraud_score} level={tx.risk_level} size={190} />
                  </div>
                  <div>
                    <p className="label mb-2">SHAP Feature Attributions</p>
                    <ShapBars factors={tx.fraud_factors ?? []} />
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3">
                  <div className="flex items-center gap-2 text-xs text-ink-3">
                    {tx.is_anomaly && (
                      <span className="inline-flex items-center gap-1 rounded border border-warn/20 bg-warn/10 px-2 py-0.5 text-[10px] font-semibold text-warn">
                        <ShieldAlert className="h-3 w-3" /> Unusual spending pattern
                      </span>
                    )}
                    <span className="num font-semibold">{formatINR(tx.amount, { decimals: true })}</span>
                  </div>

                  <motion.button
                    type="button"
                    whileTap={{ scale: 0.97 }}
                    transition={spring}
                    onClick={() => (confirming ? onDelete(tx.id) : setConfirming(true))}
                    className={clsx(
                      "btn-danger relative overflow-hidden py-1 px-3 text-xs",
                      confirming && "!bg-danger !text-white"
                    )}
                  >
                    <Trash2 className="h-3 w-3" />
                    <span>{confirming ? "Confirm Delete" : "Delete"}</span>
                    {confirming && (
                      <motion.span
                        className="absolute inset-x-0 bottom-0 h-0.5 origin-left bg-white/70"
                        initial={{ scaleX: 1 }}
                        animate={{ scaleX: 0 }}
                        transition={{ duration: 3.5, ease: "linear" }}
                      />
                    )}
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
