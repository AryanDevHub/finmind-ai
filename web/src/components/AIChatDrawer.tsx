import clsx from "clsx";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ArrowUp, PanelRightClose, PanelRightOpen, Sparkles, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { useTypewriter } from "@/hooks/useTypewriter";
import { api, ApiError } from "@/lib/api";
import { spring } from "@/lib/motion";
import type { ChatMessage, ChatResponse } from "@/types";
import { ToolCallCard } from "./ToolCallCard";

const SUGGESTIONS = [
  "Analyze my spending velocity",
  "Any fraud risks this week?",
  "Where can I save ₹5,000?",
  "How much did I spend on Food last month?",
  "Find my gym or fitness charges and total them",
];

let seq = 0;
const uid = () => `m${Date.now()}-${seq++}`;

/** **bold** → <strong>; everything else stays plain text (the reply is never injected as HTML). */
function inline(text: string): ReactNode[] {
  return text.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith("**") && p.endsWith("**") ? <strong key={i} className="font-semibold text-ink-1">{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>));
}

function Thinking() {
  return (
    <div className="flex items-center gap-1.5 px-1 py-2" role="status" aria-label="Advisor is thinking">
      {[0, 1, 2].map((i) => (
        <motion.span key={i} className="h-1.5 w-1.5 rounded-full bg-signal" animate={{ opacity: [0.25, 1, 0.25], scale: [0.8, 1.2, 0.8] }} transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }} />
      ))}
      <span className="ml-2 text-xs text-ink-3">Querying your ledger…</span>
    </div>
  );
}

/**
 * Assistant turn. For a fresh reply it plays: tool cards appear one by one (spinner → ✓), THEN the answer is
 * typed out with a blinking cursor. Replays never happen for older messages.
 */
function AssistantMessage({ msg, onAnimated }: { msg: ChatMessage; onAnimated: (id: string) => void }) {
  const steps = msg.steps ?? [];
  const reduce = useReducedMotion();
  const [revealed, setRevealed] = useState(msg.animate && !reduce ? 0 : steps.length);

  useEffect(() => {
    if (!msg.animate || revealed >= steps.length) return;
    const t = setTimeout(() => setRevealed((r) => r + 1), 560);
    return () => clearTimeout(t);
  }, [msg.animate, revealed, steps.length]);

  const ready = revealed >= steps.length;
  const { shown, done } = useTypewriter(msg.content, !!msg.animate && ready);
  useEffect(() => { if (msg.animate && ready && done) onAnimated(msg.id); }, [msg.animate, ready, done, msg.id, onAnimated]);

  return (
    <div className="flex gap-2.5">
      <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-signal/15 text-signal"><Sparkles className="h-3.5 w-3.5" /></span>
      <div className="min-w-0 flex-1 space-y-2">
        {steps.slice(0, Math.min(revealed + 1, steps.length)).map((s, i) => <ToolCallCard key={i} step={s} running={i === revealed} />)}
        {ready && (
          <div className={clsx("whitespace-pre-wrap rounded-2xl rounded-tl-sm border px-3.5 py-2.5 text-[13.5px] leading-relaxed", msg.error ? "border-danger/30 bg-danger/10 text-danger" : "border-white/[0.08] bg-white/[0.04] text-ink-2")}>
            {inline(shown)}
            {!done && <span aria-hidden className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] animate-blink bg-signal" />}
          </div>
        )}
      </div>
    </div>
  );
}

interface Props { open: boolean; docked: boolean; onClose: () => void; onToggleDock: () => void }

/**
 * Slide-out advisor. Docked (≥ lg) it shares the screen with the dashboard; otherwise it overlays it.
 * Answers come from the hybrid agent: exact numbers via SQL, fuzzy lookups via vector search.
 */
