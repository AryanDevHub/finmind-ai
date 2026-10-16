import clsx from "clsx";
import { motion } from "framer-motion";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";

import { useCountUp } from "@/hooks/useCountUp";
import { item } from "@/lib/motion";
import { GlassCard } from "./ui/GlassCard";

export interface MetricCardProps {
  label: string;
  value: number;
  /** Formats the (animated) number: currency, percent, plain. */
  format: (n: number) => string;
  /** Colour of the accents. */
  color: string;
  /** Active fraud alert badge. */
  pulse?: boolean;
  /** Month-over-month change in %. `good` says which direction is desirable. */
  delta?: { pct: number | null; good: "up" | "down" };
  hint?: ReactNode;
  /** Right-hand visual: progress ring, alert badge... */
  visual?: ReactNode;
  /** Full-width strip under the value (sparkline). */
  footer?: ReactNode;
}

/**
 * Precision KPI Tile
 * Engineered tabular numbers, clean percentage badges, and integrated sparklines.
 */
export function MetricCard({ label, value, format, color: _color, pulse: _pulse, delta, hint, visual, footer }: MetricCardProps) {
  const shown = useCountUp(value);
  const up = (delta?.pct ?? 0) >= 0;
  const favourable = delta?.pct == null ? null : (delta.good === "up") === up;

  return (
    <GlassCard variants={item} className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="label">{label}</p>
          <p
            className="num mt-2 whitespace-nowrap text-2xl font-bold tracking-tight text-ink-1"
            aria-label={`${label}: ${format(value)}`}
          >
            {format(shown)}
          </p>

          <div className="mt-2.5 flex min-h-[20px] flex-wrap items-center gap-2 text-xs text-ink-3">
            {delta && delta.pct != null && (
              <motion.span
                initial={{ opacity: 0, y: 3 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
                className={clsx(
                  "num inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[11px] font-semibold",
                  favourable ? "bg-emerald/10 text-emerald" : "bg-warn/10 text-warn"
                )}
              >
                {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {Math.abs(delta.pct).toFixed(0)}%
              </motion.span>
            )}
            {hint}
          </div>
        </div>

        {visual && <div className="shrink-0 self-center">{visual}</div>}
      </div>

      {footer && <div className="mt-3 border-t border-border/60 pt-2">{footer}</div>}
    </GlassCard>
  );
}
