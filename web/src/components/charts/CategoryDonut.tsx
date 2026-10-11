import { useReducedMotion } from "framer-motion";
import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Sector } from "recharts";

import { CATEGORY_META } from "@/lib/categories";
import { formatINR } from "@/lib/format";
import type { CategorySlice } from "@/lib/metrics";

interface SectorProps { cx: number; cy: number; innerRadius: number; outerRadius: number; startAngle: number; endAngle: number; fill: string }

/** Donut with smooth slice expansion on hover and live telemetry (name · amount · share) in the centre. */
export function CategoryDonut({ data }: { data: readonly CategorySlice[] }) {
  const [active, setActive] = useState<number | null>(null);
  const reduce = useReducedMotion();
  const total = data.reduce((s, d) => s + d.amount, 0);
  const cur = active !== null ? data[active] : undefined;

  const activeShape = (p: unknown) => {
    const s = p as SectorProps;
    return (
      <g style={{ filter: `drop-shadow(0 0 10px ${s.fill}99)` }}>
        <Sector cx={s.cx} cy={s.cy} innerRadius={s.innerRadius - 2} outerRadius={s.outerRadius + 9} startAngle={s.startAngle} endAngle={s.endAngle} fill={s.fill} cornerRadius={6} />
      </g>
    );
  };

  return (
    <div className="flex flex-col items-center gap-5 sm:flex-row">
      <div className="relative h-[220px] w-[220px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data as CategorySlice[]} dataKey="amount" nameKey="category" innerRadius="64%" outerRadius="88%" paddingAngle={3} cornerRadius={6} stroke="none"
              isAnimationActive={!reduce} animationDuration={900}
              activeIndex={active ?? undefined} activeShape={activeShape}
              onMouseEnter={(_, i) => setActive(i)} onMouseLeave={() => setActive(null)}>
              {data.map((d) => <Cell key={d.category} fill={CATEGORY_META[d.category].color} opacity={active === null || data[active]?.category === d.category ? 1 : 0.35} />)}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <p className="label">{cur ? cur.category : "Total spent"}</p>
            <p className="num mt-1 text-xl font-semibold">{formatINR(cur ? cur.amount : total)}</p>
            {cur && <p className="num text-xs text-ink-3">{cur.pct.toFixed(1)}%</p>}
          </div>
        </div>
      </div>
      <ul className="w-full min-w-0 flex-1 space-y-1.5" aria-label="Spending by category">
        {data.slice(0, 6).map((d, i) => (
          <li key={d.category} onMouseEnter={() => setActive(i)} onMouseLeave={() => setActive(null)}
            className="flex cursor-default items-center justify-between gap-3 rounded-lg px-2.5 py-1.5 text-sm transition-colors hover:bg-white/[0.04]">
            <span className="flex items-center gap-2 text-ink-2"><span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY_META[d.category].color }} />{d.category}</span>
            <span className="num text-xs text-ink-1">{formatINR(d.amount)} <span className="text-ink-4">· {d.pct.toFixed(0)}%</span></span>
          </li>
        ))}
      </ul>
    </div>
  );
}
