/** Server-state hooks (TanStack Query). Components never call fetch directly. */
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "./api";
import type {
  AddTransactionResult, AnomalyReport, Budget, Category, ForecastResponse, NewTransaction, RiskPreview, Transaction, TransactionType,
} from "@/types";

export const qk = {
  transactions: ["transactions"] as const,
  budgets: ["budgets"] as const,
  anomalies: ["anomalies"] as const,
  forecast: ["forecast"] as const,
};

const PAGE = 200;
const MAX_ROWS = 1000;

/** The API caps a page at 200 rows; walk the pages (newest first) up to MAX_ROWS. */
export async function fetchAllTransactions(signal?: AbortSignal): Promise<Transaction[]> {
  const out: Transaction[] = [];
  while (out.length < MAX_ROWS) {
    const page = await api<Transaction[]>(`/transactions/me?limit=${PAGE}&offset=${out.length}`, { signal });
    out.push(...page);
    if (page.length < PAGE) break;
  }
  return out;
}

export const useTransactions = () =>
  useQuery({ queryKey: qk.transactions, queryFn: ({ signal }) => fetchAllTransactions(signal), refetchInterval: 30_000 });

export function useAddTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (tx: NewTransaction) => api<AddTransactionResult>("/transaction/add", { method: "POST", json: tx }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.transactions });
      void qc.invalidateQueries({ queryKey: qk.budgets });
    },
  });
}

/** Optimistic delete: the row leaves the list immediately and comes back if the server refuses. */
export function useDeleteTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/transaction/${id}`, { method: "DELETE" }),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: qk.transactions });
      const previous = qc.getQueryData<Transaction[]>(qk.transactions);
      qc.setQueryData<Transaction[]>(qk.transactions, (old) => old?.filter((t) => t.id !== id));
      return { previous };
    },
    onError: (_e, _id, ctx) => { if (ctx?.previous) qc.setQueryData(qk.transactions, ctx.previous); },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: qk.transactions });
      void qc.invalidateQueries({ queryKey: qk.budgets });
    },
  });
}

export const useBudgets = () => useQuery({ queryKey: qk.budgets, queryFn: ({ signal }) => api<Budget[]>("/budgets/me", { signal }) });

export function useSetBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { category: Category; limit_amount: number }) => api("/budget/set", { method: "POST", json: b }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.budgets }),
  });
}

export const useAnomalies = () => useQuery({ queryKey: qk.anomalies, queryFn: ({ signal }) => api<AnomalyReport>("/anomalies/me", { signal }) });

/** The API answers 202 {status:"pending"} while a background job computes the forecast: poll until it's ready. */
export const useForecast = () =>
  useQuery({
    queryKey: qk.forecast,
    queryFn: ({ signal }) => api<ForecastResponse>("/forecast/me", { signal }),
    refetchInterval: (q) => (q.state.data?.status === "pending" ? 4_000 : false),
  });

export function useRefreshAnalytics() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/analytics/refresh", { method: "POST" }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: qk.forecast });
      setTimeout(() => void qc.invalidateQueries({ queryKey: qk.anomalies }), 5_000);
    },
  });
}

export interface PreviewDraft { amount: number; category: Category; transaction_type: TransactionType; description: string }

/** Live "what would the model say" estimate. Read-only on the server: nothing is stored or recorded. */
export function usePreview(draft: PreviewDraft, enabled: boolean) {
  return useQuery({
    queryKey: ["preview", draft.amount, draft.category, draft.transaction_type] as const,
    queryFn: ({ signal }) =>
      api<RiskPreview>("/transaction/preview", {
        method: "POST", signal,
        json: { description: draft.description.trim() || "preview", amount: draft.amount, category: draft.category, transaction_type: draft.transaction_type },
      }),
    enabled: enabled && draft.amount > 0,
    placeholderData: keepPreviousData,
    staleTime: 0, gcTime: 30_000, retry: false,
  });
}
