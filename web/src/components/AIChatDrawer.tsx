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
  "Find my recurring charges and total them",
];

let seq = 0;
const uid = () => `m${Date.now()}-${seq++}`;

/** **bold** → <strong>; everything else stays plain text. */
function inline(text: string): ReactNode[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .map((p, i) =>
      p.startsWith("**") && p.endsWith("**") ? (
        <strong key={i} className="font-semibold text-ink-1">
          {p.slice(2, -2)}
        </strong>
      ) : (
        <span key={i}>{p}</span>
      )
    );
}

function Thinking() {
  return (
    <div className="flex items-center gap-1.5 px-1 py-2" role="status" aria-label="Advisor is thinking">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-brand"
          animate={{ opacity: [0.25, 1, 0.25], scale: [0.8, 1.2, 0.8] }}
          transition={{ duration: 1.1, repeat: Infinity, delay: i * 0.18 }}
        />
      ))}
      <span className="ml-2 text-xs text-ink-3">Analyzing financial records…</span>
    </div>
  );
}

function AssistantMessage({ msg, onAnimated }: { msg: ChatMessage; onAnimated: (id: string) => void }) {
  const steps = msg.steps ?? [];
  const reduce = useReducedMotion();
  const [revealed, setRevealed] = useState(msg.animate && !reduce ? 0 : steps.length);

  useEffect(() => {
    if (!msg.animate || revealed >= steps.length) return;
    const t = setTimeout(() => setRevealed((r) => r + 1), 500);
    return () => clearTimeout(t);
  }, [msg.animate, revealed, steps.length]);

  const ready = revealed >= steps.length;
  const { shown, done } = useTypewriter(msg.content, !!msg.animate && ready);
  useEffect(() => {
    if (msg.animate && ready && done) onAnimated(msg.id);
  }, [msg.animate, ready, done, msg.id, onAnimated]);

  return (
    <div className="flex gap-2.5">
      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-brand">
        <Sparkles className="h-3 w-3" />
      </span>
      <div className="min-w-0 flex-1 space-y-2">
        {steps.slice(0, Math.min(revealed + 1, steps.length)).map((s, i) => (
          <ToolCallCard key={i} step={s} running={i === revealed} />
        ))}
        {ready && (
          <div
            className={clsx(
              "whitespace-pre-wrap rounded-xl rounded-tl-sm border px-3.5 py-2.5 text-xs leading-relaxed",
              msg.error
                ? "border-danger/30 bg-danger/10 text-danger"
                : "border-border bg-surface text-ink-2"
            )}
          >
            {inline(shown)}
            {!done && <span aria-hidden className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] bg-brand animate-pulse" />}
          </div>
        )}
      </div>
    </div>
  );
}

interface Props {
  open: boolean;
  docked: boolean;
  onClose: () => void;
  onToggleDock: () => void;
}

