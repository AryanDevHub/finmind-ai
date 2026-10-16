import clsx from "clsx";
import { motion } from "framer-motion";
import { Building2, LayoutDashboard, LineChart, PiggyBank, Receipt, ShieldCheck, type LucideIcon } from "lucide-react";

import type { Route } from "@/hooks/useHashRoute";
import { spring } from "@/lib/motion";
import { Logo } from "./Logo";

export const NAV: { id: Route; label: string; icon: LucideIcon }[] = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "bank", label: "Bank Connect", icon: Building2 },
  { id: "transactions", label: "Transactions", icon: Receipt },
  { id: "budgets", label: "Budgets", icon: PiggyBank },
  { id: "insights", label: "Analytics", icon: LineChart },
];

/** Desktop: precision left rail. Mobile: bottom tab bar with 5 items. */
export function Sidebar({ route, onNavigate }: { route: Route; onNavigate: (r: Route) => void }) {
  return (
    <>
      {/* Desktop Rail */}
      <nav aria-label="Primary" className="sticky top-0 hidden h-screen w-[240px] shrink-0 flex-col border-r border-border bg-[#090D15] p-4 md:flex">
        <div className="mb-6 mt-1 px-2">
          <Logo />
          <div className="mt-2 flex items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded border border-emerald/20 bg-emerald/5 px-1.5 py-0.5 text-[10px] font-semibold text-emerald">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald" />
              Verified Bank Sync
            </span>
          </div>
        </div>

        <div className="space-y-1">
          <p className="px-2 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-ink-3">Platform</p>
          <ul className="space-y-1">
            {NAV.map(({ id, label, icon: Icon }) => {
              const active = route === id;
              return (
                <li key={id}>
                  <button
                    onClick={() => onNavigate(id)}
                    aria-current={active ? "page" : undefined}
                    className={clsx(
                      "group relative flex w-full items-center gap-3 rounded-lg px-3 py-2 text-xs font-semibold tracking-wide transition-all duration-150",
                      active
                        ? "border border-border-strong bg-surface text-ink-1 shadow-sm"
                        : "text-ink-2 hover:border-border hover:bg-surface/50 hover:text-ink-1"
                    )}
                  >
                    {active && (
                      <motion.span
                        layoutId="nav-active-indicator"
                        transition={spring}
                        className="absolute -left-1 top-1.5 bottom-1.5 w-1 rounded-full bg-emerald"
                      />
                    )}
                    <Icon className={clsx("h-4 w-4 shrink-0 transition-colors", active ? "text-emerald" : "text-ink-3 group-hover:text-ink-2")} />
                    <span>{label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Security & System Info Footer */}
        <div className="mt-auto border-t border-border pt-4 px-2">
          <div className="flex items-center gap-2 text-[11px] font-medium text-ink-3">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald" />
            <span>256-Bit Encrypted</span>
          </div>
          <p className="mt-1 text-[10px] leading-tight text-ink-4">
            LightGBM ML · TreeSHAP<br />
            pgvector · Llama 3.3 70B
          </p>
        </div>
      </nav>

      {/* Mobile Bottom Navigation (All 5 items accommodated) */}
      <nav aria-label="Primary Mobile" className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-border bg-[#090D15]/95 px-1 pb-[max(env(safe-area-inset-bottom),0.4rem)] pt-2 backdrop-blur-md md:hidden">
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = route === id;
          return (
            <button
              key={id}
              onClick={() => onNavigate(id)}
              aria-current={active ? "page" : undefined}
              className={clsx(
                "flex flex-col items-center gap-1 rounded-md py-1 text-[10px] font-semibold transition-colors",
                active ? "text-emerald" : "text-ink-3 hover:text-ink-2"
              )}
            >
              <Icon className="h-4 w-4" />
              <span className="truncate">{label.split(" ")[0]}</span>
            </button>
          );
        })}
      </nav>
    </>
  );
}
