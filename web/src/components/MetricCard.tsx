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
  /** Colour of the ambient backlight and accents. */
  color: string;
  /** Pulsating glow, used for active fraud alerts. */
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
 * KPI tile: count-up number (tabular figures), a coloured ambient backlight that can pulse, 3D tilt on hover,
 * and a staggered entrance when placed inside a `variants={container}` parent.
 */
export function MetricCard({ label, value, format, color, pulse, delta, hint, visual, footer }: MetricCardProps) {
  const shown = useCountUp(value);
  const up = (delta?.pct ?? 0) >= 0;
  const favourable = delta?.pct == null ? null : (delta.good === "up") === up;

  return (
    <GlassCard tilt variants={item} className="overflow-hidden p-5">
      {/* ambient backlight */}
      <div aria-hidden className={clsx("pointer-events-none absolute -right-10 -top-14 h-44 w-44 rounded-full blur-3xl", pulse ? "animate-glow" : "opacity-30")}
        style={{ background: `radial-gradient(circle, ${color}, transparent 68%)` }} />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="label">{label}</p>
          <p className="num mt-2 whitespace-nowrap text-[26px] font-semibold leading-none tracking-tight" aria-label={`${label}: ${format(value)}`}>{format(shown)}</p>
          <div className="mt-3 flex min-h-[20px] flex-wrap items-center gap-2 text-xs text-ink-3">
            {delta && delta.pct != null && (
              <motion.span initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.6 }}
                className={clsx("num inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 font-semibold", favourable ? "bg-gain/10 text-gain" : "bg-warn/10 text-warn")}>
                {up ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
                {Math.abs(delta.pct).toFixed(0)}%
              </motion.span>
            )}
            {hint}
          </div>
        </div>
        {visual && <div className="shrink-0 self-center">{visual}</div>}
      </div>
      {footer && <div className="relative mt-3">{footer}</div>}
    </GlassCard>
  );
}
