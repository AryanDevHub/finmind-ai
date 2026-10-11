import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, LockKeyhole, ShieldCheck, Sparkles, Zap } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { spring } from "@/lib/motion";
import type { RiskLevel } from "@/types";
import { FraudGauge } from "./FraudGauge";
import { Logo } from "./Logo";

const DEMO: { v: number; level: RiskLevel; label: string }[] = [
  { v: 6, level: "LOW", label: "₹450 · Food · 1:20 PM" },
  { v: 41, level: "MEDIUM", label: "₹8,999 · Shopping · 9:05 PM" },
  { v: 93, level: "CRITICAL", label: "9 swipes in 40 s · card testing" },
];

/** Split-screen login/register with a live gauge demo so the product explains itself. */
export function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState(0);

  useEffect(() => { const id = setInterval(() => setDemo((d) => (d + 1) % DEMO.length), 3200); return () => clearInterval(id); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      if (mode === "register") {
        if (password.length < 8) throw new ApiError(422, "Password must be at least 8 characters.");
        await register(username.trim(), email.trim(), password);
      }
      await login(username.trim(), password);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 401 ? "Incorrect username or password."
            : err.status === 429 ? "Too many failed attempts. Try again in a few minutes."
            : err.status === 409 ? "That username or email is already registered." : err.detail
          : "Something went wrong.",
      );
    } finally { setBusy(false); }
  };

  const d = DEMO[demo]!;
  return (
    <div className="relative grid min-h-screen overflow-hidden lg:grid-cols-[1.1fr_1fr]">
      <div aria-hidden className="pointer-events-none absolute -left-40 top-1/4 h-[480px] w-[480px] animate-glow rounded-full blur-3xl" style={{ background: "radial-gradient(circle,rgba(34,211,238,.25),transparent 65%)" }} />

      <section className="relative hidden flex-col justify-between p-12 lg:flex">
        <Logo />
        <div>
          <motion.h1 initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: 0.1 }} className="max-w-md text-4xl font-extrabold leading-[1.1] tracking-tight">
            Every transaction, scored <span className="bg-gradient-to-r from-signal to-emerald-300 bg-clip-text text-transparent">before it hurts.</span>
          </motion.h1>
          <p className="mt-4 max-w-md text-ink-2">Real-time ML fraud detection with explanations, budgets that show their pace, and an advisor that shows its SQL.</p>
          <div className="glass-static mt-10 inline-flex max-w-sm flex-col items-center gap-3 p-6">
            <AnimatePresence mode="wait">
              <motion.div key={demo} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="flex flex-col items-center gap-3">
                <FraudGauge value={d.v} level={d.level} size={210} />
                <p className="num text-xs text-ink-3">{d.label}</p>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
        <ul className="flex gap-6 text-xs text-ink-3">
          <li className="flex items-center gap-1.5"><Zap className="h-3.5 w-3.5 text-signal" /> ONNX scoring</li>
          <li className="flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-signal" /> TreeSHAP explanations</li>
          <li className="flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5 text-signal" /> Text-to-SQL advisor</li>
        </ul>
      </section>

      <section className="relative grid place-items-center p-6">
        <motion.div initial={{ opacity: 0, y: 24, scale: 0.98 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={spring} className="glass-elevated w-full max-w-[400px] p-7">
          <div className="mb-6 lg:hidden"><Logo /></div>
          <div role="tablist" className="relative mb-6 grid grid-cols-2 rounded-xl border border-white/10 bg-void/50 p-1">
            {(["login", "register"] as const).map((m) => (
              <button key={m} role="tab" aria-selected={mode === m} onClick={() => { setMode(m); setError(null); }} className={clsx("relative rounded-lg py-2 text-sm font-semibold", mode === m ? "text-void" : "text-ink-2")}>
                {mode === m && <motion.span layoutId="auth-tab" className="absolute inset-0 rounded-lg bg-signal" transition={spring} />}
                <span className="relative">{m === "login" ? "Log in" : "Create account"}</span>
              </button>
            ))}
          </div>

          <form onSubmit={(e) => void submit(e)} className="space-y-4" noValidate>
            <div><label htmlFor="u" className="label">{mode === "login" ? "Username or email" : "Username"}</label>
              <input id="u" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} className="field mt-1.5" required /></div>
            <AnimatePresence initial={false}>
              {mode === "register" && (
                <motion.div key="email" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="overflow-hidden">
                  <label htmlFor="e" className="label">Email</label>
                  <input id="e" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} className="field mt-1.5" required />
                </motion.div>
              )}
            </AnimatePresence>
            <div><label htmlFor="p" className="label">Password</label>
              <input id="p" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} className="field mt-1.5" required />
              {mode === "register" && <p className="mt-1 text-[11px] text-ink-4">At least 8 characters.</p>}</div>
            <AnimatePresence>{error && <motion.p role="alert" initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{error}</motion.p>}</AnimatePresence>
            <motion.button type="submit" whileTap={{ scale: 0.98 }} transition={spring} disabled={busy || !username || !password} className="btn-primary w-full !py-3">
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LockKeyhole className="h-4 w-4" />}{mode === "login" ? "Log in" : "Create account"}
            </motion.button>
          </form>
          <p className="mt-5 text-center text-[11px] leading-relaxed text-ink-4">Sessions use a 15-minute access token and a rotating HttpOnly refresh cookie.</p>
        </motion.div>
      </section>
    </div>
  );
}
