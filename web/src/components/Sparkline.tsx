import { motion } from "framer-motion";
import { useId } from "react";

/**
 * Minimal animated sparkline: the line draws itself in, with a soft gradient fill underneath.
 * Fluid width (fills its container); the stroke keeps a constant thickness however the SVG is stretched.
 */
export function Sparkline({ data, color = "#22D3EE", height = 34 }: { data: readonly number[]; color?: string; height?: number }) {
  const gid = useId();
  const W = 200;
  if (data.length < 2) return <div style={{ height }} aria-hidden />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => [(i / (data.length - 1)) * W, height - 3 - ((v - min) / span) * (height - 8)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  const area = `${line} L${W} ${height} L0 ${height} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${height}`} preserveAspectRatio="none" width="100%" height={height} role="img" aria-label="trend sparkline" className="block">
      <defs>
        <linearGradient id={gid} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.35} />
          <stop offset="100%" stopColor={color} stopOpacity={0} />
        </linearGradient>
      </defs>
      <motion.path d={area} fill={`url(#${gid})`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5, duration: 0.8 }} />
      <motion.path d={line} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1, ease: "easeOut" }} style={{ filter: `drop-shadow(0 0 4px ${color}88)` }} />
    </svg>
  );
}
