import clsx from "clsx";

import { RISK_STYLE } from "@/lib/risk";
import type { RiskLevel } from "@/types";

/** LOW / MEDIUM / HIGH / CRITICAL pill. CRITICAL pulses. */
export function RiskBadge({ level, className }: { level: RiskLevel; className?: string }) {
  const s = RISK_STYLE[level];
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[10.5px] font-bold uppercase tracking-wider", s.bg, s.ring, s.text, className)}>
      <span className="relative flex h-1.5 w-1.5">
        {level === "CRITICAL" && <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75" style={{ background: s.hex }} />}
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full" style={{ background: s.hex }} />
      </span>
      {level}
    </span>
  );
}
