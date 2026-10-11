import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AddTransactionPanel } from "@/components/AddTransactionPanel";
import { AIChatDrawer } from "@/components/AIChatDrawer";
import { Dashboard } from "@/components/Dashboard";
import { FraudGauge } from "@/components/FraudGauge";
import { ShapBars } from "@/components/ShapBars";
import { highlightSql, previewJson, ToolCallCard } from "@/components/ToolCallCard";
import { TransactionRow } from "@/components/TransactionRow";
import { ToastProvider } from "@/components/ui/Toast";
import * as apiModule from "@/lib/api";
import type { ToolStep } from "@/types";
import { FACTORS, tx } from "./factories";

// Respect reduced motion in tests: animations snap, so assertions don't race timers.
beforeEach(() => {
  window.matchMedia = ((q: string) => ({ matches: q.includes("reduce"), media: q, onchange: null, addListener() {}, removeListener() {}, addEventListener() {}, removeEventListener() {}, dispatchEvent: () => false })) as unknown as typeof window.matchMedia;
});

const wrap = (ui: ReactNode) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(<QueryClientProvider client={qc}><ToastProvider>{ui}</ToastProvider></QueryClientProvider>);
};

describe("FraudGauge", () => {
  it("exposes the value as an accessible meter and clamps out-of-range input", () => {
    const { rerender } = render(<FraudGauge value={72.4} level="HIGH" />);
    const meter = screen.getByRole("meter", { name: /fraud probability/i });
    expect(meter).toHaveAttribute("aria-valuenow", "72");
    expect(screen.getByText("HIGH")).toBeInTheDocument();
    rerender(<FraudGauge value={250} />);
    expect(screen.getByRole("meter")).toHaveAttribute("aria-valuenow", "100");
  });
});

describe("ShapBars", () => {
  it("shows signed log-odds contributions and labels, hiding the value of one-hot category factors", () => {
    render(<ShapBars factors={FACTORS} />);
    expect(screen.getByText("Transactions in last 5 minutes")).toBeInTheDocument();
    expect(screen.getByText("+1.62")).toBeInTheDocument();
    expect(screen.getByText("-0.30")).toBeInTheDocument();
    expect(screen.getByText("Category is Food").textContent).toBe("Category is Food"); // no "= 1" noise
    expect(screen.getAllByRole("listitem")).toHaveLength(3);
  });
  it("handles an empty explanation", () => {
    render(<ShapBars factors={[]} />);
    expect(screen.getByText(/no attribution/i)).toBeInTheDocument();
  });
});

describe("TransactionRow", () => {
  const flagged = tx({ id: "t1", description: "Probe purchase", fraud_score: 88, risk_level: "CRITICAL", is_flagged: true, fraud_factors: FACTORS });

  it("expands an expense into ML diagnostics with the gauge and SHAP bars", async () => {
    render(<ul><TransactionRow tx={flagged} onDelete={vi.fn()} /></ul>);
    expect(screen.queryByText(/ML Fraud Diagnostics/i)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Probe purchase/ }));
    expect(await screen.findByText(/ML Fraud Diagnostics/i)).toBeInTheDocument();
    expect(screen.getByRole("meter", { name: /fraud probability/i })).toHaveAttribute("aria-valuenow", "88");
    expect(screen.getByText("+1.62")).toBeInTheDocument();
  });

  it("needs two clicks to delete (accidental clicks are harmless)", async () => {
    const onDelete = vi.fn();
    render(<ul><TransactionRow tx={flagged} onDelete={onDelete} defaultOpen /></ul>);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /click again to delete/i }));
    expect(onDelete).toHaveBeenCalledWith("t1");
  });

  it("income rows are not expandable and never show a risk badge", () => {
    render(<ul><TransactionRow tx={tx({ transaction_type: "income", category: "Salary", description: "Salary", amount: 55000 })} onDelete={vi.fn()} /></ul>);
    expect(screen.queryByRole("button", { expanded: false })).toBeNull();
    expect(screen.getByText("+₹55,000")).toBeInTheDocument();
    expect(screen.queryByText("LOW")).toBeNull();
  });
});

describe("ToolCallCard", () => {
  const ok: ToolStep = { tool: "run_sql_query", ok: true, detail: "SELECT SUM(amount) AS total FROM agent_transactions WHERE category = 'Food' LIMIT 100", row_count: 1, error: null, preview: { columns: ["total"], rows: [[1000]] } };

  it("collapses by default and reveals arguments + JSON result on click", async () => {
    render(<ToolCallCard step={ok} />);
    expect(screen.getByText("1 row returned")).toBeInTheDocument();
    expect(screen.queryByText(/Arguments/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /SQL query/ }));
    expect(await screen.findByText(/Arguments · sql/)).toBeInTheDocument();
    expect(screen.getByText(/"total": 1000/)).toBeInTheDocument();
  });
  it("shows the database error for a failed step", async () => {
    render(<ToolCallCard defaultOpen step={{ ...ok, ok: false, error: 'column "amnt" does not exist', preview: null, row_count: 0 }} />);
    expect(screen.getAllByText(/does not exist/).length).toBeGreaterThan(0);
  });
  it("highlighting never changes the text, and the preview JSON notes truncation", () => {
    const { container } = render(<pre>{highlightSql(ok.detail)}</pre>);
    expect(container.textContent).toBe(ok.detail);
    expect(previewJson({ ...ok, row_count: 9, preview: { columns: ["a"], rows: [[1], [2]] } })).toContain("7 more row(s)");
  });
});

