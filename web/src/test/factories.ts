import type { Transaction } from "@/types";

let n = 0;
/** Build a Transaction with sensible defaults. */
export function tx(o: Partial<Transaction> = {}): Transaction {
  return {
    id: `tx-${n++}`, description: "Swiggy", merchant: null, amount: 450, category: "Food", transaction_type: "expense",
    occurred_at: "2026-10-10T08:00:00Z", fraud_score: 3, risk_level: "LOW", is_flagged: false, fraud_factors: null, is_anomaly: false, ...o,
  };
}

export const FACTORS = [
  { feature: "tx_count_5m", label: "Transactions in last 5 minutes", value: 9, contribution: 1.62, direction: "increases_risk" as const },
  { feature: "amount", label: "Transaction amount", value: 35, contribution: 0.41, direction: "increases_risk" as const },
  { feature: "cat_Food", label: "Category is Food", value: 1, contribution: -0.3, direction: "decreases_risk" as const },
];
