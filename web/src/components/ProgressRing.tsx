import { motion } from "framer-motion";

import { useCountUp } from "@/hooks/useCountUp";

/** Circular progress with a count-up percentage in the middle. `value` is clamped to 0..100 for the arc. */
export function ProgressRing({ value, color, size = 72, stroke = 7, label }: { value: number; color: string; size?: number; stroke?: number; label?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, value));
  const shown = useCountUp(value);
  return (
    <div className="relative shrink-0" style={{ width: size, height: size }} role="meter" aria-label={label ?? "progress"} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(clamped)}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={stroke} />
        <motion.circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={c} initial={{ strokeDashoffset: c }} animate={{ strokeDashoffset: c * (1 - clamped / 100) }}
          transition={{ type: "spring", stiffness: 60, damping: 18, delay: 0.25 }}
          style={{ filter: `drop-shadow(0 0 6px ${color}88)` }}
        />
      </svg>
      <span className="num absolute inset-0 grid place-items-center text-[13px] font-semibold" style={{ color }}>{Math.round(shown)}%</span>
    </div>
  );
}
