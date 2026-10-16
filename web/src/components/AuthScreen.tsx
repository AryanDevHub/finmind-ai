import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { Loader2, LockKeyhole, ShieldCheck, Zap } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { spring } from "@/lib/motion";
import type { RiskLevel } from "@/types";
import { FraudGauge } from "./FraudGauge";
import { Logo } from "./Logo";

const DEMO: { v: number; level: RiskLevel; label: string }[] = [
  { v: 6, level: "LOW", label: "₹450 · Food & Groceries · 1:20 PM" },
  { v: 41, level: "MEDIUM", label: "₹8,999 · Electronics · 9:05 PM" },
  { v: 93, level: "CRITICAL", label: "9 rapid attempts in 40s · Card Testing" },
];

/** Precision Institutional Auth Screen */
export function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [demo, setDemo] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setDemo((d) => (d + 1) % DEMO.length), 3200);
    return () => clearInterval(id);
  }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") {
        if (password.length < 8) throw new ApiError(422, "Password must be at least 8 characters.");
        await register(username.trim(), email.trim(), password);
      }
      await login(username.trim(), password);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.status === 401
            ? "Incorrect username or password."
            : err.status === 429
            ? "Too many failed attempts. Try again in a few minutes."
            : err.status === 409
            ? "That username or email is already registered."
            : err.detail
          : "An unexpected error occurred."
      );
    } finally {
      setBusy(false);
    }
  };

  const d = DEMO[demo]!;

  return (
    <div className="relative grid min-h-screen lg:grid-cols-[1.1fr_1fr] bg-[#080C14]">
      {/* Left Column: Institutional Value & Live Model Demo */}
      <section className="relative hidden flex-col justify-between border-r border-border p-12 lg:flex bg-[#0A0E18]">
        <div>
          <Logo />
          <div className="mt-2 inline-flex items-center gap-1.5 rounded border border-emerald/20 bg-emerald/5 px-2 py-0.5 text-[11px] font-semibold text-emerald">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald" />
            Institutional Financial Telemetry
          </div>
        </div>

        <div className="my-auto py-8">
          <h1 className="max-w-md text-3xl font-extrabold leading-tight tracking-tight text-ink-1">
            Real-time fraud defense & financial intelligence.
          </h1>
          <p className="mt-3 max-w-md text-xs leading-relaxed text-ink-3">
            Every transaction is analyzed in real time with LightGBM ML models, TreeSHAP explainability, and RBI Account Aggregator streaming.
          </p>

          <div className="glass mt-8 inline-flex max-w-sm flex-col items-center gap-3 p-5">
            <AnimatePresence mode="wait">
              <motion.div
                key={demo}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="flex flex-col items-center gap-2"
              >
                <FraudGauge value={d.v} level={d.level} size={190} />
                <p className="num text-xs font-semibold text-ink-2">{d.label}</p>
              </motion.div>
            </AnimatePresence>
          </div>
        </div>

        <ul className="flex flex-wrap gap-5 border-t border-border pt-4 text-[11px] text-ink-3">
          <li className="flex items-center gap-1.5">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald" />
            <span>RFC 6749 Token Rotation</span>
          </li>
          <li className="flex items-center gap-1.5">
            <LockKeyhole className="h-3.5 w-3.5 text-emerald" />
            <span>AES-256-GCM Encryption</span>
          </li>
          <li className="flex items-center gap-1.5">
            <Zap className="h-3.5 w-3.5 text-brand" />
            <span>Sandboxed SQL Sandbox</span>
          </li>
        </ul>
      </section>

      {/* Right Column: Authentication Card */}
      <section className="flex items-center justify-center p-6 sm:p-12">
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={spring}
          className="glass-elevated w-full max-w-[380px] p-6 sm:p-7"
        >
          <div className="mb-6 lg:hidden">
            <Logo />
          </div>

          {/* Segmented Mode Selector */}
          <div role="tablist" className="mb-6 grid grid-cols-2 rounded-lg border border-border bg-[#0C121D] p-1">
            {(["login", "register"] as const).map((m) => {
              const active = mode === m;
              return (
                <button
                  key={m}
                  role="tab"
                  aria-selected={active}
                  onClick={() => {
                    setMode(m);
                    setError(null);
                  }}
                  className={clsx(
                    "rounded-md py-1.5 text-xs font-semibold transition-all duration-150",
                    active
                      ? "border border-border-strong bg-surface text-ink-1 shadow-sm"
                      : "text-ink-3 hover:text-ink-1"
                  )}
                >
                  {m === "login" ? "Sign In" : "Create Account"}
                </button>
              );
            })}
          </div>

          <form onSubmit={(e) => void submit(e)} className="space-y-3.5" noValidate>
            <div>
              <label htmlFor="u" className="label block mb-1.5">
                {mode === "login" ? "Username or Email" : "Username"}
              </label>
              <input
                id="u"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="field"
                placeholder="Enter username"
                required
              />
            </div>

            <AnimatePresence initial={false}>
              {mode === "register" && (
                <motion.div
                  key="email"
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="overflow-hidden"
                >
                  <label htmlFor="e" className="label block mb-1.5">
                    Email Address
                  </label>
                  <input
                    id="e"
                    type="email"
                    autoComplete="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="field"
                    placeholder="name@example.com"
                    required
                  />
                </motion.div>
              )}
            </AnimatePresence>

            <div>
              <label htmlFor="p" className="label block mb-1.5">
                Password
              </label>
              <input
                id="p"
                type="password"
                autoComplete={mode === "login" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field"
                placeholder="••••••••"
                required
              />
              {mode === "register" && <p className="mt-1 text-[11px] text-ink-4">Minimum 8 characters.</p>}
            </div>

            <AnimatePresence>
              {error && (
                <motion.p
                  role="alert"
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-xs text-danger"
                >
                  {error}
                </motion.p>
              )}
            </AnimatePresence>

            <button
              type="submit"
              disabled={busy || !username || !password}
              className="btn-primary w-full py-2.5 mt-2"
            >
              {busy ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <LockKeyhole className="h-4 w-4" />
              )}
              <span>{mode === "login" ? "Sign In" : "Create Account"}</span>
            </button>
          </form>

          <p className="mt-5 text-center text-[10px] leading-relaxed text-ink-4">
            Encrypted with rotating HttpOnly sessions. Single-device token families.
          </p>
        </motion.div>
      </section>
    </div>
  );
}
