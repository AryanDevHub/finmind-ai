import { useReducedMotion } from "framer-motion";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCompactINR, formatINR } from "@/lib/format";
import type { SeriesPoint } from "@/lib/metrics";
import { AXIS, ChartTooltip, GRID } from "./ChartTooltip";

/** Cumulative net savings as a spline area with a soft gradient fill. */
export function SavingsArea({ data }: { data: readonly SeriesPoint[] }) {
  const reduce = useReducedMotion();
  const neg = data.some((d) => d.value < 0);
  return (
    <div className="h-[200px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data as SeriesPoint[]} margin={{ top: 8, right: 4, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="gSave" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#22D3EE" stopOpacity={0.45} /><stop offset="100%" stopColor="#22D3EE" stopOpacity={0} /></linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="date" {...AXIS} interval="preserveStartEnd" minTickGap={36} />
          <YAxis {...AXIS} tickFormatter={formatCompactINR} width={52} />
          {neg && <ReferenceLine y={0} stroke="rgba(244,63,94,0.5)" strokeDasharray="4 4" />}
          <Tooltip cursor={{ stroke: "rgba(34,211,238,0.35)" }} content={<ChartTooltip rows={(e) => ({ name: "Net savings", value: formatINR(Number(e.value)), color: "#22D3EE" })} />} />
          <Area type="monotone" dataKey="value" stroke="#22D3EE" strokeWidth={2.5} fill="url(#gSave)" isAnimationActive={!reduce} animationDuration={1100}
            activeDot={{ r: 5, stroke: "#070A11", strokeWidth: 2, fill: "#22D3EE" }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