describe("AIChatDrawer", () => {
  it("runs a question through the agent and renders tool cards before the answer", async () => {
    const spy = vi.spyOn(apiModule, "api").mockResolvedValue({
      reply: "You spent **₹1,000** on Food last month.",
      tool_trace: [{ tool: "run_sql_query", ok: true, detail: "SELECT 1", row_count: 1, error: null, preview: { columns: ["total"], rows: [[1000]] } }],
    });
    render(<AIChatDrawer open docked={false} onClose={vi.fn()} onToggleDock={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "How much did I spend on Food last month?" }));
    expect(await screen.findByText(/You spent/)).toBeInTheDocument();
    expect(screen.getByText("₹1,000").tagName).toBe("STRONG");           // **bold** rendered, never injected as HTML
    expect(screen.getByText("SQL query")).toBeInTheDocument();
    const body = spy.mock.calls[0]![1] as { json: { message: string; chat_history: unknown[] } };
    expect(body.json.message).toBe("How much did I spend on Food last month?");
    expect(body.json.chat_history).toEqual([]);
    spy.mockRestore();
  });

  it("explains a missing server key instead of failing silently", async () => {
    const spy = vi.spyOn(apiModule, "api").mockRejectedValue(new apiModule.ApiError(503, "x"));
    render(<AIChatDrawer open docked={false} onClose={vi.fn()} onToggleDock={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/message the ai advisor/i), "hello{Enter}");
    expect(await screen.findByText(/GROQ_API_KEY is missing/)).toBeInTheDocument();
    spy.mockRestore();
  });

  it("never renders model output as HTML", async () => {
    const spy = vi.spyOn(apiModule, "api").mockResolvedValue({ reply: "<img src=x onerror=alert(1)> hi", tool_trace: [] });
    const { container } = render(<AIChatDrawer open docked={false} onClose={vi.fn()} onToggleDock={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/message the ai advisor/i), "x{Enter}");
    await screen.findByText(/hi$/);
    expect(container.querySelector("img")).toBeNull();
    spy.mockRestore();
  });
});

describe("Dashboard", () => {
  it("renders KPIs from the ledger and surfaces flagged transactions", async () => {
    const now = new Date().toISOString();
    const rows = [
      tx({ transaction_type: "income", category: "Salary", description: "Salary", amount: 55_000, occurred_at: now }),
      tx({ amount: 10_000, description: "Big spend", occurred_at: now }),
      tx({ amount: 777, description: "Probe", is_flagged: true, risk_level: "CRITICAL", fraud_score: 91, occurred_at: now, fraud_factors: FACTORS }),
    ];
    vi.spyOn(apiModule, "api").mockResolvedValue(rows);
    wrap(<Dashboard onAdd={vi.fn()} goTo={vi.fn()} />);
    expect(await screen.findByText("Monthly inflow")).toBeInTheDocument();
    expect(screen.getByText("Active fraud flags")).toBeInTheDocument();
    expect(screen.getByLabelText(/Threat level: High threat/)).toBeInTheDocument();
    expect(screen.getByText("Probe")).toBeInTheDocument();
    expect(screen.getByLabelText(/Monthly inflow: ₹55,000/)).toBeInTheDocument();
    vi.restoreAllMocks();
  });

  it("offers a clear first action when the ledger is empty", async () => {
    vi.spyOn(apiModule, "api").mockResolvedValue([]);
    const onAdd = vi.fn();
    wrap(<Dashboard onAdd={onAdd} goTo={vi.fn()} />);
    await userEvent.click(await screen.findByRole("button", { name: /add your first transaction/i }));
    expect(onAdd).toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});

describe("AddTransactionPanel", () => {
  it("asks the model for a read-only preview as you type, then shows the recorded verdict on submit", async () => {
    const factors = FACTORS;
    const spy = vi.spyOn(apiModule, "api").mockImplementation(async (path: string) => {
      if (path === "/transaction/preview") return { fraud_score: 41.5, risk_level: "MEDIUM", is_flagged: false, risk_factors: factors, degraded: false };
      if (path === "/transaction/add") return { id: "new", fraud_score: 44, risk_level: "MEDIUM", is_flagged: false, risk_factors: factors, model_version: "v1", degraded: false };
      return [];
    });
    wrap(<AddTransactionPanel open onClose={vi.fn()} />);
    const submit = screen.getByRole("button", { name: /add transaction/i });
    expect(submit).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Amount"), "8999");
    await userEvent.type(screen.getByLabelText("Description"), "Amazon order");
    await waitFor(() => expect(spy).toHaveBeenCalledWith("/transaction/preview", expect.anything()), { timeout: 3000 });
    const previewCall = spy.mock.calls.find((c) => c[0] === "/transaction/preview")![1] as { json: { amount: number } };
    expect(previewCall.json.amount).toBe(8999);
    expect(await screen.findByText(/estimate only/i)).toBeInTheDocument();
    await userEvent.click(submit);
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
    expect(spy.mock.calls.filter((c) => c[0] === "/transaction/add")).toHaveLength(1);
    const add = within(screen.getByRole("dialog"));
    expect(add.getByRole("meter")).toHaveAttribute("aria-valuenow", "44");
    vi.restoreAllMocks();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    vi.spyOn(apiModule, "api").mockResolvedValue([]);
    wrap(<AddTransactionPanel open onClose={onClose} />);
    fireEvent.keyDown(window, { key: "Escape" });
    expect(onClose).toHaveBeenCalled();
    vi.restoreAllMocks();
  });
});
