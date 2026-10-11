import { useReducedMotion } from "framer-motion";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCompactINR, formatINR } from "@/lib/format";
import type { MonthFlow } from "@/lib/metrics";
import { AXIS, ChartTooltip, GRID } from "./ChartTooltip";

/** Grouped inflow/outflow bars with rounded tops and a glass tooltip. */
export function FlowBars({ data }: { data: readonly MonthFlow[] }) {
  const reduce = useReducedMotion();
  return (
    <div className="h-[240px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data as MonthFlow[]} barGap={4} margin={{ top: 8, right: 4, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="gIn" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#34D399" /><stop offset="100%" stopColor="#34D399" stopOpacity={0.35} /></linearGradient>
            <linearGradient id="gOut" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#22D3EE" /><stop offset="100%" stopColor="#22D3EE" stopOpacity={0.35} /></linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="month" {...AXIS} />
          <YAxis {...AXIS} tickFormatter={formatCompactINR} width={52} />
          <Tooltip cursor={{ fill: "rgba(255,255,255,0.04)", radius: 8 }}
            content={<ChartTooltip rows={(e) => ({ name: e.dataKey === "inflow" ? "Inflow" : "Outflow", value: formatINR(Number(e.value)), color: e.dataKey === "inflow" ? "#34D399" : "#22D3EE" })} />} />
          <Bar dataKey="inflow" fill="url(#gIn)" radius={[7, 7, 0, 0]} maxBarSize={26} isAnimationActive={!reduce} animationDuration={900} />
          <Bar dataKey="outflow" fill="url(#gOut)" radius={[7, 7, 0, 0]} maxBarSize={26} isAnimationActive={!reduce} animationDuration={900} animationBegin={150} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
