export function Logo({ collapsed = false }: { collapsed?: boolean }) {
  return (
    <div className="flex items-center gap-2.5">
      <span className="grid h-9 w-9 place-items-center rounded-xl bg-card" style={{ boxShadow: "0 0 0 1px rgba(34,211,238,.35), 0 0 24px -4px rgba(34,211,238,.5)" }}>
        <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="#22D3EE" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 16l5-6 4 4 7-8" /></svg>
      </span>
      {!collapsed && <span className="text-[17px] font-extrabold tracking-tight">FinMind <span className="text-signal">AI</span></span>}
    </div>
  );
}
