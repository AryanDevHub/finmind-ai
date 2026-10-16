import clsx from "clsx";
import { AnimatePresence } from "framer-motion";
import { Inbox, Search, X } from "lucide-react";
import { useMemo, useState } from "react";

import type { Transaction } from "@/types";
import { TransactionRow } from "./TransactionRow";
import { Skeleton } from "./ui/Skeleton";

type Filter = "all" | "flagged" | "expense" | "income";
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "flagged", label: "Flagged" },
  { id: "expense", label: "Expenses" },
  { id: "income", label: "Income" },
];
const PAGE = 15;

interface Props {
  transactions: readonly Transaction[];
  loading?: boolean;
  onDelete: (id: string) => void;
  /** Dashboard preview mode: no filters, no search, fixed row count. */
  preview?: number;
}

/** Filterable, searchable financial transaction ledger. */
export function TransactionLedger({ transactions, loading, onDelete, preview }: Props) {
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");
  const [visible, setVisible] = useState(PAGE);

  const counts = useMemo(
    () => ({
      all: transactions.length,
      flagged: transactions.filter((t) => t.is_flagged).length,
      expense: transactions.filter((t) => t.transaction_type === "expense").length,
      income: transactions.filter((t) => t.transaction_type === "income").length,
    }),
    [transactions]
  );

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
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          {/* Segmented Filter Pills */}
          <div role="tablist" aria-label="Filter transactions" className="flex gap-1 rounded-lg border border-border bg-[#0C121D] p-1">
            {FILTERS.map((f) => {
              const active = filter === f.id;
              return (
                <button
                  key={f.id}
                  role="tab"
                  aria-selected={active}
                  onClick={() => {
                    setFilter(f.id);
                    setVisible(PAGE);
                  }}
                  className={clsx(
                    "flex items-center gap-1.5 rounded-md px-3 py-1 text-xs font-semibold transition-all duration-150",
                    active
                      ? "border border-border-strong bg-surface text-ink-1 shadow-sm"
                      : "text-ink-3 hover:text-ink-1"
                  )}
                >
                  <span>{f.label}</span>
                  <span
                    className={clsx(
                      "num rounded px-1 py-0.2 text-[10px]",
                      active ? "bg-border text-ink-1" : "text-ink-4"
                    )}
                  >
                    {counts[f.id]}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Quick Search */}
          <div className="relative min-w-[200px] flex-1 sm:max-w-xs">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-4" />
            <input
              value={q}
              onChange={(e) => {
                setQ(e.target.value);
                setVisible(PAGE);
              }}
              placeholder="Filter by merchant, category..."
              aria-label="Search transactions"
              className="field !py-1.5 pl-8 pr-7 text-xs"
            />
            {q && (
              <button
                onClick={() => setQ("")}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-4 hover:text-ink-2"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </div>
      )}

      {loading ? (
        <div className="space-y-2">
          {Array.from({ length: preview ?? 5 }).map((_, i) => (
            <Skeleton key={i} className="h-[60px] rounded-xl" />
          ))}
        </div>
      ) : shown.length === 0 ? (
        <div className="glass grid place-items-center gap-2 py-12 text-center">
          <Inbox className="h-7 w-7 text-ink-4" />
          <p className="text-xs font-semibold text-ink-2">{transactions.length ? "No transactions match your filter" : "No transactions recorded"}</p>
          <p className="text-[11px] text-ink-4">
            {transactions.length ? "Try clearing search keywords or switching filters." : "Connect a bank account or add an entry above."}
          </p>
        </div>
      ) : (
        <ul className="space-y-1">
          <AnimatePresence initial={false}>
            {shown.map((t) => (
              <TransactionRow key={t.id} tx={t} onDelete={onDelete} />
            ))}
          </AnimatePresence>
        </ul>
      )}

      {!preview && rows.length > visible && (
        <button
          className="btn-secondary mx-auto mt-3 flex"
          onClick={() => setVisible((v) => v + PAGE)}
        >
          Show more ({rows.length - visible} remaining)
        </button>
      )}
    </div>
  );
}
