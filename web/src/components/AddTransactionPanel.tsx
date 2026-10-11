import clsx from "clsx";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Loader2, ShieldCheck, X } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { useDebounced } from "@/hooks/useDebounced";
import { ApiError } from "@/lib/api";
import { CATEGORY_META } from "@/lib/categories";
import { formatINR } from "@/lib/format";
import { spring } from "@/lib/motion";
import { useAddTransaction, usePreview } from "@/lib/queries";
import { CATEGORIES, type AddTransactionResult, type Category, type TransactionType } from "@/types";
import { FraudGauge } from "./FraudGauge";
import { ShapBars } from "./ShapBars";
import { useToast } from "./ui/Toast";

const PRESETS = [100, 500, 1000, 5000];

/**
 * Glass modal (bottom sheet on phones) for adding a transaction. While you type, a debounced, read-only
 * request asks the model what it WOULD say (nothing is stored); on submit you get the real, recorded verdict.
 */
export function AddTransactionPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const add = useAddTransaction();
  const [type, setType] = useState<TransactionType>("expense");
  const [amountText, setAmountText] = useState("");
  const [category, setCategory] = useState<Category>("Food");
  const [description, setDescription] = useState("");
  const [merchant, setMerchant] = useState("");
  const [result, setResult] = useState<AddTransactionResult | null>(null);
  const amountRef = useRef<HTMLInputElement>(null);

  const amount = Number(amountText.replace(/,/g, ""));
  const validAmount = Number.isFinite(amount) && amount > 0;
  const debouncedAmount = useDebounced(validAmount ? amount : 0, 350);
  const preview = usePreview({ amount: debouncedAmount, category, transaction_type: type, description }, open && !result);

  // reset every time the panel opens; focus the amount; close on Escape
  useEffect(() => {
    if (!open) return;
    setType("expense"); setAmountText(""); setCategory("Food"); setDescription(""); setMerchant(""); setResult(null); add.reset();
    const t = setTimeout(() => amountRef.current?.focus(), 120);
    const esc = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => { clearTimeout(t); window.removeEventListener("keydown", esc); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (!validAmount || !description.trim() || add.isPending) return;
    add.mutate(
      { description: description.trim(), amount, category, transaction_type: type, ...(merchant.trim() ? { merchant: merchant.trim() } : {}) },
      {
        onSuccess: (res) => {
          setResult(res);
          if (res.is_flagged) toast.push({ tone: "error", title: `Flagged ${res.risk_level}`, body: `${description.trim()} scored ${res.fraud_score.toFixed(1)}% fraud risk.` });
          else toast.push({ tone: "success", title: "Transaction added", body: type === "expense" ? `Risk ${res.risk_level} · ${res.fraud_score.toFixed(1)}%` : formatINR(amount) });
        },
      },
    );
  };

  const p = preview.data;
  const errMsg = add.error instanceof ApiError ? add.error.detail : add.error ? "Something went wrong." : null;

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center md:items-center md:p-6">
          <motion.div className="absolute inset-0 bg-void/70 backdrop-blur-sm" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />
          <motion.div
            role="dialog" aria-modal="true" aria-label="Add transaction"
            initial={{ opacity: 0, y: 60, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 40, scale: 0.98 }} transition={spring}
            className="glass-elevated relative max-h-[92vh] w-full overflow-y-auto rounded-b-none md:max-w-3xl md:rounded-b-2xl"
            onKeyDown={(e) => (e.metaKey || e.ctrlKey) && e.key === "Enter" && submit()}
          >
            <div className="flex items-center justify-between border-b border-white/[0.07] px-5 py-4">
              <div>
                <h2 className="text-base font-bold">Add transaction</h2>
                <p className="text-xs text-ink-3">Scored in real time · <kbd className="rounded bg-white/10 px-1 text-[10px]">Ctrl</kbd>+<kbd className="rounded bg-white/10 px-1 text-[10px]">Enter</kbd> to save</p>
              </div>
              <button onClick={onClose} aria-label="Close" className="rounded-lg p-2 text-ink-3 hover:bg-white/5 hover:text-ink-1"><X className="h-5 w-5" /></button>
            </div>

            <AnimatePresence mode="wait" initial={false}>
              {result ? (
                <motion.div key="result" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="p-5 sm:p-7">
                  <div className="mb-5 flex items-center gap-2 text-gain"><CheckCircle2 className="h-5 w-5" /><span className="font-semibold">Saved.</span></div>
                  {type === "expense" ? (
                    <div className="grid items-center gap-6 md:grid-cols-[230px_1fr]">
                      <div className="flex justify-center"><FraudGauge value={result.fraud_score} level={result.risk_level} /></div>
                      <div><p className="label mb-3">Why this score</p><ShapBars factors={result.risk_factors} />
                        {result.degraded && <p className="mt-3 text-xs text-warn">Velocity data was unavailable, so this score used neutral defaults and may understate risk.</p>}
                      </div>
                    </div>
                  ) : <p className="text-sm text-ink-2">Income is recorded but not fraud-scored.</p>}
                  <div className="mt-6 flex justify-end gap-3">
                    <button className="btn-ghost" onClick={() => { setResult(null); setAmountText(""); setDescription(""); setMerchant(""); add.reset(); amountRef.current?.focus(); }}>Add another</button>
                    <button className="btn-primary" onClick={onClose}>Done</button>
                  </div>
                </motion.div>
              ) : (
                <motion.form key="form" onSubmit={submit} exit={{ opacity: 0 }} className="grid gap-6 p-5 sm:p-7 md:grid-cols-[1fr_300px]">
                  <div className="space-y-5">
                    <div role="radiogroup" aria-label="Type" className="relative grid grid-cols-2 rounded-xl border border-white/10 bg-void/50 p-1">
                      {(["expense", "income"] as const).map((t) => (
                        <button key={t} type="button" role="radio" aria-checked={type === t} onClick={() => setType(t)}
                          className={clsx("rounded-lg py-2 text-sm font-semibold capitalize transition-colors duration-200",
                            type === t ? (t === "expense" ? "bg-signal text-void" : "bg-gain text-void") : "text-ink-2 hover:text-ink-1")}>
                          {t}
                        </button>
                      ))}
                    </div>

                    <div>
                      <label htmlFor="amount" className="label">Amount</label>
                      <div className="relative mt-1.5">
                        <span className="num pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-xl text-ink-3">₹</span>
                        <input id="amount" ref={amountRef} inputMode="decimal" autoComplete="off" placeholder="0" value={amountText}
                          onChange={(e) => setAmountText(e.target.value.replace(/[^\d.,]/g, ""))} className="field num !py-3.5 pl-10 text-2xl font-semibold" />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {PRESETS.map((n) => (
                          <button key={n} type="button" onClick={() => setAmountText(String(n))} className="num rounded-lg border border-white/10 px-2.5 py-1 text-xs text-ink-2 transition-colors hover:border-signal/40 hover:text-ink-1">{formatINR(n)}</button>
                        ))}
                      </div>
                    </div>

                    <div>
                      <p className="label">Category</p>
                      <div className="mt-1.5 grid grid-cols-5 gap-2" role="radiogroup" aria-label="Category">
                        {CATEGORIES.map((c) => {
                          const { icon: Icon, color } = CATEGORY_META[c];
                          const on = category === c;
                          return (
                            <button key={c} type="button" role="radio" aria-checked={on} onClick={() => setCategory(c)} title={c}
                              className={clsx("flex flex-col items-center gap-1 rounded-xl border px-1 py-2 text-[10px] font-medium transition-all", on ? "border-transparent text-ink-1" : "border-white/[0.07] text-ink-3 hover:border-white/20")}
                              style={on ? { background: `${color}22`, boxShadow: `0 0 0 1px ${color}88, 0 0 18px -6px ${color}` } : undefined}>
                              <Icon className="h-4 w-4" style={{ color: on ? color : undefined }} /><span className="truncate">{c}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <label htmlFor="desc" className="label">Description</label>
                        <input id="desc" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={200} placeholder="e.g. Swiggy dinner" className="field mt-1.5" />
                      </div>
                      <div>
                        <label htmlFor="merchant" className="label">Merchant <span className="normal-case text-ink-4">(optional)</span></label>
                        <input id="merchant" value={merchant} onChange={(e) => setMerchant(e.target.value)} maxLength={120} className="field mt-1.5" />
                      </div>
                    </div>

                    {errMsg && <p role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{errMsg}</p>}
                    <motion.button type="submit" whileTap={{ scale: 0.98 }} transition={spring} disabled={!validAmount || !description.trim() || add.isPending} className="btn-primary w-full !py-3">
                      {add.isPending ? <><Loader2 className="h-4 w-4 animate-spin" /> Scoring…</> : "Add transaction"}
                    </motion.button>
                  </div>

                  {/* live, read-only risk estimate */}
                  <aside aria-live="polite" className="rounded-2xl border border-white/[0.07] bg-void/40 p-4">
                    <p className="label flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-signal" /> Live risk estimate</p>
                    {type === "income" ? (
                      <p className="mt-6 text-sm text-ink-3">Income isn't fraud-scored.</p>
                    ) : !validAmount ? (
                      <p className="mt-6 text-sm text-ink-3">Enter an amount to see how the model rates it.</p>
                    ) : !p ? (
                      <div className="mt-6 flex justify-center"><Loader2 className="h-5 w-5 animate-spin text-ink-3" /></div>
                    ) : (
                      <div className={clsx("mt-3 flex flex-col items-center gap-4 transition-opacity", preview.isFetching && "opacity-60")}>
                        <FraudGauge value={p.fraud_score} level={p.risk_level} size={200} />
                        <div className="w-full"><ShapBars factors={p.risk_factors} compact /></div>
                        <p className="text-[11px] leading-relaxed text-ink-4">Estimate only. Nothing is saved yet, and the final score also reflects the exact time of submission.</p>
                      </div>
                    )}
                  </aside>
                </motion.form>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
