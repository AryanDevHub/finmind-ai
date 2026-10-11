import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

type Tone = "success" | "warn" | "error" | "info";
interface ToastItem { id: number; tone: Tone; title: string; body?: string }
interface ToastApi { push: (t: Omit<ToastItem, "id">) => void }

const Ctx = createContext<ToastApi | null>(null);
const ICON = { success: CheckCircle2, warn: AlertTriangle, error: XCircle, info: Info } as const;
const COLOR: Record<Tone, string> = { success: "text-gain", warn: "text-warn", error: "text-danger", info: "text-signal" };

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const push = useCallback((t: Omit<ToastItem, "id">) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs.slice(-3), { ...t, id }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), 5000);
  }, []);
  const api = useMemo(() => ({ push }), [push]);

  return (
    <Ctx.Provider value={api}>
      {children}
      <div aria-live="polite" className="pointer-events-none fixed bottom-20 right-4 z-[100] flex w-[min(92vw,360px)] flex-col gap-2 md:bottom-6 md:right-6">
        <AnimatePresence initial={false}>
          {items.map((t) => {
            const Icon = ICON[t.tone];
            return (
              <motion.div
                key={t.id} layout role="status"
                initial={{ opacity: 0, x: 40, scale: 0.96 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: 40, scale: 0.96 }}
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
                className="glass-elevated pointer-events-auto flex gap-3 p-3.5"
              >
                <Icon className={clsx("mt-0.5 h-5 w-5 shrink-0", COLOR[t.tone])} />
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{t.title}</p>
                  {t.body && <p className="mt-0.5 text-[13px] text-ink-2">{t.body}</p>}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): ToastApi {
  const c = useContext(Ctx);
  if (!c) throw new Error("useToast must be used inside <ToastProvider>");
  return c;
}
