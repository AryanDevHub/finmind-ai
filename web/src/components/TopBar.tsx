import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { LogOut, Plus, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import type { Heartbeat } from "@/hooks/useHeartbeat";
import { spring } from "@/lib/motion";
import { THREAT_STYLE } from "@/lib/risk";
import type { ThreatLevel, User } from "@/types";

interface Props {
  title: string;
  user: User;
  heartbeat: Heartbeat;
  threat: ThreatLevel;
  chatOpen: boolean;
  onToggleChat: () => void;
  onAdd: () => void;
  onLogout: () => void;
}

/** Status bar: live API heartbeat, session threat pulse, advisor toggle, add button and the user menu. */
export function TopBar({ title, user, heartbeat, threat, chatOpen, onToggleChat, onAdd, onLogout }: Props) {
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const t = THREAT_STYLE[threat];
  const up = heartbeat.status === "up";

  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setMenu(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menu]);

  return (
    <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-white/[0.06] bg-void/70 px-4 py-3 backdrop-blur-xl md:px-6">
      <h1 className="min-w-0 flex-1 truncate text-lg font-bold tracking-tight md:text-xl">{title}</h1>

      <div className="hidden items-center gap-2 sm:flex">
        <span title={up ? "API reachable" : heartbeat.status === "checking" ? "Checking API…" : "API unreachable"} className="flex items-center gap-2 rounded-full border border-white/[0.08] bg-card/70 px-3 py-1.5 text-xs">
          <span className="relative flex h-2 w-2">
            {up && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-gain opacity-60" />}
            <span className={clsx("relative inline-flex h-2 w-2 rounded-full", up ? "bg-gain" : heartbeat.status === "checking" ? "bg-warn" : "bg-danger")} />
          </span>
          <span className="text-ink-2">{up ? "Live" : heartbeat.status === "checking" ? "Connecting" : "Offline"}</span>
          {up && heartbeat.latencyMs !== null && <span className="num text-ink-4">{heartbeat.latencyMs}ms</span>}
        </span>
        <span title={t.description} className="flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold" style={{ borderColor: `${t.hex}44`, background: `${t.hex}12`, color: t.hex }}>
          <span className="relative flex h-2 w-2">
            {threat !== "clear" && <span className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-70" style={{ background: t.hex }} />}
            <span className="relative inline-flex h-2 w-2 rounded-full" style={{ background: t.hex }} />
          </span>
          {t.label}
        </span>
      </div>

      <motion.button whileTap={{ scale: 0.97 }} transition={spring} onClick={onToggleChat} aria-pressed={chatOpen}
        className={clsx("btn-ghost !px-3 md:!px-4", chatOpen && "!border-signal/40 !bg-signal/10 !text-signal")}>
        <Sparkles className="h-4 w-4" /><span className="hidden md:inline">AI Advisor</span>
      </motion.button>
      <motion.button whileTap={{ scale: 0.97 }} transition={spring} onClick={onAdd} className="btn-primary !px-3 md:!px-4"><Plus className="h-4 w-4" /><span className="hidden md:inline">Add transaction</span></motion.button>

      <div ref={ref} className="relative">
        <button onClick={() => setMenu((m) => !m)} aria-haspopup="menu" aria-expanded={menu} aria-label="Account menu"
          className="grid h-9 w-9 place-items-center rounded-full bg-gradient-to-br from-signal to-indigo-500 text-sm font-bold text-void">{user.username.slice(0, 1).toUpperCase()}</button>
        <AnimatePresence>
          {menu && (
            <motion.div role="menu" initial={{ opacity: 0, y: -6, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: -6, scale: 0.97 }} transition={spring}
              className="glass-elevated absolute right-0 mt-2 w-60 p-2">
              <div className="px-3 py-2"><p className="truncate text-sm font-semibold">{user.username}</p><p className="truncate text-xs text-ink-3">{user.email}</p></div>
              <button role="menuitem" onClick={onLogout} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-white/5 hover:text-danger"><LogOut className="h-4 w-4" /> Log out</button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  );
}