export function AIChatDrawer({ open, docked, onClose, onToggleDock }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const stick = useRef(true);

  // keep the newest content in view while it grows (typewriter, tool cards) unless the user scrolled up
  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const ro = new ResizeObserver(() => { if (stick.current) scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" }); });
    ro.observe(el);
    return () => ro.disconnect();
  }, [open]);
  useEffect(() => { if (open) setTimeout(() => area.current?.focus(), 250); }, [open]);
  useEffect(() => {
    if (!open) return;
    const esc = (e: globalThis.KeyboardEvent) => e.key === "Escape" && !docked && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, docked, onClose]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || sending) return;
    const history = messages.filter((m) => !m.pending && !m.error).slice(-20).map((m) => ({ role: m.role, content: m.content }));
    const pendingId = uid();
    stick.current = true;
    setMessages((ms) => [...ms, { id: uid(), role: "user", content: q }, { id: pendingId, role: "assistant", content: "", pending: true }]);
    setInput(""); setSending(true);
    try {
      const res = await api<ChatResponse>("/chat", { method: "POST", json: { message: q, chat_history: history }, timeoutMs: 60_000 });
      setMessages((ms) => ms.map((m) => (m.id === pendingId ? { id: pendingId, role: "assistant", content: res.reply, steps: res.tool_trace, animate: true } : m)));
    } catch (e) {
      const msg = e instanceof ApiError
        ? e.status === 503 ? "The AI advisor isn't configured on the server (GROQ_API_KEY is missing)."
          : e.status === 429 ? "You're sending messages too quickly. Please wait a moment." : e.detail
        : "Something went wrong.";
      setMessages((ms) => ms.map((m) => (m.id === pendingId ? { id: pendingId, role: "assistant", content: msg, error: true } : m)));
    } finally { setSending(false); }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(input); } };
  const markAnimated = (id: string) => setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, animate: false } : m)));

  return (
    <AnimatePresence>
      {open && (
        <>
          {!docked && <motion.div key="scrim" className="fixed inset-0 z-40 bg-void/60 backdrop-blur-[2px] lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose} />}
          <motion.aside key="drawer" role="complementary" aria-label="AI financial advisor"
            initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={spring}
            className="glass-elevated fixed inset-y-0 right-0 z-40 flex w-full flex-col rounded-none border-y-0 border-r-0 sm:w-[440px]">
            <header className="flex items-center gap-3 border-b border-white/[0.07] px-4 py-3.5">
              <span className="grid h-9 w-9 place-items-center rounded-xl bg-signal/15 text-signal" style={{ boxShadow: "0 0 20px -4px rgba(34,211,238,.6)" }}><Sparkles className="h-[18px] w-[18px]" /></span>
              <div className="min-w-0 flex-1"><h2 className="text-sm font-bold">AI Advisor</h2><p className="truncate text-[11px] text-ink-3">SQL for exact numbers · vector search for fuzzy lookups</p></div>
              {messages.length > 0 && <button onClick={() => setMessages([])} aria-label="Clear conversation" className="rounded-lg p-2 text-ink-3 hover:bg-white/5 hover:text-ink-1"><Trash2 className="h-4 w-4" /></button>}
              <button onClick={onToggleDock} aria-label={docked ? "Undock" : "Dock beside content"} className="hidden rounded-lg p-2 text-ink-3 hover:bg-white/5 hover:text-ink-1 lg:block">{docked ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}</button>
              <button onClick={onClose} aria-label="Close advisor" className="rounded-lg p-2 text-ink-3 hover:bg-white/5 hover:text-ink-1"><X className="h-4 w-4" /></button>
            </header>

            <div ref={scroller} onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }} className="flex-1 overflow-y-auto px-4 py-4">
              <div ref={inner} className="space-y-4">
                {messages.length === 0 && (
                  <div className="pt-6 text-center">
                    <motion.div animate={{ y: [0, -5, 0] }} transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }} className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-signal/10 text-signal"><Sparkles className="h-7 w-7" /></motion.div>
                    <p className="text-sm font-semibold">Ask about your money</p>
                    <p className="mx-auto mt-1 max-w-[280px] text-xs leading-relaxed text-ink-3">I show every query I run, so you can verify each number.</p>
                  </div>
                )}
                {messages.map((m) =>
                  m.role === "user" ? (
                    <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end">
                      <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm border border-signal/25 bg-signal/10 px-3.5 py-2.5 text-[13.5px] text-ink-1">{m.content}</p>
                    </motion.div>
                  ) : m.pending ? (
                    <div key={m.id} className="flex gap-2.5"><span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-signal/15 text-signal"><Sparkles className="h-3.5 w-3.5" /></span><Thinking /></div>
                  ) : <AssistantMessage key={m.id} msg={m} onAnimated={markAnimated} />,
                )}
              </div>
            </div>

            <footer className="border-t border-white/[0.07] p-3">
              {messages.length === 0 && (
                <div className="mb-2.5 flex flex-wrap gap-1.5">
                  {SUGGESTIONS.map((s) => <button key={s} onClick={() => void send(s)} className="rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-ink-2 transition-colors hover:border-signal/40 hover:text-ink-1">{s}</button>)}
                </div>
              )}
              <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-void/60 p-2 focus-within:border-signal/50">
                <textarea ref={area} value={input} rows={1} maxLength={2000} onChange={(e) => { setInput(e.target.value); e.currentTarget.style.height = "auto"; e.currentTarget.style.height = `${Math.min(e.currentTarget.scrollHeight, 120)}px`; }}
                  onKeyDown={onKey} placeholder="Ask about spending, budgets, fraud…" aria-label="Message the AI advisor" className="max-h-[120px] min-h-[36px] flex-1 resize-none bg-transparent px-2 py-1.5 text-sm placeholder:text-ink-4 focus:outline-none focus-visible:ring-0 focus-visible:ring-offset-0" />
                <motion.button whileTap={{ scale: 0.92 }} onClick={() => void send(input)} disabled={sending || !input.trim()} aria-label="Send message"
                  className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-signal text-void transition-opacity disabled:opacity-30"><ArrowUp className="h-4 w-4" /></motion.button>
              </div>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
