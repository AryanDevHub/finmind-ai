import type { ReactNode } from "react";

interface Entry { name?: string | number; value?: number | string | Array<number | string>; color?: string; dataKey?: string | number }
interface Props {
  active?: boolean;
  label?: string | number;
  payload?: Entry[];
  /** Map a series entry to a display row; return null to hide it. */
  rows?: (e: Entry) => { name: string; value: string; color?: string } | null;
  title?: ReactNode;
}

/** Glassmorphic tooltip shared by every chart. */
export function ChartTooltip({ active, label, payload, rows, title }: Props) {
  if (!active || !payload?.length) return null;
  const lines = payload
    .map((e) => (rows ? rows(e) : { name: String(e.name ?? e.dataKey ?? ""), value: String(e.value ?? ""), color: e.color }))
    .filter((x): x is { name: string; value: string; color?: string } => x !== null);
  if (!lines.length) return null;
  return (
    <div className="glass-elevated min-w-[150px] px-3.5 py-2.5 text-xs shadow-2xl">
      {(title ?? label) !== undefined && <p className="mb-1.5 font-semibold text-ink-1">{title ?? label}</p>}
      <ul className="space-y-1">
        {lines.map((l) => (
          <li key={l.name} className="flex items-center justify-between gap-5">
            <span className="flex items-center gap-1.5 text-ink-2">
              {l.color && <span className="h-2 w-2 rounded-full" style={{ background: l.color }} />}{l.name}
            </span>
            <span className="num font-semibold text-ink-1">{l.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export const AXIS = { stroke: "#5C6B8A", fontSize: 11, tickLine: false, axisLine: false } as const;
export const GRID = "rgba(255,255,255,0.05)";
