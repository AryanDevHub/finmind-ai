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

/** Precision Top Navigation Bar with live telemetry, AI Copilot trigger, and user controls. */
export function TopBar({ title, user, heartbeat, threat, chatOpen, onToggleChat, onAdd, onLogout }: Props) {
  const [menu, setMenu] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const t = THREAT_STYLE[threat];
  const up = heartbeat.status === "up";

  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setMenu(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [menu]);

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-border bg-[#090D15]/90 px-4 backdrop-blur-md md:px-6">
      <div className="flex flex-1 items-center gap-3 min-w-0">
        <h1 className="truncate text-base font-bold tracking-tight text-ink-1 md:text-lg">{title}</h1>
      </div>

      {/* Telemetry Pills */}
      <div className="hidden items-center gap-2 sm:flex">
        {/* Heartbeat Status */}
        <div
          title={up ? "API connected" : "Connecting..."}
          className="flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1 text-[11px] font-medium"
        >
          <span className="relative flex h-1.5 w-1.5">
            {up && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald opacity-60" />}
            <span className={clsx("relative inline-flex h-1.5 w-1.5 rounded-full", up ? "bg-emerald" : "bg-warn")} />
          </span>
          <span className="text-ink-2">{up ? "API Online" : "Connecting"}</span>
          {up && heartbeat.latencyMs !== null && <span className="num text-ink-4 text-[10px]">{heartbeat.latencyMs}ms</span>}
        </div>

        {/* Security Threat Level */}
        <div
          title={t.description}
          className="flex items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1 text-[11px] font-semibold"
          style={{ borderColor: `${t.hex}33`, color: t.hex }}
        >
          <span className="h-1.5 w-1.5 rounded-full" style={{ background: t.hex }} />
          <span>{t.label}</span>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleChat}
          aria-pressed={chatOpen}
          className={clsx(
            "btn-secondary text-xs",
            chatOpen && "!border-brand !bg-brand/10 !text-brand"
          )}
        >
          <Sparkles className="h-3.5 w-3.5 text-brand" />
          <span className="hidden sm:inline">AI Advisor</span>
        </button>

        <button onClick={onAdd} className="btn-primary text-xs">
          <Plus className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Add Transaction</span>
        </button>
      </div>

      {/* User Avatar Menu */}
      <div ref={ref} className="relative ml-1">
        <button
          onClick={() => setMenu((m) => !m)}
          aria-haspopup="menu"
          aria-expanded={menu}
          aria-label="Account menu"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-border bg-surface text-xs font-bold text-ink-1 transition-colors hover:border-border-strong hover:bg-elevated"
        >
          {user.username.slice(0, 1).toUpperCase()}
        </button>

        <AnimatePresence>
          {menu && (
            <motion.div
              role="menu"
              initial={{ opacity: 0, y: -4, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -4, scale: 0.98 }}
              transition={spring}
              className="glass-elevated absolute right-0 mt-2 w-56 p-1.5"
            >
              <div className="border-b border-border px-2.5 py-2">
                <p className="truncate text-xs font-semibold text-ink-1">{user.username}</p>
                <p className="truncate text-[11px] text-ink-3">{user.email}</p>
              </div>
              <div className="pt-1">
                <button
                  role="menuitem"
                  onClick={onLogout}
                  className="flex w-full items-center gap-2 rounded-md px-2.5 py-1.5 text-xs text-ink-2 transition-colors hover:bg-danger/10 hover:text-danger"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>Log out</span>
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  );
}
