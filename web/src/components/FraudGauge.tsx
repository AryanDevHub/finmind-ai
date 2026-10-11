import { motion, useReducedMotion } from "framer-motion";
import { useId } from "react";

import { useCountUp } from "@/hooks/useCountUp";
import { gaugeColor } from "@/lib/risk";
import type { RiskLevel } from "@/types";
import { RiskBadge } from "./ui/RiskBadge";

interface Props {
  /** Calibrated fraud probability in percent (0..100). */
  value: number;
  level?: RiskLevel;
  size?: number;
  /** Hide the big number + badge (compact previews). */
  compact?: boolean;
}

const CX = 100, CY = 100, R = 78;
const ARC = `M ${CX - R} ${CY} A ${R} ${R} 0 0 1 ${CX + R} ${CY}`;

/**
 * Semicircular risk gauge: gradient arc (emerald → amber → crimson), a needle that swings on a spring,
 * and a count-up readout whose colour is interpolated from the value.
 */
export function FraudGauge({ value, level, size = 220, compact = false }: Props) {
  const gid = useId();
  const reduce = useReducedMotion();
  const v = Math.max(0, Math.min(100, value));
  const shown = useCountUp(v, { duration: 900 });
  const color = gaugeColor(v);
  const angle = -90 + v * 1.8; // -90° (0%) … +90° (100%)

  return (
    <div className="inline-flex flex-col items-center" role="meter" aria-label="Fraud probability" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(v)} style={{ width: size }}>
      <svg viewBox="0 0 200 118" width={size} height={size * 0.59} className="overflow-visible">
        <defs>
          <linearGradient id={gid} x1={CX - R} x2={CX + R} y1="0" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#34D399" />
            <stop offset="45%" stopColor="#FBBF24" />
            <stop offset="100%" stopColor="#F43F5E" />
          </linearGradient>
        </defs>
        <path d={ARC} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth={12} strokeLinecap="round" />
        <motion.path d={ARC} fill="none" stroke={`url(#${gid})`} strokeWidth={12} strokeLinecap="round"
          initial={{ pathLength: 0 }} animate={{ pathLength: Math.max(v / 100, 0.001) }}
          transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 55, damping: 16, delay: 0.1 }}
          style={{ filter: `drop-shadow(0 0 7px ${color}77)` }} />
        {[0, 25, 50, 75, 100].map((t) => {
          const a = ((-90 + t * 1.8) * Math.PI) / 180;
          return (
            <g key={t}>
              <line x1={CX + (R + 11) * Math.sin(a)} y1={CY - (R + 11) * Math.cos(a)} x2={CX + (R + 16) * Math.sin(a)} y2={CY - (R + 16) * Math.cos(a)} stroke="rgba(255,255,255,0.25)" strokeWidth={1.5} />
              <text x={CX + (R + 27) * Math.sin(a)} y={CY - (R + 27) * Math.cos(a) + 3} textAnchor="middle" fontSize="8" fill="#5C6B8A" className="num">{t}</text>
            </g>
          );
        })}
        {/* needle: rotates around the hub on a spring */}
        <motion.g initial={{ rotate: -90 }} animate={{ rotate: angle }} transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 70, damping: 11, mass: 0.9 }}
          style={{ transformOrigin: `${CX}px ${CY}px`, transformBox: "view-box" }}>
          <path d={`M ${CX - 3} ${CY} L ${CX} ${CY - R + 8} L ${CX + 3} ${CY} Z`} fill={color} style={{ filter: `drop-shadow(0 0 4px ${color})` }} />
        </motion.g>
        <circle cx={CX} cy={CY} r={7} fill="#0E1424" stroke={color} strokeWidth={2.5} />
      </svg>
      {!compact && (
        <div className="-mt-1 flex flex-col items-center gap-1.5">
          <span className="num text-3xl font-semibold leading-none" style={{ color }}>{shown.toFixed(1)}<span className="text-lg">%</span></span>
          {level && <RiskBadge level={level} />}
        </div>
      )}
    </div>
  );
}
