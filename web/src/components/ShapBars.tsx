import clsx from "clsx";
import { motion } from "framer-motion";

import type { SHAPValue } from "@/types";

/**
 * Diverging attribution bars. Right/crimson pushes the fraud score UP, left/emerald pulls it DOWN.
 * Bar length is proportional to |contribution| relative to the largest driver shown.
 * Values are TreeSHAP contributions in LOG-ODDS (not percentage points); the server returns the top 3.
 */
export function ShapBars({ factors, compact = false }: { factors: readonly SHAPValue[]; compact?: boolean }) {
  if (!factors.length) return <p className="text-sm text-ink-3">No attribution recorded for this transaction.</p>;
  const max = Math.max(...factors.map((f) => Math.abs(f.contribution)), 1e-9);
  return (
    <div>
      <ul className="space-y-2.5" aria-label="Feature attributions">
        {factors.map((f, i) => {
          const up = f.contribution > 0;
          const pct = (Math.abs(f.contribution) / max) * 100;
          return (
            <li key={f.feature} className={clsx("grid items-center gap-x-3", compact ? "grid-cols-[1fr]" : "grid-cols-[minmax(0,12rem)_1fr_3.5rem]")}>
              <span className="truncate text-[13px] text-ink-2" title={f.label}>
                {f.label}
                {!f.feature.startsWith("cat_") && <span className="num ml-1.5 text-ink-4">{Number.isInteger(f.value) ? f.value : f.value.toFixed(2)}</span>}
              </span>
              <div className="relative h-2.5" aria-hidden>
                <div className="absolute inset-0 rounded-full bg-white/[0.04]" />
                <div className="absolute inset-y-0 left-1/2 w-px bg-white/20" />
                <motion.div
                  className={clsx("absolute inset-y-0 rounded-full", up ? "left-1/2 origin-left bg-gradient-to-r from-danger/70 to-danger" : "right-1/2 origin-right bg-gradient-to-l from-gain/70 to-gain")}
                  style={{ width: `${pct / 2}%`, boxShadow: `0 0 12px ${up ? "#F43F5E66" : "#34D39966"}` }}
                  initial={{ scaleX: 0 }} animate={{ scaleX: 1 }} transition={{ delay: 0.15 + i * 0.12, type: "spring", stiffness: 120, damping: 18 }}
                />
              </div>
              <span className={clsx("num text-right text-xs font-semibold", up ? "text-danger" : "text-gain", compact && "hidden")}>
                {f.contribution > 0 ? "+" : ""}{f.contribution.toFixed(2)}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-[11px] leading-relaxed text-ink-4">
        ← lowers risk · raises risk →  Contributions are TreeSHAP values in log-odds; the model reports its top 3 drivers.
      </p>
    </div>
  );
}
