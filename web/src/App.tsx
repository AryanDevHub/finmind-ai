import { AnimatePresence, motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AddTransactionPanel } from "@/components/AddTransactionPanel";
import { AIChatDrawer } from "@/components/AIChatDrawer";
import { AuthScreen } from "@/components/AuthScreen";
import { BudgetView } from "@/components/BudgetView";
import { Dashboard } from "@/components/Dashboard";
import { InsightsView } from "@/components/InsightsView";
import { Logo } from "@/components/Logo";
import { Sidebar, NAV } from "@/components/Sidebar";
import { TopBar } from "@/components/TopBar";
import { TransactionsView } from "@/components/TransactionsView";
import { useHeartbeat } from "@/hooks/useHeartbeat";
import { useHashRoute } from "@/hooks/useHashRoute";
import { useAuth } from "@/lib/auth";
import { useTransactions } from "@/lib/queries";
import { computeFraudMetrics, THREAT_STYLE } from "@/lib/risk";
import type { User } from "@/types";

function Shell({ user }: { user: User }) {
  const { logout } = useAuth();
  const [route, go] = useHashRoute();
  const [addOpen, setAddOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [docked, setDocked] = useState(false);
  const heartbeat = useHeartbeat();
  const { data: txs } = useTransactions();

  const threat = useMemo(() => computeFraudMetrics(txs ?? []).threat, [txs]);
  const t = THREAT_STYLE[threat];
  const openAdd = useCallback(() => setAddOpen(true), []);
  const closeChat = useCallback(() => setChatOpen(false), []);
  const toggleDock = useCallback(() => setDocked((d) => !d), []);

  // keyboard shortcuts (ignored while typing): N = new transaction, A = advisor
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.metaKey || e.ctrlKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable) return;
      if (e.key === "n") { e.preventDefault(); setAddOpen(true); }
      if (e.key === "a") { e.preventDefault(); setChatOpen((o) => !o); }
    };
    window.addEventListener("keydown", on);
    return () => window.removeEventListener("keydown", on);
  }, []);

  const title = NAV.find((n) => n.id === route)?.label ?? "Command Center";

  return (
    <div className="flex min-h-screen">
      {/* global threat pulse: sweeps across the top, recoloured by the current threat level */}
      <div aria-hidden className="threat-bar fixed inset-x-0 top-0 z-[60] h-[2px]"
        style={{ backgroundImage: `linear-gradient(90deg, transparent, ${t.hex}, transparent)`, boxShadow: threat === "clear" ? undefined : `0 0 14px ${t.hex}` }} />
      <Sidebar route={route} onNavigate={go} />
      <div className={`flex min-w-0 flex-1 flex-col transition-[padding] duration-300 ${chatOpen && docked ? "lg:pr-[440px]" : ""}`}>
        <TopBar title={title} user={user} heartbeat={heartbeat} threat={threat} chatOpen={chatOpen} onToggleChat={() => setChatOpen((o) => !o)} onAdd={openAdd} onLogout={() => void logout()} />
        <main className="mx-auto w-full max-w-[1400px] flex-1 p-4 pb-28 md:p-6 md:pb-10">
          <AnimatePresence mode="wait" initial={false}>
            <motion.div key={route} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.18 }}>
              {route === "dashboard" && <Dashboard onAdd={openAdd} goTo={go} />}
              {route === "transactions" && <TransactionsView />}
              {route === "budgets" && <BudgetView />}
              {route === "insights" && <InsightsView />}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
      <AddTransactionPanel open={addOpen} onClose={() => setAddOpen(false)} />
      <AIChatDrawer open={chatOpen} docked={docked} onClose={closeChat} onToggleDock={toggleDock} />
    </div>
  );
}

export default function App() {
  const { state } = useAuth();
  if (state.status === "loading") {
    return <div className="grid min-h-screen place-items-center"><motion.div animate={{ opacity: [0.4, 1, 0.4] }} transition={{ duration: 1.6, repeat: Infinity }}><Logo /></motion.div></div>;
  }
  if (state.status === "anon") return <AuthScreen />;
  return <Shell user={state.user} />;
}
