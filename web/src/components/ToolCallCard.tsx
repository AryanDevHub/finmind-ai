import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, ChevronDown, Database, Loader2, Search, XCircle } from "lucide-react";
import { useState, type ReactNode } from "react";

import type { ToolStep } from "@/types";

const SQL_KEYWORDS = new Set(("SELECT FROM WHERE GROUP BY ORDER LIMIT AND OR NOT AS IN ON JOIN LEFT RIGHT INNER WITH CASE WHEN THEN ELSE END DESC ASC FILTER OVER PARTITION DISTINCT BETWEEN LIKE ILIKE IS NULL INTERVAL HAVING TRUE FALSE").split(" "));
const SQL_FUNCS = new Set(("SUM COUNT AVG MIN MAX ROUND COALESCE NULLIF DATE_TRUNC TO_CHAR EXTRACT CAST LOWER UPPER NOW RANK ROW_NUMBER").split(" "));

/** Light, dependency-free SQL highlighting: strings, numbers, functions, keywords. */
export function highlightSql(sql: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z_0-9]*)|(\s+|[^\sA-Za-z_\d']+)/g;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = re.exec(sql))) {
    const tok = m[0];
    const k = key++;
    if (m[1]) out.push(<span key={k} className="text-amber-300">{tok}</span>);
    else if (m[2]) out.push(<span key={k} className="text-violet-300">{tok}</span>);
    else if (m[3]) {
      const up = tok.toUpperCase();
      if (SQL_KEYWORDS.has(up)) out.push(<span key={k} className="font-semibold text-signal">{tok}</span>);
      else if (SQL_FUNCS.has(up) && sql[m.index + tok.length] === "(") out.push(<span key={k} className="text-emerald-300">{tok}</span>);
      else out.push(<span key={k}>{tok}</span>);
    } else out.push(<span key={k}>{tok}</span>);
  }
  return out;
}

const TOOL_META: Record<string, { name: string; icon: typeof Database; argLabel: string }> = {
  run_sql_query: { name: "SQL query", icon: Database, argLabel: "Arguments · sql" },
  semantic_search_transactions: { name: "Semantic search", icon: Search, argLabel: "Arguments · query" },
};

/** JSON view of a tool result: columns + rows -> array of objects. */
export function previewJson(step: ToolStep): string {
  if (!step.preview) return "{}";
  const { columns, rows } = step.preview;
  const objs = rows.map((r) => Object.fromEntries(columns.map((c, i) => [c, r[i]])));
  const more = step.row_count > rows.length ? `\n// … ${step.row_count - rows.length} more row(s) not shown` : "";
  return JSON.stringify(objs, null, 2) + more;
}

interface Props { step: ToolStep; /** still executing (spinner), before the result is revealed */ running?: boolean; defaultOpen?: boolean }

/** Collapsible accordion showing one tool call the agent made: name, arguments, JSON result and status. */
export function ToolCallCard({ step, running = false, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = TOOL_META[step.tool] ?? { name: step.tool, icon: Database, argLabel: "Arguments" };
  const Icon = meta.icon;
  const isSql = step.tool === "run_sql_query";

  return (
    <motion.div initial={{ opacity: 0, y: 8, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={{ type: "spring", stiffness: 300, damping: 26 }}
      className={clsx("overflow-hidden rounded-xl border bg-void/50", running ? "border-signal/30" : step.ok ? "border-white/[0.09]" : "border-danger/30")}>
      <button type="button" disabled={running} aria-expanded={open} onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left">
        <Icon className="h-4 w-4 shrink-0 text-signal" />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-semibold">{meta.name}</span>
          <span className="block truncate text-[11px] text-ink-3">{running ? "Running…" : step.ok ? `${step.row_count} row${step.row_count === 1 ? "" : "s"} returned` : step.error ?? "Failed"}</span>
        </span>
        {running ? <Loader2 className="h-4 w-4 animate-spin text-signal" /> : step.ok ? (
          <motion.span initial={{ scale: 0 }} animate={{ scale: 1 }} transition={{ type: "spring", stiffness: 500, damping: 18 }}><CheckCircle2 className="h-4 w-4 text-gain" /></motion.span>
        ) : <XCircle className="h-4 w-4 text-danger" />}
        {!running && <ChevronDown className={clsx("h-4 w-4 text-ink-3 transition-transform", open && "rotate-180")} />}
      </button>
      <AnimatePresence initial={false}>
        {open && !running && (
          <motion.div initial={{ height: 0 }} animate={{ height: "auto" }} exit={{ height: 0 }} transition={{ type: "spring", stiffness: 280, damping: 32 }} className="overflow-hidden">
            <div className="space-y-3 border-t border-white/[0.06] p-3">
              <div>
                <p className="label mb-1.5">{meta.argLabel}</p>
                <pre className="num max-h-40 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-void p-2.5 text-[11.5px] leading-relaxed text-ink-2">{isSql ? highlightSql(step.detail) : step.detail}</pre>
              </div>
              <div>
                <p className="label mb-1.5">{step.ok ? "Result" : "Error"}</p>
                <pre className={clsx("num max-h-48 overflow-auto rounded-lg bg-void p-2.5 text-[11.5px] leading-relaxed", step.ok ? "text-ink-2" : "text-danger")}>{step.ok ? previewJson(step) : step.error}</pre>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
