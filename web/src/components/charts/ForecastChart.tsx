import { useReducedMotion } from "framer-motion";
import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatCompactINR, formatDay, formatINR } from "@/lib/format";
import type { ForecastWeek } from "@/types";
import { AXIS, ChartTooltip, GRID } from "./ChartTooltip";

/** AutoARIMA forecast: mean line with nested 80% and 95% prediction bands. */
export function ForecastChart({ weeks }: { weeks: readonly ForecastWeek[] }) {
  const reduce = useReducedMotion();
  const data = weeks.map((w) => ({ week: formatDay(w.week_start), mean: w.mean, b80: [w.lo80, w.hi80] as [number, number], b95: [w.lo95, w.hi95] as [number, number] }));
  return (
    <div className="h-[260px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="week" {...AXIS} />
          <YAxis {...AXIS} tickFormatter={formatCompactINR} width={52} domain={[0, "auto"]} />
          <Tooltip content={<ChartTooltip title="Week of" rows={(e) => {
            const v = e.value;
            if (e.dataKey === "mean") return { name: "Forecast", value: formatINR(Number(v)), color: "#22D3EE" };
            if (Array.isArray(v)) return { name: e.dataKey === "b80" ? "80% band" : "95% band", value: `${formatCompactINR(Number(v[0]))} – ${formatCompactINR(Number(v[1]))}` };
            return null;
          }} />} />
          <Area dataKey="b95" stroke="none" fill="#22D3EE" fillOpacity={0.1} isAnimationActive={!reduce} />
          <Area dataKey="b80" stroke="none" fill="#22D3EE" fillOpacity={0.22} isAnimationActive={!reduce} />
          <Line dataKey="mean" type="monotone" stroke="#22D3EE" strokeWidth={2.5} dot={{ r: 3.5, fill: "#22D3EE", stroke: "#070A11", strokeWidth: 2 }} isAnimationActive={!reduce} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
