/**
 * Domain types. They mirror the FastAPI response schemas (backend/schemas.py) 1:1, so a rename on the
 * server shows up here as a compile error instead of a runtime surprise.
 */

export const CATEGORIES = [
  "Food", "Transport", "Shopping", "Entertainment", "Bills", "Health", "Education", "Salary", "Investment", "Other",
] as const;
export type Category = (typeof CATEGORIES)[number];
/** Categories a budget can be set for (income categories excluded). */
export const BUDGET_CATEGORIES = CATEGORIES.filter((c) => c !== "Salary" && c !== "Investment") as readonly Category[];

export type TransactionType = "income" | "expense";
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
/** Session-level threat indicator derived from recent flagged activity (see lib/risk.ts). */
export type ThreatLevel = "clear" | "moderate" | "high";

export interface User {
  id: string;
  username: string;
  email: string;
}

/**
 * One TreeSHAP attribution for a scored transaction. `contribution` is in LOG-ODDS of the raw model:
 * positive pushes toward fraud, negative away. The API returns only the top 3 drivers.
 */
export interface SHAPValue {
  feature: string;
  label: string;
  value: number;
  contribution: number;
  direction: "increases_risk" | "decreases_risk";
}

export interface Transaction {
  id: string;
  description: string;
  merchant: string | null;
  amount: number;
  category: Category;
  transaction_type: TransactionType;
  occurred_at: string; // ISO-8601, UTC
  fraud_score: number; // 0..100, calibrated probability
  risk_level: RiskLevel;
  is_flagged: boolean;
  fraud_factors: SHAPValue[] | null;
  is_anomaly: boolean;
}

export interface NewTransaction {
  description: string;
  merchant?: string;
  amount: number;
  category: Category;
  transaction_type: TransactionType;
}

export interface AddTransactionResult {
  id: string;
  fraud_score: number;
  risk_level: RiskLevel;
  is_flagged: boolean;
  risk_factors: SHAPValue[];
  model_version: string | null;
  /** true when Redis velocity features were unavailable and neutral defaults were used. */
  degraded: boolean;
}

/** What the model would say right now. Nothing is stored. */
export interface RiskPreview {
  fraud_score: number;
  risk_level: RiskLevel;
  is_flagged: boolean;
  risk_factors: SHAPValue[];
  degraded: boolean;
}

export interface Budget {
  category: Category;
  month: string; // YYYY-MM
  limit_amount: number;
  spent_amount: number;
  percent_used: number;
  over_budget: boolean;
}

/** Aggregates behind the "Active Fraud Flags" card and the global threat pulse. */
export interface FraudMetrics {
  flaggedCount: number;
  criticalCount: number;
  amountAtRisk: number;
  avgScore: number;
  recentFlagged: number;
  recentCritical: number;
  threat: ThreatLevel;
}

export interface Anomaly {
  id: string;
  description: string;
  amount: number;
  category: Category;
  occurred_at: string;
  anomaly_score: number;
  method: string;
  reason: string;
}

export interface AnomalyReport {
  status: "ok" | "pending" | "insufficient_data";
  method: "isolation_forest" | "mad" | null;
  scored_at: string | null;
  expense_count: number;
  min_required: number;
  anomalies: Anomaly[];
  message: string | null;
}

export interface ForecastWeek {
  week_start: string;
  mean: number;
  lo80: number;
  hi80: number;
  lo95: number;
  hi95: number;
}

export type ForecastResponse =
  | { status: "pending" }
  | { status: "insufficient_data"; history_weeks: number; min_required_weeks: number }
  | {
      status: "ok";
      model: string;
      interval_method: "conformal" | "parametric";
      history_weeks: number;
      weekly: ForecastWeek[];
      total_next_4_weeks: number;
      computed_at?: string;
    };

/** One tool invocation the AI advisor made, with the first rows of its result. */
export interface ToolStep {
  tool: "run_sql_query" | "semantic_search_transactions" | (string & {});
  ok: boolean;
  /** The SQL that ran, or the semantic query. */
  detail: string;
  row_count: number;
  error: string | null;
  preview: { columns: string[]; rows: unknown[][] } | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  steps?: ToolStep[];
  /** Waiting for the API. */
  pending?: boolean;
  error?: boolean;
  /** Play the tool-step + typewriter reveal (only for messages that just arrived). */
  animate?: boolean;
}

export interface ChatResponse {
  reply: string;
  tool_trace: ToolStep[];
}
