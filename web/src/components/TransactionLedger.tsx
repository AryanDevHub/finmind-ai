import clsx from "clsx";
import { AnimatePresence } from "framer-motion";
import { Inbox, Search } from "lucide-react";
import { useMemo, useState } from "react";

import type { Transaction } from "@/types";
import { TransactionRow } from "./TransactionRow";
import { Skeleton } from "./ui/Skeleton";

type Filter = "all" | "flagged" | "expense" | "income";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" }, { id: "flagged", label: "Flagged" }, { id: "expense", label: "Expenses" }, { id: "income", label: "Income" },
];
const PAGE = 15;

interface Props {
  transactions: readonly Transaction[];
  loading?: boolean;
  onDelete: (id: string) => void;
  /** Dashboard preview mode: no filters, no search, fixed row count. */
  preview?: number;
}

/** Filterable, searchable ledger. Rows animate in/out with height + opacity as the list changes. */
export function TransactionLedger({ transactions, loading, onDelete, preview }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [visible, setVisible] = useState(PAGE);

  const counts = useMemo(() => ({
    all: transactions.length,
    flagged: transactions.filter((t) => t.is_flagged).length,
    expense: transactions.filter((t) => t.transaction_type === "expense").length,
    income: transactions.filter((t) => t.transaction_type === "income").length,
  }), [transactions]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return transactions.filter((t) => {
      if (filter === "flagged" && !t.is_flagged) return false;
      if ((filter === "expense" || filter === "income") && t.transaction_type !== filter) return false;
      return !needle || `${t.description} ${t.merchant ?? ""} ${t.category}`.toLowerCase().includes(needle);
    });
  }, [transactions, filter, q]);

  const shown = preview ? rows.slice(0, preview) : rows.slice(0, visible);

  return (
    <div>
      {!preview && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <div role="tablist" aria-label="Filter transactions" className="flex gap-1 rounded-xl border border-white/[0.08] bg-card/60 p-1">
            {FILTERS.map((f) => (
              <button key={f.id} role="tab" aria-selected={filter === f.id} onClick={() => { setFilter(f.id); setVisible(PAGE); }}
                className={clsx("rounded-lg px-3 py-1.5 text-[13px] font-semibold transition-colors duration-200", filter === f.id ? "bg-signal text-void shadow-[0_6px_18px_-8px_rgba(34,211,238,0.8)]" : "text-ink-2 hover:bg-white/[0.05] hover:text-ink-1")}>
                {f.label} <span className={clsx("num text-[11px]", filter === f.id ? "text-void/70" : "text-ink-4")}>{counts[f.id]}</span>
              </button>
            ))}
          </div>
          <label className="relative min-w-[180px] flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-4" />
            <input value={q} onChange={(e) => { setQ(e.target.value); setVisible(PAGE); }} placeholder="Search description, merchant…" aria-label="Search transactions" className="field !py-2 pl-9" />
          </label>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">{Array.from({ length: preview ?? 5 }).map((_, i) => <Skeleton key={i} className="h-[68px] rounded-2xl" />)}</div>
      ) : shown.length === 0 ? (
        <div className="glass-static grid place-items-center gap-2 py-14 text-center">
          <Inbox className="h-8 w-8 text-ink-4" />
          <p className="text-sm font-semibold">{transactions.length ? "Nothing matches" : "No transactions yet"}</p>
          <p className="text-xs text-ink-3">{transactions.length ? "Try a different filter or search." : "Add your first one to see it scored in real time."}</p>
        </div>
      ) : (
        <ul>
          <AnimatePresence initial={false}>
            {shown.map((t) => <TransactionRow key={t.id} tx={t} onDelete={onDelete} />)}
          </AnimatePresence>
        </ul>
      )}

      {!preview && rows.length > visible && (
        <button className="btn-ghost mx-auto mt-3 flex" onClick={() => setVisible((v) => v + PAGE)}>Show more ({rows.length - visible} left)</button>
      )}
    </div>
  );
}
