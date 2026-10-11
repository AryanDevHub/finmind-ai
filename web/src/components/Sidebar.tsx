import clsx from "clsx";
import { motion } from "framer-motion";
import { Building2, LayoutDashboard, LineChart, PiggyBank, Receipt, type LucideIcon } from "lucide-react";

import type { Route } from "@/hooks/useHashRoute";
import { spring } from "@/lib/motion";
import { Logo } from "./Logo";

export const NAV: { id: Route; label: string; icon: LucideIcon }[] = [
  { id: "dashboard", label: "Command Center", icon: LayoutDashboard },
  { id: "bank", label: "Bank Sync", icon: Building2 },
  { id: "transactions", label: "Transactions", icon: Receipt },
  { id: "budgets", label: "Budgets", icon: PiggyBank },
  { id: "insights", label: "Insights", icon: LineChart },
];

/** Desktop: left rail with a sliding active pill. Mobile: bottom tab bar. */
export function Sidebar({ route, onNavigate }: { route: Route; onNavigate: (r: Route) => void }) {
  return (
    <>
      <nav aria-label="Primary" className="sticky top-0 hidden h-screen w-[248px] shrink-0 flex-col border-r border-white/[0.06] bg-void/40 p-5 backdrop-blur-xl md:flex">
        <div className="mb-9 mt-1 px-1"><Logo /></div>
        <ul className="space-y-1">
          {NAV.map(({ id, label, icon: Icon }) => (
            <li key={id}>
              <button onClick={() => onNavigate(id)} aria-current={route === id ? "page" : undefined}
                className={clsx("relative flex w-full items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-semibold transition-colors", route === id ? "text-ink-1" : "text-ink-3 hover:text-ink-1")}>
                {route === id && <motion.span layoutId="nav-pill" transition={spring} className="absolute inset-0 rounded-xl border border-signal/25 bg-signal/10" style={{ boxShadow: "0 0 24px -8px rgba(34,211,238,.5)" }} />}
                <Icon className={clsx("relative h-[18px] w-[18px]", route === id && "text-signal")} />
                <span className="relative">{label}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-auto px-1 text-[11px] leading-relaxed text-ink-4">LightGBM · ONNX · TreeSHAP<br />pgvector · Llama 3.3 70B</p>
      </nav>

      <nav aria-label="Primary" className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-white/[0.08] bg-void/85 px-2 pb-[max(env(safe-area-inset-bottom),0.4rem)] pt-1.5 backdrop-blur-xl md:hidden">
        {NAV.map(({ id, label, icon: Icon }) => (
          <button key={id} onClick={() => onNavigate(id)} aria-current={route === id ? "page" : undefined} className={clsx("flex flex-col items-center gap-0.5 rounded-lg py-1.5 text-[10px] font-semibold", route === id ? "text-signal" : "text-ink-3")}>
            <Icon className="h-5 w-5" />{label.split(" ")[0]}
          </button>
        ))}
      </nav>
    </>
  );
}