/** Slide-out AI Financial Copilot drawer. */
export function AIChatDrawer({ open, docked, onClose, onToggleDock }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scroller = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const stick = useRef(true);

  useEffect(() => {
    const el = inner.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      if (stick.current) scroller.current?.scrollTo({ top: scroller.current.scrollHeight, behavior: "smooth" });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, [open]);

  useEffect(() => {
    if (open) setTimeout(() => area.current?.focus(), 200);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const esc = (e: globalThis.KeyboardEvent) => e.key === "Escape" && !docked && onClose();
    window.addEventListener("keydown", esc);
    return () => window.removeEventListener("keydown", esc);
  }, [open, docked, onClose]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || sending) return;
    const history = messages
      .filter((m) => !m.pending && !m.error)
      .slice(-20)
      .map((m) => ({ role: m.role, content: m.content }));
    const pendingId = uid();
    stick.current = true;
    setMessages((ms) => [
      ...ms,
      { id: uid(), role: "user", content: q },
      { id: pendingId, role: "assistant", content: "", pending: true },
    ]);
    setInput("");
    setSending(true);

    try {
      const res = await api<ChatResponse>("/chat", {
        method: "POST",
        json: { message: q, chat_history: history },
        timeoutMs: 60_000,
      });
      setMessages((ms) =>
        ms.map((m) =>
          m.id === pendingId
            ? { id: pendingId, role: "assistant", content: res.reply, steps: res.tool_trace, animate: true }
            : m
        )
      );
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.status === 503
            ? "The AI advisor is not configured (GROQ_API_KEY missing)."
            : e.status === 429
            ? "Rate limit exceeded. Please wait a moment."
            : e.detail
          : "Unexpected error communicating with AI advisor.";
      setMessages((ms) =>
        ms.map((m) => (m.id === pendingId ? { id: pendingId, role: "assistant", content: msg, error: true } : m))
      );
    } finally {
      setSending(false);
    }
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send(input);
    }
  };

  const markAnimated = (id: string) =>
    setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, animate: false } : m)));

  return (
    <AnimatePresence>
      {open && (
        <>
          {!docked && (
            <motion.div
              key="scrim"
              className="fixed inset-0 z-40 bg-void/70 backdrop-blur-sm lg:hidden"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={onClose}
            />
          )}

          <motion.aside
            key="drawer"
            role="complementary"
            aria-label="AI financial advisor"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={spring}
            className="fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-border bg-[#0B0F17] shadow-modal sm:w-[420px]"
          >
            {/* Header */}
            <header className="flex h-14 items-center gap-3 border-b border-border px-4">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-border bg-surface text-brand">
                <Sparkles className="h-3.5 w-3.5" />
              </span>
              <div className="min-w-0 flex-1">
                <h2 className="text-xs font-bold text-ink-1">AI Advisor</h2>
                <p className="truncate text-[10px] text-ink-3">Llama 3.3 70B · Sandboxed SQL Analytics</p>
              </div>

              {messages.length > 0 && (
                <button
                  onClick={() => setMessages([])}
                  aria-label="Clear chat"
                  className="rounded-md p-1.5 text-ink-3 hover:bg-surface hover:text-ink-1"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              )}
              <button
                onClick={onToggleDock}
                aria-label={docked ? "Undock" : "Dock beside content"}
                className="hidden rounded-md p-1.5 text-ink-3 hover:bg-surface hover:text-ink-1 lg:block"
              >
                {docked ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}
              </button>
              <button
                onClick={onClose}
                aria-label="Close"
                className="rounded-md p-1.5 text-ink-3 hover:bg-surface hover:text-ink-1"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </header>

            {/* Messages Thread */}
            <div
              ref={scroller}
              onScroll={(e) => {
                const el = e.currentTarget;
                stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
              }}
              className="flex-1 overflow-y-auto px-4 py-4"
            >
              <div ref={inner} className="space-y-3.5">
                {messages.length === 0 && (
                  <div className="pt-8 text-center">
                    <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-surface text-brand">
                      <Sparkles className="h-5 w-5" />
                    </div>
                    <p className="text-xs font-bold text-ink-1">Financial Intelligence Copilot</p>
                    <p className="mx-auto mt-1 max-w-[260px] text-[11px] leading-relaxed text-ink-3">
                      Ask about your cashflow, recurring bills, or anomalies. Every SQL step is rendered transparently.
                    </p>
                  </div>
                )}

                {messages.map((m) =>
                  m.role === "user" ? (
                    <motion.div
                      key={m.id}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="flex justify-end"
                    >
                      <p className="max-w-[85%] whitespace-pre-wrap break-words rounded-xl rounded-tr-sm border border-border-strong bg-[#141C2B] px-3 py-2 text-xs text-ink-1">
                        {m.content}
                      </p>
                    </motion.div>
                  ) : m.pending ? (
                    <div key={m.id} className="flex gap-2">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-border bg-surface text-brand">
                        <Sparkles className="h-3 w-3" />
                      </span>
                      <Thinking />
                    </div>
                  ) : (
                    <AssistantMessage key={m.id} msg={m} onAnimated={markAnimated} />
                  )
                )}
              </div>
            </div>

            {/* Footer Input */}
            <footer className="border-t border-border p-3">
              {messages.length === 0 && (
                <div className="mb-2 flex flex-wrap gap-1">
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      onClick={() => void send(s)}
                      className="rounded border border-border bg-surface/50 px-2 py-1 text-[11px] text-ink-3 transition-colors hover:border-brand/40 hover:text-ink-1"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              )}

              <div className="flex items-end gap-2 rounded-lg border border-border bg-[#0C121D] p-1.5 focus-within:border-brand/70">
                <textarea
                  ref={area}
                  value={input}
                  rows={1}
                  maxLength={2000}
                  onChange={(e) => {
                    setInput(e.target.value);
                    e.currentTarget.style.height = "auto";
                    e.currentTarget.style.height = `${Math.min(e.currentTarget.scrollHeight, 100)}px`;
                  }}
                  onKeyDown={onKey}
                  placeholder="Ask a question about your finances..."
                  aria-label="Message the AI advisor"
                  className="max-h-[100px] min-h-[32px] flex-1 resize-none bg-transparent px-2 py-1 text-xs text-ink-1 placeholder:text-ink-4 focus:outline-none"
                />
                <button
                  onClick={() => void send(input)}
                  disabled={sending || !input.trim()}
                  aria-label="Send message"
                  className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald text-white transition-opacity hover:bg-emerald-hover disabled:opacity-30"
                >
                  <ArrowUp className="h-3.5 w-3.5" />
                </button>
              </div>
            </footer>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
